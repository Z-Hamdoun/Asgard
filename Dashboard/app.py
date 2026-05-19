from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

import sys, os, socket, asyncio

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, "../")))

from utils.class_GCS import GroundStation


# --- FONCTIONS UTILITAIRES ---
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # On n'a pas besoin de se connecter réellement,
        # l'OS nous donne l'IP qui sortirait vers cette adresse
        s.connect(("8.8.8.8", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# --- GESTIONNAIRE WEBSOCKET ---


class ConnectionManager:
    def __init__(self):
        # On utilise un dictionnaire pour associer un ID à une connexion
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"Connecté : {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"Déconnecté : {client_id}")

    async def send_to_target(self, message: dict, target_id: str):
        """Envoie un message à un destinataire spécifique."""
        websocket = self.active_connections.get(target_id)
        if websocket:
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """Envoie à tout le monde (Utile pour les notifications globales)."""
        for connection in self.active_connections.values():
            await connection.send_json(message)


# --- MONITORING CGM ---
async def _cgm_monitor():
    """Draine la queue CGM du GCS et pousse chaque événement vers le Dashboard."""
    try:
        while True:
            gcs = _gcs
            if gcs:
                try:
                    while True:
                        event = gcs.cgm_event_queue.get_nowait()
                        await manager.send_to_target(event, "dashboard")
                except Exception:
                    pass  # queue vide ou erreur d'envoi, on reboucle
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass  # arrêt propre demandé par le lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor_task = asyncio.create_task(_cgm_monitor())
    try:
        yield
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        if _gcs:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _gcs.close)


# --- INITIALISATION DE L'APPLICATION ---
app = FastAPI(lifespan=lifespan)
manager = ConnectionManager()

# GCS initialisé en lazy dans un thread — ne bloque pas l'event loop asyncio
_gcs: GroundStation | None = None

async def get_gcs() -> GroundStation | None:
    global _gcs
    if _gcs is not None:
        return _gcs
    try:
        loop = asyncio.get_event_loop()
        _gcs = await loop.run_in_executor(None, lambda: GroundStation(use_simu=False))
        print("[GCS] Connexion MAVLink établie.")
    except asyncio.CancelledError:
        raise  # laisse uvicorn gérer le shutdown proprement
    except Exception as e:
        print(f"[GCS] Impossible de se connecter : {e}")
        return None
    return _gcs

# Chemins absolus — fonctionne peu importe le répertoire de lancement d'uvicorn
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# --- ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    local_ip = get_local_ip()
    return templates.TemplateResponse(
        request=request, name="index.html", context={"local_ip": local_ip}
    )


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            command = data.get("command")
            target = data.get("target")

            # ======================================================
            # Messages venant de Valhalla (relais WebSocket → Dashboard)
            # ======================================================
            if client_id == "Valhalla":
                await manager.send_to_target(data, "dashboard")
                continue

            # ======================================================
            # Routage radio mavlink
            # ======================================================
            elif command == "main_mission":
                if target == "Valhalla":
                    gcs = await get_gcs()
                    if gcs:
                        num_mission = int(data.get("num_mission", 1))
                        gcs.lancer_mission(num_mission)
                await manager.send_to_target(
                    {"type": "status", "command": "mission_starting", "source": "GCS"},
                    "dashboard",
                )

            elif command == "urgency_stop":
                gcs = await get_gcs()
                if gcs:
                    gcs.arret_urgence()
                await manager.send_to_target(
                    {"type": "status", "command": "stopped", "source": "GCS"},
                    "dashboard",
                )

            elif command == "urgency_landing":
                gcs = await get_gcs()
                if gcs:
                    gcs.force_rtl()
                await manager.send_to_target(
                    {"type": "status", "command": "landing", "source": "GCS"},
                    "dashboard",
                )

            elif command == "co_V":
                if target == "Valhalla":
                    gcs = await get_gcs()
                    if gcs:
                        try:
                            gcs.connect_valhalla()
                            await manager.send_to_target(
                                {"type": "status", "command": "connecting_valhalla", "source": "GCS"},
                                "dashboard",
                            )
                        except Exception as e:
                            await manager.send_to_target(
                                {"type": "status", "command": "gcs_error", "source": "GCS", "output": str(e)},
                                "dashboard",
                            )
                    else:
                        await manager.send_to_target(
                            {"type": "status", "command": "gcs_unavailable", "source": "GCS"},
                            "dashboard",
                        )

            # ======================================================
            # Routage wifi websocket (update_config, git_pull, etc.)
            # ======================================================
            else:
                if target and target in manager.active_connections:
                    await manager.send_to_target(data, target)
                else:
                    await manager.send_to_target(data, "dashboard")

    except WebSocketDisconnect:
        manager.disconnect(client_id)
