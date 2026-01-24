from __future__ import annotations

import logging
from typing import Iterable

import caldav
from core.nextcloud.config import NextcloudConfig
from core.nextcloud.events import NextcloudCalendarEvent, build_ical_event

logger = logging.getLogger(__name__)

_DASH_TRANSLATION = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)


class NextcloudCalendarClient:
    """Thin client wrapper for creating events in Nextcloud calendars."""

    def __init__(self, config: NextcloudConfig) -> None:
        self.config = config
        self._client = _build_dav_client(config)
        self._calendars: dict[str, caldav.Calendar] = {}

    def calendar_for(self, calendar_name: str) -> caldav.Calendar:
        """Resolve and cache the configured calendar by name."""
        if calendar_name in self._calendars:
            return self._calendars[calendar_name]
        principal = self._client.principal()
        calendars = principal.calendars()
        target_name = _normalize_calendar_name(calendar_name)
        for calendar in calendars:
            name = _resolve_calendar_name(calendar)
            if name and _normalize_calendar_name(name) == target_name:
                self._calendars[calendar_name] = calendar
                return calendar
        calendar_names = [
            name for name in (_resolve_calendar_name(cal) for cal in calendars) if name
        ]
        available_names = ", ".join(calendar_names) if calendar_names else "none"
        raise ValueError(
            f"Calendar not found. Requested '{calendar_name}', available: {available_names}"
        )

    def create_events(self, events: Iterable[NextcloudCalendarEvent]) -> list[str]:
        """Create one or more calendar events and return their URLs when available."""
        event_list = list(events)
        if not event_list:
            return []
        created_urls: list[str] = []
        for event in event_list:
            calendar = self.calendar_for(event.calendar_name)
            ical_payload = build_ical_event(event)
            if event.item_kind == "task":
                created_event = calendar.add_todo(ical_payload)
            else:
                created_event = calendar.add_event(ical_payload)
            created_url = getattr(created_event, "url", None)
            if created_url is not None:
                created_urls.append(str(created_url))
        logger.info("Created %s Nextcloud events", len(event_list))
        return created_urls


def _build_dav_client(config: NextcloudConfig) -> caldav.DAVClient:
    try:
        return caldav.DAVClient(
            url=config.dav_url,
            username=config.username,
            password=config.password,
            timeout=config.request_timeout_seconds,
        )
    except TypeError:
        return caldav.DAVClient(
            url=config.dav_url,
            username=config.username,
            password=config.password,
        )


def _resolve_calendar_name(calendar: caldav.Calendar) -> str:
    name = getattr(calendar, "name", None)
    if name:
        return str(name)
    url = getattr(calendar, "url", None)
    if url is None:
        return ""
    return str(url)


def _normalize_calendar_name(value: str) -> str:
    return value.translate(_DASH_TRANSLATION).strip().lower()
