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
from enum import Enum
from fastapi import HTTPException
from solders.transaction import VersionedTransaction # type: ignore
from solders import message
from datetime import datetime
import re
from pytz import timezone
import httpx

from utility.logger import logger

class SolanaTransactionError(str, Enum):
    INSUFFICIENT_LAMPORTS = "Insufficient SOL balance for transaction fees"
    TRANSFER_FAILED = "Transfer failed due to insufficient lamports"
    INSTRUCTION_ERROR = "Error processing transaction instruction"
    SIMULATION_FAILED = "Transaction simulation failed"
    INVALID_INSTRUCTION = "Invalid transaction instruction"
    COMPUTE_BUDGET_EXCEEDED = "Compute budget exceeded"
    TOKEN_ACCOUNT_SETUP_FAILED = "Token account setup failed"

def parse_simulation_error(error_logs: list) -> tuple[str, dict]:
    error_details = {
        "compute_units_consumed": None,
        "required_lamports": None,
        "available_lamports": None
    }
    
    for log in error_logs:
        if "Transfer: insufficient lamports" in log:
            parts = log.split("insufficient lamports")[1].split(",")
            if len(parts) >= 2:
                available = parts[0].strip()
                needed = parts[1].split("need")[1].strip()
                error_details["available_lamports"] = int(available)
                error_details["required_lamports"] = int(needed)
                return SolanaTransactionError.TRANSFER_FAILED, error_details
        elif "consumed" in log and "compute units" in log:
            units = log.split("consumed")[1].split("of")[0].strip()
            error_details["compute_units_consumed"] = int(units)
            return SolanaTransactionError.SIMULATION_FAILED, error_details

def handle_transaction_error(e: Exception) -> HTTPException:
    error_message = str(e)
    
    if "Transaction simulation failed" in error_message:
        try:
            error_data = e.args[0]
            if "insufficient funds for rent" in error_message.lower():
                return HTTPException(
                    status_code=400,
                    detail={
                        "code": "INSUFFICIENT_RENT",
                        "message": "Account has insufficient SOL to maintain minimum required balance (rent). Add more SOL to your wallet to cover rent requirement.",
                        "minimum_required": "0.0028 SOL"  # Minimum for token accounts
                    }
                )
            elif hasattr(error_data, 'data') and hasattr(error_data.data, 'logs'):
                error_type, details = parse_simulation_error(error_data.data.logs)
                if error_type == SolanaTransactionError.TRANSFER_FAILED:
                    return HTTPException(
                        status_code=400,
                        detail={
                            "code": "INSUFFICIENT_FUNDS",
                            "message": "Insufficient funds for transaction",
                            "available": details["available_lamports"],
                            "required": details["required_lamports"]
                        }
                    )
        except Exception:
            pass

    error_mapping = {
        "insufficient lamports": {
            "code": "INSUFFICIENT_BALANCE",
            "message": "Insufficient SOL balance for transaction fees"
        },
        "custom program error: 0x1": {
            "code": "INSTRUCTION_ERROR",
            "message": "Failed to process transaction instruction"
        },
        "compute budget exceeded": {
            "code": "COMPUTE_BUDGET_EXCEEDED",
            "message": "Transaction exceeded compute budget"
        }
    }

    for error_pattern, error_info in error_mapping.items():
        if error_pattern in error_message.lower():
            return HTTPException(
                status_code=400,
                detail=error_info
            )

    return HTTPException(
        status_code=500,
        detail={
            "code": "TRANSACTION_FAILED",
            "message": error_message
        }
    )

async def handle_token_account_setup(keypair, to_token_pubkey):
    try:
        to_token_account = get_tkn_acct(keypair.pubkey(), to_token_pubkey)
        if not to_token_account['tkn_acct_pubkey']:
            logger.info("Creating new associated token account")
            create_assoc_tkn_acct(keypair, keypair.pubkey(), to_token_pubkey)
    except Exception as e:
        logger.error(f"Token account setup failed: {str(e)}")
        error_data = e.args[0] if e.args else None
        
        if hasattr(error_data, 'data') and hasattr(error_data.data, 'logs'):
            error_type, details = parse_simulation_error(error_data.data.logs)
            if error_type == SolanaTransactionError.TRANSFER_FAILED:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": SolanaTransactionError.TOKEN_ACCOUNT_SETUP_FAILED.value,
                        "available": details["available_lamports"],
                        "required": details["required_lamports"]
                    }
                )
        
        raise HTTPException(
            status_code=500,
            detail={"error": SolanaTransactionError.TOKEN_ACCOUNT_SETUP_FAILED.value}
        )
    
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
    
async def send_discord_webhook(transaction_data: dict):
    """Send transaction notification to Discord webhook"""
    embed = {
        "title": "New Swap Transaction",
        "color": 3066993,  # Green color
        "fields": [
            {
                "name": "Transaction ID",
                "value": f"[{transaction_data['transaction_id']}]({transaction_data['transaction_url']})",
                "inline": False
            },
            {
                "name": "Status",
                "value": transaction_data['status'].capitalize(),
                "inline": True
            },
            {
                "name": "Time",
                "value": datetime.now(timezone('Asia/Kolkata')).strftime("%Y-%m-%d %H:%M:%S IST"),
                "inline": True
            }
        ],
        "footer": {
            "text": "Solana Swap"
        }
    }

    webhook_data = {
        "embeds": [embed]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "",
                json=webhook_data,
                timeout=5
            ) as response:
                if response.status != 204:
                    logger.error(f"Failed to send Discord webhook: {await response.text()}")
                else:
                    logger.info("Discord webhook sent successfully")
    except Exception as e:
        logger.error(f"Error sending Discord webhook: {str(e)}")


@router.post("/swap")
async def perform_swap(request: SwapRequest):
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
            await handle_token_account_setup(keypair, to_token_pubkey)

        # Quote fetching with detailed error handling
        try:
            decimals = manager.get_spl_token_decimals(data['from_token'])
            if decimals is None:
                raise ValueError("Failed to fetch token decimals")

            slippage_bps = int(float(data['slippage']) * 100)
            amount_in_smallest_unit = str(int(float(data['amount']) * 10 ** decimals))

            quote_params = {
                'inputMint': data['from_token'],
                'outputMint': data['to_token'],
                'amount': amount_in_smallest_unit,
                'slippageBps': str(slippage_bps)
            }

            async with aiohttp.ClientSession() as session:
                async with session.get('https://quote-api.jup.ag/v6/quote', params=quote_params, timeout=10) as response:
                    if response.status != 200:
                        error_body = await response.text()
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
                async with session.post('https://quote-api.jup.ag/v6/swap', json=swap_payload, timeout=10) as response:
                    if response.status != 200:
                        error_body = await response.text()
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Jupiter swap API error: {error_body}"
                        )
                    swap_data = await response.json()

            raw_transaction = VersionedTransaction.from_bytes(base64.b64decode(swap_data['swapTransaction']))
            signature = keypair.sign_message(message.to_bytes_versioned(raw_transaction.message))
            signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])
            
            result = manager.send_swap(signed_txn)
            transaction_id = json.loads(result.to_json())['result']
            
            transaction_data = {
                "status": "success",
                "transaction_id": transaction_id,
                "transaction_url": f"https://solscan.io/tx/{transaction_id}"
            }
            
            await send_discord_webhook(transaction_data)
            return transaction_data

        except aiohttp.ClientError as e:
            logger.error(f"Swap API network error: {str(e)}")
            raise HTTPException(status_code=503, detail="Jupiter API is currently unavailable")
        except Exception as e:
            logger.error(f"Swap execution failed: {str(e)}\n{traceback.format_exc()}")
            raise handle_transaction_error(e)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        raise handle_transaction_error(e)
    finally:
        if keypair:
            del keypair
        if 'private_key' in data:
            del data['private_key']
