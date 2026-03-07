import asyncio
from spade.agent import Agent
from config import AGENTS, PASSWORD

class DummyAgent(Agent):
    async def setup(self):
        print(f"Sou o [{self.name}] e estou ligado ao servidor XMPP!")

async def main():
    print("A iniciar o Smart Home MAS...")

    # Instanciar agentes e iniciar agentes
    world_agent = DummyAgent(AGENTS["world"], PASSWORD)
    env_agent = DummyAgent(AGENTS["environment"], PASSWORD)
    await world_agent.start(auto_register=True)
    await env_agent.start(auto_register=True)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("A desligar o sistema...")
    finally:
        await world_agent.stop()
        await env_agent.stop()

if __name__ == "__main__":
    asyncio.run(main())