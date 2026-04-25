import os
import asyncio
from config import XMPP_SERVER, PASSWORD, AGENTS
from simulation.enviroment import WorldAgent
from agents import AirConditioner, Heater, Refrigerator, WashingMachine, DishWasher, AirFryerAgent
from agents.battery_agent import BatteryAgent

BASELINE_AGENTS = {
    "world": f"b_world@{XMPP_SERVER}",
    "ac_livingroom": f"b_ac@{XMPP_SERVER}",
    "heater_livingroom": f"b_heater@{XMPP_SERVER}",
    "fridge": f"b_fridge@{XMPP_SERVER}",
    "washing_machine": f"b_wm@{XMPP_SERVER}",
    "dish_washer": f"b_dw@{XMPP_SERVER}",
    "battery": f"b_batt@{XMPP_SERVER}",
    "air_fryer": f"b_af@{XMPP_SERVER}",
}

# Mapping from baseline device name to main device name
B_TO_MAIN = {
    "b_ac": "ac.livingroom",
    "b_heater": "heater.livingroom",
    "b_fridge": "fridge",
    "b_wm": "washing_machine",
    "b_dw": "dish_washer",
    "b_batt": "battery",
    "b_af": "air_fryer",
}

async def start_baseline_simulation(main_world_agent=None):
    # Instantiate Device Agents — only battery as peer (no inter-device negotiation)
    ac_jid = BASELINE_AGENTS["ac_livingroom"]
    heater_jid = BASELINE_AGENTS["heater_livingroom"]
    fridge_jid = BASELINE_AGENTS["fridge"]
    wm_jid = BASELINE_AGENTS["washing_machine"]
    dw_jid = BASELINE_AGENTS["dish_washer"]
    battery_jid = BASELINE_AGENTS["battery"]
    air_fryer_jid = BASELINE_AGENTS["air_fryer"]
    world_jid = BASELINE_AGENTS["world"]


    # Baseline: devices only know about battery (no inter-device negotiation).
    # Battery still charges from solar and discharges to meet demand.
    device_peers = [battery_jid]
    battery_peers = [ac_jid, heater_jid, fridge_jid, wm_jid, dw_jid, air_fryer_jid]

    jid_list = [ac_jid, heater_jid, fridge_jid, wm_jid, dw_jid, battery_jid, air_fryer_jid]

    ac_livingroom = AirConditioner(ac_jid, PASSWORD, target_temp=21, temp_margin=2, peers=device_peers)
    heater_livingroom = Heater(heater_jid, PASSWORD, target_temp=21, temp_margin=2, peers=device_peers)
    fridge = Refrigerator(fridge_jid, PASSWORD, target_temp=4, temp_margin=1, peers=device_peers)
    washingmachine = WashingMachine(wm_jid, PASSWORD, peers=device_peers)
    dish_washer = DishWasher(dw_jid, PASSWORD, peers=device_peers)
    battery_agent = BatteryAgent(battery_jid, PASSWORD, peers=battery_peers)
    air_fryer = AirFryerAgent(air_fryer_jid, PASSWORD, peers=device_peers)
    
    world_agent = WorldAgent(world_jid, PASSWORD, season="summer", receivers=jid_list)
    world_agent.is_baseline = True
    # Share environment from main world so temp, solar, prices are identical
    if main_world_agent:
        import asyncio as _aio
        world_agent.main_world = main_world_agent
        world_agent._state_queue = _aio.Queue()  # Main world pushes state here
        main_world_agent.baseline_world = world_agent  # So main world can push

    agents_to_start = [
        ac_livingroom, heater_livingroom, fridge, 
        washingmachine, dish_washer, battery_agent, 
        air_fryer, world_agent
    ]
    
    await asyncio.gather(*[agent.start(auto_register=True) for agent in agents_to_start])
    print("Baseline agents started.")
    
    return agents_to_start, world_agent

def generate_comparative_report(day, main_world, baseline_world):
    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/comparative_report_day_{day}.txt"
    
    main_hist = main_world.daily_history.get(day, {})
    base_hist = baseline_world.daily_history.get(day, {})
    
    if not main_hist or not base_hist:
        return
        
    main_cost = main_hist.get("total_daily_cost_euro", 0.0)
    base_cost = base_hist.get("total_daily_cost_euro", 0.0)
    
    main_cons = main_hist.get("total_daily_consumption_kwh", 0.0)
    base_cons = base_hist.get("total_daily_consumption_kwh", 0.0)
    
    main_ren = main_hist.get("total_daily_renewable_kwh", 0.0)
    base_ren = base_hist.get("total_daily_renewable_kwh", 0.0)
    
    savings = base_cost - main_cost
    savings_pct = (savings / base_cost * 100) if base_cost > 0 else 0.0
    
    report_content = f"""==================================================
COMPARATIVE SIMULATION REPORT - DAY {day}
==================================================

1. OVERALL METRICS
--------------------------------------------------
Metric                 | Baseline         | Multi-Agent      | Difference
--------------------------------------------------
Total Energy (kWh)     | {base_cons:14.3f} | {main_cons:14.3f} | {main_cons - base_cons:10.3f}
Renewable Used (kWh)   | {base_ren:14.3f} | {main_ren:14.3f} | {main_ren - base_ren:10.3f}
Total Cost (EUR)       | {base_cost:14.3f} | {main_cost:14.3f} | {main_cost - base_cost:10.3f}

2. ECONOMIC ANALYSIS
--------------------------------------------------
Baseline Cost (No Agent Coordination): {base_cost:.3f} EUR
Multi-Agent Cost (With Coordination):  {main_cost:.3f} EUR
Savings Achieved:                      {savings:.3f} EUR ({savings_pct:.1f}%)

3. DEVICE BREAKDOWN (Multi-Agent vs Baseline)
--------------------------------------------------
"""
    main_devs = main_hist.get("device_daily_consumption_kwh", {})
    base_devs = base_hist.get("device_daily_consumption_kwh", {})
    
    dev_metrics = {}
    for k, v in main_devs.items():
        dev_metrics[k] = {"main": v, "base": 0.0}
        
    for k, v in base_devs.items():
        mapped_k = B_TO_MAIN.get(k, k)
        if mapped_k not in dev_metrics:
            dev_metrics[mapped_k] = {"main": 0.0, "base": v}
        else:
            dev_metrics[mapped_k]["base"] = v
            
    for dev, metrics in sorted(dev_metrics.items()):
        report_content += f"{dev:20s}: Baseline {metrics['base']:8.3f} kWh | Multi-Agent {metrics['main']:8.3f} kWh | Diff {metrics['main'] - metrics['base']:8.3f} kWh\n"
        
    report_content += "\n==================================================\n"
    
    with open(report_path, "w") as f:
        f.write(report_content)
        
    print(f"\n[REPORT] Comparative report for Day {day} saved to {report_path}\n")
