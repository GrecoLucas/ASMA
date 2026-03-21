# config.py

XMPP_SERVER = "localhost"
PASSWORD = "password_super_secreta"
MAX_POWER_KW = 7.0  # Global power limit of the house for P2P negotiation

# JIDS of each agent
AGENTS = {
    "world": f"world@{XMPP_SERVER}",
    "environment": f"environment@{XMPP_SERVER}",
    "solar": f"solar@{XMPP_SERVER}",
    "fridge": f"fridge@{XMPP_SERVER}",
    "ac_livingroom": f"ac.livingroom@{XMPP_SERVER}"
}

# Simulation 
SIMULATION_SPEED = 2