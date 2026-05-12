import os, sys, time, threading
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from class_Valkyrie import Valkyrie
from Communication.class_ESP32_Link import ESP32_Link

CONFIG_FILE = "Valkyrie/mission_config.json"

demarrage_valkyrie_event = threading.Event()

# ==============================================================================
# GESTION JSON LOCALE VALKYRIE
# ==============================================================================
def update_config(new_data):
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except json.JSONDecodeError:
            pass
            
    config.update(new_data)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"[JSON] Fichier Valkyrie mis à jour avec : {new_data}")

def read_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# ==============================================================================
# Thread ecoute de l ESP32
# ==============================================================================
def run_esp32_listener(esp_link):
    print("[LIEN ESP32] En attente de l'ordre ou de la config de Valhalla...")
    
    while not demarrage_valkyrie_event.is_set():
        
        # Vérification des nouvelles configurations
        new_config = esp_link.get_and_clear_config()
        if new_config:
            print("[LIEN ESP32] Configuration reçue du porteur ! Sauvegarde...")
            update_config(new_config)
            
        # Vérification de l'ordre de décollage
        cmd = esp_link.get_and_clear_command()
        if cmd == "START":
            print("\n[LIEN ESP32] ORDRE DE DÉMARRAGE REÇU DE VALHALLA !")
            demarrage_valkyrie_event.set()
            break
            
        time.sleep(0.1)

# ==============================================================================
# Thread mission
# ==============================================================================
def run_pilot_thread(drone, esp_link):
    print("[VALKYRIE] En attente du feu vert ESP-NOW...")
    
    # Bloque ici jusqu'à réception de "START"
    demarrage_valkyrie_event.wait() 
    
    time.sleep(0.5)
    print("\n[VALKYRIE] LANCEMENT MISSION.")
    
    # On lit le fichier JSON que l'autre thread a écrit grâce à l'ESP32
    config_dict = read_config()
    if not drone.load_config(config_dict):
        print("[PILOTE VALKYRIE] Erreur: Configuration invalide ou vide. Arrêt de la mission.")
        return
    
    
    if drone.takeoff_autonome(2):
        print(f"[VALKYRIE] Altitude de {2}m atteinte.")
        
        # Phase de Quadrillage sur la zone partagée par Valhalla !
        print("[VALKYRIE] Lancement du quadrillage...")
        if drone.executer_quadrillage():
            drone.precision_loiter_and_land()
    else:
        print("[VALKYRIE] Échec du décollage.")


# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================
if __name__ == "__main__":
    print("Connexion a Valkyrie...")
    
    drone = Valkyrie(address="127.0.0.1:14560", target_system=2) 
    
    # Mock=True 
    esp32 = ESP32_Link(port="/dev/ttyACM1", baudrate=115200, mock_simulation=True,
                       udp_rx_port=5002,
                       udp_tx_port=5001)
    esp32.connect() 
    
    thread_esp = threading.Thread(target=run_esp32_listener, args=(esp32,))
    thread_pilote = threading.Thread(target=run_pilot_thread, args=(drone, esp32))
    
    thread_esp.start()
    thread_pilote.start()
    
    thread_pilote.join()