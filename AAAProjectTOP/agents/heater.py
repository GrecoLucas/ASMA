"""
agents/heater.py – Smart Heater Agent.

Responsibilities
────────────────
  • Maintains room temperature within [MIN_TEMP, MAX_TEMP].
  • Prefers to run during cheap hours or when solar is available,
    pre-heating the room so it can coast through expensive peaks.
  • If temperature is about to drop below minimum, runs regardless of price.

Decision logic (temperature + price aware)
──────────────────────────────────────────
  MUST run  →  temperature < MIN_TEMP
  PREFER run→  temperature < (MIN_TEMP + 1.0) AND (cheap OR solar OR battery)
  SMART run →  temperature < MAX_TEMP AND (cheap OR solar) → pre-heat
  OFF       →  temperature >= MAX_TEMP  OR  (expensive AND not critical)

Message I/O
───────────
  IN  ← world:   {"type": "STATE", ...}
  IN  ← battery: {"type": "BATTERY_BOOST", ...}
  OUT → world:   {"type": "REPORT", ...}
"""

import asyncio
from spade.behaviour import CyclicBehaviour
from spade.template import Template

import config
import environment as env
from agents.base_agent import BaseDeviceAgent


class HeaterAgent(BaseDeviceAgent):

    def __init__(self, jid, password, metrics, **kwargs):
        super().__init__(jid, password, metrics, **kwargs)
        self.temperature   = config.HEATER_TEMP_INITIAL
        self.battery_boost = 0.0

    # ── Battery boost receiver ───────────────────────────────────────────────

    class BoostBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=0.1)
            if msg is None:
                return
            data = self.agent.parse(msg)
            if data and data.get("type") == "BATTERY_BOOST":
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

            hour     = data["hour"]
            price    = data["price"]
            solar_kw = data["solar_kw"]
            self.agent.current_state = data

            await asyncio.sleep(0.2)   # let boost messages arrive

            temp     = self.agent.temperature
            t_min    = config.HEATER_MIN_TEMP
            t_max    = config.HEATER_MAX_TEMP
            solar_ok  = solar_kw >= config.SOLAR_USEFUL
            cheap_ok  = env.is_cheap(hour)
            expensive = env.is_expensive(hour)
            batt_ok   = self.agent.battery_boost >= config.HEATER_POWER_KW * 0.5
            critical  = temp < t_min                    # must heat
            low_temp  = temp < t_min + 1.0              # prefer to heat
            pre_heat  = temp < t_max and (cheap_ok or solar_ok)  # opportunistic

            # ── Decision ─────────────────────────────────────────────────────
            should_run = False
            reason     = ""

            if critical:
                should_run = True
                reason = "⚠ temp critical – forced run"

            elif temp >= t_max:
                reason = f"temp {temp:.1f}°C at max – off"

            elif low_temp and (cheap_ok or solar_ok or batt_ok):
                should_run = True
                if cheap_ok:   reason = "low temp + cheap power"
                elif solar_ok: reason = "low temp + solar available"
                else:          reason = "low temp + battery boost"

            elif pre_heat and not expensive:
                should_run = True
                reason = "pre-heating during cheap/solar window"

            elif expensive:
                reason = f"expensive electricity ({price:.2f}€) – coasting at {temp:.1f}°C"

            else:
                reason = f"temp OK ({temp:.1f}°C) – staying off"

            # ── Update room temperature ───────────────────────────────────────
            if should_run:
                self.agent.temperature += config.HEATER_TEMP_GAIN_PER_H
            else:
                self.agent.temperature -= config.HEATER_TEMP_LOSS_PER_H

            self.agent.temperature = max(14.0, min(25.0, self.agent.temperature))
            new_temp = self.agent.temperature

            # ── Energy source ─────────────────────────────────────────────────
            if should_run:
                if solar_ok:  source = "solar"
                elif batt_ok: source = "battery"
                else:         source = "grid"
            else:
                source = "none"

            self.agent.log(
                f"{'🔥 HEATING' if should_run else '❄  off    '}  "
                f"temp {temp:.1f}→{new_temp:.1f}°C  {reason}  source={source}"
            )

            # ── Reset battery boost for next tick ────────────────────────────
            self.agent.battery_boost = 0.0

            # ── Report to World ───────────────────────────────────────────────
            await self.agent.send_json(
                config.WORLD_JID,
                {
                    "type":     "REPORT",
                    "agent":    "heater",
                    "hour":     hour,
                    "running":  should_run,
                    "power_kw": config.HEATER_POWER_KW if should_run else 0.0,
                    "source":   source,
                    "price":    price,
                    "note":     f"{reason} temp={new_temp:.1f}°C",
                },
                metadata={"type": "REPORT"},
            )

    # ── Setup ────────────────────────────────────────────────────────────────

    async def setup(self):
        self.log(f"Heater Agent started. "
                 f"Temp={self.temperature:.1f}°C  "
                 f"Range=[{config.HEATER_MIN_TEMP},{config.HEATER_MAX_TEMP}]°C.")

        boost_tmpl = Template()
        boost_tmpl.set_metadata("type", "BATTERY_BOOST")
        self.add_behaviour(self.BoostBehaviour(), boost_tmpl)

        state_tmpl = Template()
        state_tmpl.set_metadata("type", "STATE")
        self.add_behaviour(self.MainBehaviour(), state_tmpl)
