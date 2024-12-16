import aiohttp


async def fetch_holders_count(session: aiohttp.ClientSession, address: str, chain: str) -> int:
    explorer_api = "https://api.bscscan.com/api" if chain == "bsc" else "https://api.etherscan.io/api"
    async with session.get(f"{explorer_api}?module=token&action=tokenholderlist&contractaddress={address}") as response:
        data = await response.json()
        return len(data.get("result", []))