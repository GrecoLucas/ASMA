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


class TemperatureSensorComponent:
    """Sensor component that reads temperature."""
    def __init__(self):
        self.current_temp = None

    def read(self):
        return self.current_temp

    def update(self, temperature):
        self.current_temp = temperature


class ACActuatorComponent:
    """Actuator component that controls AC on/off."""
    def __init__(self):
        self.is_on = False

    def execute(self, command):
        """Execute command: 'on' or 'off'."""
        if command == "on":
            self.is_on = True
            return "AC turned ON"
        elif command == "off":
            self.is_on = False
            return "AC turned OFF"
        return "Invalid command"

    def get_state(self):
        return "ON" if self.is_on else "OFF"


class AirConditioner(Device):
    """Air conditioner device agent with temperature sensor and actuator."""

    def __init__(self, jid, password, target_temp=22, temp_margin=2):
        super().__init__(jid, password, device_type="air_conditioner")
        self.target_temp = target_temp
        self.temp_margin = temp_margin
        self.current_temp = None
        self.current_hour = None

        # Add sensor and actuator components
        self.add_sensor("temperature", TemperatureSensorComponent())
        self.add_actuator("ac_switch", ACActuatorComponent())

    class MonitorEnvironment(CyclicBehaviour):
        """Monitor environment and control AC based on temperature."""
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    data = json.loads(msg.body)
                    temperature = data.get("temperature")
                    hour = data.get("hour")

                    # Update sensor reading
                    self.agent.sensors["temperature"].update(temperature)
                    self.agent.current_temp = temperature
                    self.agent.current_hour = hour

                    # AC control logic
                    ac_actuator = self.agent.actuators["ac_switch"]
                    current_state = ac_actuator.get_state()

                    # Turn on if temp exceeds target + margin
                    if temperature > self.agent.target_temp + self.agent.temp_margin:
                        if not ac_actuator.is_on:
                            self.agent.actuate("ac_switch", "on")
                            print(f"[{self.agent.name}] AC turned ON (Temp: {temperature}°C > {self.agent.target_temp + self.agent.temp_margin}°C)")

                    # Turn off if temp falls below target - margin
                    elif temperature < self.agent.target_temp - self.agent.temp_margin:
                        if ac_actuator.is_on:
                            self.agent.actuate("ac_switch", "off")
                            print(f"[{self.agent.name}] AC turned OFF (Temp: {temperature}°C < {self.agent.target_temp - self.agent.temp_margin}°C)")

                    else:
                        print(f"[{self.agent.name}] Hour: {hour:02d}h | Temp: {temperature}°C | AC: {current_state} | Target: {self.agent.target_temp}°C±{self.agent.temp_margin}°C")

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[{self.agent.name}] Error parsing message: {e}")

    async def setup(self):
        print(f"Agent [{self.name}] (AirConditioner) started.")
        print(f"  - Target temperature: {self.target_temp}°C")
        print(f"  - Temperature margin: ±{self.temp_margin}°C")
        self.add_behaviour(self.MonitorEnvironment())