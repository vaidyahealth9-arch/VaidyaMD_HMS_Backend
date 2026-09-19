"""
VaidyaMD HMS — WebSocket Connection Manager for Real-time Notifications
"""

import json
from typing import Dict, List
from fastapi import WebSocket
from uuid import UUID


class ConnectionManager:
    """Manages WebSocket connections per user for real-time notification push."""

    def __init__(self):
        # Map of user_id -> list of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a new WebSocket connection and register it for a user."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection for a user."""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: dict):
        """Send a JSON message to all connections of a specific user."""
        if user_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.append(connection)
            # Clean up dead connections
            for dead in dead_connections:
                self.active_connections[user_id].remove(dead)

    async def broadcast_to_role(self, role: str, tenant_id: str, message: dict, user_roles: dict):
        """
        Broadcast a message to all connected users with a specific role.
        user_roles: dict mapping user_id -> {role, tenant_id}
        """
        for user_id, info in user_roles.items():
            if info.get("role") == role and info.get("tenant_id") == tenant_id:
                await self.send_to_user(user_id, message)

    async def broadcast_all(self, message: dict):
        """Broadcast a message to ALL connected users."""
        for user_id in self.active_connections:
            await self.send_to_user(user_id, message)

    @property
    def connected_users_count(self) -> int:
        return len(self.active_connections)


# Singleton instance
ws_manager = ConnectionManager()

# Track connected users' roles for role-based broadcasting
connected_user_roles: Dict[str, dict] = {}
