import json
from spade.behaviour import CyclicBehaviour

from .device_base import Device


class TemperatureSensorComponent:
    """Sensor component that reads temperature."""

    def __init__(self):
        self.current_temp = None

    def read(self):
        return self.current_temp

    def update(self, temperature):
        self.current_temp = temperature


class TemperatureSensor(Device):
    """A temperature sensor device agent that listens for environment data."""

    class ReadTemperature(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    data = json.loads(msg.body)
                    temperature = data.get("temperature")
                    hour = data.get("hour")
                    print(f"[{self.agent.name}] Temperature reading -> Hour: {hour}h, Temp: {temperature}°C")
                    self.agent.sensors["temperature"].update(temperature)
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[{self.agent.name}] Error parsing message: {e}")

    async def setup(self):
        print(f"Agent [{self.name}] (TemperatureSensor) started.")
        self.add_sensor("temperature", TemperatureSensorComponent())
        self.add_behaviour(self.ReadTemperature())
