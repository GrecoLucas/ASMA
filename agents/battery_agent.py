import json
from spade.message import Message
from agents.device_base import Device
from config import MINUTES_PER_STEP

class BatteryAgent(Device):
    def __init__(self, jid, password, capacity_kwh=5.0, max_power_kw=20.0, peers=None):
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
        return self.current_charge_kw  # O que ela puxa da rede para carregar

    def get_provided_power_kw(self):
        return self.current_discharge_kw

    def update_energy_counters(self, world_state):
        h = self.current_hour
        self.current_charge_kw = 0.0 # Nunca carrega da rede (Grid = 0)
        self.current_discharge_kw = 0.0

        # 1. Carregamento Solar (ex: entre 7h e 12h se houver sol)
        if 7 <= h < 12 and self.solar_production > 0:
            self.solar_to_battery = min(self.solar_production * 2, self.max_power_kw)
        else:
            self.solar_to_battery = 0.0
        # 2. Descarga para a Casa (13h-18h)
        if 13 <= h < 18 and self.charge_kwh > 0:
            self.current_discharge_kw = self.max_power_kw
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
            "status": "CHARGING with solar panels" if solar_charging > 0 else ("DISCHARGING" if self.current_discharge_kw > 0 else "IDLE"),
            "power_kw": round(self.current_charge_kw, 3), # Grid draw (0.0)
            "solar_charge_kw": round(solar_charging, 3),  # Solar draw
            "provided_power_kw": round(self.current_discharge_kw, 3),
            "priority": -100,
        }

    class BatteryP2P(Device.PeerCommunicationBehaviour):
        """Versão simplificada: apenas responde quanta energia está a dar no momento"""
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                data = json.loads(msg.body)
                if data.get("event") == "power_request":
                    reply = Message(to=str(msg.sender).split("/", 1)[0])
                    reply.set_metadata("ontology", "p2p")
                    reply.body = json.dumps({
                        "event": "power_reply",
                        "transaction_id": data.get("transaction_id"),
                        "decision": "accept",
                        "provided_power_kw": round(self.agent.current_discharge_kw, 3),
                        "responder_priority": -100
                    })
                    await self.send(reply)

    async def setup(self):
        from spade.template import Template
        from config import AGENTS
        
        # Comportamento para ouvir o Mundo (horas)
        t_world = Template()
        t_world.sender = AGENTS["world"]
        self.add_behaviour(self.MonitorEnvironment(), t_world)

        # Comportamento para responder aos Peers
        t_p2p = Template()
        t_p2p.metadata = {"ontology": "p2p"}
        self.add_behaviour(self.BatteryP2P(), t_p2p)
