"""Common Flet UI layout constants shared across pages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommonUILayout:
    """Typed container for UI layout constants to keep pages in sync."""

    column_spacing: int
    container_padding: int
    container_border_radius: int
    button_spacing: int
    text_field_width: int


COMMON_UI_LAYOUT = CommonUILayout(
    column_spacing=20,
    container_padding=20,
    container_border_radius=10,
    button_spacing=10,
    text_field_width=100,
)


__all__ = ["CommonUILayout", "COMMON_UI_LAYOUT"]
