"""Central logging setup, shared by every dar_app module.

Import ``logger`` from here instead of re-configuring logging per module -
logging.basicConfig() only needs to run once (it configures the root logger).
"""
import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(r"L:\Engineering\DAR Docktag Cards\cache_data\logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_filename = LOG_DIR / f"server_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("dar_app")
logger.info("=" * 60)
logger.info(f"SERVER STARTED - Logging to {log_filename}")
logger.info("=" * 60)
