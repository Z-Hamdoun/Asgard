import os
import time
from pymavlink import mavutil

# Activation obligatoire de MAVLink 2
os.environ['MAVLINK20'] = '1'

# PARAMÈTRES RÉSEAU
# Flux entrants depuis les 2 RadioMasters via le Hotspot Wi-Fi
ADDR_RADIO_VALHALLA = "udpin:0.0.0.0:14550"
ADDR_RADIO_VALKYRIE = "udpin:0.0.0.0:14560"

# Flux sortants vers les instances locales
ADDR_MP_VALHALLA = "udpout:192.168.50.83:14552" # Pour Mission Planner 1
ADDR_MP_VALKYRIE = "udpout:192.168.50.83:14561" # Pour Mission Planner 2
ADDR_DASHBOARD        = "udpout:127.0.0.1:14556" # Pour le script Dashboard local
ADDR_GCS              = "udpout:127.0.0.1:14554" # Pour le GCS (class_GCS.py) — Valhalla
ADDR_GCS_VALKYRIE     = "udpout:127.0.0.1:14557" # Pour le GCS (class_GCS.py) — Valkyrie directe

SYSID_VALHALLA = 1
SYSID_VALKYRIE = 2

# INITIALISATION
print("Démarrage du Hub MAVLink ASGARD...")
link_radio_valhalla = mavutil.mavlink_connection(ADDR_RADIO_VALHALLA, autoreconnect=True)
link_radio_valkyrie = mavutil.mavlink_connection(ADDR_RADIO_VALKYRIE, autoreconnect=True)

link_mp_valhalla = mavutil.mavlink_connection(ADDR_MP_VALHALLA, autoreconnect=True)
link_mp_valkyrie = mavutil.mavlink_connection(ADDR_MP_VALKYRIE, autoreconnect=True)
link_dashboard        = mavutil.mavlink_connection(ADDR_DASHBOARD,    autoreconnect=True)
link_gcs              = mavutil.mavlink_connection(ADDR_GCS,          autoreconnect=True)
link_gcs_valkyrie     = mavutil.mavlink_connection(ADDR_GCS_VALKYRIE, autoreconnect=True)

# BOUCLE DE ROUTAGE
try:
    while True:
        # --- De la Radio vers les Logiciels Locaux ---
        # Télémétrie Valhalla
        msg_v = link_radio_valhalla.recv_match(blocking=False)
        if msg_v and msg_v.get_type() != 'BAD_DATA':
            buf = msg_v.get_msgbuf()
            link_mp_valhalla.write(buf)  # Envoi à MP 1
            link_dashboard.write(buf)    # Envoi au Dashboard
            link_gcs.write(buf)          # Envoi au GCS Valhalla (active le _cgm_hook)
            # GPS Valhalla partagé avec Valkyrie (Phase 4 Mission 1 sans ESP32)
            if msg_v.get_type() == 'GLOBAL_POSITION_INT':
                link_radio_valkyrie.write(buf)

        # Télémétrie Valkyrie
        msg_vk = link_radio_valkyrie.recv_match(blocking=False)
        if msg_vk and msg_vk.get_type() != 'BAD_DATA':
            buf = msg_vk.get_msgbuf()
            link_mp_valkyrie.write(buf)      # Envoi à MP 2
            link_dashboard.write(buf)        # Envoi au Dashboard
            link_gcs_valkyrie.write(buf)     # Envoi au GCS Valkyrie (classe GCS)
            # CGMs Valkyrie relayés vers Valhalla (run_relais_thread sans ESP32)
            if msg_vk.get_type() == 'NAMED_VALUE_INT':
                link_radio_valhalla.write(buf)

        # --- Des Logiciels Locaux vers les Radios (Ordres/Gotos) ---
        # Ordres depuis MP Valhalla
        msg_mp_v = link_mp_valhalla.recv_match(blocking=False)
        if msg_mp_v and msg_mp_v.get_type() != 'BAD_DATA':
            link_radio_valhalla.write(msg_mp_v.get_msgbuf())

        # Ordres depuis MP Valkyrie
        msg_mp_vk = link_mp_valkyrie.recv_match(blocking=False)
        if msg_mp_vk and msg_mp_vk.get_type() != 'BAD_DATA':
            link_radio_valkyrie.write(msg_mp_vk.get_msgbuf())

        # Ordres depuis le GCS Valhalla (class_GCS.py) — vers Valhalla
        msg_gcs = link_gcs.recv_match(blocking=False)
        if msg_gcs and msg_gcs.get_type() != 'BAD_DATA':
            link_radio_valhalla.write(msg_gcs.get_msgbuf())

        # Ordres depuis le GCS Valkyrie (class_GCS.py) — directement vers Valkyrie
        msg_gcs_vk = link_gcs_valkyrie.recv_match(blocking=False)
        if msg_gcs_vk and msg_gcs_vk.get_type() != 'BAD_DATA':
            link_radio_valkyrie.write(msg_gcs_vk.get_msgbuf())

        msg_dash = link_dashboard.recv_match(blocking=False)
        if msg_dash and msg_dash.get_type() != 'BAD_DATA':
            # NAMED_VALUE_INT (CGM) n'a pas de champ target_system → on évite le broadcast
            target_sys = getattr(msg_dash, 'target_system', 0)

            # Si l'ordre est destiné à Valhalla (ID 1) ou Broadcast (0)
            if target_sys == SYSID_VALHALLA or target_sys == 0:
                link_radio_valhalla.write(msg_dash.get_msgbuf())

            # Si l'ordre est explicitement destiné à Valkyrie (ID 2)
            # Note : on exclut le broadcast (0) car NAMED_VALUE_INT (CGM) n'a pas de target_system,
            # ce qui ferait transiter tous les CGMs du GCS vers Valkyrie par erreur.
            if target_sys == SYSID_VALKYRIE:
                link_radio_valkyrie.write(msg_dash.get_msgbuf())

        time.sleep(0.001)

except KeyboardInterrupt:
    print("\nArrêt du routeur.")