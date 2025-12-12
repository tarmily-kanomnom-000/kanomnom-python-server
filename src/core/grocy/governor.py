from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from src.core.grocy.client import GrocyClient
from src.core.grocy.exceptions import ManifestNotFoundError
from src.core.grocy.manager import GrocyManager
from src.core.grocy.metadata import InstanceMetadataRepository
from src.core.grocy.models import InstanceMetadata, UniversalManifest
from src.core.grocy.services import QuantityUnitSyncResult


class GrocyGovernor:
    """Governs lifecycle and coordination across Grocy instances."""

    def __init__(self, metadata_repository: InstanceMetadataRepository, manifest_root: Path) -> None:
        self.metadata_repository = metadata_repository
        self.manifest_root = manifest_root
        self._managers: Dict[str, GrocyManager] = {}

    def available_instances(self) -> list[str]:
        """Return indexes that can be governed."""
        return self.metadata_repository.list_instance_indexes()

    def manager_for(self, instance_index: str) -> GrocyManager:
        """Return a GrocyManager for the requested instance, creating it if necessary."""
        if instance_index in self._managers:
            return self._managers[instance_index]
        metadata = self.metadata_repository.load(instance_index)
        client = GrocyClient(metadata.grocy_url, metadata.api_key)
        manager = GrocyManager(instance_index, client)
        self._managers[instance_index] = manager
        return manager

    def clear_manager(self, instance_index: str) -> None:
        """Remove a cached manager so future calls reload metadata and clients."""
        if instance_index in self._managers:
            del self._managers[instance_index]

    def list_instances_with_metadata(self) -> list[tuple[str, InstanceMetadata]]:
        """Return metadata for every known Grocy instance."""
        instances: list[tuple[str, InstanceMetadata]] = []
        for instance_index in self.metadata_repository.list_instance_indexes():
            metadata = self.metadata_repository.load(instance_index)
            instances.append((instance_index, metadata))
        return instances

    def ensure_quantity_units(self, instance_index: str) -> QuantityUnitSyncResult:
        """Ensure an instance has every quantity unit defined in the universal manifest."""
        manifest = self._load_universal_manifest()
        manager = self.manager_for(instance_index)
        return manager.ensure_quantity_units(manifest)

    def _load_universal_manifest(self) -> UniversalManifest:
        universal_dir = self.manifest_root / "universal"
        if not universal_dir.exists():
            raise ManifestNotFoundError(f"Missing universal manifest directory: {universal_dir}")
        return UniversalManifest.load(universal_dir)
