import asyncio
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from config import AGENTS, PASSWORD, SIMULATION_SPEED
from simulation.enviroment import EnvironmentAgent 

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

    # List of receiver agents
    receiver_jids = [AGENTS["world"], AGENTS["fridge"]]

    # 1. Instantiate Device Agents
    world_agent = DummyDeviceAgent(AGENTS["world"], PASSWORD)
    fridge_agent = DummyDeviceAgent(AGENTS["fridge"], PASSWORD)
    
    # 2. Instantiate Environment Agent (Reads JSON and Broadcasts)
    env_agent = EnvironmentAgent(
        AGENTS["environment"], 
        PASSWORD, 
        scenario_file="simulation/days/summer.json", # Change to winter.json to test winter
        receivers=receiver_jids
    )

    # Start all agents
    await world_agent.start(auto_register=True)
    await fridge_agent.start(auto_register=True)
    await env_agent.start(auto_register=True)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupting simulation...")
    finally:
        await world_agent.stop()
        await fridge_agent.stop()
        await env_agent.stop()
        print("System shut down successfully.")

if __name__ == "__main__":
    asyncio.run(main())