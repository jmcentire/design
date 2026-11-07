"""Inventory boundary for later site and rendered checks (M1/M4)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Requirement:
    construct: str
    slot: str | None = None
    state: str = "default"
    asset_kind: str | None = None
