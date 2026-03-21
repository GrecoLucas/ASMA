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

    def __init__(self, jid, password, device_type="generic", peers=None, priority=10):
        super().__init__(jid, password)
        self.device_type = device_type
        self.peers = peers or []
        self.priority = priority
        self.sensors = {}
        self.actuators = {}
        self.relations = {}
        self.rules = []
        self.status = "idle"
        self.shed_timeout = 0

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
                if rule.command == "on" and self.shed_timeout > 0:
                    continue  # Under shedding penalty, cannot turn on right now

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
        """For 15-minute simulation steps, kWh equals a quarter of current kW draw."""
        return round(self.get_power_consumption_kw() * 0.25, 3)

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
        minute = world_state.get("minute", 0)
        return f"Time: {hour:02d}:{minute:02d}"

    class MonitorEnvironment(CyclicBehaviour):
        """Generic behavior that monitors environment and controls device using rules."""

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    world_state = json.loads(msg.body)
                    
                    if self.agent.shed_timeout > 0:
                        self.agent.shed_timeout -= 1

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
                        "minute": world_state.get("minute", 0),
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

                            # Se ligar, envia Broadcast de Intenção aos Peers (Negociação)
                            if rule.command == "on" and self.agent.peers:
                                for peer_jid in self.agent.peers:
                                    peer_msg = Message(to=peer_jid)
                                    peer_msg.set_metadata("performative", "inform")
                                    peer_msg.set_metadata("ontology", "p2p")
                                    peer_msg.body = json.dumps({
                                        "event": "power_request",
                                        "priority": self.agent.priority,
                                        "power_kw": self.agent.active_power_kw
                                    })
                                    await self.send(peer_msg)
                                    
                                    if GUI_AVAILABLE:
                                        state = get_simulation_state()
                                        state.add_message(self.agent.name.split("@")[0], peer_jid.split("@")[0], "POWER REQUEST (I want to turn ON)")

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

    class PeerCommunicationBehaviour(CyclicBehaviour):
        """Escuta pedidos de peers e, se tiver menor prioridade, liberta carga (Shedding)."""
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    data = json.loads(msg.body)
                    if data.get("event") == "power_request":
                        req_priority = data.get("priority")
                        req_kw = data.get("power_kw")
                        current_power_kw = self.agent.get_power_consumption_kw()
                        
                        # Se estou ativo e ouço alguem com MAIOR prioridade (número menor)
                        if current_power_kw > self.agent.idle_power_kw and self.agent.priority > req_priority:
                            print(f"[{self.agent.name}] CONFLITO P2P: Cedendo energia a {msg.sender} (Shedding)")
                            
                            if GUI_AVAILABLE:
                                state = get_simulation_state()
                                state.add_message(self.agent.name.split("@")[0], msg.sender.split("@")[0], "YIELDING (Shedding load due to higher priority)")
                                
                            self.agent.shed_timeout = 3  # Desativa por 3 ticks do simulador
                            
                            # Força o desligamento dos atuadores e reseta Rules
                            for rule in self.agent.rules:
                                if rule.command == "off":
                                    self.agent.actuate(rule.actuator_name, rule.command)
                                    rule.last_triggered = True
                                elif rule.command == "on":
                                    rule.last_triggered = False
                                    
                            from config import AGENTS
                            notify_msg = Message(to=AGENTS["world"])
                            notify_msg.body = json.dumps({
                                "event": "state_changed",
                                "device_name": self.agent.name.split("@")[0],
                                "state": "OFF (SHED)",
                            })
                            await self.send(notify_msg)
                except Exception as e:
                    print(f"[{self.agent.name}] P2P Error: {e}")

    async def setup(self):
        print(f"Agent [{self.name}] ({self.device_type.title()}) started. P2P priority: {self.priority}")
        if self.rules:
            print(f"  - Rules configured: {len(self.rules)}")
            for rule in self.rules:
                print(f"    - {rule}")
                
        from spade.template import Template
        from config import AGENTS
        
        # Filtro para mensagens do Mundo
        world_template = Template()
        world_template.sender = AGENTS["world"]
        self.add_behaviour(self.MonitorEnvironment(), world_template)
        
        # Filtro para mensagens P2P
        peer_template = Template()
        peer_template.metadata = {"ontology": "p2p"}
        self.add_behaviour(self.PeerCommunicationBehaviour(), peer_template)

    def __repr__(self):
        return f"Device(name={self.name}, type={self.device_type}, status={self.status})"
