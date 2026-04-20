"""
config.py – Central configuration for the Smart Home MAS simulation.
All tuneable constants live here so you only have one place to change things.
"""

# ── XMPP / SPADE ────────────────────────────────────────────────────────────
XMPP_SERVER = "localhost"   # use the same local Prosody host as the main ASMA project
AGENT_PASSWORD = "password_super_secreta"  # aligned with working ASMA setup

# Agent JIDs (project-specific to avoid conflicts with the main ASMA project)
WORLD_JID    = f"aaa_world@{XMPP_SERVER}"
WASHING_JID  = f"aaa_washing@{XMPP_SERVER}"
HEATER_JID   = f"aaa_heater@{XMPP_SERVER}"
BATTERY_JID  = f"aaa_battery@{XMPP_SERVER}"
SOLAR_JID    = f"aaa_solar@{XMPP_SERVER}"

ALL_DEVICE_JIDS = [WASHING_JID, HEATER_JID, BATTERY_JID, SOLAR_JID]

# ── SIMULATION ───────────────────────────────────────────────────────────────
SIMULATION_HOURS = 24          # hours 0-23
TICK_DURATION    = 2.5         # real seconds per simulated hour (speed up the demo)

# ── ELECTRICITY PRICES (€/kWh) by hour 0-23 ─────────────────────────────────
ELECTRICITY_PRICES = [
    0.06, 0.06, 0.05, 0.05, 0.05, 0.07,   # 00-05  night  (cheap)
    0.09, 0.12, 0.16, 0.18, 0.20, 0.22,   # 06-11  morning peak
    0.20, 0.18, 0.16, 0.15, 0.17, 0.21,   # 12-17  afternoon
    0.24, 0.26, 0.22, 0.18, 0.14, 0.10,   # 18-23  evening peak → night
]

# ── SOLAR PRODUCTION (kW) by hour 0-23 ──────────────────────────────────────
SOLAR_PRODUCTION = [
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0,         # 00-05  night
    0.1, 0.4, 0.9, 1.4, 2.0, 2.6,         # 06-11  rising
    3.0, 3.2, 2.8, 2.4, 1.8, 1.0,         # 12-17  peak
    0.4, 0.1, 0.0, 0.0, 0.0, 0.0,         # 18-23  sunset
]

# ── DECISION THRESHOLDS ──────────────────────────────────────────────────────
PRICE_CHEAP     = 0.10   # €/kWh – run freely below this
PRICE_EXPENSIVE = 0.18   # €/kWh – avoid running above this if possible
SOLAR_USEFUL    = 0.5    # kW    – minimum solar to be considered "available"

# ── WASHING MACHINE ──────────────────────────────────────────────────────────
WASHING_POWER_KW    = 2.0   # kW consumed while running
WASHING_DURATION_H  = 2     # hours needed to complete a cycle
WASHING_DEADLINE_H  = 22    # must START by this hour (so it finishes by 24)
WASHING_EARLIEST_H  = 6     # earliest allowed start hour

# ── HEATER ───────────────────────────────────────────────────────────────────
HEATER_POWER_KW          = 1.5    # kW consumed while heating
HEATER_MIN_TEMP          = 19.0   # °C – turn on if temperature falls below
HEATER_MAX_TEMP          = 22.0   # °C – turn off when temperature reaches
HEATER_TEMP_INITIAL      = 21.0   # °C – starting room temperature
HEATER_TEMP_LOSS_PER_H   = 0.8    # °C lost per hour when heater is off
HEATER_TEMP_GAIN_PER_H   = 1.5    # °C gained per hour when heater is on

# ── BATTERY ──────────────────────────────────────────────────────────────────
BATTERY_CAPACITY_KWH    = 5.0    # total usable capacity
BATTERY_CHARGE_RATE_KW  = 1.2    # max charge per hour
BATTERY_DISCHARGE_KW    = 1.5    # max discharge per hour
BATTERY_INITIAL_SOC     = 0.30   # starting state-of-charge (30 %)
BATTERY_MIN_SOC         = 0.10   # never discharge below 10 %
BATTERY_MAX_SOC         = 0.95   # never charge above 95 %
BATTERY_EFFICIENCY      = 0.92   # round-trip efficiency

# ── WEBSOCKET UI ──────────────────────────────────────────────────────────
WS_PORT                 = 8080
