from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from solders.keypair import Keypair # type: ignore
from solana.rpc.api import Client
from solders.pubkey import Pubkey as Pubkey # type: ignore
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (
    transfer_checked,
    TransferCheckedParams,
    get_associated_token_address
)
import aiohttp
import json
from datetime import datetime
import pytz
from solana.rpc.types import TokenAccountOpts
import time

from utility.dataconfig import Config
from ..main import create_assoc_tkn_acct, SolanaTransactionManager, get_tkn_acct

router = APIRouter(
    prefix="/api/wallet",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)

class SendTokenRequest(BaseModel):
    src_key: str
    tkn_addr: str
    dest_addr: str
    tkn_amt: float

async def send_discord_webhook(transaction_details: dict):
    """Send transaction details to Discord channel via webhook."""
    webhook_url = "https://discord.com/api/webhooks/1320821148182905004/kWcbaBokaJMUSv2u3fduRVooYWQ9eeQPY5xma7-w5an4SNyXftBNJ8koH7g_pFlIovw9"  # Add this to your Config class
    
    embed = {
        "title": "New Token Transfer",
        "color": 3447003,  
        "fields": [
            {
                "name": "Transaction Hash",
                "value": transaction_details["transaction_hash"],
                "inline": False
            },
            {
                "name": "Amount",
                "value": str(transaction_details["amount"]),
                "inline": True
            },
            {
                "name": "Token",
                "value": transaction_details["token_address"],
                "inline": True
            },
            {
                "name": "Destination",
                "value": transaction_details["destination"],
                "inline": True
            }
        ],
        "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
    }
    
    webhook_data = {
        "embeds": [embed]
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(webhook_url, json=webhook_data) as response:
                if response.status != 204:
                    print(f"Failed to send Discord webhook: {await response.text()}")
        except Exception as e:
            print(f"Error sending Discord webhook: {str(e)}")

@router.post("/send_token")
async def send_tkn(request: SendTokenRequest):
    try:
        src_keypair = Keypair.from_base58_string(request.src_key)
        tkn_pubkey = Pubkey.from_string(request.tkn_addr)
        dest_pubkey = Pubkey.from_string(request.dest_addr)
        manager = SolanaTransactionManager(Config.RPC_URL)
        
        src_tkn_data = get_tkn_acct(src_keypair.pubkey(), tkn_pubkey)
        if not src_tkn_data['tkn_acct_pubkey']:
            raise HTTPException(status_code=400, detail="Source account does not have that token")

        dest_tkn_data = get_tkn_acct(dest_pubkey, tkn_pubkey)
        
        dest_tkn_acct_pubkey = (
            dest_tkn_data['tkn_acct_pubkey'] if dest_tkn_data['tkn_acct_pubkey']
            else create_assoc_tkn_acct(src_keypair, dest_pubkey, tkn_pubkey)
        )
        
        time.sleep(15)
        
        txn = manager.get_transaction_builder(src_keypair.pubkey())
        send_amt_lamps = int(request.tkn_amt * 10 ** int(src_tkn_data['tkn_dec']))
        txn.add(transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=src_tkn_data['tkn_acct_pubkey'],
                mint=tkn_pubkey,
                dest=Pubkey.from_string(str(dest_tkn_acct_pubkey)),
                owner=src_keypair.pubkey(),
                amount=send_amt_lamps,
                decimals=src_tkn_data['tkn_dec'],
            )
        ))
        txn.sign(src_keypair)
        txn_hash = manager.send_transaction(txn)
        transaction_details = {
            "transaction_hash": txn_hash,
            "amount": request.tkn_amt,
            "token_address": request.tkn_addr,
            "destination": request.dest_addr
        }
        await send_discord_webhook(transaction_details)
        return {"status": "success", "transaction_hash": txn_hash}
    except KeyError as ke:
        raise HTTPException(status_code=400, detail=f"Missing key: {str(ke)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
