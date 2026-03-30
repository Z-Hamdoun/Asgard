import cv2
import numpy as np
import math

class PnPLandingSystem:
    def __init__(self, marker_distance=0.40, net_depth=0.20, laptop=False):
        """
        Args:
            marker_distance (float): Coté du carré formé par les coins (en mètres), il faut bien le mesurer!.
            net_depth (float): Profondeur du filet (distance verticale entre cadre et centre) en mètres, en vrai c'est pas si important,
            sauf pour un deplacement verticala.
        """
        # Modele 3D, Ordre : Centre, TL, TR, BR, BL
        half = marker_distance / 2
        
        self.object_points = np.array([
            [0, 0, net_depth],  # Centre (au fond du filet, donc le z est positif)
            [-half, -half, 0],  # Top-Left z = 0
            [half, -half, 0],   # Top-Right
            [half, half, 0],    # Bottom-Right
            [-half, half, 0]    # Bottom-Left
        ], dtype=np.float32)

        # Calibration : A changer selon PI Camera ou Gazebo
        self.camera_matrix = np.array([
            [600, 0, 320],
            [0, 600, 240],
            [0, 0, 1]
        ], dtype=np.float32)
        
        if laptop :
            self.camera_matrix = np.array([
                [1000, 0, 640],
                [0, 1000, 360],
                [0, 0, 1] ], dtype=np.float32)
            
        self.dist_coeffs = np.zeros((4,1))

        # Seuils couleurs magenta (utilisez un site pour visualiser ou choisir la couleur)
        self.lower_hsv1 = np.array([120, 50, 50])
        self.upper_hsv1 = np.array([179, 255, 255])
        self.lower_hsv2 = np.array([0, 70, 50])
        self.upper_hsv2 = np.array([10, 255, 255])
        
        # Parametres de detection
        self.min_contour_area = 5
        self.iterations = 0 # facultatif pour eliminer le bruit

    def get_landing_vector(self, frame, verbose=False):
        """
        Retourne (dx, dy, dz) en mètres dans le repère du drone (Body Frame).
        dx : + = Cible est devant
        dy : + = Cible est a droite
        dz : + = Cible est en bas (altitude relative)
        attention cela depend de l'orientation du drone et de la camera donc c'est possible qu'il faut ajouter des signes -
        """
        if frame is None:
            if verbose: print("[PnP] Erreur: Image vide (None)")
            return None

        # Traitement Image
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_hsv1, self.upper_hsv1) + \
               cv2.inRange(hsv, self.lower_hsv2, self.upper_hsv2)
        
        opening = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3,3), np.uint8), iterations=self.iterations)
        closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8), iterations=self.iterations)
        
        contours, _ = cv2.findContours(closing, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours = []
        for c in contours:
            if cv2.contourArea(c) > self.min_contour_area:
                valid_contours.append(c)
        
        if verbose:
            print(f"[PnP] Candidats (Rose) trouvés : {len(valid_contours)}")

        valid_contours = sorted(valid_contours, key=cv2.contourArea, reverse=True)[:5]

        points_2d = []
        for c in valid_contours:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                points_2d.append([cX, cY])

        if len(points_2d) != 5:
            if verbose: print(f"[PnP] ECHEC : Seulement {len(points_2d)} points valides sur 5 requis.")
            return None 

        if verbose: print("[PnP] SUCCÈS : 5 points trouvés ! Calcul en cours...")

        # Tri et PnP
        try:
            ordered_points = self._order_points(np.array(points_2d, dtype=np.float32))
            
            flags = cv2.SOLVEPNP_SQPNP 

            success, rvec, tvec = cv2.solvePnP(
                self.object_points, 
                ordered_points, 
                self.camera_matrix, 
                self.dist_coeffs,
                flags=flags
            )

            if not success: 
                if verbose: print("[PnP] ECHEC : solvePnP a échoué.")
                return None

            # tvec est dans le repère de la camera :
            # x_cam = Droite/Gauche image
            # y_cam = Haut/Bas image (Y vers le bas)
            # z_cam = Profondeur
            x_cam = tvec[0][0]
            y_cam = tvec[1][0]
            z_cam = tvec[2][0]

            # Conversion au repere du drone (Body Frame FRD)
            # Hypothese : Camera pointe vers le bas, haut de l'image = Avant Drone
            
            # Axe X (Avant/Arriere)
            # Si la cible est en haut de l'image (y_cam negatif), elle est devant le drone (dx positif).
            # Donc dx = -y_cam
            drone_dx = -x_cam # a changer si necessaire!!!!!

            # Axe Y (Gauche/Droite)
            # Si la cible est à droite de l'image (x_cam positif), elle est à DROITE du drone (dy positif).
            # Donc dy = x_cam
            drone_dy = y_cam

            # Axe Z (Altitude)
            # z_cam est la distance devant la caméra, donc l'altitude relative.
            drone_dz = z_cam
            
            return (drone_dx, drone_dy, drone_dz)
            
        except Exception as e:
            if verbose: print(f"[PnP] ERREUR CRITIQUE : {e}")
            return None

    def _order_points(self, pts):
        mean = np.mean(pts, axis=0)
        dists = np.linalg.norm(pts - mean, axis=1)
        center_idx = np.argmin(dists)
        center = pts[center_idx]

        corners = np.delete(pts, center_idx, axis=0)

        def angle_sort(p):
            return math.atan2(p[1] - center[1], p[0] - center[0])

        corners = sorted(corners, key=angle_sort)
        
        return np.array([center] + corners, dtype=np.float32)