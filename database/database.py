from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import Depends
from typing import Optional
import os

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db_name: str = "user_management"

    def __init__(self):
        mongodb_url = ("mongodb+srv://exril:exrilatgrain@grain.4kcd1.mongodb.net/memepay")
        if not mongodb_url:
            mongodb_url = "mongodb+srv://exril:exrilatgrain@grain.4kcd1.mongodb.net/memepay"

        try:
            self.client = AsyncIOMotorClient(mongodb_url)
            self.db = self.client[self.db_name]
            self.users = self.db.users
            self.tokens = self.db.tokens
        except Exception as e:
            raise Exception(f"Failed to connect to MongoDB: {str(e)}")

    async def connect(self):
        try:
            await self.client.admin.command('ping')
        except Exception as e:
            raise Exception(f"Failed to connect to MongoDB: {str(e)}")

    async def close(self):
        if self.client:
            self.client.close()


db = Database()


async def get_database() -> Database:
    try:
        await db.connect()
        return db
    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}")
