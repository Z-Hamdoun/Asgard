import os, sys, time, threading
import queue as _queue
import asyncio
import websockets
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from class_Valkyrie import Valkyrie
from Communication.class_ESP32_Link import ESP32_Link
from Communication.class_GripperESP32 import GripperESP32
import pymavlink_code.code_de_gestion_de_missions as CGM
from utils.class_Logger import Logger, make_logger

CONFIG_FILE = "Valkyrie/mission_config.json"

_logger: Logger | None = None
_ip_ordi: str = ""

SIMU = False  # True = SITL, False = REEL

# Valeurs par défaut appliquées si un paramètre est absent ou null
CONFIG_DEFAULTS = {
    "alt_quadrillage":    3,
    "taille_quadrillage": 10,
    "pas_quadrillage":    2,
    "camera_wide":        False,
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
        print("[FAILSAFE] ESP32 perdu irrémédiablement. LAND déclenché.")
        drone.change_mode("LAND")
        return False
    return True


# ==============================================================================
# CONNEXION WIFI PONCTUELLE (logs)
# ==============================================================================
async def _fetch_log_async(ip_ordi: str, timeout_s: float = 60.0) -> None:
    """Se connecte au Dashboard, attend la commande print_log, envoie le fichier de logs."""
    uri = f"ws://{ip_ordi}:8000/ws/Valkyrie"
    print(f"[WIFI] Connexion ponctuelle à {uri}...")
    deadline = time.time() + timeout_s
    try:
        async with websockets.connect(uri, close_timeout=2) as ws:
            await ws.send(json.dumps({"type": "status", "command": "valkyrie_ready", "source": "Valkyrie"}))
            print("[WIFI] Connecté. En attente de commandes...")
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(raw)
                    command = data.get("command")

                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong", "source": "Valkyrie",
                                                   "sent_at": data.get("sent_at")}))

                    elif command == "print_log":
                        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.log")
                        try:
                            with open(log_path, "r", encoding="utf-8") as f:
                                content = f.read()
                        except Exception:
                            content = "(aucun log disponible)"
                        await ws.send(json.dumps({"type": "log", "command": "log_ack",
                                                   "source": "Valkyrie", "output": content}))
                        break

                    elif command == "disconnect":
                        break

                except asyncio.TimeoutError:
                    pass  # Normal, on reboucle
    except Exception as e:
        print(f"[WIFI] Erreur connexion Valkyrie : {e}")


def fetch_log_from_dashboard(ip_ordi: str, timeout_s: float = 60.0) -> None:
    """Wrapper synchrone pour _fetch_log_async."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_fetch_log_async(ip_ordi, timeout_s))
    finally:
        loop.close()


# ==============================================================================
# MISSIONS
# ==============================================================================
def run_mission_1(drone: Valkyrie, esp32: ESP32_Link, config: dict,
                  gripper: "GripperESP32 | None" = None):
    """
    Mission 1 complète :
      1. Décollage + quadrillage spirale (e-ArUco)
      2. Precision land e-ArUco avec alignement yaw (nez/pince vers la cible)
      3. Fermeture pince -- si saisie échoue --> réouverture + nouvelle tentative
      4. Décollage avec objet saisi --> GCS positionne 2m au-dessus de Valhalla (LOITER)
      5. Centrage PnP sur les 4 marqueurs de Valhalla
      6. Arrêt RC override --> ouverture pince (lâcher) --> RTL
    """
    _MAX_GRIP_RETRIES = 3

    if _logger:
        _logger.log("[MISSION 1] Démarrage.")
    if not drone.load_config(config):
        print("[MISSION 1] Configuration invalide. Abandon.")
        if _logger:
            _logger.log("[MISSION 1] Configuration invalide. Abandon.")
        return

    # --- Phase 1 : Décollage ---
    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 1] Échec du décollage.")
        if _logger:
            _logger.log("[MISSION 1] ECHEC décollage.")
        return
    print("[MISSION 1] Décollage OK.")
    if _logger:
        _logger.log("[MISSION 1] Décollage OK.")

    # --- Phase 2 : Quadrillage e-ArUco + precision land pince ---
    objet_saisi = False
    for tentative in range(_MAX_GRIP_RETRIES):
        if _logger:
            _logger.log(f"[MISSION 1] Tentative saisie {tentative + 1}/{_MAX_GRIP_RETRIES} -- quadrillage.")
        print(f"[MISSION 1] Tentative precision land {tentative + 1}/{_MAX_GRIP_RETRIES}")

        while True:
            cible_trouvee = drone.executer_quadrillage(e_analyse=True)
            if not cible_trouvee:
                print("[MISSION 1] Quadrillage terminé sans trouver la cible.")
                if _logger:
                    _logger.log("[MISSION 1] Quadrillage terminé : cible introuvable.")
                drone.send_cgm(CGM.VALKYRIE_NO_TARGET_FOUND)
                return

            resultat = drone.precision_loiter_and_land_gripper(e_analyse=True)

            if resultat is False:
                print("[MISSION 1] Mission interrompue (urgence).")
                if _logger:
                    _logger.log("[MISSION 1] Mission interrompue (urgence).")
                return
            if resultat is True:
                if _logger:
                    _logger.log("[MISSION 1] Atterri sur cible. Tentative saisie pince.")
                break
            print("[MISSION 1] Cible perdue. Requadrillage...")
            if _logger:
                _logger.log("[MISSION 1] Cible perdue en LOITER. Requadrillage.", wanna_print=False)

        if gripper is None:
            print("[MISSION 1] Pince non connectée. Simulation de saisie -- mission continue.")
            if _logger:
                _logger.log("[MISSION 1] Pince absente : saisie simulée, mission continue.")
            objet_saisi = True
            break

        print("[MISSION 1] Atterri. Fermeture de la pince...")
        caught = gripper.close_gripper()

        if caught:
            print("[MISSION 1] Objet saisi avec succès !")
            if _logger:
                _logger.log("[MISSION 1] Objet saisi avec succès (pince fermée + contact).")
            drone.send_cgm(CGM.VALKYRIE_GRIP_OK)
            objet_saisi = True
            break

        print(f"[MISSION 1] Saisie échouée (tentative {tentative + 1}). Réouverture...")
        if _logger:
            _logger.log(f"[MISSION 1] Saisie échouée tentative {tentative + 1}. Réouverture pince.")
        gripper.open_gripper()

        if tentative < _MAX_GRIP_RETRIES - 1:
            if not drone.takeoff_autonome(config["alt_quadrillage"]):
                print("[MISSION 1] Échec redécollage pour nouvelle tentative.")
                if _logger:
                    _logger.log("[MISSION 1] ECHEC redécollage pour nouvelle tentative saisie.")
                return

    if not objet_saisi:
        print(f"[MISSION 1] Objet non saisi après {_MAX_GRIP_RETRIES} tentatives. Abandon.")
        if _logger:
            _logger.log(f"[MISSION 1] Objet non saisi après {_MAX_GRIP_RETRIES} tentatives. Abandon.")
        drone.send_cgm(CGM.VALKYRIE_NO_TARGET_FOUND)
        return

    # --- Phase 3 : Redécollage avec l'objet ---
    print("[MISSION 1] Redécollage avec objet saisi...")
    if _logger:
        _logger.log("[MISSION 1] Phase 3 : redécollage avec objet.")
    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 1] Échec redécollage avec objet. Lâcher et abandon.")
        if _logger:
            _logger.log("[MISSION 1] ECHEC redécollage avec objet. Lâcher et abandon.")
        if gripper is not None:
            gripper.open_gripper()
        return

    # --- Phase 4 : GCS positionne Valkyrie 2m au-dessus de Valhalla puis LOITER ---
    if _logger:
        _logger.log("[MISSION 1] Phase 4 : attente LOITER posé par le GCS (goto Valhalla).")
    print("[MISSION 1] Phase 4 : en attente que le GCS positionne Valkyrie au-dessus de Valhalla...")
    drone.send_cgm(CGM.VALKYRIE_WAITING_MISSION)

    deadline_loiter = time.time() + 120.0
    en_loiter = False
    while time.time() < deadline_loiter:
        if drone.fin_mission:
            if gripper is not None:
                gripper.open_gripper()
            return
        if drone.mode() == "LOITER":
            drone._rc_throttle_pwm = 1500
            drone._precision_active = True
            drone._rc_thread = threading.Thread(target=drone._rc_override_loop, daemon=True)
            drone._rc_thread.start()
            en_loiter = True
            break
        time.sleep(0.5)

    if not en_loiter:
        print("[MISSION 1] Timeout Phase 4 : LOITER non reçu depuis le GCS. Lâcher et RTL.")
        if _logger:
            _logger.log("[MISSION 1] Timeout Phase 4 : GCS n'a pas mis Valkyrie en LOITER. Lâcher + RTL.")
        if gripper is not None:
            gripper.open_gripper()
        drone.return_to_launch()
        return

    print("[MISSION 1] LOITER confirmé -- RC override actif -- Phase 4 terminée.")

    # --- Phase 5 : Centrage PnP sur les 4 coins de Valhalla ---
    print("[MISSION 1] Centrage PnP sur Valhalla...")
    if _logger:
        _logger.log("[MISSION 1] Phase 5 : centrage PnP sur Valhalla.")
    centrage_ok = drone.pnp_center_over_valhalla(timeout=60.0)
    if not centrage_ok:
        print("[MISSION 1] Centrage PnP timeout -- lâcher quand même.")
        if _logger:
            _logger.log("[MISSION 1] Centrage PnP timeout -- lâcher quand même.")

    # --- Phase 6 : Lâcher l'objet (RC override maintenu en LOITER) ---
    print("[MISSION 1] Ouverture pince --> lâcher de l'objet.")
    if _logger:
        _logger.log("[MISSION 1] Phase 6 : ouverture pince, lâcher.")
    if gripper is not None:
        gripper.open_gripper()

    # --- Phase 7 : RTL --- RC override coupé après que le FC reprend la main
    drone.send_cgm(CGM.VALKYRIE_LANDED)
    print("[MISSION 1] Objet livré à Valhalla. RTL Valkyrie.")
    if _logger:
        _logger.log("[MISSION 1] Objet livré. RTL.")
    drone.return_to_launch()
    drone._precision_active = False
    if drone._rc_thread:
        drone._rc_thread.join(timeout=1.0)


def run_mission_2(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """
    Mission 2 : décollage + precision loiter/land ArUco direct (sans quadrillage).
      1. Décollage à alt_quadrillage
      2. RC override + LOITER
      3. Precision loiter + land ArUco (relance si cible perdue)
    """
    if _logger:
        _logger.log("[MISSION 2] Démarrage.")
    if not drone.load_config(config):
        print("[MISSION 2] Configuration invalide. Abandon.")
        if _logger:
            _logger.log("[MISSION 2] Configuration invalide. Abandon.")
        return

    # --- Phase 1 : Décollage ---
    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 2] Échec du décollage.")
        if _logger:
            _logger.log("[MISSION 2] ECHEC décollage.")
        return
    print("[MISSION 2] Décollage OK.")
    if _logger:
        _logger.log("[MISSION 2] Décollage OK.")

    # --- Phase 2 + 3 : LOITER + precision loiter/land (relance si cible perdue) ---
    while True:
        if drone.fin_mission:
            return

        # Démarrage RC override (normalement géré par executer_quadrillage)
        drone._rc_throttle_pwm = 1500
        drone._precision_active = True
        drone._rc_thread = threading.Thread(target=drone._rc_override_loop, daemon=True)
        drone._rc_thread.start()

        time.sleep(2) # nouveau
        loiter_ok = False
        for _ in range(5):
            if drone.change_mode("LOITER"):
                loiter_ok = True
                break
            time.sleep(1)

        if not loiter_ok:
            print("[MISSION 2] Impossible de passer en LOITER. Abandon.")
            if _logger:
                _logger.log("[MISSION 2] ECHEC passage LOITER.")
            drone._precision_active = False
            if drone._rc_thread:
                drone._rc_thread.join(timeout=1.0)
            drone.send_cgm(CGM.VALKYRIE_MODE_CHANGE_FAIL)
            return

        print("[MISSION 2] LOITER actif. Precision loiter/land ArUco...")
        if _logger:
            _logger.log("[MISSION 2] LOITER actif. Precision loiter/land démarré.")

        resultat = drone.precision_loiter_and_land_gripper(e_analyse=True)

        if resultat is True:
            print("[MISSION 2] Atterrissage de précision réussi.")
            if _logger:
                _logger.log("[MISSION 2] Atterrissage de précision réussi.")
            drone.send_cgm(CGM.VALKYRIE_LANDED)
            return
        elif resultat is False:
            print("[MISSION 2] Mission interrompue (urgence).")
            if _logger:
                _logger.log("[MISSION 2] Mission interrompue par urgence.")
            return
        else:
            # None : cible perdue en LOITER → retour en LOITER et nouvelle tentative
            print("[MISSION 2] Cible perdue. Retour en LOITER...")
            if _logger:
                _logger.log("[MISSION 2] Cible perdue -- retour LOITER.")


def run_mission_3(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 3 : quadrillage spiral + Precision Land ArUco simple (4x4_250)."""
    if _logger:
        _logger.log("[MISSION 3] Démarrage.")
    if not drone.load_config(config):
        print("[MISSION 3] Configuration invalide. Abandon.")
        if _logger:
            _logger.log("[MISSION 3] ECHEC -- configuration invalide.")
        return

    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 3] Échec du décollage.")
        if _logger:
            _logger.log("[MISSION 3] ECHEC décollage.")
        return

    print("[MISSION 3] Décollage OK.")
    if _logger:
        _logger.log(f"[MISSION 3] Décollage OK à {config['alt_quadrillage']}m.")

    # Boucle requadrillage : on retente si la cible est perdue en LOITER
    while True:
        if _logger:
            _logger.log("[MISSION 3] Début du quadrillage spiral.")
        cible_trouvee = drone.executer_quadrillage(e_analyse=False)
        if not cible_trouvee:
            print("[MISSION 3] Quadrillage terminé sans trouver la cible.")
            if _logger:
                _logger.log("[MISSION 3] Quadrillage terminé -- cible introuvable.")
            drone.send_cgm(CGM.VALKYRIE_NO_TARGET_FOUND)
            return

        if _logger:
            _logger.log("[MISSION 3] Cible ArUco trouvée. Début precision loiter/land.")
        resultat = drone.precision_loiter_and_land(e_analyse=False)

        if resultat is True:
            print("[MISSION 3] Atterrissage de précision réussi.")
            if _logger:
                _logger.log("[MISSION 3] Atterrissage de précision réussi.")
            drone.send_cgm(CGM.VALKYRIE_LANDED)
            return
        elif resultat is False:
            print("[MISSION 3] Mission interrompue (fin_mission).")
            if _logger:
                _logger.log("[MISSION 3] Mission interrompue par urgence.")
            return
        else:  # None --> cible perdue en LOITER --> requadrillage
            print("[MISSION 3] Cible perdue. Relance du quadrillage...")
            if _logger:
                _logger.log("[MISSION 3] Cible perdue en LOITER -- requadrillage.")


def run_mission_4(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 4 : quadrillage spiral + Precision Land e-ArUco (inner/outer) + pince."""
    if _logger:
        _logger.log("[MISSION 4] Démarrage.")
    if not drone.load_config(config):
        print("[MISSION 4] Configuration invalide. Abandon.")
        if _logger:
            _logger.log("[MISSION 4] ECHEC -- configuration invalide.")
        return

    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 4] Échec du décollage.")
        if _logger:
            _logger.log("[MISSION 4] ECHEC décollage.")
        return

    print("[MISSION 4] Décollage OK.")
    if _logger:
        _logger.log(f"[MISSION 4] Décollage OK à {config['alt_quadrillage']}m.")

    # Boucle requadrillage : on retente si la cible est perdue en LOITER
    while True:
        if _logger:
            _logger.log("[MISSION 4] Début du quadrillage spiral (e-ArUco).")
        cible_trouvee = drone.executer_quadrillage(e_analyse=True)
        if not cible_trouvee:
            print("[MISSION 4] Quadrillage terminé sans trouver la cible.")
            if _logger:
                _logger.log("[MISSION 4] Quadrillage terminé -- cible introuvable.")
            drone.send_cgm(CGM.VALKYRIE_NO_TARGET_FOUND)
            return

        if _logger:
            _logger.log("[MISSION 4] Cible e-ArUco trouvée. Début precision loiter/land gripper.")
        resultat = drone.precision_loiter_and_land_gripper(e_analyse=True)

        if resultat is True:
            print("[MISSION 4] Atterrissage de précision réussi.")
            if _logger:
                _logger.log("[MISSION 4] Atterrissage de précision réussi.")
            drone.send_cgm(CGM.VALKYRIE_LANDED)
            return
        elif resultat is False:
            print("[MISSION 4] Mission interrompue (fin_mission).")
            if _logger:
                _logger.log("[MISSION 4] Mission interrompue par urgence.")
            return
        else:  # None --> cible perdue en LOITER --> requadrillage
            print("[MISSION 4] Cible perdue. Relance du quadrillage...")
            if _logger:
                _logger.log("[MISSION 4] Cible perdue en LOITER -- requadrillage.")


def run_mission_5(drone: Valkyrie, esp32: ESP32_Link, config: dict):
    """Mission 5 : décollage → GCS positionne au-dessus de Valhalla → centrage PnP."""
    if _logger:
        _logger.log("[MISSION 5] Démarrage : goto Valhalla + PnP.")
    print("[MISSION 5] Démarrage.")

    if not drone.load_config(config):
        print("[MISSION 5] Configuration invalide. Abandon.")
        if _logger:
            _logger.log("[MISSION 5] ECHEC -- configuration invalide.")
        return

    if not drone.takeoff_autonome(config["alt_quadrillage"]):
        print("[MISSION 5] Échec du décollage.")
        if _logger:
            _logger.log("[MISSION 5] ECHEC décollage.")
        return

    print("[MISSION 5] Décollage OK.")
    if _logger:
        _logger.log(f"[MISSION 5] Décollage OK à {config['alt_quadrillage']}m.")

    # Le GCS appelle goto_valkyrie_au_dessus_valhalla() et met Valkyrie en LOITER.
    # Valkyrie signale qu'il est prêt et attend ce changement de mode (max 120s).
    print("[MISSION 5] En attente que le GCS positionne Valkyrie au-dessus de Valhalla...")
    if _logger:
        _logger.log("[MISSION 5] Attente LOITER posé par le GCS (goto Valhalla).")
    drone.send_cgm(CGM.VALKYRIE_WAITING_MISSION)

    deadline_loiter = time.time() + 120.0
    en_loiter = False
    while time.time() < deadline_loiter:
        if drone.fin_mission:
            return
        if drone.mode() == "LOITER":
            # CRITIQUE : activer le RC override immédiatement (sinon le drone tombe en LOITER)
            drone._rc_throttle_pwm = 1500
            drone._precision_active = True
            drone._rc_thread = threading.Thread(target=drone._rc_override_loop, daemon=True)
            drone._rc_thread.start()
            en_loiter = True
            break
        time.sleep(0.5)

    if not en_loiter:
        print("[MISSION 5] Timeout : LOITER non reçu depuis le GCS. LAND.")
        if _logger:
            _logger.log("[MISSION 5] ECHEC -- timeout LOITER. LAND.")
        drone.change_mode("LAND")
        return

    print("[MISSION 5] LOITER confirmé -- RC override actif. Début centrage PnP sur Valhalla...")
    if _logger:
        _logger.log("[MISSION 5] LOITER confirmé. RC override actif. Centrage PnP démarré.")

    centrage_ok = drone.pnp_center_over_valhalla(timeout=60.0)

    # Arrêt du RC override avant LAND (le FC reprend le contrôle du throttle)
    drone._precision_active = False
    if drone._rc_thread:
        drone._rc_thread.join(timeout=1.0)

    if centrage_ok:
        print("[MISSION 5] Centrage PnP réussi.")
        if _logger:
            _logger.log("[MISSION 5] Centrage PnP réussi.")
        drone.send_cgm(CGM.VALKYRIE_LANDED)
    else:
        print("[MISSION 5] Centrage PnP timeout -- position non confirmée.")
        if _logger:
            _logger.log("[MISSION 5] Centrage PnP timeout.")

    drone.change_mode("LAND")


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
    if num_mission not in _MISSION_RUNNERS:
        print(f"[MISSION] Numéro de mission invalide : {num_mission}")
        drone.send_cgm(CGM.VALKYRIE_MISSION_INVALID)
        return
    config = read_config_safe()
    runner = _MISSION_RUNNERS[num_mission]
    print(f"[MISSION] Lancement mission {num_mission}...")
    if _logger:
        _logger.log(f"[MISSION] Lancement mission {num_mission}.")
    try:
        if num_mission == 1:
            runner(drone, esp32, config, gripper)
        else:
            runner(drone, esp32, config)
    except Exception:
        if _logger:
            _logger.log(f"[MISSION {num_mission}] Exception non gérée :", exception=True)
        raise

    # Si une urgence a coupé la mission, attendre l'atterrissage puis réinitialiser
    if drone.fin_mission:
        print("[MISSION] Urgence détectée -- attente désarmement Valkyrie...")
        drone.fin_mission = False
        drone.allow_actions = True
        drone.wait_motors_disarmed(timeout=120.0)
        print("[MISSION] Valkyrie désarmé. Retour à l'attente de mission.")

    print(f"[MISSION] Mission {num_mission} terminée. En attente du prochain ordre.")
    drone.send_cgm(CGM.VALKYRIE_WAITING_MISSION)


# File thread-safe alimentée par drone._cgm_hook (MAVLink radio fallback)
_cgm_radio_queue: _queue.SimpleQueue = _queue.SimpleQueue()



def _traiter_cgm_radio(drone: Valkyrie, esp32: ESP32_Link,
                       gripper: "GripperESP32 | None", cgm_value: int):
    """Traite un CGM reçu via MAVLink radio (fallback sans ESP32)."""
    _mission_radio = {
        CGM.PC_DEMANDE_MISSION_1_VALKYRIE.value: 1,
        CGM.PC_DEMANDE_MISSION_2_VALKYRIE.value: 2,
        CGM.PC_DEMANDE_MISSION_3_VALKYRIE.value: 3,
        CGM.PC_DEMANDE_MISSION_4_VALKYRIE.value: 4,
        CGM.PC_DEMANDE_MISSION_5_VALKYRIE.value: 5,
    }
    if cgm_value in _mission_radio:
        run_mission(drone, esp32, _mission_radio[cgm_value], gripper)
    elif cgm_value == CGM.PC_CONFIGURE_VALKYRIE.value:
        if _ip_ordi:
            fetch_log_from_dashboard(_ip_ordi)
    elif cgm_value == CGM.PC_CALIB_GRIPPER_VALKYRIE.value:
        if gripper is not None:
            gripper.calibrate()
    elif cgm_value == CGM.PC_OPEN_GRIPPER_VALKYRIE.value:
        if gripper is not None:
            gripper.open_gripper()
    elif cgm_value == CGM.PC_CLOSE_GRIPPER_VALKYRIE.value:
        if gripper is not None:
            gripper.close_gripper()


# ==============================================================================
# BOUCLE PRINCIPALE (attente ordres ESP32 ou MAVLink radio)
# ==============================================================================
def main_loop(drone: Valkyrie, esp32: ESP32_Link, gripper: GripperESP32 | None = None):
    """
    Boucle infinie d'écoute des messages de Valhalla.
    - ESP32 (primaire) : CFG:json, CMD:START:N
    - MAVLink radio (fallback) : PC_DEMANDE_MISSION_*_VALKYRIE via _cgm_radio_queue
    Les urgences (CGM 213/214) sont gérées par les callbacks ESP32 et le hook MAVLink.
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

        # Ordres MAVLink radio : CGMs reçus directement depuis le GCS
        while not _cgm_radio_queue.empty():
            try:
                _traiter_cgm_radio(drone, esp32, gripper, _cgm_radio_queue.get_nowait())
            except _queue.Empty:
                break

        # Ping-pong ESP32 : réponse automatique (santé du lien série UART pince)
        # Toutes les commandes mission/pince arrivent par MAVLink radio via _traiter_cgm_radio.
        cgm_recu = esp32.get_and_clear_cgm()
        if cgm_recu == CGM.ESP32_PING.value:
            print("[MAIN] ESP32_PING reçu. Envoi du PONG...")
            esp32.send_cgm(CGM.ESP32_PONG.value)

        time.sleep(0.1)


# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-ip", required=True, help="IP du PC Dashboard")
    args = parser.parse_args()
    _ip_ordi = args.dashboard_ip

    _logger = make_logger(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.log"))
    _logger.log("[VALKYRIE] Démarrage.")

    _startup_config = read_config_safe()
    _camera_wide    = bool(_startup_config.get("camera_wide", False))
    print(f"[MAIN] camera_wide={_camera_wide} (lu depuis {CONFIG_FILE})")

    print("[MAIN] Connexion MAVLink à Valkyrie...")
    if SIMU:
        drone = Valkyrie(address="127.0.0.1:14560", target_system=2, logger=_logger)
    else:
        drone = Valkyrie(address="/dev/ttyAMA0", target_system=2, baud=921600,
                         logger=_logger, camera_wide=_camera_wide)

    print("[MAIN] Connexion ESP32...")
    esp32 = ESP32_Link(
        port="/dev/ttyAMA3",
        baudrate=115200,
        mock_simulation=SIMU,
        udp_rx_port=5002,
        udp_tx_port=5001,
    )
    while not esp32.connect():
        print("[MAIN] ESP32 non disponible. Retry dans 5s...")
        drone.send_cgm(CGM.VALKYRIE_ESP32_FAIL)
        time.sleep(5)
    print("[MAIN] ESP32 connecté.")

    esp32.set_fail_callback(lambda _: drone.send_cgm(CGM.VALKYRIE_ESP32_FAIL))

    # Urgences et ordres de mission : arrivent par MAVLink radio (GCS direct)
    def _on_emergency_stop():
        print("[URGENCE] Désarmement forcé Valkyrie !")
        drone.disarm(force=True)
        drone.fin_mission = True

    def _on_emergency_landing():
        print("[URGENCE] Atterrissage d'urgence Valkyrie !")
        drone.change_mode("LAND")
        drone.fin_mission = True

    # Hook MAVLink radio : urgences traitées immédiatement, autres CGMs mis en file
    def _cgm_hook_radio(cgm):
        if cgm.value == CGM.PC_A_DISARM_FORCE_VALKYRIE.value:
            _on_emergency_stop()
        elif cgm.value == CGM.PC_URGENCY_LANDING_VALKYRIE.value:
            _on_emergency_landing()
        else:
            _cgm_radio_queue.put(cgm.value)

    drone._cgm_hook = _cgm_hook_radio

    drone.set_esp32_link(esp32)

    gripper = GripperESP32(esp32)
    if not gripper.connect():
        print("[MAIN] Pince non connectée -- fonctions pince désactivées.")
        gripper = None

    main_loop(drone, esp32, gripper)
