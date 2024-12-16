import aiohttp

async def fetch_volume_24h(session: aiohttp.ClientSession, address: str, chain: str) -> float:
    if chain == "bsc":
        return await fetch_pancakeswap_volume(session, address)
    elif chain == "eth":
        return await fetch_uniswap_volume(session, address)
    else:
        raise ValueError(f"Unsupported chain: {chain}")


async def fetch_pancakeswap_volume(session: aiohttp.ClientSession, address: str) -> float:
    query = """
    query ($address: Bytes!) {
      token(id: $address) {
        tradeVolumeUSD
      }
    }
    """
    variables = {"address": address.lower()}
    url = "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange-v2"

    async with session.post(url, json={"query": query, "variables": variables}) as response:
        data = await response.json()
        if "data" in data and "token" in data["data"] and data["data"]["token"]:
            return float(data["data"]["token"]["tradeVolumeUSD"])
    return 0.0


async def fetch_uniswap_volume(session: aiohttp.ClientSession, address: str) -> float:
    query = """
    query ($address: ID!) {
      token(id: $address) {
        tradeVolumeUSD
      }
    }
    """
    variables = {"address": address.lower()}
    url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"

    async with session.post(url, json={"query": query, "variables": variables}) as response:
        data = await response.json()
        if "data" in data and "token" in data["data"] and data["data"]["token"]:
            return float(data["data"]["token"]["tradeVolumeUSD"])
    return 0.0
