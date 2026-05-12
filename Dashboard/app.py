from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from utils.class_GCS import GroundStation

import asyncio
import time
import socket


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


# --- INITIALISATION DE L'APPLICATION ---
app = FastAPI()
manager = ConnectionManager()
gcs = GroundStation(use_simu=False)

# 1. On "monte" le dossier static pour qu'il soit accessible via /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. On configure le moteur de templates
templates = Jinja2Templates(directory="templates")


# --- ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    local_ip = get_local_ip()
    return templates.TemplateResponse(
        request=request, name="index.html", context={"local_ip": local_ip}
    )


@app.get("/start-mission")
async def executer_python():
    try:
        # Lancement du script de manière asynchrone
        process = await asyncio.create_subprocess_exec(
            "python",
            "start_mission.py",  # Remplacez par le nom ou le chemin de votre script
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # On attend que le script termine et on récupère la sortie (stdout) et les erreurs (stderr)
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            # Succès : on renvoie ce que le script a affiché, en décodant les bytes en texte
            return {"statut": "succes", "resultat": stdout.decode("utf-8")}
        else:
            # Erreur lors de l'exécution du script
            return {"statut": "erreur", "message": stderr.decode("utf-8")}

    except Exception as e:
        # Erreur si le script est introuvable ou autre plantage serveur
        return {"statut": "erreur", "message": str(e)}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            command = data.get("command")
            target = data.get("target")

            # ======================================================
            # Routage radio mavlink
            # ======================================================
            if command == "main_mission":
                if target == "Valhalla":
                    gcs.lancer_mission()  # Envoi du CGM 201 par l'antenne
                await manager.send_to_target(
                    {"type": "status", "command": "mission_starting", "source": "GCS"},
                    "dashboard",
                )

            elif command == "urgency_stop":
                if target == "Valhalla":
                    gcs.arret_urgence()
                await manager.send_to_target(
                    {"type": "status", "command": "stopped", "source": "GCS"},
                    "dashboard",
                )

            elif command == "urgency_landing":
                if target == "Valhalla":
                    gcs.force_rtl()
                await manager.send_to_target(
                    {"type": "status", "command": "landing", "source": "GCS"},
                    "dashboard",
                )

            # ======================================================
            # routage wifi websocket
            # ======================================================
            else:
                if target and target in manager.active_connections:
                    # Pour update_config, update_coords, git_pull, etc.
                    await manager.send_to_target(data, target)
                else:
                    await manager.send_to_target(data, "dashboard")

    except WebSocketDisconnect:
        manager.disconnect(client_id)
