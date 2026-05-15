import os, sys, time, threading
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from class_Valkyrie import Valkyrie
from Communication.class_ESP32_Link import ESP32_Link
import pymavlink_code.code_de_gestion_de_missions as CGM

CONFIG_FILE = "Valkyrie/mission_config.json"

# Valeurs par défaut appliquées si un paramètre est absent ou null
CONFIG_DEFAULTS = {
    "alt_quadrillage":    5,
    "taille_quadrillage": 10,
    "pas_quadrillage":    2,
    "camera_resolution":  [848, 480],
    "square_pnp_size":    40,
    "taille_aruco":       [40, 10],
    "id_aruco":           [1, 1],
}

# ==============================================================================
# GESTION JSON
# ==============================================================================
def read_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def read_config_safe() -> dict:
    """Lit la config et substitue les valeurs par défaut pour les clés absentes ou nulles."""
    config = read_config()
    for key, default_val in CONFIG_DEFAULTS.items():
        if config.get(key) is None:
            config[key] = default_val
            print(f"[JSON] '{key}' manquant — valeur par défaut : {default_val}")
    return config

def update_config(new_data: dict):
    config = read_config()
    config.update(new_data)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"[JSON] Config Valkyrie mise à jour.")


# ==============================================================================
# MISSIONS
# ==============================================================================
def run_mission_1(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 1 : quadrillage spirale et atterrissage de précision sur ArUco."""
    if not drone.load_config(config):
        print("[MISSION 1] Configuration invalide. Abandon.")
        return

    if drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 1] Décollage OK.")
        if drone.executer_quadrillage():
            drone.precision_loiter_and_land()
    else:
        print("[MISSION 1] Échec du décollage.")


def run_mission_2(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 2 : à implémenter."""
    print("[MISSION 2] Non implémentée.")


def run_mission_3(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 3 : Valkyrie takeoff, Quadrillage spiral, Precision Land sur ArUco avec failsafes."""
    if not drone.load_config(config):
        print("[MISSION 3] Configuration invalide. Abandon.")
        return

    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 3] Échec du décollage.")
        return

    print("[MISSION 3] Décollage OK.")

    # Boucle requadrillage : on retente si la cible est perdue en LOITER
    while True:
        cible_trouvee = drone.executer_quadrillage()
        if not cible_trouvee:
            print("[MISSION 3] Quadrillage terminé sans trouver la cible.")
            return

        resultat = drone.precision_loiter_and_land()

        if resultat is True:
            print("[MISSION 3] Atterrissage de précision réussi.")
            return
        elif resultat is False:
            print("[MISSION 3] Mission interrompue (fin_mission).")
            return
        else:  # None --> cible perdue en LOITER --> requadrillage
            print("[MISSION 3] Cible perdue. Relance du quadrillage...")


def run_mission_4(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 4 : à implémenter."""
    print("[MISSION 4] Non implémentée.")


def run_mission_5(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 5 : à implémenter."""
    print("[MISSION 5] Non implémentée.")


_MISSION_RUNNERS = {
    1: run_mission_1,
    2: run_mission_2,
    3: run_mission_3,
    4: run_mission_4,
    5: run_mission_5,
}


def run_mission(drone: Valkyrie, esp32: ESP32_Link, num_mission: int):
    """Charge la config sécurisée et dispatche vers la bonne mission."""
    config = read_config_safe()
    runner = _MISSION_RUNNERS.get(num_mission, run_mission_1)
    print(f"[MISSION] Lancement mission {num_mission}...")
    runner(drone, esp32, config)
    print(f"[MISSION] Mission {num_mission} terminée. En attente du prochain ordre.")


# ==============================================================================
# BOUCLE PRINCIPALE (attente ordres ESP32 de Valhalla)
# ==============================================================================
def main_loop(drone: Valkyrie, esp32: ESP32_Link):
    """
    Boucle infinie d'écoute des messages ESP-NOW de Valhalla.
    - CFG:json      --> mise à jour de la config locale
    - CMD:START:N   --> lancement de la mission N
    """
    print("\n[MAIN] Valkyrie en attente d'ordres de Valhalla (ESP-NOW)...\n")

    while True:
        # Mise à jour de la configuration
        new_config = esp32.get_and_clear_config()
        if new_config:
            print("[MAIN] Config reçue de Valhalla. Sauvegarde...")
            update_config(new_config)

        # Ordre de lancement de mission
        num_mission = esp32.get_and_clear_mission_start()
        if num_mission is not None:
            run_mission(drone, esp32, num_mission)

        time.sleep(0.1)


# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================
if __name__ == "__main__":
    print("[MAIN] Connexion MAVLink à Valkyrie...")
    # drone = Valkyrie(address="/dev/ttyAMA0", target_system=2)  # REEL
    drone = Valkyrie(address="127.0.0.1:14560", target_system=2)  # SITL

    print("[MAIN] Connexion ESP32...")
    esp32 = ESP32_Link(port="/dev/ttyACM1", baudrate=115200, mock_simulation=True,
                       udp_rx_port=5002,
                       udp_tx_port=5001)
    esp32.connect()

    drone.set_esp32_link(esp32)

    main_loop(drone, esp32)
