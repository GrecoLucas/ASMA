"""
agents/solar_panel.py – Solar Panel Agent.

Responsibilities
────────────────
  • Reads solar production from the environment each hour.
  • Informs the Battery Agent how much power is available for charging.
  • Reports its production to the World Agent.

Decision logic (simple)
────────────────────────
  • Always "produces" whatever the environment says (no control).
  • Announces production via a SOLAR_UPDATE message.

Message I/O
───────────
  IN  ← world:    {"type": "STATE", ...}
  OUT → battery:  {"type": "SOLAR_UPDATE", "hour": h, "solar_kw": kw}
  OUT → world:    {"type": "REPORT",  "agent": "solar", ...}
"""

import json
import spade
from spade.behaviour import CyclicBehaviour
from spade.template import Template

import config
import environment as env
from agents.base_agent import BaseDeviceAgent


class SolarPanelAgent(BaseDeviceAgent):

    class MainBehaviour(CyclicBehaviour):

        async def run(self):
            msg = await self.receive(timeout=config.TICK_DURATION)
            if msg is None:
                return

            data = self.agent.parse(msg)
            if data is None or data.get("type") != "STATE":
                return

            hour     = data["hour"]
            solar_kw = data["solar_kw"]
            price    = data["price"]
            self.agent.current_state = data

            is_on = solar_kw > 0.0
            self.agent.log(f"producing {solar_kw:.2f} kW  "
                           f"{'☀ active' if is_on else '🌑 no production'}")

            # Tell the Battery Agent how much solar is available
            await self.agent.send_json(
                config.BATTERY_JID,
                {
                    "type":     "SOLAR_UPDATE",
                    "hour":     hour,
                    "solar_kw": solar_kw,
                },
                metadata={"type": "SOLAR_UPDATE"},
            )

            # Report to World (solar "cost" is zero – it's free)
            source = "solar" if is_on else "none"
            await self.agent.send_json(
                config.WORLD_JID,
                {
                    "type":     "REPORT",
                    "agent":    "solar",
                    "hour":     hour,
                    "running":  is_on,
                    "power_kw": solar_kw,
                    "source":   source,
                    "price":    0.0,
                    "note":     f"production={solar_kw:.2f}kW",
                },
                metadata={"type": "REPORT"},
            )

    async def setup(self):
        self.log("Solar Panel Agent started.")
        tmpl = Template()
        tmpl.set_metadata("type", "STATE")
        self.add_behaviour(self.MainBehaviour(), tmpl)
