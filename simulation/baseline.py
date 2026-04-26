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

async def start_baseline_simulation():
    # Instantiate Device Agents with peers=[] so they don't negotiate
    ac_jid = BASELINE_AGENTS["ac_livingroom"]
    heater_jid = BASELINE_AGENTS["heater_livingroom"]
    fridge_jid = BASELINE_AGENTS["fridge"]
    wm_jid = BASELINE_AGENTS["washing_machine"]
    dw_jid = BASELINE_AGENTS["dish_washer"]
    battery_jid = BASELINE_AGENTS["battery"]
    air_fryer_jid = BASELINE_AGENTS["air_fryer"]
    world_jid = BASELINE_AGENTS["world"]


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


def generate_averaged_report(total_days, main_world, baseline_world):
    """Generate a statistical comparison report averaged over all simulated days."""
    import math
    os.makedirs("reports", exist_ok=True)
    report_path = "reports/averaged_comparative_report.txt"

    # Collect daily values from both worlds
    main_costs, base_costs = [], []
    main_energy, base_energy = [], []
    main_renew, base_renew = [], []
    main_solar_gen, base_solar_gen = [], []
    main_dev_totals = {}  # {device_name: [day1_kwh, day2_kwh, ...]}
    base_dev_totals = {}

    matched_days = 0
    for day in range(1, total_days + 1):
        m = main_world.daily_history.get(day)
        b = baseline_world.daily_history.get(day)
        if not m or not b:
            continue
        matched_days += 1

        main_costs.append(m.get("total_daily_cost_euro", 0.0))
        base_costs.append(b.get("total_daily_cost_euro", 0.0))

        main_energy.append(m.get("total_daily_consumption_kwh", 0.0))
        base_energy.append(b.get("total_daily_consumption_kwh", 0.0))

        main_renew.append(m.get("total_daily_renewable_kwh", 0.0))
        base_renew.append(b.get("total_daily_renewable_kwh", 0.0))

        main_solar_gen.append(m.get("total_daily_solar_generated_kwh", 0.0))
        base_solar_gen.append(b.get("total_daily_solar_generated_kwh", 0.0))

        # Per-device breakdown
        for dev, kwh in m.get("device_daily_consumption_kwh", {}).items():
            main_dev_totals.setdefault(dev, []).append(kwh)
        for dev, kwh in b.get("device_daily_consumption_kwh", {}).items():
            mapped = B_TO_MAIN.get(dev, dev)
            base_dev_totals.setdefault(mapped, []).append(kwh)

    if matched_days == 0:
        print("[REPORT] No matched days found — cannot generate averaged report.")
        return

    def mean(lst):
        return sum(lst) / len(lst) if lst else 0.0

    def stddev(lst):
        if len(lst) < 2:
            return 0.0
        m = mean(lst)
        return math.sqrt(sum((x - m) ** 2 for x in lst) / (len(lst) - 1))

    # Compute averaged metrics
    avg_main_cost = mean(main_costs)
    avg_base_cost = mean(base_costs)
    std_main_cost = stddev(main_costs)
    std_base_cost = stddev(base_costs)

    avg_main_energy = mean(main_energy)
    avg_base_energy = mean(base_energy)
    std_main_energy = stddev(main_energy)
    std_base_energy = stddev(base_energy)

    avg_main_renew = mean(main_renew)
    avg_base_renew = mean(base_renew)
    std_main_renew = stddev(main_renew)
    std_base_renew = stddev(base_renew)

    avg_main_solar = mean(main_solar_gen)
    avg_base_solar = mean(base_solar_gen)

    avg_savings = avg_base_cost - avg_main_cost
    savings_pct = (avg_savings / avg_base_cost * 100) if avg_base_cost > 0 else 0.0

    # Per-day savings for std dev of savings
    day_savings = [b - m for b, m in zip(base_costs, main_costs)]
    std_savings = stddev(day_savings)

    report = f"""{'=' * 70}
AVERAGED COMPARATIVE SIMULATION REPORT
{'=' * 70}
Season: Summer  |  Days simulated: {matched_days}  |  Values: Mean ± StdDev

1. OVERALL METRICS (per day)
{'-' * 70}
{'Metric':<24s} | {'Baseline':>20s} | {'Multi-Agent':>20s} | {'Difference':>12s}
{'-' * 70}
{'Total Energy (kWh)':<24s} | {avg_base_energy:8.3f} ± {std_base_energy:6.3f} | {avg_main_energy:8.3f} ± {std_main_energy:6.3f} | {avg_main_energy - avg_base_energy:+10.3f}
{'Renewable Used (kWh)':<24s} | {avg_base_renew:8.3f} ± {std_base_renew:6.3f} | {avg_main_renew:8.3f} ± {std_main_renew:6.3f} | {avg_main_renew - avg_base_renew:+10.3f}
{'Solar Generated (kWh)':<24s} | {avg_base_solar:8.3f}          | {avg_main_solar:8.3f}          | {avg_main_solar - avg_base_solar:+10.3f}
{'Total Cost (EUR)':<24s} | {avg_base_cost:8.3f} ± {std_base_cost:6.3f} | {avg_main_cost:8.3f} ± {std_main_cost:6.3f} | {avg_main_cost - avg_base_cost:+10.3f}

2. ECONOMIC ANALYSIS
{'-' * 70}
Baseline Avg Cost (No Coordination):   {avg_base_cost:.3f} ± {std_base_cost:.3f} EUR/day
Multi-Agent Avg Cost (With Coord.):     {avg_main_cost:.3f} ± {std_main_cost:.3f} EUR/day
Average Daily Savings:                  {avg_savings:.3f} ± {std_savings:.3f} EUR ({savings_pct:+.1f}%)

3. DEVICE BREAKDOWN — Mean daily consumption (kWh)
{'-' * 70}
"""

    # Merge device names
    all_devs = sorted(set(list(main_dev_totals.keys()) + list(base_dev_totals.keys())))
    for dev in all_devs:
        m_vals = main_dev_totals.get(dev, [])
        b_vals = base_dev_totals.get(dev, [])
        m_avg = mean(m_vals)
        m_std = stddev(m_vals)
        b_avg = mean(b_vals)
        b_std = stddev(b_vals)
        diff = m_avg - b_avg
        report += (f"{dev:20s}: Baseline {b_avg:7.3f}±{b_std:5.3f} | "
                   f"Multi-Agent {m_avg:7.3f}±{m_std:5.3f} | "
                   f"Diff {diff:+7.3f} kWh\n")

    report += f"\n{'=' * 70}\n"

    with open(report_path, "w") as f:
        f.write(report)

    print(f"\n{'=' * 60}")
    print(f"  AVERAGED REPORT saved to {report_path}")
    print(f"  {matched_days} days | Savings: {avg_savings:.3f} EUR/day ({savings_pct:+.1f}%)")
    print(f"{'=' * 60}\n")

