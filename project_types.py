"""Shared type definitions and protocols for the project."""
from __future__ import annotations

from typing import Any, Protocol, TypedDict


class CommandDict(TypedDict):
    """Shape of a voice command entry in config.COMMANDS."""
    cmd: str
    func: str
    args: bool


class LightsProtocol(Protocol):
    """Protocol for the lights controller used by commands and hardware."""

    def set_color(self, color_name: str) -> None: ...
    def change_after(self, seconds: float, mode: str | None = None) -> None: ...
    def stop(self, fade_time: float = 1.0, steps: int = 20) -> None: ...
    def set_solid(self, color_name: str) -> None: ...
    def turn_off(self) -> None: ...
    def is_stopped(self) -> bool: ...


# Convenience alias for "any lights-like object"
LightsLike = LightsProtocol
