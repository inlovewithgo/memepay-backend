from fastapi import FastAPI, HTTPException, Request, APIRouter
from typing import Optional, List, Dict, Any
import httpx
from pydantic import BaseModel
from decimal import Decimal
import asyncio
from collections import defaultdict
from utility.logger import logger
from database.redis import cached
import os

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

class TokenData(BaseModel):
    id: int
    name: str
    symbol: str
    balance: str
    balanceUsd: float
    priceChange: float
    logoUrl: str
    marketCap: float
    price: float
    explorerUrl: str
    pubkey: str
    mint: str
    owner: str
    decimals: int

class TokenResponse(BaseModel):
    wallet: str
    tokens: List[TokenData]
    count: int

def get_token_metadata(mint: str) -> Dict[str, str]:
    KNOWN_TOKENS = {
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {
            "name": "USD Coin",
            "symbol": "USDC",
            "logoUrl": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v/logo.png"
        },
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {
            "name": "USD Tether",
            "symbol": "USDT",
            "logoUrl": "https://raw.githubusercontent.com/solana-labs/token-list/main/assets/mainnet/Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB/logo.svg"
        },
    }
    return KNOWN_TOKENS.get(mint, {
        "name": f"Token {mint[:4]}...{mint[-4:]}",
        "symbol": "UNKNOWN",
        "logoUrl": ""
    })

async def fetch_token_accounts(wallet: str, rpc_url: str) -> Dict[str, Any]:
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

async def fetch_token_market_data(token_addresses: List[str]) -> Dict[str, Any]:
    if not token_addresses:
        return {"pairs": []}
    addresses = ",".join(token_addresses)
    url = f"https://api.dexscreener.com/latest/dex/tokens/{addresses}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            if isinstance(data, dict) and "pairs" in data:
                return data
            else:
                print(f"Unexpected response structure: {data}")
                return {"pairs": []}
    except Exception as e:
        print(f"Error fetching market data: {e}")
        return {"pairs": []}

def format_balance(amount: str, decimals: int) -> str:
    try:
        raw_amount = Decimal(amount)
        factor = Decimal(10) ** decimals
        adjusted_amount = raw_amount / factor
        return f"{adjusted_amount:,.5f}".rstrip('0').rstrip('.')
    except Exception:
        return "0"

def process_token_data(token_accounts: List[Dict], market_data: Dict[str, Any]) -> List[Dict]:
    token_balances = {}
    for account in token_accounts:
        parsed_info = account["account"]["data"]["parsed"]["info"]
        raw_amount = parsed_info["tokenAmount"]["amount"]
        if float(raw_amount) > 0:
            mint = parsed_info["mint"]
            decimals = parsed_info["tokenAmount"]["decimals"]
            if mint in token_balances:
                current_balance = Decimal(token_balances[mint]["raw_balance"])
                raw_amount = str(Decimal(raw_amount) + current_balance)
            token_balances[mint] = {
                "balance": format_balance(raw_amount, decimals),
                "raw_balance": raw_amount,
                "decimals": decimals,
                "pubkey": account["pubkey"],
                "mint": mint,
                "owner": parsed_info["owner"]
            }

    market_lookup = {}
    for pair in market_data.get("pairs", []):
        try:
            if not isinstance(pair, dict) or "baseToken" not in pair:
                continue
            base_token = pair["baseToken"]
            if not isinstance(base_token, dict) or "address" not in base_token:
                continue
            mint = base_token["address"]
            if mint not in market_lookup or market_lookup[mint]["marketCap"] < float(pair.get("marketCap", 0)):
                market_lookup[mint] = {
                    "name": base_token.get("name", "").strip(),
                    "symbol": base_token.get("symbol", "UNKNOWN"),
                    "price": float(pair.get("priceUsd", 0) or 0),
                    "priceChange": float(pair.get("priceChange24h", 0) or 0),
                    "marketCap": float(pair.get("marketCap", 0) or 0),
                    "logoUrl": pair.get("info", {}).get("imageUrl", "")
                }
        except Exception as e:
            print(f"Error processing market pair: {e}")

    result = []
    for idx, (mint, balance_data) in enumerate(token_balances.items(), 1):
        market_info = market_lookup.get(mint, None)
        if market_info is None:
            metadata = get_token_metadata(mint)
            balance = balance_data["balance"]
            market_info = {
                "name": metadata["name"],
                "symbol": metadata["symbol"],
                "price": 0,
                "priceChange": 0,
                "marketCap": 0,
                "logoUrl": metadata["logoUrl"]
            }
        
        balance = balance_data["balance"]
        balance_usd = float(balance.replace(",", "")) * market_info["price"]
        
        result.append(TokenData(
            id=idx,
            name=market_info["name"],
            symbol=market_info["symbol"],
            balance=balance,
            balanceUsd=round(balance_usd, 2),
            priceChange=market_info["priceChange"],
            logoUrl=market_info["logoUrl"],
            marketCap=market_info["marketCap"],
            price=market_info["price"],
            explorerUrl=f"https://solscan.io/token/{mint}",
            pubkey=token_balances[mint]["pubkey"],
            mint=mint,
            owner=token_balances[mint]["owner"],
            decimals=token_balances[mint]["decimals"]
        ))
    return result

@router.get("/tokens", response_model=TokenResponse)
@cached(expire=300) 
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
        logger.info(f"Fetching token accounts for wallet: {wallet}")
        token_response = await fetch_token_accounts(wallet, rpc_url)
        
        if "error" in token_response:
            logger.warning(f"No token accounts found for wallet: {wallet}")
            return TokenResponse(
                wallet=wallet,
                tokens=[],
                count=0
            )
            
        if "result" not in token_response:
            raise HTTPException(
                status_code=500,
                detail="Invalid response from RPC endpoint"
            )
            
        token_accounts = token_response["result"]["value"]
        
        if not token_accounts:
            return TokenResponse(
                wallet=wallet,
                tokens=[],
                count=0
            )
            
        mint_addresses = []
        for account in token_accounts:
            try:
                parsed_info = account["account"]["data"]["parsed"]["info"]
                if float(parsed_info["tokenAmount"]["amount"]) > 0:
                    mint = parsed_info["mint"]
                    if mint not in mint_addresses:
                        mint_addresses.append(mint)
            except KeyError:
                continue
        
        market_data = await fetch_token_market_data(mint_addresses)
        tokens = process_token_data(token_accounts, market_data)
        
        logger.info(f"Successfully fetched {len(tokens)} tokens for wallet: {wallet}")
        return TokenResponse(
            wallet=wallet,
            tokens=tokens,
            count=len(tokens)
        )
        
    except httpx.RequestError as e:
        logger.error(f"RPC connection error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to RPC endpoint"
        )
    except Exception as error:
        logger.error(f"Error processing token data: {str(error)}")
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )