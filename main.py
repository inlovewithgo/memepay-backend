import uvicorn
from utility.logger import logger

def run_app():
    try:
        logger.info("Starting the application...")
        uvicorn.run("api", host="0.0.0.0", port=8000)
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    run_app()