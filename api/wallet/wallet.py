from fastapi import FastAPI, HTTPException, Request, APIRouter
from typing import Optional, List
from pydantic import BaseModel
import httpx

from utility.dataconfig import Config
from database.models import TokenData

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

async def fetch_token_accounts(wallet: str, rpc_url: str):
    """Fetch token accounts for a given wallet from an RPC endpoint."""
    rpc_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
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

def process_token_data(token_accounts: List[dict]) -> List[TokenData]:
    """Process raw token account data into a list of TokenData objects."""
    tokens = []
    for account in token_accounts:
        parsed_info = account["account"]["data"]["parsed"]["info"]
        raw_amount = parsed_info["tokenAmount"]["amount"]
        if float(raw_amount) > 0:
            tokens.append(TokenData(
                pubkey=account["pubkey"],
                mint=parsed_info["mint"],
                owner=parsed_info["owner"],
                decimals=parsed_info["tokenAmount"]["decimals"],
                balance=parsed_info["tokenAmount"]["uiAmountString"]
            ))
    return tokens

@router.get("/tokens", response_model=List[TokenData])
async def get_tokens(
    request: Request,
    wallet: str,
    rpc_url: Optional[str] = None
):
    """Retrieve token balances for a given wallet."""
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

        return process_token_data(token_accounts)

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
    """Retrieve SOL balance for a given wallet."""
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
