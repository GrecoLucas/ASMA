"""
main.py – Entry point for the Smart Home Multi-Agent Energy System.

Run with:
    python main.py

Prerequisites:
    • A Prosody XMPP server running on localhost (see docker-compose.yml).
    • Python packages from requirements.txt installed.
"""

import asyncio
import os
import sys
import spade

import config
from metrics import Metrics
from agents import (
    WorldAgent,
    SolarPanelAgent,
    BatteryAgent,
    WashingMachineAgent,
    HeaterAgent,
)


def _configure_console_encoding() -> None:
    """Use UTF-8 console streams so Unicode logs do not crash on Windows."""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


async def main():
    _configure_console_encoding()

    print("=" * 60)
    print("  🏠  Smart Home Energy Management System")
    print(f"  Simulating {config.SIMULATION_HOURS} hours "
          f"(tick = {config.TICK_DURATION}s real time)")
    print("=" * 60)

    # Shared metrics object – passed to every agent
    metrics = Metrics()

    async def ws_handler(ws):
        metrics.connected_clients.add(ws)
        try:
            import json
            initial = json.dumps({
                "type": "STATE", "hour": metrics.current_hour, "price": metrics.current_price, 
                "solar_kw": metrics.current_solar, "battery_soc": metrics.current_battery_soc
            })
            await ws.send(initial)
            async for message in ws:
                pass
        finally:
            metrics.connected_clients.remove(ws)
            
    import websockets
    print(f"  Starting WebSocket server on ws://localhost:{config.WS_PORT}")
    ws_server = await websockets.serve(ws_handler, "localhost", config.WS_PORT)

    # ── Instantiate agents ───────────────────────────────────────────────────
    solar   = SolarPanelAgent(config.SOLAR_JID,   config.AGENT_PASSWORD, metrics)
    battery = BatteryAgent   (config.BATTERY_JID, config.AGENT_PASSWORD, metrics)
    washing = WashingMachineAgent(config.WASHING_JID, config.AGENT_PASSWORD, metrics)
    heater  = HeaterAgent    (config.HEATER_JID,  config.AGENT_PASSWORD, metrics)
    world   = WorldAgent     (config.WORLD_JID,   config.AGENT_PASSWORD, metrics)

    # ── Start agents (auto_register creates XMPP accounts on first run) ──────
    await solar.start  (auto_register=True)
    await battery.start(auto_register=True)
    await washing.start(auto_register=True)
    await heater.start (auto_register=True)
    await world.start  (auto_register=True)   # start last – it drives the clock

    print("\n  All agents started. Simulation running…\n")

    # ── Wait for simulation to complete ──────────────────────────────────────
    sim_duration = config.TICK_DURATION * (config.SIMULATION_HOURS + 3)
    await asyncio.sleep(sim_duration)

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    print("  Stopping agents…")
    await world.stop()
    await heater.stop()
    await washing.stop()
    await battery.stop()
    await solar.stop()
    ws_server.close()
    await ws_server.wait_closed()
    print("  Done.")


if __name__ == "__main__":
    spade.run(main())
