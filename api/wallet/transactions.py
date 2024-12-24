from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from datetime import datetime
import pytz
from typing import List, Optional
from utility.logger import logger
import time

router = APIRouter(
    prefix="/api/wallet",
    tags=["Transactions"],
    responses={404: {"description": "Not found"}},
)

class TransactionRequest(BaseModel):
    wallet_address: str
    limit: int = 10

class TransactionResponse(BaseModel):
    signature: str
    block_time: Optional[int]
    type: str
    status: str
    amount: float
    token_address: Optional[str]
    from_address: str
    to_address: str
    timestamp: Optional[str]

@router.post("/transactions")
async def get_transactions(request: TransactionRequest):
    try:
        logger.info(f"Processing transaction request for wallet: {request.wallet_address}")
        
        client = Client("https://api.mainnet-beta.solana.com")
        try:
            pubkey = Pubkey.from_string(request.wallet_address)
        except ValueError as ve:
            logger.error(f"Invalid wallet address: {request.wallet_address}")
            raise HTTPException(status_code=400, detail="Invalid wallet address.")
        
        response = client.get_signatures_for_address(pubkey, limit=request.limit)
        
        if not response or not response.value:
            logger.info(f"No transactions found for wallet: {request.wallet_address}")
            return {"status": "success", "transactions": []}
        
        transactions = []
        for sig_info in response.value:
            max_retries = 3
            retry_delay = 1  # seconds
            for attempt in range(max_retries):
                try:
                    tx_response = client.get_transaction(
                        sig_info.signature,
                        encoding="jsonParsed",
                        max_supported_transaction_version=0
                    )
                    
                    if not tx_response or not tx_response.value:
                        logger.warning(f"Transaction {sig_info.signature} not found")
                        break
                    
                    tx = tx_response.value
                    meta = tx.transaction.meta
                    message = tx.transaction.transaction.message
                    
                    if not meta or not message or not message.account_keys:
                        logger.warning(f"Incomplete transaction data for {sig_info.signature}")
                        break
                    
                    pre_balances = meta.pre_balances if meta else []
                    post_balances = meta.post_balances if meta else []
                    accounts = message.account_keys
                    
                    tx_type = "Unknown"
                    amount = 0.0
                    token_address = None
                    
                    for instruction in message.instructions:
                        program_id = str(instruction.program_id)
                        
                        if program_id == "11111111111111111111111111111111":
                            tx_type = "SOL Transfer"
                            if len(pre_balances) > 0 and len(post_balances) > 0:
                                amount = abs(post_balances[0] - pre_balances[0]) / 1e9
                        elif program_id == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA":
                            tx_type = "Token Transfer"
                            if hasattr(instruction, 'parsed') and instruction.parsed:
                                parsed_data = instruction.parsed
                                if isinstance(parsed_data, dict) and 'info' in parsed_data:
                                    amount = float(parsed_data['info'].get('amount', 0)) / 1e9
                                    token_address = parsed_data['info'].get('mint')
                    
                    transactions.append(TransactionResponse(
                        signature=str(sig_info.signature),
                        block_time=tx.block_time,
                        type=tx_type,
                        status="success" if not meta.err else "failed",
                        amount=amount,
                        token_address=token_address,
                        from_address=str(accounts[0]),
                        to_address=str(accounts[1]) if len(accounts) > 1 else "",
                        timestamp=datetime.fromtimestamp(
                            tx.block_time, pytz.timezone('Asia/Kolkata')
                        ).isoformat() if tx.block_time else None
                    ))
                    break  # Successfully processed, exit retry loop
                except Exception as tx_error:
                    logger.error(f"Error processing transaction {sig_info.signature}: {tx_error}")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Max retries reached for transaction {sig_info.signature}")
        
        return {"status": "success", "transactions": transactions}
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch transactions: {str(e)}"
        )
