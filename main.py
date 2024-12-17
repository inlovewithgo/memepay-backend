import os
import importlib
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import status
from datetime import datetime

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
        wallet_path = os.path.join(os.path.dirname(__file__), "api", "wallet")
        for filename in os.listdir(wallet_path):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = f"api.wallet.{filename[:-3]}"
                module = importlib.import_module(module_name)
                if hasattr(module, "router"):
                    app.include_router(getattr(module, "router"), prefix=f"/api/{filename[:-3]}")
                    logger.info(f"Endpoint /api/{filename[:-3]} is now online")
    except Exception as e:
        logger.error(f"Failed to load wallet endpoints: {e}")

    try:
        user_module = importlib.import_module("api.users.user")
        if hasattr(user_module, "router"):
            app.include_router(user_module.router, prefix="/api/users")
            logger.info("User authentication endpoints are now online")
    except Exception as e:
        logger.error(f"Failed to load user endpoints: {e}")

    try:
        await send_startup_webhook(
            True,
            "Application started successfully.",
            [
                "Endpoint /api/transfer is now online",
                "Endpoint /api/sendToken is now online",
                "Endpoint /api/swap is now online",
                "OAuth endpoints are now online",
            ],
        )
        logger.info("Startup webhook sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send startup webhook: {e}")

    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.oauth_config = {
    "google_client_id": GOOGLE_CLIENT_ID,
    "google_client_secret": GOOGLE_CLIENT_SECRET,
    "google_redirect_uri": GOOGLE_REDIRECT_URI,
    "secret_key": SECRET_KEY,
    "algorithm": ALGORITHM,
    "access_token_expire_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
}

app.include_router(discovery_router, prefix="/api/discovery", tags=["discovery"])

@app.get(
    "/health",
    tags=["healthcheck"],
    summary="Perform a Health Check",
    status_code=status.HTTP_200_OK,
)
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


async def fetch_data_from_db(collection):
    try:
        cursor = collection.find({})
        documents = await cursor.to_list(length=None)  # Convert to list
        for document in documents:
            print(document)
        return documents
    except Exception as e:
        logger.error(f"Database fetch error: {e}")
        return []


def main():
    import asyncio
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI]):
        logger.error("Missing required environment variables for OAuth setup.")
        exit(1)

    logger.info("Running the application...")
    config = Config()
    config.bind = ["0.0.0.0:9999"]
    config.reload = True

    asyncio.run(serve(app, config))


if __name__ == "__main__":
    main()
