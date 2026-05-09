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
# Thread wifi
# ==============================================================================
async def wait_for_mission_start(ip_ordi, esp32_link):
    uri = f"ws://{ip_ordi}:8000/ws/Valhalla"

    while not demarrage_mission_event.is_set():
        try:
            async with websockets.connect(uri, close_timeout=0.5) as websocket:
                print(f"[WIFI] Connecté à {ip_ordi}")
                
                while not demarrage_mission_event.is_set():
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                        data = json.loads(message)

                        if data.get("type") == "ping":
                            await websocket.send(json.dumps({"type": "pong", "source": "Valhalla", "sent_at": data.get("sent_at")}))

                        elif data.get("command") == "print_log" and data.get("target") == "Valhalla":
                            try:
                                with open("log_test_valh.txt", "r") as f:
                                    log_txt = f.read()
                                await sendlog(websocket, "log_ack", log_txt)
                            except Exception as e:
                                await sendfail(websocket, "log_fail", str(e))

                        elif data.get("command") == "git_pull" and data.get("target") == "Valhalla":
                            try:
                                repo_path = "/home/asgard/Desktop/dassault-helics-2026"
                                result = subprocess.check_output(["git", "pull"], cwd=repo_path).decode("utf-8")
                                await sendlog(websocket, "pull_ack", result)
                            except Exception as e:
                                await sendfail(websocket, "pull_fail", str(e))

                        elif data.get("command") in ["update_config", "update_coords"]:
                            nouveaux_parametres = data.get("data")
                            if nouveaux_parametres:
                                # Savgarde locale
                                update_config(nouveaux_parametres)
                                await sendack(websocket, "config_ack")
                                
                                # Relai vers valkyrie via esp32
                                esp32_link.send_config_json(nouveaux_parametres)
                                


                    except asyncio.TimeoutError:
                        pass 

        except Exception as e:
            if not demarrage_mission_event.is_set():
                print(f"[WIFI] Déconnecté. Nouvelle tentative dans 1s... ({e})")
                await asyncio.sleep(1)

def run_wifi_thread(ip_ordi, esp32_link):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(wait_for_mission_start(ip_ordi, esp32_link))
    loop.close()
    print("[WIFI] THREAD SITE WEB TERMINÉ ET DÉTRUIT. La Radio prend le relais ")

# ==============================================================================
# Thread Mission
# ==============================================================================
def run_pilot_thread(drone, esp32_link):
    print("[MISSION] Mission démarrée. En attente d'un CGM...")
    
    # boucle d'ecoute
    while not demarrage_mission_event.is_set():
        
        # Le pilote écoute la radio pour recevoir le feu vert de la GCS
        for cgm_declencheur in LISTE_CGMS_DEMARRAGE:
            if drone.check_cgm(cgm_declencheur):
                drone.delete_cgm(cgm_declencheur)
                print(f"\n[MISSION] CGM DE DÉMARRAGE REÇU VIA RADIO : {cgm_declencheur.name} !")
                
                esp32_link.send_start_mission() # Demande a valkyrie de se preparer!
                demarrage_mission_event.set() # tue le wifi !
                break
                
        time.sleep(0.1) 

    # ==========================================
    # EXÉCUTION DE LA MISSION DE VOL
    # ==========================================
    time.sleep(0.5) 
    
    print("\n[MISSION] DÉBUT DE LA MISSION AUTONOME.")
    config = read_config()
    lat = config.get("lat_mission")
    lng = config.get("lng_mission")
    alt = config.get("alt_quadrillage", 5)
    
    if lat is None or lng is None:
        print("[ERREUR] Aucune coordonnée GPS ! Avez-vous configuré le JSON ?")
        drone.send_cgm(CGM.VALHALLA_NO_TARGET_FOUND)
        return
        
    print(f"[MISSION] Cible chargée -> Lat: {lat}, Lng: {lng}, Alt: {alt}m")
    drone.config = config
    
    if drone.takeoff_pc(altitude=3):
        print(f"[MISSION] Départ vers {lat}, {lng}...")
        if drone.execute_goto_from_config(radius_acceptance=2.0):
            print("[PILOTE] Point atteint. Lancement de la procédure d'attente Valkyrie.")
            drone.land_and_wait_valkyrie()
    else:
        print("[MISSION] Échec du décollage.")
        
    print("\n[MISSION] MISSION TERMINÉE.")




if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <IP_PC>")
        sys.exit(1)
        
    ip_ordi = sys.argv[1]

    # Connexion au drone
    # valhalla = Valhalla(address="/dev/ttyAMA0", target_system=1) # REEL
    valhalla = Valhalla(address="127.0.0.1:14550", target_system=1) # SITL
    
    esp32 = ESP32_Link(port="/dev/ttyUSB0", baudrate=115200, mock_simulation=True)
    esp32.connect()
    
    thread_wifi = threading.Thread(target=run_wifi_thread, args=(ip_ordi, esp32))
    thread_pilote = threading.Thread(target=run_pilot_thread, args=(valhalla, esp32))
    
    thread_wifi.start()
    thread_pilote.start()
    
    thread_pilote.join()