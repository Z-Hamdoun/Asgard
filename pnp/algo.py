import cv2
import numpy as np
import math


class PnPLandingSystem:
    """
    Cette classe est le cerveau du système. Elle connaît la forme de la cible à chercher,
    sait repérer la couleur rose, et calcule la distance en 3D.
    """

    def __init__(self, marker_distance=0.40, net_depth=0.20):
        # 1. LA FORME DE LA CIBLE (Modèle 3D)
        # On explique à l'ordinateur à quoi ressemble notre cible dans la vraie vie.
        # marker_distance : La taille du carré (40 cm).
        # net_depth : La profondeur du point central (20 cm plus bas).
        half = marker_distance / 2
        self.h_min_d, self.s_min_d, self.v_min_d = 0, 0, 0
        self.h_max_d, self.s_max_d, self.v_max_d = 255, 100, 80
        self.h_min_d2, self.s_min_d2, self.v_min_d2 = 90, 100, 80
        self.h_max_d2, self.s_max_d2, self.v_max_d2 = 115, 255, 255

        self.h_min_b, self.s_min_b, self.v_min_b = 90, 0, 200
        self.h_max_b, self.s_max_b, self.v_max_b = 115, 255, 255
        self.params = {
            "dark1": {"low": [0, 0, 0], "high": [255, 100, 80]},
            "dark2": {"low": [90, 100, 80], "high": [115, 255, 175]},
            "bright1": {"low": [90, 0, 175], "high": [115, 255, 235]},
            "bright2": {"low": [0, 0, 235], "high": [255, 255, 255]},
        }
        # On définit les 5 points dans l'espace (X, Y, Z) en mètres.
        self.object_points = np.array(
            [
                [
                    0,
                    0,
                    net_depth,
                ],  # Point 1 : Le centre (enfoncé de 20cm, donc Z est positif)
                [-half, -half, 0],  # Point 2 : Coin Haut-Gauche
                [half, -half, 0],  # Point 3 : Coin Haut-Droit
                [half, half, 0],  # Point 4 : Coin Bas-Droit
                [-half, half, 0],  # Point 5 : Coin Bas-Gauche
            ],
            dtype=np.float32,
        )

        # 2. LES YEUX DE LA CAMÉRA (Matrice intrinsèque)
        # C'est la "paire de lunettes" de la caméra. Cela décrit comment sa lentille
        # déforme la réalité. Ici, on utilise des valeurs standards pour une webcam de PC.
        self.camera_matrix = np.array(
            [[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32
        )
        self.dist_coeffs = np.zeros((4, 1))
        self.min_contour_area = 50
        self.max_contour_area = 1600
        # Le Blanc/Bleu clair en HSV a une saturation basse et une valeur (luminosité) très haute.
        # (Cette deuxième plage est vide/inutile ici, mais gardée pour la structure de l'algo)

        # 4. CRITÈRES POUR RECONNAÎTRE UNE TACHE
        self.max_uncircularity_ratio = (
            0.15  # La tache doit être à peu près ronde ou carrée
        )
        # Configuration des seuils (à charger via sliders ou fichier)

    def _get_masks(self, hsv):
        """Génère et combine les masques isolés."""
        mask_d1 = cv2.inRange(
            hsv,
            np.array(self.params["dark1"]["low"]),
            np.array(self.params["dark1"]["high"]),
        )
        mask_d2 = cv2.inRange(
            hsv,
            np.array(self.params["dark2"]["low"]),
            np.array(self.params["dark2"]["high"]),
        )
        mask_b1 = cv2.inRange(
            hsv,
            np.array(self.params["bright1"]["low"]),
            np.array(self.params["bright1"]["high"]),
        )
        mask_b2 = cv2.inRange(
            hsv,
            np.array(self.params["bright2"]["low"]),
            np.array(self.params["bright2"]["high"]),
        )

        mask_dark = cv2.bitwise_or(mask_d1, mask_d2)
        mask_bright = cv2.bitwise_or(mask_b1, mask_b2)

        return mask_dark, mask_bright

    def _is_circular(self, cnt, area):
        """Vérifie si une forme est approximativement ronde."""
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            return False
        circularity = 4 * np.pi * (area / (perimeter**2))
        return 0.5 < circularity < 1.5

    def get_contours(self, frame):
        if frame is None:
            return [], None, None

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask_dark, mask_bright = self._get_masks(hsv)

        # On cherche les contours sur le masque SOMBRE uniquement pour la structure externe
        # ou sur un combined_mask si on veut boucher les trous.
        # Ici, on utilise le combined pour avoir la forme pleine.
        combined = cv2.bitwise_or(mask_dark, mask_bright)
        contours, hierarchy = cv2.findContours(
            combined, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )

        results = []
        if hierarchy is None:
            return [], mask_dark, mask_bright

        for i, cnt in enumerate(contours):
            # 1. Est-ce un contour parent (externe) ?
            if hierarchy[0][i][3] == -1:
                area_l = cv2.contourArea(cnt)

                if 1000 > area_l > 50 and self._is_circular(cnt, area_l):
                    child_idx = hierarchy[0][i][2]

                    if child_idx != -1:
                        child_cnt = contours[child_idx]
                        area_s = cv2.contourArea(child_cnt)

                        # --- LA CORRECTION EST ICI ---
                        # On vérifie que le centre du petit contour est BLANC dans le masque CLAIR
                        M_s = cv2.moments(child_cnt)
                        if M_s["m00"] > 0:
                            cx_s = int(M_s["m10"] / M_s["m00"])
                            cy_s = int(M_s["m01"] / M_s["m00"])

                            # On vérifie si ce point appartient au masque bright
                            if mask_bright[cy_s, cx_s] > 0:
                                M_l = cv2.moments(cnt)
                                cx_l, cy_l = int(M_l["m10"] / M_l["m00"]), int(
                                    M_l["m01"] / M_l["m00"]
                                )
                                results.append(((cx_l, cy_l), area_l, cnt, child_cnt))

        return results, mask_dark, mask_bright

    def get_landing_vector(self, frame, verbose=False):
        """
        C'est ici qu'on calcule la distance en mètres entre la caméra et la cible.
        """
        # Étape 1 : On récupère les 5 taches roses sur l'image
        valid_contours = self.get_contours(frame)
        if valid_contours is None:
            return None, []

        # Étape 2 : On cherche le centre exact (en pixels) de chaque tache
        points_2d = []
        for c in valid_contours:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                points_2d.append([cX, cY])

        if len(points_2d) != 5:
            return None, points_2d

        if verbose:
            print("[PnP] SUCCÈS : 5 points trouvés ! Calcul en cours...")

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
                return None, points_2d

            # tvec contient notre position par rapport à la caméra
            x_cam = tvec[0][0]  # Décalage gauche/droite
            y_cam = tvec[1][0]  # Décalage haut/bas
            z_cam = tvec[2][0]  # Profondeur (distance)

            # Étape 5 : Traduction pour le Drone
            # On réorganise les axes pour que ce soit logique pour le pilotage d'un drone
            drone_dx = -x_cam  # Avant/Arrière
            drone_dy = y_cam  # Gauche/Droite
            drone_dz = z_cam  # Altitude relative
            return (drone_dx, drone_dy, drone_dz), points_2d

        except Exception as e:
            if verbose:
                print(f"[PnP] ERREUR : {e}")
            return None, points_2d

    def _order_points(self, pts):
        """
        Trie les points pour savoir qui est qui (centre, haut-gauche, etc.).
        """
        # Le point le plus proche du milieu de tous les autres est forcément notre point Central
        mean = np.mean(pts, axis=0)
        dists = np.linalg.norm(pts - mean, axis=1)
        center_idx = np.argmin(dists)
        center = pts[center_idx]

        # Les 4 autres sont les coins
        corners = np.delete(pts, center_idx, axis=0)

        # On trie les coins en tournant autour du centre (comme les aiguilles d'une montre)
        def angle_sort(p):
            return math.atan2(p[1] - center[1], p[0] - center[0])

        corners = sorted(corners, key=angle_sort)

        # On renvoie la liste rangée : Centre en premier, suivi des 4 coins
        return np.array([center] + corners, dtype=np.float32)
