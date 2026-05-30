import cv2
import numpy as np
import math
import time

import ctypes


# 1. Définition des structures pour faire le pont avec le C
class BBox(ctypes.Structure):
    _fields_ = [
        ("x_min", ctypes.c_float),
        ("x_max", ctypes.c_float),
        ("y_min", ctypes.c_float),
        ("y_max", ctypes.c_float),
        ("id", ctypes.c_int),
    ]


class Result(ctypes.Structure):
    _fields_ = [("id1", ctypes.c_int), ("id2", ctypes.c_int), ("id3", ctypes.c_int)]


import ctypes
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, "logic.so")
_lib_load_error = None
try:
    lib = ctypes.CDLL(lib_path)
    lib.find_nested_triplets.argtypes = [
        ctypes.POINTER(BBox),
        ctypes.c_int,
        ctypes.POINTER(Result),
        ctypes.c_int,
    ]
    lib.find_nested_triplets.restype = ctypes.c_int
except OSError as e:
    lib = None
    _lib_load_error = e
    print(f"[PnP] Avertissement : logic.so non chargeable ({lib_path}) : {e}")


class PnPLandingSystem:
    """
    Détection et localisation de la cible Valhalla (4 marqueurs circulaires imbriqués).

    Améliorations v2 par rapport à v1 :

    1. Anti-flip PnP
       Pour une cible planaire à 4 points, solvePnP a DEUX solutions mathématiquement
       valides (la vraie pose et sa "réflexion miroir"). Au premier frame on utilise
       SQPNP (solution globale robuste). Pour tous les frames suivants, on injecte la
       solution précédente comme point de départ (useExtrinsicGuess=True + ITERATIVE).
       L'algorithme reste ancré à la solution courante → plus de saut brutal dz 1m→2m
       quand le drone s'incline légèrement.

    2. Compensation d'attitude (roll/pitch)
       Quand le drone n'est pas parfaitement à plat, la caméra est inclinée.
       solvePnP donne tvec dans le repère caméra, pas dans le plan horizontal monde.
       On applique la matrice de rotation Ry(pitch)·Rx(roll) pour projeter le vecteur
       déplacement sur le plan horizontal réel :
           dz_vrai  = dz_cam · cos(roll) · cos(pitch)
           dx_vrai  = dx_cam · cos(pitch) + dz_cam · sin(pitch) · sin(roll)
           dy_vrai  = dy_cam · cos(roll)  - dz_cam · sin(roll)
       → dz ne varie plus quand le drone s'incline à altitude constante.
    """

    def __init__(self, marker_distance=0.33, camera_matrix=None, dist_coeffs=None):
        half = marker_distance / 2
        self.object_points = np.array(
            [
                [-half, -half, 0],  # Coin Haut-Gauche
                [half,  -half, 0],  # Coin Haut-Droit
                [half,   half, 0],  # Coin Bas-Droit
                [-half,  half, 0],  # Coin Bas-Gauche
            ],
            dtype=np.float32,
        )

        if camera_matrix is not None:
            self.camera_matrix = np.array(camera_matrix, dtype=np.float64)
        else:
            self.camera_matrix = np.array(
                [
                    [376.91194, 0.00000, 425.07994],
                    [0.00000, 380.07917, 245.66015],
                    [0.00000, 0.00000,   1.00000  ],
                ],
                dtype=np.float64,
            )

        if dist_coeffs is not None:
            self.dist_coeffs = np.array(dist_coeffs, dtype=np.float64)
        else:
            self.dist_coeffs = np.array(
                [-0.00284, 0.09082, 0.00265, -0.00063, -0.07958], dtype=np.float64
            )

        # Solution PnP du frame précédent — point de départ pour éviter le flip.
        self._prev_rvec: np.ndarray | None = None
        self._prev_tvec: np.ndarray | None = None

    def reset(self):
        """Réinitialise la solution précédente (à appeler si la cible est perdue)."""
        self._prev_rvec = None
        self._prev_tvec = None

    def _is_circular(self, cnt, area):
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            return False
        circularity = 4 * np.pi * (area / (perimeter**2))
        return 0.7 < circularity < 1.3

    def get_nested_squares(self, data):
        if lib is None:
            raise RuntimeError(f"[PnP] logic.so indisponible : {_lib_load_error}")
        n = len(data)
        c_boxes = (BBox * n)()
        for i, item in enumerate(data):
            limits = item["limits"]
            c_boxes[i] = BBox(
                limits["x_min"],
                limits["x_max"],
                limits["y_min"],
                limits["y_max"],
                item["id"],
            )
        max_results = 1000
        c_results = (Result * max_results)()
        num_found = lib.find_nested_triplets(c_boxes, n, c_results, max_results)
        return [
            (c_results[i].id1, c_results[i].id2, c_results[i].id3)
            for i in range(num_found)
        ]

    def get_contours(self, frame, normalization=True, areamax=5000, areamin=10):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if normalization:
            gray = cv2.normalize(gray, gray.copy(), 0, 255, cv2.NORM_MINMAX)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY_INV)
        contours, hierarchy = cv2.findContours(
            thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )
        results = []
        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area > areamax or area < areamin:
                continue
            if not self._is_circular(cnt, area):
                continue
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            x, y, w, h = cv2.boundingRect(cnt)
            results.append(
                {
                    "id": i,
                    "center": (cX, cY),
                    "area": area,
                    "limits": {"x_min": x, "x_max": x + w, "y_min": y, "y_max": y + h},
                }
            )
        results_nested = self.get_nested_squares(results)
        ids_third = {t[2] for t in results_nested}
        return [dico for dico in results if dico["id"] in ids_third]

    def get_landing_vector(
        self,
        frame,
        attitude: "tuple[float, float] | None" = None,
        overpoint=True,
        normalization=True,
        areamax=5000,
        areamin=10,
    ):
        """
        Calcule le vecteur (dx, dy, dz) en mètres entre la caméra et le centre de la cible.

        Args:
            frame      : image BGR
            attitude   : (roll_rad, pitch_rad) depuis l'IMU du drone.
                         Si fourni, applique la compensation d'attitude pour projeter
                         le vecteur dans le plan horizontal monde.
                         Si None, retourne les coordonnées brutes caméra.
            overpoint  : si True, garde seulement les 4 plus grandes taches
            normalization / areamax / areamin : paramètres de détection de contours

        Returns:
            (dx, dy, dz) en mètres  — ou un tuple d'erreur (code, code, str)
        """
        Taches = self.get_contours(frame, normalization, areamax, areamin)

        if overpoint and len(Taches) > 4:
            Taches = sorted(Taches, key=lambda x: x["area"], reverse=True)[:4]

        if len(Taches) != 4:
            # Cible perdue : réinitialiser le point de départ pour le prochain frame
            self.reset()
            return (444, 444, str(len(Taches)) + " taches")

        points_2d = [tache["center"] for tache in Taches]

        try:
            ordered_points = self._order_points(np.array(points_2d, dtype=np.float32))

            if self._prev_rvec is not None:
                # --- Frames suivants : ancrage à la solution précédente ---
                # SOLVEPNP_ITERATIVE + useExtrinsicGuess reste près de la solution
                # courante → impossible de flipper vers la solution miroir.
                success, rvec, tvec = cv2.solvePnP(
                    self.object_points,
                    ordered_points,
                    self.camera_matrix,
                    self.dist_coeffs,
                    rvec=self._prev_rvec.copy(),
                    tvec=self._prev_tvec.copy(),
                    useExtrinsicGuess=True,
                    flags=cv2.SOLVEPNP_ITERATIVE,
                )
            else:
                # --- Premier frame : solution globale robuste sans biais ---
                success, rvec, tvec = cv2.solvePnP(
                    self.object_points,
                    ordered_points,
                    self.camera_matrix,
                    self.dist_coeffs,
                    flags=cv2.SOLVEPNP_SQPNP,
                )

            if not success:
                self.reset()
                return (666, 666, "erreur pnp")

            # Mémoriser pour le prochain frame
            self._prev_rvec = rvec
            self._prev_tvec = tvec

            x_cam = tvec[0][0]
            y_cam = tvec[1][0]
            z_cam = tvec[2][0]

            # Remapping caméra → drone (convention identique à algo.py v1)
            drone_dx = -x_cam
            drone_dy =  y_cam
            drone_dz =  z_cam

            # --- Compensation d'attitude (roll / pitch) ---
            # Sans cette étape, une légère inclinaison du drone fait varier dz
            # artificiellement car le tvec est dans le repère caméra incliné.
            # On projette sur le plan horizontal monde via Ry(pitch)·Rx(roll).
            if attitude is not None:
                roll, pitch = attitude
                if not (math.isnan(roll) or math.isnan(pitch)):
                    cr, sr = math.cos(roll),  math.sin(roll)
                    cp, sp = math.cos(pitch), math.sin(pitch)
                    dx_c = drone_dx * cp + drone_dz * sp * sr
                    dy_c = drone_dy * cr - drone_dz * sr
                    dz_c = drone_dz * cr * cp - drone_dx * sp
                    drone_dx, drone_dy, drone_dz = dx_c, dy_c, dz_c

            return (drone_dx, drone_dy, drone_dz)

        except Exception as e:
            self.reset()
            return ((999, 999, str(e)),)

    def _order_points(self, pts):
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect
