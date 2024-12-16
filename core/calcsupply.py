from utility.logger import logger

async def calculate_circulating_supply(contract, total_supply: int) -> float:
    try:
        DEAD_ADDRESS = "0x000000000000000000000000000000000000dead"
        ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

        burned_tokens = await contract.functions.balanceOf(DEAD_ADDRESS).call()
        zero_tokens = await contract.functions.balanceOf(ZERO_ADDRESS).call()

        try:
            locked_tokens = await contract.functions.lockedSupply().call()
        except Exception:
            locked_tokens = 0

        try:
            reserved_tokens = await contract.functions.reservedSupply().call()
        except Exception:
            reserved_tokens = 0

        circulating = total_supply - (burned_tokens + zero_tokens + locked_tokens + reserved_tokens)

        decimals = await contract.functions.decimals().call()
        circulating_adjusted = float(circulating) / (10 ** decimals)

        return max(0.0, circulating_adjusted)

    except Exception as e:
        logger.error(f"Error calculating circulating supply: {str(e)}")
        return float(total_supply)
