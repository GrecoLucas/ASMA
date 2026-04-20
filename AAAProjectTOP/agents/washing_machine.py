"""
agents/washing_machine.py – Washing Machine Agent.

Responsibilities
────────────────
  • Must complete one wash cycle (DURATION hours) within [EARLIEST, DEADLINE].
  • Prefers cheap electricity or solar power.
  • Coordinates with other agents via PLAN messages to avoid simultaneous
    high-price loads.

Decision logic (flexible scheduling)
──────────────────────────────────────
  1. If the cycle is already done → stay off.
  2. If we're past the deadline and cycle isn't done → start NOW (forced run).
  3. Otherwise choose to run if:
       (a) price is cheap,  OR
       (b) solar is available,  OR
       (c) battery is offering a boost,
     AND we haven't received more than 1 other PLAN_TO_RUN this hour.
  4. If 2+ other agents already plan to run AND price is expensive → defer.

Coordination messages
──────────────────────
  OUT → all peers: {"type": "PLAN_TO_RUN", "agent": "washing", "hour": h,
                    "power_kw": kw, "priority": "low|high"}
  IN  ← peers:     {"type": "PLAN_TO_RUN", ...}
  IN  ← battery:   {"type": "BATTERY_BOOST", ...}
  IN  ← world:     {"type": "STATE", ...}
  OUT → world:     {"type": "REPORT", ...}
"""

import json
import asyncio
import spade
from spade.behaviour import CyclicBehaviour
from spade.template import Template

import config
import environment as env
from agents.base_agent import BaseDeviceAgent


class WashingMachineAgent(BaseDeviceAgent):

    def __init__(self, jid, password, metrics, **kwargs):
        super().__init__(jid, password, metrics, **kwargs)
        self.hours_run       = 0       # hours of the current cycle completed
        self.cycle_done      = False
        self.battery_boost   = 0.0    # available battery kW this hour
        self.peer_plans      = []     # PLAN_TO_RUN messages received this tick

    # ── Coordination receiver ────────────────────────────────────────────────

    class CoordBehaviour(CyclicBehaviour):
        """Stores PLAN_TO_RUN and BATTERY_BOOST messages for the current tick."""

        async def run(self):
            msg = await self.receive(timeout=0.1)
            if msg is None:
                return
            data = self.agent.parse(msg)
            if data is None:
                return
            if data.get("type") == "PLAN_TO_RUN":
                self.agent.peer_plans.append(data)
            elif data.get("type") == "BATTERY_BOOST":
                self.agent.battery_boost = data.get("available_kw", 0.0)

    # ── Main decision behaviour ──────────────────────────────────────────────

    class MainBehaviour(CyclicBehaviour):

        async def run(self):
            msg = await self.receive(timeout=config.TICK_DURATION)
            if msg is None:
                return

            data = self.agent.parse(msg)
            if data is None or data.get("type") != "STATE":
                return

            hour       = data["hour"]
            price      = data["price"]
            solar_kw   = data["solar_kw"]
            self.agent.current_state = data

            # Reset per-tick state
            self.agent.peer_plans    = []
            self.agent.battery_boost = 0.0
            await asyncio.sleep(0.3)   # short pause so CoordBehaviour can collect messages

            cycle_done   = self.agent.cycle_done
            hours_run    = self.agent.hours_run
            hours_left   = config.WASHING_DURATION_H - hours_run
            time_left    = config.WASHING_DEADLINE_H - hour
            peer_count   = len(self.agent.peer_plans)
            battery_ok   = self.agent.battery_boost >= config.WASHING_POWER_KW * 0.5
            solar_ok     = solar_kw >= config.SOLAR_USEFUL
            cheap_ok     = env.is_cheap(hour)
            expensive    = env.is_expensive(hour)
            too_late     = time_left <= hours_left  # must start now or miss deadline
            in_window    = config.WASHING_EARLIEST_H <= hour <= config.WASHING_DEADLINE_H

            # ── Decision ─────────────────────────────────────────────────────
            should_run = False
            reason     = ""

            if cycle_done:
                reason = "cycle already done"

            elif not in_window:
                reason = f"outside allowed window ({config.WASHING_EARLIEST_H}-{config.WASHING_DEADLINE_H}h)"

            elif too_late:
                should_run = True
                reason = "⚠ deadline forcing run"

            elif cheap_ok:
                should_run = True
                reason = "cheap electricity"

            elif solar_ok:
                should_run = True
                reason = "solar available"

            elif battery_ok:
                should_run = True
                reason = "battery boost available"

            elif expensive and peer_count >= 2:
                reason = f"deferring – price expensive & {peer_count} peers already running"

            elif not expensive:
                should_run = True
                reason = "medium price, no better option"

            else:
                reason = f"deferring – price={price:.2f}€, waiting for better slot"

            # ── If planning to run, announce to peers ─────────────────────────
            if should_run:
                # Only heater and battery subscribe to PLAN_TO_RUN.
                peers = [config.HEATER_JID, config.BATTERY_JID]
                priority = "high" if too_late else "low"
                await self.agent.broadcast_json(
                    peers,
                    {
                        "type":     "PLAN_TO_RUN",
                        "agent":    "washing",
                        "hour":     hour,
                        "power_kw": config.WASHING_POWER_KW,
                        "priority": priority,
                    },
                    metadata={"type": "PLAN_TO_RUN"},
                )

                self.agent.hours_run += 1
                if self.agent.hours_run >= config.WASHING_DURATION_H:
                    self.agent.cycle_done = True

            # ── Determine energy source ───────────────────────────────────────
            if should_run:
                if solar_ok:
                    source = "solar"
                elif battery_ok:
                    source = "battery"
                else:
                    source = "grid"
            else:
                source = "none"

            self.agent.log(
                f"{'🔄 RUNNING' if should_run else '💤 off    '}  "
                f"{reason}  "
                f"(cycle {self.agent.hours_run}/{config.WASHING_DURATION_H}h  "
                f"source={source})"
            )

            # ── Report to World ───────────────────────────────────────────────
            await self.agent.send_json(
                config.WORLD_JID,
                {
                    "type":     "REPORT",
                    "agent":    "washing",
                    "hour":     hour,
                    "running":  should_run,
                    "power_kw": config.WASHING_POWER_KW if should_run else 0.0,
                    "source":   source,
                    "price":    price,
                    "note":     reason,
                },
                metadata={"type": "REPORT"},
            )

    # ── Setup ────────────────────────────────────────────────────────────────

    async def setup(self):
        self.log(f"Washing Machine Agent started. "
                 f"Deadline={config.WASHING_DEADLINE_H}h, "
                 f"Duration={config.WASHING_DURATION_H}h.")

        coord_tmpl = Template()
        coord_tmpl.set_metadata("type", "PLAN_TO_RUN")
        boost_tmpl = Template()
        boost_tmpl.set_metadata("type", "BATTERY_BOOST")
        # Combine templates with OR  (SPADE Template supports | operator)
        self.add_behaviour(self.CoordBehaviour(), coord_tmpl | boost_tmpl)

        state_tmpl = Template()
        state_tmpl.set_metadata("type", "STATE")
        self.add_behaviour(self.MainBehaviour(), state_tmpl)
