import aiohttp
import time
from utility.logger import logger


async def calculate_6h_change(session: aiohttp.ClientSession, address: str, chain: str) -> float:
    try:
        current_time = int(time.time())
        six_hours_ago = current_time - (6 * 3600)

        if chain == "bsc":
            url = f"https://api.pancakeswap.info/api/v2/tokens/{address}"
        else:
            url = f"https://api.uniswap.org/v1/token/{address}"

        async with session.get(url) as response:
            current_data = await response.json()
            current_price = float(current_data.get('data', {}).get('price', 0))

        historical_query = """
        query ($address: Bytes!, $timestamp: Int!) {
          token(id: $address) {
            tokenDayData(first: 1, where: {timestamp_lt: $timestamp}) {
              priceUSD
            }
          }
        }
        """
        variables = {
            "address": address.lower(),
            "timestamp": six_hours_ago
        }

        graph_url = "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange-v2" if chain == "bsc" else "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"

        async with session.post(graph_url, json={"query": historical_query, "variables": variables}) as response:
            historical_data = await response.json()
            old_price = float(
                historical_data.get('data', {}).get('token', {}).get('tokenDayData', [{}])[0].get('priceUSD', 0))

        if old_price == 0:
            return 0.0

        percentage_change = ((current_price - old_price) / old_price) * 100
        return round(percentage_change, 2)

    except Exception as e:
        logger.error(f"Error calculating 6h change for token {address}: {str(e)}")
        return 0.0
