"""
agents/battery.py – Battery Storage Agent.

Responsibilities
────────────────
  • Maintains State-of-Charge (SoC).
  • Charges from solar when solar surplus is available.
  • Also charges from the grid during cheap hours if SoC is low.
  • Discharges to cover other agents' demand during expensive hours.
  • Broadcasts its current status to the World Agent every hour.
  • Tells other device agents whether it can supply them power.

Decision logic
──────────────
  CHARGE  →  solar available  OR  (price is cheap AND soc < 80%)
  DISCHARGE → price is expensive AND soc > MIN_SOC
  IDLE    →  otherwise

Message I/O
───────────
  IN ← world:  {"type": "STATE", ...}
  IN ← solar:  {"type": "SOLAR_UPDATE", "solar_kw": kw}
  OUT → world: {"type": "BATTERY_STATUS", "soc": ..., "available_kw": ...}
  OUT → world: {"type": "REPORT", ...}
  OUT → all devices: {"type": "BATTERY_BOOST", "available_kw": kw}  (when discharging)
"""

import json
import spade
from spade.behaviour import CyclicBehaviour
from spade.template import Template

import config
import environment as env
from agents.base_agent import BaseDeviceAgent


class BatteryAgent(BaseDeviceAgent):

    def __init__(self, jid, password, metrics, **kwargs):
        super().__init__(jid, password, metrics, **kwargs)
        self.soc        = config.BATTERY_INITIAL_SOC
        self.solar_kw   = 0.0   # latest value from Solar Panel
        self.pending_state: dict | None = None   # buffered STATE message

    # ── Sub-behaviours ───────────────────────────────────────────────────────

    class ReceiveSolarBehaviour(CyclicBehaviour):
        """Listens for SOLAR_UPDATE messages from the Solar Panel."""
        async def run(self):
            msg = await self.receive(timeout=0.1)
            if msg is None:
                return
            data = self.agent.parse(msg)
            if data and data.get("type") == "SOLAR_UPDATE":
                self.agent.solar_kw = data.get("solar_kw", 0.0)

    class MainBehaviour(CyclicBehaviour):
        """Makes charge/discharge decisions on STATE messages."""

        async def run(self):
            msg = await self.receive(timeout=config.TICK_DURATION)
            if msg is None:
                return

            data = self.agent.parse(msg)
            if data is None or data.get("type") != "STATE":
                return

            hour   = data["hour"]
            price  = data["price"]
            self.agent.current_state = data
            agent  = self.agent

            solar_kw  = agent.solar_kw
            soc       = agent.soc
            cap       = config.BATTERY_CAPACITY_KWH
            min_soc   = config.BATTERY_MIN_SOC
            max_soc   = config.BATTERY_MAX_SOC
            chg_rate  = config.BATTERY_CHARGE_RATE_KW
            dchg_rate = config.BATTERY_DISCHARGE_KW
            eff       = config.BATTERY_EFFICIENCY

            # ── Decision logic ───────────────────────────────────────────────
            mode         = "idle"
            power_kw     = 0.0
            source       = "grid"
            available_kw = 0.0   # how much can be offered to other agents

            solar_surplus = solar_kw - 0.3   # rough estimate of household base load

            if solar_surplus > 0.1 and soc < max_soc:
                # Charge from solar surplus
                charge_kw = min(solar_surplus * eff, chg_rate, cap * (max_soc - soc))
                agent.soc += charge_kw / cap
                mode      = "charging"
                power_kw  = charge_kw
                source    = "solar"

            elif env.is_cheap(hour) and soc < 0.80:
                # Opportunistic grid charge during cheap hours
                charge_kw = min(chg_rate * 0.5, cap * (max_soc - soc))
                agent.soc += (charge_kw * eff) / cap
                mode      = "charging (grid)"
                power_kw  = charge_kw
                source    = "grid"

            elif env.is_expensive(hour) and soc > min_soc:
                # Discharge to help other agents avoid expensive grid power
                discharge_kw = min(dchg_rate, cap * (soc - min_soc))
                agent.soc   -= discharge_kw / cap
                mode         = "discharging"
                power_kw     = discharge_kw
                source        = "battery"
                available_kw  = discharge_kw

            # Clamp SoC to valid range
            agent.soc = max(min_soc, min(max_soc, agent.soc))

            agent.log(f"{mode:<22}  SoC={agent.soc*100:.0f}%  "
                      f"power={power_kw:.2f}kW  "
                      f"{'💰 offering ' + str(round(available_kw,1)) + 'kW' if available_kw else ''}")

            # ── Notify World of battery status ───────────────────────────────
            await agent.send_json(
                config.WORLD_JID,
                {
                    "type":         "BATTERY_STATUS",
                    "soc":          agent.soc,
                    "available_kw": available_kw,
                },
                metadata={"type": "BATTERY_STATUS"},
            )

            # ── If discharging, broadcast boost offer to devices ─────────────
            if available_kw > 0:
                # Only heater and washing subscribe to BATTERY_BOOST.
                device_jids = [config.HEATER_JID, config.WASHING_JID]
                await agent.broadcast_json(
                    device_jids,
                    {
                        "type":         "BATTERY_BOOST",
                        "hour":         hour,
                        "available_kw": available_kw,
                    },
                    metadata={"type": "BATTERY_BOOST"},
                )

            # ── Report to World ──────────────────────────────────────────────
            running = mode not in ("idle",)
            await agent.send_json(
                config.WORLD_JID,
                {
                    "type":     "REPORT",
                    "agent":    "battery",
                    "hour":     hour,
                    "running":  running,
                    "power_kw": power_kw,
                    "source":   source,
                    "price":    price if source == "grid" else 0.0,
                    "note":     f"{mode}  soc={agent.soc*100:.0f}%",
                },
                metadata={"type": "REPORT"},
            )

    # ── Setup ────────────────────────────────────────────────────────────────

    async def setup(self):
        self.log(f"Battery Agent started. SoC={self.soc*100:.0f}% "
                 f"cap={config.BATTERY_CAPACITY_KWH}kWh.")

        # Two separate behaviours with different templates
        solar_tmpl = Template()
        solar_tmpl.set_metadata("type", "SOLAR_UPDATE")
        self.add_behaviour(self.ReceiveSolarBehaviour(), solar_tmpl)

        state_tmpl = Template()
        state_tmpl.set_metadata("type", "STATE")
        self.add_behaviour(self.MainBehaviour(), state_tmpl)
