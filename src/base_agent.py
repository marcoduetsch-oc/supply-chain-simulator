"""Base agent class and event types for the supply chain simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    """A message one agent sends to another (or to itself)."""
    tick: int
    source: str
    target: str
    kind: str          # e.g. 'order_placed', 'stock_delivered', 'goods_shipped'
    data: dict = field(default_factory=dict)


class BaseAgent:
    """Every supply-chain agent extends this."""

    def __init__(self, name: str, log: list | None = None):
        self.name = name
        self.log = log or []   # shared log reference

    def reset(self):
        """Called once before the simulation starts."""
        raise NotImplementedError

    def step(self, tick: int, state: dict, events: list[Event]) -> list[Event]:
        """Called every tick.

        Args:
            tick:   current simulation tick (0-based)
            state:  shared mutable state dict (read / write)
            events: new events that arrived this tick

        Returns:
            list of new events to publish
        """
        raise NotImplementedError

    def _info(self, msg: str):
        self.log.append(msg)
