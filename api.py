import os
import importlib
from contextlib import asynccontextmanager
from fastapi import FastAPI
from utility.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting up the application...")
    wallet_path = os.path.join(os.path.dirname(__file__), 'api', 'wallet')
    for filename in os.listdir(wallet_path):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = f"api.wallet.{filename[:-3]}"
            module = importlib.import_module(module_name)
            if hasattr(module, 'router'):
                app.include_router(getattr(module, 'router'))
                logger.info(f"Endpoint /{filename[:-3]} is now online")

    yield
    logger.info("Shutting down the application...")


app = FastAPI(lifespan=lifespan)

if __name__ == "__main__":
    import uvicorn

    logger.info("Running the application...")
    uvicorn.run(app, host="0.0.0.0", port=65500)