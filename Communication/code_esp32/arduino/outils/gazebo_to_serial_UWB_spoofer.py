"""
Ce script récupère les données de position de Gazebo et les envoie sous forme de
message mavlink vision_position_estimate_send à un port série.

L'objectif est de simuler un module ESP32-UWB qui envoie ces messages à la carte 
ESP32 de télécommunication. Cette carte peut être simulée par test1.cpp, qui se 
connecte à ardupilot d'un coté et mission planner de l'autre.

"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pymavlink import mavutil
from lib.Hardware.class_Local_Position_Sensor import Local_Position_Sensor
import time
sensor = Local_Position_Sensor(simulation=True, drone_name_gz="iris_with_gimbal0")


port = "/tmp/ttyV4"
baudrate = 57600
master = mavutil.mavlink_connection(
        port, baud=baudrate
    )

master.first_byte = False # Comme si on avait déjà reçu un message
master.WIRE_PROTOCOL_VERSION = "2.0" # On active MAVLink 2
os.environ['MAVLINK20'] = '1' # On active MAVLink 2
mavutil.set_dialect(dialect='ardupilotmega') # On charge le dialecte
# Reste de la fonction master.auto_mavlink_version
master.mav = mavutil.mavlink.MAVLink(master, srcSystem=master.source_system, srcComponent=master.source_component)
master.mav.robust_parsing = master.robust_parsing
master.WIRE_PROTOCOL_VERSION = mavutil.mavlink.WIRE_PROTOCOL_VERSION

def time_usec() -> int:
    """timestamp Unix en us"""
    return int(time.time() * 1e6)

while 1:
    time.sleep(0.1)
    print(sensor.x, sensor.y, sensor.z)
    master.mav.vision_position_estimate_send(
            time_usec(),
            sensor.x, sensor.y, sensor.z,
            0, 0, 0,
            [float('NaN')]*21, 0
        )
