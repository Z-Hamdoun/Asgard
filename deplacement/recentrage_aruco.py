from pymavlink_code.pymavlink_code.class_MAVLinCS import MAVLinCS
import math


def recentrage(drone: MAVLinCS) -> float:
    """"""
    pass


def rapproche_drone(
    drone: MAVLinCS,
    position_drone: {x: float, y: float, z: float},
    distance_aruco: {x: float, y: float, z: float},
    angle_drone: float,
) -> float:
    """Rapproche le drone vers le code Aruco.
    Arg: 
    -drone: connexion au FC du drone
    -position drone: dictionnaire qui donne la position gps du drone
    -distance aruco: dictionnaire qui donne la position du code aruco dans le repère relatif du drone
    -angle drone: angle de passage entre le repaire du drone et le repère NESW
    
    Output:
    -distance résiduel en mètre par rapport au aruco
    """
    coord_relative_aruco = {
        x: distance_aruco.x * math.sin(angle_drone)
        - distance_aruco.y * math.cos(angle_drone),
        y: distance_aruco.x * math.cos(angle_drone)
        + distance_aruco.y * math.sin(angle_drone),
        z: distance_aruco.z,
    }
    drone.goto(
        position_drone.x + coord_relative_aruco.x,
        position_drone.y + coord_relative_aruco.y,
        position_drone.z + coord_relative_aruco.z,
    )
    new_distance_aruco=0 #il faudrait avoir une fonction qui calcule la distance au code aruco en traitement d'image.
    return new_distance_aruco
