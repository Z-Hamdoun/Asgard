from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import time
import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # On n'a pas besoin de se connecter réellement, 
        # l'OS nous donne l'IP qui sortirait vers cette adresse
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip



app = FastAPI()

# 1. On "monte" le dossier static pour qu'il soit accessible via /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. On configure le moteur de templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    local_ip = get_local_ip()
    return templates.TemplateResponse(
        request=request, 
        name="index.html",
        context={"local_ip": local_ip}
    )



class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # On reçoit le "Pong" de la RPi ou du navigateur
            data = await websocket.receive_json()
            # On renvoie l'info à tout le monde (pour que l'interface HTML voit le résultat)
            await manager.broadcast(data)
    except:
        manager.disconnect(websocket)