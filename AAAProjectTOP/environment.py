"""
environment.py – Stateless helpers that describe the simulated world at any hour.

This module does NOT hold simulation state; it just provides look-up functions
so that agents can query prices / solar production without coupling to a clock.
"""

import config


def get_price(hour: int) -> float:
    """Return electricity price (€/kWh) for the given simulation hour."""
    return config.ELECTRICITY_PRICES[hour % 24]


def get_solar(hour: int) -> float:
    """Return solar production (kW) for the given simulation hour."""
    return config.SOLAR_PRODUCTION[hour % 24]


def is_cheap(hour: int) -> bool:
    return get_price(hour) <= config.PRICE_CHEAP


def is_expensive(hour: int) -> bool:
    return get_price(hour) >= config.PRICE_EXPENSIVE


def has_solar(hour: int) -> bool:
    return get_solar(hour) >= config.SOLAR_USEFUL


def hour_label(hour: int) -> str:
    return f"{hour:02d}:00"


def describe_hour(hour: int) -> str:
    price  = get_price(hour)
    solar  = get_solar(hour)
    label  = "CHEAP" if is_cheap(hour) else ("EXPENSIVE" if is_expensive(hour) else "MEDIUM")
    return (f"Hour {hour_label(hour)}  price={price:.2f}€/kWh [{label}]  "
            f"solar={solar:.1f}kW {'☀' if has_solar(hour) else '🌑'}")
