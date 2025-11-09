from pymavlink_code.class_MAVLinCS import MAVLinCS
from pymavlink import mavutil

log_file = "test.log"

print("Connexion avec le drone..")
drone = MAVLinCS(
    address="127.0.0.1:14550",
    source_system=201,
    source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
    target_system=1,
    baud=57600,
    timeout_heartbeat=None,
)
drone.logger.log("Connexion établie")

armed = drone.arm()
if armed:
    drone.logger.log("Drone armé")
    drone.takeoff(10)
