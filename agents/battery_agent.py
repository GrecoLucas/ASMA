import json
from .device_base import Device

class BatteryAgent(Device):
    """
    Battery Agent with integrated Solar logic.
    Stores energy from solar panels directly. Agents use energy from the battery.
    Can charge and discharge simultaneously.
    """

    def __init__(self, jid, password, capacity_kwh=5.0, max_rate_kw=2.0, price_threshold=0.15, peers=None):
        super().__init__(jid, password, device_type="battery", peers=peers)
        self.capacity_kwh = capacity_kwh
        self.current_charge_kwh = 0.0  # Starts empty
        self.max_rate_kw = max_rate_kw
        self.price_threshold = price_threshold  # Kept for signature compatibility
        self.current_power_kw = 0.0
        self.battery_flow_kw = 0.0
        self.current_priority = 5

    def calculate_priority(self, world_state=None):
        return 5

    def update_sensors(self, world_state):
        from config import MINUTES_PER_STEP
        if not world_state:
            return

        solar_production = world_state.get("solar_production", 0.0)

        # Calculate house consumption from peers (positive power only)
        house_consumption_kw = sum(data.get("power_kw", 0.0) for data in self.peer_power_status.values() if data.get("power_kw", 0.0) > 0)

        # Determine battery limits
        step_hours = MINUTES_PER_STEP / 60.0
        max_possible_charge = (self.capacity_kwh - self.current_charge_kwh) / step_hours
        max_possible_discharge = self.current_charge_kwh / step_hours

        # 1. Energia solar deve ser armazenada na bateria (Charge from solar)
        charging_from_solar = min(self.max_rate_kw, max_possible_charge, solar_production)

        # 2. Agentes usam energia da bateria (Discharge to house)
        # Bateria deveria dar para carregar e utilizar ao mesmo tempo
        effective_discharge_limit = min(self.max_rate_kw, max_possible_discharge + charging_from_solar)
        discharging_to_house = min(effective_discharge_limit, house_consumption_kw)
        
        # Calculate battery net internal flow
        self.battery_flow_kw = charging_from_solar - discharging_to_house

        # Calculate total grid power exchange for this agent
        self.current_power_kw = charging_from_solar - discharging_to_house - solar_production

        # Update status based on battery exact flow
        if charging_from_solar > 0.01 and discharging_to_house > 0.01:
            self.status = "CHARGING & DISCHARGING"
        elif charging_from_solar > 0.01:
            self.status = "CHARGING"
        elif discharging_to_house > 0.01:
            self.status = "DISCHARGING"
        else:
            self.status = "FULL" if self.current_charge_kwh >= self.capacity_kwh - 0.01 else "IDLE"

    def update_energy_counters(self, world_state):
        # Update daily/hourly stats normally (uses self.current_power_kw for grid consumption logic)
        super().update_energy_counters(world_state)
        
        # Update internal battery state based on internal flow, not grid power
        from config import MINUTES_PER_STEP
        step_hours = MINUTES_PER_STEP / 60.0
        self.current_charge_kwh += self.battery_flow_kw * step_hours
        self.current_charge_kwh = max(0.0, min(self.capacity_kwh, self.current_charge_kwh))

    def get_power_consumption_kw(self):
        return self.current_power_kw

    def get_device_state_for_gui(self):
        state = super().get_device_state_for_gui()
        state["charge_kwh"] = round(self.current_charge_kwh, 2)
        state["capacity_kwh"] = round(self.capacity_kwh, 2)
        state["charge_percent"] = round((self.current_charge_kwh / self.capacity_kwh) * 100, 1)
        state["battery_flow_kw"] = round(self.battery_flow_kw, 3)
        return state
