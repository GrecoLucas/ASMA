from .device_base import Device, Rule


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
    """Air conditioner device agent with temperature sensor and rule-based actuator control."""

    def __init__(self, jid, password, target_temp=22, temp_margin=2, peers=None):
        super().__init__(jid, password, device_type="air_conditioner", peers=peers, priority=5)
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
            "priority": self.priority,
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
        minute = world_state.get("minute", 0)
        ac_actuator = self.actuators["ac_switch"]
        current_state = ac_actuator.get_state()
        power = self.get_power_consumption_kw()
        return (
            f"Time: {hour:02d}:{minute:02d} | Temp: {self.current_temp}°C | AC: {current_state} | "
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
