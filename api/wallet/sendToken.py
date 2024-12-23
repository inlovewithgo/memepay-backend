from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import transfer_checked, TransferCheckedParams
from typing import Optional
import asyncio
import httpx
from utility.logger import logging
from utility.dataconfig import Config
from ..main import create_assoc_tkn_acct, SolanaTransactionManager, get_tkn_acct

router = APIRouter(
    prefix="/api/wallet",
    tags=["Authentication"]
)


class SendTokenRequest(BaseModel):
    src_key: str
    tkn_addr: str
    dest_addr: str
    tkn_amt: float

    @validator('tkn_amt')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v


async def check_token_balance(src_keypair: Keypair, tkn_pubkey: Pubkey, amount: float) -> bool:
    src_tkn_data = get_tkn_acct(src_keypair.pubkey(), tkn_pubkey)
    
    if not src_tkn_data or not src_tkn_data.get('tkn_acct_pubkey'):
        return False
        
    decimals = int(src_tkn_data['tkn_dec'])
    required_amount = int(amount * (10 ** decimals))
    current_balance = float(src_tkn_data.get('tkn_bal', 0))
    
    return current_balance >= amount



async def check_sol_balance(src_key: str) -> bool:
    try:
        src_keypair = Keypair.from_base58_string(src_key)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                Config.RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getBalance",
                    "params": [str(src_keypair.pubkey())]
                },
                headers={"Content-Type": "application/json"}
            )

            data = response.json()
            if "error" in data:
                logging.error(f"RPC error checking SOL balance: {data['error']}")
                raise HTTPException(
                    status_code=500,
                    detail=f"RPC error: {data['error']['message']}"
                )

            balance_lamports = data["result"].get("value", 0)
            logging.info(f"SOL balance: {balance_lamports} lamports")
            if balance_lamports < 5000:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient SOL balance. Current: {balance_lamports} lamports, Required: 5000 lamports"
                )
            return True

    except Exception as e:
        logging.error(f"Failed to check SOL balance: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check SOL balance: {str(e)}"
        )


@router.post("/send_token")
async def send_tkn(request: SendTokenRequest):
    try:
        logging.info("Starting token transfer process")
        if not request.src_key or len(request.src_key) == 0:
            raise HTTPException(
                status_code=400,
                detail="Private key is missing or invalid"
            )

        try:
            src_keypair = Keypair.from_base58_string(request.src_key)
            tkn_pubkey = Pubkey.from_string(request.tkn_addr)
            dest_pubkey = Pubkey.from_string(request.dest_addr)
            logging.info(f"Token address: {request.tkn_addr}")
            logging.info(f"Destination address: {request.dest_addr}")
        except ValueError as e:
            logging.error(f"Invalid key format: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid key format: {str(e)}"
            )

        # Check balances
        logging.info("Checking balances")
        await check_sol_balance(request.src_key)
        await check_token_balance(src_keypair, tkn_pubkey, request.tkn_amt)

        # Get the transaction manager
        manager = SolanaTransactionManager(Config.RPC_URL)
        logging.info("Created transaction manager")

        # Get recent blockhash
        async with httpx.AsyncClient() as client:
            response = await client.post(
                Config.RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getLatestBlockhash",
                    "params": [{"commitment": "confirmed"}]
                },
                headers={"Content-Type": "application/json"}
            )

            blockhash_data = response.json()
            if "error" in blockhash_data:
                logging.error(f"Blockhash error: {blockhash_data['error']}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get recent blockhash"
                )

            blockhash = blockhash_data["result"]["value"]["blockhash"]
            logging.info(f"Got blockhash: {blockhash}")

        try:
            fee_payer = Keypair.from_base58_string(Config.FEE_PRIVATE_KEY)
            txn = manager.get_transaction_builder(fee_payer.pubkey()) 
            logging.info("Created transaction builder")
        except Exception as e:
            logging.error(f"Error creating transaction: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create transaction: {str(e)}"
            )

        src_tkn_data = get_tkn_acct(src_keypair.pubkey(), tkn_pubkey)
        if not src_tkn_data or not src_tkn_data.get('tkn_acct_pubkey'):
            logging.error("Source token account not found")
            raise HTTPException(
                status_code=400,
                detail="Source token account not found"
            )

        dest_tkn_data = get_tkn_acct(dest_pubkey, tkn_pubkey)
        try:
            dest_tkn_acct_pubkey = (
                dest_tkn_data['tkn_acct_pubkey'] if dest_tkn_data.get('tkn_acct_pubkey')
                else create_assoc_tkn_acct(src_keypair, dest_pubkey, tkn_pubkey)
            )
            logging.info(f"Destination token account: {dest_tkn_acct_pubkey}")
        except Exception as e:
            logging.error(f"Error with destination token account: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to setup destination token account: {str(e)}"
            )

        try:
            decimals = int(src_tkn_data['tkn_dec'])
            send_amt_lamps = int(request.tkn_amt * (10 ** decimals))
            logging.info(f"Amount in lamports: {send_amt_lamps}")

            transfer_ix = transfer_checked(
                TransferCheckedParams(
                    program_id=TOKEN_PROGRAM_ID,
                    source=src_tkn_data['tkn_acct_pubkey'],
                    mint=tkn_pubkey,
                    dest=dest_tkn_acct_pubkey,
                    owner=src_keypair.pubkey(),
                    amount=send_amt_lamps,
                    decimals=decimals
                )
            )

            txn.add(transfer_ix)
            logging.info("Added transfer instruction")

            fee_payer = Keypair.from_base58_string(Config.FEE_PRIVATE_KEY)
        
            txn.sign([src_keypair, fee_payer])
            
            logging.info("Signed transaction")

            max_retries = 3
            retry_delay = 0.5  # seconds

            for attempt in range(max_retries):
                try:
                    txn_hash = manager.send_transaction(txn)
                    logging.info(f"Transaction successful! Hash: {txn_hash}")
                    return {
                        "status": "success",
                        "transaction_hash": txn_hash,
                        "message": "Transaction completed successfully"
                    }
                except Exception as e:
                    if attempt == max_retries - 1:
                        logging.error(f"Final attempt failed: {str(e)}")
                        raise
                    logging.warning(f"Attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(retry_delay)

        except Exception as e:
            logging.error(f"Transaction execution failed: {str(e)}")
            logging.error(f"Transaction details: {txn}")
            raise HTTPException(
                status_code=500,
                detail=f"Transaction failed: {str(e)}"
            )

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
