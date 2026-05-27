import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import cv2
import cv2.aruco as aruco
import numpy as np
from typing import Sequence
import time
import threading

from utils.class_Logger import Logger

RESOLUTION_CAMERA_GAZEBO = (848, 480)  # A vérifier


# Note importante : Les fonctions d'analyse ArUco sont incompréhensibles (même par les auteurs désormais)
# Si elles marchent pas, cherchez pas et refaites les lol


class Camera:
    """Crée une connection avec une caméra."""

    def __init__(
        self,
        simulation: str | None,
        resolution_id: int = 1,
        do_crop: bool = True,
        camera_topic: str = "/world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image",
        gstream_port: int = 5600,
        logger: Logger = Logger(),
    ):
        """Initialise la caméra.

        Note:
            Pour simulation:
                - None -> Pi Camera
                - SITL -> Camera Gazebo via Topic
                - HITL -> Camera Gazebo via Gstream

        Args:
            simulation (str | None): 'SITL' ou 'HITL' ou None.
            resolution_id (int): Numéro de résolution. Inutile sur Gazebo.
            do_crop (bool): Indique si on veut utiliser l'algorithme de crop pour l'analyse ArUco.
            camera_topic (str): Topic de la caméra Gazebo.
            gstream_port (int): Port utilisé par Gstream (sur une RPI par exemple).
            logger (Logger): Logger utilisé.
        """
        if simulation not in ["SITL", "HITL", None]:
            raise ValueError(f"simulation ({simulation}) not in 'SITL', 'HITL', None")

        # -----------------
        # Variables de base
        # -----------------

        self.logger: Logger = logger
        """Logger utilisé."""

        self._resolution: tuple[int, int] = None
        """Résolution de la caméra."""

        self._simulation: str | None = simulation
        """SITL, HITL ou None."""

        self._frame: np.ndarray | None = None
        """Dernière frame obtenue sur Gazebo."""

        self._time_frame: float = time.time()
        """Temps de la dernière frame obtenue sur Gazebo."""

        self._time_boot: float = time.time()
        """Temps de boot."""

        self._picam2 = None
        """Objet Pi Camera."""

        self._node = None
        """Objet Node, permettant de s'abonner au topic Gazebo."""

        self._pipeline = None
        """Pipeline Gstream."""

        self._appsink = None
        """Appsing Gstream."""

        self._Gst = None
        """Gst."""

        self._stop_gstream_thread: threading.Event | None = None
        """Variable permettant l'arrêt du thread Gstream."""

        self._gstream_thread_stopped: threading.Event | None = None
        """Variable indiquant si le thread Gstream est arrêté ou non."""

        self._gstream_thread: threading.Thread = None
        """Thread Gstream."""

        # ---------------------------
        # Initialisation de la caméra
        # ---------------------------

        # Recherche de la résolution de la caméra
        if simulation is None:
            # A vérifier
            if resolution_id == 1:
                self._resolution = (640, 480)
            elif resolution_id == 2:
                self._resolution = (1296, 972)
            elif resolution_id == 3:
                self._resolution = (1920, 1080)
            elif resolution_id == 4:
                self._resolution = (2592, 1944)
            else:
                raise ValueError("Resolution à choisir entre 1 et 4")
        else:
            # Résolution de la caméra sur Gazebo
            self._resolution = RESOLUTION_CAMERA_GAZEBO

        try:
            if simulation is None:  # On simule pas -> Pi Camera
                self.logger.log("[INFO] Intializing Pi Camera..")
                # On importe le module
                from picamera2 import Picamera2

                # Initialisation de la Pi Camera 2
                self._picam2 = Picamera2()
                self._picam2.preview_configuration.main.size = (
                    self._resolution[0],
                    self._resolution[1],
                )
                self._picam2.preview_configuration.main.format = "RGB888"
                self._picam2.preview_configuration.controls.FrameRate = 30
                self._picam2.configure("preview")
                self._picam2.start()
                # self._picam2.set_controls({"ExposureTime": 3500})
                self._picam2.set_controls(
                    {
                        "AeEnable": True,  # Keep auto-exposure ON
                        "ExposureValue": -1,
                    }
                )
                # "AeExposureMode": "Short"})
                time.sleep(2)  # Laisser le temps à la caméra de s'initialiser
            elif simulation == "SITL":  # On est sur Gazebo via topic
                self.logger.log("[INFO] Intializing Gazebo camera")
                # On importe les modules
                from gz.transport13 import Node
                from gz.msgs10.image_pb2 import Image

                # On s'abonne au topic
                self._node = Node()
                subscribed = self._node.subscribe(
                    Image, camera_topic, self._image_callback
                )
                if not subscribed:
                    raise RuntimeError(f"Failed to subscribe to topic: {camera_topic}")
            else:  # HITL -> Gstream
                self.logger.log("[INFO] Intializing Gstream camera")
                # On importe les modules
                import gi

                gi.require_version("Gst", "1.0")
                from gi.repository import Gst, GObject

                self._Gst = Gst
                self._Gst.init(None)

                pipeline_str = (
                    f"udpsrc port={gstream_port} "
                    "caps=application/x-rtp,media=video,encoding-name=H264,clock-rate=90000 "
                    "! rtpjitterbuffer latency=200 "
                    "! rtph264depay ! avdec_h264 ! videoconvert "
                    "! video/x-raw,format=BGR "
                    "! appsink name=appsink emit-signals=true max-buffers=1 drop=true"
                )

                self._pipeline = self._Gst.parse_launch(pipeline_str)

                # récupérer appsink (doit exister maintenant)
                self._appsink = self._pipeline.get_by_name("appsink")
                if self._appsink is None:
                    raise RuntimeError(
                        "Impossible de récupérer appsink depuis le pipeline GStreamer. Pipeline: "
                        + pipeline_str
                    )

                # démarrer le pipeline après la vérification
                self._pipeline.set_state(self._Gst.State.PLAYING)
                # Thread
                self._stop_gstream_thread = threading.Event()
                self._gstream_thread_stopped = threading.Event()
                self._gstream_thread_stopped.set()
                self._gstream_thread = threading.Thread(
                    target=self._gstream_thread_fct, args=(), daemon=True
                )
                self._gstream_thread.start()
            self.logger.log("[SUCCESS] Camera initialized")

            # -----------------------------------
            # Charger les paramètres de la caméra
            # -----------------------------------

            self._camera_matrix: np.ndarray = None
            """Matrice de la caméra"""

            self._dist_coeffs: np.ndarray = None
            """Matrice de distorsion de la caméra"""

            if simulation is None:
                # self._camera_matrix = np.array([
                #     [600.0,   0.0, 320.0],  # Fx ~420, Cx = 320 (Largeur/2)
                #     [  0.0, 600.0, 240.0],  # Fy ~420, Cy = 240 (Hauteur/2)
                #     [  0.0,   0.0,   1.0]
                # ], dtype=np.float64)
                # self._dist_coeffs = np.array([0, 0, 0, 0, 0], dtype=np.float64) # Celle-là non plus

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

            else:
                # Matrices de la caméra Gazebo (à vérifier)
                # self._camera_matrix = np.array([
                #     [1272.5231351852417, 0.0, 648.0],
                #     [0, 1272.5229930877686, 365.0],
                #     [0, 0, 1]
                # ], dtype=np.float64)
                self._camera_matrix = np.array(
                    [
                        [205.4696273803711, 0.0, 320.0],
                        [0, 205.4696559906006, 240.0],
                        [0, 0, 1],
                    ],
                    dtype=np.float64,
                )
                self._dist_coeffs = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
            
            
            # -- Parametres e-aruco ----------------------
            # Outer: DICT_7X7_50 ID=5  - bit central noir, 61% surface noire
            # Inner: DICT_4X4_50 ID=17 - 75% surface noire, précision close-range
            #
            # Tailles physiques selon mode :
            #   SITL (Gazebo fx=205) : outer=70cm, inner=10cm  --> détectables aux
            #                          altitudes de quadrillage/atterrissage SITL
            #   Réel (Pi Camera fx=963): outer=35cm, inner=5cm
            self._aruco_dict_outer   = aruco.getPredefinedDictionary(aruco.DICT_7X7_50)
            self._aruco_dict_inner   = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
            self._detector_outer     = aruco.ArucoDetector(self._aruco_dict_outer,  aruco.DetectorParameters())
            self._detector_inner     = aruco.ArucoDetector(self._aruco_dict_inner, aruco.DetectorParameters())
            self.outer_aruco_id      = 5
            self.inner_aruco_id      = 17
            if simulation:
                self.outer_aruco_size = 0.70   # Gazebo : 70cm - ~29px à 5m (fx=205)
                self.inner_aruco_size = 0.10   # Gazebo : 10cm - ~41px à 0.4m
            else:
                self.outer_aruco_size = 0.35   # Réel : 7 × 5cm
                self.inner_aruco_size = 0.05   # Réel : length_inner
            self._inner_crop         = None
            self._inner_scale_down   = None
            self._outer_crop         = None
            self._outer_scale_down   = None
            # -------------------------------------------------------------------
            
            # Créer le dictionnaire ArUco et les paramètres de détection
            self._aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_250)
            """Dictionnaire ArUco."""

            self._aruco_params = aruco.DetectorParameters()
            """Paramètres de détection ArUco."""

            # Code Aruco (à changer)
            self.aruco_id: int = 0
            """ID du code ArUco à chercher."""
            self.aruco_size: float = 0
            """Taille du code ArUco en m."""
            if self._simulation:
                self.aruco_id = 4
                self.aruco_size = 0.62  # Taille ArUco sur Gazebo
            else:
                self.aruco_id = 4
                self.aruco_size = 0.1

            # Variables utilisées pour la détection ArUco
            self.DO_CROP: bool = do_crop
            """Indique si on utilise l'algorithme de crop ou non."""
            self._last_scale_down = None
            self._last_crop = None
            self._already_found_once = False
            self._last_found_altitude = None
            self._last_found_distance = None
            self._last_found_px_size = None
            self._kernel = np.ones((3, 3), np.uint8)
            self._kernel2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))

            self.logger.log("[SUCCESS] Camera parameters loaded")
        except Exception as e:
            # Gestion de l'erreur : fermeture de la caméra
            if simulation is None:
                # On ferme proprement la caméra
                try:
                    self._picam2.stop()
                except Exception:
                    pass
                try:
                    self._picam2.close()
                except Exception:
                    pass
            elif simulation == "HITL":
                try:
                    self._stop_gstream_thread.set()
                    self._gstream_thread_stopped.wait(timeout=10)
                except Exception:
                    pass
                try:
                    self._pipeline.set_state(self._Gst.State.NULL)
                except Exception:
                    pass
            raise e

    # ------------
    # Informations
    # ------------

    @property
    def resolution(self) -> tuple[int, int]:
        """Résolution de la caméra."""
        return self._resolution

    @property
    def time_boot_ms(self) -> int:
        """Temps depuis la création de l'objet."""
        return int((time.time() - self._time_boot) * 1e3)

    # ------------------------
    # Capture d'image + outils
    # ------------------------

    def get_frame(
        self, affiche: bool = False, timeout: float = 5, save=False
    ) -> np.ndarray:
        """
        Renvoie la dernière frame capturée, et affiche ou non celle-ci.

        Args:
            affiche (bool): Si l'utilisateur veut afficher la frame.
            timeout (float): Temps d'attente maximum de l'image sur le simulateur en secondes.

        Returns:
            np.ndarray: L'image capturée en format BGR, ou None si le timeout est dépassé (Gazebo).
        """
        if self._simulation is None:  # Pi Camera
            frame = self._picam2.capture_array()
        else:  # Camera Gazebo ou Gstream
            start_time = time.time()
            time_since_boot_waiting = self.time_boot_ms
            # On attend la prochaine image (on prend pas ce qu'on a déjà capturé, comme sur la PiCam)
            while (
                self._frame is None or not self._time_frame >= time_since_boot_waiting
            ):
                if time.time() - start_time > timeout:
                    self.logger.log("[WARNING] Timeout: No frame received")
                    return None
                time.sleep(0.01)
            frame = self._frame

        if affiche:
            if frame is not None:
                cv2.imshow("Camera", frame)
                if self._simulation:
                    cv2.waitKey(50)
        # Attention à bien renvoyer la frame en RGB
        if save:
            cv2.imwrite("image.jpg", frame)
        return frame  # cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    def encode(self, img: np.ndarray, quality: int = 80) -> tuple[bytes, int, int]:
        """Encode une image en bytes.

        Args:
            img (np.ndarray): Image à encoder.
            quality (int): 1 (qualité très faible, image très compressée) et 100 (qualité maximale, image peu compressée)

        Returns:
            tuple:
                - **image** (*bytes*) - Image en bytes.
                - **height** (*float*) - Hauteur en px.
                - **width** (*float*) - Largeur en px.
        """
        height, width = img.shape
        _, img_encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return img_encoded.tobytes(), height, width

    def save_image(self, image: np.ndarray) -> None:
        """Enregistre l'image dans un fichier avec un nom basé sur l'horodatage actuel.

        Args:
            image (np.ndarray): Image à enregistrer.
        """
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"image_{timestamp}.jpg"
        cv2.imwrite(filename, image)

    # ----------------------------------------------------------------
    # Analyse ArUco (changez si ça marche pas et que vous avez la foi)
    # ----------------------------------------------------------------

    def _camera_to_drone(
        self, tvec: list[float, float, float]
    ) -> tuple[float, float, float]:
        """Fonction qui transforme le vecteur tvec en déplacements.

        Args:
            tvec (list[float, float, float]): Vecteur tvec donné par la caméra.

        Returns:
            tuple:
                - **dx** (*float*) - Déplacement vers l'avant du drone (m).
                - **dy** (*float*) - Déplacement vers la droite du drone (m).
                - **dz** (*float*) - Déplacement vers le dessous du drone (m).
        """
        dx, dy, dz = float(tvec[0]), float(tvec[1]), float(tvec[2])
        if not self._simulation:
            return -dy, dx, dz  # A vérifier   # combinaisons testees: - + / + + /
        else:
            return dx, dy, dz  # A vérifier

    def _detect_aruco_marker(
            self,
            frame: np.ndarray,
            crop_state: str,
        ):
        """
        Détecte le marqueur e-ArUco correspondant à crop_state dans frame.

        Args:
            frame      : image en niveaux de gris (full-res).
            crop_state : 'inner' ou 'outer'.

        Returns:
            (dx, dy, dz, taille_px, corner) si trouvé, None sinon.
        """
        if crop_state == 'outer':
            detector   = self._detector_outer
            target_id  = self.outer_aruco_id
            marker_size = self.outer_aruco_size
        else:
            detector   = self._detector_inner
            target_id  = self.inner_aruco_id
            marker_size = self.inner_aruco_size

        last_crop       = getattr(self, f'_{crop_state}_crop')
        last_scale_down = getattr(self, f'_{crop_state}_scale_down')

        # --- Appliquer le crop si on a une estimation précédente ---
        if last_crop is not None and last_scale_down is not None and self.DO_CROP:
            frame_crop = frame[last_crop[0] : last_crop[2], last_crop[1] : last_crop[3]]
            new_w = frame_crop.shape[1] // last_scale_down
            new_h = frame_crop.shape[0] // last_scale_down
            if new_w > 50 and new_h > 50:
                frame_search = cv2.resize(
                    frame_crop, (new_w, new_h), interpolation=cv2.INTER_AREA
                )
            else:
                frame_search = frame
                last_crop = None
                setattr(self, f"_{crop_state}_crop", None)
                setattr(self, f"_{crop_state}_scale_down", None)
        else:
            frame_search = frame

        corners, ids, _ = detector.detectMarkers(frame_search)

        if ids is None:
            return None

        for aruco_id, corner in zip(ids, corners):
            if int(aruco_id) != target_id:
                continue

            # Reconvertir en référentiel full-frame si crop actif
            if last_crop is not None and last_scale_down is not None and self.DO_CROP:
                corner = corner.copy()
                corner[:, :, 0] = corner[:, :, 0] * last_scale_down + last_crop[1]
                corner[:, :, 1] = corner[:, :, 1] * last_scale_down + last_crop[0]

            _, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                [corner], marker_size, self._camera_matrix, self._dist_coeffs
            )
            tvec = tvec[0][0]

            bbox = (
                int(corner[:, :, 1].min()),
                int(corner[:, :, 0].min()),
                int(corner[:, :, 1].max()),
                int(corner[:, :, 0].max()),
            )
            taille_px = (bbox[3] - bbox[1], bbox[2] - bbox[0])
            margin = int(max(taille_px) * 1.5) + self._resolution[0] // 6
            new_crop = (
                max(bbox[0] - margin, 0),
                max(bbox[1] - margin, 0),
                min(bbox[2] + margin, self._resolution[1]),
                min(bbox[3] + margin, self._resolution[0]),
            )
            setattr(self, f'_{crop_state}_crop',       new_crop)
            setattr(self, f'_{crop_state}_scale_down', max(min(min(taille_px) // 32, 10), 1))

            dx, dy, dz = self._camera_to_drone(tvec)
            return dx, dy, dz, taille_px, corner

        return None

    def analyse_e_aruco(self, affichage: bool = False) -> tuple:
        """
        Détecte les marqueurs e-ArUco (outer 7x7 + inner 4x4) dans une frame.

        Stratégie double marqueur (cf. papier Khazetdinov et al., SIBCON 2021) :
          - Outer (DICT_7X7_50, 36 cm) --> détectable de loin (~2-5 m),
            utilisé pour le centrage en Loiter.
          - Inner (DICT_4X4_50, 4 cm)  --> détectable de près (<~1 m),
            utilisé pour le guidage Precision Land final.

        Priorité : inner > outer (inner est plus précis, si visible on l'utilise).

        Args:
            affichage (bool): Affiche la frame si True.

        Returns:
            tuple (dx, dy, dz, info, frame) :
              - dx/dy/dz : déplacements en mètres (cf. _camera_to_drone).
              - info     : "INNER:..." | "OUTER:..." | None (aucun marqueur).
              - frame    : image gris analysée, None si rien détecté.
            Retourne (0, 0, 0, None, None) si aucun marqueur détecté.
        """
        t_begin = self.time_boot_ms

        raw_frame = self.get_frame(affiche=affichage, timeout=2)
        if raw_frame is None:
            return 0, 0, 0, None, None

        frame = cv2.cvtColor(raw_frame, cv2.COLOR_RGB2GRAY)
        t_captured = self.time_boot_ms

        # -- Priorité : marqueur INNER (précision finale, DICT_4X4_50 ID=17) -
        # En-dessous de 8px, l'estimation PnP est aberrante (faux positifs typiques : 2-3px ;
        # une vraie détection inner à 1,5m réel donne ~12px).
        _MIN_INNER_PX = 8
        result = self._detect_aruco_marker(frame, 'inner')
        if result is not None:
            dx, dy, dz, taille_px, _ = result
            if min(taille_px) < _MIN_INNER_PX:
                # Trop petit — presque certainement du bruit ; on réinitialise le crop
                # pour éviter de rester verrouillé sur ce faux positif.
                self._inner_crop = None
                self._inner_scale_down = None
                self.logger.log(
                    f"[e-ArUco INNER] rejeté (taille={taille_px} < {_MIN_INNER_PX}px)",
                    wanna_print=True
                )
            else:
                t_det = self.time_boot_ms
                info = (f"INNER:id{self.inner_aruco_id},"
                        f"sz{taille_px},"
                        f"rec{round(t_captured - t_begin, 3)},"
                        f"det{round(t_det - t_captured, 3)}")
                self.logger.log(
                    f"[e-ArUco INNER] dx={dx:.3f}m dy={dy:.3f}m dz={dz:.3f}m taille={taille_px}",
                    wanna_print=True
                )
                return dx, dy, dz, info, frame

        # Fallback : marqueur OUTER (centrage loiter, DICT_7X7_50 ID=5)
        result = self._detect_aruco_marker(frame, 'outer')
        if result is not None:
            dx, dy, dz, taille_px, _ = result
            t_det = self.time_boot_ms
            info = (
                f"OUTER:id{self.outer_aruco_id},"
                f"sz{taille_px},"
                f"rec{round(t_captured - t_begin, 3)},"
                f"det{round(t_det - t_captured, 3)}"
            )
            self.logger.log(
                f"[e-ArUco OUTER] dx={dx:.3f}m dy={dy:.3f}m dz={dz:.3f}m taille={taille_px}",
                wanna_print=True,
            )
            return dx, dy, dz, info, frame

        # -- Rien détecté -----------------------------------------------------
        if not self._simulation:
            try:
                meta = self._picam2.capture_metadata()
                self.logger.log(
                    f"[LOG] Expo={meta['ExposureTime']}µs ISO={meta['AnalogueGain']*100:.0f}",
                    wanna_print=False,
                )
            except Exception:
                pass

        return 0, 0, 0, None, None

    # 1ère fonction d'analyse, plus 'simpliste'
    def analyse(
        self, affichage: bool = False
    ) -> tuple[float, float, float, str | None, np.ndarray | None]:
        """Détermine les distances à effectuer pour aller sur le code Aruco.

        Args:
            affichage (bool): Affiche l'image si désiré.

        Returns:
            tuple:
                - **dx** (*float*) - déplacement vers l'avant en m. 0 s'il n'y a pas le bon code ArUco.
                - **dy** (*float*) - déplacement vers la droite en m. 0 s'il n'y a pas le bon code ArUco.
                - **dz** (*float*) - déplacement vers le bas en m. 0 s'il n'y a pas le bon code ArUco.
                - **info** (*str | None*) - Infos diverses de la détection. None s'il n'y a pas le bon code ArUco.
                - **frame** (*np.ndarray | None*) - Frame analysée. None s'il n'y a pas le bon code ArUco.
        """
        # Image à un instant t
        t_begin = self.time_boot_ms
        raw = self.get_frame(affiche=affichage, timeout=2)
        if raw is None:
            return 0, 0, 0, None, None
        frame = cv2.cvtColor(raw, cv2.COLOR_RGB2GRAY)
        last_aruco_time = self.time_boot_ms

        if (
            self._last_scale_down is not None
            and self._last_crop is not None
            and self.DO_CROP
        ):
            # Crop:
            frame_crop = frame[
                self._last_crop[0] : self._last_crop[2],
                self._last_crop[1] : self._last_crop[3],
            ]

            # Scale down:
            new_width = frame_crop.shape[1] // self._last_scale_down
            new_height = frame_crop.shape[0] // self._last_scale_down
            if new_width > 50 or new_height > 50:
                frame_treated = cv2.resize(
                    frame_crop, (new_width, new_height), interpolation=cv2.INTER_AREA
                )
            else:
                frame_treated = frame
                self._last_scale_down, self._last_crop = None, None
        else:
            frame_treated = frame

        # Détecter les marqueurs ArUco
        corners, ids, _ = cv2.aruco.detectMarkers(
            frame_treated, self._aruco_dict, parameters=self._aruco_params
        )
        t_marker_detect = self.time_boot_ms
        corners: Sequence[cv2.typing.MatLike]

        if ids is not None:
            for aruco_id, corner in zip(ids, corners):
                # if aruco_id != self.aruco_id:
                #     continue

                if self._last_crop is not None and self.DO_CROP:
                    corner[:, :, 0] *= self._last_scale_down
                    corner[:, :, 1] *= self._last_scale_down
                    corner[:, :, 0] += self._last_crop[1]
                    corner[:, :, 1] += self._last_crop[0]

                # cv2.aruco.drawDetectedMarkers(frame, corners, ids)
                # self.save_image(image=frame)

                _, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                    [corner], self.aruco_size, self._camera_matrix, self._dist_coeffs
                )
                tvec = tvec[0][0]  # Extraire le vecteur de translation
                # if self._last_crop is not None and self.DO_CROP:
                #    self.write_log(f"ID: {aruco_id[0]}, x={tvec[0]:.2f} m, y={tvec[1]:.2f} m, z={tvec[2]:.2f} m, x:{self._last_crop[2]-self._last_crop[0]}, y:{self._last_crop[3]-self._last_crop[1]}, scale:{self._last_scale_down}")
                # else:
                #    self.write_log(f"ID: {aruco_id[0]}, x={tvec[0]:.2f} m, y={tvec[1]:.2f} m, z={tvec[2]:.2f} m")

                last_crop = (
                    int(corner[:, :, 1].min()),
                    int(corner[:, :, 0].min()),
                    int(corner[:, :, 1].max()),
                    int(corner[:, :, 0].max()),
                )

                taille_aruco_px = (
                    last_crop[3] - last_crop[1],
                    last_crop[2] - last_crop[0],
                )
                to_crop = (
                    int(taille_aruco_px[0] * 1.5) + self._resolution[0] / 6,
                    int(taille_aruco_px[1] * 1.5) + self._resolution[0] / 6,
                )

                self._last_crop = (
                    max(int(last_crop[0] - to_crop[1]), 0),
                    max(int(last_crop[1] - to_crop[0]), 0),
                    min(int(last_crop[2] + to_crop[1]), self._resolution[1]),
                    min(int(last_crop[3] + to_crop[0]), self._resolution[0]),
                )
                self._last_scale_down = max(min(min(taille_aruco_px) // 32, 10), 1)

                dx, dy, dz = self._camera_to_drone(tvec=tvec)
                self.logger.log(
                    f"[LOG] ID {aruco_id[0]}, x={dx:.2f} m, y={dy:.2f} m, z={dz:.2f} m, aruco {taille_aruco_px}, last_crop:{last_crop}",
                    wanna_print=False,
                )

                info = f"id:{int(aruco_id)},rec:{round(last_aruco_time-t_begin, 4)},det:{round(t_marker_detect-last_aruco_time, 4)},sd{self._last_scale_down}"
                return dx, dy, dz, info, frame_treated
        if not self._simulation:
            self.logger.log(
                f"[LOG] Exposure Time: {self._picam2.capture_metadata()['ExposureTime']} µs, ISO: {self._picam2.capture_metadata()['AnalogueGain'] * 100:.0f}",
                wanna_print=False,
            )

        self._last_crop = None
        self._last_scale_down = None
        return 0, 0, 0, None, None

    # 2ème fonction d'analyse, plus complexe
    def analyse_scale_down(
        self, affichage: bool = False, current_altitude: float = None
    ) -> tuple[float, float, float, str | None, np.ndarray | None]:
        """Détermine les distances à effectuer pour aller sur le code Aruco.

        Args:
            affichage (bool): Affiche l'image si désiré.

        Returns:
            tuple:
                - **dx** (*float*) - déplacement vers l'avant en m. 0 s'il n'y a pas le bon code ArUco.
                - **dy** (*float*) - déplacement vers la droite en m. 0 s'il n'y a pas le bon code ArUco.
                - **dz** (*float*) - déplacement vers le bas en m. 0 s'il n'y a pas le bon code ArUco.
                - **info** (*str | None*) - Infos diverses de la détection. None s'il n'y a pas le bon code ArUco.
                - **frame** (*np.ndarray | None*) - Frame analysée. None s'il n'y a pas le bon code ArUco.
        """
        # Image à un instant t
        t_begin = self.time_boot_ms
        frame = self.get_frame(affiche=affichage, timeout=2)

        last_aruco_time = self.time_boot_ms

        scale_down_ratio_analyse = self._find_ratio(
            self._already_found_once, current_altitude
        )
        img, pre_corners, zone_detected = self._whiten_grass_protected(
            frame, scale_down_ratio_analyse
        )
        # threading.Thread(target=self.save_image, args=(img,)).start()

        if zone_detected and self.DO_CROP:
            # Crop:
            scale_down_ratio_detection = max(min(min(pre_corners[2:]) // 64, 10), 1)

            img_crop = img[
                pre_corners[1] : pre_corners[1] + pre_corners[3],
                pre_corners[0] : pre_corners[0] + pre_corners[2],
            ]

            new_width = img_crop.shape[1] // scale_down_ratio_detection
            new_height = img_crop.shape[0] // scale_down_ratio_detection

            if new_width > 40 or new_height > 40:
                frame_treated = cv2.resize(img_crop, (new_width, new_height))
                # frame_treated = cv2.resize(frame_crop, (new_width, new_height), interpolation=cv2.INTER_AREA)
            else:
                self.logger.log(
                    "[WARNING] Problème de taille de l'image, crop trop petit"
                )
                frame_treated = img
                zone_detected = False
        else:
            scale_down_ratio_detection = 1
            frame_treated = img

        # Détecter les marqueurs ArUco
        corners, ids, _ = cv2.aruco.detectMarkers(
            frame_treated, self._aruco_dict, parameters=self._aruco_params
        )
        t_marker_detect = self.time_boot_ms
        corners: Sequence[cv2.typing.MatLike]

        if ids is not None:
            for aruco_id, corner in zip(ids, corners):
                if aruco_id != self.aruco_id:
                    continue

                if zone_detected and self.DO_CROP:
                    # write_log(f"corners_before_crop: {corner}")
                    corner[:, :, 0] *= scale_down_ratio_detection
                    corner[:, :, 1] *= scale_down_ratio_detection
                    corner[:, :, 0] += pre_corners[1]
                    corner[:, :, 1] += pre_corners[0]
                # self.write_log(f"corners_after_crop:{corner}")
                # self.write_log(f"Corner {corner[0]}")
                cv2.aruco.drawDetectedMarkers(img, corners, ids)
                # threading.Thread(target=self.save_image, args=(img,)).start()

                _, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                    [corner], self.aruco_size, self._camera_matrix, self._dist_coeffs
                )
                tvec = tvec[0][0]  # Extraire le vecteur de translation

                last_crop = (
                    int(corner[:, :, 1].min()),
                    int(corner[:, :, 0].min()),
                    int(corner[:, :, 1].max()),
                    int(corner[:, :, 0].max()),
                )
                # write_log(f"last_crop1: {last_crop}")
                taille_aruco_px = (
                    last_crop[3] - last_crop[1],
                    last_crop[2] - last_crop[0],
                )

                dx, dy, dz = self._camera_to_drone(tvec=tvec)

                self._already_found_once = True
                self._last_found_altitude = current_altitude
                self._last_found_distance = dz
                self._last_found_px_size = min(taille_aruco_px)
                # self.logger.log(f"taille_aruco_px {taille_aruco_px}")
                self.logger.log(
                    f"[LOG] ID {aruco_id[0]}, xf={dx:.2f} m, yr={dy:.2f} m, zd={dz:.2f} m, aruco {taille_aruco_px}, last_crop:{last_crop}",
                    wanna_print=False,
                )

                info = f"id:{int(aruco_id)},rec:{round(last_aruco_time-t_begin, 4)},det:{round(t_marker_detect-last_aruco_time, 4)},sd{scale_down_ratio_detection}"
                return dx, dy, dz, info, frame_treated
        if not self._simulation:
            self.logger.log(
                f"[LOG] Exposure Time: {self._picam2.capture_metadata()['ExposureTime']} µs, ISO: {self._picam2.capture_metadata()['AnalogueGain'] * 100:.0f}",
                wanna_print=False,
            )

        return 0, 0, 0, None, None

    # ---------------------------------------------------
    # Callback Topic + thread Gstream + fonctions sombres
    # ---------------------------------------------------

    def _image_callback(self, msg) -> None:
        """Callback analysant les messages de type Image du topic Gazebo.

        Args:
            msg (Image): L'image du topic Gazebo.
        """
        try:
            width = msg.width
            height = msg.height
            data = msg.data

            self._frame = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3)
            self._time_frame = self.time_boot_ms
        except Exception:
            self._frame = None

    def _gstream_thread_fct(self) -> None:
        """Fonction à lancer en arrière plan pour récupérer les images Gstream."""
        self._gstream_thread_stopped.clear()
        while not self._stop_gstream_thread.is_set():
            try:
                sample = self._appsink.emit("try-pull-sample", self._Gst.SECOND // 2)
                if not sample:
                    continue
                buf = sample.get_buffer()
                caps = sample.get_caps()
                arr = buf.extract_dup(0, buf.get_size())
                # on récupère width/height via caps
                structure = caps.get_structure(0)
                width = structure.get_value("width")
                height = structure.get_value("height")
                self._frame = np.frombuffer(arr, dtype=np.uint8).reshape(
                    (height, width, 3)
                )
                self._time_frame = self.time_boot_ms
            except Exception:
                self._frame = None
        self._gstream_thread_stopped.set()

    def _find_ratio(self, already_found_once, current_altitude) -> float:
        """Trouve le ratio de scale down à appliquer pour l'analyse avant de faire la détection ArUco."""
        height = self.resolution[1]
        if not already_found_once:
            return 8

        # Gère le cas où l'altitude est absolue
        current_estimated_distance = current_altitude - (
            self._last_found_altitude - self._last_found_distance
        )

        current_estimated_distance = max(current_estimated_distance, 0.2)
        current_estimated_px_size = min(
            self._last_found_px_size
            * self._last_found_distance
            / current_estimated_distance,
            int(height * 0.8),
        )
        # self.write_log(f"lfps:{self._last_found_px_size} ceps {current_estimated_px_size} lfd: {self._last_found_distance} cea: {current_estimated_distance}")
        subsample_ratio = min(max(current_estimated_px_size / 64, height / 64), 1)

        return int(subsample_ratio * 8)

    def _whiten_grass_protected(self, rgb_image_src, subsample_ratio):
        """Supprime les zones de haute saturation (surement de l'herbe) et renvoie la position la plus probable de l'ArUco."""
        width = self.resolution[0]
        height = self.resolution[1]
        rgb_image = cv2.resize(
            rgb_image_src,
            (width // subsample_ratio, height // subsample_ratio),
            interpolation=cv2.INTER_LINEAR,
        )

        B, G, R = rgb_image[::, ::, 0], rgb_image[::, ::, 1], rgb_image[::, ::, 2]
        a = np.stack([R, G, B], axis=0)
        diff = np.max(a, axis=0) - np.min(a, axis=0)
        tolerance = 30
        gray_mask_small = diff > tolerance

        # Pour éliminer les plus petites zones : max 4 "pixels"
        gray_mask_small = cv2.dilate(
            gray_mask_small.astype(np.uint8), self._kernel, iterations=1
        )
        # Pour élargir la zone de recherche aruco après avoir supprimé les petites aberrations
        gray_mask_small = ~cv2.dilate(
            ~gray_mask_small.astype(np.uint8), self._kernel2, iterations=1
        )

        gray_mask = cv2.resize(
            gray_mask_small, (width, height), interpolation=cv2.INTER_LINEAR
        )
        if self._simulation:
            rgb_image_src_copy = rgb_image_src.copy()
        else:
            rgb_image_src_copy = rgb_image_src

        rgb_image_src_copy[gray_mask == 1] = [255, 255, 255]
        rgb_image[gray_mask_small == 1] = [255, 255, 255]

        # Trouve les contours des formes qui se détachent
        _, obstacle = cv2.threshold(rgb_image[:, :, 0], 100, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(
            obstacle, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Afin de ne pas détecter les plus petites zones
        min_area = int((25 * 25) / (subsample_ratio**2))  # Aruco de 25px

        candidates = []
        for cnt in contours:
            rect = cv2.boundingRect(cnt)
            if rect[2] * rect[3] >= min_area:
                candidates.append((rect, rect[2] * rect[3]))

        sort_cand = sorted(candidates, key=lambda x: x[1])

        # Si on détecte 2 zones dont la seconde (ordonnées par taille) represente plus de la moitié de sa surface : on a détecté de la merde
        # Si la plus grosse zone détectée fait presque la taille de l'écran : la suppression de l'herbe ne s'est pas bien passée
        if (
            candidates
            and (
                (
                    len(sort_cand) >= 2
                    and sort_cand[-1][0][0] * sort_cand[-2][0][0] != 0
                    and sort_cand[-1][0][0] / sort_cand[-2][0][0] > 2
                )
                or (
                    len(sort_cand) == 1
                    or sort_cand[-1][0][0] * sort_cand[-2][0][0] != 0
                )
            )
            and (
                sort_cand[-1][0][2] < width // subsample_ratio - 2
                and sort_cand[-1][0][3] < height // subsample_ratio - 2
            )
        ):
            candidate = (
                np.array(sort_cand[-1][0]) + np.array([-2, -4, 3, 4])
            ) * subsample_ratio
            candidate[0] = max(0, candidate[0])
            candidate[1] = max(0, candidate[1])
            candidate[2] = min(width - candidate[0], candidate[2])
            candidate[3] = min(height - candidate[1], candidate[3])
            zone_detected = True
        else:
            candidate = np.array([0, 0, width, height])
            zone_detected = False

        return rgb_image_src_copy, candidate, zone_detected

    # ----------------------
    # Fermeture de la caméra
    # ----------------------

    def close(self) -> None:
        """Ferme la caméra."""
        self.logger.log("[INFO] Closing camera..")
        try:
            if self._simulation is None:
                self._picam2.stop()
                self._picam2.close()
            elif self._simulation == "HITL":
                self._stop_gstream_thread.set()
                self._gstream_thread_stopped.wait(timeout=10)
                self._pipeline.set_state(self._Gst.State.NULL)
        except Exception:
            self.logger.log(exception=True)
        try:
            cv2.destroyAllWindows()
        except Exception:
            self.logger.log(exception=True)
        self.logger.log("[SUCCESS] Camera closed")
