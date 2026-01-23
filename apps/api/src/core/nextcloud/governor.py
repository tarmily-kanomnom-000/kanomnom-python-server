from __future__ import annotations

from core.nextcloud.client import NextcloudCalendarClient
from core.nextcloud.config import load_nextcloud_config
from core.nextcloud.credentials import NextcloudCredentialsRepository
from core.nextcloud.metadata import NextcloudMetadataRepository


class NextcloudGovernor:
    """Governs lifecycle and coordination across Nextcloud instances."""

    def __init__(
        self,
        metadata_repository: NextcloudMetadataRepository,
        credentials_repository: NextcloudCredentialsRepository,
    ) -> None:
        self.metadata_repository = metadata_repository
        self.credentials_repository = credentials_repository
        self._clients: dict[str, NextcloudCalendarClient] = {}

    def available_instances(self) -> list[str]:
        """Return instance keys that can be governed."""
        return self.metadata_repository.list_instance_keys()

    def client_for(self, instance_key: str) -> NextcloudCalendarClient:
        """Return a NextcloudCalendarClient for the requested instance, creating it if necessary."""
        if instance_key in self._clients:
            return self._clients[instance_key]
        metadata = self.metadata_repository.load(instance_key)
        credentials = self.credentials_repository.load(instance_key)
        config = load_nextcloud_config(metadata, credentials)
        client = NextcloudCalendarClient(config)
        self._clients[instance_key] = client
        return client

    def clear_client(self, instance_key: str) -> None:
        """Remove a cached client so future calls reload metadata and clients."""
        if instance_key in self._clients:
            del self._clients[instance_key]
