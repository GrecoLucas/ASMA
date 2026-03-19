import asyncio
from threading import Thread
from config import AGENTS, PASSWORD, SIMULATION_SPEED
from simulation.enviroment import WorldAgent
from agents import AirConditioner, Refrigerator
from gui import start_gui

async def main():
    print("Starting Smart Home Energy Management System...")
    print(f"Simulation speed: 1 hour = {SIMULATION_SPEED} real seconds.\n")

    # Start GUI in separate thread
    gui_thread = Thread(target=start_gui, daemon=True)
    gui_thread.start()
    print("GUI started...")

    # 1. Instantiate Device Agents
    ac_livingroom = AirConditioner(AGENTS["ac_livingroom"], PASSWORD, target_temp=20, temp_margin=2)
    fridge = Refrigerator(AGENTS["fridge"], PASSWORD, target_temp=4, temp_margin=1)
    world_agent = WorldAgent(AGENTS["world"], PASSWORD, season="summer", receivers=[AGENTS["ac_livingroom"], AGENTS["fridge"]])

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
        print("System shut down successfully.")

if __name__ == "__main__":
    asyncio.run(main())