import aiohttp
from api.discovery.discovery import tokens_collection
from core.updatesingletoken import update_single_token
import asyncio
from utility.logger import logger

async def update_all_tokens():
    async with aiohttp.ClientSession() as session:
        tokens = tokens_collection.find({})
        for token in tokens:
            try:
                await update_single_token(token["chain"], token["address"])
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error updating token {token['address']}: {str(e)}")