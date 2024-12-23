from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
from solana.rpc.core import RPCException
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.system_program import TransferParams, transfer
import httpx
from utility.dataconfig import Config
from utility.logger import logging

router = APIRouter(
    prefix="/api/wallet",
    tags=["Authentication"],
    responses={
        404: {"description": "Not found"},
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"}
    }
)


class TransferRequest(BaseModel):
    sender_private_key: str
    receiver_address: str
    amount: float

    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v


async def check_sol_balance(src_keypair: Keypair, amount: float) -> bool:
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
            raise HTTPException(status_code=500, detail=f"RPC error: {data['error']['message']}")

        balance_lamports = data["result"]["value"]
        required_lamports = int(amount * Config.LAMPORTS_PER_SOL)

        if balance_lamports < required_lamports:
            raise HTTPException(status_code=400, detail="Insufficient SOL balance")
        return True


@router.post("/transfer")
async def transfer_sol(request: TransferRequest):
    try:
        src_keypair = Keypair.from_base58_string(request.sender_private_key)
        dest_pubkey = Pubkey.from_string(request.receiver_address)

        # Check balance
        await check_sol_balance(src_keypair, request.amount)

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
                raise HTTPException(status_code=500, detail="Failed to get recent blockhash")

            blockhash = blockhash_data["result"]["value"]["blockhash"]

        # Create and sign transaction
        transaction = Transaction()
        transaction.recent_blockhash = blockhash

        # Add transfer instruction
        send_amt_lamps = int(request.amount * Config.LAMPORTS_PER_SOL)
        transfer_ix = transfer(TransferParams(
            from_pubkey=src_keypair.pubkey(),
            to_pubkey=dest_pubkey,
            lamports=send_amt_lamps
        ))
        transaction.add(transfer_ix)

        # Sign transaction
        transaction.sign([src_keypair])

        # Send transaction
        serialized_txn = transaction.serialize()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                Config.RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "sendTransaction",
                    "params": [
                        serialized_txn.hex(),
                        {"encoding": "base64", "preflightCommitment": "confirmed"}
                    ]
                },
                headers={"Content-Type": "application/json"}
            )
            result = response.json()

            if "error" in result:
                raise HTTPException(status_code=400, detail=f"Transaction failed: {result['error']['message']}")

            return {"status": "success", "transaction_hash": result["result"]}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RPCException as e:
        raise HTTPException(status_code=400, detail="Transaction failed: RPC error")
    except Exception as e:
        logging.error(f"Transfer error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
