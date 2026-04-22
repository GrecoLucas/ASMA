from .device_base import Device, Rule
from config import (
    AC_TARGET_TEMP, AC_TEMP_MARGIN, AC_PRICE_SENSITIVITY, AC_ACTIVE_POWER_KW,
    AC_IDLE_POWER_KW, AC_PRIORITY_THRESHOLDS, DEFAULT_ENERGY_PRICE
)


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

    def __init__(self, jid, password, target_temp=AC_TARGET_TEMP, temp_margin=AC_TEMP_MARGIN, peers=None):
        super().__init__(jid, password, device_type="air_conditioner", peers=peers)
        self.target_temp = target_temp
        self.temp_margin = temp_margin
        self.current_temp = None
        self.current_hour = None
        self.price_sensitivity = AC_PRICE_SENSITIVITY  # Low: comfort matters but can defer slightly
        self.current_energy_price = DEFAULT_ENERGY_PRICE  # Updated each tick from world state

        self.add_sensor("temperature", TemperatureSensorComponent())
        self.add_actuator("ac_switch", ACActuatorComponent())

        # Typical split AC consumption profile
        self.active_power_kw = AC_ACTIVE_POWER_KW
        self.idle_power_kw = AC_IDLE_POWER_KW

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
        self.current_energy_price = world_state.get("energy_price", DEFAULT_ENERGY_PRICE)
        self.current_temp = temperature

        if temperature is not None:
            self.sensors["temperature"].update(temperature)

    def calculate_priority(self, world_state=None):
        """Calculate AC priority based on temperature deviation from target.

        Priority scale (0=lowest, 5=highest):
        - 5: Extreme discomfort (≥8°C deviation) - health/safety concern
        - 4: High discomfort (6-8°C deviation) - very uncomfortable
        - 3: Moderate discomfort (4-6°C deviation) - uncomfortable
        - 2: Slight discomfort (2-4°C deviation) - noticeable
        - 1: Comfortable (<2°C deviation) - within acceptable range

        Returns:
            int: Priority value 1-5
        """
        if self.current_temp is None:
            return 3  # Default medium priority if no temp data

        temp_deviation = abs(self.current_temp - self.target_temp)

        # Extreme discomfort - health/safety concern
        if temp_deviation >= AC_PRIORITY_THRESHOLDS[0]:
            raw_priority = 5

        # High discomfort - very uncomfortable
        elif temp_deviation >= AC_PRIORITY_THRESHOLDS[1]:
            raw_priority = 4

        # Moderate discomfort - uncomfortable
        elif temp_deviation >= AC_PRIORITY_THRESHOLDS[2]:
            raw_priority = 3

        # Slight discomfort - noticeable but tolerable
        elif temp_deviation >= AC_PRIORITY_THRESHOLDS[3]:
            raw_priority = 2

        # Comfortable - within acceptable range
        else:
            raw_priority = 1

        # Apply price modifier: slight adjustment based on energy cost
        price_modifier = self._calculate_price_modifier()
        return max(0, min(5, raw_priority + price_modifier))

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
            "priority": self.current_priority if self.current_priority is not None else 1,
            "ac_status": ac_actuator.get_state(),
            "current_temp": self.current_temp,
            "target_temp": self.target_temp,
            "temp_margin": self.temp_margin,
            "power_kw": round(self.get_power_consumption_kw(), 3),
            "max_power_kw": self.active_power_kw,
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
        await super().setup()
