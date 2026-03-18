import asyncio
import json
import math
import random
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
from config import AGENTS, PASSWORD, SIMULATION_SPEED

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
        self.current_hour = 0
        self.day_count = 0
        self.active_devices = {}  # Track active devices and their effects

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
        return {
            "hour": self.current_hour,
            "temperature": self.generate_temperature(self.current_hour),
            "solar_production": self.generate_solar_production(self.current_hour),
            "energy_price": self.generate_electricity_price(self.current_hour),
            "season": self.season,
            "day": self.day_count,
            "simulated": True  # Flag to indicate this is simulated data
        }
    
    def apply_device_effects(self):
        """Apply temperature effects from active devices."""
        # AC cooling effect
        if self.active_devices.get("ac.livingroom") == "ON":
            # AC cools the environment gradually
            self.current_temperature -= 0.8
            print(f"[WorldAgent] AC is ON: cooling effect applied (now {self.current_temperature:.1f}°C)")

        # Fridge cooling effect (minor, mostly contained)
        if self.active_devices.get("fridge") == "ON":
            self.current_temperature += 0.1

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
                        print(f"[WorldAgent] Device '{device_name}' state: {state}")
                except (json.JSONDecodeError, KeyError) as e:
                    pass  # Ignore invalid messages

    class WorldSimulationBehaviour(PeriodicBehaviour):
        """Behavior that simulates world conditions and broadcasts them."""
        async def run(self):
            # Advance time
            self.agent.current_hour = (self.agent.current_hour + 1) % 24

            # New day started
            if self.agent.current_hour == 0:
                self.agent.day_count += 1
                print("\n" + "="*60)
                print(f"NEW SIMULATED DAY {self.agent.day_count} ({self.agent.season.upper()})")
                print("="*60)

            # Generate world state (natural temperature first)
            state = self.agent.generate_world_state()

            # Apply device effects AFTER natural temp calculation
            self.agent.apply_device_effects()

            # Update state with modified temperature after device effects
            state["temperature"] = round(self.agent.current_temperature, 1)

            # Log current conditions
            active_info = f" | Active devices: {', '.join(self.agent.active_devices.keys())}" if self.agent.active_devices else ""
            print(f"[WorldAgent] {state['hour']:02d}:00 | Temp: {state['temperature']}°C | "
                  f"Solar: {state['solar_production']}kW | Price: {state['energy_price']}€{active_info}")

            # Update GUI state
            if GUI_AVAILABLE:
                gui_state = get_simulation_state()
                gui_state.update_world_state(state)

            # Broadcast state to all receiver agents
            for receiver_jid in self.agent.receivers:
                msg = Message(to=receiver_jid)
                msg.body = json.dumps(state)
                await self.send(msg)

    async def setup(self):
        print(f"WorldAgent [{self.name}] starting simulation...")
        print(f"Season: {self.season.title()}, Speed: {SIMULATION_SPEED}s/hour")

        # Start behaviors
        self.add_behaviour(self.WorldSimulationBehaviour(period=SIMULATION_SPEED))
        self.add_behaviour(self.DeviceStateListener())