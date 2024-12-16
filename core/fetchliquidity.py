import aiohttp
from web3 import Web3


async def fetch_liquidity(session: aiohttp.ClientSession, address: str, chain: str) -> float:
    if chain == "bsc":
        return await fetch_pancakeswap_liquidity(session, address)
    elif chain == "eth":
        return await fetch_uniswap_liquidity(session, address)
    else:
        raise ValueError(f"Unsupported chain: {chain}")


async def fetch_pancakeswap_liquidity(session: aiohttp.ClientSession, address: str) -> float:
    query = """
    query ($address: Bytes!) {
      pair(id: $address) {
        reserveUSD
      }
    }
    """
    variables = {"address": address.lower()}
    url = "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange-v2"

    async with session.post(url, json={"query": query, "variables": variables}) as response:
        data = await response.json()
        if "data" in data and "pair" in data["data"] and data["data"]["pair"]:
            return float(data["data"]["pair"]["reserveUSD"])
    return 0.0


async def fetch_uniswap_liquidity(session: aiohttp.ClientSession, address: str) -> float:
    query = """
    query ($address: ID!) {
      pair(id: $address) {
        reserveUSD
      }
    }
    """
    variables = {"address": address.lower()}
    url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"

    async with session.post(url, json={"query": query, "variables": variables}) as response:
        data = await response.json()
        if "data" in data and "pair" in data["data"] and data["data"]["pair"]:
            return float(data["data"]["pair"]["reserveUSD"])
    return 0.0
