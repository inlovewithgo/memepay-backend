from fastapi import FastAPI, HTTPException, Request, APIRouter
from typing import Optional, List
from pydantic import BaseModel
import httpx
import os

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

class TokenData(BaseModel):
    pubkey: str
    mint: str
    owner: str
    decimals: int
    balance: str

async def fetch_token_accounts(wallet: str, rpc_url: str):
    rpc_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet,
            {
                "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
            },
            {
                "encoding": "jsonParsed"
            }
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
    if not wallet:
        raise HTTPException(status_code=400, detail="Wallet address is required")
    
    if not rpc_url:
        rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    
    try:
        token_response = await fetch_token_accounts(wallet, rpc_url)
        
        if "error" in token_response:
            return []
            
        if "result" not in token_response:
            raise HTTPException(
                status_code=500,
                detail="Invalid response from RPC endpoint"
            )
            
        token_accounts = token_response["result"]["value"]
        
        if not token_accounts:
            return []
        
        return process_token_data(token_accounts)
        
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to RPC endpoint"
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
