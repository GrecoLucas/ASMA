"""
agents/base_agent.py – Common base class for all device agents.

Provides:
  • send_json()    – convenience wrapper around spade Message
  • log()          – prefixed print with agent name + hour
  • current_state  – dict populated when a STATE message arrives
"""

from __future__ import annotations
import json
import asyncio
import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message


class BaseDeviceAgent(Agent):
    """Shared scaffolding for Washing Machine, Heater, Battery, Solar Panel."""

    def __init__(self, jid: str, password: str, metrics, **kwargs):
        super().__init__(jid, password, **kwargs)
        self.metrics = metrics
        self.current_state: dict = {}    # filled by the latest STATE message
        self.agent_label = jid.split("@")[0]    # human-friendly name for logs

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def send_json(self, to_jid: str, data: dict, metadata: dict | None = None):
        """Build and send a SPADE message with a JSON body."""
        msg = Message(to=to_jid)
        msg.body = json.dumps(data)
        if metadata:
            for k, v in metadata.items():
                msg.set_metadata(k, v)

        # In this SPADE version, only behaviours expose send().
        loop = asyncio.get_running_loop()
        sent = loop.create_future()

        class _SendOnce(OneShotBehaviour):
            def __init__(self, outbound_msg: Message, done_future: asyncio.Future):
                super().__init__()
                self._outbound_msg = outbound_msg
                self._done_future = done_future

            async def run(self):
                try:
                    await self.send(self._outbound_msg)
                    if not self._done_future.done():
                        self._done_future.set_result(True)
                except Exception as exc:
                    if not self._done_future.done():
                        self._done_future.set_exception(exc)

        self.add_behaviour(_SendOnce(msg, sent))
        await sent

    async def broadcast_json(self, jids: list[str], data: dict, metadata: dict | None = None):
        """Send the same JSON message to several recipients."""
        for jid in jids:
            await self.send_json(jid, data, metadata)

    def log(self, msg: str):
        hour = self.current_state.get("hour", "?")
        if isinstance(hour, int):
            print(f"  [h{hour:02}] [{self.agent_label:<10}] {msg}")
        else:
            print(f"  [????] [{self.agent_label:<10}] {msg}")

    @staticmethod
    def parse(raw_message) -> dict | None:
        """Safely parse a SPADE message body as JSON."""
        if raw_message is None:
            return None
        try:
            return json.loads(raw_message.body)
        except (json.JSONDecodeError, AttributeError):
            return None
