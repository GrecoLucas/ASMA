# config.py

XMPP_SERVER = "localhost"
PASSWORD = "password_super_secreta"
MAX_POWER_KW = 1.6  # Global power limit of the house for P2P negotiation

# JIDS of each agent
AGENTS = {
    "world": f"world@{XMPP_SERVER}",
    "environment": f"environment@{XMPP_SERVER}",
    "solar": f"solar@{XMPP_SERVER}",
    "fridge": f"fridge@{XMPP_SERVER}",
    "ac_livingroom": f"ac.livingroom@{XMPP_SERVER}",
    "washing_machine": f"washing_machine@{XMPP_SERVER}",
    "dish_washer": f"dish_washer@{XMPP_SERVER}",
    "battery": f"battery@{XMPP_SERVER}",
}

# Simulation 
SIMULATION_SPEED = 2
MINUTES_PER_STEP = 60

# Distributed P2P negotiation settings
NEGOTIATION_TIMEOUT_SEC = 5
NEGOTIATION_RETRY_LIMIT = 1
NEGOTIATION_LOOP_PERIOD_SEC = 1