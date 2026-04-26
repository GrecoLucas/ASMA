from .device_base import Device, Rule
from config import (
    WASHING_MACHINE_THRESHOLD, WASHING_MACHINE_CYCLE_DURATION_STEPS,
    WASHING_MACHINE_PER_CYCLE, WASHING_MACHINE_ACCUMULATION_RATE,
    WASHING_MACHINE_PRICE_SENSITIVITY, WASHING_MACHINE_ACTIVE_POWER_KW,
    WASHING_MACHINE_IDLE_POWER_KW, WASHING_MACHINE_WAITING_BONUS_DIVIDER,
    WASHING_MACHINE_PRIORITY_THRESHOLDS, DEFAULT_ENERGY_PRICE,
    PRICE_MIN, PRICE_MAX
)


class LaundrySensorComponent:
    """Sensor component that tracks pending laundry count."""

    def __init__(self):
        self.pending_clothes = 0

    def read(self):
        return self.pending_clothes

    def update(self, clothes_count):
        self.pending_clothes = clothes_count


class ReadyToWashSensorComponent:
    """Sensor component that indicates when it's best to wash."""

    def __init__(self):
        self.ready = False

    def read(self):
        return self.ready

    def update(self, is_ready):
        self.ready = is_ready


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

    def __init__(self, jid, password, clothes_threshold=WASHING_MACHINE_THRESHOLD, peers=None, enable_price_optimization=False):
        super().__init__(jid, password, device_type="washing_machine", peers=peers)
        self.clothes_threshold = clothes_threshold
        self.enable_price_optimization = enable_price_optimization
        self.pending_clothes = 0
        self.current_hour = None
        self.cycle_steps_remaining = 0  # Steps remaining in current wash cycle
        self.cycle_duration_steps = WASHING_MACHINE_CYCLE_DURATION_STEPS
        self.clothes_per_cycle = WASHING_MACHINE_PER_CYCLE
        self.accumulation_rate = WASHING_MACHINE_ACCUMULATION_RATE
        self.steps_waiting = 0          # How many steps clothes have been waiting (>= threshold)
        self.price_sensitivity = WASHING_MACHINE_PRICE_SENSITIVITY
        self.current_energy_price = DEFAULT_ENERGY_PRICE  # Updated each tick from world state

        self.add_sensor("laundry", LaundrySensorComponent())
        self.add_sensor("ready_to_wash", ReadyToWashSensorComponent())
        self.add_actuator("motor", WashingMotorComponent())

        # Power profile: active kW, idle kW
        self.active_power_kw = WASHING_MACHINE_ACTIVE_POWER_KW
        self.idle_power_kw = WASHING_MACHINE_IDLE_POWER_KW

        self.add_rule(
            Rule(
                name="Start Washing - Smart",
                sensor_name="ready_to_wash",
                operator="==",
                threshold=True,
                actuator_name="motor",
                command="on",
            )
        )

        self.add_rule(
            Rule(
                name="Stop Washing - No Clothes",
                sensor_name="laundry",
                operator="<",
                threshold=WASHING_MACHINE_THRESHOLD,
                actuator_name="motor",
                command="off",
            )
        )

    def update_sensors(self, world_state):
        super().update_sensors(world_state)
        self.current_hour = world_state.get("hour")
        self.current_energy_price = world_state.get("energy_price", DEFAULT_ENERGY_PRICE)
        motor = self.actuators["motor"]

        if motor.is_running:
            # Washing in progress - reset waiting time
            self.steps_waiting = 0

            if self.cycle_steps_remaining == 0:
                # Motor just turned on (or resumed after shed), start a new wash cycle
                self.cycle_steps_remaining = self.cycle_duration_steps
            else:
                # Continue existing cycle
                self.cycle_steps_remaining -= 1
                # If cycle just completed, wash the clothes
                if self.cycle_steps_remaining == 0:
                    washed = min(self.clothes_per_cycle, self.pending_clothes)
                    self.pending_clothes = max(0, self.pending_clothes - washed)
                    # If more clothes remain, start a new cycle immediately
                    if self.pending_clothes >= self.clothes_threshold:
                        self.cycle_steps_remaining = self.cycle_duration_steps
        else:
            # Machine is idle (or forcibly shed).
            if self.shed_timeout <= 0:
                self.pending_clothes += self.accumulation_rate

            if self.shed_timeout <= 0:
                self.cycle_steps_remaining = 0

            # Track waiting time when above threshold
            if self.pending_clothes >= self.clothes_threshold:
                self.steps_waiting += 1

        if self.enable_price_optimization:
            # Smart mode: prefer cheap hours, but force execution after long wait.
            cheap_threshold = PRICE_MIN + (PRICE_MAX - PRICE_MIN) * 0.4
            is_cheap_energy = self.current_energy_price <= cheap_threshold
            ready = False
            if self.pending_clothes >= self.clothes_threshold:
                if is_cheap_energy or self.steps_waiting > 24: # Waited for 24 hours max
                    ready = True
        else:
            # Baseline mode: start as soon as threshold is reached.
            ready = self.pending_clothes >= self.clothes_threshold

        self.sensors["ready_to_wash"].update(ready)
        self.sensors["laundry"].update(self.pending_clothes)

    def calculate_priority(self, world_state=None):
        """Calculate washing machine priority based on waiting time and clothes accumulation.

        Priority scale (0=lowest, 5=highest):
        - Base priority from clothes count
        - Increases with waiting time (steps since reaching threshold)

        Formula: Base priority increases by 1 for every 3 steps of waiting.

        Returns:
            int: Priority value 0-5
        """
        if self.pending_clothes < self.clothes_threshold:
            return 0  # Not enough clothes, no priority

        # Base priority from clothes count
        if self.pending_clothes >= WASHING_MACHINE_PRIORITY_THRESHOLDS[0]:
            base_priority = 5
        elif self.pending_clothes >= WASHING_MACHINE_PRIORITY_THRESHOLDS[1]:
            base_priority = 4
        elif self.pending_clothes >= WASHING_MACHINE_PRIORITY_THRESHOLDS[2]:
            base_priority = 3
        elif self.pending_clothes >= WASHING_MACHINE_PRIORITY_THRESHOLDS[3]:
            base_priority = 2
        else:  # Threshold to First Threshold range
            base_priority = 1

        # Add priority based on waiting time (1 priority per X steps)
        #waiting_bonus = self.steps_waiting // WASHING_MACHINE_WAITING_BONUS_DIVIDER

        raw_priority = base_priority #+ waiting_bonus
        # Apply price modifier: boost in cheap hours, penalize in expensive hours
        price_modifier = self._calculate_price_modifier() if self.enable_price_optimization else 0
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
