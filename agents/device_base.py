import json
import time
import uuid
import logging
import threading
import asyncio
import random
from itertools import combinations
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message

# Import GUI state if available
try:
    from gui import get_simulation_state
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

from config import (
    PRICE_MIN, PRICE_MAX, DEFAULT_PRIORITY, DEFAULT_ENERGY_PRICE,
    NEGOTIATION_JITTER_MAX, NEGOTIATION_TIMEOUT, SHED_TIMEOUT_STEPS
)


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
        self.negotiation_failures = 0

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

    _class_lock = threading.Lock()

    # Track which shedders were already used in a committed negotiation per simulation slot.
    _slot_shed_registry = {}
    # Track pending power reservations from agents currently negotiating (race condition prevention)
    _pending_power_reservations = {}

    @classmethod
    def _purge_old_slots(cls, current_day):
        """Remove slot entries from previous days to prevent memory leak."""
        with cls._class_lock:
            cls._slot_shed_registry = {
                k: v for k, v in cls._slot_shed_registry.items()
                if k[0] >= current_day
            }

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
        self.solar_production = 0.0

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
        return DEFAULT_PRIORITY  # Default priority from config

    def estimate_total_power(self):
        """Estimate current gross power demand from all devices.

        Returns the total power consumption from P2P data, own consumption,
        and pending power reservations from other agents currently negotiating.
        Uses the higher value between last known status and pending reservation for each peer.

        NOTE: This returns GROSS demand — it does NOT subtract provided power
        (battery discharge). Supply-side contributions (solar, battery, grid)
        are accounted for in get_total_available_power() to avoid double-counting.

        Returns:
            float: Estimated gross total power demand in kW
        """
        my_name = self._normalize_agent_name(self.name)
        
        with Device._class_lock:
            # Bug Fix 2: Include own reservation in total power if we are negotiating to turn ON
            my_reservation = Device._pending_power_reservations.get(my_name, 0.0)
            total = max(self.get_power_consumption_kw(), my_reservation)
            
            # Get all agent names we know about
            all_peers = set(self.peer_power_status.keys())
            all_peers.update(Device._pending_power_reservations.keys())
            
        if my_name in all_peers:
            all_peers.remove(my_name)
            
        for peer in all_peers:
            status = self.peer_power_status.get(peer, {})
            status_p = status.get("power_kw", 0.0)
            
            with Device._class_lock:
                res_p = Device._pending_power_reservations.get(peer, 0.0)
            
            # max() clamps negative values (e.g. battery discharging) to 0,
            # while correctly counting positive consumption (e.g. battery charging from solar)
            total += max(status_p, res_p)
            
        return total


    def _calculate_price_modifier(self):
        """Calculate priority modifier based on current energy price.

        Returns a value that increases priority in cheap hours and decreases
        in expensive hours. Devices with price_sensitivity=0 are unaffected.
        """
        sensitivity = getattr(self, 'price_sensitivity', 0)
        if sensitivity == 0:
            return 0
        price = getattr(self, 'current_energy_price', DEFAULT_ENERGY_PRICE)
        normalized = (price - PRICE_MIN) / (PRICE_MAX - PRICE_MIN)
        normalized = max(0.0, min(1.0, normalized))
        return round(sensitivity * (1.0 - 2.0 * normalized))

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
        self.solar_production = world_state.get("solar_production", 0.0)

    def get_power_consumption_kw(self):
        """Return current power draw in kW. Override for custom behavior."""
        return self.idle_power_kw

    def get_provided_power_kw(self):
        """Return power provided to the system (e.g. by battery). Override in subclasses."""
        return 0.0

    def get_available_power_kw(self):
        """Return maximum power this device can provide right now. Override in subclasses."""
        return 0.0

    def get_total_available_power(self):
        """Total power ceiling for negotiations: Grid limit + Solar + Battery discharge.

        Energy priority order:
          1. Solar powers the house first
          2. Excess solar charges the battery
          3. Battery supplements when solar is insufficient
          4. Grid covers whatever remains

        Returns:
            float: Maximum power (kW) the house can draw from all sources combined.
        """
        from config import MAX_POWER_KW
        solar = getattr(self, 'solar_production', 0.0)
        
        # Battery capacity comes from P2P broadcasts (available_power_kw),
        # which is the same as the GUI's min(max_power_kw, charge_kwh).
        battery_available = 0.0
        if getattr(self, "device_type", "") == "battery":
            battery_available = self.get_available_power_kw()
        elif 'battery' in self.peer_power_status:
            battery_available = self.peer_power_status['battery'].get('available_power_kw', 0.0)
            
        return MAX_POWER_KW + solar + battery_available


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
            Device._purge_old_slots(day)

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

    def _push_gui_device_state(self):
        """Push current device state to GUI immediately after out-of-cycle state changes."""
        if not GUI_AVAILABLE:
            return
        state = get_simulation_state()
        state.update_device_state(self.name, self.get_device_state_for_gui())

    @staticmethod
    def _normalize_agent_name(agent_id):
        value = str(agent_id or "")
        if "/" in value:
            value = value.split("/", 1)[0]
        if "@" in value:
            value = value.split("@", 1)[0]
        return value

    def _log_p2p(self, sender, receiver, content, event=None, tx_id=None, **kwargs):
        if not GUI_AVAILABLE:
            return
        state = get_simulation_state()

        # Format the event clearly with additional context
        tag_prefix = f"[{event}] " if event else ""

        # Enhance messages with more details
        if "REQUEST to turn ON" in content:
            power = kwargs.get('power_kw', 0)
            priority = kwargs.get('priority', '?')
            total = kwargs.get('total_kw', 0)
            content = f"Requests {power:.2f}kW (Priority {priority}, Total: {total:.2f}kW / {self.get_total_available_power():.2f}kW)"
        elif "REPLY" in content:
            decision = kwargs.get("decision", "").lower()
            reason = kwargs.get("reason", "")
            shed_power_kw = kwargs.get("shed_power_kw", 0.0)
            responder_priority = kwargs.get("responder_priority", "?")
            if decision == "accept":
                if reason == "shed_possible":
                    content = f"Accepts [SHED {shed_power_kw:.2f}kW p{responder_priority}]"
                else:
                    content = "Accepts [LIMIT]"
            elif decision == "reject":
                if reason == "not_lower_priority":
                    content = "Rejects [PRIORITY]"
                elif reason == "no_shed_capacity":
                    content = "Rejects [NO SHED CAP]"
                else:
                    content = "Rejects [NOT ELIGIBLE]"
        elif "COMMIT applied, turned ON" in content:
            selected_count = kwargs.get("selected_count", 0)
            selected_peers = kwargs.get("selected_peers", [])
            overflow_kw = kwargs.get("overflow_kw", 0.0)
            if overflow_kw > 0:
                peers_text = ", ".join(selected_peers) if selected_peers else "none"
                content = f"✓ ON [SHED {selected_count}: {peers_text}]"
            else:
                content = "✓ ON [NO SHED]"
        elif "ABORT" in content:
            if "timeout" in content:
                content = "✗ Aborted (timeout)"
            elif "shedder already used this slot" in content:
                content = "✗ Aborted (shedder already used this slot)"
            elif "insufficient accepted shedding" in content:
                content = "✗ Aborted (accepted shedding not enough)"
            else:
                content = "✗ Aborted"

        state.add_message(
            self._normalize_agent_name(sender),
            self._normalize_agent_name(receiver),
            f"{tag_prefix}{content}",
        )

    async def _start_power_negotiation(self, rule, behaviour, world_state=None):
        from config import MAX_POWER_KW

        tx_id = uuid.uuid4().hex
        requester = self._normalize_agent_name(self.name)

        # Bug Fix 1: Register power reservation BEFORE Jitter so others see our intention
        # during their own calculation cycles even if we are still sleeping.
        with Device._class_lock:
            Device._pending_power_reservations[requester] = self.active_power_kw

        # Introduction of Jitter to break synchronization of agents starting simultaneously
        await asyncio.sleep(random.uniform(0.1, NEGOTIATION_JITTER_MAX))

        # With Bug Fix 2, estimate_total_power() now includes our own pending reservation.
        estimated_total = self.estimate_total_power()
        expected = {self._normalize_agent_name(peer_jid) for peer_jid in self.peers}
        slot_key = None
        if world_state is not None:
            slot_key = (
                int(world_state.get("day", 0)),
                int(world_state.get("hour", 0)),
                int(world_state.get("minute", 0)),
            )

        self.pending_negotiations[tx_id] = {
            "created_at": time.monotonic(),
            "rule": rule,
            "requester": requester,
            "expected_replies": expected,
            "replies": {},
            "estimated_total_kw": estimated_total,
            "max_power_kw": MAX_POWER_KW,
            "slot_key": slot_key,
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
            self._log_p2p(
                requester, peer_jid, "REQUEST to turn ON",
                event="REQUEST", tx_id=tx_id,
                power_kw=self.active_power_kw,
                priority=self.current_priority,
                total_kw=estimated_total
            )

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
            "shed_power_kw": float(data.get("shed_power_kw", 0.0)),
            "responder_priority": int(data.get("responder_priority", DEFAULT_PRIORITY)),
        }

        self._log_p2p(
            peer_name,
            self.name,
            f"REPLY {decision.upper()} {reason}".strip(),
            event="REPLY",
            tx_id=tx_id,
            decision=decision,
            reason=reason,
            shed_power_kw=float(data.get("shed_power_kw", 0.0)),
            responder_priority=int(data.get("responder_priority", DEFAULT_PRIORITY)),
        )

        expected = negotiation["expected_replies"]
        if expected.issubset(set(negotiation["replies"].keys())):
            await self._finalize_negotiation(tx_id, timed_out=False, behaviour=behaviour)

    async def _finalize_negotiation(self, tx_id, timed_out, behaviour):
        from config import AGENTS

        negotiation = self.pending_negotiations.get(tx_id)
        if not negotiation:
            return

        requester_priority = self.current_priority if self.current_priority is not None else DEFAULT_PRIORITY

        accepted_replies = {
            peer_name: reply
            for peer_name, reply in negotiation["replies"].items()
            if reply.get("decision") == "accept"
        }

        # Total available power = Grid + Solar + Battery discharge.
        # Overflow is how much demand exceeds this ceiling.
        total_available = self.get_total_available_power()
        overflow_kw = max(0.0, negotiation["estimated_total_kw"] - total_available)

        selected_shedders = []
        commit = False
        blocked_shedder_conflict = False

        # New policy: no unanimity required. Commit if at least one peer accepts
        # and enough accepted low-priority shedding is available for overflow.
        if accepted_replies:
            if overflow_kw <= 0:
                commit = True
            else:
                shedding_candidates = []
                for peer_name, reply in accepted_replies.items():
                    responder_priority = int(reply.get("responder_priority", DEFAULT_PRIORITY))
                    shed_power_kw = float(reply.get("shed_power_kw", 0.0))
                    can_shed = bool(reply.get("should_shed", False)) and shed_power_kw > 0
                    if can_shed and responder_priority < requester_priority:
                        shedding_candidates.append((peer_name, responder_priority, shed_power_kw))

                # Optimize for the fewest devices first; tie-break by lower priorities.
                for k in range(1, len(shedding_candidates) + 1):
                    feasible_sets = []
                    for candidate_set in combinations(shedding_candidates, k):
                        total_shed = sum(item[2] for item in candidate_set)
                        if total_shed + 1e-9 >= overflow_kw:
                            priorities = sorted(item[1] for item in candidate_set)
                            feasible_sets.append((priorities, -total_shed, candidate_set))

                    if feasible_sets:
                        feasible_sets.sort(key=lambda item: (item[0], item[1]))
                        best_set = feasible_sets[0][2]
                        selected_shedders = [item[0] for item in best_set]
                        commit = True
                        break

        # Guard against overlapping same-slot commits reusing the same shedder (Bug 2: use lock)
        slot_key = negotiation.get("slot_key")
        if commit and overflow_kw > 0 and slot_key is not None:
            with Device._class_lock:
                used_shedders = Device._slot_shed_registry.setdefault(slot_key, set())
                if any(peer in used_shedders for peer in selected_shedders):
                    commit = False
                    blocked_shedder_conflict = True
                else:
                    used_shedders.update(selected_shedders)

        for peer_jid in self.peers:
            peer_name = self._normalize_agent_name(peer_jid)
            msg = Message(to=peer_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("ontology", "p2p")
            msg.body = json.dumps(
                {
                    "event": "power_commit" if commit else "power_abort",
                    "transaction_id": tx_id,
                    "requester": negotiation["requester"],
                    "shed_peers": selected_shedders if commit else [],
                    "peer_selected_for_shed": peer_name in selected_shedders if commit else False,
                }
            )
            await behaviour.send(msg)

        rule = negotiation["rule"]
        if commit:
            rule.negotiation_failures = 0
            self.actuate(rule.actuator_name, "on")
            # Bug Fix 3: Broadcast power status immediately so peers see the new load
            await self._broadcast_power_status(behaviour)
            self._push_gui_device_state()
            self._log_p2p(
                self.name,
                "all_peers",
                "COMMIT applied, turned ON",
                event="COMMIT",
                tx_id=tx_id,
                selected_count=len(selected_shedders),
                selected_peers=selected_shedders,
                overflow_kw=overflow_kw,
            )
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
            rule.negotiation_failures += 1
            # Exponential backoff: apply shed_timeout to slow down retries
            from config import NEGOTIATION_RETRY_LIMIT
            if rule.negotiation_failures > NEGOTIATION_RETRY_LIMIT:
                self.shed_timeout = max(self.shed_timeout, min(2 ** rule.negotiation_failures, 10))
            if timed_out:
                reason = "timeout"
            elif blocked_shedder_conflict:
                reason = "shedder already used this slot"
            else:
                reason = "insufficient accepted shedding"
            self._log_p2p(self.name, "all_peers", f"ABORT due to {reason}", event="ABORT", tx_id=tx_id)

        # Clear reservation regardless of commit/abort (Bug 2: use lock)
        requester = negotiation.get("requester", "")
        with Device._class_lock:
            Device._pending_power_reservations.pop(requester, None)
        self.pending_negotiations.pop(tx_id, None)

    async def _broadcast_power_status(self, behaviour, world_state=None):
        """Broadcast current power status to peers. Used for regular updates and immediate COMMIT notifications."""
        if not self.peers:
            return
        
        device_name = self.name.split("@")[0]
        current_power = self.get_power_consumption_kw()
        provided_power = self.get_provided_power_kw()
        available_power = self.get_available_power_kw()
        
        # Use world state time or system time as fallback
        if world_state:
            timestamp = world_state.get("hour", 0) * 60 + world_state.get("minute", 0)
        else:
            timestamp = int(time.time())

        for peer_jid in self.peers:
            power_status_msg = Message(to=peer_jid)
            power_status_msg.set_metadata("performative", "inform")
            power_status_msg.set_metadata("ontology", "p2p")
            power_status_msg.body = json.dumps({
                "event": "power_status",
                "device_name": device_name,
                "power_kw": round(current_power, 3),
                "provided_power_kw": round(provided_power, 3),
                "available_power_kw": round(available_power, 3),
                "timestamp": timestamp
            })
            await behaviour.send(power_status_msg)

    async def _apply_shedding(self, requester_name, tx_id, behaviour):
        from config import AGENTS

        # Adding +1 ensures the net effective timeout after the decrement is exactly the intended steps.
        self.shed_timeout = SHED_TIMEOUT_STEPS + 1
        # Find the primary actuator (from the first "on" rule) and shed only that
        primary_actuator = None
        for rule in self.rules:
            if rule.command == "on":
                primary_actuator = rule.actuator_name
                rule.last_triggered = False
                break
        for rule in self.rules:
            if rule.command == "off" and (primary_actuator is None or rule.actuator_name == primary_actuator):
                self.actuate(rule.actuator_name, rule.command)
                rule.last_triggered = True
                break

        self._push_gui_device_state()

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
            msg = await self.receive(timeout=NEGOTIATION_TIMEOUT)
            if msg:
                try:
                    world_state = json.loads(msg.body)

                    # Calculate current priority based on world state
                    self.agent.current_priority = self.agent.calculate_priority(world_state)

                    # so the net effective timeout is 3 steps as intended.
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
                    await self.agent._broadcast_power_status(self, world_state)

                    # Notify world about hourly consumption
                    # WorldAgent uses the correct price for this time slot's cost calculation.
                    consumption_msg = Message(to=AGENTS["world"])
                    consumption_msg.body = json.dumps({
                        "event": "device_consumption",
                        "device_name": device_name,
                        "hour": world_state.get("hour"),
                        "minute": world_state.get("minute", 0),
                        "day": world_state.get("day"),
                        "energy_price": world_state.get("energy_price", DEFAULT_ENERGY_PRICE),
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
                                await self.agent._start_power_negotiation(rule, self, world_state)
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
                    logging.warning(f"[{self.agent.name}] Error parsing world message: {e}")

    class PeerCommunicationBehaviour(CyclicBehaviour):
        """Escuta pedidos de peers e atualiza status de energia. Liberta carga se necessário (Shedding)."""
        async def run(self):
            msg = await self.receive(timeout=NEGOTIATION_TIMEOUT)
            if msg:
                try:
                    data = json.loads(msg.body)

                    # Handle power status updates from peers
                    if data.get("event") == "power_status":
                        device_name = data.get("device_name")
                        power_kw = data.get("power_kw", 0)
                        provided_power_kw = data.get("provided_power_kw", 0)
                        available_power_kw = data.get("available_power_kw", 0)
                        timestamp = data.get("timestamp", 0)
 
                        self.agent.peer_power_status[device_name] = {
                            "power_kw": power_kw,
                            "provided_power_kw": provided_power_kw,
                            "available_power_kw": available_power_kw,
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
                            req_priority = DEFAULT_PRIORITY

                        # Calculate my current priority
                        my_priority = self.agent.current_priority if self.agent.current_priority is not None else DEFAULT_PRIORITY
                        my_name = self.agent._normalize_agent_name(self.agent.name)
                        
                        current_power_kw = self.agent.get_power_consumption_kw()
                        shed_power_kw = max(0.0, current_power_kw - self.agent.idle_power_kw)

                        # Locally recalculate total power instead of trusting delayed requester projection
                        projected_total_kw = self.agent.estimate_total_power()

                        # Total available power = Grid + Solar + Battery discharge
                        total_available_power = self.agent.get_total_available_power()

                        should_shed = (
                            projected_total_kw > total_available_power
                            and shed_power_kw > 0
                            and (my_priority < req_priority or (my_priority == req_priority and my_name > requester))
                        )
                        decision = "accept" if (projected_total_kw <= total_available_power or should_shed) else "reject"
                        if should_shed:
                            reason = "shed_possible"
                        elif projected_total_kw <= total_available_power:
                            reason = "within_limit"
                        elif shed_power_kw <= 0:
                            reason = "no_shed_capacity"
                        elif my_priority >= req_priority:
                            reason = "not_lower_priority"
                        else:
                            reason = "cannot_shed"

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
                                "shed_power_kw": round(shed_power_kw, 3),
                                "responder_priority": my_priority,
                                "responder": self.agent._normalize_agent_name(self.agent.name),
                            }
                        )
                        await self.send(reply)

                    elif data.get("event") == "power_reply":
                        await self.agent._register_power_reply(data, msg.sender, self)

                    elif data.get("event") == "power_commit":
                        tx_id = data.get("transaction_id")
                        shed_peers = data.get("shed_peers", [])
                        my_name = self.agent._normalize_agent_name(self.agent.name)
                        decision = self.agent.incoming_request_decisions.pop(tx_id, None)
                        actual_shed_power = max(0.0, self.agent.get_power_consumption_kw() - self.agent.idle_power_kw)
                        if decision and decision.get("accept") and my_name in shed_peers and actual_shed_power > 0:
                            await self.agent._apply_shedding(decision.get("requester", "unknown"), tx_id, self)
                        elif decision and my_name in shed_peers and actual_shed_power <= 0:
                            self.agent._log_p2p(
                                self.agent.name,
                                data.get("requester", "unknown"),
                                "SHED skipped (already off)",
                                event="SHED_SKIP",
                                tx_id=tx_id,
                            )
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
                    logging.warning(f"[{self.agent.name}] P2P Error: {e}")

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

        # Initialize peer power status with idle defaults to avoid underestimation
        for peer_jid in self.peers:
            peer_name = self._normalize_agent_name(peer_jid)
            self.peer_power_status[peer_name] = {"power_kw": 0.0, "timestamp": 0}

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
