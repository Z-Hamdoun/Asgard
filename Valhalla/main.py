import os, sys, threading, time
import asyncio
import websockets
import json
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from Communication.class_ESP32_Link import ESP32_Link
from class_Valhalla import Valhalla
import pymavlink_code.code_de_gestion_de_missions as CGM

CONFIG_FILE = "Valhalla/mission_config.json"


# Cet événement sera déclenché par un CGM Radio.
# Dès qu'il est déclenché le thread Wifi se suicide et le Thread Pilote décolle.
demarrage_mission_event = threading.Event()

# Liste des CGMs qui vont déclencher la mission et tuer le Wifi
LISTE_CGMS_DEMARRAGE = [
    CGM.PC_DEMANDE_TAKEOFF_VALHALLA,
]

# ==============================================================================
# GESTION JSON
# ==============================================================================
def read_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def update_config(new_data):
    config = read_config()
    config.update(new_data)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"[JSON] Fichier mis à jour avec : {new_data}")

async def sendfail(socket, failure, e):
    response = {"type": "status", "command": failure, "source": "Valhalla", "output": str(e)}
    return await socket.send(json.dumps(response))

async def sendack(socket, ack):
    response = {"type": "status", "command": ack, "source": "Valhalla"}
    return await socket.send(json.dumps(response))

async def sendlog(socket, command, result):
    response = {"type": "log", "command": command, "source": "Valhalla", "output": result}
    return await socket.send(json.dumps(response))


# ==============================================================================
# THREAD RELAIS (Valhalla -> GCS)
# ==============================================================================
def run_relais_thread(drone, esp_link):
    """
    Ce thread tourne en permanence sur Valhalla.
    Il écoute les messages de Valkyrie (ESP-NOW) et les transfert à la GCS (MAVLink).
    """
    print("[RELAIS] Thread de transfert ESP-NOW <-> MAVLink activé.")
    
    while True:
        cgm_recu_int = esp_link.get_and_clear_cgm()
        
        if cgm_recu_int is not None:
            objet_cgm = CGM.CGM.get(cgm_recu_int)
            
            if objet_cgm is not None and objet_cgm.name != "EMPTY":
                print(f"[RELAIS] Transfert du CGM {objet_cgm.name} ({cgm_recu_int}) vers la GCS (PC)...")
                drone.send_cgm(objet_cgm) 
            else:
                print(f"[RELAIS-ERREUR] Code CGM {cgm_recu_int} inconnu dans la bibliothèque locale !")
            
        time.sleep(0.1)

# ==============================================================================
# Thread wifi
# ==============================================================================
async def _fetch_config_async(ip_ordi: str, timeout_s: float = 60.0) -> bool:
    """
    Se connecte au Dashboard, attend une config ou des commandes,
    puis se déconnecte proprement.
    Retourne True si une config a bien été reçue.
    """
    uri = f"ws://{ip_ordi}:8000/ws/Valhalla"
    print(f"[WIFI] Connexion ponctuelle à {uri}...")
    config_received = False
    deadline = time.time() + timeout_s

    try:
        async with websockets.connect(uri, close_timeout=2) as ws:
            print("[WIFI] Connecté. En attente de la configuration...")
            # Signale au Dashboard que Valhalla est pret
            await ws.send(json.dumps({"type": "status", "command": "valhalla_ready", "source": "Valhalla"}))

            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(raw)
                    command = data.get("command")

                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong", "source": "Valhalla",
                                                   "sent_at": data.get("sent_at")}))

                    elif command in ("update_config", "update_coords"):
                        new_params = data.get("data", {})
                        if new_params:
                            update_config(new_params)
                            await ws.send(json.dumps({"type": "status", "command": "config_ack", "source": "Valhalla"}))
                            config_received = True
                            print("[WIFI] Config reçue. Déconnexion.")
                            break  # Config obtenue --> on sort

                    elif command == "git_pull":
                        try:
                            repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                            result = subprocess.check_output(["git", "pull"], cwd=repo_path).decode("utf-8")
                            await ws.send(json.dumps({"type": "log", "command": "pull_ack",
                                                      "source": "Valhalla", "output": result}))
                        except Exception as e:
                            await ws.send(json.dumps({"type": "status", "command": "pull_fail",
                                                      "source": "Valhalla", "output": str(e)}))

                    elif command == "disconnect":
                        print("[WIFI] Déconnexion demandée par le Dashboard.")
                        break

                except asyncio.TimeoutError:
                    pass  # Normal, on reboucle

    except Exception as e:
        print(f"[WIFI] Erreur de connexion : {e}")

    return config_received

def fetch_config_from_dashboard(ip_ordi: str, timeout_s: float = 60.0) -> bool:
    """Wrapper synchrone pour fetch_config_async."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_config_async(ip_ordi, timeout_s))
    finally:
        loop.close()

# ==============================================================================
# EXÉCUTION DE LA MISSION DE VOL
# ==============================================================================
def run_mission(drone: Valhalla, esp32: ESP32_Link):
    config = read_config()
    lat = config.get("lat_mission")
    lng = config.get("lng_mission")
    alt = config.get("alt_quadrillage", 5)

    if lat is None or lng is None:
        print("[MISSION] Aucune coordonnée GPS ! Configurez d'abord via CGM.")
        drone.send_cgm(CGM.VALHALLA_NO_TARGET_FOUND)
        return

    print(f"[MISSION] Cible -> Lat: {lat}, Lng: {lng}, Alt: {alt}m")
    drone.config = config

    if drone.takeoff_pc(altitude=3):
        print(f"[MISSION] Décollage OK. En route vers {lat}, {lng}...")
        if drone.execute_goto_from_config(radius_acceptance=2.0):
            print("[MISSION] Point atteint. Envoi config à Valkyrie...")
            esp32.send_config(config)
            time.sleep(1.0)
            print("[MISSION] Ordre décollage Valkyrie...")
            esp32.send_start_mission()
            drone.land_and_wait_valkyrie()
    else:
        print("[MISSION] Échec du décollage.")

    print("[MISSION] Mission terminée. Retour à la boucle d'attente.")

# ==============================================================================
# BOUCLE PRINCIPALE CGM
# ==============================================================================
def main_loop(drone: Valhalla, esp32: ESP32_Link, ip_ordi: str):
    """
    Boucle infinie d'écoute des CGMs radio.
    Chaque CGM déclenche une action puis retourne ici.
    """
    print("\n[MAIN] Boucle CGM active. En attente d'ordres radio...\n")

    while True:

        # --- Configurer Valhalla (connexion WiFi ponctuelle) ---
        if drone.check_cgm(CGM.PC_CONFIGURE_VALHALLA):
            drone.delete_cgm(CGM.PC_CONFIGURE_VALHALLA)
            print("[CGM] PC_CONFIGURE_VALHALLA reçu. Connexion WiFi...")
            success = fetch_config_from_dashboard(ip_ordi, timeout_s=60.0)
            if success:
                esp32.send_config(read_config())  # Relai immédiat vers Valkyrie
                drone.send_cgm(CGM.VALHALLA_CONFIG_OK)
                print("[CGM] Configuration OK. Retour à l'attente.")
            else:
                drone.send_cgm(CGM.VALHALLA_CONFIG_FAIL)
                print("[CGM] Échec configuration. Retour à l'attente.")

        # --- Lancer la mission ---
        elif drone.check_cgm(CGM.PC_DEMANDE_TAKEOFF_VALHALLA):
            drone.delete_cgm(CGM.PC_DEMANDE_TAKEOFF_VALHALLA)
            print("[CGM] PC_DEMANDE_TAKEOFF_VALHALLA reçu. Lancement mission...")
            run_mission(drone, esp32)

        # --- Arrêt d'urgence ---
        elif drone.check_cgm(CGM.PC_A_DISARM_FORCE_VALHALLA):
            drone.delete_cgm(CGM.PC_A_DISARM_FORCE_VALHALLA)
            print("[CGM] ARRÊT D'URGENCE reçu !")
            drone.disarm_force()

        time.sleep(0.1)


# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <IP_PC>")
        sys.exit(1)

    ip_ordi = sys.argv[1]

    print("[MAIN] Connexion MAVLink à Valhalla...")
    # valhalla = Valhalla(address="/dev/ttyAMA0", target_system=1)  # RÉEL
    valhalla = Valhalla(address="127.0.0.1:14550", target_system=1)  # SITL

    print("[MAIN] Connexion ESP32...")
    esp32 = ESP32_Link(port="/dev/ttyACM0", baudrate=115200, mock_simulation=True,
                       udp_rx_port=5001, udp_tx_port=5002)
    esp32.connect()

    # Thread relais permanent (daemon → meurt avec le process principal)
    threading.Thread(target=run_relais_thread, args=(valhalla, esp32), daemon=True).start()

    # Boucle principale (bloquante)
    main_loop(valhalla, esp32, ip_ordi)