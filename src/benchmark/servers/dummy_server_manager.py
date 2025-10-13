"""
Dummy server manager for template/example service.
"""
from benchmark.servers.base_server_manager import BaseServerManager
from typing import Dict, Any, List

class DummyServerManager(BaseServerManager):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.config = config

    def verify_health(self, endpoints: List[str], timeout: int = 600) -> bool:
        print(f"[Dummy] Verifying health for endpoints: {endpoints}")
        return True

    def prepare_service(self, endpoints: List[str], timeout: int = 600) -> bool:
        print(f"[Dummy] Preparing service for endpoints: {endpoints}")
        return True

    def get_health_check_endpoint(self) -> str:
        return "/health"

    @classmethod
    def parse_service_config(cls, recipe_config: Dict[str, Any]) -> Dict[str, Any]:
        return {}
