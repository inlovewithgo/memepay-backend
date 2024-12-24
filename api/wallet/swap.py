from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import transfer_checked, TransferCheckedParams
from utility.dataconfig import Config
from utility.create_acc import JupiterReferralAPI
from ..main import create_assoc_tkn_acct, SolanaTransactionManager, get_tkn_acct
from spl.token._layouts import MINT_LAYOUT
from solana.rpc.api import Client
import aiohttp
import base64
import json
import time
import traceback
from solders.transaction import VersionedTransaction
from solders import message
from utility.logger import logger

def get_token_decimals(token_address):
    try:
        http_client = Client("https://api.mainnet-beta.solana.com")
        addr = Pubkey.from_string(token_address)
        info = http_client.get_account_info(addr)
        return MINT_LAYOUT.parse(info.value.data).decimals
    except Exception as e:
        logger.error(f"Error fetching token decimals: {str(e)}")
        return None

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

@router.post("/swap")
async def perform_swap(request: SwapRequest):
    try:
        manager = SolanaTransactionManager(Config.RPC_URL)
        logger.info("Starting swap operation")
        data = request.dict()

        # Validate request data
        required_fields = ['private_key', 'from_token', 'to_token', 'amount']
        if not isinstance(data, dict):
            logger.error("Invalid request format received")
            raise HTTPException(status_code=400, detail="Invalid request format")

        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Missing required fields in request: {missing_fields}")
            raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing_fields)}")

        # Validate amount
        try:
            amount = float(data['amount'])
            if amount <= 0:
                logger.error(f"Invalid amount received: {amount}")
                raise HTTPException(status_code=400, detail="Amount must be positive")
        except ValueError:
            logger.error("Invalid amount format in request")
            raise HTTPException(status_code=400, detail="Invalid amount format")

        # Validate private key
        if not isinstance(data['private_key'], str):
            logger.error("Invalid private key format: not a string")
            raise HTTPException(status_code=400, detail="Private key must be a string")

        try:
            logger.info("Validating keypair")
            keypair = Keypair.from_base58_string(data['private_key'])
            data['private_key'] = None
            logger.info("Keypair validation successful")
        except Exception as e:
            logger.error(f"Invalid private key format: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid private key format")

        # Validate token addresses
        try:
            logger.info("Validating token addresses")
            from_token_pubkey = Pubkey.from_string(data['from_token'])
            to_token_pubkey = Pubkey.from_string(data['to_token'])
            logger.info("Token address validation successful")
        except Exception as e:
            logger.error(f"Invalid token address format: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid token address format")

        # Setup token accounts
        try:
            logger.info("Setting up token accounts")
            if str(to_token_pubkey) != "So11111111111111111111111111111111111111112":
                to_token_account = get_tkn_acct(keypair.pubkey(), to_token_pubkey)
                if not to_token_account['tkn_acct_pubkey']:
                    logger.info("Creating new associated token account")
                    create_assoc_tkn_acct(keypair, keypair.pubkey(), to_token_pubkey)
        except Exception as e:
            logger.error(f"Token account creation failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to setup token account")

        # Setup referral accounts
        try:
            logger.info("Setting up referral accounts")
            api = JupiterReferralAPI()
            existing_mints = await get_existing_mints()
            sendkey = Keypair.from_base58_string(Config.FEE_PRIVATE_KEY)

            if str(from_token_pubkey) not in existing_mints:
                logger.info(f"Creating referral for from_token: {str(from_token_pubkey)}")
                from_referral = api.create_token_account(
                    referral_pubkey=Config.FEE_KEY,
                    mint=str(from_token_pubkey),
                    fee_payer=Config.FEE_RECIPIENT
                )
                api.send_tx(txn=from_referral, keypair=sendkey)
                await add_mint_to_file(str(from_token_pubkey))

            if str(to_token_pubkey) not in existing_mints:
                logger.info(f"Creating referral for to_token: {str(to_token_pubkey)}")
                to_referral = api.create_token_account(
                    referral_pubkey=Config.FEE_KEY,
                    mint=str(to_token_pubkey),
                    fee_payer=Config.FEE_RECIPIENT
                )
                api.send_tx(txn=to_referral, keypair=sendkey)
                await add_mint_to_file(str(to_token_pubkey))
        except Exception as e:
            logger.error(f"Referral setup failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to setup referral accounts")

        time.sleep(2)

        # Fetch quote
        try:
            logger.info("Fetching quote")
            quote_url = 'https://quote-api.jup.ag/v6/quote'
            decimals = get_token_decimals(data['from_token'])
            if decimals is None:
                raise HTTPException(status_code=500, detail="Failed to fetch token decimals")

            quote_params = {
                'inputMint': data['from_token'],
                'outputMint': data['to_token'],
                'amount': str(int(float(data['amount']) * 10 ** decimals)),
                'slippageBps': '100',
                'platformFeeBps': '20'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(quote_url, params=quote_params, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Quote API returned status {response.status}")
                        raise HTTPException(status_code=500, detail="Failed to get quote")
                    quote_response = await response.json()
                    logger.info("Quote fetched successfully")
        except Exception as e:
            logger.error(f"Quote API call failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch quote")

        # Calculate fee account
        try:
            logger.info("Calculating referral fee account")
            seeds = [
                b"referral_ata",
                bytes(Pubkey.from_string("3cnbobTC5P1oBinqZsDkSpX2AJX8qLy68RLYgexSisrA")),
                bytes(to_token_pubkey)
            ]
            referral_program_id = Pubkey.from_string("REFER4ZgmyYx9c6He5XfaTMiGfdLwRnkV4RPp9t9iF3")
            fee_account, _ = Pubkey.find_program_address(seeds, referral_program_id)
            logger.info("Fee account calculated successfully")
        except Exception as e:
            logger.error(f"Fee account calculation failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to calculate fee account")

        # Execute swap
        logger.info("Initiating swap")
        swap_url = 'https://quote-api.jup.ag/v6/swap'
        swap_payload = {
            'userPublicKey': str(keypair.pubkey()),
            'quoteResponse': quote_response,
            'wrapAndUnwrapSol': True,
            'prioritizationFeeLamports': 500000,
            'feeAccount': str(fee_account),
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(swap_url, json=swap_payload, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Swap API returned status {response.status}")
                        raise HTTPException(status_code=500, detail="Failed to create swap transaction")
                    swap_data = await response.json()
                    logger.info("Swap transaction created successfully")
            except Exception as e:
                logger.error(f"Swap API call failed: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to create swap")

            try:
                logger.info("Processing transaction")
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
            except Exception as e:
                logger.error(f"Transaction signing/submission failed: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to process transaction")

    except Exception as e:
        logger.error(f"Swap failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        logger.info("Cleaning up sensitive data")
        if 'keypair' in locals():
            del keypair
        if 'private_key' in data:
            del data['private_key']

async def get_existing_mints():
    try:
        logger.info("Reading existing mints")
        with open('existing_mints.txt', 'r') as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        logger.warning("existing_mints.txt not found")
        return set()

async def add_mint_to_file(mint: str):
    logger.info(f"Adding new mint to file: {mint}")
    with open('existing_mints.txt', 'a') as f:
        f.write(f"\n{mint}\n")
