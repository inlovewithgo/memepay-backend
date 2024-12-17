from fastapi import FastAPI, HTTPException
from web3 import Web3
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from pymongo import ASCENDING
from .redis import redis_config

class Database:
    def __init__(self):
        self.mongodb_url = "mongodb://exril:exrilatmemepay@194.15.36.168:27017/admin"
        self.client = None
        self.db = None
        self.tokens = None
        self.pairs = None

    async def initialize(self):
        try:
            self.client = AsyncIOMotorClient(
                self.mongodb_url,
                io_loop=asyncio.get_running_loop()
            )
            self.db = self.client["user_management"]
            self.tokens = self.db.tokens
            self.pairs = self.db.pairs
            await self.client.admin.command('ping')
            return self
        except Exception as e:
            raise Exception(f"Failed to connect to MongoDB: {str(e)}")

    async def close(self):
        if self.client:
            self.client.close()

db = Database()

class Web3Config:
    def __init__(self):
        self.BSC_NODE = "https://bsc-dataseed.binance.org/"
        self.ETHEREUM_NODE = "https://mainnet.infura.io/v3/apikeydaaldeidharbhai"
        self.PANCAKESWAP_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
        self.UNISWAP_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
        self.w3_bsc = None
        self.w3_eth = None

    async def initialize(self):
        try:
            self.w3_bsc = Web3(Web3.HTTPProvider(self.BSC_NODE))
            self.w3_eth = Web3(Web3.HTTPProvider(self.ETHEREUM_NODE))
            return self
        except Exception as e:
            raise Exception(f"Failed to initialize Web3: {str(e)}")

web3_config = Web3Config()

async def init_web3_and_db():
    try:
        await db.initialize()
        await web3_config.initialize()
        await redis_config.initialize()

        await db.tokens.create_index([("address", ASCENDING)], unique=True)
        await db.tokens.create_index([("symbol", ASCENDING)])
        await db.pairs.create_index([("address", ASCENDING)], unique=True)

        return {
            "w3_bsc": web3_config.w3_bsc,
            "w3_eth": web3_config.w3_eth,
            "tokens_collection": db.tokens,
            "pairs_collection": db.pairs,
            "PANCAKESWAP_FACTORY": web3_config.PANCAKESWAP_FACTORY,
            "UNISWAP_FACTORY": web3_config.UNISWAP_FACTORY,
            "redis_client": redis_config.client
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize services: {str(e)}"
        )

w3_bsc = None
w3_eth = None
tokens_collection = None
pairs_collection = None
PANCAKESWAP_FACTORY = web3_config.PANCAKESWAP_FACTORY
UNISWAP_FACTORY = web3_config.UNISWAP_FACTORY

async def get_web3_config():
    if not web3_config.w3_bsc or not web3_config.w3_eth:
        await web3_config.initialize()
    return web3_config

async def get_database():
    if not db.client:
        await db.initialize()
    return db

async def get_redis():
    if not redis_config.initialized:
        await redis_config.initialize()
    return redis_config
