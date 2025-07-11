from fastapi import FastAPI, HTTPException, Request, APIRouter
from typing import Optional, List
from pydantic import BaseModel
import httpx

from utility.dataconfig import Config
from database.models import TokenData

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

async def fetch_token_accounts(wallet: str, rpc_url: str):
    rpc_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet,
            {"programId": ""},
            {"encoding": "jsonParsed"}
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            rpc_url,
            json=rpc_request,
            headers={"Content-Type": "application/json"}
        )
        return response.json()

def process_token_data(token_accounts: List[dict], mint_filter: Optional[str] = None) -> List[TokenData]:
    tokens = []
    for account in token_accounts:
        parsed_info = account["account"]["data"]["parsed"]["info"]
        raw_amount = parsed_info["tokenAmount"]["amount"]
        mint_address = parsed_info["mint"]
        
        if mint_filter and mint_address != mint_filter:
            continue
            
        if float(raw_amount) > 0:
            tokens.append(TokenData(
                pubkey=account["pubkey"],
                mint=mint_address,
                owner=parsed_info["owner"],
                decimals=parsed_info["tokenAmount"]["decimals"],
                balance=parsed_info["tokenAmount"]["uiAmountString"]
            ))
    return tokens

@router.get("/tokens", response_model=List[TokenData])
async def get_tokens(
    request: Request,
    wallet: str,
    mints: Optional[str] = None,
    rpc_url: Optional[str] = None
):
    if not wallet:
        raise HTTPException(status_code=400, detail="Wallet address is required")

    rpc_url = rpc_url or Config.RPC_URL

    try:
        token_response = await fetch_token_accounts(wallet, rpc_url)

        if "error" in token_response:
            return []

        if "result" not in token_response:
            raise HTTPException(
                status_code=500,
                detail="Invalid response from RPC endpoint"
            )

        token_accounts = token_response["result"].get("value", [])
        
        return process_token_data(token_accounts, mints)

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to RPC endpoint"
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

@router.get("/sol")
async def get_sol_balance(
    request: Request,
    wallet: str,
    rpc_url: Optional[str] = None
):
    if not wallet:
        raise HTTPException(status_code=400, detail="Wallet address is required")

    rpc_url = rpc_url or Config.RPC_URL

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getBalance",
                    "params": [wallet]
                },
                headers={"Content-Type": "application/json"}
            )

            data = response.json()

            if "error" in data:
                raise HTTPException(
                    status_code=500,
                    detail=f"RPC error: {data['error']['message']}"
                )

            if "result" not in data:
                raise HTTPException(
                    status_code=500,
                    detail="Invalid response from RPC endpoint"
                )

            balance_in_lamports = data["result"].get("value", 0)
            balance_in_sol = balance_in_lamports / 1_000_000_000

            return {
                "balance": str(balance_in_sol),
                "raw_balance": balance_in_lamports
            }

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to RPC endpoint"
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )