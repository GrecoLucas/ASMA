import json
from spade.message import Message
from agents.device_base import Device
from config import MINUTES_PER_STEP
from spade.template import Template
from config import AGENTS
        

class BatteryAgent(Device):
    def __init__(self, jid, password, capacity_kwh=20.0, max_power_kw=20.0, peers=None):
        super().__init__(jid, password, device_type="battery", peers=peers)
        self.capacity_kwh = capacity_kwh
        self.max_power_kw = max_power_kw
        self.charge_kwh = capacity_kwh / 2.0  # Começa com 50%
        self.current_discharge_kw = 0.0
        self.current_charge_kw = 0.0
        self.current_hour = 0

    def update_sensors(self, world_state):
       self.current_hour = world_state.get("hour", 0)
       self.solar_production = world_state.get("solar_production", 0.0) # Captura o sol

    def get_power_consumption_kw(self):
        # Se a bateria extrai do painel solar, isso conta como "consumo" do ponto de vista do World. 
        # (O World injecta o Solar_Production total, então a bateria precisa "consumir" essa parcela).
        # E se a bateria está a descarregar, ela "produz" energia para o World.
        return getattr(self, "solar_to_battery", 0.0) - self.current_discharge_kw

    def get_provided_power_kw(self):
        return self.current_discharge_kw

    def update_energy_counters(self, world_state):
        self.current_charge_kw = 0.0 # Nunca carrega da rede (Grid = 0)
        self.current_discharge_kw = 0.0

        # Calculate total demand from other devices
        total_demand_kw = sum(p.get("power_kw", 0.0) for p in self.peer_power_status.values())

        # 1. Carregamento Solar (Only use excess solar)
        excess_solar_kw = max(0.0, self.solar_production - total_demand_kw)
        
        available_capacity_kwh = self.capacity_kwh - self.charge_kwh
        max_charge_power_kw = min(self.max_power_kw, available_capacity_kwh * (60.0 / MINUTES_PER_STEP))
        
        self.solar_to_battery = min(excess_solar_kw, max_charge_power_kw)

        # 2. Descarga baseada na demanda dos agentes
        available_kw = (self.charge_kwh * 60) / MINUTES_PER_STEP
        
        unmet_demand_kw = max(0.0, total_demand_kw - self.solar_production)
        
        if self.charge_kwh > 0 and unmet_demand_kw > 0.0:
            desired_discharge = min(unmet_demand_kw, self.max_power_kw)
            self.current_discharge_kw = min(desired_discharge, available_kw)
        else:
            self.current_discharge_kw = 0.0

        # Atualização física da carga
        net_flow = self.solar_to_battery - self.current_discharge_kw
        self.charge_kwh += net_flow * (MINUTES_PER_STEP / 60.0)
        self.charge_kwh = max(0.0, min(self.capacity_kwh, self.charge_kwh))

        super().update_energy_counters(world_state)

    def get_device_state_for_gui(self):
        solar_charging = getattr(self, "solar_to_battery", 0.0)
        return {
            "device_type": "battery",
            "battery_level": round((self.charge_kwh / self.capacity_kwh) * 100, 1),
            "capacity_kwh": self.capacity_kwh,
            "charge_kwh": round(self.charge_kwh, 3),
            "max_power_kw": self.max_power_kw,
            "status": "CHARGING with solar panels" if solar_charging > 0 else ("DISCHARGING" if self.current_discharge_kw > 0 else "IDLE"),
            "power_kw": round(self.current_charge_kw, 3), # Grid draw (0.0)
            "solar_charge_kw": round(solar_charging, 3),  # Solar draw
            "provided_power_kw": round(self.current_discharge_kw, 3),
            "priority": -100,
        }

    class BatteryP2P(Device.PeerCommunicationBehaviour):
        """Rotina P2P da bateria: armazena consumption dos peers e responde a requests com capacidade disponivel."""
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                try:
                    data = json.loads(msg.body)
                    if data.get("event") == "power_status":
                        device_name = data.get("device_name")
                        self.agent.peer_power_status[device_name] = {
                            "power_kw": data.get("power_kw", 0),
                            "timestamp": data.get("timestamp", 0)
                        }
                    elif data.get("event") == "power_request":
                        available_kw = (self.agent.charge_kwh * 60) / MINUTES_PER_STEP
                        can_provide = min(self.agent.max_power_kw, available_kw)
                        
                        reply = Message(to=str(msg.sender).split("/", 1)[0])
                        reply.set_metadata("ontology", "p2p")
                        reply.body = json.dumps({
                            "event": "power_reply",
                            "transaction_id": data.get("transaction_id"),
                            "decision": "accept",
                            "provided_power_kw": round(can_provide, 3),
                            "responder_priority": -100
                        })
                        await self.send(reply)
                except Exception as e:
                    import logging
                    logging.warning(f"[BatteryP2P] Error: {e}")

    async def setup(self):
        # Comportamento para ouvir o Mundo (horas)
        t_world = Template()
        t_world.sender = AGENTS["world"]
        self.add_behaviour(self.MonitorEnvironment(), t_world)

        # Comportamento para responder aos Peers
        t_p2p = Template()
        t_p2p.metadata = {"ontology": "p2p"}
        self.add_behaviour(self.BatteryP2P(), t_p2p)
