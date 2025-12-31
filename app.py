# Load modules
import logging
import time

from src.logger_config import setup_logging
from src.modules import romm_library_cleanup, torrents, library_cleanup
from src.modules.config_parse import LOG_FILE_PATH, ON_STARTUP, WAIT_TIME, TESTING, DEBUG_LOGGING
from src.tests.romm import RommTestAPI

# Configure logging before importing other modules
log_level = logging.DEBUG if DEBUG_LOGGING else logging.INFO
setup_logging(level=log_level, log_file_path=LOG_FILE_PATH)
logger = logging.getLogger(__name__)


def test():
    RommTestAPI().test()


def run():
    torrents.run()
    library_cleanup.run()
    romm_library_cleanup.run()

def main():
    """Main application loop that runs on schedule."""
    logger.info("Starting the application...")

    if TESTING:
        logger.info("Running tests mode...")
        test()
        return

    if ON_STARTUP:
        logger.info("Running torrent manager on startup...")
        run()

    while True:
        wait_seconds = WAIT_TIME * 3600
        logger.info(f"Waiting {WAIT_TIME} hours for the next cycle...")
        time.sleep(wait_seconds)
        run()


if __name__ == "__main__":
    main()
