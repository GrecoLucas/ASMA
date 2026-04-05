import json
from .device_base import Device

class SolarPanelAgent(Device):
    """
    Solar Panel Agent.
    It reads solar production from the environment and injects it into the grid (as negative consumed power).
    This offset helps other devices by effectively lowering the total house consumption,
    which may prevent load shedding.
    """

    def __init__(self, jid, password, max_capacity_kw=3.5, peers=None):
        super().__init__(jid, password, device_type="solar_panel", peers=peers)
        self.max_capacity_kw = max_capacity_kw
        self.current_solar_production = 0.0
        # Priority doesn't really matter as it has negative power, will never shed
        self.current_priority = 5

    def calculate_priority(self, world_state=None):
        return 5

    def update_sensors(self, world_state):
        if not world_state:
            return

        # Read actual simulated production from world state
        self.current_solar_production = world_state.get("solar_production", 0.0)
        
        if self.current_solar_production > 0:
            self.status = "PRODUCING"
        else:
            self.status = "IDLE"

    def get_power_consumption_kw(self):
        """Power is negative because it generates energy."""
        return -self.current_solar_production

    def get_device_state_for_gui(self):
        state = super().get_device_state_for_gui()
        # Ensure power_kw is reported appropriately negative for GUI visual cues
        state["power_kw"] = round(-self.current_solar_production, 3)
        return state
