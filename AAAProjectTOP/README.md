# 🏠 Smart Home Energy Management System

### Multi-Agent System built with Python + SPADE

A **minimal, functional, decentralised** MAS prototype where smart device agents
coordinate to reduce energy costs by exploiting solar production, battery storage,
and dynamic electricity prices.

---

## 1. Project Structure

```
smart_home_mas/
│
├── main.py                   # Entry point – creates & starts all agents
├── config.py                 # All tuneable constants (prices, thresholds, etc.)
├── environment.py            # Stateless helpers: get_price(h), get_solar(h), …
├── metrics.py                # Shared Metrics object; prints final report
│
├── agents/
│   ├── __init__.py
│   ├── base_agent.py         # BaseDeviceAgent: send_json(), log(), parse()
│   ├── world_agent.py        # Drives the clock; broadcasts STATE every tick
│   ├── solar_panel.py        # Reads env solar; notifies Battery
│   ├── battery.py            # Charges from solar/cheap grid; discharges at peak
│   ├── washing_machine.py    # Flexible scheduler – avoids peak prices
│   └── heater.py             # Temperature controller – pre-heats during cheap windows
│
├── docker-compose.yml        # Optional: local Prosody via Docker (not required)
├── prosody.cfg.lua           # Optional Prosody config for Docker mode
└── requirements.txt
```

### File Responsibilities

| File                 | What it does                                            |
| -------------------- | ------------------------------------------------------- |
| `config.py`          | Single source of truth for all constants                |
| `environment.py`     | Look-up tables for prices and solar (no state)          |
| `metrics.py`         | Collects & displays energy/cost summary                 |
| `base_agent.py`      | Convenience wrappers shared by all device agents        |
| `world_agent.py`     | Simulation clock + state broadcaster + metric collector |
| `solar_panel.py`     | Announces production; feeds Battery via SOLAR_UPDATE    |
| `battery.py`         | Charges/discharges; broadcasts BATTERY_BOOST to peers   |
| `washing_machine.py` | Schedules wash cycle respecting deadline + peer load    |
| `heater.py`          | Maintains room temp; pre-heats during cheap windows     |
| `main.py`            | Wires everything together                               |

---

## 2. Architecture Overview

```
                    ┌─────────────────┐
                    │   World Agent   │  ← drives simulation clock
                    │  (broadcasts    │     (1 tick = 1 simulated hour)
                    │   STATE msg)    │
                    └────────┬────────┘
                             │  STATE {hour, price, solar_kw, battery_soc}
           ┌─────────────────┼──────────────────────┐
           ▼                 ▼                      ▼
   ┌──────────────┐  ┌──────────────┐      ┌──────────────┐
   │  Solar Panel │  │   Battery    │      │Washing Mach. │
   │    Agent     │  │    Agent     │      │    Agent     │
   └──────┬───────┘  └──────┬───────┘      └──────┬───────┘
          │  SOLAR_UPDATE   │  BATTERY_BOOST        │  PLAN_TO_RUN
          └────────────────►│◄──────────────────────┘
                            │  BATTERY_BOOST ───────────────► Heater Agent
                            │
                    All agents send REPORT → World Agent
```

### Message Types

| Message          | Direction         | Purpose                                     |
| ---------------- | ----------------- | ------------------------------------------- |
| `STATE`          | World → All       | Current hour, price, solar, battery SoC     |
| `SOLAR_UPDATE`   | Solar → Battery   | kW available for charging                   |
| `BATTERY_BOOST`  | Battery → Devices | kW available for discharge at peak          |
| `PLAN_TO_RUN`    | Washing → Peers   | Coordination: avoids simultaneous peak load |
| `REPORT`         | All → World       | Action taken; feeds the metrics log         |
| `BATTERY_STATUS` | Battery → World   | Updated SoC after charging/discharging      |

---

## 3. Agent Decision Logic (Summary)

### ☀ Solar Panel

Always-on; reports current production to Battery and World.

### 🔋 Battery

```
if solar_surplus available AND soc < 95%  → CHARGE from solar
elif price cheap AND soc < 80%            → CHARGE from grid (half rate)
elif price expensive AND soc > 10%        → DISCHARGE, broadcast BATTERY_BOOST
else                                      → IDLE
```

### 🧺 Washing Machine

```
if cycle done                             → OFF
if past deadline                          → FORCE RUN (regardless of price)
elif price cheap                          → RUN
elif solar available                      → RUN
elif battery offering boost               → RUN
elif expensive AND 2+ peers plan to run   → DEFER (coordination!)
elif medium price                         → RUN
else                                      → DEFER
```

### 🌡 Heater

```
if temp < MIN_TEMP                        → FORCE RUN (critical)
elif temp at MAX_TEMP                     → OFF
elif low temp AND (cheap OR solar)        → RUN
elif cheap window AND temp < MAX_TEMP     → PRE-HEAT (anticipate peak)
elif expensive                            → COAST (rely on thermal mass)
else                                      → OFF
```

---

## 4. Setup & Run Instructions

### Prerequisites

- Python 3.10+
- A local Prosody/XMPP server already running on `localhost` (same setup used by the main ASMA project)

### Step 1 – Ensure XMPP Is Running

Use your existing local Prosody service used by the main project (`XMPP_SERVER=localhost`).
No Docker is required for this project path.

### Step 2 – Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 3 – Run the Simulation

```bash
python main.py
```

Each simulated hour takes **2.5 real seconds** by default (configurable in `config.py`).  
The full 24-hour simulation completes in **~65 seconds**.

### Step 4 – Read the Output

During the run you'll see live per-agent decisions:

```
────────────────────────────────────────────────────────────
  🕐  Hour 02:00  price=0.05€/kWh [CHEAP]  solar=0.0kW 🌑
────────────────────────────────────────────────────────────
  [h02] [solar     ] producing 0.00 kW  🌑 no production
  [h02] [battery   ] charging (grid)         SoC=36%  power=0.60kW
  [h02] [washing   ] 🔄 RUNNING  cheap electricity  (cycle 1/2h  source=grid)
  [h02] [heater    ] 🔥 HEATING  temp 20.2→21.7°C  pre-heating during cheap/solar window
```

At the end:

```
=================================================================
  SMART HOME ENERGY MANAGEMENT – SIMULATION REPORT
=================================================================

📋  HOURLY ACTION LOG
  [02:00] washing        ON   2.0kW via ⚡grid     cost=0.1000€
  [10:00] washing        ON   2.0kW via ☀solar     cost=0.0000€
  ...

  PER-AGENT SUMMARY
  Agent            Energy (kWh)   Cost (€)
  ──────────────── ───────────── ──────────
  battery                  6.00     0.1080
  heater                  10.50     0.8820
  washing                  4.00     0.1000
  solar                   21.60     0.0000

  TOTALS
  Total energy consumed : 42.10 kWh
  Total cost            : 1.0900 €

  ☀  Solar   : 18.30 kWh  (43%)
  🔋 Battery : 6.00  kWh  (14%)
  ⚡ Grid    : 17.80 kWh  (42%)
```

### Optional Docker Mode

If you explicitly want isolated Docker-based Prosody for this folder, you can still use:

```bash
docker compose up -d
```

but the default intended flow is to reuse the already-working local Prosody from the main project.

---

## 5. Configuration Tuning (`config.py`)

| Parameter              | Default    | Effect                                  |
| ---------------------- | ---------- | --------------------------------------- |
| `TICK_DURATION`        | 2.5s       | Simulation speed (lower = faster)       |
| `PRICE_CHEAP`          | 0.10 €/kWh | Threshold below which agents run freely |
| `PRICE_EXPENSIVE`      | 0.18 €/kWh | Threshold above which agents defer      |
| `WASHING_DEADLINE_H`   | 22         | Latest hour washing must start          |
| `BATTERY_CAPACITY_KWH` | 5.0 kWh    | Size of the home battery                |
| `HEATER_MIN_TEMP`      | 19°C       | Triggers forced heating                 |

---

## 6. Incremental Improvement Roadmap

### 🟢 Easy (next immediate steps)

1. **Add an EV Charger Agent**
   - Similar to Washing Machine but with a larger power draw (7kW) and a `must_finish_by` constraint.
   - Shows the pattern scales to more agents.

2. **Randomise solar & prices**
   - Add ±10% noise to `SOLAR_PRODUCTION` and `ELECTRICITY_PRICES` each run.
   - Makes the system more realistic and demonstrates robustness.

3. **CLI / env-var configuration**
   - Accept `--tick`, `--hours`, `--battery-size` as CLI args using `argparse`.

### 🟡 Medium (a few days of work)

4. **Visualise the simulation**
   - Log each agent's state to a CSV in `world_agent.py`.
   - Add a `plot_results.py` script using `matplotlib` to draw price curves,
     energy usage bars, and battery SoC over time.

5. **Priority-based negotiation**
   - Replace the simple "defer if 2 peers are running" rule with a proper
     priority score: `score = urgency / (price * load)`.
   - Agents broadcast their score; the lowest-score agent defers.

6. **Persistent battery SoC across runs**
   - Save battery SoC to a JSON file at the end of each simulation.
   - Load it at startup so repeated runs model a real multi-day scenario.

7. **REST API for user preferences**
   - Add a tiny FastAPI endpoint that lets the user update `WASHING_DEADLINE_H`,
     temperature range, etc. at runtime.
   - World Agent polls this endpoint at the start of each day.

### 🔴 Advanced (research / production direction)

8. **Real-time price feed**
   - Replace the static `ELECTRICITY_PRICES` list with a live API
     (e.g., ENTSO-E Transparency Platform or Tibber API).

9. **Reinforcement Learning agent**
   - Replace the rule-based Battery Agent with a DQN agent trained on historical
     price & solar data to maximise cost savings.

10. **Multi-home federation**
    - Run multiple instances of the system, each on a separate XMPP subdomain.
    - Add a `GridAgent` that mediates peer-to-peer energy trading between homes.

11. **SPADE BDI extension**
    - Migrate agents to use `spade_bdi` (BDI extension) for richer belief/desire/
      intention reasoning instead of hand-coded if/else logic.

---

## Troubleshooting

| Problem                       | Solution                                                                                      |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| `ConnectionRefusedError`      | Prosody isn't running – check `docker compose ps`                                             |
| `SASLError: not-authorized`   | Delete XMPP accounts and re-run (Prosody data volume may be stale) – `docker compose down -v` |
| Agents not receiving messages | Ensure all JIDs are on the same XMPP domain (`localhost`)                                     |
| Simulation runs too fast/slow | Adjust `TICK_DURATION` in `config.py`                                                         |
| `ModuleNotFoundError: spade`  | Run `pip install -r requirements.txt`                                                         |
