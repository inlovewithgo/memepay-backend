import datetime
import aiohttp
import time
import timedelta
from utility.logger import logger

async def fetch_makers_count(session: aiohttp.ClientSession, address: str, chain: str) -> int:
    try:
        query = """
        query ($token: String!) {
            dexTrades(
                where: {
                    baseCurrency: {is: $token},
                    timestamp: {since: TIME_FROM_24H_AGO}
                }
            ) {
                makers: count(distinct: makerAddress)
            }
        }
        """

        if chain == "bsc":
            endpoint = "https://graphql.bitquery.io/bsc"
        else:
            endpoint = "https://graphql.bitquery.io/eth"

        variables = {
            "token": address.lower(),
            "TIME_FROM_24H_AGO": (datetime.utcnow() - timedelta(hours=24)).isoformat()
        }

        headers = {
            "Content-Type": "application/json",
        }

        async with session.post(
                endpoint,
                json={"query": query, "variables": variables},
                headers=headers
        ) as response:
            if response.status == 200:
                data = await response.json()
                return int(data.get("data", {}).get("dexTrades", {}).get("makers", 0))
            return 0

    except Exception as e:
        logger.error(f"Error fetching makers count for token {address}: {str(e)}")
        return 0
