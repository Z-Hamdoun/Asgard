from math import cos, sin
import numpy as np

# Pas vraiment testé
def drone_to_ned(
        x: float,
        y: float,
        z: float,
        roll: float,
        pitch: float,
        yaw: float
    ) -> tuple[float, float, float]:
    """Transforme un vecteur dans le repère du drone (avant, droite, bas)
    vers le repère monde NED (Nord, Est, Bas),
    en tenant compte des angles d'attitude (roll, pitch, yaw).
    
    Args:
        x (float): Avant (drone).
        y (float): Droite (drone).
        z (float): Bas (drone).
        roll (float): Roll (rad).
        pitch (float): Pitch (rad).
        yaw (float): Yaw (rad).
    
    Returns:
        tuple:
            - **n** (*float*) – Nord.
            - **e** (*float*) – Est.
            - **d** (*float*) – Bas.
    """

    # Matrice de rotation autour de X (roll)
    Rx = np.array([
        [1, 0, 0],
        [0, cos(roll), -sin(roll)],
        [0, sin(roll),  cos(roll)]
    ])

    # Matrice de rotation autour de Y (pitch)
    Ry = np.array([
        [cos(pitch), 0, sin(pitch)],
        [0, 1, 0],
        [-sin(pitch), 0, cos(pitch)]
    ])

    # Matrice de rotation autour de Z (yaw)
    Rz = np.array([
        [cos(yaw), -sin(yaw), 0],
        [sin(yaw),  cos(yaw), 0],
        [0, 0, 1]
    ])

    # Matrice de rotation totale : R = Rz * Ry * Rx
    R = Rz @ Ry @ Rx

    # Vecteur déplacement dans le repère drone
    v_drone = np.array([x, y, z])

    # Changement de base vers le repère NED
    v_ned = R @ v_drone

    dx, dy, dz = v_ned
    return dx, dy, dz
