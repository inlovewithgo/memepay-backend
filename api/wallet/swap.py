from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from solders.keypair import Keypair # type: ignore
from solders.pubkey import Pubkey as Pubkey # type: ignore
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import transfer_checked, TransferCheckedParams
from utility.dataconfig import Config
from utility.create_acc import JupiterReferralAPI
from ..main import create_assoc_tkn_acct, SolanaTransactionManager, get_tkn_acct
import aiohttp
import base64
import json
import time
import traceback
from solders.transaction import VersionedTransaction # type: ignore
from solders import message

from utility.logger import logger

router = APIRouter(
    prefix="/api/wallet",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)


class SwapRequest(BaseModel):
    private_key: str
    from_token: str
    to_token: str
    amount: float
    slippage : int

@router.post("/swap")
async def perform_swap(request: SwapRequest):
    # Clear sensitive data in finally block
    keypair = None
    data = request.dict()
    
    try:
        manager = SolanaTransactionManager(Config.RPC_URL)
        logger.info("Starting swap operation")

        # Validate request data
        required_fields = ['private_key', 'from_token', 'to_token', 'amount', 'slippage']
        if not isinstance(data, dict):
            logger.error("Invalid request format received")
            raise HTTPException(status_code=400, detail="Invalid request format")

        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Missing required fields in request: {missing_fields}")
            raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing_fields)}")

        # Amount validation with detailed error
        try:
            amount = float(data['amount'])
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError as e:
            logger.error(f"Amount validation failed: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

        # Slippage validation with detailed error
        try:
            slippage = float(data['slippage'])
            if slippage <= 0:
                raise ValueError("Slippage must be positive")
            if slippage > 100:
                raise ValueError("Slippage cannot exceed 100%")
        except ValueError as e:
            logger.error(f"Slippage validation failed: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

        # Keypair validation with detailed error
        try:
            keypair = Keypair.from_base58_string(data['private_key'])
            data['private_key'] = None  # Clear sensitive data immediately
        except Exception as e:
            logger.error(f"Keypair validation failed: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid private key format")

        # Token address validation
        try:
            from_token_pubkey = Pubkey.from_string(data['from_token'])
            to_token_pubkey = Pubkey.from_string(data['to_token'])
        except Exception as e:
            logger.error(f"Token address validation failed: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid token address: {str(e)}")

        # Token account setup
        if str(to_token_pubkey) != "So11111111111111111111111111111111111111112":
            try:
                to_token_account = get_tkn_acct(keypair.pubkey(), to_token_pubkey)

                if not to_token_account['tkn_acct_pubkey']:
                    logger.info("Creating new associated token account")
                    create_assoc_tkn_acct(keypair, keypair.pubkey(), to_token_pubkey)
            except Exception as e:
                logger.error(f"Token account setup failed: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Token account setup failed: {str(e)}")

        # Quote fetching with detailed error handling
        try:
            decimals = manager.get_spl_token_decimals(data['from_token'])
            if decimals is None:
                raise ValueError("Failed to fetch token decimals")

            # Convert slippage to basis points (bps)
            # Example: 0.5% slippage = 50 basis points
            slippage_bps = int(float(data['slippage']) * 100)  # Convert percentage to basis points
            
            # Format amount based on token decimals - ensure it's an integer string
            amount_in_smallest_unit = str(int(float(data['amount']) * 10 ** decimals))
            
            quote_params = {
                'inputMint': data['from_token'],
                'outputMint': data['to_token'],
                'amount': amount_in_smallest_unit,
                'slippageBps': str(slippage_bps)  # Must be an integer string like "50" for 0.5%
            }
            
            logger.debug(f"Quote request parameters: {quote_params}")  # Add debug logging

            # Build and log the full URL for debugging
            query_string = '&'.join([f"{k}={v}" for k, v in quote_params.items()])
            full_url = f'https://quote-api.jup.ag/v6/quote?{query_string}'
            logger.debug(f"Full quote request URL: {full_url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get('https://quote-api.jup.ag/v6/quote', 
                                     params=quote_params, 
                                     timeout=10) as response:
                    if response.status != 200:
                        error_body = await response.text()
                        logger.error(f"Quote API error: Status {response.status}, Body: {error_body}")
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Jupiter quote API error: {error_body}"
                        )
                    quote_response = await response.json()
                    logger.info("Quote fetched successfully")

        except aiohttp.ClientError as e:
            logger.error(f"Quote API network error: {str(e)}")
            raise HTTPException(status_code=503, detail="Jupiter API is currently unavailable")
        except Exception as e:
            logger.error(f"Quote fetching failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch quote: {str(e)}")

        # Swap execution
        try:
            swap_payload = {
                'userPublicKey': str(keypair.pubkey()),
                'quoteResponse': quote_response,
                'wrapAndUnwrapSol': True,
                'prioritizationFeeLamports': 500000
            }

            async with aiohttp.ClientSession() as session:
                async with session.post('https://quote-api.jup.ag/v6/swap',
                                      json=swap_payload,
                                      timeout=10) as response:
                    if response.status != 200:
                        error_body = await response.text()
                        logger.error(f"Swap API error: Status {response.status}, Body: {error_body}")
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Jupiter swap API error: {error_body}"
                        )
                    swap_data = await response.json()

                # Transaction processing
                raw_transaction = VersionedTransaction.from_bytes(base64.b64decode(swap_data['swapTransaction']))

                signature = keypair.sign_message(message.to_bytes_versioned(raw_transaction.message))
                signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])

                result = manager.send_swap(signed_txn)

                transaction_id = json.loads(result.to_json())['result']
                
                logger.info(f"Transaction completed successfully. ID: {transaction_id}")
                return {
                    "status": "success",
                    "transaction_id": transaction_id,
                    "transaction_url": f"https://solscan.io/tx/{transaction_id}"
                }

        except aiohttp.ClientError as e:
            logger.error(f"Swap API network error: {str(e)}")
            raise HTTPException(status_code=503, detail="Jupiter API is currently unavailable")
        except Exception as e:
            logger.error(f"Swap execution failed: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Swap execution failed: {str(e)}")

    except HTTPException:
        raise  # Re-raise HTTP exceptions without modification
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        # Clean up sensitive data
        if keypair:
            del keypair
        if 'private_key' in data:
            del data['private_key']