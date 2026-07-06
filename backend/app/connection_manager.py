import asyncio
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps organization_id (str) to lists of asyncio.Queue instances
        self.active_connections: Dict[str, List[asyncio.Queue]] = {}

    def register(self, org_id: str) -> asyncio.Queue:
        if org_id not in self.active_connections:
            self.active_connections[org_id] = []
        queue = asyncio.Queue()
        self.active_connections[org_id].append(queue)
        logger.info(f"Registered SSE streaming client for Org: {org_id}. Total active: {len(self.active_connections[org_id])}")
        return queue

    def disconnect(self, org_id: str, queue: asyncio.Queue):
        if org_id in self.active_connections:
            if queue in self.active_connections[org_id]:
                self.active_connections[org_id].remove(queue)
            if not self.active_connections[org_id]:
                del self.active_connections[org_id]
        logger.info(f"Disconnected SSE streaming client for Org: {org_id}")

    def broadcast(self, org_id: str, event_type: str, data: dict):
        """
        Broadcasts a structured real-time event to all connected merchants under this organization.
        """
        if org_id in self.active_connections:
            payload = {
                "event": event_type,
                "data": data
            }
            # Put in queue of all listeners
            for queue in self.active_connections[org_id]:
                try:
                    queue.put_nowait(payload)
                except Exception as e:
                    logger.debug("Error delivering broadcast payload to connection queue: %s", str(e))

manager = ConnectionManager()
