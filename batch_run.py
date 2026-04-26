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

async def multi_agent_simulation():
    # Instantiate Device Agents with peers=[] so they don't negotiate
    ac_jid = AGENTS["ac_livingroom"]
    heater_jid = AGENTS["heater_livingroom"]
    fridge_jid = AGENTS["fridge"]
    whashing_machine_jid = AGENTS["washing_machine"]
    dish_washer_jid = AGENTS["dish_washer"]
    battery_jid = AGENTS["battery"]
    air_fryer_jid = AGENTS["air_fryer"]

    price_opt = True

    jid_list = [ac_jid, heater_jid, fridge_jid, whashing_machine_jid, dish_washer_jid, battery_jid, air_fryer_jid]

    ac_livingroom = AirConditioner(ac_jid, PASSWORD, target_temp=21, temp_margin=2, peers=[jid for jid in jid_list if jid != ac_jid], enable_price_optimization=price_opt)
    heater_livingroom = Heater(heater_jid, PASSWORD, target_temp=21, temp_margin=2, peers=[jid for jid in jid_list if jid != heater_jid], enable_price_optimization=price_opt)
    fridge = Refrigerator(fridge_jid, PASSWORD, target_temp=4, temp_margin=1, peers=[jid for jid in jid_list if jid != fridge_jid], enable_price_optimization=price_opt)
    washingmachine = WashingMachine(
        whashing_machine_jid,
        PASSWORD,
        peers=[jid for jid in jid_list if jid != whashing_machine_jid],
        enable_price_optimization=price_opt,
    )
    dish_washer = DishWasher(
        dish_washer_jid,
        PASSWORD,
        peers=[jid for jid in jid_list if jid != dish_washer_jid],
        enable_price_optimization=price_opt,
    )
    battery_agent = BatteryAgent(
        battery_jid,
        PASSWORD,
        capacity_kwh=20.0,
        max_power_kw=2.0,
        peers=[jid for jid in jid_list if jid != battery_jid],
        enable_price_optimization=price_opt,
    )
    air_fryer = AirFryerAgent(air_fryer_jid, PASSWORD, peers=[jid for jid in jid_list if jid != air_fryer_jid], enable_price_optimization=price_opt)
    
    world_agent = WorldAgent(AGENTS["world"], PASSWORD, season="summer", receivers=jid_list, enable_price_optimization=price_opt)
    world_agent.is_baseline = False

    agents_to_start = [
        ac_livingroom, heater_livingroom, fridge, 
        washingmachine, dish_washer, battery_agent, 
        air_fryer, world_agent
    ]
    
    return agents_to_start, world_agent

async def baseline_simulation():
        # Instantiate Device Agents with peers=[] so they don't negotiate
    ac_jid = BASELINE_AGENTS["ac_livingroom"]
    heater_jid = BASELINE_AGENTS["heater_livingroom"]
    fridge_jid = BASELINE_AGENTS["fridge"]
    wm_jid = BASELINE_AGENTS["washing_machine"]
    dw_jid = BASELINE_AGENTS["dish_washer"]
    battery_jid = BASELINE_AGENTS["battery"]
    air_fryer_jid = BASELINE_AGENTS["air_fryer"]
    world_jid = BASELINE_AGENTS["world"]

    enable_price_opt = False  # Baseline does not optimize for price

    jid_list = [ac_jid, heater_jid, fridge_jid, wm_jid, dw_jid, battery_jid, air_fryer_jid]

    ac_livingroom = AirConditioner(ac_jid, PASSWORD, target_temp=21, temp_margin=2, peers=[battery_jid])
    heater_livingroom = Heater(heater_jid, PASSWORD, target_temp=21, temp_margin=2, peers=[battery_jid])
    fridge = Refrigerator(fridge_jid, PASSWORD, target_temp=4, temp_margin=1, peers=[battery_jid])
    washingmachine = WashingMachine(wm_jid, PASSWORD, peers=[battery_jid], enable_price_optimization=enable_price_opt)
    dish_washer = DishWasher(dw_jid, PASSWORD, peers=[battery_jid], enable_price_optimization=enable_price_opt)
    battery_agent = BatteryAgent(battery_jid, PASSWORD, capacity_kwh=20.0, max_power_kw=2.0, peers=[], enable_price_optimization=enable_price_opt)
    air_fryer = AirFryerAgent(air_fryer_jid, PASSWORD, peers=[battery_jid])
    
    world_agent = WorldAgent(world_jid, PASSWORD, season="summer", receivers=jid_list)
    world_agent.is_baseline = True

    agents_to_start = [
        ac_livingroom, heater_livingroom, fridge, 
        washingmachine, dish_washer, battery_agent, 
        air_fryer, world_agent
    ]
    return agents_to_start, world_agent  

async def run_batch(target_days: int):
    print(f"=" * 60)
    print(f"  BATCH SIMULATION — {target_days} days")
    print(f"  Speed: {config.SIMULATION_SPEED}s/step, Jitter: {config.NEGOTIATION_JITTER_MAX}s")
    print(f"=" * 60)
    start_time = time.time()

    # ── 1. Multi-Agent system ──Stil
    main_agents, world = await multi_agent_simulation()

    # ── 2. Baseline system ──
    baseline_agents, baseline_world = await baseline_simulation()

    # ── 3. Start all agents ──
    print("Starting agents...")
    await asyncio.gather(*[a.start(auto_register=True) for a in main_agents + baseline_agents])
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
