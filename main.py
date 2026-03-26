import asyncio
from threading import Thread
from config import AGENTS, PASSWORD, SIMULATION_SPEED
from simulation.enviroment import WorldAgent
from agents import AirConditioner, Refrigerator
from gui import start_gui

async def main():

    # Start GUI in separate thread
    gui_thread = Thread(target=start_gui, daemon=True)
    gui_thread.start()

    # 1. Instantiate Device Agents
    ac_jid = AGENTS["ac_livingroom"]
    fridge_jid = AGENTS["fridge"]

    ac_livingroom = AirConditioner(ac_jid, PASSWORD, target_temp=21, temp_margin=2, peers=[fridge_jid])
    fridge = Refrigerator(fridge_jid, PASSWORD, target_temp=4, temp_margin=1, peers=[ac_jid])
    world_agent = WorldAgent(AGENTS["world"], PASSWORD, season="summer", receivers=[ac_jid, fridge_jid])

    # Start all agents (devices first, then world broadcaster)
    await ac_livingroom.start(auto_register=True)
    await fridge.start(auto_register=True)
    await world_agent.start(auto_register=True)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupting simulation...")
    finally:
        await world_agent.stop()
        await ac_livingroom.stop()
        await fridge.stop()

if __name__ == "__main__":
    asyncio.run(main())