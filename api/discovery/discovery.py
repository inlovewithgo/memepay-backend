import asyncio
import aiohttp
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from database.models import Token, TokenPrice, TokenMetrics
from middleware.web3 import w3_bsc, w3_eth, tokens_collection
from pymongo import DESCENDING
from utility.logger import logger
from core.updatesingletoken import update_single_token
from utility.updatealltokens import update_all_tokens

router = APIRouter()

@router.get("/tokens", response_model=List[Token])
async def get_tokens(
        chain: Optional[str] = None,
        min_liquidity: Optional[float] = None,
        min_volume: Optional[float] = None,
        skip: int = 0,
        limit: int = 50
):
    query = {}
    if chain:
        query["chain"] = chain
    if min_liquidity:
        query["liquidity"] = {"$gte": min_liquidity}
    if min_volume:
        query["volume_24h"] = {"$gte": min_volume}

    tokens = list(tokens_collection.find(query, {'_id': 0}).skip(skip).limit(limit))
    return tokens


@router.get("/token/{chain}/{address}", response_model=Token)
async def get_token(chain: str, address: str):
    token = tokens_collection.find_one({"address": address.lower(), "chain": chain}, {'_id': 0})
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return token


@router.get("/trending")
async def get_trending_tokens(timeframe: str = "24h", limit: int = 10):
    sort_field = "volume_24h" if timeframe == "24h" else "price.change_6h"
    tokens = list(tokens_collection.find({}, {'_id': 0}).sort(sort_field, DESCENDING).limit(limit))
    return tokens


@router.post("/tokens/refresh/{chain}/{address}")
async def refresh_token(chain: str, address: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(update_single_token, chain, address)
    return {"message": "Token refresh scheduled"}

@router.on_event("startup")
async def start_background_tasks():
    async def periodic_update():
        while True:
            try:
                await update_all_tokens()
            except Exception as e:
                logger.error(f"Error in periodic update: {str(e)}")
            await asyncio.sleep(300)

    asyncio.create_task(periodic_update())
