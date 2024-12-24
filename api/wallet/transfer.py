from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..main import send_sol
import aiohttp
import pytz
from datetime import datetime
from pydantic import BaseModel, validator


router = APIRouter(
    prefix="/api/wallet",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)

class TransferRequest(BaseModel):
    sender_private_key: str
    receiver_address: str
    amount: float

async def send_discord_webhook(transaction_details: dict):
    """Send SOL transfer details to Discord channel via webhook."""
    webhook_url = "https://discord.com/api/webhooks/1320823113747005523/lQpfKBV_qqjOkNwpam_F5z4G4NXCkAMlXc3c-ugRrlD-sHwUGwvj_2MeRjCT4Cup0OLe"
    
    embed = {
        "title": "New SOL Transfer",
        "color": 5793266,  # Green color
        "fields": [
            {
                "name": "Transaction Hash",
                "value": f"`{transaction_details["transaction_hash"]}`",
                "inline": False
            },
            {
                "name": "Amount (SOL)",
                "value": f"`{str(transaction_details["amount"])}`",
                "inline": True
            },
            {
                "name": "Receiver",
                "value": f"`{transaction_details["receiver"]}`",
                "inline": True
            }
        ],
        "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
        "footer": {
            "text": "Solana Network Transaction"
        }
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

@router.post("/transfer")
async def transfer_sol(request: TransferRequest):
    try:
        transaction_hash = send_sol(
            src_key=request.sender_private_key,
            dest_addr=request.receiver_address,
            amt_sol=request.amount
        )
        
        transaction_details = {
            "transaction_hash": transaction_hash,
            "amount": request.amount,
            "receiver": request.receiver_address
        }
        
        await send_discord_webhook(transaction_details)
        
        return {"status": "success", "transaction_hash": transaction_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
