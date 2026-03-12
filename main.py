import asyncio
import json
import math
import random
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
from config import AGENTS, PASSWORD, SIMULATION_SPEED
from simulation.enviroment import WorldAgent 

class DummyDeviceAgent(Agent):
    class ReceiveEnvironment(CyclicBehaviour):
        async def run(self):
            # Wait for environment messages
            msg = await self.receive(timeout=10)
            if msg:
                data = json.loads(msg.body)
                print(f"[{self.agent.name}] Data received -> Hour: {data['hour']}h, Price: {data['energy_price']}€")

    async def setup(self):
        print(f"Agent [{self.name}] started.")
        self.add_behaviour(self.ReceiveEnvironment())

async def main():
    print("Starting Smart Home Energy Management System...")
    print(f"Simulation speed: 1 hour = {SIMULATION_SPEED} real seconds.\n")

    # 1. Instantiate Device Agents
    world_agent = WorldAgent(AGENTS["world"], PASSWORD, season="winter")

    # Start all agents
    await world_agent.start(auto_register=True)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupting simulation...")
    finally:
        await world_agent.stop()
        print("System shut down successfully.")

if __name__ == "__main__":
    asyncio.run(main())