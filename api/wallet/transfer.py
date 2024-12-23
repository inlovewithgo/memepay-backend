from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..main import send_sol

router = APIRouter(
    prefix="/api/wallet",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}},
)

class TransferRequest(BaseModel):
    sender_private_key: str
    receiver_address: str
    amount: float

@router.post("/wallet/transfer")
async def transfer_sol(request: TransferRequest):
    try:
        transaction_hash = send_sol(
            src_key=request.sender_private_key,
            dest_addr=request.receiver_address,
            amt_sol=request.amount
        )
        return {"status": "success", "transaction_hash": transaction_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))