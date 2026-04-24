from .device_base import Device, Rule
from config import (
	HEATER_TARGET_TEMP, HEATER_TEMP_MARGIN, HEATER_PRICE_SENSITIVITY, HEATER_ACTIVE_POWER_KW,
	HEATER_IDLE_POWER_KW, HEATER_PRIORITY_THRESHOLDS, DEFAULT_ENERGY_PRICE
)


class TemperatureSensorComponent:
	"""Sensor component that reads temperature."""

	def __init__(self):
		self.current_temp = None

	def read(self):
		return self.current_temp

	def update(self, temperature):
		self.current_temp = temperature


class HeaterActuatorComponent:
	"""Actuator component that controls heater on/off."""

	def __init__(self):
		self.is_on = False

	def execute(self, command):
		if command == "on":
			self.is_on = True
			return "Heater turned ON"
		elif command == "off":
			self.is_on = False
			return "Heater turned OFF"
		return "Invalid command"

	def get_state(self):
		return "ON" if self.is_on else "OFF"


class Heater(Device):
	"""Heater device agent that heats when temperature is too cold."""

	def __init__(self, jid, password, target_temp=HEATER_TARGET_TEMP, temp_margin=HEATER_TEMP_MARGIN, peers=None):
		super().__init__(jid, password, device_type="heater", peers=peers)
		self.target_temp = target_temp
		self.temp_margin = temp_margin
		self.current_temp = None
		self.current_hour = None
		self.price_sensitivity = HEATER_PRICE_SENSITIVITY
		self.current_energy_price = DEFAULT_ENERGY_PRICE

		self.add_sensor("temperature", TemperatureSensorComponent())
		self.add_actuator("heater_switch", HeaterActuatorComponent())

		self.active_power_kw = HEATER_ACTIVE_POWER_KW
		self.idle_power_kw = HEATER_IDLE_POWER_KW

		self.add_rule(
			Rule(
				name="Heater On - Too Cold",
				sensor_name="temperature",
				operator="<",
				threshold=target_temp - temp_margin,
				actuator_name="heater_switch",
				command="on",
			)
		)

		self.add_rule(
			Rule(
				name="Heater Off - Warm Enough",
				sensor_name="temperature",
				operator=">=",
				threshold=target_temp,
				actuator_name="heater_switch",
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
		"""Calculate heater priority from cold deviation below target.

		Priority scale (0=lowest, 5=highest) with same thresholds as AC:
		- 5: >=8C below target
		- 4: 6-8C below target
		- 3: 4-6C below target
		- 2: 2-4C below target
		- 1: <2C below target (or above target)
		"""
		if self.current_temp is None:
			return 3

		cold_deviation = self.target_temp - self.current_temp

		if cold_deviation < 0:
			raw_priority = 0
		elif cold_deviation >= HEATER_PRIORITY_THRESHOLDS[0]:
			raw_priority = 5
		elif cold_deviation >= HEATER_PRIORITY_THRESHOLDS[1]:
			raw_priority = 4
		elif cold_deviation >= HEATER_PRIORITY_THRESHOLDS[2]:
			raw_priority = 3
		elif cold_deviation >= HEATER_PRIORITY_THRESHOLDS[3]:
			raw_priority = 2
		else:
			raw_priority = 1

		price_modifier = self._calculate_price_modifier()
		return max(0, min(5, raw_priority + price_modifier))

	def get_power_consumption_kw(self):
		heater_actuator = self.actuators["heater_switch"]
		return self.active_power_kw if heater_actuator.is_on else self.idle_power_kw

	def get_operating_state(self):
		heater_actuator = self.actuators["heater_switch"]
		return heater_actuator.get_state()

	def get_device_state_for_gui(self):
		heater_actuator = self.actuators["heater_switch"]
		return {
			"device_type": "heater",
			"priority": self.current_priority if self.current_priority is not None else 1,
			"heater_status": heater_actuator.get_state(),
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
		heater_actuator = self.actuators["heater_switch"]
		current_state = heater_actuator.get_state()
		power = self.get_power_consumption_kw()
		return (
			f"Time: {hour:02d}:{minute:02d} | Temp: {self.current_temp}°C | Heater: {current_state} | "
			f"Power: {power:.2f} kW | Daily: {self.daily_consumption_kwh:.2f} kWh"
		)

	async def setup(self):
		await super().setup()
