import json
from .device_base import Device

class BatteryAgent(Device):
    """
    Battery Agent.
    Stores excess energy from solar panels and discharges it during high-price peak hours
    or when house consumption is very high, prioritizing self-consumption and saving costs.
    """

    def __init__(self, jid, password, capacity_kwh=5.0, max_rate_kw=2.0, price_threshold=0.15, peers=None):
        super().__init__(jid, password, device_type="battery", peers=peers)
        self.capacity_kwh = capacity_kwh
        self.current_charge_kwh = 0.0  # Starts empty
        self.max_rate_kw = max_rate_kw
        self.price_threshold = price_threshold
        self.current_power_kw = 0.0
        self.current_priority = 5

    def calculate_priority(self, world_state=None):
        return 5

    def update_sensors(self, world_state):
        from config import MINUTES_PER_STEP
        if not world_state:
            return

        price = world_state.get("energy_price", 0.0)
        
        # Calculate net house power from peers (includes solar which is negative)
        net_house_power = sum(data.get("power_kw", 0.0) for data in self.peer_power_status.values())

        # Determine battery operation limits based on current charge
        step_hours = MINUTES_PER_STEP / 60.0
        max_possible_charge = (self.capacity_kwh - self.current_charge_kwh) / step_hours
        max_possible_discharge = self.current_charge_kwh / step_hours

        # Actual limits are the minimum of physical rate and available charge
        limit_charge_kw = min(self.max_rate_kw, max_possible_charge)
        limit_discharge_kw = min(self.max_rate_kw, max_possible_discharge)

        # Logic Cascade
        if net_house_power < -0.01:
            # Excess solar energy, charge
            charge_amount = min(limit_charge_kw, abs(net_house_power))
            self.current_power_kw = charge_amount
            if self.current_power_kw > 0.01:
                self.status = "CHARGING"
            else:
                self.status = "FULL" if self.current_charge_kwh >= self.capacity_kwh else "IDLE"
                
        elif net_house_power > 0.01 and price >= self.price_threshold:
            # Price is high, let's discharge to offset house consumption
            # We want to provide up to net_house_power
            # battery power becomes negative (injecting into local grid)
            discharge_amount = min(limit_discharge_kw, net_house_power)
            self.current_power_kw = -discharge_amount
            if self.current_power_kw < -0.01:
                self.status = "DISCHARGING"
            else:
                self.status = "EMPTY" if self.current_charge_kwh <= 0 else "IDLE"
        else:
            # Price is normal and no excess solar
            self.current_power_kw = 0.0
            self.status = "IDLE"

    def update_energy_counters(self, world_state):
        # Update daily/hourly stats normally
        super().update_energy_counters(world_state)
        
        # Update internal battery state based on consumption
        # positive consumption means charging, negative means discharging
        self.current_charge_kwh += self.hourly_consumption_kwh
        self.current_charge_kwh = max(0.0, min(self.capacity_kwh, self.current_charge_kwh))

    def get_power_consumption_kw(self):
        return self.current_power_kw

    def get_device_state_for_gui(self):
        state = super().get_device_state_for_gui()
        state["charge_kwh"] = round(self.current_charge_kwh, 2)
        state["capacity_kwh"] = round(self.capacity_kwh, 2)
        state["charge_percent"] = round((self.current_charge_kwh / self.capacity_kwh) * 100, 1)
        return state
