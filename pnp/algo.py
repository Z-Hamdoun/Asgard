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

    def get_contours(self, frame):
        if frame is None:
            return [], None, None

        # 1. Conversion en HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 2. Plages de couleurs
        lower_dark = np.array([140, 50, 0])  # Bleu marine / Noir
        upper_dark = np.array([190, 255, 150])  # Bleu moyen, luminosité plafonnée
        lower_bright = np.array([130, 0, 190])  # Bleu clair / Désaturé
        upper_bright = np.array([180, 255, 255])
        # Masques
        mask_dark = cv2.inRange(hsv, lower_dark, upper_dark)
        mask_bright = cv2.inRange(hsv, lower_bright, upper_bright)

        # Union pour l'analyse de hiérarchie
        combined_mask = cv2.bitwise_or(mask_dark, mask_bright)

        # 3. Trouver les contours avec hiérarchie (CCOMP pour parents/enfants directs)
        contours, hierarchy = cv2.findContours(
            combined_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )

        results = []

        if hierarchy is None:
            return results, None, None

        for i, cnt in enumerate(contours):
            # On cherche un contour parent (la grosse tache)
            if hierarchy[0][i][3] == -1:
                area_large = cv2.contourArea(cnt)

                if area_large > 50:
                    # Vérification circularité
                    perimeter = cv2.arcLength(cnt, True)
                    if perimeter == 0:
                        continue
                    circularity = 4 * np.pi * (area_large / (perimeter * perimeter))

                    if 0.5 < circularity < 1.5:
                        # Chercher l'enfant direct (la petite tache interne)
                        child_idx = hierarchy[0][i][2]

                        if child_idx != -1:
                            child_cnt = contours[child_idx]
                            area_small = cv2.contourArea(child_cnt)

                            # On valide que l'enfant est bien plus petit
                            if 0 < area_small < area_large:
                                # Calcul du centre
                                M = cv2.moments(cnt)
                                if M["m00"] != 0:
                                    cx = int(M["m10"] / M["m00"])
                                    cy = int(M["m01"] / M["m00"])

                                    # On renvoie le tuple complet
                                    # ( (x, y), Aire, Contour_Gros, Contour_Petit )
                                    results.append(
                                        ((cx, cy), area_large, cnt, child_cnt)
                                    )

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
