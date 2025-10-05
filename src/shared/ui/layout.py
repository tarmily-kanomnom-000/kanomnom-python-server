"""Reusable layout helpers for Flet containers."""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from .constants import COMMON_UI_LAYOUT


@dataclass(frozen=True, slots=True)
class LayoutConfig:
    """Configuration for a styled container."""

    padding: int
    border_radius: int
    background_color: str
    expand: int


def default_layout_config() -> LayoutConfig:
    """Return the standard layout configuration used across calculator pages."""

    return LayoutConfig(
        padding=COMMON_UI_LAYOUT.container_padding,
        border_radius=COMMON_UI_LAYOUT.container_border_radius,
        background_color=ft.Colors.BLUE_GREY_100,
        expand=1,
    )


def styled_container(content: ft.Control, config: LayoutConfig) -> ft.Container:
    """Wrap content in a Flet container using the supplied configuration."""

    return ft.Container(
        content=content,
        padding=config.padding,
        border_radius=config.border_radius,
        bgcolor=config.background_color,
        expand=config.expand,
    )


__all__ = ["LayoutConfig", "default_layout_config", "styled_container"]
