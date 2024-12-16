from core.fetchliquidity import fetch_liquidity
from core.fetchday import fetch_volume_24h
from core.calcsupply import calculate_circulating_supply
from core.calcsixhour import calculate_6h_change
from core.fetchmakercount import fetch_makers_count
from core.fetchholdercount import fetch_holders_count
from core.fetchtransactionsday import fetch_transactions_24h
from core.tokenage import get_token_age

from database.models import Token, TokenPrice, TokenMetrics
from middleware.web3 import w3_bsc, w3_eth, tokens_collection

import aiohttp
import datetime

from utility.logger import logger


async def fetch_token_data(session: aiohttp.ClientSession, address: str, chain: str) -> dict:
    try:
        w3 = w3_bsc if chain == "bsc" else w3_eth

        token_abi = [
            {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}],
             "type": "function"},
            {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}],
             "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}],
             "type": "function"},
            {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}],
             "type": "function"}
        ]

        contract = w3.eth.contract(address=w3.to_checksum_address(address), abi=token_abi)

        name = await contract.functions.name().call()
        symbol = await contract.functions.symbol().call()
        decimals = await contract.functions.decimals().call()
        total_supply = await contract.functions.totalSupply().call()

        async with session.get(
                f"https://api.coingecko.com/api/v3/simple/token_price/{chain}?contract_addresses={address}&vs_currencies=usd&include_24h_change=true") as response:
            price_data = await response.json()

        holders = await fetch_holders_count(session, address, chain)
        liquidity = await fetch_liquidity(session, address, chain)
        volume = await fetch_volume_24h(session, address, chain)
        transactions = await fetch_transactions_24h(session, address, chain)

        return {
            "address": address,
            "name": name,
            "symbol": symbol,
            "chain": chain,
            "decimals": decimals,
            "price": TokenPrice(
                usd=price_data.get(address.lower(), {}).get("usd", 0),
                change_24h=price_data.get(address.lower(), {}).get("usd_24h_change", 0),
                change_6h=await calculate_6h_change(session, address, chain)
            ),
            "liquidity": liquidity,
            "age": await get_token_age(w3, address),
            "txns_24h": transactions,
            "volume_24h": volume,
            "makers_count": await fetch_makers_count(session, address, chain),
            "market_metrics": TokenMetrics(
                total_supply=total_supply / (10 ** decimals),
                circulating_supply=await calculate_circulating_supply(contract, total_supply),
                holders=holders,
                market_cap=(total_supply / (10 ** decimals)) * price_data.get(address.lower(), {}).get("usd", 0)
            ),
            "updated_at": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error fetching data for token {address}: {str(e)}")
        raise
