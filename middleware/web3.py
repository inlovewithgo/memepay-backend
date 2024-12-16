from fastapi import FastAPI, HTTPException, BackgroundTasks
from pymongo import MongoClient, ASCENDING, DESCENDING
from web3 import Web3
from database.database import db

def init_web3_and_db():
    BSC_NODE = "https://bsc-dataseed.binance.org/"
    ETHEREUM_NODE = "https://mainnet.infura.io/v3/apikeydaaldeidharbhai"
    PANCAKESWAP_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
    UNISWAP_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"

    w3_bsc = Web3(Web3.HTTPProvider(BSC_NODE))
    w3_eth = Web3(Web3.HTTPProvider(ETHEREUM_NODE))

    tokens_collection = db["tokens"]
    pairs_collection = db["pairs"]

    tokens_collection.create_index([("address", ASCENDING)], unique=True)
    tokens_collection.create_index([("symbol", ASCENDING)])
    pairs_collection.create_index([("address", ASCENDING)], unique=True)

    return {
        "w3_bsc": w3_bsc,
        "w3_eth": w3_eth,
        "tokens_collection": tokens_collection,
        "pairs_collection": pairs_collection,
        "PANCAKESWAP_FACTORY": PANCAKESWAP_FACTORY,
        "UNISWAP_FACTORY": UNISWAP_FACTORY
    }

web3_config = init_web3_and_db()
w3_bsc = web3_config["w3_bsc"]
w3_eth = web3_config["w3_eth"]
tokens_collection = web3_config["tokens_collection"]
pairs_collection = web3_config["pairs_collection"]
PANCAKESWAP_FACTORY = web3_config["PANCAKESWAP_FACTORY"]
UNISWAP_FACTORY = web3_config["UNISWAP_FACTORY"]
