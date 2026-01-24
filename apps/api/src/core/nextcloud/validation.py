from __future__ import annotations

from dataclasses import dataclass

from core.nextcloud.config import load_nextcloud_config
from core.nextcloud.credentials import NextcloudCredentialsRepository
from core.nextcloud.metadata import NextcloudMetadataRepository
from core.nextcloud.models import NextcloudCalendarMetadata


@dataclass(frozen=True)
class NextcloudManifestValidationConfig:
    required_order_tag: str


def validate_nextcloud_manifests(
    metadata_repository: NextcloudMetadataRepository,
    credentials_repository: NextcloudCredentialsRepository,
    config: NextcloudManifestValidationConfig,
) -> None:
    """Validate Nextcloud manifests and raise if required tags are missing."""
    instance_keys = metadata_repository.list_instance_keys()
    for instance_key in instance_keys:
        metadata = metadata_repository.load(instance_key)
        credentials = credentials_repository.load(instance_key)
        resolved_config = load_nextcloud_config(metadata, credentials)
        _require_single_tag(
            resolved_config.calendars, config.required_order_tag, instance_key
        )


def _require_single_tag(
    calendars: list[NextcloudCalendarMetadata],
    tag: str,
    instance_key: str,
) -> None:
    matches = [calendar for calendar in calendars if tag in calendar.tags]
    if len(matches) == 1:
        return
    if len(matches) == 0:
        raise ValueError(
            f"Nextcloud instance {instance_key} missing calendar tag '{tag}'."
        )
    raise ValueError(
        f"Nextcloud instance {instance_key} has multiple calendars with tag '{tag}'."
    )
