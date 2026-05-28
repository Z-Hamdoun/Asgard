import os, sys, threading, time, math
import asyncio
import websockets
import json
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from Communication.class_ESP32_Link import ESP32_Link
from class_Valhalla import Valhalla
import pymavlink_code.code_de_gestion_de_missions as CGM
from utils.class_Logger import Logger, make_logger

CONFIG_FILE = "Valhalla/mission_config.json"

_logger: Logger | None = None

SIMU = True  # True = SITL, False = REEL

# CGMs qui signalent la fin de la mission Valkyrie (succès ou échec terminal)
_VALKYRIE_TERMINAL_CGMS = frozenset({
    CGM.VALKYRIE_LANDED.value,
    CGM.VALKYRIE_NO_TARGET_FOUND.value,
    CGM.VALKYRIE_MODE_CHANGE_FAIL.value,
    CGM.VALKYRIE_TAKEOFF_FAIL.value,
    CGM.VALKYRIE_FOLLOW_GPS_LOST.value,  # Mission 5 : GPS Valhalla perdu → RTL Valkyrie
})

# Event + résultat partagés entre le thread relais et le runner de mission
_valkyrie_done   = threading.Event()
_valkyrie_result = [None]  # liste pour etre mutable depuis le thread relais

# Events d'urgence : settés par le watcher, clearés après cleanup
_emergency_stop_event    = threading.Event()  # désarmement forcé
_emergency_landing_event = threading.Event()  # RTL + retour attente

# Ping-pong ESP32 : timestamp d'envoi et event de réception du pong
_esp32_ping_sent_at = [0.0]
_esp32_pong_event   = threading.Event()

# Valeurs par défaut appliquees si un paramètre est absent ou null
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
def read_config():
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
            print(f"[JSON] '{key}' manquant - valeur par défaut : {default_val}")
    return config

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
    Quand un CGM terminal de Valkyrie arrive, il signale aussi _valkyrie_done.
    """
    print("[RELAIS] Thread de transfert ESP-NOW <-> MAVLink activé.")

    while True:
        cgm_recu_int = esp_link.get_and_clear_cgm()

        if cgm_recu_int is not None:
            # Pong ESP32 : consommé localement, pas relayé vers la GCS
            if cgm_recu_int == CGM.ESP32_PONG.value:
                print(f"[RELAIS] ESP32_PONG reçu.")
                _esp32_pong_event.set()
            else:
                objet_cgm = CGM.CGM.get(cgm_recu_int)

                if objet_cgm is not None and objet_cgm.name != "EMPTY":
                    print(f"[RELAIS] Transfert du CGM {objet_cgm.name} ({cgm_recu_int}) vers la GCS (PC)...")
                    drone.send_cgm(objet_cgm)
                else:
                    print(f"[RELAIS-ERREUR] Code CGM {cgm_recu_int} inconnu dans la bibliothèque locale !")

                # Signal de fin de mission Valkyrie pour débloquer run_mission_3
                if cgm_recu_int in _VALKYRIE_TERMINAL_CGMS:
                    _valkyrie_result[0] = cgm_recu_int
                    _valkyrie_done.set()

        time.sleep(0.1)

# ==============================================================================
# Thread wifi
# ==============================================================================
async def _fetch_config_async(ip_ordi: str, esp32: ESP32_Link, timeout_s: float = 60.0) -> bool:
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
                            break

                    elif command == "git_pull":
                        try:
                            repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                            result = subprocess.check_output(["git", "pull"], cwd=repo_path).decode("utf-8")
                            await ws.send(json.dumps({"type": "log", "command": "pull_ack",
                                                      "source": "Valhalla", "output": result}))
                        except Exception as e:
                            await ws.send(json.dumps({"type": "status", "command": "pull_fail",
                                                      "source": "Valhalla", "output": str(e)}))

                    elif command == "esp32-btn":
                        print("[WIFI] Test de connectivité ESP32 demandé...")
                        _esp32_pong_event.clear()
                        _esp32_ping_sent_at[0] = time.time()
                        esp32.send_cgm(CGM.ESP32_PING.value)
                        pong_ok = False
                        for _ in range(50):
                            await asyncio.sleep(0.1)
                            if _esp32_pong_event.is_set():
                                pong_ok = True
                                break
                        if pong_ok:
                            latency_ms = int((time.time() - _esp32_ping_sent_at[0]) * 1000)
                            print(f"[WIFI] ESP32 PONG reçu ! Latence : {latency_ms}ms")
                            await ws.send(json.dumps({"type": "status", "command": "esp32_pong",
                                                      "source": "Valhalla",
                                                      "output": f"ESP32 Link OK : {latency_ms}ms"}))
                        else:
                            print("[WIFI] ESP32 PONG timeout (5s).")
                            await ws.send(json.dumps({"type": "status", "command": "esp32_timeout",
                                                      "source": "Valhalla",
                                                      "output": "ESP32 Link TIMEOUT (>5s)"}))

                    elif command == "print_log":
                        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.log")
                        try:
                            with open(log_path, "r", encoding="utf-8") as f:
                                content = f.read()
                        except Exception:
                            content = "(aucun log disponible)"
                        await sendlog(ws, "log_ack", content)

                    elif command == "disconnect":
                        print("[WIFI] Déconnexion demandée par le Dashboard.")
                        break

                except asyncio.TimeoutError:
                    pass  # Normal, on reboucle

    except Exception as e:
        print(f"[WIFI] Erreur de connexion : {e}")

    return config_received

def fetch_config_from_dashboard(ip_ordi: str, esp32: ESP32_Link, timeout_s: float = 60.0) -> bool:
    """Wrapper synchrone pour fetch_config_async."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_config_async(ip_ordi, esp32, timeout_s))
    finally:
        loop.close()

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
# EXÉCUTION DES MISSIONS
# ==============================================================================

_VALKYRIE_CONFIG_KEYS = {
    "taille_quadrillage", "pas_quadrillage", "alt_quadrillage",
    "square_pnp_size", "taille_aruco", "id_aruco",
    "camera_type", "camera_resolution",
}

def _config_valkyrie(config: dict) -> dict:
    """Filtre la config pour Valkyrie : exclut lat/lng (inutiles + trop lourds pour ESP-NOW)."""
    return {k: v for k, v in config.items() if k in _VALKYRIE_CONFIG_KEYS}


def _check_coords(config: dict, drone: Valhalla) -> bool:
    """Vérifie que les coordonnées GPS cibles sont présentes. Envoie un CGM d'erreur sinon."""
    if config.get("lat_mission") is None or config.get("lng_mission") is None:
        print("[MISSION] Aucune coordonnée GPS ! Configurez d'abord.")
        drone.send_cgm(CGM.VALHALLA_NO_TARGET_FOUND)
        return False
    return True


def run_mission_1(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 1 : aller au point GPS, larguer Valkyrie, atterrir et attendre sa fin."""
    lat = config["lat_mission"]
    lng = config["lng_mission"]
    alt = config["alt_quadrillage"]

    print(f"[MISSION 1] Cible -> Lat: {lat}, Lng: {lng}, Alt: {alt}m")
    if _logger:
        _logger.log(f"[MISSION 1] Démarrage. Cible GPS lat={lat} lng={lng} alt={alt}m")
    drone.config = config

    if drone.takeoff_pc(altitude=3):
        print(f"[MISSION 1] Décollage OK. En route vers {lat}, {lng}...")
        if _logger:
            _logger.log("[MISSION 1] Décollage OK. En route vers la cible GPS.")
        if drone.execute_goto_from_config(radius_acceptance=2.0) and not drone.fin_mission:
            print("[MISSION 1] Point atteint. Envoi config à Valkyrie...")
            if _logger:
                _logger.log("[MISSION 1] Point GPS atteint. Envoi config + ordre décollage à Valkyrie.")
            _valkyrie_done.clear()
            _valkyrie_result[0] = None
            esp32.send_config(_config_valkyrie(config))
            time.sleep(1.0)
            print("[MISSION 1] Ordre décollage Valkyrie...")
            drone.send_cgm(CGM.DEMANDE_TAKEOFF_VALKYRIE)
            esp32.send_start_mission(num_mission=1)
            drone.land_and_wait_valkyrie()

            # Diffusion GPS Valhalla pendant toute l'attente :
            # Valkyrie en a besoin pour le mode FOLLOW (Phase 4 de sa mission).
            _gps_running = [True]
            _gps_log_last = [0.0]

            def _gps_broadcast():
                while _gps_running[0] and not drone.fin_mission:
                    lat, lon, rel_alt, alt_msl = drone.position()
                    if not (math.isnan(lat) or math.isnan(lon)
                            or math.isnan(rel_alt) or math.isnan(alt_msl)):
                        esp32.send_telemetry(lat, lon, rel_alt, alt_msl)
                        now = time.time()
                        if _logger and now - _gps_log_last[0] >= 1.0:
                            _logger.log(f"[GPS] Valhalla lat={lat:.6f} lon={lon:.6f} alt_rel={rel_alt:.1f}m", wanna_print=False)
                            _gps_log_last[0] = now
                    time.sleep(0.1)

            gps_thread = threading.Thread(target=_gps_broadcast, daemon=True)
            gps_thread.start()

            print("[MISSION 1] En attente de la fin de mission Valkyrie (max 15min)...")
            if _logger:
                _logger.log("[MISSION 1] Atterri. GPS diffusé. Attente fin de mission Valkyrie (max 15min).")
            completed = _valkyrie_done.wait(timeout=900.0)
            _gps_running[0] = False
            gps_thread.join(timeout=2.0)

            if not completed:
                print("[MISSION 1] Timeout -- aucune réponse de Valkyrie. Retour à l'attente.")
                if _logger:
                    _logger.log("[MISSION 1] TIMEOUT -- pas de réponse Valkyrie après 15min.")
            else:
                cgm = _valkyrie_result[0]
                if cgm == CGM.VALKYRIE_LANDED.value:
                    print("[MISSION 1] Valkyrie a atterri avec succès sur l'ArUco !")
                    if _logger:
                        _logger.log("[MISSION 1] Valkyrie a atterri avec succès sur l'ArUco.")
                else:
                    obj = CGM.CGM.get(cgm)
                    msg = obj.name if obj else str(cgm)
                    print(f"[MISSION 1] Mission Valkyrie terminée en échec : {msg}")
                    if _logger:
                        _logger.log(f"[MISSION 1] Mission Valkyrie terminée en échec : {msg}")
    else:
        print("[MISSION 1] Échec du décollage.")
        if _logger:
            _logger.log("[MISSION 1] ECHEC décollage Valhalla.")


def run_mission_2(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 2 : à implémenter."""
    print("[MISSION 2] Non implémentée.")
    drone.send_cgm(CGM.VALHALLA_NO_TARGET_FOUND)


def run_mission_3(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 3 : envoie config + ordre à Valkyrie, puis attend sa fin via ESP32."""
    print("[MISSION 3] Valkyrie quadrillage et Aruco Precision Land")

    _valkyrie_done.clear()
    _valkyrie_result[0] = None

    esp32.send_config(_config_valkyrie(config))
    time.sleep(1)
    print("[MISSION 3] Ordre décollage Valkyrie...")
    drone.send_cgm(CGM.DEMANDE_TAKEOFF_VALKYRIE)
    esp32.send_start_mission(num_mission=3)

    print("[MISSION 3] En attente de la fin de mission Valkyrie (max 10min)...")
    completed = _valkyrie_done.wait(timeout=600.0)

    if not completed:
        print("[MISSION 3] Timeout - aucune réponse de Valkyrie. Retour à l'attente.")
        return

    cgm = _valkyrie_result[0]
    if cgm == CGM.VALKYRIE_LANDED.value:
        print("[MISSION 3] Valkyrie a atterri avec succès sur l'ArUco !")
    else:
        obj = CGM.CGM.get(cgm)
        print(f"[MISSION 3] Mission Valkyrie terminée en échec : {obj.name if obj else cgm}")


def run_mission_4(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 4 : à implémenter."""
    print("[MISSION 4] Valkyrie quadrillage et Aruco Precision Land")

    _valkyrie_done.clear()
    _valkyrie_result[0] = None

    esp32.send_config(_config_valkyrie(config))
    time.sleep(1)
    print("[MISSION 4] Ordre décollage Valkyrie...")
    drone.send_cgm(CGM.DEMANDE_TAKEOFF_VALKYRIE)
    esp32.send_start_mission(num_mission=4)

    print("[MISSION 4] En attente de la fin de mission Valkyrie (max 10min)...")
    completed = _valkyrie_done.wait(timeout=600.0)

    if not completed:
        print("[MISSION 4] Timeout - aucune réponse de Valkyrie. Retour à l'attente.")
        return

    cgm = _valkyrie_result[0]
    if cgm == CGM.VALKYRIE_LANDED.value:
        print("[MISSION 4] Valkyrie a atterri avec succès sur l'ArUco !")
    else:
        obj = CGM.CGM.get(cgm)
        print(f"[MISSION 4] Mission Valkyrie terminée en échec : {obj.name if obj else cgm}")


def run_mission_5(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 5 : Valhalla RC-contrôlé, diffuse son GPS pour que Valkyrie le suive."""
    if not check_esp32_or_rtl(esp32, drone):
        return

    _valkyrie_done.clear()
    _valkyrie_result[0] = None

    # Démarrage de Valkyrie en mode FOLLOW
    print("[MISSION 5] Ordre mission FOLLOW à Valkyrie (CMD:START:5)...")
    esp32.send_start_mission(num_mission=5)

    # Diffusion GPS Valhalla à 10 Hz jusqu'à fin de mission
    print("[MISSION 5] Diffusion GPS Valhalla via ESP32 démarrée.")
    _gps_running = [True]

    def _gps_broadcast():
        while _gps_running[0] and not drone.fin_mission:
            # position() retourne (lat, lon, relative_alt, alt_msl)
            lat, lon, rel_alt, alt_msl = drone.position()
            if not (math.isnan(lat) or math.isnan(lon) or math.isnan(rel_alt) or math.isnan(alt_msl)):
                esp32.send_telemetry(lat, lon, rel_alt, alt_msl)
            time.sleep(0.1)

    gps_thread = threading.Thread(target=_gps_broadcast, daemon=True)
    gps_thread.start()

    print("[MISSION 5] En attente fin mission FOLLOW Valkyrie (max 8 min)...")
    _valkyrie_done.wait(timeout=480)

    _gps_running[0] = False
    gps_thread.join(timeout=2.0)

    cgm = _valkyrie_result[0]
    if cgm is not None:
        obj = CGM.CGM.get(cgm)
        print(f"[MISSION 5] Fin Valkyrie : {obj.name if obj else cgm}")
    else:
        print("[MISSION 5] Timeout ou urgence -- fin mission FOLLOW.")


_MISSION_RUNNERS = {
    1: run_mission_1,
    2: run_mission_2,
    3: run_mission_3,
    4: run_mission_4,
    5: run_mission_5,
}


def _reset_after_emergency(drone: Valhalla):
    """Réinitialise fin_mission/allow_actions pour permettre un nouveau départ."""
    drone.fin_mission = False
    drone.allow_actions = True


def _handle_emergency_landing_cleanup(drone: Valhalla):
    """Attend l'atterrissage après un RTL d'urgence, puis réinitialise l'état."""
    _reset_after_emergency(drone)
    print("[URGENCE] Attente atterrissage Valhalla...")
    drone.wait_motors_disarmed(timeout=120.0)
    print("[URGENCE] Valhalla posé. Retour à l'attente de mission.")
    _emergency_landing_event.clear()


def run_mission(drone: Valhalla, esp32: ESP32_Link, num_mission: int):
    """Point d'entrée unique : charge la config sécurisée et dispatche vers la bonne mission."""
    config = read_config_safe()
    # Mission 5 ne nécessite pas de coordonnées GPS cibles (Valhalla est RC-contrôlé)
    if num_mission != 5 and not _check_coords(config, drone):
        return

    runner = _MISSION_RUNNERS.get(num_mission, run_mission_1)
    print(f"[MISSION] Lancement mission {num_mission}...")
    runner(drone, esp32, config)

    # Cleanup après urgence -- priority landing > stop (stop est déjà désarmé)
    if _emergency_landing_event.is_set():
        _handle_emergency_landing_cleanup(drone)
    elif _emergency_stop_event.is_set():
        _reset_after_emergency(drone)
        _emergency_stop_event.clear()

    print(f"[MISSION] Mission {num_mission} terminée. Retour à la boucle d'attente.")
    drone.send_cgm(CGM.VALHALLA_WAITING_MISSION)

# ==============================================================================
# WATCHER D'URGENCE (thread de fond)
# ==============================================================================
def emergency_watcher(drone: Valhalla, esp32: ESP32_Link):
    """
    Surveille en permanence les CGMs d'urgence, y compris pendant une mission active.
    Tourne dans un thread daemon indépendant de main_loop.
    """
    while True:
        # --- Arrêt d'urgence : désarme Valhalla + relaie vers Valkyrie ---
        if drone.check_cgm(CGM.PC_A_DISARM_FORCE_VALHALLA):
            drone.delete_cgm(CGM.PC_A_DISARM_FORCE_VALHALLA)
            print("[URGENCE-WD] Désarmement forcé Valhalla !")
            # timeout_ack=0 : envoie la commande sans attendre l'ACK (non bloquant)
            drone.disarm(force=True, timeout_ack=0)
            # Couper IMMÉDIATEMENT les boucles de mission et débloquer les wait()
            drone.fin_mission = True
            _emergency_stop_event.set()
            _valkyrie_done.set()       # débloque _valkyrie_done.wait() dans run_mission_*
            esp32.send_cgm(CGM.PC_A_DISARM_FORCE_VALKYRIE.value)

        # --- Atterrissage d'urgence : RTL Valhalla + relai Valkyrie ---
        if drone.check_cgm(CGM.PC_URGENCY_LANDING_VALHALLA):
            drone.delete_cgm(CGM.PC_URGENCY_LANDING_VALHALLA)
            print("[URGENCE-WD] Atterrissage d'urgence Valhalla !")
            # timeout=0 : envoie la commande RTL sans bloquer
            drone.return_to_launch(timeout=0)
            # Couper IMMÉDIATEMENT les boucles de mission
            drone.fin_mission = True
            _valkyrie_done.set()                        # débloque les wait() de mission
            _emergency_landing_event.set()
            esp32.send_cgm(CGM.PC_URGENCY_LANDING_VALKYRIE.value)  # relai Valkyrie

        # --- Commandes pince : relai direct vers Valkyrie via ESP-NOW ---
        if drone.check_cgm(CGM.PC_OPEN_GRIPPER_VALKYRIE):
            drone.delete_cgm(CGM.PC_OPEN_GRIPPER_VALKYRIE)
            print("[PINCE-WD] Ordre ouverture pince → relai Valkyrie.")
            esp32.send_cgm(CGM.PC_OPEN_GRIPPER_VALKYRIE.value)

        if drone.check_cgm(CGM.PC_CLOSE_GRIPPER_VALKYRIE):
            drone.delete_cgm(CGM.PC_CLOSE_GRIPPER_VALKYRIE)
            print("[PINCE-WD] Ordre fermeture pince → relai Valkyrie.")
            esp32.send_cgm(CGM.PC_CLOSE_GRIPPER_VALKYRIE.value)

        if drone.check_cgm(CGM.PC_CALIB_GRIPPER_VALKYRIE):
            drone.delete_cgm(CGM.PC_CALIB_GRIPPER_VALKYRIE)
            print("[PINCE-WD] Ordre calibration pince → relai Valkyrie.")
            esp32.send_cgm(CGM.PC_CALIB_GRIPPER_VALKYRIE.value)

        if drone.check_cgm(CGM.PC_CONFIGURE_VALKYRIE):
            drone.delete_cgm(CGM.PC_CONFIGURE_VALKYRIE)
            print("[WD] Connexion WiFi Valkyrie → relai ESP-NOW.")
            esp32.send_cgm(CGM.PC_CONFIGURE_VALKYRIE.value)

        time.sleep(0.05)


# ==============================================================================
# BOUCLE PRINCIPALE CGM
# ==============================================================================
def main_loop(drone: Valhalla, esp32: ESP32_Link, ip_ordi: list[str]):
    """
    Boucle infinie d'écoute des CGMs radio.
    Chaque CGM déclenche une action puis retourne ici.
    Les urgences sont gérées par emergency_watcher (thread de fond).
    """
    print("\n[MAIN] Boucle CGM active. En attente d'ordres radio...\n")
    drone.send_cgm(CGM.VALHALLA_WAITING_MISSION)

    while True:

        # Nettoyage post-urgence si déclenchée hors mission (stop ou landing)
        if _emergency_stop_event.is_set():
            _reset_after_emergency(drone)
            _emergency_stop_event.clear()
            drone.send_cgm(CGM.VALHALLA_WAITING_MISSION)
            continue

        if _emergency_landing_event.is_set():
            _handle_emergency_landing_cleanup(drone)
            drone.send_cgm(CGM.VALHALLA_WAITING_MISSION)
            continue

        # --- Configurer Valhalla (connexion WiFi ponctuelle) ---
        if drone.check_cgm(CGM.PC_CONFIGURE_VALHALLA):
            drone.delete_cgm(CGM.PC_CONFIGURE_VALHALLA)
            print("[CGM] PC_CONFIGURE_VALHALLA reçu. Connexion WiFi...")
            success = fetch_config_from_dashboard(ip_ordi[0], esp32, timeout_s=60.0)
            if success:
                esp32.send_config(_config_valkyrie(read_config()))  # Relai immediat vers Valkyrie
                drone.send_cgm(CGM.VALHALLA_CONFIG_OK)
                print("[CGM] Configuration OK. Retour à l'attente.")
            else:
                drone.send_cgm(CGM.VALHALLA_CONFIG_FAIL)
                print("[CGM] Échec configuration. Retour à l'attente.")

        # --- Lancer mission 1 ---
        elif drone.check_cgm(CGM.PC_DEMANDE_MISSION_1_VALHALLA):
            drone.delete_cgm(CGM.PC_DEMANDE_MISSION_1_VALHALLA)
            run_mission(drone, esp32, num_mission=1)

        # --- Lancer mission 2 ---
        elif drone.check_cgm(CGM.PC_DEMANDE_MISSION_2_VALHALLA):
            drone.delete_cgm(CGM.PC_DEMANDE_MISSION_2_VALHALLA)
            run_mission(drone, esp32, num_mission=2)

        # --- Lancer mission 3 ---
        elif drone.check_cgm(CGM.PC_DEMANDE_MISSION_3_VALHALLA):
            drone.delete_cgm(CGM.PC_DEMANDE_MISSION_3_VALHALLA)
            run_mission(drone, esp32, num_mission=3)

        # --- Lancer mission 4 ---
        elif drone.check_cgm(CGM.PC_DEMANDE_MISSION_4_VALHALLA):
            drone.delete_cgm(CGM.PC_DEMANDE_MISSION_4_VALHALLA)
            run_mission(drone, esp32, num_mission=4)

        # --- Lancer mission 5 ---
        elif drone.check_cgm(CGM.PC_DEMANDE_MISSION_5_VALHALLA):
            drone.delete_cgm(CGM.PC_DEMANDE_MISSION_5_VALHALLA)
            run_mission(drone, esp32, num_mission=5)

        time.sleep(0.1)


# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <IP_PC>")
        sys.exit(1)

    ip_ordis = sys.argv[1:]

    _logger = make_logger(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.log"))
    _logger.log("[VALHALLA] Démarrage.")

    print("[MAIN] Connexion MAVLink à Valhalla...")
    if SIMU:
        valhalla = Valhalla(address="127.0.0.1:14550", target_system=1)
    else:
        valhalla = Valhalla(address="/dev/ttyAMA0", target_system=1, baud=921600)

    print("[MAIN] Connexion ESP32...")
    esp32 = ESP32_Link(port="/dev/ttyACM0", baudrate=115200, mock_simulation=SIMU,
                       udp_rx_port=5001, udp_tx_port=5002)
    while not esp32.connect():
        print("[MAIN] ESP32 non disponible. Retry dans 5s...")
        valhalla.send_cgm(CGM.VALHALLA_ESP32_FAIL)
        time.sleep(5)
    print("[MAIN] ESP32 connecté.")

    esp32.set_fail_callback(lambda _: valhalla.send_cgm(CGM.VALHALLA_ESP32_FAIL))

    # Thread relais permanent (meurt avec le process principal)
    threading.Thread(target=run_relais_thread, args=(valhalla, esp32), daemon=True).start()

    # Thread watcher d'urgence (surveille les CGMs d'urgence même pendant les missions)
    threading.Thread(target=emergency_watcher, args=(valhalla, esp32), daemon=True).start()

    # Boucle principale (bloquante)
    main_loop(valhalla, esp32, ip_ordis)