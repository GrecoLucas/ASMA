import asyncio
from threading import Thread
from config import AGENTS, PASSWORD, SIMULATION_SPEED
from simulation.enviroment import WorldAgent
from agents import AirConditioner, Refrigerator, WashingMachine, DishWasher
from gui import start_gui

async def main():

    # Start GUI in separate thread
    gui_thread = Thread(target=start_gui, daemon=True)
    gui_thread.start()

    # 1. Instantiate Device Agents
    ac_jid = AGENTS["ac_livingroom"]
    fridge_jid = AGENTS["fridge"]
    whashing_machine_jid = AGENTS["washing_machine"]
    dish_washer_jid = AGENTS["dish_washer"]

    jid_list = [ac_jid, fridge_jid, whashing_machine_jid, dish_washer_jid]

    ac_livingroom = AirConditioner(ac_jid, PASSWORD, target_temp=21, temp_margin=2, peers=[jid for jid in jid_list if jid != ac_jid])
    fridge = Refrigerator(fridge_jid, PASSWORD, target_temp=4, temp_margin=1, peers=[jid for jid in jid_list if jid != fridge_jid])
    washingmachine = WashingMachine(whashing_machine_jid, PASSWORD, peers=[jid for jid in jid_list if jid != whashing_machine_jid])
    dish_washer = DishWasher(dish_washer_jid, PASSWORD, peers=[jid for jid in jid_list if jid != dish_washer_jid])
    
    world_agent = WorldAgent(AGENTS["world"], PASSWORD, season="summer", receivers=jid_list)

    # Start all agents (devices first, then world broadcaster)
    await ac_livingroom.start(auto_register=True)
    await fridge.start(auto_register=True)
    await washingmachine.start(auto_register=True)
    await dish_washer.start(auto_register=True)
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
        await washingmachine.stop()
        await dish_washer.stop()

if __name__ == "__main__":
    asyncio.run(main())