from pymavlink_code.class_MAVLinCS import MAVLinCS
from Camera.class_Camera import Camera
from pymavlink import mavutil

# Master drone
drone0 = MAVLinCS(
    address="127.0.0.1:14550",
    source_system=201,
    source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
    target_system=1,
    baud=57600,
    timeout_heartbeat=None,
)

# Petit drone
drone1 = MAVLinCS(
    address="127.0.0.1:14560",
    source_system=201,
    source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
    target_system=2,
    baud=57600,
    timeout_heartbeat=None,
)

# Armement des deux drones
armed_drone0 = drone0.arm()
armed_drone1 = drone1.arm()

if armed_drone0 and armed_drone1:
    # simple takeoff
    drone0.logger.log("Drone armé")
    drone0.takeoff(3)
    drone1.takeoff(3)


