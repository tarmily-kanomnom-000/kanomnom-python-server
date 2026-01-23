from __future__ import annotations

from core.cache.medusa_token_cache import MedusaTokenCacheManager
from core.medusa.auth import MedusaAuthProvider
from core.medusa.client import MedusaClient
from core.medusa.config import load_medusa_config
from core.medusa.credentials import MedusaCredentialsRepository
from core.medusa.metadata import MedusaMetadataRepository


class MedusaGovernor:
    """Governs lifecycle and coordination across Medusa instances."""

    def __init__(
        self,
        metadata_repository: MedusaMetadataRepository,
        credentials_repository: MedusaCredentialsRepository,
    ) -> None:
        self.metadata_repository = metadata_repository
        self.credentials_repository = credentials_repository
        self._clients: dict[str, MedusaClient] = {}

    def available_instances(self) -> list[str]:
        """Return instance keys that can be governed."""
        return self.metadata_repository.list_instance_keys()

    def client_for(self, instance_key: str) -> MedusaClient:
        """Return a MedusaClient for the requested instance, creating it if necessary."""
        if instance_key in self._clients:
            return self._clients[instance_key]
        metadata = self.metadata_repository.load(instance_key)
        credentials = self.credentials_repository.load(instance_key)
        config = load_medusa_config(metadata, credentials)
        token_cache = MedusaTokenCacheManager()
        auth_provider = MedusaAuthProvider(config, token_cache)
        client = MedusaClient(config, auth_provider)
        self._clients[instance_key] = client
        return client

    def clear_client(self, instance_key: str) -> None:
        """Remove a cached client so future calls reload metadata and clients."""
        if instance_key in self._clients:
            del self._clients[instance_key]
