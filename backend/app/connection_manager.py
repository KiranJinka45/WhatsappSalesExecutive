import asyncio
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps organization_id (str) to lists of asyncio.Queue instances
        self.active_connections: Dict[str, List[asyncio.Queue]] = {}

    def register(self, org_id) -> asyncio.Queue:
        org_id_str = str(org_id)
        if org_id_str not in self.active_connections:
            self.active_connections[org_id_str] = []
        queue = asyncio.Queue()
        self.active_connections[org_id_str].append(queue)
        logger.info(f"Registered SSE streaming client for Org: {org_id_str}. Total active: {len(self.active_connections[org_id_str])}")
        return queue

    def disconnect(self, org_id, queue: asyncio.Queue):
        org_id_str = str(org_id)
        if org_id_str in self.active_connections:
            if queue in self.active_connections[org_id_str]:
                self.active_connections[org_id_str].remove(queue)
            if not self.active_connections[org_id_str]:
                del self.active_connections[org_id_str]
        logger.info(f"Disconnected SSE streaming client for Org: {org_id_str}")

    def broadcast(self, org_id, event_type: str, data: dict):
        """
        Broadcasts a structured real-time event to all connected merchants under this organization.
        """
        org_id_str = str(org_id)
        if org_id_str in self.active_connections:
            payload = {
                "event": event_type,
                "data": data
            }
            # Put in queue of all listeners
            for queue in self.active_connections[org_id_str]:
                try:
                    queue.put_nowait(payload)
                except Exception as e:
                    logger.debug("Error delivering broadcast payload to connection queue: %s", str(e))

manager = ConnectionManager()
