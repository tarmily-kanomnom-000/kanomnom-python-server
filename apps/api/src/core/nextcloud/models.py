from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NextcloudInstanceMetadata:
    """Connection metadata for a Nextcloud CalDAV instance."""

    instance_key: str
    dav_url: str
    calendars: list["NextcloudCalendarMetadata"]


@dataclass(frozen=True)
class NextcloudInstanceCredentials:
    """Credentials for a Nextcloud CalDAV instance."""

    username: str
    password: str


@dataclass(frozen=True)
class NextcloudCalendarMetadata:
    """Calendar metadata stored in the Nextcloud manifest."""

    name: str
    description: str | None
    tags: list[str]
