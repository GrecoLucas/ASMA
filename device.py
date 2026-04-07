"""Compatibility layer.

Device agents were moved to the `agents` package.
This module re-exports the same classes to avoid breaking old imports.
"""

from agents import AirConditioner, Refrigerator, 
from agents.device_base import Device, Rule

__all__ = [
    "Rule",
    "Device",
    "AirConditioner",
    "Refrigerator",
    "WashingMachine",
    "DishWasher",
]
