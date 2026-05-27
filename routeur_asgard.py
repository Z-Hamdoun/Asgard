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
ADDR_MP_VALHALLA = "udpout:127.0.0.1:14551" # Pour Mission Planner 1
ADDR_MP_VALKYRIE = "udpout:127.0.0.1:14561" # Pour Mission Planner 2
ADDR_DASHBOARD   = "udpout:127.0.0.1:14556" # Pour le script Dashboard local

SYSID_VALHALLA = 1
SYSID_VALKYRIE = 2

# INITIALISATION
print("Démarrage du Hub MAVLink ASGARD...")
link_radio_valhalla = mavutil.mavlink_connection(ADDR_RADIO_VALHALLA, autoreconnect=True)
link_radio_valkyrie = mavutil.mavlink_connection(ADDR_RADIO_VALKYRIE, autoreconnect=True)

link_mp_valhalla = mavutil.mavlink_connection(ADDR_MP_VALHALLA, autoreconnect=True)
link_mp_valkyrie = mavutil.mavlink_connection(ADDR_MP_VALKYRIE, autoreconnect=True)
link_dashboard   = mavutil.mavlink_connection(ADDR_DASHBOARD, autoreconnect=True)

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

        # Télémétrie Valkyrie
        msg_vk = link_radio_valkyrie.recv_match(blocking=False)
        if msg_vk and msg_vk.get_type() != 'BAD_DATA':
            buf = msg_vk.get_msgbuf()
            link_mp_valkyrie.write(buf)  # Envoi à MP 2
            link_dashboard.write(buf)    # Envoi au Dashboard

        # --- Des Logiciels Locaux vers les Radios (Ordres/Gotos) ---
        # Ordres depuis MP Valhalla
        msg_mp_v = link_mp_valhalla.recv_match(blocking=False)
        if msg_mp_v and msg_mp_v.get_type() != 'BAD_DATA':
            link_radio_valhalla.write(msg_mp_v.get_msgbuf())

        # Ordres depuis MP Valkyrie
        msg_mp_vk = link_mp_valkyrie.recv_match(blocking=False)
        if msg_mp_vk and msg_mp_vk.get_type() != 'BAD_DATA':
            link_radio_valkyrie.write(msg_mp_vk.get_msgbuf())

        time.sleep(0.001)

except KeyboardInterrupt:
    print("\nArrêt du routeur.")