import json
import math
import random
import logging
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
from config import (
    AGENTS,
    PASSWORD,
    SIMULATION_SPEED,
    MINUTES_PER_STEP,
    SOLAR_PRODUCTION_START_HOUR,
    SOLAR_PRODUCTION_END_HOUR,
    SOLAR_WEATHER_FACTOR_MIN,
    SOLAR_WEATHER_FACTOR_MAX,
    SOLAR_PEAK_BY_SEASON_KW,
)

# Import GUI state if available
try:
    from gui import get_simulation_state
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

class WorldAgent(Agent):
    def __init__(self, jid, password, season="summer", receivers=None, enable_price_optimization=True):
        super().__init__(jid, password)
        self.enable_price_optimization = enable_price_optimization
        self.season = season.lower()
        self.receivers = receivers or []
        self.rng = random.Random(42)  # Fixed seed for reproducible generation
        self.clock_minutes = 0
        self.day_count = 1
        self.active_devices = {}  # Track active devices and their effects
        self.device_daily_consumption_kwh = {}
        self.hourly_consumption_by_slot = {}
        self.total_daily_consumption_kwh = 0.0
        self.last_hour_consumption_kwh = 0.0
        self.total_daily_cost_euro = 0.0
        self.total_daily_renewable_kwh = 0.0
        self.total_daily_solar_generated_kwh = 0.0
        self.last_world_state = {}
        self.daily_history = {}
        self.is_baseline = False

        # Bug 12 fix: initialize _renewable_per_slot in __init__ instead of lazy hasattr
        self._renewable_per_slot = {}

        # Base parameters for different seasons
        self.season_params = {
            "summer": {"base_temp": 22, "temp_range": 15, "solar_peak": 1.2},
            "winter": {"base_temp": 8, "temp_range": 12, "solar_peak": 0.8},
            "spring": {"base_temp": 15, "temp_range": 12, "solar_peak": 1.0},
            "autumn": {"base_temp": 12, "temp_range": 10, "solar_peak": 0.9}
        }

        # Initialize current temperature
        params = self.season_params.get(self.season, self.season_params["summer"])
        self.current_temperature = params["base_temp"]

    def reset_daily_energy_totals(self):
        """Reset daily consumption accounting at day rollover."""
        self.daily_history[self.day_count] = {
            "total_daily_consumption_kwh": self.total_daily_consumption_kwh,
            "total_daily_cost_euro": self.total_daily_cost_euro,
            "total_daily_renewable_kwh": self.total_daily_renewable_kwh,
            "total_daily_solar_generated_kwh": self.total_daily_solar_generated_kwh,
            "device_daily_consumption_kwh": self.device_daily_consumption_kwh.copy()
        }

        self.device_daily_consumption_kwh = {}
        self.hourly_consumption_by_slot = {}
        self.total_daily_consumption_kwh = 0.0
        self.total_daily_cost_euro = 0.0
        self.total_daily_renewable_kwh = 0.0
        self.total_daily_solar_generated_kwh = 0.0
        self.last_hour_consumption_kwh = 0.0
        # Bug 12 fix: _renewable_per_slot is now always initialized, just clear it
        self._renewable_per_slot.clear()
        if hasattr(self, '_solar_per_slot'):
            self._solar_per_slot.clear()

    def _is_battery(self, device_name):
        """Check if a device name refers to a battery agent (main or baseline)."""
        return device_name in ("battery", "b_batt")

    def register_device_consumption(self, device_name, day, hour, minute, consumption_kwh, energy_price=None, grid_charge_kwh=0.0):
        """Register step consumption from a device, de-duplicated by (day, hour, minute, device).
        
        grid_charge_kwh: Power specifically drawn from the grid (e.g. for battery arbitrage) 
        that should NOT be offset by solar.
        """
        if day != self.day_count:
            return

        slot_key = (day, hour, minute)
        slot_data = self.hourly_consumption_by_slot.setdefault(slot_key, {})
        
        # Track grid-only consumption separately
        if not hasattr(self, '_grid_charge_by_slot'):
            self._grid_charge_by_slot = {}
        slot_grid_charges = self._grid_charge_by_slot.setdefault(slot_key, {})

        if device_name in slot_data:
            return

        slot_data[device_name] = consumption_kwh
        if grid_charge_kwh > 0:
            slot_grid_charges[device_name] = grid_charge_kwh
        
        # Only add actual device consumption to the total (ignore renewable generation like solar or battery discharge)
        # But include battery CHARGING consumption (positive consumption_kwh)
        if consumption_kwh > 0:
            self.device_daily_consumption_kwh[device_name] = (
                self.device_daily_consumption_kwh.get(device_name, 0.0) + consumption_kwh
            )
            self.total_daily_consumption_kwh += consumption_kwh

        self.last_hour_consumption_kwh = round(sum(v for k, v in slot_data.items() if v > 0 and not self._is_battery(k)), 3)
        self.last_hour_grid_consumption_kwh = getattr(self, '_last_grid_cons', 0.0)
        self.last_hour_battery_consumption_kwh = getattr(self, '_last_battery_cons', 0.0)
        self.last_hour_cost_euro = getattr(self, '_last_hour_cost', 0.0)

        # Calculate renewable energy used after all devices in this slot are registered
        self._calculate_renewable_usage_for_slot(slot_key, energy_price)

    def _calculate_renewable_usage_for_slot(self, slot_key, energy_price=None):
        """
        Calculate how much renewable energy was actually used by devices in this time slot.
        """
        slot_data = self.hourly_consumption_by_slot.get(slot_key, {})
        if not slot_data:
            return

        renewable_available = 0.0
        house_consumption = 0.0
        battery_provided = 0.0
        battery_consumed = 0.0

        grid_only_charge = sum(getattr(self, '_grid_charge_by_slot', {}).get(slot_key, {}).values())
 
        for device_name, consumption_kwh in slot_data.items():
            if consumption_kwh < 0:
                # Negative = energy production (solar or battery discharge)
                if self._is_battery(device_name):
                    battery_provided += abs(consumption_kwh)
                else: # mostly solar and others
                    renewable_available += abs(consumption_kwh)
            elif consumption_kwh > 0:
                # Positive = energy consumption by actual devices
                if self._is_battery(device_name):
                    # For battery, total consumption includes solar_charge and grid_charge
                    # We subtract grid_only_charge to find what is eligible for solar
                    battery_consumed += max(0.0, consumption_kwh - getattr(self, '_grid_charge_by_slot', {}).get(slot_key, {}).get(device_name, 0.0))
                else:
                    house_consumption += consumption_kwh

        # 1. Solar powers the house first
        solar_to_house = min(renewable_available, house_consumption)
        house_remaining = max(0.0, house_consumption - solar_to_house)

        # 2. Leftover solar charges the battery
        solar_remaining = max(0.0, renewable_available - solar_to_house)
        solar_to_battery = min(solar_remaining, battery_consumed)

        # 3. Battery discharges to power the remaining house needs
        battery_to_house = min(battery_provided, house_remaining)
        house_remaining = max(0.0, house_remaining - battery_to_house)

        # 4. Grid covers house needs, any battery charging not met by solar, AND grid-only charges
        net_grid_consumption = house_remaining + max(0.0, battery_consumed - solar_to_battery) + grid_only_charge
        
        renewable_used_this_slot = solar_to_house + solar_to_battery

        # Get previous renewable and cost values for this slot (0 if not yet calculated)
        previous_renewable = getattr(self, '_renewable_per_slot', {}).get(slot_key, 0.0)
        previous_cost = getattr(self, '_cost_per_slot', {}).get(slot_key, 0.0)
        previous_solar = getattr(self, '_solar_per_slot', {}).get(slot_key, 0.0)

        # Store for display
        self._last_grid_cons = net_grid_consumption
        self._last_battery_cons = battery_to_house 
        self._last_solar_cons = solar_to_house
        self.last_hour_grid_consumption_kwh = round(self._last_grid_cons, 3)
        self.last_hour_battery_consumption_kwh = round(self._last_battery_cons, 3)
        self.last_hour_solar_consumption_kwh = round(self._last_solar_cons, 3)
        self.last_hour_solar_generated_kwh = round(renewable_available, 3)

        # Ensure dictionaries exist
        if not hasattr(self, '_renewable_per_slot'):
            self._renewable_per_slot = {}
        if not hasattr(self, '_cost_per_slot'):
            self._cost_per_slot = {}
        if not hasattr(self, '_solar_per_slot'):
            self._solar_per_slot = {}

        # Price fallback logic
        if energy_price is not None:
            price = energy_price
        elif self.last_world_state:
            price = self.last_world_state.get("energy_price", 0.12)
        else:
            price = 0.12

        new_cost_euro = net_grid_consumption * price

        # Update totals: remove old value, add new value
        self.total_daily_renewable_kwh -= previous_renewable
        self.total_daily_renewable_kwh += renewable_used_this_slot
        
        self.total_daily_solar_generated_kwh -= previous_solar
        self.total_daily_solar_generated_kwh += renewable_available
        
        self.total_daily_cost_euro -= previous_cost
        self.total_daily_cost_euro += new_cost_euro

        # Store new values for this slot
        self._renewable_per_slot[slot_key] = renewable_used_this_slot
        self._solar_per_slot[slot_key] = renewable_available
        self._cost_per_slot[slot_key] = new_cost_euro
        self._last_hour_cost = new_cost_euro
        self.last_hour_cost_euro = round(self._last_hour_cost, 3)

    def generate_temperature(self, hour):
        """Generate realistic temperature variations with smooth transitions."""
        params = self.season_params.get(self.season, self.season_params["summer"])
        base_temp = params["base_temp"]
        temp_range = params["temp_range"]

        # Calculate target temperature based on daily cycle (min at 6am, max at 3pm)
        cycle = math.cos((hour - 15) * math.pi / 12) * (temp_range / 2)
        target_temp = base_temp + cycle

        # Smooth transition: move current temp towards target by a small amount
        # This simulates thermal inertia in the environment, scaled by step size
        base_transition_rate_per_hour = 0.1  # How fast the temperature shifts per hour
        transition_rate = base_transition_rate_per_hour * (MINUTES_PER_STEP / 60.0)
        self.current_temperature += (target_temp - self.current_temperature) * transition_rate

        # Add small random variation for realistic weather fluctuations (±0.5°C)
        variation = self.rng.uniform(-0.5, 0.5)
        self.current_temperature += variation

        return round(self.current_temperature, 1)

    def generate_solar_production(self, hour):
        """Generate solar production based on sun patterns."""
        solar_peak = SOLAR_PEAK_BY_SEASON_KW.get(
            self.season,
            SOLAR_PEAK_BY_SEASON_KW["summer"]
        )

        # Solar production follows a sun-angle curve during the configured daylight window
        if SOLAR_PRODUCTION_START_HOUR <= hour <= SOLAR_PRODUCTION_END_HOUR:
            # Bell curve pattern with peak at noon
            daylight_hours = SOLAR_PRODUCTION_END_HOUR - SOLAR_PRODUCTION_START_HOUR
            angle = (hour - SOLAR_PRODUCTION_START_HOUR) * math.pi / daylight_hours
            production = solar_peak * math.sin(angle)

            # Add weather variability (clouds, etc.)
            weather_factor = self.rng.uniform(SOLAR_WEATHER_FACTOR_MIN, SOLAR_WEATHER_FACTOR_MAX)
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
        variation = self.rng.uniform(0.9, 1.1)
        price *= variation

        return round(price, 3)

    def generate_world_state(self):
        """Generate current world state data.

        Bug 9 fix: generate_temperature() mutates self.current_temperature internally.
        apply_device_effects() is called separately in WorldSimulationBehaviour AFTER
        this method, so here we read the temperature BEFORE device effects to avoid
        the field being set twice. The behaviour will overwrite state["temperature"]
        after applying device effects.
        """
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
            "hourly_consumption_total_kwh": round(getattr(self, 'last_hour_consumption_kwh', 0.0), 3),
            "hourly_grid_consumption_kwh": round(getattr(self, 'last_hour_grid_consumption_kwh', 0.0), 3),
            "hourly_battery_consumption_kwh": round(getattr(self, 'last_hour_battery_consumption_kwh', 0.0), 3),
            "hourly_solar_consumption_kwh": round(getattr(self, 'last_hour_solar_consumption_kwh', 0.0), 3),
            "hourly_cost_euro": round(getattr(self, 'last_hour_cost_euro', 0.0), 3),
            "daily_consumption_total_kwh": round(self.total_daily_consumption_kwh, 3),
            "hourly_solar_generated_kwh": round(getattr(self, 'last_hour_solar_generated_kwh', 0.0), 3),
            "daily_solar_generated_kwh": round(getattr(self, 'total_daily_solar_generated_kwh', 0.0), 3),
            "daily_cost_euro": round(self.total_daily_cost_euro, 3),
            "daily_renewable_kwh": round(self.total_daily_renewable_kwh, 3),
            "device_daily_consumption_kwh": {
                device: round(total, 3)
                for device, total in self.device_daily_consumption_kwh.items()
            },
            "simulated": True  # Flag to indicate this is simulated data
        }

    def apply_device_effects(self):
        """Apply temperature effects from active devices."""
        # AC cooling effect
        if self.active_devices.get("ac.livingroom") == "ON" or self.active_devices.get("b_ac") == "ON":
            # AC cools the environment gradually, reduced to step scale
            self.current_temperature -= 0.8 * (MINUTES_PER_STEP / 60.0)

        # Heater warming effect
        if self.active_devices.get("heater.livingroom") == "ON" or self.active_devices.get("b_heater") == "ON":
            # Heater warms the environment gradually, reduced to step scale
            self.current_temperature += 0.8 * (MINUTES_PER_STEP / 60.0)

        # Fridge cooling effect (minor, mostly contained)
        #if self.active_devices.get("fridge") == "ON":
            #self.current_temperature += 0.1 * (MINUTES_PER_STEP / 60.0)

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
                        # Bug 7 fix: read the energy_price sent by the device for this slot
                        energy_price = data.get("energy_price")
                        grid_charge_kwh = data.get("grid_charge_kwh", 0.0)
                        self.agent.register_device_consumption(
                            device_name=device_name,
                            day=day,
                            hour=hour,
                            minute=minute,
                            consumption_kwh=consumption_kwh,
                            energy_price=energy_price,
                            grid_charge_kwh=grid_charge_kwh,
                        )

                        if GUI_AVAILABLE and self.agent.last_world_state:
                            gui_state = get_simulation_state()
                            merged_state = self.agent.last_world_state.copy()
                            merged_state["hourly_consumption_total_kwh"] = round(getattr(self.agent, 'last_hour_consumption_kwh', 0.0), 3)
                            merged_state["hourly_grid_consumption_kwh"] = round(getattr(self.agent, 'last_hour_grid_consumption_kwh', 0.0), 3)
                            merged_state["hourly_battery_consumption_kwh"] = round(getattr(self.agent, 'last_hour_battery_consumption_kwh', 0.0), 3)
                            merged_state["hourly_solar_consumption_kwh"] = round(getattr(self.agent, 'last_hour_solar_consumption_kwh', 0.0), 3)
                            merged_state["hourly_cost_euro"] = round(getattr(self.agent, 'last_hour_cost_euro', 0.0), 3)
                            merged_state["hourly_solar_generated_kwh"] = round(getattr(self.agent, 'last_hour_solar_generated_kwh', 0.0), 3)
                            merged_state["daily_consumption_total_kwh"] = round(self.agent.total_daily_consumption_kwh, 3)
                            merged_state["daily_cost_euro"] = round(self.agent.total_daily_cost_euro, 3)
                            merged_state["daily_renewable_kwh"] = round(self.agent.total_daily_renewable_kwh, 3)
                            merged_state["daily_solar_generated_kwh"] = round(getattr(self.agent, 'total_daily_solar_generated_kwh', 0.0), 3)
                            merged_state["device_daily_consumption_kwh"] = {
                                device: round(total, 3)
                                for device, total in self.agent.device_daily_consumption_kwh.items()
                            }
                            
                            # Only update GUI if not baseline
                            if not getattr(self.agent, "is_baseline", False):
                                gui_state.update_world_state(merged_state)
                except (json.JSONDecodeError, KeyError) as e:
                    # Bug 14 fix: log instead of silently ignoring errors
                    logging.debug(f"[WorldAgent] DeviceStateListener parse error: {e}")

    class WorldSimulationBehaviour(PeriodicBehaviour):
        """Behavior that simulates world conditions and broadcasts them."""
        async def run(self):
            if GUI_AVAILABLE and get_simulation_state().is_paused:
                return

            # Bug 9 fix: generate_world_state() calls generate_temperature() which already
            # mutates self.current_temperature. apply_device_effects() then makes a
            # second mutation. To keep the logic clean:
            # 1. Generate the base world state (temperature from natural cycle)
            # 2. Apply device effects to self.current_temperature
            # 3. Overwrite state["temperature"] with the post-effects value
            # This preserves the intended design without double-applying random noise.
            state = self.agent.generate_world_state()

            # Apply device effects AFTER natural temp calculation
            self.agent.apply_device_effects()

            # Update state with modified temperature after device effects
            state["temperature"] = round(self.agent.current_temperature, 1)

            self.agent.last_world_state = state.copy()

            # Inject solar production into the consumption tracker
            # Reuse the value already generated in generate_world_state() to avoid
            # a second random draw that would track different solar than what's broadcast.
            solar_power_kw = state["solar_production"]
            # Register it as negative consumption, since it produces energy
            self.agent.register_device_consumption(
                device_name="solar",
                day=state["day"],
                hour=state["hour"],
                minute=state["minute"],
                consumption_kwh=-solar_power_kw * (MINUTES_PER_STEP / 60.0),
                energy_price=0.0
            )

            # Update GUI state
            if GUI_AVAILABLE and not getattr(self.agent, "is_baseline", False):
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

                self.agent.reset_daily_energy_totals()
                self.agent.day_count += 1
                
                # Check if we should trigger report generation
                if hasattr(self.agent, 'on_day_end') and callable(self.agent.on_day_end):
                    self.agent.on_day_end(self.agent.day_count - 1)

    async def setup(self):

        # Start behaviors
        self.add_behaviour(self.WorldSimulationBehaviour(period=SIMULATION_SPEED))
        self.add_behaviour(self.DeviceStateListener())