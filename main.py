import os
import importlib
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import status
from datetime import datetime
from database.database import db

from database.database import init_web3_and_db, get_web3_config
from database.redis import redis_config
from database.redis import cached
from utility.logger import logger
from utility.webhookManager import send_startup_webhook
from api.discovery.discovery import router as discovery_router

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "GOOGLE_REDIRECT_URI")
SECRET_KEY = os.getenv("SECRET_KEY", "SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up the application...")

    try:
        await db.initialize()
        if not db.client:
            raise Exception("Database client not initialized")
        logger.info("Database initialized successfully")

        await redis_config.initialize()
        logger.info("Redis cache initialized successfully")

        app.state.db = db

        web3_config = await init_web3_and_db()
        app.state.web3_config = web3_config

        wallet_path = os.path.join(os.path.dirname(__file__), "api", "wallet")
        for filename in os.listdir(wallet_path):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = f"api.wallet.{filename[:-3]}"
                module = importlib.import_module(module_name)
                if hasattr(module, "router"):
                    app.include_router(getattr(module, "router"))
                    logger.info(f"Endpoint /api/{filename[:-3]} is now online")

        userpath = os.path.join(os.path.dirname(__file__), "api", "users")
        for filename in os.listdir(userpath):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = f"api.users.{filename[:-3]}"
                module = importlib.import_module(module_name)
                if hasattr(module, "router"):
                    app.include_router(getattr(module, "router"))
                    logger.info(f"Auth endpoint loaded")

        await send_startup_webhook(
            True,
            "Application started successfully.",
            ["All endpoints are now online"]
        )
        yield
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        await send_startup_webhook(
            False,
            f"Application startup failed: {str(e)}",
            [],
        )
        raise
    finally:
        logger.info("Shutting down the application...")



app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(discovery_router, prefix="/api/discovery", tags=["discovery"])


@app.get("/health", tags=["healthcheck"], status_code=status.HTTP_200_OK)
@cached(expire=30)
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


def main():
    import asyncio
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    logger.info("Running the application...")
    config = Config()
    config.bind = ["0.0.0.0:9999"]
    config.reload = True

    asyncio.run(serve(app, config))


if __name__ == "__main__":
    main()
