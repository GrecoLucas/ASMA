import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

class Device(Agent):
    """Base class for device agents with sensors, actuators, and relations."""
    
    def __init__(self, jid, password, device_type="generic"):
        super().__init__(jid, password)
        self.device_type = device_type
        self.sensors = {}
        self.actuators = {}
        self.relations = {}
        self.status = "idle"
    
    def add_sensor(self, sensor_name, sensor_object):
        """Add a sensor to the device."""
        self.sensors[sensor_name] = sensor_object
    
    def add_actuator(self, actuator_name, actuator_object):
        """Add an actuator to the device."""
        self.actuators[actuator_name] = actuator_object
    
    def add_relation(self, related_device_name, relation_type):
        """Define a relation to another device."""
        self.relations[related_device_name] = relation_type
    
    def get_sensor_data(self, sensor_name):
        """Retrieve data from a specific sensor."""
        if sensor_name in self.sensors:
            return self.sensors[sensor_name].read()
        return None
    
    def actuate(self, actuator_name, command):
        """Send a command to a specific actuator."""
        if actuator_name in self.actuators:
            return self.actuators[actuator_name].execute(command)
        return None
    
    def __repr__(self):
        return f"Device(name={self.name}, type={self.device_type}, status={self.status})"


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
                    self.agent.sensors["temperature"] = temperature
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[{self.agent.name}] Error parsing message: {e}")

    async def setup(self):
        print(f"Agent [{self.name}] (TemperatureSensor) started.")
        self.add_behaviour(self.ReadTemperature())