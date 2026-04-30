# --- IMPORTS ---
import asyncio
import websockets
import json
import sys
import subprocess
import json_config
import json_coords
import importlib.metadata
import os


# --- FONCTIONS UTILITAIRES WEBSOCKET ---
def sendfail(socket, failure, e):
    response = {"type": "status", "command": failure, "source": "Valkyrie", "output": e}
    return socket.send(json.dumps(response))


def sendack(socket, ack):
    response = {"type": "status", "command": ack, "source": "Valkyrie"}
    return socket.send(json.dumps(response))


def senddata(socket, command, data):
    response = {"type": "log", "command": command, "source": "Valkyrie", "data": data}
    return socket.send(json.dumps(response))


def sendlog(socket, command, result):
    response = {
        "type": "log",
        "command": command,
        "source": "Valkyrie",
        "output": result,
    }
    return socket.send(json.dumps(response))


# --- GESTION DE LA MISSION EN ARRIERE-PLAN ---
async def run_mission(websocket, command_str):
    """Exécute la mission sans bloquer la lecture du WebSocket."""
    try:
        process = await asyncio.create_subprocess_shell(
            command_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            executable="/bin/bash",
        )

        # On stocke le process dans l'objet websocket pour y accéder ailleurs
        websocket.current_process = process
        print(f"--- exécution de main (PID: {process.pid}) ---")
        await sendack(websocket, "start_main_ack")

        # Lecture asynchrone des lignes
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            clean_line = line.decode().strip()
            if clean_line:
                await sendlog(websocket, "main_log", clean_line)
                print(clean_line)

        return_code = await process.wait()
        if return_code != 0:
            await sendfail(websocket, "main_fail", return_code)
            print(f"--- Terminé avec erreur {return_code} ---")

    except Exception as e:
        print(f"Erreur mission: {e}")
    finally:
        websocket.current_process = None


async def check_requirements(websocket, requirements_path="requirements.txt"):
    if not os.path.exists(requirements_path):
        print(f"Fichier {requirements_path} introuvable.")
        await sendfail(websocket, "check_valk_fail", "requirements.txt introuvable")

    with open(requirements_path, "r") as f:
        dependencies = [
            line.split("==")[0].split(">=")[0].strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

    missing = []
    for auth in dependencies:
        try:
            importlib.metadata.version(auth)
        except importlib.metadata.PackageNotFoundError:
            missing.append(auth)

    if missing:
        print(f"Erreur de dépendance. Manquant(s) : {', '.join(missing)}")
        await sendfail(
            websocket,
            "check_fail",
            f"Manquant(s) : {', '.join(missing)}",
        )
    else:
        print("Toutes les dépendances sont présentes et à jour.")
        await sendack(websocket, "check_ack")


# --- BOUCLE PRINCIPALE DU CLIENT ---
async def responder(ip_ordi):
    uri = f"ws://{ip_ordi}:8000/ws/Valkyrie"

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print(f"Connecté à {ip_ordi}")
                websocket.current_process = None  # Initialisation

                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    # 1. Gestion du PING
                    if data.get("type") == "ping":
                        sent_at = data.get("sent_at")
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "pong",
                                    "source": "Valkyrie",
                                    "sent_at": sent_at,
                                }
                            )
                        )

                    # 2. Gestion des commandes de la console
                    elif data.get("command") == "terminal_log":
                        print(data.get("output"))

                    # 3. Lancement de la MISSION
                    elif data.get("command") == "main_mission":
                        if websocket.current_process is not None:
                            print("Mission déjà en cours.")
                            await sendack(websocket, "already_mission")
                        else:
                            cmd = (
                                "source /rootgit/venv/bin/activate && "
                                "cd ~/Desktop/mission/dassault-helics-2026 && "
                                "python -u main.py"
                            )
                            # On lance la mission en tâche de fond (non-bloquant)
                            asyncio.create_task(run_mission(websocket, cmd))

                    # 4. Commande d'arrêt d'urgence
                    elif data.get("command") == "urgency_stop":
                        if websocket.current_process:
                            websocket.current_process.terminate()
                            print("Processus stoppé proprement.")
                            await sendack(websocket, "stop_ack")
                        else:
                            print("Aucun processus en cours.")
                            await sendack(websocket, "no_process")

                    # 5. Gestion des Logs
                    elif (
                        data.get("command") == "print_log"
                        and data.get("target") == "Valkyrie"
                    ):
                        print("envoi des logs")
                        f = open("log_test_valk.txt")
                        log_txt = f.read()
                        f.close()
                        await sendlog(websocket, "log_ack", log_txt)

                    # 6. Gestion des Configurations
                    elif data.get("command") == "update_config":
                        print("Nouvelle configuration reçue depuis l'interface web.")
                        nouveaux_parametres = data.get("data")
                        if nouveaux_parametres:
                            json_config.sauvegarder_config(nouveaux_parametres)
                            await sendack(websocket, "param_ack")
                    elif data.get("command") == "ask_config":
                        print("Requette de configuration vers l'interface web.")
                        parametres = json_config.charger_config()
                        await senddata(websocket, "ask_ack", parametres)
                    # 6.5 Gestion des Config de coordonnées
                    elif data.get("command") == "update_coords":
                        print("Nouvelle coordonnées reçue depuis l'interface web.")
                        nouveaux_parametres = data.get("data")
                        if nouveaux_parametres:
                            json_coords.sauvegarder_config(nouveaux_parametres)
                            await sendack(websocket, "coords_ack")
                    elif data.get("command") == "ask_coords":
                        print("Requette de configuration vers l'interface web.")
                        parametres = json_coords.charger_config()
                        await senddata(websocket, "ask_coords_ack", parametres)

                    # 7. GIT PULL
                    elif (
                        data.get("command") == "git_pull"
                        and data.get("target") == "Valkyrie"
                    ):
                        # (Ton code git pull peut rester ici ou passer en asynchrone aussi)
                        try:
                            repo_path = (
                                "/home/helics/Desktop/mission/dassault-helics-2026"
                            )
                            result = subprocess.check_output(
                                ["git", "pull"], cwd=repo_path
                            ).decode("utf-8")
                            print(result)
                            await sendlog(websocket, "pull_ack", result)
                        except Exception as e:
                            await sendfail(websocket, "pull_fail", str(e))

                    # 8. Check valkyrie
                    elif data.get("command") == "check_V":
                        asyncio.create_task(check_requirements(websocket))

        except Exception as e:
            print(f"Déconnecté. Nouvelle tentative dans 1s... ({e})")
            await asyncio.sleep(1)


# --- POINT D'ENTREE ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    asyncio.run(responder(sys.argv[1]))
