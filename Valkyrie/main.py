import os, sys, time, threading
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from class_Valkyrie import Valkyrie
from Communication.class_ESP32_Link import ESP32_Link
from Communication.class_GripperESP32 import GripperESP32
import pymavlink_code.code_de_gestion_de_missions as CGM

CONFIG_FILE = "Valkyrie/mission_config.json"

SIMU = True  # True = SITL, False = REEL

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
            print(f"[JSON] '{key}' manquant -- valeur par défaut : {default_val}")
    return config

def update_config(new_data: dict):
    config = read_config()
    config.update(new_data)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"[JSON] Config Valkyrie mise à jour.")


# ==============================================================================
# FAILSAFE ESP32
# ==============================================================================
def check_esp32_or_rtl(esp32: ESP32_Link, drone) -> bool:
    """
    À appeler avant toute opération qui dépend physiquement de l'ESP32
    (pince, follow mode, etc.). Si le watchdog a épuisé ses tentatives, déclenche RTL.
    Retourne False si RTL déclenché, True si ESP32 opérationnel.
    """
    if esp32.reconnect_exhausted.is_set():
        print("[FAILSAFE] ESP32 perdu irrémédiablement. RTL déclenché.")
        drone.return_to_launch()
        return False
    return True


# ==============================================================================
# MISSIONS
# ==============================================================================
def run_mission_1(drone: Valkyrie, esp32: ESP32_Link, config: dict,
                  gripper: "GripperESP32 | None" = None):
    """
    Mission 1 complète :
      1. Décollage + quadrillage spirale
      2. Precision land avec alignement yaw (nez/pince vers la cible)
      3. Fermeture pince -- si saisie échoue --> réouverture + nouvelle tentative
      4. Décollage avec objet saisi --> FOLLOW mode vers Valhalla (2m au-dessus)
      5. Centrage PnP sur les 4 marqueurs de Valhalla
      6. Ouverture pince (lâcher) --> RTL
    """
    _MAX_GRIP_RETRIES = 3

    if not drone.load_config(config):
        print("[MISSION 1] Configuration invalide. Abandon.")
        return

    # --- Phase 1 : Décollage ---
    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 1] Échec du décollage.")
        return
    print("[MISSION 1] Décollage OK.")

    # --- Phase 2 : Quadrillage + precision land avec pince ---
    # Boucle requadrillage : recommence si cible perdue en LOITER
    # Boucle saisie : recommence si la pince ne saisit pas l'objet
    objet_saisi = False
    for tentative in range(_MAX_GRIP_RETRIES):
        print(f"[MISSION 1] Tentative precision land {tentative + 1}/{_MAX_GRIP_RETRIES}")

        # Quadrillage (toujours sur la 1ère tentative ; retentatives recommencent au début)
        while True:
            cible_trouvee = drone.executer_quadrillage()
            if not cible_trouvee:
                print("[MISSION 1] Quadrillage terminé sans trouver la cible.")
                drone.send_cgm(CGM.VALKYRIE_NO_TARGET_FOUND)
                return

            # Precision loiter + alignement yaw + LAND
            resultat = drone.precision_loiter_and_land_gripper()

            if resultat is False:
                print("[MISSION 1] Mission interrompue (urgence).")
                return
            if resultat is True:
                break  # atterri --> passer à la pince
            # None : cible perdue en LOITER --> requadrillage
            print("[MISSION 1] Cible perdue. Requadrillage...")

        # Atterri, moteurs coupés -- tenter la saisie
        if gripper is None:
            # Pince indisponible : on simule la saisie et on continue la mission
            print("[MISSION 1] Pince non connectée. Simulation de saisie -- mission continue.")
            objet_saisi = True
            break

        print("[MISSION 1] Atterri. Fermeture de la pince...")
        caught = gripper.close_gripper()

        if caught:
            print("[MISSION 1] Objet saisi avec succès !")
            drone.send_cgm(CGM.VALKYRIE_GRIP_OK)
            objet_saisi = True
            break

        print(f"[MISSION 1] Saisie échouée (tentative {tentative + 1}). Réouverture...")
        gripper.open_gripper()

        if tentative < _MAX_GRIP_RETRIES - 1:
            if not drone.takeoff_autonome(config["alt_quadrillage"]):
                print("[MISSION 1] Échec redécollage pour nouvelle tentative.")
                return

    if not objet_saisi:
        print(f"[MISSION 1] Objet non saisi après {_MAX_GRIP_RETRIES} tentatives. Abandon.")
        drone.send_cgm(CGM.VALKYRIE_NO_TARGET_FOUND)
        return

    # --- Phase 3 : Redécollage avec l'objet ---
    print("[MISSION 1] Redécollage avec objet saisi...")
    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 1] Échec redécollage avec objet. Lâcher et abandon.")
        if gripper is not None:
            gripper.open_gripper()
        return

    # --- Phase 4 : FOLLOW mode --> approche Valhalla (2m au-dessus) ---
    print("[MISSION 1] Passage en FOLLOW --> approche de Valhalla...")
    if not drone.approach_valhalla_follow(timeout=120.0):
        print("[MISSION 1] Approche FOLLOW échouée. Lâcher et RTL.")
        if gripper is not None:
            gripper.open_gripper()
        drone.return_to_launch()
        return

    # --- Phase 5 : Centrage PnP sur les 4 coins de Valhalla ---
    print("[MISSION 1] Centrage PnP sur Valhalla...")
    centrage_ok = drone.pnp_center_over_valhalla(timeout=60.0)
    if not centrage_ok:
        print("[MISSION 1] Centrage PnP timeout -- lâcher quand même.")

    # --- Phase 6 : Lâcher l'objet ---
    print("[MISSION 1] Ouverture pince --> lâcher de l'objet.")
    if gripper is not None:
        gripper.open_gripper()

    # --- Phase 7 : RTL ---
    drone.send_cgm(CGM.VALKYRIE_LANDED)
    print("[MISSION 1] Objet livré à Valhalla. RTL Valkyrie.")
    drone.return_to_launch()


def run_mission_2(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 2 : à implémenter."""
    print("[MISSION 2] Non implémentée.")


def run_mission_3(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 3 : quadrillage spiral + Precision Land e-ArUco (inner/outer)."""
    if not drone.load_config(config):
        print("[MISSION 3] Configuration invalide. Abandon.")
        return

    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 3] Échec du décollage.")
        return

    print("[MISSION 3] Décollage OK.")

    # Boucle requadrillage : on retente si la cible est perdue en LOITER
    while True:
        cible_trouvee = drone.executer_quadrillage(e_analyse=True)
        if not cible_trouvee:
            print("[MISSION 3] Quadrillage terminé sans trouver la cible.")
            drone.send_cgm(CGM.VALKYRIE_NO_TARGET_FOUND)
            return

        resultat = drone.precision_loiter_and_land(e_analyse=True)

        if resultat is True:
            print("[MISSION 3] Atterrissage de précision réussi.")
            drone.send_cgm(CGM.VALKYRIE_LANDED)
            return
        elif resultat is False:
            print("[MISSION 3] Mission interrompue (fin_mission).")
            return  # GCS a déclenché l'arrêt, pas besoin de CGM
        else:  # None --> cible perdue en LOITER --> requadrillage
            print("[MISSION 3] Cible perdue. Relance du quadrillage...")


def run_mission_4(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 4 : à implémenter."""
    if not drone.load_config(config):
        print("[MISSION 3] Configuration invalide. Abandon.")
        return

    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 3] Échec du décollage.")
        return

    print("[MISSION 3] Décollage OK.")

    # Boucle requadrillage : on retente si la cible est perdue en LOITER
    while True:
        cible_trouvee = drone.executer_quadrillage(e_analyse=True)
        if not cible_trouvee:
            print("[MISSION 4] Quadrillage terminé sans trouver la cible.")
            drone.send_cgm(CGM.VALKYRIE_NO_TARGET_FOUND)
            return

        resultat = drone.precision_loiter_and_land_gripper(e_analyse=True)

        if resultat is True:
            print("[MISSION 3] Atterrissage de précision réussi.")
            drone.send_cgm(CGM.VALKYRIE_LANDED)
            return
        elif resultat is False:
            print("[MISSION 4] Mission interrompue (fin_mission).")
            return  # GCS a déclenché l'arrêt, pas besoin de CGM
        else:  # None --> cible perdue en LOITER --> requadrillage
            print("[MISSION 4] Cible perdue. Relance du quadrillage...")


def run_mission_5(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 5 : FOLLOW mode -- Valkyrie suit Valhalla à 2m au-dessus."""
    if not drone.follow_valhalla():
        print("[MISSION 5] FOLLOW échoué ou GPS Valhalla perdu.")


_MISSION_RUNNERS = {
    1: run_mission_1,
    2: run_mission_2,
    3: run_mission_3,
    4: run_mission_4,
    5: run_mission_5,
}


def run_mission(drone: Valkyrie, esp32: ESP32_Link, num_mission: int,
                gripper: "GripperESP32 | None" = None):
    """Charge la config sécurisée et dispatche vers la bonne mission."""
    config = read_config_safe()
    runner = _MISSION_RUNNERS.get(num_mission, run_mission_1)
    print(f"[MISSION] Lancement mission {num_mission}...")
    # run_mission_1 accepte gripper ; les autres non (signature générique)
    if num_mission == 1:
        runner(drone, esp32, config, gripper)
    else:
        runner(drone, esp32, config)

    # Si une urgence a coupé la mission, attendre l'atterrissage puis réinitialiser
    if drone.fin_mission:
        print("[MISSION] Urgence détectée -- attente désarmement Valkyrie...")
        drone.fin_mission = False
        drone.allow_actions = True
        drone.wait_motors_disarmed(timeout=120.0)
        print("[MISSION] Valkyrie désarmé. Retour à l'attente de mission.")

    print(f"[MISSION] Mission {num_mission} terminée. En attente du prochain ordre.")
    drone.send_cgm(CGM.VALKYRIE_WAITING_MISSION)


# ==============================================================================
# BOUCLE PRINCIPALE (attente ordres ESP32 de Valhalla)
# ==============================================================================
def main_loop(drone: Valkyrie, esp32: ESP32_Link, gripper: GripperESP32 | None = None):
    """
    Boucle infinie d'écoute des messages ESP-NOW de Valhalla.
    - CFG:json      --> mise à jour de la config locale
    - CMD:START:N   --> lancement de la mission N
    Les urgences (CGM 213/214) sont gérées par les callbacks ESP32 enregistrés dans __main__.
    """
    print("\n[MAIN] Valkyrie en attente d'ordres de Valhalla (ESP-NOW)...\n")
    drone.send_cgm(CGM.VALKYRIE_WAITING_MISSION)

    while True:
        # Nettoyage post-urgence si déclenchée hors mission
        if drone.fin_mission:
            print("[MAIN] fin_mission hors mission -- attente désarmement...")
            drone.fin_mission = False
            drone.allow_actions = True
            drone.wait_motors_disarmed(timeout=120.0)
            print("[MAIN] Valkyrie désarmé. Retour à l'attente.")
            drone.send_cgm(CGM.VALKYRIE_WAITING_MISSION)

        # Mise à jour de la configuration
        new_config = esp32.get_and_clear_config()
        if new_config:
            print("[MAIN] Config reçue de Valhalla. Sauvegarde...")
            update_config(new_config)

        # Ordre de lancement de mission
        num_mission = esp32.get_and_clear_mission_start()
        if num_mission is not None:
            run_mission(drone, esp32, num_mission, gripper)

        # Ping-pong ESP32 : réponse automatique
        cgm_recu = esp32.get_and_clear_cgm()
        if cgm_recu == CGM.ESP32_PING.value:
            print("[MAIN] ESP32_PING reçu. Envoi du PONG...")
            esp32.send_cgm(CGM.ESP32_PONG.value)

        # Commandes manuelles pince depuis le Dashboard
        elif cgm_recu == CGM.PC_CALIB_GRIPPER_VALKYRIE.value:
            print("[MAIN] Calibration de la pince...")
            if gripper is not None:
                gripper.calibrate()
            else:
                print("[MAIN] Pince non connectée.")

        elif cgm_recu == CGM.PC_OPEN_GRIPPER_VALKYRIE.value:
            print("[MAIN] Ouverture manuelle de la pince...")
            if gripper is not None:
                gripper.open_gripper()
            else:
                print("[MAIN] Pince non connectée.")

        elif cgm_recu == CGM.PC_CLOSE_GRIPPER_VALKYRIE.value:
            print("[MAIN] Fermeture manuelle de la pince...")
            if gripper is not None:
                caught = gripper.close_gripper()
                print(f"[MAIN] Résultat fermeture pince : {'SAISIE OK' if caught else 'RIEN SAISI'}")
            else:
                print("[MAIN] Pince non connectée.")

        time.sleep(0.1)


# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================
if __name__ == "__main__":
    print("[MAIN] Connexion MAVLink à Valkyrie...")
    if SIMU:
        drone = Valkyrie(address="127.0.0.1:14560", target_system=2)
    else:
        drone = Valkyrie(address="/dev/ttyAMA0", target_system=2, baud=921600)

    print("[MAIN] Connexion ESP32...")
    esp32 = ESP32_Link(port="/dev/ttyACM0", baudrate=115200, mock_simulation=SIMU,
                       udp_rx_port=5002, udp_tx_port=5001)
    while not esp32.connect():
        print("[MAIN] ESP32 non disponible. Retry dans 5s...")
        drone.send_cgm(CGM.VALKYRIE_ESP32_FAIL)
        time.sleep(5)
    print("[MAIN] ESP32 connecté.")

    esp32.set_fail_callback(lambda _: drone.send_cgm(CGM.VALKYRIE_ESP32_FAIL))

    # Callbacks d'urgence -- déclenchés immédiatement par le thread ESP32, sans polling
    def _on_emergency_stop():
        print("[URGENCE] Désarmement forcé Valkyrie !")
        drone.disarm(force=True)
        drone.fin_mission = True

    def _on_emergency_landing():
        print("[URGENCE] Atterrissage d'urgence Valkyrie !")
        drone.return_to_launch()
        drone.fin_mission = True

    esp32.register_emergency_cgm(CGM.PC_A_DISARM_FORCE_VALKYRIE.value, _on_emergency_stop)
    esp32.register_emergency_cgm(CGM.PC_URGENCY_LANDING_VALKYRIE.value, _on_emergency_landing)

    drone.set_esp32_link(esp32)

    gripper = GripperESP32(port="/dev/ttyACM1")
    if not gripper.connect():
        print("[MAIN] Pince non connectée -- fonctions pince désactivées.")
        gripper = None

    main_loop(drone, esp32, gripper)
