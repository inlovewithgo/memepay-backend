import subprocess
from utility.logger import logger

def run_app():
    try:
        logger.info("Starting the application...")
        result = subprocess.run(['python3', 'core/app.py'], check=True, capture_output=True, text=True)
        logger.info("Application output:\n" + result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occurred: {e.stderr}")

if __name__ == "__main__":
    run_app()