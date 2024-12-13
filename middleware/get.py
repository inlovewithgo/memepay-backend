# middleware/get.py
import httpx
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app_logger")

class GetRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "GET":
            client_ip = request.client.host
            log_message = f"GET request to {request.url.path} from IP: {client_ip}"
            logger.info(log_message)
            await send_log_webhook(log_message)
        response = await call_next(request)
        if response.status_code >= 400:
            error_message = f"Error {response.status_code} on GET request to {request.url.path} from IP: {client_ip}"
            logger.error(error_message)
            await send_log_webhook(error_message)
        return response

async def send_log_webhook(message: str):
    webhook_url = "https://discord.com/api/webhooks/1317079138762358814/2TEeFuZY6tQagUQBAfetZ0FErVUGI5NbhyOhpckshPpGYcc-iZgyQ9D-zJRRqsfns4cR"
    content = {
        "content": message
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(webhook_url, json=content)
            response.raise_for_status()
            logger.info("Log webhook sent successfully.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send log webhook: {e.response.text}")
        except Exception as e:
            logger.error(f"An error occurred while sending log webhook: {str(e)}")