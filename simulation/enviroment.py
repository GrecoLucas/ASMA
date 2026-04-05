import json
import math
import random
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
from config import AGENTS, PASSWORD, SIMULATION_SPEED, MINUTES_PER_STEP

# Import GUI state if available
try:
    from gui import get_simulation_state
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False 

class WorldAgent(Agent):
    def __init__(self, jid, password, season="summer", receivers=None):
        super().__init__(jid, password)
        self.season = season.lower()
        self.receivers = receivers or []
        self.clock_minutes = 0
        self.day_count = 1
        self.active_devices = {}  # Track active devices and their effects
        self.device_daily_consumption_kwh = {}
        self.hourly_consumption_by_slot = {}
        self.total_daily_consumption_kwh = 0.0
        self.last_hour_consumption_kwh = 0.0
        self.total_daily_cost_euro = 0.0
        self.total_renewable_kwh = 0.0
        self.last_world_state = {}

        # Base parameters for different seasons
        self.season_params = {
            "summer": {"base_temp": 22, "temp_range": 15, "solar_peak": 3.5},
            "winter": {"base_temp": 8, "temp_range": 12, "solar_peak": 1.8},
            "spring": {"base_temp": 15, "temp_range": 12, "solar_peak": 2.8},
            "autumn": {"base_temp": 12, "temp_range": 10, "solar_peak": 2.2}
        }

        # Initialize current temperature
        params = self.season_params.get(self.season, self.season_params["summer"])
        self.current_temperature = params["base_temp"]

    def reset_daily_energy_totals(self):
        """Reset daily consumption accounting at day rollover."""
        self.device_daily_consumption_kwh = {}
        self.hourly_consumption_by_slot = {}
        self.total_daily_consumption_kwh = 0.0
        self.total_daily_cost_euro = 0.0
        self.total_renewable_kwh = 0.0
        self.last_hour_consumption_kwh = 0.0

    def register_device_consumption(self, device_name, day, hour, minute, consumption_kwh):
        """Register step consumption from a device, de-duplicated by (day, hour, minute, device)."""
        if day != self.day_count:
            return

        slot_key = (day, hour, minute)
        slot_data = self.hourly_consumption_by_slot.setdefault(slot_key, {})

        if device_name in slot_data:
            return

        slot_data[device_name] = consumption_kwh
        self.device_daily_consumption_kwh[device_name] = (
            self.device_daily_consumption_kwh.get(device_name, 0.0) + consumption_kwh
        )
        self.total_daily_consumption_kwh += consumption_kwh
        # Track renewable specifically (solar panel inherently sends negative consumption)
        if device_name == "solar" and consumption_kwh < 0:
            self.total_renewable_kwh += abs(consumption_kwh)

        self.last_hour_consumption_kwh = round(sum(slot_data.values()), 3)

    def generate_temperature(self, hour):
        """Generate realistic temperature variations with smooth transitions."""
        params = self.season_params.get(self.season, self.season_params["summer"])
        base_temp = params["base_temp"]
        temp_range = params["temp_range"]

        # Calculate target temperature based on daily cycle (min at 6am, max at 3pm)
        cycle = math.cos((hour - 15) * math.pi / 12) * (temp_range / 2)
        target_temp = base_temp + cycle

        # Smooth transition: move current temp towards target by a small amount
        # This simulates thermal inertia in the environment
        transition_rate = 0.1  # How fast the temperature shifts (0-1, higher = faster)
        self.current_temperature += (target_temp - self.current_temperature) * transition_rate

        # Add small random variation for realistic weather fluctuations (±0.5°C)
        variation = random.uniform(-0.5, 0.5)
        self.current_temperature += variation

        return round(self.current_temperature, 1)

    def generate_solar_production(self, hour):
        """Generate solar production based on sun patterns."""
        params = self.season_params.get(self.season, self.season_params["summer"])
        solar_peak = params["solar_peak"]
        
        # Solar production follows sun angle (6am to 6pm)
        if 6 <= hour <= 18:
            # Bell curve pattern with peak at noon
            angle = (hour - 6) * math.pi / 12
            production = solar_peak * math.sin(angle)
            
            # Add weather variability (clouds, etc.)
            weather_factor = random.uniform(0.7, 1.0)
            production *= weather_factor
        else:
            production = 0.0
        
        return round(max(0, production), 2)

    def generate_electricity_price(self, hour):
        """Generate electricity price with peak/off-peak patterns."""
        # Base price
        base_price = 0.12
        
        # Peak hours (7-9am and 6-8pm) have higher prices
        if (7 <= hour <= 9) or (18 <= hour <= 20):
            peak_multiplier = 2.0
        # Off-peak hours (10pm to 6am) have lower prices
        elif hour >= 22 or hour <= 6:
            peak_multiplier = 0.7
        else:
            peak_multiplier = 1.2
        
        price = base_price * peak_multiplier
        
        # Add market variation
        variation = random.uniform(0.9, 1.1)
        price *= variation
        
        return round(price, 3)

    def generate_world_state(self):
        """Generate current world state data."""
        hour = self.clock_minutes // 60
        minute = self.clock_minutes % 60
        float_hour = hour + minute / 60.0
        
        return {
            "hour": hour,
            "minute": minute,
            "temperature": self.generate_temperature(float_hour),
            "solar_production": self.generate_solar_production(float_hour),
            "energy_price": self.generate_electricity_price(float_hour),
            "season": self.season,
            "day": self.day_count,
            "hourly_consumption_total_kwh": round(self.last_hour_consumption_kwh, 3),
            "daily_consumption_total_kwh": round(self.total_daily_consumption_kwh, 3),
            "daily_cost_euro": round(self.total_daily_cost_euro, 3),
            "daily_renewable_kwh": round(self.total_renewable_kwh, 3),
            "device_daily_consumption_kwh": {
                device: round(total, 3)
                for device, total in self.device_daily_consumption_kwh.items()
            },
            "simulated": True  # Flag to indicate this is simulated data
        }
    
    def apply_device_effects(self):
        """Apply temperature effects from active devices."""
        # AC cooling effect
        if self.active_devices.get("ac.livingroom") == "ON":
            # AC cools the environment gradually, reduced to step scale
            self.current_temperature -= 0.8 * (MINUTES_PER_STEP / 60.0)

        # Fridge cooling effect (minor, mostly contained)
        if self.active_devices.get("fridge") == "ON":
            self.current_temperature += 0.1 * (MINUTES_PER_STEP / 60.0)

    class DeviceStateListener(CyclicBehaviour):
        """Listen for device state change messages."""
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    data = json.loads(msg.body)
                    device_name = data.get("device_name")
                    state = data.get("state")
                    event = data.get("event")

                    if event == "state_changed":
                        self.agent.active_devices[device_name] = state
                    elif event == "device_consumption":
                        hour = data.get("hour")
                        minute = data.get("minute", 0)
                        day = data.get("day")
                        consumption_kwh = float(data.get("consumption_kwh", 0.0))
                        self.agent.register_device_consumption(
                            device_name=device_name,
                            day=day,
                            hour=hour,
                            minute=minute,
                            consumption_kwh=consumption_kwh,
                        )

                        if GUI_AVAILABLE and self.agent.last_world_state:
                            gui_state = get_simulation_state()
                            merged_state = self.agent.last_world_state.copy()
                            merged_state["hourly_consumption_total_kwh"] = round(self.agent.last_hour_consumption_kwh, 3)
                            merged_state["daily_consumption_total_kwh"] = round(self.agent.total_daily_consumption_kwh, 3)
                            merged_state["daily_cost_euro"] = round(self.agent.total_daily_cost_euro, 3)
                            merged_state["daily_renewable_kwh"] = round(self.agent.total_renewable_kwh, 3)
                            merged_state["device_daily_consumption_kwh"] = {
                                device: round(total, 3)
                                for device, total in self.agent.device_daily_consumption_kwh.items()
                            }
                            gui_state.update_world_state(merged_state)
                except (json.JSONDecodeError, KeyError) as e:
                    pass  # Ignore invalid messages

    class WorldSimulationBehaviour(PeriodicBehaviour):
        """Behavior that simulates world conditions and broadcasts them."""
        async def run(self):
            if GUI_AVAILABLE and get_simulation_state().is_paused:
                return

            # Simulate current hour state first, then advance to the next hour.
            state = self.agent.generate_world_state()

            # Apply device effects AFTER natural temp calculation
            self.agent.apply_device_effects()

            # Update state with modified temperature after device effects
            state["temperature"] = round(self.agent.current_temperature, 1)

            # Calculate cost for the current step based on net house consumption
            price = state["energy_price"]
            net_power = 0.0
            if GUI_AVAILABLE:
                gui_state = get_simulation_state()
                devs = gui_state.get_all_devices()
                for d in devs:
                    d_state = gui_state.get_device_state(d)
                    net_power += d_state.get("power_kw", 0.0)
            
            if net_power > 0:
                step_consumption = net_power * (MINUTES_PER_STEP / 60.0)
                self.agent.total_daily_cost_euro += step_consumption * price

            self.agent.last_world_state = state.copy()


            # Update GUI state
            if GUI_AVAILABLE:
                gui_state = get_simulation_state()
                gui_state.update_world_state(state)

            # Broadcast state to all receiver agents
            for receiver_jid in self.agent.receivers:
                msg = Message(to=receiver_jid)
                msg.body = json.dumps(state)
                await self.send(msg)

            # Advance time step
            self.agent.clock_minutes += MINUTES_PER_STEP

            # At midnight (1440 mins), close previous day and reset counters.
            if self.agent.clock_minutes >= 1440:
                self.agent.clock_minutes = 0

                self.agent.day_count += 1
                self.agent.reset_daily_energy_totals()

    async def setup(self):

        # Start behaviors
        self.add_behaviour(self.WorldSimulationBehaviour(period=SIMULATION_SPEED))
        self.add_behaviour(self.DeviceStateListener())