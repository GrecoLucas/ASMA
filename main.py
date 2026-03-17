import asyncio
import json
import math
import random
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
from config import AGENTS, PASSWORD, SIMULATION_SPEED
from simulation.enviroment import WorldAgent
from device import AirConditioner

async def main():
    print("Starting Smart Home Energy Management System...")
    print(f"Simulation speed: 1 hour = {SIMULATION_SPEED} real seconds.\n")

    # 1. Instantiate Device Agents
    ac_livingroom = AirConditioner(AGENTS["ac_livingroom"], PASSWORD, target_temp=22, temp_margin=2)
    world_agent = WorldAgent(AGENTS["world"], PASSWORD, season="winter", receivers=[AGENTS["ac_livingroom"]])

    # Start all agents
    await world_agent.start(auto_register=True)
    await ac_livingroom.start(auto_register=True)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupting simulation...")
    finally:
        await world_agent.stop()
        await ac_livingroom.stop()
        print("System shut down successfully.")

if __name__ == "__main__":
    asyncio.run(main())