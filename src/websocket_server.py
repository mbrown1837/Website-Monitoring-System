"""
WebSocket Server for Real-time Status Updates

This module provides WebSocket functionality for real-time status updates
of manual checks and queue processing.
"""

import json
import asyncio
import websockets
import threading
from datetime import datetime, timezone
from typing import Set, Dict, Any
from src.logger_setup import setup_logging
from src.config_loader import get_config

class WebSocketServer:
    def __init__(self, config_path=None):
        self.config = get_config(config_path=config_path) if config_path else get_config()
        self.logger = setup_logging(config_path=config_path) if config_path else setup_logging()
        
        # WebSocket connections
        self.connections: Set[websockets.WebSocketServerProtocol] = set()
        
        # Server configuration - force IPv4 to avoid port conflicts
        self.host = '0.0.0.0'  # Bind to all interfaces to avoid IPv6 conflicts
        self.port = self.config.get('websocket', {}).get('port', 8765)
        
        self.logger.info(f"WebSocket server configured for {self.host}:{self.port}")
    
    async def register_connection(self, websocket, path):
        """Register a new WebSocket connection."""
        self.connections.add(websocket)
        self.logger.info(f"📡 New WebSocket connection registered (total: {len(self.connections)})")
        
        try:
            # Send welcome message
            await websocket.send(json.dumps({
                'type': 'connection',
                'status': 'connected',
                'message': 'Connected to Website Monitor WebSocket',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }))
            
            # Keep connection alive
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(websocket, data)
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON received from WebSocket: {message}")
                except Exception as e:
                    self.logger.error(f"Error handling WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("WebSocket connection closed")
        finally:
            self.connections.discard(websocket)
            self.logger.info(f"📡 WebSocket connection removed (total: {len(self.connections)})")
    
    async def _handle_message(self, websocket, data):
        """Handle incoming WebSocket messages."""
        message_type = data.get('type')
        
        if message_type == 'ping':
            # Respond to ping with pong
            await websocket.send(json.dumps({
                'type': 'pong',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }))
        elif message_type == 'subscribe':
            # Subscribe to specific updates
            subscription = data.get('subscription', 'all')
            self.logger.info(f"WebSocket subscribed to: {subscription}")
        else:
            self.logger.warning(f"Unknown message type: {message_type}")
    
    async def broadcast_status_update(self, queue_id, status, message, data=None):
        """Broadcast a status update to all connected clients."""
        if not self.connections:
            return
        
        update_data = {
            'type': 'status_update',
            'queue_id': queue_id,
            'status': status,
            'message': message,
            'data': data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        message_json = json.dumps(update_data)
        disconnected = set()
        
        for websocket in self.connections.copy():
            try:
                await websocket.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(websocket)
            except Exception as e:
                self.logger.error(f"Error sending WebSocket message: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected connections
        self.connections -= disconnected
        if disconnected:
            self.logger.info(f"📡 Removed {len(disconnected)} disconnected WebSocket connections")
    
    async def broadcast_queue_update(self, queue_data):
        """Broadcast queue status update to all connected clients."""
        if not self.connections:
            return
        
        update_data = {
            'type': 'queue_update',
            'queue': queue_data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        message_json = json.dumps(update_data)
        disconnected = set()
        
        for websocket in self.connections.copy():
            try:
                await websocket.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(websocket)
            except Exception as e:
                self.logger.error(f"Error sending WebSocket queue update: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected connections
        self.connections -= disconnected
        if disconnected:
            self.logger.info(f"📡 Removed {len(disconnected)} disconnected WebSocket connections")
    
    async def start_server(self):
        """Start the WebSocket server."""
        port = self.port
        max_attempts = 10
        
        for attempt in range(max_attempts):
            try:
                self.logger.info(f"🚀 Starting WebSocket server on {self.host}:{port}")
                
                async with websockets.serve(self.register_connection, self.host, port):
                    self.logger.info(f"✅ WebSocket server running on ws://{self.host}:{port}")
                    await asyncio.Future()  # Run forever
                    
            except OSError as e:
                if "Address already in use" in str(e) or "10048" in str(e):
                    port += 1
                    self.logger.warning(f"Port {port-1} is already in use, trying port {port}")
                    if attempt < max_attempts - 1:
                        continue
                    else:
                        self.logger.error(f"Could not find an available port after {max_attempts} attempts")
                        raise
                else:
                    self.logger.error(f"Error starting WebSocket server: {e}")
                    raise
            except Exception as e:
                self.logger.error(f"Error starting WebSocket server: {e}")
                raise
    
    def start_server_thread(self):
        """Start the WebSocket server in a background thread."""
        def run_server():
            asyncio.set_event_loop(asyncio.new_event_loop())
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.start_server())
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        return thread

# Global WebSocket server instance
_websocket_server = None

def get_websocket_server(config_path=None):
    """Get the global WebSocket server instance."""
    global _websocket_server
    if _websocket_server is None:
        _websocket_server = WebSocketServer(config_path)
    return _websocket_server

def start_websocket_server(config_path=None):
    """Start the global WebSocket server."""
    server = get_websocket_server(config_path)
    return server.start_server_thread()

def get_websocket_url(config_path=None):
    """Get the WebSocket URL for client connections."""
    config = get_config(config_path=config_path) if config_path else get_config()
    host = config.get('websocket', {}).get('host', 'localhost')
    port = config.get('websocket', {}).get('port', 8765)
    
    # Try to find an available port if the default is in use
    import socket
    for test_port in range(port, port + 10):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, test_port))
                return f"ws://{host}:{test_port}"
        except OSError:
            continue
    
    # Fallback to default
    return f"ws://{host}:{port}"
