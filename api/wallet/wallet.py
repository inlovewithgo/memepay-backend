from fastapi import FastAPI, HTTPException, Request , APIRouter
from typing import Optional, List, Dict, Any
import httpx
from pydantic import BaseModel
from decimal import Decimal
import asyncio
from collections import defaultdict

router = APIRouter()

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
    """Get default token metadata based on known token addresses"""
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
    """Fetch token accounts from Solana RPC"""
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
    """Fetch token market data from DexScreener"""
    if not token_addresses:
        return {"pairs": []}
        
    addresses = ",".join(token_addresses)
    url = f"https://api.dexscreener.com/latest/dex/tokens/{addresses}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            # Ensure we have the expected structure
            if isinstance(data, dict) and "pairs" in data:
                return data
            else:
                print(f"Unexpected response structure: {data}")
                return {"pairs": []}
    except Exception as e:
        print(f"Error fetching market data: {e}")
        return {"pairs": []}

def format_balance(amount: str, decimals: int) -> str:
    """Format balance with commas and proper decimal places"""
    try:
        raw_amount = Decimal(amount)
        factor = Decimal(10) ** decimals
        adjusted_amount = raw_amount / factor
        return f"{adjusted_amount:,.5f}".rstrip('0').rstrip('.')
    except Exception:
        return "0"

def process_token_data(token_accounts: List[Dict], market_data: Dict[str, Any]) -> List[Dict]:
    """Process and combine token account data with market data"""
    # First, consolidate token balances
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

    # Create market data lookup
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

    # Combine data
    result = []
    for idx, (mint, balance_data) in enumerate(token_balances.items(), 1):
        # Get market data if available, otherwise use defaults
        market_info = market_lookup.get(mint, None)
        if market_info is None:
            # Use default metadata for unknown tokens
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

@router.get("/wallet/tokens", response_model=TokenResponse)
async def get_tokens(
    request: Request,
    wallet: str,
    rpc_url: Optional[str] = None
):
    if not wallet:
        raise HTTPException(status_code=400, detail="Wallet address is required")
    
    if not rpc_url:
        rpc_url = "https://solana-mainnet.api.syndica.io/api-key/faKTzw51EinVZKmoyEVd7wbePKtmKhFYt4HEDuoxGAW4fkbEFUVrsL2MY1uRc9kXcQTZC8acLTQGb8dEufyX65LrzXd38S7NHS"
    
    try:
        # Fetch token accounts
        token_response = await fetch_token_accounts(wallet, rpc_url)
        token_accounts = token_response["result"]["value"]
        
        # Get unique mint addresses with positive balances
        mint_addresses = []
        for account in token_accounts:
            parsed_info = account["account"]["data"]["parsed"]["info"]
            if float(parsed_info["tokenAmount"]["amount"]) > 0:
                mint = parsed_info["mint"]
                if mint not in mint_addresses:
                    mint_addresses.append(mint)
        
        # Fetch market data for all tokens
        market_data = await fetch_token_market_data(mint_addresses)
        
        # Process and combine token data
        tokens = process_token_data(token_accounts, market_data)
        
        return TokenResponse(
            wallet=wallet,
            tokens=tokens,
            count=len(tokens)
        )
        
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching token data: {str(error)}"
        )
