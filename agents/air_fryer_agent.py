from .device_base import Device, Rule
from config import (
    AIR_FRYER_ACTIVE_POWER_KW, AIR_FRYER_IDLE_POWER_KW, AIR_FRYER_PRIORITY,
    AIR_FRYER_CHANCE_PER_HOUR, AIR_FRYER_CYCLE_DURATION_MINUTES
)
import json
import random

class CookingSensorComponent:
    def __init__(self):
        self.needs_cooking = False

    def read(self):
        return 1.0 if self.needs_cooking else 0.0

    def update(self, status):
        self.needs_cooking = status

class SwitchComponent:
    def __init__(self, agent):
        self.agent = agent

    def execute(self, command):
        if command == "on":
            self.agent.status = "on"
            return "Air Fryer started"
        elif command == "off":
            self.agent.status = "idle"
            return "Air Fryer stopped"
        return "Invalid command"

class AirFryerAgent(Device):
    """Air Fryer agent that has a random chance to start a cooking cycle each hour."""

    def __init__(self, jid, password, peers=None):
        super().__init__(jid, password, device_type="air_fryer", peers=peers)
        self.active_power_kw = AIR_FRYER_ACTIVE_POWER_KW
        self.idle_power_kw = AIR_FRYER_IDLE_POWER_KW
        self.current_priority = AIR_FRYER_PRIORITY
        self.cycle_minutes_remaining = 0
        self.last_day_run = -1

        self.add_sensor("cooking_needed", CookingSensorComponent())
        self.add_actuator("switch", SwitchComponent(self))

        self.add_rule(
            Rule(
                name="Start Cooking",
                sensor_name="cooking_needed",
                operator="==",
                threshold=1.0,
                actuator_name="switch",
                command="on",
            )
        )
        
        self.add_rule(
            Rule(
                name="Stop Cooking",
                sensor_name="cooking_needed",
                operator="==",
                threshold=0.0,
                actuator_name="switch",
                command="off",
            )
        )

    def calculate_priority(self, world_state=None):
        return AIR_FRYER_PRIORITY

    def update_sensors(self, world_state):
        from config import MINUTES_PER_STEP
        
        # Trigger logic: Every hour (step), check for a random chance to start if idle
        if self.cycle_minutes_remaining == 0:
            if random.random() < AIR_FRYER_CHANCE_PER_HOUR:
                self.cycle_minutes_remaining = AIR_FRYER_CYCLE_DURATION_MINUTES

        # Timer logic: Subtract the actual simulated minutes passed
        if self.status == "on" and self.cycle_minutes_remaining > 0:
            self.cycle_minutes_remaining = max(0, self.cycle_minutes_remaining - MINUTES_PER_STEP)
            
        # Update sensor based on remaining time
        cooking_needed = self.cycle_minutes_remaining > 0
        self.sensors["cooking_needed"].update(cooking_needed)


    def get_power_consumption_kw(self):
        return self.active_power_kw if self.status == "on" else self.idle_power_kw

    def get_device_state_for_gui(self):
        return {
            "device_type": "air_fryer",
            "priority": AIR_FRYER_PRIORITY,
            "status": self.status.upper(),
            "cycle_minutes_remaining": self.cycle_minutes_remaining,
            "power_kw": round(self.get_power_consumption_kw(), 3),
            "max_power_kw": self.active_power_kw,
            "hourly_consumption_kwh": round(self.hourly_consumption_kwh, 3),
            "daily_consumption_kwh": round(self.daily_consumption_kwh, 3),
        }

    async def setup(self):
        print(f"AirFryerAgent starting: {self.jid}")
        await super().setup()
