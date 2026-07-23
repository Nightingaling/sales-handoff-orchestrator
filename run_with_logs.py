import logging
import uvicorn
from src.main import app

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("Starting application with diagnostic logging...")

if __name__ == "__main__":
    logger.info("run_with_logs.py: Launching Uvicorn")
    uvicorn.run(app, host="127.0.0.1", port=8001)
    logger.info("run_with_logs.py: Uvicorn has exited.")
