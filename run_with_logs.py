import logging
import uvicorn
import sys
import os

# Add the virtual environment's site-packages directory to sys.path
# This is a workaround for application control policies that may prevent
# running scripts directly from the venv.
venv_site_packages = os.path.join(os.path.dirname(__file__), "venv", "Lib", "site-packages")
if os.path.exists(venv_site_packages):
    sys.path.insert(0, venv_site_packages)

from src.main import app

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("Starting application with diagnostic logging...")

if __name__ == "__main__":
    logger.info("run_with_logs.py: Launching Uvicorn")
    uvicorn.run(app, host="127.0.0.1", port=8001)
    logger.info("run_with_logs.py: Uvicorn has exited.")
