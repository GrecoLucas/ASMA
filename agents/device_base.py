import json
import time
import uuid
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
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

    def __init__(self, jid, password, device_type="generic", peers=None):
        super().__init__(jid, password)
        self.device_type = device_type
        self.peers = peers or []
        self.current_priority = None  # Calculated dynamically each step
        self.peer_power_status = {}  # Tracks {peer_name: {power_kw, timestamp}}
        self.pending_negotiations = {}  # {tx_id: {rule, expected_replies, replies, ...}}
        self.incoming_request_decisions = {}  # {tx_id: {accept, should_shed, requester}}
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

    def calculate_priority(self, world_state=None):
        """Calculate device priority (0-5, where 5=highest).

        Override in subclasses based on device-specific operational needs.
        - 5: Critical/highest priority
        - 3-4: High priority
        - 3: Medium priority (default)
        - 0-2: Low priority (can defer)

        Returns:
            int: Priority value 0-5
        """
        return 3  # Default medium priority

    def estimate_total_power(self):
        """Estimate current total power consumption from P2P data and own consumption.

        Returns:
            float: Estimated total power in kW
        """
        my_power = self.get_power_consumption_kw()
        peer_power = sum(
            data["power_kw"]
            for data in self.peer_power_status.values()
        )
        return my_power + peer_power

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

                if rule.command == "on" and self.peers:
                    # In distributed mode, defer ON until negotiation COMMIT.
                    rule.last_triggered = True
                    result = (rule, True, "Negotiation started", True)
                else:
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
        """For configurable simulation steps, kWh equals a fraction of current kW draw."""
        from config import MINUTES_PER_STEP
        return round(self.get_power_consumption_kw() * (MINUTES_PER_STEP / 60.0), 3)

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

    @staticmethod
    def _normalize_agent_name(agent_id):
        value = str(agent_id or "")
        if "/" in value:
            value = value.split("/", 1)[0]
        if "@" in value:
            value = value.split("@", 1)[0]
        return value

    def _log_p2p(self, sender, receiver, content, event=None, tx_id=None):
        if not GUI_AVAILABLE:
            return
        state = get_simulation_state()
        tag_parts = []
        if event:
            tag_parts.append(event)
        if tx_id:
            tag_parts.append(f"tx={tx_id[:8]}")
        tag_prefix = f"[{' | '.join(tag_parts)}] " if tag_parts else ""
        state.add_message(
            self._normalize_agent_name(sender),
            self._normalize_agent_name(receiver),
            f"{tag_prefix}{content}",
        )

    async def _start_power_negotiation(self, rule, behaviour):
        from config import MAX_POWER_KW

        tx_id = uuid.uuid4().hex
        requester = self._normalize_agent_name(self.name)
        current_power = self.get_power_consumption_kw()
        power_increase = max(0.0, self.active_power_kw - current_power)
        estimated_total = self.estimate_total_power() + power_increase
        expected = {self._normalize_agent_name(peer_jid) for peer_jid in self.peers}

        self.pending_negotiations[tx_id] = {
            "created_at": time.monotonic(),
            "rule": rule,
            "requester": requester,
            "expected_replies": expected,
            "replies": {},
            "estimated_total_kw": estimated_total,
            "max_power_kw": MAX_POWER_KW,
            "attempts": 0,
        }

        for peer_jid in self.peers:
            peer_msg = Message(to=peer_jid)
            peer_msg.set_metadata("performative", "inform")
            peer_msg.set_metadata("ontology", "p2p")
            peer_msg.body = json.dumps(
                {
                    "event": "power_request",
                    "transaction_id": tx_id,
                    "requester": requester,
                    "priority": self.current_priority,
                    "power_needed_kw": round(self.active_power_kw, 3),
                    "projected_total_kw": round(estimated_total, 3),
                    "max_power_kw": MAX_POWER_KW,
                }
            )
            await behaviour.send(peer_msg)
            self._log_p2p(requester, peer_jid, "REQUEST to turn ON", event="REQUEST", tx_id=tx_id)


    async def _register_power_reply(self, data, msg_sender, behaviour):
        tx_id = data.get("transaction_id")
        if not tx_id or tx_id not in self.pending_negotiations:
            return

        peer_name = self._normalize_agent_name(msg_sender)
        decision = (data.get("decision") or "reject").lower()
        should_shed = bool(data.get("should_shed", False))
        reason = data.get("reason", "")

        negotiation = self.pending_negotiations[tx_id]
        negotiation["replies"][peer_name] = {
            "decision": decision,
            "should_shed": should_shed,
            "reason": reason,
        }

        self._log_p2p(peer_name, self.name, f"REPLY {decision.upper()} {reason}".strip(), event="REPLY", tx_id=tx_id)

        expected = negotiation["expected_replies"]
        if expected.issubset(set(negotiation["replies"].keys())):
            await self._finalize_negotiation(tx_id, timed_out=False, behaviour=behaviour)

    async def _finalize_negotiation(self, tx_id, timed_out, behaviour):
        from config import AGENTS

        negotiation = self.pending_negotiations.get(tx_id)
        if not negotiation:
            return

        replies = negotiation["replies"].values()
        has_reject = any(reply.get("decision") != "accept" for reply in replies)
        commit = not has_reject and len(negotiation["replies"]) > 0 and not timed_out

        for peer_jid in self.peers:
            msg = Message(to=peer_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("ontology", "p2p")
            msg.body = json.dumps(
                {
                    "event": "power_commit" if commit else "power_abort",
                    "transaction_id": tx_id,
                    "requester": negotiation["requester"],
                }
            )
            await behaviour.send(msg)

        rule = negotiation["rule"]
        if commit:
            self.actuate(rule.actuator_name, "on")
            self._log_p2p(self.name, "all_peers", "COMMIT applied, turned ON", event="COMMIT", tx_id=tx_id)
            notify_msg = Message(to=AGENTS["world"])
            notify_msg.body = json.dumps(
                {
                    "event": "state_changed",
                    "device_name": self._normalize_agent_name(self.name),
                    "state": "ON",
                }
            )
            await behaviour.send(notify_msg)
        else:
            # Release the ON rule so it can reattempt if condition remains true.
            rule.last_triggered = False
            reason = "timeout" if timed_out else "peer rejection"
            self._log_p2p(self.name, "all_peers", f"ABORT due to {reason}", event="ABORT", tx_id=tx_id)

        self.pending_negotiations.pop(tx_id, None)

    async def _apply_shedding(self, requester_name, tx_id, behaviour):
        from config import AGENTS

        self.shed_timeout = 3
        for rule in self.rules:
            if rule.command == "off":
                self.actuate(rule.actuator_name, rule.command)
                rule.last_triggered = True
            elif rule.command == "on":
                rule.last_triggered = False

        notify_msg = Message(to=AGENTS["world"])
        notify_msg.body = json.dumps(
            {
                "event": "state_changed",
                "device_name": self._normalize_agent_name(self.name),
                "state": "OFF (SHED)",
            }
        )
        await behaviour.send(notify_msg)
        self._log_p2p(self.name, requester_name, "SHED load after COMMIT", event="SHED", tx_id=tx_id)

    class MonitorEnvironment(CyclicBehaviour):
        """Generic behavior that monitors environment and controls device using rules."""

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    world_state = json.loads(msg.body)

                    # Calculate current priority based on world state
                    self.agent.current_priority = self.agent.calculate_priority(world_state)

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

                    # Broadcast power status to peers (P2P communication)
                    if self.agent.peers:
                        current_power = self.agent.get_power_consumption_kw()
                        for peer_jid in self.agent.peers:
                            power_status_msg = Message(to=peer_jid)
                            power_status_msg.set_metadata("performative", "inform")
                            power_status_msg.set_metadata("ontology", "p2p")
                            power_status_msg.body = json.dumps({
                                "event": "power_status",
                                "device_name": device_name,
                                "power_kw": round(current_power, 3),
                                "timestamp": world_state.get("hour", 0) * 60 + world_state.get("minute", 0)
                            })
                            await self.send(power_status_msg)

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

                            # Se ligar, envia Broadcast de Intenção aos Peers (Negociação)
                            if rule.command == "on" and self.agent.peers:
                                await self.agent._start_power_negotiation(rule, self)
                                continue

                            notify_msg = Message(to=AGENTS["world"])
                            notify_msg.body = json.dumps({
                                "event": "state_changed",
                                "device_name": device_name,
                                "state": rule.command.upper(),
                            })
                            await self.send(notify_msg)

                    if GUI_AVAILABLE:
                        state = get_simulation_state()
                        device_state = self.agent.get_device_state_for_gui()
                        state.update_device_state(self.agent.name, device_state)

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[{self.agent.name}] Error parsing message: {e}")

    class PeerCommunicationBehaviour(CyclicBehaviour):
        """Escuta pedidos de peers e atualiza status de energia. Liberta carga se necessário (Shedding)."""
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    data = json.loads(msg.body)

                    # Handle power status updates from peers
                    if data.get("event") == "power_status":
                        device_name = data.get("device_name")
                        power_kw = data.get("power_kw", 0)
                        timestamp = data.get("timestamp", 0)

                        # Update peer power status
                        self.agent.peer_power_status[device_name] = {
                            "power_kw": power_kw,
                            "timestamp": timestamp
                        }

                    # Handle power requests for negotiation
                    elif data.get("event") == "power_request":
                        tx_id = data.get("transaction_id")
                        req_priority = data.get("priority")
                        requester = data.get("requester", "unknown")
                        projected_total_kw = data.get("projected_total_kw", data.get("current_total_kw", 0))
                        max_power_kw = data.get("max_power_kw", 7.0)

                        if req_priority is None:
                            req_priority = 3

                        # Calculate my current priority
                        my_priority = self.agent.current_priority if self.agent.current_priority is not None else 3
                        current_power_kw = self.agent.get_power_consumption_kw()

                        should_shed = (
                            projected_total_kw > max_power_kw
                            and current_power_kw > self.agent.idle_power_kw
                            and my_priority < req_priority
                        )
                        decision = "accept" if (projected_total_kw <= max_power_kw or should_shed) else "reject"
                        reason = "shed_possible" if should_shed else ("within_limit" if projected_total_kw <= max_power_kw else "cannot_shed")

                        self.agent.incoming_request_decisions[tx_id] = {
                            "accept": decision == "accept",
                            "should_shed": should_shed,
                            "requester": requester,
                        }

                        reply = Message(to=str(msg.sender).split("/", 1)[0])
                        reply.set_metadata("performative", "inform")
                        reply.set_metadata("ontology", "p2p")
                        reply.body = json.dumps(
                            {
                                "event": "power_reply",
                                "transaction_id": tx_id,
                                "decision": decision,
                                "should_shed": should_shed,
                                "reason": reason,
                                "responder": self.agent._normalize_agent_name(self.agent.name),
                            }
                        )
                        await self.send(reply)

                    elif data.get("event") == "power_reply":
                        await self.agent._register_power_reply(data, msg.sender, self)

                    elif data.get("event") == "power_commit":
                        tx_id = data.get("transaction_id")
                        decision = self.agent.incoming_request_decisions.pop(tx_id, None)
                        if decision and decision.get("accept") and decision.get("should_shed"):
                            await self.agent._apply_shedding(decision.get("requester", "unknown"), tx_id, self)
                        self.agent._log_p2p(
                            data.get("requester", "unknown"),
                            self.agent.name,
                            "COMMIT received",
                            event="COMMIT",
                            tx_id=tx_id,
                        )

                    elif data.get("event") == "power_abort":
                        tx_id = data.get("transaction_id")
                        self.agent.incoming_request_decisions.pop(tx_id, None)
                        self.agent._log_p2p(
                            data.get("requester", "unknown"),
                            self.agent.name,
                            "ABORT received",
                            event="ABORT",
                            tx_id=tx_id,
                        )

                except Exception as e:
                    print(f"[{self.agent.name}] P2P Error: {e}")

    class NegotiationTimeoutBehaviour(PeriodicBehaviour):
        """Abort pending negotiations when replies do not arrive in time."""

        async def run(self):
            from config import NEGOTIATION_TIMEOUT_SEC

            now = time.monotonic()
            pending_ids = list(self.agent.pending_negotiations.keys())
            for tx_id in pending_ids:
                negotiation = self.agent.pending_negotiations.get(tx_id)
                if not negotiation:
                    continue

                age = now - negotiation["created_at"]
                if age >= NEGOTIATION_TIMEOUT_SEC:
                    await self.agent._finalize_negotiation(tx_id, timed_out=True, behaviour=self)

    async def setup(self):
                
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

        from config import NEGOTIATION_LOOP_PERIOD_SEC
        self.add_behaviour(self.NegotiationTimeoutBehaviour(period=NEGOTIATION_LOOP_PERIOD_SEC))

    def __repr__(self):
        return f"Device(name={self.name}, type={self.device_type}, status={self.status})"
