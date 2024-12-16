import aiohttp
import time
from utility.logger import logger

async def fetch_transactions_24h(session: aiohttp.ClientSession, address: str, chain: str) -> int:
    try:
        timestamp_24h_ago = int(time.time()) - 86400

        if chain == "bsc":
            explorer_api = "https://api.bscscan.com/api"
        else:
            explorer_api = "https://api.etherscan.io/api"

        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": address,
            "starttime": timestamp_24h_ago,
            "endtime": int(time.time()),
            "sort": "desc"
        }

        async with session.get(explorer_api, params=params) as response:
            data = await response.json()
            transactions = data.get("result", [])
            return len(transactions)

    except Exception as e:
        logger.error(f"Error fetching 24h transactions for {address}: {str(e)}")
        return 0