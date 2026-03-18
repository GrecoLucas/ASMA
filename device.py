import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

# Import GUI state if available
try:
    from gui import get_simulation_state
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False


class Rule:
    """A rule that evaluates a sensor condition and triggers an actuator action."""

    def __init__(self, name, sensor_name, operator, threshold, actuator_name, command):
        """
        Initialize a rule.

        Args:
            name: Rule name (e.g., "Turn AC on when hot")
            sensor_name: Name of the sensor to monitor (e.g., "temperature")
            operator: Comparison operator (">", "<", ">=", "<=", "==", "!=")
            threshold: Value to compare against
            actuator_name: Name of the actuator to control (e.g., "ac_switch")
            command: Command to send to actuator (e.g., "on", "off")
        """
        self.name = name
        self.sensor_name = sensor_name
        self.operator = operator
        self.threshold = threshold
        self.actuator_name = actuator_name
        self.command = command
        self.last_triggered = False  # Track if rule was active last check

    def evaluate(self, sensor_value):
        """Check if the sensor value satisfies the condition."""
        if sensor_value is None:
            return False

        if self.operator == ">":
            return sensor_value > self.threshold
        elif self.operator == "<":
            return sensor_value < self.threshold
        elif self.operator == ">=":
            return sensor_value >= self.threshold
        elif self.operator == "<=":
            return sensor_value <= self.threshold
        elif self.operator == "==":
            return sensor_value == self.threshold
        elif self.operator == "!=":
            return sensor_value != self.threshold
        return False

    def __repr__(self):
        return f"Rule({self.name}: {self.sensor_name} {self.operator} {self.threshold} → {self.actuator_name}:{self.command})"

class Device(Agent):
    """Base class for device agents with sensors, actuators, and relations."""

    def __init__(self, jid, password, device_type="generic"):
        super().__init__(jid, password)
        self.device_type = device_type
        self.sensors = {}
        self.actuators = {}
        self.relations = {}
        self.rules = []  # List of rules for this device
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

    def add_rule(self, rule):
        """Add a rule to the device."""
        self.rules.append(rule)

    def evaluate_rules(self, sensor_name, sensor_value):
        """
        Evaluate all rules for a given sensor and execute matching actuator commands.

        Returns a list of (rule, condition_met, action_taken, state_changed) tuples.
        """
        results = []
        for rule in self.rules:
            if rule.sensor_name != sensor_name:
                continue

            # Check if condition is met
            condition_met = rule.evaluate(sensor_value)

            # If condition state changed, execute action
            if condition_met and not rule.last_triggered:
                # Transition: False -> True (condition just became true)
                self.actuate(rule.actuator_name, rule.command)
                result = (rule, True, f"Activated: {rule.command}", True)
                rule.last_triggered = True
            elif not condition_met and rule.last_triggered:
                # Transition: True -> False (condition just became false)
                # We could execute a reverse command here if needed
                # For now, just track the state change
                rule.last_triggered = False
                result = (rule, False, "Condition no longer met", False)
            else:
                result = (rule, condition_met, "No state change", False)

            results.append(result)

        return results

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

    def update_sensors(self, world_state):
        """
        Update device sensors based on world state.
        Override this method in subclasses to extract specific data.

        Args:
            world_state: Dictionary with hour, temperature, solar_production, energy_price, etc.
        """
        # Base implementation does nothing - subclasses override as needed
        pass

    def get_device_state_for_gui(self):
        """
        Return device state data for GUI display.
        Override this method in subclasses for custom GUI display.

        Returns:
            Dictionary with device-specific state information
        """
        return {
            "device_type": self.device_type,
            "status": self.status
        }

    def get_log_info(self, world_state):
        """
        Return a string with device-specific logging information.
        Override this method in subclasses for custom logging.
        """
        hour = world_state.get("hour", 0)
        return f"Hour: {hour:02d}h"

    class MonitorEnvironment(CyclicBehaviour):
        """Generic behavior that monitors environment and controls device using rules."""
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    world_state = json.loads(msg.body)

                    # Let the device update its sensors based on world state
                    self.agent.update_sensors(world_state)

                    # Evaluate all rules for all sensors
                    all_rule_results = []
                    for sensor_name in self.agent.sensors.keys():
                        sensor_value = self.agent.get_sensor_data(sensor_name)
                        rule_results = self.agent.evaluate_rules(sensor_name, sensor_value)
                        all_rule_results.extend(rule_results)

                    # Notify world agent only when a rule actually changed state
                    state_changed_rules = [r for r, _, _, state_changed in all_rule_results if state_changed]
                    if state_changed_rules:
                        for rule in state_changed_rules:
                            print(f"[{self.agent.name}] ✓ {rule.name}: {rule.command.upper()}")
                            # Notify world agent of state change
                            from config import AGENTS
                            device_name = self.agent.name.split("@")[0]  # Extract device name from JID
                            # Send message from behavior (not agent)
                            notify_msg = Message(to=AGENTS["world"])
                            notify_msg.body = json.dumps({
                                "event": "state_changed",
                                "device_name": device_name,
                                "state": rule.command.upper()
                            })
                            await self.send(notify_msg)
                    else:
                        print(f"[{self.agent.name}] {self.agent.get_log_info(world_state)}")

                    # Update GUI state
                    if GUI_AVAILABLE:
                        state = get_simulation_state()
                        device_state = self.agent.get_device_state_for_gui()
                        state.update_device_state(self.agent.name, device_state)

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[{self.agent.name}] Error parsing message: {e}")

    async def setup(self):
        """Setup the device agent with default behavior."""
        print(f"Agent [{self.name}] ({self.device_type.title()}) started.")
        if self.rules:
            print(f"  - Rules configured: {len(self.rules)}")
            for rule in self.rules:
                print(f"    • {rule}")
        self.add_behaviour(self.MonitorEnvironment())

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
                    self.agent.sensors["temperature"].update(temperature)
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[{self.agent.name}] Error parsing message: {e}")

    async def setup(self):
        print(f"Agent [{self.name}] (TemperatureSensor) started.")
        self.add_sensor("temperature", TemperatureSensorComponent())
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


class RefrigeratorSensorComponent:
    """Sensor component that reads fridge temperature."""
    def __init__(self):
        self.current_temp = None

    def read(self):
        return self.current_temp

    def update(self, temperature):
        self.current_temp = temperature


class RefrigeratorCompressor:
    """Actuator component that controls the fridge compressor."""
    def __init__(self):
        self.is_running = False

    def execute(self, command):
        """Execute command: 'on' or 'off' for compressor."""
        if command == "on":
            self.is_running = True
            return "Compressor started"
        elif command == "off":
            self.is_running = False
            return "Compressor stopped"
        return "Invalid command"

    def get_state(self):
        return "RUNNING" if self.is_running else "IDLE"


class AirConditioner(Device):
    """Air conditioner device agent with temperature sensor and actuator that uses rules."""

    def __init__(self, jid, password, target_temp=22, temp_margin=2):
        super().__init__(jid, password, device_type="air_conditioner")
        self.target_temp = target_temp
        self.temp_margin = temp_margin
        self.current_temp = None
        self.current_hour = None

        # Add sensor and actuator components
        self.add_sensor("temperature", TemperatureSensorComponent())
        self.add_actuator("ac_switch", ACActuatorComponent())

        # Add rules for AC control
        self.add_rule(Rule(
            name="AC On - Too Hot",
            sensor_name="temperature",
            operator=">",
            threshold=target_temp + temp_margin,
            actuator_name="ac_switch",
            command="on"
        ))

        self.add_rule(Rule(
            name="AC Off - Cool Enough",
            sensor_name="temperature",
            operator="<",
            threshold=target_temp - temp_margin,
            actuator_name="ac_switch",
            command="off"
        ))

    def update_sensors(self, world_state):
        """Update temperature sensor from world state."""
        temperature = world_state.get("temperature")
        self.current_hour = world_state.get("hour")
        self.current_temp = temperature

        if temperature is not None:
            self.sensors["temperature"].update(temperature)

    def get_device_state_for_gui(self):
        """Return AC-specific state for GUI."""
        ac_actuator = self.actuators["ac_switch"]
        return {
            "device_type": "air_conditioner",
            "ac_status": ac_actuator.get_state(),
            "current_temp": self.current_temp,
            "target_temp": self.target_temp,
            "temp_margin": self.temp_margin
        }

    def get_log_info(self, world_state):
        """Return AC-specific logging information."""
        hour = world_state.get("hour", 0)
        ac_actuator = self.actuators["ac_switch"]
        current_state = ac_actuator.get_state()
        return f"Hour: {hour:02d}h | Temp: {self.current_temp}°C | AC: {current_state} | Target: {self.target_temp}°C±{self.temp_margin}°C"

    async def setup(self):
        """Setup the AC with additional info."""
        print(f"Agent [{self.name}] (AirConditioner) started.")
        print(f"  - Target temperature: {self.target_temp}°C")
        print(f"  - Temperature margin: ±{self.temp_margin}°C")
        print(f"  - Rules configured: {len(self.rules)}")
        for rule in self.rules:
            print(f"    • {rule}")
        self.add_behaviour(self.MonitorEnvironment())


class Refrigerator(Device):
    """Refrigerator device agent that maintains cold temperature using rules."""

    def __init__(self, jid, password, target_temp=4, temp_margin=1):
        super().__init__(jid, password, device_type="refrigerator")
        self.target_temp = target_temp
        self.temp_margin = temp_margin
        self.current_temp = None
        self.current_hour = None

        # Add sensor and actuator components
        # Fridge receives ambient temperature but maintains internal cold storage
        self.add_sensor("temperature", RefrigeratorSensorComponent())
        self.add_actuator("compressor", RefrigeratorCompressor())

        # Add rules for fridge control
        # Start compressor if interior gets too warm
        self.add_rule(Rule(
            name="Compressor On - Warming Up",
            sensor_name="temperature",
            operator=">",
            threshold=target_temp + temp_margin,
            actuator_name="compressor",
            command="on"
        ))

        # Stop compressor if interior gets too cold
        self.add_rule(Rule(
            name="Compressor Off - Cool Enough",
            sensor_name="temperature",
            operator="<",
            threshold=target_temp - temp_margin,
            actuator_name="compressor",
            command="off"
        ))

    # NOT FINAL - STILL NO SIMULATION OF OUTSIDE INFLUENCE ON FRIDGE INTERIOR - SIMPLIFIED MODEL
    def update_sensors(self, world_state):
        """Update fridge temperature based on ambient + internal state."""
        ambient_temp = world_state.get("temperature")
        self.current_hour = world_state.get("hour")

        # Fridge interior temperature is affected by ambient but much slower
        # Simplified: ambient affects interior only gradually
        if ambient_temp is not None:
            compressor = self.actuators["compressor"]
            if compressor.is_running:
                # Compressor cooling: interior stays cold
                self.current_temp = self.target_temp + (ambient_temp - 20) * 0.1
            else:
                # No active cooling: interior warms toward ambient (slowly)
                if self.current_temp is None:
                    self.current_temp = self.target_temp
                self.current_temp += (ambient_temp - self.current_temp) * 0.05

            self.sensors["temperature"].update(round(self.current_temp, 1))

    def get_device_state_for_gui(self):
        """Return fridge-specific state for GUI."""
        compressor = self.actuators["compressor"]
        return {
            "device_type": "refrigerator",
            "compressor_status": compressor.get_state(),
            "current_temp": self.current_temp,
            "target_temp": self.target_temp,
            "temp_margin": self.temp_margin
        }

    def get_log_info(self, world_state):
        """Return fridge-specific logging information."""
        hour = world_state.get("hour", 0)
        compressor = self.actuators["compressor"]
        status = compressor.get_state()
        return f"Hour: {hour:02d}h | Interior: {self.current_temp}°C | Compressor: {status} | Target: {self.target_temp}°C±{self.temp_margin}°C"

    async def setup(self):
        """Setup the fridge with additional info."""
        print(f"Agent [{self.name}] (Refrigerator) started.")
        print(f"  - Target temperature: {self.target_temp}°C")
        print(f"  - Temperature margin: ±{self.temp_margin}°C")
        print(f"  - Rules configured: {len(self.rules)}")
        for rule in self.rules:
            print(f"    • {rule}")
        self.add_behaviour(self.MonitorEnvironment())