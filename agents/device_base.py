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
        self.name = name
        self.sensor_name = sensor_name
        self.operator = operator
        self.threshold = threshold
        self.actuator_name = actuator_name
        self.command = command
        self.last_triggered = False

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
        return (
            f"Rule({self.name}: {self.sensor_name} {self.operator} "
            f"{self.threshold} -> {self.actuator_name}:{self.command})"
        )


class Device(Agent):
    """Base class for device agents with sensors, actuators, relations, and energy accounting."""

    def __init__(self, jid, password, device_type="generic"):
        super().__init__(jid, password)
        self.device_type = device_type
        self.sensors = {}
        self.actuators = {}
        self.relations = {}
        self.rules = []
        self.status = "idle"

        # Energy model values in kW
        self.active_power_kw = 0.0
        self.idle_power_kw = 0.0

        # Daily accounting
        self.current_day = 1
        self.hourly_consumption_kwh = 0.0
        self.daily_consumption_kwh = 0.0

    def add_sensor(self, sensor_name, sensor_object):
        self.sensors[sensor_name] = sensor_object

    def add_actuator(self, actuator_name, actuator_object):
        self.actuators[actuator_name] = actuator_object

    def add_relation(self, related_device_name, relation_type):
        self.relations[related_device_name] = relation_type

    def add_rule(self, rule):
        self.rules.append(rule)

    def evaluate_rules(self, sensor_name, sensor_value):
        """Evaluate all rules for a given sensor and execute matching actuator commands."""
        results = []
        for rule in self.rules:
            if rule.sensor_name != sensor_name:
                continue

            condition_met = rule.evaluate(sensor_value)

            if condition_met and not rule.last_triggered:
                self.actuate(rule.actuator_name, rule.command)
                result = (rule, True, f"Activated: {rule.command}", True)
                rule.last_triggered = True
            elif not condition_met and rule.last_triggered:
                rule.last_triggered = False
                result = (rule, False, "Condition no longer met", False)
            else:
                result = (rule, condition_met, "No state change", False)

            results.append(result)

        return results

    def get_sensor_data(self, sensor_name):
        if sensor_name in self.sensors:
            return self.sensors[sensor_name].read()
        return None

    def actuate(self, actuator_name, command):
        if actuator_name in self.actuators:
            return self.actuators[actuator_name].execute(command)
        return None

    def update_sensors(self, world_state):
        """Override in subclasses to map world state into device sensors."""
        pass

    def get_power_consumption_kw(self):
        """Return current power draw in kW. Override for custom behavior."""
        return self.idle_power_kw

    def get_hourly_consumption_kwh(self, world_state):
        """For one-hour simulation steps, kWh equals current kW draw for that step."""
        return round(self.get_power_consumption_kw(), 3)

    def get_operating_state(self):
        """Return state name used in logs and world notifications."""
        return self.status.upper()

    def update_energy_counters(self, world_state):
        day = world_state.get("day", self.current_day)
        if day != self.current_day:
            self.current_day = day
            self.daily_consumption_kwh = 0.0

        self.hourly_consumption_kwh = self.get_hourly_consumption_kwh(world_state)
        self.daily_consumption_kwh += self.hourly_consumption_kwh

    def get_device_state_for_gui(self):
        return {
            "device_type": self.device_type,
            "status": self.status,
            "power_kw": round(self.get_power_consumption_kw(), 3),
            "hourly_consumption_kwh": round(self.hourly_consumption_kwh, 3),
            "daily_consumption_kwh": round(self.daily_consumption_kwh, 3),
        }

    def get_log_info(self, world_state):
        hour = world_state.get("hour", 0)
        return f"Hour: {hour:02d}h"

    class MonitorEnvironment(CyclicBehaviour):
        """Generic behavior that monitors environment and controls device using rules."""

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    world_state = json.loads(msg.body)

                    self.agent.update_sensors(world_state)

                    all_rule_results = []
                    for sensor_name in self.agent.sensors.keys():
                        sensor_value = self.agent.get_sensor_data(sensor_name)
                        rule_results = self.agent.evaluate_rules(sensor_name, sensor_value)
                        all_rule_results.extend(rule_results)

                    self.agent.update_energy_counters(world_state)

                    from config import AGENTS
                    device_name = self.agent.name.split("@")[0]

                    # Notify world about hourly consumption
                    consumption_msg = Message(to=AGENTS["world"])
                    consumption_msg.body = json.dumps({
                        "event": "device_consumption",
                        "device_name": device_name,
                        "hour": world_state.get("hour"),
                        "day": world_state.get("day"),
                        "power_kw": self.agent.get_power_consumption_kw(),
                        "consumption_kwh": self.agent.hourly_consumption_kwh,
                    })
                    await self.send(consumption_msg)

                    # Notify world when a rule changed state
                    state_changed_rules = [r for r, _, _, state_changed in all_rule_results if state_changed]
                    if state_changed_rules:
                        for rule in state_changed_rules:
                            print(f"[{self.agent.name}] [OK] {rule.name}: {rule.command.upper()}")
                            notify_msg = Message(to=AGENTS["world"])
                            notify_msg.body = json.dumps({
                                "event": "state_changed",
                                "device_name": device_name,
                                "state": rule.command.upper(),
                            })
                            await self.send(notify_msg)
                    else:
                        print(f"[{self.agent.name}] {self.agent.get_log_info(world_state)}")

                    if GUI_AVAILABLE:
                        state = get_simulation_state()
                        device_state = self.agent.get_device_state_for_gui()
                        state.update_device_state(self.agent.name, device_state)

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[{self.agent.name}] Error parsing message: {e}")

    async def setup(self):
        print(f"Agent [{self.name}] ({self.device_type.title()}) started.")
        if self.rules:
            print(f"  - Rules configured: {len(self.rules)}")
            for rule in self.rules:
                print(f"    - {rule}")
        self.add_behaviour(self.MonitorEnvironment())

    def __repr__(self):
        return f"Device(name={self.name}, type={self.device_type}, status={self.status})"
