import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pymavlink_code.class_MAVLinCS import MAVLinCS
from divers.geopy_fct import deplacement_nord_est
from pymavlink import mavutil
from math import sqrt

log_file = "test.log"

try:
    print("Connexion avec le drone..")
    drone = MAVLinCS(
        address="0.0.0.0:14550",
        source_system=201,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
        target_system=1,
        baud=57600,
        timeout_heartbeat=None,
        log_file=log_file
    )
    drone.write_log("Connexion établie")
    
    drone.write_log("En attente du GPS..")
    drone.wait_gps_fix(timeout=None)
    drone.write_log("GPS fix")

    drone.write_log("Arement..")
    armed = drone.arm()
    if armed:
        drone.write_log("Drone armé")
        lat_i, lon_i, _, alt_i = drone.position()
        takeoff_succeded = drone.takeoff(altitude=5)
        if takeoff_succeded:
            drone.write_log("Takeoff réussi")
            landed = drone.land()
            if landed:
                drone.write_log("Atterissage réussi")
                lat_f, lon_f, _, alt_f = drone.position()
                d_Nord, d_Est = deplacement_nord_est((lat_i, lon_i), (lat_f, lon_f))
                distance_horizontale = sqrt(d_Nord**2 + d_Est**2)
                distance_verticale = abs(alt_i - alt_f)
                drone.write_log("Déplacement du drone:")
                drone.write_log(f"  Plan horizontal: {distance_horizontale} m")
                drone.write_log(f"  Hauteur: {distance_verticale} m")
            else:
                drone.write_log("Atterissage échoué")
        else:
            drone.write_log("Takeoff échoué")
    else:
        drone.write_log("Armement échoué")
except Exception:
    print("Erreur innatendue")
except KeyboardInterrupt:
    print("Arrêt demandé")
finally:
    try:
        drone.close()
    except Exception:
        pass
    print("Connexion fermée")
