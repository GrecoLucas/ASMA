import json
from spade.behaviour import CyclicBehaviour

from .device_base import (
    Device,
    Rule,
    TemperatureSensorComponent,
    ACActuatorComponent,
    RefrigeratorSensorComponent,
    RefrigeratorCompressor,
)


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


class AirConditioner(Device):
    """Air conditioner device agent with temperature sensor and rule-based actuator control."""

    def __init__(self, jid, password, target_temp=22, temp_margin=2):
        super().__init__(jid, password, device_type="air_conditioner")
        self.target_temp = target_temp
        self.temp_margin = temp_margin
        self.current_temp = None
        self.current_hour = None

        self.add_sensor("temperature", TemperatureSensorComponent())
        self.add_actuator("ac_switch", ACActuatorComponent())

        # Typical split AC consumption profile
        self.active_power_kw = 1.35
        self.idle_power_kw = 0.08

        self.add_rule(
            Rule(
                name="AC On - Too Hot",
                sensor_name="temperature",
                operator=">",
                threshold=target_temp + temp_margin,
                actuator_name="ac_switch",
                command="on",
            )
        )

        self.add_rule(
            Rule(
                name="AC Off - Cool Enough",
                sensor_name="temperature",
                operator="<",
                threshold=target_temp - temp_margin,
                actuator_name="ac_switch",
                command="off",
            )
        )

    def update_sensors(self, world_state):
        temperature = world_state.get("temperature")
        self.current_hour = world_state.get("hour")
        self.current_temp = temperature

        if temperature is not None:
            self.sensors["temperature"].update(temperature)

    def get_power_consumption_kw(self):
        ac_actuator = self.actuators["ac_switch"]
        return self.active_power_kw if ac_actuator.is_on else self.idle_power_kw

    def get_operating_state(self):
        ac_actuator = self.actuators["ac_switch"]
        return ac_actuator.get_state()

    def get_device_state_for_gui(self):
        ac_actuator = self.actuators["ac_switch"]
        return {
            "device_type": "air_conditioner",
            "ac_status": ac_actuator.get_state(),
            "current_temp": self.current_temp,
            "target_temp": self.target_temp,
            "temp_margin": self.temp_margin,
            "power_kw": round(self.get_power_consumption_kw(), 3),
            "hourly_consumption_kwh": round(self.hourly_consumption_kwh, 3),
            "daily_consumption_kwh": round(self.daily_consumption_kwh, 3),
        }

    def get_log_info(self, world_state):
        hour = world_state.get("hour", 0)
        ac_actuator = self.actuators["ac_switch"]
        current_state = ac_actuator.get_state()
        power = self.get_power_consumption_kw()
        return (
            f"Hour: {hour:02d}h | Temp: {self.current_temp}°C | AC: {current_state} | "
            f"Power: {power:.2f} kW | Daily: {self.daily_consumption_kwh:.2f} kWh"
        )

    async def setup(self):
        print(f"Agent [{self.name}] (AirConditioner) started.")
        print(f"  - Target temperature: {self.target_temp}°C")
        print(f"  - Temperature margin: ±{self.temp_margin}°C")
        print(f"  - Power profile: idle={self.idle_power_kw}kW, active={self.active_power_kw}kW")
        print(f"  - Rules configured: {len(self.rules)}")
        for rule in self.rules:
            print(f"    - {rule}")
        self.add_behaviour(self.MonitorEnvironment())


class Refrigerator(Device):
    """Refrigerator device agent that maintains cold temperature using rules."""

    def __init__(self, jid, password, target_temp=4, temp_margin=1):
        super().__init__(jid, password, device_type="refrigerator")
        self.target_temp = target_temp
        self.temp_margin = temp_margin
        self.current_temp = None
        self.current_hour = None

        self.add_sensor("temperature", RefrigeratorSensorComponent())
        self.add_actuator("compressor", RefrigeratorCompressor())

        # Typical compressor profile
        self.active_power_kw = 0.18
        self.idle_power_kw = 0.03

        self.add_rule(
            Rule(
                name="Compressor On - Warming Up",
                sensor_name="temperature",
                operator=">",
                threshold=target_temp + temp_margin,
                actuator_name="compressor",
                command="on",
            )
        )

        self.add_rule(
            Rule(
                name="Compressor Off - Cool Enough",
                sensor_name="temperature",
                operator="<",
                threshold=target_temp - temp_margin,
                actuator_name="compressor",
                command="off",
            )
        )

    def update_sensors(self, world_state):
        ambient_temp = world_state.get("temperature")
        self.current_hour = world_state.get("hour")

        if ambient_temp is not None:
            compressor = self.actuators["compressor"]
            if compressor.is_running:
                self.current_temp = self.target_temp + (ambient_temp - 20) * 0.1
            else:
                if self.current_temp is None:
                    self.current_temp = self.target_temp
                self.current_temp += (ambient_temp - self.current_temp) * 0.05

            self.sensors["temperature"].update(round(self.current_temp, 1))

    def get_power_consumption_kw(self):
        compressor = self.actuators["compressor"]
        return self.active_power_kw if compressor.is_running else self.idle_power_kw

    def get_operating_state(self):
        compressor = self.actuators["compressor"]
        return compressor.get_state()

    def get_device_state_for_gui(self):
        compressor = self.actuators["compressor"]
        return {
            "device_type": "refrigerator",
            "compressor_status": compressor.get_state(),
            "current_temp": self.current_temp,
            "target_temp": self.target_temp,
            "temp_margin": self.temp_margin,
            "power_kw": round(self.get_power_consumption_kw(), 3),
            "hourly_consumption_kwh": round(self.hourly_consumption_kwh, 3),
            "daily_consumption_kwh": round(self.daily_consumption_kwh, 3),
        }

    def get_log_info(self, world_state):
        hour = world_state.get("hour", 0)
        compressor = self.actuators["compressor"]
        status = compressor.get_state()
        power = self.get_power_consumption_kw()
        return (
            f"Hour: {hour:02d}h | Interior: {self.current_temp}°C | Compressor: {status} | "
            f"Power: {power:.2f} kW | Daily: {self.daily_consumption_kwh:.2f} kWh"
        )

    async def setup(self):
        print(f"Agent [{self.name}] (Refrigerator) started.")
        print(f"  - Target temperature: {self.target_temp}°C")
        print(f"  - Temperature margin: ±{self.temp_margin}°C")
        print(f"  - Power profile: idle={self.idle_power_kw}kW, active={self.active_power_kw}kW")
        print(f"  - Rules configured: {len(self.rules)}")
        for rule in self.rules:
            print(f"    - {rule}")
        self.add_behaviour(self.MonitorEnvironment())
