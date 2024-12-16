import datetime

async def get_token_age(w3, address: str) -> int:
    contract_creation = await w3.eth.get_transaction_receipt(address)
    creation_block = await w3.eth.get_block(contract_creation["blockNumber"])
    creation_time = datetime.fromtimestamp(creation_block["timestamp"])
    return (datetime.utcnow() - creation_time).days
