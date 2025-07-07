from fastapi import FastAPI, HTTPException, BackgroundTasks
from pymongo import MongoClient, ASCENDING, DESCENDING
from web3 import Web3
from database.database import db

async def init_web3_and_db():
    BSC_NODE = "https://bsc-dataseed.binance.org/"
    ETHEREUM_NODE = "https://mainnet.infura.io/v3/apikeydaaldeidharbhai"
    PANCAKESWAP_FACTORY = ""
    UNISWAP_FACTORY = ""

    w3_bsc = Web3(Web3.HTTPProvider(BSC_NODE))
    w3_eth = Web3(Web3.HTTPProvider(ETHEREUM_NODE))

    await db.initialize()
    tokens_collection = db.db.tokens
    pairs_collection = db.db.pairs

    await tokens_collection.create_index([("address", ASCENDING)], unique=True)
    await tokens_collection.create_index([("symbol", ASCENDING)])
    await pairs_collection.create_index([("address", ASCENDING)], unique=True)

    return {
        "w3_bsc": w3_bsc,
        "w3_eth": w3_eth,
        "tokens_collection": tokens_collection,
        "pairs_collection": pairs_collection,
        "PANCAKESWAP_FACTORY": PANCAKESWAP_FACTORY,
        "UNISWAP_FACTORY": UNISWAP_FACTORY
    }

w3_bsc = None
w3_eth = None
tokens_collection = None
pairs_collection = None
PANCAKESWAP_FACTORY = ""
UNISWAP_FACTORY = ""
