import logging

from src.modules.api.romm import RommAPI

logger = logging.getLogger(__name__)

class RommTestAPI(RommAPI):
    @staticmethod
    def test():
        """Test various API endpoints."""
        api = RommAPI()
        api.heartbeat()
        # api.get_game_by_id(38567)
        api.get_profile()
        api.get_config()
        api.get_collections()
        api.get_virtual_collections()
        platform_id = api.get_platform_by_slug()
        api.filter_games()
        if platform_id:
            romm_api = RommAPI()
            # Scan the file changes in the library folder
            logger.info("Scanning for file changes in the library folder...")
            romm_api.scan_library(platforms=[platform_id], scan_type="hashes")
            # Scan for new metadata sources
            logger.info("Scanning for new metadata sources...")
            romm_api.scan_library(platforms=[platform_id])
