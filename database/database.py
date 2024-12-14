from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URL = ("mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.user_db
user_collection = db.users

async def connect_to_mongo():
    try:
        await client.admin.command('ping')
        print("Successfully connected to MongoDB!")
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
