import asyncio
import json
import os
from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour, CyclicBehaviour
from spade.message import Message
from config import SIMULATION_SPEED

class EnvironmentAgent(Agent):
    def __init__(self, jid, password, scenario_file="simulation/days/summer.json", receivers=None):
        super().__init__(jid, password)
        self.scenario_file = scenario_file
        self.receivers = receivers or []
        
        # Initial current state
        self.current_hour = 0
        self.data = None
        self.current_state = {}

    def load_scenario(self):
        """Loads simulation data from the JSON file."""
        try:
            with open(self.scenario_file, 'r') as f:
                # The file is a list of days, we use the first day [0]
                self.data = json.load(f)[0]
            print(f"Scenario loaded: {self.scenario_file} ({self.data['metadata']['season']})")
        except Exception as e:
            print(f"Error loading scenario: {e}")
            self.data = None

    def update_state(self):
        """Updates the internal state based on the current hour."""
        if not self.data:
            return

        h = self.current_hour
        
        # Extract data from JSON for the current hour h
        self.current_state = {
            "hour": h,
            "temperature": self.data["environment"]["outdoor_temperature_c"][h],
            "solar_production": self.data["environment"]["solar_production_kw"][h],
            "energy_price": self.data["grid_market"]["dynamic_price_eur_kwh"][h],
            "occupancy": self.data["user_profile"]["occupancy_status"][h],
            "uncontrollable_load": self.data["base_load"]["uncontrollable_kw"][h]
        }

    class BroadcastStateBehaviour(PeriodicBehaviour):
        """Behavior that periodically sends the state to all agents."""
        async def run(self):
            # 1. Advance the clock
            self.agent.current_hour = (self.agent.current_hour + 1) % 24
            
            # If it's midnight, it's a new day
            if self.agent.current_hour == 0:
                print("\n" + "="*50)
                print(f"NEW SIMULATED DAY STARTED ({self.agent.data['metadata']['season']})")
                print("="*50)

            # 2. Update state based on JSON
            self.agent.update_state()
            state = self.agent.current_state

            # 3. Log in terminal
            print(f"[Environment] {state['hour']:02d}:00 | Temp: {state['temperature']}ºC | "
                  f"Solar: {state['solar_production']}kW | Price: {state['energy_price']}€ | "
                  f"Occupancy: {state['occupancy']}")

            # 4. Send to other agents (Push)
            if self.agent.receivers:
                payload = json.dumps(state)
                for receiver in self.agent.receivers:
                    msg = Message(to=str(receiver))
                    msg.set_metadata("performative", "inform")
                    msg.set_metadata("ontology", "environment_state")
                    msg.body = payload
                    await self.send(msg)

    class HandleRequestsBehaviour(CyclicBehaviour):
        """Behavior that responds to direct information requests (Pull)."""
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg and msg.metadata.get("performative") == "query-ref":
                # Response to the request with the current state
                reply = msg.make_reply()
                reply.set_metadata("performative", "inform")
                reply.body = json.dumps(self.agent.current_state)
                await self.send(reply)

    async def setup(self):
        print(f"EnvironmentAgent starting... (Speed: {SIMULATION_SPEED}s/hour)")
        
        self.load_scenario()
        if self.data:
            # Initialize state with hour 0 before starting
            self.update_state()
            self.add_behaviour(self.BroadcastStateBehaviour(period=SIMULATION_SPEED))
            self.add_behaviour(self.HandleRequestsBehaviour())
        else:
            print("Critical failure: Could not load simulation data.")
