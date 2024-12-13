# api.py
import os
import importlib
from contextlib import asynccontextmanager
from fastapi import FastAPI
from utility.logger import logger
from utility.webhookManager import send_startup_webhook
from middleware.get import GetRequestsMiddleware

def get_endpoints(folder):
    endpoints = []
    folder_path = os.path.join(os.path.dirname(__file__), 'api', folder)
    for filename in os.listdir(folder_path):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = f"api.{folder}.{filename[:-3]}"
            endpoint_path = f"/{folder}/{filename[:-3]}"
            endpoints.append((module_name, endpoint_path))
    return endpoints

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Starting up the application...")
        wallet_endpoints = get_endpoints('wallet')
        users_endpoints = get_endpoints('users')
        all_endpoints = wallet_endpoints + users_endpoints

        endpoint_messages = []
        for module_name, endpoint_path in all_endpoints:
            module = importlib.import_module(module_name)
            if hasattr(module, 'router'):
                app.include_router(module.router)
                logger.info(f"Endpoint {endpoint_path} is now online")
                endpoint_messages.append(f"Endpoint {endpoint_path} is now online")

        await send_startup_webhook(True, "Application started successfully.", endpoint_messages)
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        await send_startup_webhook(False, str(e), [])
        raise

    yield
    logger.info("Shutting down the application...")

app = FastAPI(lifespan=lifespan)
app.add_middleware(GetRequestsMiddleware)

if __name__ == "__main__":
    import uvicorn

    logger.info("Running the application...")
    uvicorn.run(app, host="0.0.0.0", port=65500)