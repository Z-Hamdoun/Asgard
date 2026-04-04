import cv2
import cv2.aruco as aruco
import numpy as np
import time
from typing import Sequence

# --- FAUX LOGGER POUR ÉVITER LES ERREURS ---
class MockLogger:
    def log(self, msg, wanna_print=True, exception=False):
        if wanna_print:
            print(msg)

# --- CLASSE DE TEST CAMERA PC ---
class TestCameraPC:
    def __init__(self, aruco_id=4, aruco_size_m=0.15):
        print("[INIT] Démarrage de la webcam PC...")
        self.cap = cv2.VideoCapture(0)
        
        # --- CARACTÉRISTIQUES MSI KATANA B13V ---
        self._resolution = (1280, 720)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        self._camera_matrix = np.array([
            [1000.0, 0.0, 640.0],  # Fx = ~1000, Cx = 1280/2
            [0.0, 1000.0, 360.0],  # Fy = ~1000, Cy = 720/2
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)
        self._dist_coeffs = np.zeros((5, 1), dtype=np.float64)
        
        # --- PARAMÈTRES ARUCO ---
        # On passe sur le dictionnaire 6x6 (qui contient 250 marqueurs possibles)
        self._aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_250)
        self._aruco_params = aruco.DetectorParameters()
        self.aruco_id = aruco_id
        self.aruco_size = aruco_size_m
        
        # --- VARIABLES DE L'ALGO CROP ---
        self.DO_CROP = True
        self._last_scale_down = None
        self._last_crop = None
        
        # --- AUTRES DÉPENDANCES ---
        self._simulation = True # On met True pour éviter le crash lié au metadata picam2
        self.logger = MockLogger()
        self._time_boot = time.time()

    @property
    def time_boot_ms(self) -> int:
        return int((time.time() - self._time_boot) * 1000)

    def get_frame(self, affiche=False, timeout=2) -> np.ndarray:
        ret, frame = self.cap.read()
        if not ret:
            return np.zeros((720, 1280, 3), dtype=np.uint8)
        
        # Ton algo fait cv2.cvtColor(..., cv2.COLOR_RGB2GRAY), 
        # OpenCV capte en BGR par défaut, donc on renvoie du RGB pour être cohérent.
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def _camera_to_drone(self, tvec) -> tuple[float, float, float]:
        # Conversion simple pour le test PC
        dx, dy, dz = float(tvec[0]), float(tvec[1]), float(tvec[2])
        return dx, dy, dz

    # =========================================================================
    # TA FONCTION EXACTE (Copiée-Collée)
    # =========================================================================
    def analyse(self, affichage : bool = False) -> tuple[float, float, float, str | None, np.ndarray | None]:
        """Détermine les distances à effectuer pour aller sur le code Aruco."""
        #Image à un instant t
        t_begin = self.time_boot_ms
        frame = cv2.cvtColor(self.get_frame(affiche=affichage, timeout=2), cv2.COLOR_RGB2GRAY)
        last_aruco_time = self.time_boot_ms

        if self._last_scale_down is not None and self._last_crop is not None and self.DO_CROP:
            # Crop:
            frame_crop = frame[self._last_crop[0]:self._last_crop[2],self._last_crop[1]:self._last_crop[3]]

            # Scale down:
            new_width = frame_crop.shape[1] // self._last_scale_down
            new_height = frame_crop.shape[0] // self._last_scale_down
            if new_width > 50 or new_height > 50:
                frame_treated = cv2.resize(frame_crop, (new_width, new_height), interpolation=cv2.INTER_AREA)
            else:
                frame_treated = frame
                self._last_scale_down, self._last_crop = None, None
        else:
            frame_treated = frame

        # Détecter les marqueurs ArUco
        corners, ids, _ = cv2.aruco.detectMarkers(frame_treated, self._aruco_dict, parameters=self._aruco_params)
        t_marker_detect = self.time_boot_ms
        corners: Sequence[cv2.typing.MatLike]

        if ids is not None:
            for aruco_id, corner in zip(ids, corners):
                # On accepte N'IMPORTE QUEL ID ! (On commente le filtre)
                # if aruco_id != self.aruco_id:
                #     continue

                if self._last_crop is not None and self.DO_CROP:
                    corner[:,:,0] *= self._last_scale_down
                    corner[:,:,1] *= self._last_scale_down
                    corner[:,:,0] += self._last_crop[1]
                    corner[:,:,1] += self._last_crop[0]

                _, tvec, _ = cv2.aruco.estimatePoseSingleMarkers([corner], self.aruco_size, self._camera_matrix, self._dist_coeffs)
                tvec = tvec[0][0]  # Extraire le vecteur de translation

                last_crop = (
                    int(corner[:,:,1].min()), 
                    int(corner[:,:,0].min()), 
                    int(corner[:,:,1].max()), 
                    int(corner[:,:,0].max())
                )

                taille_aruco_px = (last_crop[3]-last_crop[1], last_crop[2]-last_crop[0])
                to_crop = (int(taille_aruco_px[0]*1.5) + self._resolution[0]/6, int(taille_aruco_px[1]*1.5) + self._resolution[0]/6)

                self._last_crop = (  
                                max( int(last_crop[0]-to_crop[1]), 0 ),
                                max( int(last_crop[1]-to_crop[0]), 0 ),
                                min( int(last_crop[2]+to_crop[1]), self._resolution[1] ), 
                                min( int(last_crop[3]+to_crop[0]), self._resolution[0] )
                )
                self._last_scale_down = max(min(min(taille_aruco_px)//32, 10), 1)

                dx, dy, dz = self._camera_to_drone(tvec=tvec)
                self.logger.log(f"[LOG] ID {aruco_id[0]}, x={dx:.2f} m, y={dy:.2f} m, z={dz:.2f} m, aruco {taille_aruco_px}, last_crop:{last_crop}", wanna_print=False)

                info = f"id:{int(aruco_id[0])},rec:{round(last_aruco_time-t_begin, 4)},det:{round(t_marker_detect-last_aruco_time, 4)},sd{self._last_scale_down}"
                return dx, dy, dz, info, frame_treated
                
        self._last_crop = None
        self._last_scale_down = None
        # CORRECTIF : On renvoie 'frame_treated' au lieu de 'None' pour toujours voir la caméra !
        return 0, 0, 0, None, frame_treated

    def close(self):
        self.cap.release()
        cv2.destroyAllWindows()


# =========================================================================
# SCRIPT PRINCIPAL DE TEST
# =========================================================================
if __name__ == "__main__":
    print("--- BANC DE TEST ARUCO SUR PC ---")
    # Modifie l'ID et la taille physique de ton ArUco de test ici (en mètres)
    TARGET_ID = 4
    ARUCO_SIZE_METERS = 0.15 
    
    camera = TestCameraPC(aruco_id=TARGET_ID, aruco_size_m=ARUCO_SIZE_METERS)
    
    try:
        while True:
            # Appel de ta fonction
            dx, dy, dz, info, frame_treated = camera.analyse(affichage=False)
            
            # Affichage debug
            if frame_treated is not None:
                # Ta fonction renvoie une image traitée en niveaux de gris (car cvtColor GRAY plus haut)
                # On la passe en BGR pour pouvoir écrire du texte en couleur dessus
                display_frame = cv2.cvtColor(frame_treated, cv2.COLOR_GRAY2BGR)
                
                if info is not None:
                    # L'ArUco a été trouvé !
                    # On extrait l'ID détecté depuis la chaine info
                    detected_id = info.split(',')[0].split(':')[1]
                    text1 = f"TARGET LOCKED (ID: {detected_id})"
                    text2 = f"X: {dx:.2f}m | Y: {dy:.2f}m | Z: {dz:.2f}m"
                    cv2.putText(display_frame, text1, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    cv2.putText(display_frame, text2, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    # On affiche la zone crop en rouge
                    if camera.DO_CROP and camera._last_crop:
                        c = camera._last_crop
                        cv2.rectangle(display_frame, (c[1], c[0]), (c[3], c[2]), (0, 0, 255), 2)
                        cv2.putText(display_frame, "CROP ACTIF", (c[1], c[0]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                else:
                    cv2.putText(display_frame, "RECHERCHE ARUCO 6x6...", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                cv2.imshow("Test ArUco", display_frame)

            # Quitter avec 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\nArrêt manuel.")
    finally:
        camera.close()
        print("Webcam libérée.")