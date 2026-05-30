import os, sys, threading, time
import asyncio
import websockets
import json
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from Communication.class_ESP32_Link import ESP32_Link
from class_Valhalla import Valhalla
import pymavlink_code.code_de_gestion_de_missions as CGM
from utils.class_Logger import Logger, make_logger

CONFIG_FILE = "Valhalla/mission_config.json"

_logger: Logger | None = None

SIMU = False  # True = SITL, False = REEL

# CGMs qui signalent la fin de la mission Valkyrie (succès ou échec terminal)
_VALKYRIE_TERMINAL_CGMS = frozenset({
    CGM.VALKYRIE_LANDED.value,
    CGM.VALKYRIE_NO_TARGET_FOUND.value,
    CGM.VALKYRIE_MODE_CHANGE_FAIL.value,
    CGM.VALKYRIE_TAKEOFF_FAIL.value,
    CGM.VALKYRIE_FOLLOW_GPS_LOST.value,  # Mission 5 : GPS Valhalla perdu → RTL Valkyrie
})

# Event + résultat partagés entre le thread relais et le runner de mission
_valkyrie_done = threading.Event()
_valkyrie_result = [None]  # liste pour etre mutable depuis le thread relais

# Events d'urgence : settés par le watcher, clearés après cleanup
_emergency_stop_event    = threading.Event()  # désarmement forcé
_emergency_landing_event = threading.Event()  # RTL + retour attente

# Ping-pong ESP32 : timestamp d'envoi et event de réception du pong
_esp32_ping_sent_at = [0.0]
_esp32_pong_event = threading.Event()

# Valeurs par défaut appliquees si un paramètre est absent ou null
CONFIG_DEFAULTS = {
    "lat_mission":     0.0,
    "lng_mission":     0.0,
    "alt_quadrillage": 5,
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
    response = {
        "type": "status",
        "command": failure,
        "source": "Valhalla",
        "output": str(e),
    }
    return await socket.send(json.dumps(response))


async def sendack(socket, ack):
    response = {"type": "status", "command": ack, "source": "Valhalla"}
    return await socket.send(json.dumps(response))


async def sendlog(socket, command, result):
    response = {
        "type": "log",
        "command": command,
        "source": "Valhalla",
        "output": result,
    }
    return await socket.send(json.dumps(response))


# ==============================================================================
# THREAD RELAIS (Valhalla -> GCS)
# ==============================================================================
def run_relais_thread(drone, esp_link):
    """
    Détecte les CGMs terminaux de Valkyrie (ESP-NOW primaire, MAVLink radio fallback)
    et signale _valkyrie_done pour débloquer les missions Valhalla en attente.
    Le GCS reçoit les CGMs Valkyrie directement via son propre lien MAVLink (port 14557).
    """
    print("[RELAIS] Thread de surveillance CGMs Valkyrie activé.")
    _last_mav_cgm_ts: float = 0.0

    while True:
        # --- Primaire : CGMs Valkyrie via ESP32 ---
        cgm_recu_int = esp_link.get_and_clear_cgm()
        if cgm_recu_int is not None:
            if cgm_recu_int == CGM.ESP32_PONG.value:
                print("[RELAIS] ESP32_PONG reçu.")
                _esp32_pong_event.set()
            else:
                objet_cgm = CGM.CGM.get(cgm_recu_int)
                nom = objet_cgm.name if (objet_cgm and objet_cgm.name != "EMPTY") else str(cgm_recu_int)
                print(f"[RELAIS] ESP32 : {nom} ({cgm_recu_int}).")
                if cgm_recu_int in _VALKYRIE_TERMINAL_CGMS:
                    _valkyrie_result[0] = cgm_recu_int
                    _valkyrie_done.set()

        # --- Fallback : CGMs Valkyrie via MAVLink radio (routeur --> NAMED_VALUE_INT sysid=2) ---
        msg_vk = drone.get_msg("NAMED_VALUE_INT", source_system=2)
        if msg_vk is not None:
            ts = getattr(msg_vk, '_timestamp', 0.0)
            if ts > _last_mav_cgm_ts:
                raw_name = getattr(msg_vk, 'name', b'')
                if isinstance(raw_name, bytes):
                    raw_name = raw_name.decode('ascii', errors='ignore')
                if raw_name.rstrip('\x00').strip() == 'CGM':
                    cgm_radio_int = msg_vk.value
                    _last_mav_cgm_ts = ts
                    objet_cgm = CGM.CGM.get(cgm_radio_int)
                    nom = objet_cgm.name if (objet_cgm and objet_cgm.name != "EMPTY") else str(cgm_radio_int)
                    print(f"[RELAIS] MAVLink : {nom} ({cgm_radio_int}).")
                    if cgm_radio_int in _VALKYRIE_TERMINAL_CGMS:
                        _valkyrie_result[0] = cgm_radio_int
                        _valkyrie_done.set()

        time.sleep(0.1)


# ==============================================================================
# Thread wifi
# ==============================================================================
async def _fetch_config_async(
    ip_ordi: str, esp32: ESP32_Link, timeout_s: float = 60.0
) -> bool:
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
            await ws.send(
                json.dumps(
                    {
                        "type": "status",
                        "command": "valhalla_ready",
                        "source": "Valhalla",
                    }
                )
            )

            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(raw)
                    command = data.get("command")

                    if data.get("type") == "ping":
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "pong",
                                    "source": "Valhalla",
                                    "sent_at": data.get("sent_at"),
                                }
                            )
                        )

                    elif command in ("update_config", "update_coords"):
                        new_params = data.get("data", {})
                        if new_params:
                            update_config(new_params)
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "status",
                                        "command": "config_ack",
                                        "source": "Valhalla",
                                    }
                                )
                            )
                            config_received = True
                            print("[WIFI] Config reçue. Déconnexion.")
                            break

                    elif command == "git_pull":
                        try:
                            repo_path = os.path.abspath(
                                os.path.join(os.path.dirname(__file__), "..")
                            )
                            result = subprocess.check_output(
                                ["git", "pull"], cwd=repo_path
                            ).decode("utf-8")
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "log",
                                        "command": "pull_ack",
                                        "source": "Valhalla",
                                        "output": result,
                                    }
                                )
                            )
                        except Exception as e:
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "status",
                                        "command": "pull_fail",
                                        "source": "Valhalla",
                                        "output": str(e),
                                    }
                                )
                            )

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
                            latency_ms = int(
                                (time.time() - _esp32_ping_sent_at[0]) * 1000
                            )
                            print(f"[WIFI] ESP32 PONG reçu ! Latence : {latency_ms}ms")
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "status",
                                        "command": "esp32_pong",
                                        "source": "Valhalla",
                                        "output": f"ESP32 Link OK : {latency_ms}ms",
                                    }
                                )
                            )
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


def fetch_config_from_dashboard(
    ip_ordi: str, esp32: ESP32_Link, timeout_s: float = 60.0
) -> bool:
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

def _check_coords(config: dict, drone: Valhalla) -> bool:
    """Vérifie que les coordonnées GPS cibles sont présentes. Envoie un CGM d'erreur sinon."""
    if config.get("lat_mission") is None or config.get("lng_mission") is None:
        print("[MISSION] Aucune coordonnée GPS ! Configurez d'abord.")
        drone.send_cgm(CGM.VALHALLA_NO_TARGET_FOUND)
        return False
    return True


_VALHALLA_RTL_DELAY_S = 60.0   # délai après livraison avant réarmement (laisse Valkyrie s'éloigner)
_VALHALLA_RTL_ALT_M  = 5.0    # altitude de décollage pour le RTL final


def run_mission_1(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """
    Mission 1 :
      1. Décollage + goto point GPS configuré
      2. Atterrissage et attente livraison Valkyrie (max 15 min)
      3. Après livraison : délai _VALHALLA_RTL_DELAY_S puis réarmement + RTL
    """
    lat = config["lat_mission"]
    lng = config["lng_mission"]
    alt = config["alt_quadrillage"]

    print(f"[MISSION 1] Cible -> Lat: {lat}, Lng: {lng}, Alt: {alt}m")
    if _logger:
        _logger.log(f"[MISSION 1] Démarrage. Cible GPS lat={lat} lng={lng} alt={alt}m")
    drone.config = config

    if not drone.takeoff_pc(altitude=3):
        print("[MISSION 1] Échec du décollage.")
        if _logger:
            _logger.log("[MISSION 1] ECHEC décollage Valhalla.")
        return

    print(f"[MISSION 1] Décollage OK. En route vers {lat}, {lng}...")
    if _logger:
        _logger.log("[MISSION 1] Décollage OK. En route vers la cible GPS.")

    if not drone.execute_goto_from_config(radius_acceptance=2.0) or drone.fin_mission:
        print("[MISSION 1] Goto annulé (urgence ou navigation impossible).")
        if _logger:
            _logger.log("[MISSION 1] ECHEC goto -- urgence ou navigation impossible.")
        return

    print("[MISSION 1] Point atteint. Atterrissage et attente livraison Valkyrie...")
    if _logger:
        _logger.log("[MISSION 1] Point GPS atteint. Atterrissage.")
    _valkyrie_done.clear()
    _valkyrie_result[0] = None
    drone.land_and_wait_valkyrie()

    print("[MISSION 1] En attente de la fin de mission Valkyrie (max 15min)...")
    if _logger:
        _logger.log("[MISSION 1] Atterri. Attente fin de mission Valkyrie (max 15min).")
    completed = _valkyrie_done.wait(timeout=900.0)

    if drone.fin_mission:
        return

    if not completed:
        print("[MISSION 1] Timeout -- aucune réponse de Valkyrie.")
        if _logger:
            _logger.log("[MISSION 1] TIMEOUT -- pas de réponse Valkyrie après 15min.")
    else:
        cgm = _valkyrie_result[0]
        if cgm == CGM.VALKYRIE_LANDED.value:
            print("[MISSION 1] Valkyrie a livré l'objet avec succès !")
            if _logger:
                _logger.log("[MISSION 1] Livraison Valkyrie confirmée.")
        else:
            obj = CGM.CGM.get(cgm)
            msg = obj.name if obj else str(cgm)
            print(f"[MISSION 1] Mission Valkyrie terminée en échec : {msg}")
            if _logger:
                _logger.log(f"[MISSION 1] Mission Valkyrie terminée en échec : {msg}")

    # --- Retour à la base : délai puis réarmement + RTL ---
    print(f"[MISSION 1] Attente {_VALHALLA_RTL_DELAY_S:.0f}s avant RTL (laisse Valkyrie s'éloigner)...")
    if _logger:
        _logger.log(f"[MISSION 1] Délai {_VALHALLA_RTL_DELAY_S:.0f}s avant réarmement.")
    deadline_delay = time.time() + _VALHALLA_RTL_DELAY_S
    while time.time() < deadline_delay:
        if drone.fin_mission:
            return
        time.sleep(0.5)

    print("[MISSION 1] Réarmement Valhalla + RTL...")
    if _logger:
        _logger.log("[MISSION 1] Phase finale : réarmement Valhalla et RTL.")

    for _ in range(5):
        if drone.change_mode("GUIDED"):
            break
        time.sleep(2)

    armed = False
    for _ in range(5):
        if drone.arm():
            armed = True
            break
        time.sleep(1)

    if armed:
        drone.send_cgm(CGM.VALHALLA_ARMED)
        for _ in range(5):
            if drone.takeoff(_VALHALLA_RTL_ALT_M):
                break
            time.sleep(1)
        drone.send_cgm(CGM.VALHALLA_TOOKOFF)
        time.sleep(3.0)

    drone.send_cgm(CGM.VALHALLA_LANDING)
    drone.return_to_launch()
    if _logger:
        _logger.log("[MISSION 1] RTL Valhalla lancé.")


def run_mission_2(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 2 : à implémenter."""
    if _logger:
        _logger.log("[MISSION 2] Démarrage -- mission non implémentée.")
    print("[MISSION 2] Non implémentée.")
    drone.send_cgm(CGM.VALHALLA_NO_TARGET_FOUND)


def run_mission_3(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 3 : lance Valkyrie (quadrillage + ArUco Precision Land) via MAVLink radio."""
    if _logger:
        _logger.log("[MISSION 3] Démarrage.")
    print("[MISSION 3] Lancement mission 3 Valkyrie (MAVLink radio)...")

    _valkyrie_done.clear()
    _valkyrie_result[0] = None
    # Valkyrie est lancé par le GCS simultanément -- Valhalla attend juste la fin

    print("[MISSION 3] En attente de la fin de mission Valkyrie (max 10min)...")
    if _logger:
        _logger.log("[MISSION 3] Attente fin de mission Valkyrie (max 10min).")
    completed = _valkyrie_done.wait(timeout=600.0)

    if not completed:
        print("[MISSION 3] Timeout -- aucune réponse de Valkyrie.")
        if _logger:
            _logger.log("[MISSION 3] TIMEOUT -- pas de réponse Valkyrie après 10min.")
        return

    cgm = _valkyrie_result[0]
    if cgm == CGM.VALKYRIE_LANDED.value:
        print("[MISSION 3] Valkyrie a atterri avec succès sur l'ArUco !")
        if _logger:
            _logger.log("[MISSION 3] Valkyrie a atterri avec succès.")
    else:
        obj = CGM.CGM.get(cgm)
        msg = obj.name if obj else str(cgm)
        print(f"[MISSION 3] Mission Valkyrie terminée en échec : {msg}")
        if _logger:
            _logger.log(f"[MISSION 3] Mission Valkyrie terminée en échec : {msg}")


def run_mission_4(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 4 : lance Valkyrie (quadrillage + e-ArUco Precision Land + pince) via MAVLink radio."""
    if _logger:
        _logger.log("[MISSION 4] Démarrage.")
    print("[MISSION 4] Lancement mission 4 Valkyrie (MAVLink radio)...")

    _valkyrie_done.clear()
    _valkyrie_result[0] = None
    # Valkyrie est lancé par le GCS simultanément -- Valhalla attend juste la fin

    print("[MISSION 4] En attente de la fin de mission Valkyrie (max 10min)...")
    if _logger:
        _logger.log("[MISSION 4] Attente fin de mission Valkyrie (max 10min).")
    completed = _valkyrie_done.wait(timeout=600.0)

    if not completed:
        print("[MISSION 4] Timeout -- aucune réponse de Valkyrie.")
        if _logger:
            _logger.log("[MISSION 4] TIMEOUT -- pas de réponse Valkyrie après 10min.")
        return

    cgm = _valkyrie_result[0]
    if cgm == CGM.VALKYRIE_LANDED.value:
        print("[MISSION 4] Valkyrie a atterri avec succès sur l'ArUco !")
        if _logger:
            _logger.log("[MISSION 4] Valkyrie a atterri avec succès.")
    else:
        obj = CGM.CGM.get(cgm)
        msg = obj.name if obj else str(cgm)
        print(f"[MISSION 4] Mission Valkyrie terminée en échec : {msg}")
        if _logger:
            _logger.log(f"[MISSION 4] Mission Valkyrie terminée en échec : {msg}")


def run_mission_5(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 5 : Valkyrie suit Valhalla en FOLLOW mode.
    Le GPS de Valhalla est diffusé à Valkyrie via le routeur MAVLink (GLOBAL_POSITION_INT sysid=1).
    """
    if _logger:
        _logger.log("[MISSION 5] Démarrage FOLLOW mode.")
    print("[MISSION 5] Lancement mission 5 Valkyrie (MAVLink radio)...")

    _valkyrie_done.clear()
    _valkyrie_result[0] = None
    # Valkyrie est lancé par le GCS simultanément -- Valhalla attend juste la fin

    print("[MISSION 5] En attente fin mission FOLLOW Valkyrie (max 8 min)...")
    if _logger:
        _logger.log("[MISSION 5] Attente fin de mission Valkyrie (max 8min).")
    _valkyrie_done.wait(timeout=480)

    cgm = _valkyrie_result[0]
    if cgm is not None:
        obj = CGM.CGM.get(cgm)
        msg = obj.name if obj else str(cgm)
        print(f"[MISSION 5] Fin Valkyrie : {msg}")
        if _logger:
            _logger.log(f"[MISSION 5] Fin Valkyrie : {msg}")
    else:
        print("[MISSION 5] Timeout ou urgence -- fin mission FOLLOW.")
        if _logger:
            _logger.log("[MISSION 5] Timeout ou urgence.")


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
def emergency_watcher(drone: Valhalla):
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
            # Valkyrie est géré directement par le GCS (GroundStation.arret_urgence_valkyrie)

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

        # --- Configurer Valhalla : sélection GPS via carte interactive ---
        if drone.check_cgm(CGM.PC_CONFIGURE_VALHALLA):
            drone.delete_cgm(CGM.PC_CONFIGURE_VALHALLA)
            print("[CGM] PC_CONFIGURE_VALHALLA reçu. Connexion WiFi (carte GPS)...")
            success = fetch_config_from_dashboard(ip_ordi[0], esp32, timeout_s=60.0)
            if success:
                drone.send_cgm(CGM.VALHALLA_CONFIG_OK)
                print("[CGM] Configuration GPS OK.")
            else:
                drone.send_cgm(CGM.VALHALLA_CONFIG_FAIL)
                print("[CGM] Échec configuration GPS.")

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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-ip", required=True, help="IP du PC Dashboard")
    args = parser.parse_args()
    ip_ordis = [args.dashboard_ip]

    _logger = make_logger(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.log"))
    _logger.log("[VALHALLA] Démarrage.")

    print("[MAIN] Connexion MAVLink à Valhalla...")
    if SIMU:
        valhalla = Valhalla(address="127.0.0.1:14550", target_system=1)
    else:
        valhalla = Valhalla(address="/dev/ttyAMA0", target_system=1, baud=921600)

    print("[MAIN] Connexion ESP32...")
    esp32 = ESP32_Link(
        port="/dev/ttyAMA3",
        baudrate=115200,
        mock_simulation=SIMU,
        udp_rx_port=5001,
        udp_tx_port=5002,
    )
    while not esp32.connect():
        print("[MAIN] ESP32 non disponible. Retry dans 5s...")
        valhalla.send_cgm(CGM.VALHALLA_ESP32_FAIL)
        time.sleep(5)
    print("[MAIN] ESP32 connecté.")

    esp32.set_fail_callback(lambda _: valhalla.send_cgm(CGM.VALHALLA_ESP32_FAIL))

    # Thread relais permanent (meurt avec le process principal)
    threading.Thread(target=run_relais_thread, args=(valhalla, esp32), daemon=True).start()

    # Thread watcher d'urgence (surveille les CGMs d'urgence même pendant les missions)
    threading.Thread(target=emergency_watcher, args=(valhalla,), daemon=True).start()

    # Boucle principale (bloquante)
    main_loop(valhalla, esp32, ip_ordis)
