from fastapi import FastAPI, HTTPException
from web3 import Web3
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from pymongo import ASCENDING
from .redis import redis_config
from fastapi import status

class Database:
    def __init__(self):
        self.mongodb_url = "mongodb://exril:exrilatmemepay@194.15.36.168:27017/admin"
        self.client = None
        self.db = None
        self.tokens = None
        self.pairs = None
        self.users = None
        self.sessions = None

    async def initialize(self):
        try:
            self.client = AsyncIOMotorClient(
                self.mongodb_url,
                io_loop=asyncio.get_running_loop()
            )
            self.db = self.client["user_management"]
            self.tokens = self.db.tokens
            self.pairs = self.db.pairs
            self.users = self.db.users
            self.sessions = self.db.sessions

            await self.users.create_index([("email", ASCENDING)], unique=True)
            await self.users.create_index([("username", ASCENDING)], unique=True)
            await self.sessions.create_index(
                [("session_token", ASCENDING)],
                unique=True
            )
            await self.sessions.create_index(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=2592000
            )
            await self.sessions.create_index([("user_id", ASCENDING)])
            
            await self.tokens.create_index([("address", ASCENDING)], unique=True)
            await self.tokens.create_index([("symbol", ASCENDING)])
            await self.pairs.create_index([("address", ASCENDING)], unique=True)
            await self.tokens.create_index([("address", ASCENDING)], unique=True)
            await self.tokens.create_index([("symbol", ASCENDING)])
            await self.pairs.create_index([("address", ASCENDING)], unique=True)
            
            await self.client.admin.command('ping')
            return self
        except Exception as e:
            raise Exception(f"Failed to connect to MongoDB: {str(e)}")

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

        return {
            "w3_bsc": web3_config.w3_bsc,
            "w3_eth": web3_config.w3_eth,
            "tokens_collection": db.tokens,
            "pairs_collection": db.pairs,
            "users_collection": db.users,  # Add users collection
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

async def get_database() -> Database:
    if not db.client:
        await db.initialize()
        if not db.client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection failed"
            )
    return db


async def get_redis():
    if not redis_config.initialized:
        await redis_config.initialize()
    return redis_config
