import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from divers.class_Logger import Logger


class Local_Position_Sensor:
    """Classe gérant le capteur de position local du drone."""
    def __init__(self,
            simulation: bool,
            pose_topic: str = "/world/iris_runway/dynamic_pose/info",
            drone_name_gz: str = "iris_with_gimbal",
            logger: Logger = Logger()
        ):
        """Initialise le capteur.

        Args:
            simulation (bool): Indique si on est en simu ou non.
            pose_topic (str): Topic Gazebo avec l'entièreté des positions.
            drone_name_gz (str): Nom du drone sur Gazebo.
            logger (Logger): Logger utilisé.
        """
        self.logger = logger
        self._drone_name_gz = drone_name_gz

        # Positions locales
        self._x = self._y = self._z = 0.0

        # Indique si on a reçu une première position
        self._pos_initialized = False

        # Simulation
        self._simulation = simulation

        if simulation:
            from gz.transport13 import Node
            from gz.msgs10.pose_v_pb2 import Pose_V
            self._node = Node()
            subscribed = self._node.subscribe(Pose_V, pose_topic, self._pose_v_callback)
            if not subscribed:
                raise RuntimeError(f"Failed to subscribe to topic: {pose_topic}")
        else:
            self._node = None

    # Propriété de 1ère position reçue
    @property
    def pos_initialized(self) -> bool:
        return self._pos_initialized

    # Propriétés position locale
    @property
    def x(self) -> float:
        """Position Nord (en simulation : correspond à y Gazebo)."""
        return self._y if self._simulation else self._x

    @property
    def y(self) -> float:
        """Position Est (en simulation : correspond à x Gazebo)."""
        return self._x if self._simulation else self._y

    @property
    def z(self) -> float:
        """Position Bas (inverse de Gazebo)."""
        return -self._z if self._simulation else self._z

    # Gestion du callback
    def _pose_v_callback(self, msg) -> None:
        """Callback appelé à chaque message de type Pose_V reçu."""
        for pose in msg.pose:
            if pose.name == self._drone_name_gz:
                x = round(pose.position.x, 2)
                y = round(pose.position.y, 2)
                z = round(pose.position.z, 2)
                self._x, self._y, self._z = x, y, z
                self._pos_initialized = True
                break
