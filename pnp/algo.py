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

# Récupère le dossier où se trouve le présent fichier (algo.py)
current_dir = os.path.dirname(os.path.abspath(__file__))

# Construit le chemin complet vers logic.so
lib_path = os.path.join(current_dir, "logic.so")

# Charge la bibliothèque avec le chemin absolu
try:
    lib = ctypes.CDLL(lib_path)
except OSError as e:
    print(f"Erreur : Impossible de trouver la lib C à l'adresse {lib_path}")
    raise e
lib.find_nested_triplets.argtypes = [
    ctypes.POINTER(BBox),
    ctypes.c_int,
    ctypes.POINTER(Result),
    ctypes.c_int,
]
lib.find_nested_triplets.restype = ctypes.c_int


class PnPLandingSystem:
    """
    Cette classe est le cerveau du système. Elle connaît la forme de la cible à chercher,
    sait repérer la couleur rose, et calcule la distance en 3D.
    """

    def __init__(self, marker_distance=0.33, net_depth=0.20):
        # 1. LA FORME DE LA CIBLE (Modèle 3D)
        # On explique à l'ordinateur à quoi ressemble notre cible dans la vraie vie.
        # marker_distance : La taille du carré (40 cm).
        # net_depth : La profondeur du point central (20 cm plus bas).
        half = marker_distance / 2
        # On définit les 5 points dans l'espace (X, Y, Z) en mètres.
        self.object_points = np.array(
            [
                [-half, -half, 0],  # Point 2 : Coin Haut-Gauche
                [half, -half, 0],  # Point 3 : Coin Haut-Droit
                [half, half, 0],  # Point 4 : Coin Bas-Droit
                [-half, half, 0],  # Point 5 : Coin Bas-Gauche
            ],
            dtype=np.float32,
        )
        self._camera_matrix = np.array(
            [
                [376.91194, 0.00000, 425.07994],
                [0.00000, 380.07917, 245.66015],
                [0.00000, 0.00000, 1.00000],
            ],
            dtype=np.float64,
        )

        self._dist_coeffs = np.array(
            [-0.00284, 0.09082, 0.00265, -0.00063, -0.07958], dtype=np.float64
        )

    def _is_circular(self, cnt, area):
        """Vérifie si une forme est approximativement ronde."""
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            return False
        circularity = 4 * np.pi * (area / (perimeter**2))
        return 0.7 < circularity < 1.3

    def get_contours(self, frame):
        t0 = time.time()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        t1 = time.time()
        gray = cv2.normalize(gray, gray.copy(), 0, 255, cv2.NORM_MINMAX)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        t2 = time.time()
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY_INV)

        t3 = time.time()
        contours, hierarchy = cv2.findContours(
            thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )

        t4 = time.time()

        results = []

        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)

            if area > 5000 or area < 20:

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
                    "contours": cnt,
                    "area": area,
                    "limits": {"x_min": x, "x_max": x + w, "y_min": y, "y_max": y + h},
                }
            )

        t5 = time.time()
        results_nested = self.get_nested_squares(results)
        ids_first = {t[0] for t in results_nested}
        ids_second = {t[1] for t in results_nested}
        ids_third = {t[2] for t in results_nested}

        t6 = time.time()
        # 3. On filtre la liste d'origine
        results_corrects_petite_tache = [
            dico for dico in results if dico["id"] in ids_first
        ]
        results_corrects_moyenne_tache = [
            dico for dico in results if dico["id"] in ids_second
        ]
        results_corrects_grande_tache = [
            dico for dico in results if dico["id"] in ids_third
        ]

        t7 = time.time()
        print(
            f"bgr2gray: {t1-t0}, normalize: {t2-t1}, threshold: {t3-t2}, contours: {t4-t3}, trouve centre: {t5-t4},nested squares: {t6-t5}, liste taches: {t7-t6}, total{t7-t1}"
        )

        # --- Affichage du résultat ---
        return (
            results_corrects_petite_tache,
            results_corrects_moyenne_tache,
            results_corrects_grande_tache,
            (thresh, blurred),
        )

    def get_nested_squares(self, data):
        n = len(data)
        # Préparation des données pour le C
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

        # Buffer pour les résultats (ajustez la taille max selon vos besoins)
        max_results = 1000
        c_results = (Result * max_results)()

        # Appel de la fonction C
        num_found = lib.find_nested_triplets(c_boxes, n, c_results, max_results)

        # Conversion en liste de tuples Python
        return [
            (c_results[i].id1, c_results[i].id2, c_results[i].id3)
            for i in range(num_found)
        ]

    def get_landing_vector(self, frame, verbose=False):
        """
        C'est ici qu'on calcule la distance en mètres entre la caméra et la cible.
        """
        t = time.time()
        # Étape 1 : On récupère les 5 taches roses sur l'image
        a, b, Taches, d = self.get_contours(frame)

        if len(Taches) != 4:
            return None, (a, b, Taches, d), time.time() - t
        points_2d = [tache["center"] for tache in Taches]

        try:
            # Étape 3 : On devine quel point est le centre, et lesquels sont les coins
            ordered_points = self._order_points(np.array(points_2d, dtype=np.float32))

            # Étape 4 : LE CALCUL MAGIQUE (PnP)
            # L'ordinateur compare le modèle 3D parfait avec les points 2D déformés sur l'image.
            # Il en déduit comment la caméra est positionnée pour voir cette déformation.
            success, rvec, tvec = cv2.solvePnP(
                self.object_points,
                ordered_points,
                self.camera_matrix,
                self.dist_coeffs,
                flags=cv2.SOLVEPNP_SQPNP,
            )

            if not success:
                return None, (a, b, Taches, d), time.time() - t

            # tvec contient notre position par rapport à la caméra
            x_cam = tvec[0][0]  # Décalage gauche/droite
            y_cam = tvec[1][0]  # Décalage haut/bas
            z_cam = tvec[2][0]  # Profondeur (distance)

            # Étape 5 : Traduction pour le Drone
            # On réorganise les axes pour que ce soit logique pour le pilotage d'un drone
            drone_dx = -x_cam  # Avant/Arrière
            drone_dy = y_cam  # Gauche/Droite
            drone_dz = z_cam  # Altitude relative
            return (drone_dx, drone_dy, drone_dz), (a, b, Taches, d), time.time() - t

        except Exception as e:

            return None, (a, b, Taches, d), time.time() - t

    def _order_points(self, pts):
        """
        Trie les 4 points dans l'ordre : Haut-Gauche, Haut-Droit, Bas-Droit, Bas-Gauche.
        """
        rect = np.zeros((4, 2), dtype="float32")

        # Somme des coordonnées : x + y
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # Haut-Gauche
        rect[2] = pts[np.argmax(s)]  # Bas-Droit

        # Différence des coordonnées : y - x
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # Haut-Droit
        rect[3] = pts[np.argmax(diff)]  # Bas-Gauche

        return rect
