from .device_base import Device, Rule


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
        if command == "on":
            self.is_running = True
            return "Compressor started"
        elif command == "off":
            self.is_running = False
            return "Compressor stopped"
        return "Invalid command"

    def get_state(self):
        return "RUNNING" if self.is_running else "IDLE"


class Refrigerator(Device):
    """Refrigerator device agent that maintains cold temperature using rules."""

    def __init__(self, jid, password, target_temp=4, temp_margin=1, peers=None):
        super().__init__(jid, password, device_type="refrigerator", peers=peers)
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

    def calculate_priority(self, world_state=None):
        """Calculate Fridge priority - always highest priority.

        Priority scale (0=lowest, 5=highest):
        - Fridge always returns 5 (highest priority, never yields to other devices)

        Returns:
            int: Priority value 5 (constant)
        """
        return 5

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
            "priority": self.current_priority if self.current_priority is not None else 3,
            "compressor_status": compressor.get_state(),
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
        compressor = self.actuators["compressor"]
        status = compressor.get_state()
        power = self.get_power_consumption_kw()
        return (
            f"Time: {hour:02d}:{minute:02d} | Interior: {self.current_temp}°C | Compressor: {status} | "
            f"Power: {power:.2f} kW | Daily: {self.daily_consumption_kwh:.2f} kWh"
        )

    async def setup(self):
        for rule in self.rules:
            print(f"    - {rule}")
        await super().setup()
