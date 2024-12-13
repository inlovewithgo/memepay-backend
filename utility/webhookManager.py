import httpx
import logging

logger = logging.getLogger("app_logger")

async def send_startup_webhook(success: bool, message: str, endpoints: list):
    webhook_url = "https://discord.com/api/webhooks/1317076508002488330/rGWTWLU977Vxb9NRxQpDjJF1bvIdalcc1erNT5pxVwrSKxCZLTtSTTG3lV44Dl2tUqhI"
    embed = {
        "title": "Startup Status",
        "description": f"Startup {'successful' if success else 'failed'}: {message}",
        "color": 3066993 if success else 15158332,
        "fields": [{"name": "Endpoints", "value": "\n".join(endpoints), "inline": False}]
    }
    content = {
        "embeds": [embed]
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(webhook_url, json=content)
            response.raise_for_status()
            logger.info("Startup webhook sent successfully.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send startup webhook: {e.response.text}")
        except Exception as e:
            logger.error(f"An error occurred while sending startup webhook: {str(e)}")