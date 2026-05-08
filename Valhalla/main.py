import os
import asyncio
import websockets
import json
import sys
import subprocess
from class_Valhalla import Valhalla

CONFIG_FILE = "mission_config.json"

def read_config():
    """Lit le fichier JSON unique. S'il n'existe pas, renvoie un dico vide."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def update_config(new_data):
    """Met à jour le fichier JSON avec de nouvelles données"""
    config = read_config()
    config.update(new_data) # Ajoute ou écrase les valeurs existantes
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"[JSON] Fichier mis à jour avec : {new_data}")

# --- FONCTIONS UTILITAIRES WEBSOCKET ---
def sendfail(socket, failure, e):
    response = {"type": "status", "command": failure, "source": "Valhalla", "output": e}
    return socket.send(json.dumps(response))


def sendack(socket, ack):
    response = {"type": "status", "command": ack, "source": "Valhalla"}
    return socket.send(json.dumps(response))


def sendlog(socket, command, result):
    response = {
        "type": "log",
        "command": command,
        "source": "Valhalla",
        "output": result,
    }
    return socket.send(json.dumps(response))


# --- BOUCLE PRINCIPALE DU CLIENT ---
async def wait_for_mission_start(ip_ordi):
    uri = f"ws://{ip_ordi}:8000/ws/Valhalla"

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print(f"Connecté à {ip_ordi}")
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    # Gestion du PING
                    if data.get("type") == "ping":
                        sent_at = data.get("sent_at")
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "pong",
                                    "source": "Valhalla",
                                    "sent_at": sent_at,
                                }
                            )
                        )

                    # Gestion des Logs
                    elif (
                        data.get("command") == "print_log"
                        and data.get("target") == "Valhalla"
                    ):
                        print("envoi des logs")
                        f = open("log_test_valh.txt")
                        log_txt = f.read()
                        f.close()
                        await sendlog(websocket, "log_ack", log_txt)
                    # GIT PULL
                    elif (
                        data.get("command") == "git_pull"
                        and data.get("target") == "Valhalla"
                    ):
                        try:
                            repo_path = "/home/asgard/Desktop/dassault-helics-2026"
                            result = subprocess.check_output(
                                ["git", "pull"], cwd=repo_path
                            ).decode("utf-8")
                            await sendlog(websocket, "pull_ack", result)
                        except Exception as e:
                            await sendfail(websocket, "pull_fail", str(e))

                    # Gestion des Configurations
                    elif data.get("command") in ["update_config", "update_coords"]:
                        print("[WIFI] Nouvelles données reçues depuis l'interface web.")
                        nouveaux_parametres = data.get("data")
                        if nouveaux_parametres:
                            update_config(nouveaux_parametres)
                            await sendack(websocket, "config_ack")

                    # Declancher la mission
                    elif data.get("command") == "main_mission":
                        await sendack(websocket, "mission_starting")
                        
                        return 

        except Exception as e:
            print(f"Déconnecté. Nouvelle tentative dans 1s... ({e})")
            await asyncio.sleep(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <IP_PC>")
        sys.exit(1)
        
    ip_ordi = sys.argv[1]

    # ---------------------------------------------------------
    # Préparation et Wifi
    # Le script va bloquer ici indéfiniment jusqu'au clic sur Démarrer
    # ---------------------------------------------------------
    asyncio.run(wait_for_mission_start(ip_ordi))

    # ---------------------------------------------------------
    # Exécution de la Mission de Vol
    # On arrive ici uniquement apres avoir choisi la mission sur le site
    # ---------------------------------------------------------
    print("[MISSION] Lecture du fichier de configuration...")
    config = read_config()
    
    lat = config.get("lat_mission")
    lng = config.get("lng_mission")
    alt = config.get("alt_quadrillage", 15) # 15m par défaut si non spécifié
    
    if lat is None or lng is None:
        print("[ERREUR CRITIQUE] Aucune coordonnée GPS dans le fichier de config ! Arrêt.")
        sys.exit(1)
        
    print(f"[MISSION] Cible chargée -> Lat: {lat}, Lng: {lng}, Alt: {alt}m")
    
    # ---------------------------------------------------------
    # Lancement de la mission
    # ---------------------------------------------------------
    print("[MISSION] Initialisation de Valhalla ...")
    valhalla = Valhalla(address="/dev/ttyAMA0", target_system=1)
    
    if valhalla.takeoff_pc(altitude=15):
        print(f"[MISSION] Départ vers {lat}, {lng}...")
        valhalla.goto(lat, lng, alt)
    else:
        print("[MISSION] Échec du décollage.")
        
    print("\n[MISSION] Programme terminé.")