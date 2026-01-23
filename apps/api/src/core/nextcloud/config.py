from __future__ import annotations

from dataclasses import dataclass

from core.nextcloud.models import (
    NextcloudCalendarMetadata,
    NextcloudInstanceCredentials,
    NextcloudInstanceMetadata,
)

_DEFAULT_REQUEST_TIMEOUT_SECONDS = 15.0
_DEFAULT_EVENT_DURATION_MINUTES = 15


@dataclass(frozen=True)
class NextcloudConfig:
    instance_key: str
    dav_url: str
    calendars: list[NextcloudCalendarMetadata]
    username: str
    password: str
    request_timeout_seconds: float
    event_duration_minutes: int


def load_nextcloud_config(
    metadata: NextcloudInstanceMetadata,
    credentials: NextcloudInstanceCredentials,
) -> NextcloudConfig:
    """Load Nextcloud configuration for the provided instance metadata and credentials."""
    instance_key = metadata.instance_key
    dav_url = metadata.dav_url.rstrip("/")
    request_timeout = _DEFAULT_REQUEST_TIMEOUT_SECONDS
    event_duration = _DEFAULT_EVENT_DURATION_MINUTES
    return NextcloudConfig(
        instance_key=instance_key,
        dav_url=dav_url,
        calendars=list(metadata.calendars),
        username=credentials.username,
        password=credentials.password,
        request_timeout_seconds=request_timeout,
        event_duration_minutes=event_duration,
    )
