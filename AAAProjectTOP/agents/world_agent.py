"""
agents/world_agent.py – The World Agent.

Responsibilities
────────────────
  • Drives the simulation clock (one tick = one simulated hour).
  • Broadcasts the environment STATE to every device agent each hour.
  • Collects REPORT messages from device agents (for logging).
  • Does NOT make any energy decisions.
  • Prints the final metrics report when the simulation ends.

Message I/O
───────────
  OUT → all agents:  {"type": "STATE",  "hour": h, "price": p, "solar_kw": s,
                       "battery_soc": b, "battery_available_kw": bkw}
  IN  ← any agent:   {"type": "REPORT", "agent": ..., "running": ..., ...}
  IN  ← battery:     {"type": "BATTERY_STATUS", "soc": ..., "available_kw": ...}
"""

import json
import asyncio
import spade
from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour
from spade.message import Message
from spade.template import Template

import config
import environment as env
from metrics import Metrics


class WorldAgent(Agent):

    def __init__(self, jid: str, password: str, metrics: Metrics, **kwargs):
        super().__init__(jid, password, **kwargs)
        self.metrics = metrics
        self.hour = 0
        self.battery_soc = config.BATTERY_INITIAL_SOC
        self.battery_available_kw = 0.0

    class TickBehaviour(PeriodicBehaviour):
        """Advances the simulation clock and broadcasts state."""

        async def run(self):
            agent = self.agent
            if agent.hour >= config.SIMULATION_HOURS:
                return   # already finished; waiting for stop()

            h = agent.hour
            price   = env.get_price(h)
            solar   = env.get_solar(h)

            print(f"\n{'─'*60}")
            print(f"  🕐  {env.describe_hour(h)}")
            print(f"{'─'*60}")

            state = {
                "type":                 "STATE",
                "hour":                 h,
                "price":                price,
                "solar_kw":             solar,
                "battery_soc":          agent.battery_soc,
                "battery_available_kw": agent.battery_available_kw,
            }
            
            agent.metrics.update_world_state(h, price, solar, agent.battery_soc)

            # Broadcast to all device agents
            for jid in config.ALL_DEVICE_JIDS:
                msg = Message(to=jid)
                msg.set_metadata("type", "STATE")
                msg.body = json.dumps(state)
                await self.send(msg)

            agent.hour += 1

            # After last hour: wait a moment then stop everything
            if agent.hour >= config.SIMULATION_HOURS:
                await asyncio.sleep(config.TICK_DURATION * 0.8)
                agent.metrics.print_report()
                await agent.stop()

    class ReceiveBehaviour(CyclicBehaviour):
        """Handles REPORT and BATTERY_STATUS messages from device agents."""

        async def run(self):
            msg = await self.receive(timeout=0.2)
            if msg is None:
                return
            try:
                data = json.loads(msg.body)
            except (json.JSONDecodeError, AttributeError):
                return

            if data.get("type") == "BATTERY_STATUS":
                self.agent.battery_soc = data.get("soc", self.agent.battery_soc)
                self.agent.battery_available_kw = data.get("available_kw", 0.0)

            elif data.get("type") == "REPORT":
                self.agent.metrics.record(
                    hour     = data.get("hour", 0),
                    agent    = data.get("agent", "?"),
                    running  = data.get("running", False),
                    power_kw = data.get("power_kw", 0.0),
                    source   = data.get("source", "grid"),
                    price    = data.get("price", 0.0),
                    note     = data.get("note", ""),
                )

    async def setup(self):
        print(f"  [world     ] World Agent started. Simulating {config.SIMULATION_HOURS} hours "
              f"at {config.TICK_DURATION}s/hour.")

        tick = self.TickBehaviour(period=config.TICK_DURATION)
        self.add_behaviour(tick)

        recv_tmpl = Template()
        recv_tmpl.set_metadata("type", "REPORT")
        # Battery status uses a different metadata key; accept everything from devices
        self.add_behaviour(self.ReceiveBehaviour())
