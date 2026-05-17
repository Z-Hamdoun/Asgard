import os, sys, threading, time
import asyncio
import websockets
import json
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from Communication.class_ESP32_Link import ESP32_Link
from class_Valhalla import Valhalla
import pymavlink_code.code_de_gestion_de_missions as CGM

CONFIG_FILE = "Valhalla/mission_config.json"

# CGMs qui signalent la fin de la mission Valkyrie (succès ou échec terminal)
_VALKYRIE_TERMINAL_CGMS = frozenset(
    {
        CGM.VALKYRIE_LANDED.value,
        CGM.VALKYRIE_NO_TARGET_FOUND.value,
        CGM.VALKYRIE_MODE_CHANGE_FAIL.value,
        CGM.VALKYRIE_TAKEOFF_FAIL.value,
    }
)

# Event + résultat partagés entre le thread relais et le runner de mission
_valkyrie_done = threading.Event()
_valkyrie_result = [None]  # liste pour etre mutable depuis le thread relais

# Valeurs par défaut appliquees si un paramètre est absent ou null
CONFIG_DEFAULTS = {
    "alt_quadrillage": 5,
    "taille_quadrillage": 10,
    "pas_quadrillage": 2,
    "camera_resolution": [848, 480],
    "square_pnp_size": 40,
    "taille_aruco": [40, 10],
    "id_aruco": [1, 1],
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
    Ce thread tourne en permanence sur Valhalla.
    Il écoute les messages de Valkyrie (ESP-NOW) et les transfert à la GCS (MAVLink).
    Quand un CGM terminal de Valkyrie arrive, il signale aussi _valkyrie_done.
    """
    print("[RELAIS] Thread de transfert ESP-NOW <-> MAVLink activé.")

    while True:
        cgm_recu_int = esp_link.get_and_clear_cgm()

        if cgm_recu_int is not None:
            objet_cgm = CGM.CGM.get(cgm_recu_int)

            if objet_cgm is not None and objet_cgm.name != "EMPTY":
                print(
                    f"[RELAIS] Transfert du CGM {objet_cgm.name} ({cgm_recu_int}) vers la GCS (PC)..."
                )
                drone.send_cgm(objet_cgm)
            else:
                print(
                    f"[RELAIS-ERREUR] Code CGM {cgm_recu_int} inconnu dans la bibliothèque locale !"
                )

            # Signal de fin de mission Valkyrie pour débloquer run_mission_3
            if cgm_recu_int in _VALKYRIE_TERMINAL_CGMS:
                _valkyrie_result[0] = cgm_recu_int
                _valkyrie_done.set()

        time.sleep(0.1)


# ==============================================================================
# Thread wifi
# ==============================================================================
async def _fetch_config_async(ip_ordis: list[str], timeout_s: float = 60.0) -> bool:
    """
    Se connecte au Dashboard en essayant les IPs de la liste, attend une config
    ou des commandes, puis se déconnecte proprement.
    """
    config_received = False
    deadline = time.time() + timeout_s

    # MODIFICATION : On parcourt la liste des IPs tant qu'on n'a rien reçu
    for ip_ordi in ip_ordis:
        if config_received:
            break

        uri = f"ws://{ip_ordi}:8000/ws/Valhalla"
        print(f"[WIFI] Connexion ponctuelle à {uri}...")

        try:
            # open_timeout évite de rester bloqué trop longtemps sur une IP injoignable
            async with websockets.connect(uri, close_timeout=2, open_timeout=2) as ws:
                print(f"[WIFI] Connecté à {ip_ordi}. En attente de la configuration...")
                # Signale au Dashboard que Valhalla est pret
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
                                break  # Config obtenue --> on sort du while
                        elif command == "print_log":
                            repo_root = os.path.abspath(
                                os.path.join(os.path.dirname(__file__), ".")
                            )
                            log_path = os.path.join(repo_root, "log_test_valh.txt")
                            if os.path.exists(log_path):
                                try:
                                    with open(log_path, "r", encoding="utf-8") as f:
                                        log_txt = f.read()
                                except Exception as e:
                                    log_txt = f"Erreur: {e}"
                            else:
                                log_txt = "log_test_valh.txt pas trouvé"

                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "log",
                                        "command": "log_ack",
                                        "source": "Valhalla",
                                        "output": log_txt,
                                    }
                                )
                            )
                            break

                        elif command == "git_pull":
                            repo_root = os.path.abspath(
                                os.path.join(os.path.dirname(__file__), ".")
                            )
                            script = os.path.join(repo_root, "git_pull.sh")

                            result = subprocess.run(
                                [script],
                                cwd=repo_root,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True,
                            )

                            output = result.stdout
                            if result.returncode == 0:
                                await ws.send(
                                    json.dumps(
                                        {
                                            "type": "log",
                                            "command": "pull_ack",
                                            "source": "Valhalla",
                                            "output": output,
                                        }
                                    )
                                )
                            else:
                                await ws.send(
                                    json.dumps(
                                        {
                                            "type": "status",
                                            "command": "pull_fail",
                                            "source": "Valhalla",
                                            "output": output,
                                        }
                                    )
                                )

                        elif command == "disconnect":
                            print("[WIFI] Déconnexion demandée par le Dashboard.")
                            break

                    except asyncio.TimeoutError:
                        pass  # Normal, on reboucle

                # Si on est sorti du while parce qu'on a eu la config, on coupe la boucle for des IPs
                if config_received:
                    break

        except Exception as e:
            # MODIFICATION : Si l'IP échoue, on l'affiche et le 'for' passe naturellement à la suivante
            print(f"[WIFI] Erreur de connexion sur {ip_ordi} : {e}")

    return config_received


def fetch_config_from_dashboard(ip_ordis: list[str], timeout_s: float = 60.0) -> bool:
    """Wrapper synchrone pour fetch_config_async."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_config_async(ip_ordis, timeout_s))
    finally:
        loop.close()


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


def run_mission_1(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 1 : aller au point GPS, larguer Valkyrie, atterrir et attendre sa fin."""
    lat = config["lat_mission"]
    lng = config["lng_mission"]
    alt = config["alt_quadrillage"]

    print(f"[MISSION 1] Cible -> Lat: {lat}, Lng: {lng}, Alt: {alt}m")
    drone.config = config

    if drone.takeoff_pc(altitude=3):
        print(f"[MISSION 1] Décollage OK. En route vers {lat}, {lng}...")
        if drone.execute_goto_from_config(radius_acceptance=2.0):
            print("[MISSION 1] Point atteint. Envoi config à Valkyrie...")
            _valkyrie_done.clear()
            _valkyrie_result[0] = None
            esp32.send_config(config)
            time.sleep(1.0)
            print("[MISSION 1] Ordre décollage Valkyrie...")
            drone.send_cgm(CGM.DEMANDE_TAKEOFF_VALKYRIE)
            esp32.send_start_mission(num_mission=1)
            drone.land_and_wait_valkyrie()

            print("[MISSION 1] En attente de la fin de mission Valkyrie (max 15min)...")
            completed = _valkyrie_done.wait(timeout=900.0)
            if not completed:
                print(
                    "[MISSION 1] Timeout — aucune réponse de Valkyrie. Retour à l'attente."
                )
            else:
                cgm = _valkyrie_result[0]
                if cgm == CGM.VALKYRIE_LANDED.value:
                    print("[MISSION 1] Valkyrie a atterri avec succès sur l'ArUco !")
                else:
                    obj = CGM.CGM.get(cgm)
                    print(
                        f"[MISSION 1] Mission Valkyrie terminée en échec : {obj.name if obj else cgm}"
                    )
    else:
        print("[MISSION 1] Échec du décollage.")


def run_mission_2(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 2 : à implémenter."""
    print("[MISSION 2] Non implémentée.")
    drone.send_cgm(CGM.VALHALLA_NO_TARGET_FOUND)


def run_mission_3(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 3 : envoie config + ordre à Valkyrie, puis attend sa fin via ESP32."""
    print("[MISSION 3] Valkyrie quadrillage et Aruco Precision Land")

    _valkyrie_done.clear()
    _valkyrie_result[0] = None

    esp32.send_config(config)
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
        print(
            f"[MISSION 3] Mission Valkyrie terminée en échec : {obj.name if obj else cgm}"
        )


def run_mission_4(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 4 : à implémenter."""
    print("[MISSION 4] Non implémentée.")
    drone.send_cgm(CGM.VALHALLA_NO_TARGET_FOUND)


def run_mission_5(drone: Valhalla, esp32: ESP32_Link, config: dict):
    """Mission 5 : à implémenter."""
    print("[MISSION 5] Non implémentée.")
    drone.send_cgm(CGM.VALHALLA_NO_TARGET_FOUND)


_MISSION_RUNNERS = {
    1: run_mission_1,
    2: run_mission_2,
    3: run_mission_3,
    4: run_mission_4,
    5: run_mission_5,
}


def run_mission(drone: Valhalla, esp32: ESP32_Link, num_mission: int):
    """Point d'entrée unique : charge la config sécurisée et dispatche vers la bonne mission."""
    config = read_config_safe()
    if not _check_coords(config, drone):
        return

    runner = _MISSION_RUNNERS.get(num_mission, run_mission_1)
    print(f"[MISSION] Lancement mission {num_mission}...")
    runner(drone, esp32, config)
    print(f"[MISSION] Mission {num_mission} terminée. Retour à la boucle d'attente.")


# ==============================================================================
# BOUCLE PRINCIPALE CGM
# ==============================================================================
def main_loop(drone: Valhalla, esp32: ESP32_Link, ip_ordi: list[str]):
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
                esp32.send_config(read_config())  # Relai immediat vers Valkyrie
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

    ip_ordis = sys.argv[1:]

    print("[MAIN] Connexion MAVLink à Valhalla...")
    # valhalla = Valhalla(address="/dev/ttyAMA0", target_system=1)  # REEL
    valhalla = Valhalla(address="127.0.0.1:14550", target_system=1)  # SITL

    print("[MAIN] Connexion ESP32...")
    esp32 = ESP32_Link(
        port="/dev/ttyACM0",
        baudrate=115200,
        mock_simulation=True,
        udp_rx_port=5001,
        udp_tx_port=5002,
    )
    esp32.connect()

    # Thread relais permanent (meurt avec le process principal)
    threading.Thread(
        target=run_relais_thread, args=(valhalla, esp32), daemon=True
    ).start()

    # Boucle principale (bloquante)
    main_loop(valhalla, esp32, ip_ordis)
