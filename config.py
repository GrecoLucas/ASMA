# config.py

XMPP_SERVER = "localhost"
PASSWORD = "password_super_secreta"

# JIDS de cada agente
AGENTS = {
    "world": f"world@{XMPP_SERVER}",
    "environment": f"environment@{XMPP_SERVER}",
    "solar": f"solar@{XMPP_SERVER}",
    "fridge": f"fridge@{XMPP_SERVER}"
}

# Simulation 
SIMULATION_SPEED = 2