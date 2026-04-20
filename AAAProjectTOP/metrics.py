"""
metrics.py – Shared metrics object passed to every agent at creation time.

Each agent appends its hourly actions to the log and updates the running totals.
The World agent prints a final report at the end of the simulation.
"""

from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Set
import websockets
from websockets.server import WebSocketServerProtocol



@dataclass
class HourlyEntry:
    hour: int
    agent: str
    running: bool
    power_kw: float
    source: str          # "solar", "battery", "grid"
    cost_eur: float
    note: str = ""


class Metrics:
    """Thread-safe (asyncio-safe) store for simulation results."""

    def __init__(self):
        self.log: List[HourlyEntry] = []
        # running totals
        self.total_energy_kwh: float = 0.0
        self.total_cost_eur: float   = 0.0
        self.solar_kwh: float        = 0.0
        self.battery_kwh: float      = 0.0
        self.grid_kwh: float         = 0.0
        # per-agent usage
        self.agent_energy: Dict[str, float] = {}
        # overall summary for UI sync
        self.current_hour: int = 0
        self.current_price: float = 0.0
        self.current_solar: float = 0.0
        self.current_battery_soc: float = 0.0
        
        # websocket clients
        self.connected_clients: Set[WebSocketServerProtocol] = set()

    def update_world_state(self, hour: int, price: float, solar: float, battery_soc: float):
        """Called by world agent every hour to update global UI state."""
        self.current_hour = hour
        self.current_price = price
        self.current_solar = solar
        self.current_battery_soc = battery_soc
        self._broadcast({"type": "STATE", "hour": hour, "price": price, "solar_kw": solar, "battery_soc": battery_soc})
        
    def _broadcast(self, data: dict):
        if not self.connected_clients: return
        msg = json.dumps(data)
        async def send_to_all():
            for ws in list(self.connected_clients):
                try:
                    await ws.send(msg)
                except Exception:
                    pass
        asyncio.create_task(send_to_all())

    def record(self, hour: int, agent: str, running: bool,
               power_kw: float, source: str, price: float, note: str = ""):
        """Record one agent's action for one hour."""
        cost = power_kw * price if running else 0.0
        energy = power_kw if running else 0.0

        entry = HourlyEntry(hour, agent, running, power_kw, source, cost, note)
        self.log.append(entry)

        if running:
            self.total_energy_kwh += energy
            self.total_cost_eur   += cost
            self.agent_energy[agent] = self.agent_energy.get(agent, 0.0) + energy
            self.agent_cost[agent]   = self.agent_cost.get(agent, 0.0)   + cost
            if source == "solar":
                self.solar_kwh   += energy
            elif source == "battery":
                self.battery_kwh += energy
            else:
                self.grid_kwh    += energy
                
        # Send action to UI
        self._broadcast({
            "type": "ACTION",
            "entry": asdict(entry)
        })

    def print_report(self):
        SEP = "=" * 65

        print(f"\n{SEP}")
        print("  SMART HOME ENERGY MANAGEMENT – SIMULATION REPORT")
        print(SEP)

        # Hourly log
        print("\n📋  HOURLY ACTION LOG\n")
        for e in self.log:
            if e.running:
                icon = {"solar": "☀", "battery": "🔋", "grid": "⚡"}.get(e.source, "?")
                print(f"  [{e.hour:02d}:00] {e.agent:<14} ON   "
                      f"{e.power_kw:.1f}kW via {icon}{e.source:<8} "
                      f"cost={e.cost_eur:.4f}€  {e.note}")
            else:
                print(f"  [{e.hour:02d}:00] {e.agent:<14} off  {e.note}")

        # Per-agent summary
        print(f"\n{'─'*65}")
        print("  PER-AGENT SUMMARY")
        print(f"  {'Agent':<16} {'Energy (kWh)':>13} {'Cost (€)':>10}")
        print(f"  {'─'*16} {'─'*13} {'─'*10}")
        for agent in sorted(self.agent_energy):
            print(f"  {agent:<16} {self.agent_energy[agent]:>13.2f} "
                  f"{self.agent_cost[agent]:>10.4f}")

        # Overall totals
        print(f"\n{'─'*65}")
        print("  TOTALS")
        print(f"  Total energy consumed : {self.total_energy_kwh:.2f} kWh")
        print(f"  Total cost            : {self.total_cost_eur:.4f} €")

        if self.total_energy_kwh > 0:
            solar_pct   = 100 * self.solar_kwh   / self.total_energy_kwh
            battery_pct = 100 * self.battery_kwh / self.total_energy_kwh
            grid_pct    = 100 * self.grid_kwh    / self.total_energy_kwh
            print(f"\n  ☀  Solar   : {self.solar_kwh:.2f} kWh  ({solar_pct:.0f}%)")
            print(f"  🔋 Battery : {self.battery_kwh:.2f} kWh  ({battery_pct:.0f}%)")
            print(f"  ⚡ Grid    : {self.grid_kwh:.2f} kWh  ({grid_pct:.0f}%)")

        print(f"\n{SEP}\n")
