"""
Headless batch runner for statistical comparison.

Runs the existing XMPP-based multi-agent and baseline simulations at high speed
for N simulated days, then generates an averaged comparison report.

Usage:
    python batch_run.py [--days 1000]
"""

import sys
import argparse
import asyncio
import time
import logging

# Silence SPADE warnings about unmatched messages
logging.getLogger("spade").setLevel(logging.ERROR)

# ── Patch config for speed BEFORE any agent imports ──
import config
config.SIMULATION_SPEED = 0.02          # 10ms per world step (was 2s)
config.NEGOTIATION_JITTER_MAX = 0.02    # 10ms jitter (was 2s)
config.NEGOTIATION_TIMEOUT = 1          # 1s timeout (was 10s)
config.NEGOTIATION_TIMEOUT_SEC = 0.5    # 0.5s negotiation timeout (was 5s)

# ── Disable GUI: make gui module unimportable so headless mode is used ──
import types
_fake_gui = types.ModuleType("gui")
_fake_gui.__path__ = []  # make it a package
sys.modules["gui"] = _fake_gui
# This ensures `from gui import get_simulation_state` raises ImportError

from config import AGENTS, PASSWORD
from simulation.enviroment import WorldAgent
from agents import AirConditioner, Heater, Refrigerator, WashingMachine, DishWasher, AirFryerAgent
from agents.battery_agent import BatteryAgent
from simulation.baseline import start_baseline_simulation, generate_averaged_report, BASELINE_AGENTS


async def run_batch(target_days: int):
    print(f"=" * 60)
    print(f"  BATCH SIMULATION — {target_days} days")
    print(f"  Speed: {config.SIMULATION_SPEED}s/step, Jitter: {config.NEGOTIATION_JITTER_MAX}s")
    print(f"=" * 60)
    start_time = time.time()

    # ── 1. Multi-Agent system ──
    ac_jid = AGENTS["ac_livingroom"]
    heater_jid = AGENTS["heater_livingroom"]
    fridge_jid = AGENTS["fridge"]
    wm_jid = AGENTS["washing_machine"]
    dw_jid = AGENTS["dish_washer"]
    battery_jid = AGENTS["battery"]
    air_fryer_jid = AGENTS["air_fryer"]

    jid_list = [ac_jid, heater_jid, fridge_jid, wm_jid, dw_jid, battery_jid, air_fryer_jid]

    ac = AirConditioner(ac_jid, PASSWORD, target_temp=21, temp_margin=2,
                        peers=[j for j in jid_list if j != ac_jid])
    heater = Heater(heater_jid, PASSWORD, target_temp=21, temp_margin=2,
                    peers=[j for j in jid_list if j != heater_jid])
    fridge = Refrigerator(fridge_jid, PASSWORD, target_temp=4, temp_margin=1,
                          peers=[j for j in jid_list if j != fridge_jid])
    wm = WashingMachine(wm_jid, PASSWORD,
                        peers=[j for j in jid_list if j != wm_jid])
    dw = DishWasher(dw_jid, PASSWORD,
                    peers=[j for j in jid_list if j != dw_jid])
    battery = BatteryAgent(battery_jid, PASSWORD, capacity_kwh=20.0, max_power_kw=2.0,
                           peers=[j for j in jid_list if j != battery_jid])
    af = AirFryerAgent(air_fryer_jid, PASSWORD,
                       peers=[j for j in jid_list if j != air_fryer_jid])

    world = WorldAgent(AGENTS["world"], PASSWORD, season="summer", receivers=jid_list)

    main_agents = [ac, heater, fridge, wm, dw, battery, af, world]

    # ── 2. Baseline system ──
    baseline_agents, baseline_world = await start_baseline_simulation()

    # ── 3. Start all agents ──
    print("Starting agents...")
    await asyncio.gather(*[a.start(auto_register=True) for a in main_agents])
    print(f"All agents started. Running {target_days} simulated days...\n")

    # ── 4. Monitor progress ──
    last_report = 0
    while True:
        await asyncio.sleep(0.5)

        main_day = world.day_count
        base_day = baseline_world.day_count
        current_day = min(main_day, base_day)

        # Progress reporting every 10%
        pct = int((current_day / target_days) * 100)
        if pct >= last_report + 10 and pct <= 100:
            elapsed = time.time() - start_time
            rate = current_day / elapsed if elapsed > 0 else 0
            eta = (target_days - current_day) / rate if rate > 0 else 0
            print(f"  [{pct:3d}%] Day {current_day}/{target_days}  "
                  f"({rate:.1f} days/s, ETA {eta:.0f}s)")
            last_report = pct

        # Both reached target?
        if main_day > target_days and base_day > target_days:
            break

    elapsed = time.time() - start_time
    print(f"\nSimulation complete in {elapsed:.1f}s ({elapsed/target_days:.2f}s/day)")

    # ── 5. Generate averaged report ──
    generate_averaged_report(target_days, world, baseline_world)

    # ── 6. Cleanup ──
    print("Stopping agents...")
    for a in main_agents:
        await a.stop()
    for a in baseline_agents:
        await a.stop()

    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Batch simulation runner")
    parser.add_argument("--days", type=int, default=10000,
                        help="Number of simulated days to run (default: 10000)")
    args = parser.parse_args()

    asyncio.run(run_batch(args.days))


if __name__ == "__main__":
    main()
