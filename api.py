import os
import importlib
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from utility.logger import logger
from middleware.discord import start_bot
from utility.webhookManager import send_startup_webhook
from api.discovery.discovery import router as discovery_router


# daal dena yeh sab endpoint url lagane mai problem aayegi sirf
GOOGLE_CLIENT_ID = "GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET = "GOOGLE_CLIENT_SECRET"
GOOGLE_REDIRECT_URI = "GOOGLE_REDIRECT_URI"
SECRET_KEY = "SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up the application...")


    wallet_path = os.path.join(os.path.dirname(__file__), 'api', 'wallet')
    for filename in os.listdir(wallet_path):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = f"api.wallet.{filename[:-3]}"
            module = importlib.import_module(module_name)
            if hasattr(module, 'router'):
                app.include_router(getattr(module, 'router'))
                logger.info(f"Endpoint /{filename[:-3]} is now online")

    try:
        auth_module = importlib.import_module("api.users.oauth")
        if hasattr(auth_module, 'router'):
            app.include_router(auth_module.router, prefix="/auth", tags=["Authentication"])
            logger.info("OAuth authentication endpoints are now online")
    except Exception as e:
        logger.error(f"Failed to load OAuth endpoints: {str(e)}")


    try:
        user_module = importlib.import_module("api.users.user")
        if hasattr(user_module, 'router'):
            app.include_router(user_module.router)
            logger.info("User authentication endpoints are now online")
    except Exception as e:
        logger.error(f"Failed to load user endpoints: {str(e)}")

    await send_startup_webhook(
        True,
        "Application started successfully.",
        [
            "Endpoint /transfer is now online",
            "Endpoint /sendToken is now online",
            "Endpoint /swap is now online",
            "OAuth endpoints are now online"
        ]
    )
    await start_bot()

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
    "google_client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "google_client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
    "google_redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
    "secret_key": os.getenv("SECRET_KEY", "your-secret-key"),
    "algorithm": "HS256",
    "access_token_expire_minutes": 30
}

app.include_router(discovery_router, prefix="/api/discovery", tags=["discovery"])

# GOOGLE_CLIENT_ID=google_client_id
# GOOGLE_CLIENT_SECRET=google_client_secret
# GOOGLE_REDIRECT_URI=redirect_uri
# SECRET_KEY=secret_key


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn

    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI]):
        logger.error("Missing required environment variables for OAuth setup")
        exit(1)

    logger.info("Running the application...")
    uvicorn.run(app, host="0.0.0.0", port=65500)
