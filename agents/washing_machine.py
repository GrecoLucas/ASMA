from .device_base import Device, Rule


class LaundrySensorComponent:
    """Sensor component that tracks pending laundry count."""

    def __init__(self):
        self.pending_clothes = 0

    def read(self):
        return self.pending_clothes

    def update(self, clothes_count):
        self.pending_clothes = clothes_count


class WashingMotorComponent:
    """Actuator component that controls the washing machine motor."""

    def __init__(self):
        self.is_running = False

    def execute(self, command):
        if command == "on":
            self.is_running = True
            return "Washing started"
        elif command == "off":
            self.is_running = False
            return "Washing stopped"
        return "Invalid command"

    def get_state(self):
        return "WASHING" if self.is_running else "IDLE"


class WashingMachine(Device):
    """Washing machine device agent that washes clothes based on laundry accumulation."""

    def __init__(self, jid, password, clothes_threshold=10, peers=None):
        super().__init__(jid, password, device_type="washing_machine", peers=peers)
        self.clothes_threshold = clothes_threshold
        self.pending_clothes = 0
        self.current_hour = None
        self.cycle_steps_remaining = 0  # Steps remaining in current wash cycle
        self.cycle_duration_steps = 2  # 2 hours = 2 steps (with MINUTES_PER_STEP=60)
        self.clothes_per_cycle = 10  # How many clothes are washed per cycle
        self.accumulation_rate = 2  # Clothes accumulated per time step when idle
        self.steps_waiting = 0  # How many steps clothes have been waiting (>= threshold)
        self.price_sensitivity = 2  # High: very deferrable device
        self.current_energy_price = 0.12  # Updated each tick from world state

        self.add_sensor("laundry", LaundrySensorComponent())
        self.add_actuator("motor", WashingMotorComponent())

        # Power profile according to rules: active 0.5 kW, idle 0.05 kW
        self.active_power_kw = 0.5
        self.idle_power_kw = 0.0

        self.add_rule(
            Rule(
                name="Start Washing - Enough Clothes",
                sensor_name="laundry",
                operator=">=",
                threshold=10,
                actuator_name="motor",
                command="on",
            )
        )

        self.add_rule(
            Rule(
                name="Stop Washing - No Clothes",
                sensor_name="laundry",
                operator="<",
                threshold=10,
                actuator_name="motor",
                command="off",
            )
        )

    def update_sensors(self, world_state):
        self.current_hour = world_state.get("hour")
        self.current_energy_price = world_state.get("energy_price", 0.12)
        motor = self.actuators["motor"]

        if motor.is_running:
            # Washing in progress - reset waiting time
            self.steps_waiting = 0
            
            if self.cycle_steps_remaining == 0:
                # Motor just turned on, start a new 2-hour cycle
                self.cycle_steps_remaining = self.cycle_duration_steps
            else:
                # Continue cycle
                self.cycle_steps_remaining -= 1
                # If cycle just completed, wash the clothes
                if self.cycle_steps_remaining == 0:
                    washed = min(self.clothes_per_cycle, self.pending_clothes)
                    self.pending_clothes = max(0, self.pending_clothes - washed)
                    # If more clothes remain, start a new cycle immediately
                    if self.pending_clothes >= self.clothes_threshold:
                        self.cycle_steps_remaining = self.cycle_duration_steps
        else:
            # Machine idle - clothes accumulate over time
            self.pending_clothes += self.accumulation_rate
            # Only reset cycle if not recovering from shed
            if self.shed_timeout <= 0:
                 self.cycle_steps_remaining = 0
                 
            # Track waiting time when above threshold
            if self.pending_clothes >= self.clothes_threshold:
                self.steps_waiting += 1

        self.sensors["laundry"].update(self.pending_clothes)

    def calculate_priority(self, world_state=None):
        """Calculate washing machine priority based on waiting time and clothes accumulation.

        Priority scale (0=lowest, 5=highest):
        - Base priority from clothes count
        - Increases with waiting time (steps since reaching threshold)
        
        Formula: Base priority increases by 1 for every 3 hours (3 steps) of waiting
        
        Returns:
            int: Priority value 0-5
        """
        if self.pending_clothes < self.clothes_threshold:
            return 0  # Not enough clothes, no priority
        
        # Base priority from clothes count
        if self.pending_clothes >= 25:
            base_priority = 3
        elif self.pending_clothes >= 20:
            base_priority = 2
        else:  # 10-19 clothes
            base_priority = 1
        
        # Add priority based on waiting time (1 priority per 3 hours/steps)
        waiting_bonus = self.steps_waiting // 3
        
        raw_priority = base_priority + waiting_bonus
        # Apply price modifier: boost in cheap hours, penalize in expensive hours
        price_modifier = self._calculate_price_modifier()
        # Cap at priority 5, floor at 0
        return max(0, min(5, raw_priority + price_modifier))

    def get_power_consumption_kw(self):
        motor = self.actuators["motor"]
        return self.active_power_kw if motor.is_running else self.idle_power_kw

    def get_operating_state(self):
        motor = self.actuators["motor"]
        return motor.get_state()

    def get_device_state_for_gui(self):
        motor = self.actuators["motor"]
        return {
            "device_type": "washing_machine",
            "priority": self.current_priority if self.current_priority is not None else 0,
            "motor_status": motor.get_state(),
            "pending_clothes": self.pending_clothes,
            "cycle_steps_remaining": self.cycle_steps_remaining,
            "steps_waiting": self.steps_waiting,
            "power_kw": round(self.get_power_consumption_kw(), 3),
            "max_power_kw": self.active_power_kw,
            "hourly_consumption_kwh": round(self.hourly_consumption_kwh, 3),
            "daily_consumption_kwh": round(self.daily_consumption_kwh, 3),
        }

    def get_log_info(self, world_state):
        hour = world_state.get("hour", 0)
        minute = world_state.get("minute", 0)
        motor = self.actuators["motor"]
        status = motor.get_state()
        power = self.get_power_consumption_kw()
        waiting_info = f" | Waiting: {self.steps_waiting}h" if self.steps_waiting > 0 else ""
        return (
            f"Time: {hour:02d}:{minute:02d} | Pending: {self.pending_clothes} clothes{waiting_info} | "
            f"Motor: {status} | Power: {power:.2f} kW | Daily: {self.daily_consumption_kwh:.2f} kWh"
        )

    async def setup(self):
        for rule in self.rules:
            print(f"    - {rule}")
        await super().setup()
