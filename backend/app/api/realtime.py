"""
Real-time spray event notifications via WebSocket
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import asyncio

router = APIRouter()

# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.spray_events: List[Dict] = []  # Recent spray events

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

    def add_spray_event(self, event: dict):
        """Add a spray event and keep last 100"""
        self.spray_events.insert(0, event)
        self.spray_events = self.spray_events[:100]

manager = ConnectionManager()

# Only explicitly submitted reports can enter this in-memory feed.
@router.websocket('/ws/sprays')
async def websocket_endpoint(websocket:WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({'type':'connection_established','message':'User-submitted reports, not independently verified live spraying.','recent_events':manager.spray_events[:10]})
        while True:await websocket.receive_json()
    except WebSocketDisconnect:manager.disconnect(websocket)

@router.get('/spray-events/recent')
def get_recent_events(limit:int=Query(20,ge=1,le=100)):
    return {'count':len(manager.spray_events[:limit]),'events':manager.spray_events[:limit],'scope':'User-submitted, unverified reports. No confirmed live spraying feed.'}

@router.get('/spray-events/sites')
def get_spray_sites():return {'count':0,'sites':[],'status':'unavailable','scope':'No confirmed live spraying feed.'}

@router.post('/spray-events/simulate')
@router.post('/spray-events/report')
def unsupported_legacy_event():
    raise HTTPException(410,'The legacy random-event feed has been removed. Use the evidence-backed event workflow.')

async def spray_simulator():
    return  # Compatibility only; fabricated events are never generated.
