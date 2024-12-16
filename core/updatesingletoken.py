import aiohttp
from core.fetchtokendata import fetch_token_data
from api.discovery.discovery import tokens_collection


async def update_single_token(chain: str, address: str):
    async with aiohttp.ClientSession() as session:
        token_data = await fetch_token_data(session, address, chain)
        tokens_collection.update_one(
            {"address": address, "chain": chain},
            {"$set": token_data},
            upsert=True
        )