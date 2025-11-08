import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pymavlink import mavutil
from pymavlink_code.class_MAVLinCS import MAVLinCS

# Cette fonction est assez spécifique à notre mission, à vous de l'adapter à vos envies.

# On ajoute un waypoint de takeoff (seq = 1). A vous de voir comment vous l'implémentez.
# Nous, on a décidé de takeoff à l'altitude du 1er point

# A la fin, on considère le dernier waypoint de notre liste comme un waypoint de land.

waypoint_list_example = [ # (lat, lon, relative_alt)
    (48.8566, 2.3522, 20),   # Paris centre
    (48.8568, 2.3530, 20),   # ~70m au nord-est
    (48.8570, 2.3538, 0)    # ~70m plus loin au nord-est (wp de land)
]

def send_waypoints_mission(gcs: MAVLinCS, waypoint_list: list, accept_radius: float, takeoff_pitch: float):
    """Envoie une liste de waypoints à l'UAV."""
    gcs.write_log("<Envoi des waypoints de la mission...>")
    
    gcs.send_waypoint_ack(len(waypoint_list)+2)
    first_wp_sent = gcs.send_first_waypoint()
    if not first_wp_sent:
        gcs.clear_waypoints()
        return False
    
    first_alt = waypoint_list[0][2]
    
    gcs.send_waypoint(
        waypoint_index=1,
        command=mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        param1=takeoff_pitch,
        z=first_alt
    ) # Takeoff
    
    for i, wp in enumerate(waypoint_list):
        if i == len(waypoint_list) - 1:
            break # On fait un land du dernier point
        lat = wp[0]
        lon = wp[1]
        alt = wp[2]
        gcs.send_waypoint(
            waypoint_index=i+2,
            param2=accept_radius, # Accept Radius
            x=lat,
            y=lon,
            z=alt
        )
    gcs.send_waypoint(
        waypoint_index=len(waypoint_list)+1,
        frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
        command=mavutil.mavlink.MAV_CMD_NAV_LAND,
        param1=0, # Abort Alt
        param2=mavutil.mavlink.PRECISION_LAND_MODE_DISABLED, # Land Mode
        param4=float('NaN'), # Yaw Angle
        x=waypoint_list[-1][0],
        y=waypoint_list[-1][1],
        z=waypoint_list[-1][2]
    ) # Land
    return True

# Associé à ça, on a aussi :

# gcs.check_if_waypoints_mission_completed
# gcs.start_mission
