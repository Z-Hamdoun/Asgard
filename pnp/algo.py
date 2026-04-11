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
        self.min_contour_area = 100
        self.max_contour_area = 600
        # Le Blanc/Bleu clair en HSV a une saturation basse et une valeur (luminosité) très haute.
        # (Cette deuxième plage est vide/inutile ici, mais gardée pour la structure de l'algo)

        # 4. CRITÈRES POUR RECONNAÎTRE UNE TACHE
        self.max_uncircularity_ratio = (
            0.15  # La tache doit être à peu près ronde ou carrée
        )

    def get_contours(self, frame):
        # 1. On sépare les canaux : Bleu, Vert, Rouge
        # Dans OpenCV, l'image est en BGR. L'index 0 est le Bleu.
        b_channel = frame[:, :, 0]

        # 2. On floute pour lisser
        blurred = cv2.GaussianBlur(b_channel, (5, 5), 0)

        # 3. On cherche ce qui est TRES bleu (proche de 255 sur le canal bleu)
        # On utilise un seuil haut pour ignorer le reste
        _, mask = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)

        # 4. Filtre de sécurité : on vérifie en HSV que c'est bien dans la zone "Bleu"
        # car un point blanc pur est aussi très fort en bleu.
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # Plage large pour le bleu (environ 100 à 130 en OpenCV)
        lower_blue = np.array([100, 50, 50])
        upper_blue = np.array([135, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # On combine : il faut que ce soit fort en canal Bleu ET que la teinte soit bleue
        final_mask = cv2.bitwise_and(mask, blue_mask)

        # 5. Nettoyage
        final_mask = cv2.erode(final_mask, None, iterations=2)
        final_mask = cv2.dilate(final_mask, None, iterations=2)

        # 6. Recherche des contours
        contours, _ = cv2.findContours(
            final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        valid_contours = []
        for c in contours:
            if cv2.contourArea(c) > self.min_contour_area:
                print(cv2.contourArea(c))
                valid_contours.append(c)

        return sorted(valid_contours, key=cv2.contourArea, reverse=True)[:5]

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
