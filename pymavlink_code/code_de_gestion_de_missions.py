from enum import Enum
from typing import Optional


class Level(Enum):
    # Level
    Empty = 'Empty'
    Sucesses = 'Sucesses'
    Message = 'Message'
    Warning = 'Warning'
    Failure = 'Failure'
    Critical = 'Critical'


class CGM:
    """
    Classe représentant un CGM de gestion de mission avec différentes propriétés, niveaux et descriptions.
    Permet de catégoriser des CGMs en fonction de leur valeur et d'y associer des descriptions.
    """

    # Dictionnaire statique pour stocker les instances de CGM par valeur
    __dict: dict[int, 'CGM'] = {}

    # Dictionnaire statique pour stocker les instances de CGM par nom
    __dict_name: dict[str, 'CGM'] = {}

    def __init__(self,
                 value: int,
                 name: str,
                 short_description: str,
                 long_description: str,
                 potential_sender: Optional[str] = None):
        """
        Initialise un nouvel objet CGM.

        :param value: La valeur numérique unique associée au CGM.
        :param name: Le nom du CGM.
        :param short_description: Une courte description du CGM.
        :param long_description: Une description détaillée du CGM.
        :param potential_sender: Optionnel, indique un expéditeur potentiel.
        """
        self.value = value
        self.name = name
        self.short_description_str = short_description
        self.long_description_str = long_description
        self.potential_sender = potential_sender
        self.description = self.short_description
        self.level: Level = None

        # Déterminer le niveau et le sous-niveau en fonction de la valeur du CGM
        if self.value == 0:
            self.level = Level.Empty
        elif 100 <= self.value < 200:
            self.level = Level.Sucesses
        elif 200 <= self.value < 300:
            self.level = Level.Message
        elif 300 <= self.value < 400:
            self.level = Level.Warning
        elif 400 <= self.value < 500:
            self.level = Level.Failure
        elif 500 <= self.value < 600:
            self.level = Level.Critical
        else:
            raise ValueError("Invalid CGM number")  # Valeur hors des plages valides

        # Vérifie si le CGM existe déjà dans le dictionnaire statique
        if self.value in CGM.__dict:
            raise ValueError("Already existing CGM")  # Empêche les doublons

        # Vérifie si le CGM existe déjà dans le dictionnaire statique
        if self.name in CGM.__dict_name:
            raise ValueError("Already existing CGM")  # Empêche les doublons

        # Ajoute le CGM aux dictionnaires statiques
        CGM.__dict[self.value] = self
        CGM.__dict_name[self.name] = self

    def __repr__(self) -> str:
        return self.short_description()

    def __int__(self) -> int:
        return self.value

    def __eq__(self, other) -> bool:
        if isinstance(other, CGM):
            return self.value == other.value
        elif isinstance(other, int):
            return self.value == other
        return False

    def __hash__(self) -> int:
        return hash(self.value)

    def header(self) -> str:
        return f'[{self.level.value} {self.value}]'

    def short_description(self) -> str:
        text = self.header()
        text += f"[{self.short_description_str}]"
        return text

    def long_description(self) -> str:
        text = f'[{self.level.value} {self.value}: {self.name}]'
        if self.potential_sender is not None:
            text += f'[Sender: {self.potential_sender}]'
        text += f"[{self.long_description_str}]"
        return text

    @staticmethod
    def get(value: int) -> Optional['CGM']:
        return CGM.__dict.get(value, EMPTY)

    @staticmethod
    def get_name(name: str) -> Optional['CGM']:
        return CGM.__dict_name.get(name, EMPTY)

    @staticmethod
    def get_all_level(level: Level) -> list['CGM']:
        return sorted(
            [cgm for cgm in CGM.__dict.values() if cgm.level == level],
            key=lambda CGM: CGM.value
        )

    @staticmethod
    def get_all() -> list['CGM']:
        return list(CGM.__dict.values())


# ==============================================================================
# SPECIAL
# ==============================================================================

EMPTY = CGM(
    value=0,
    name="EMPTY",
    short_description="empty",
    long_description="empty",
    potential_sender="pc"
)

# ==============================================================================
# PC  (sender : pc --> Valhalla)
# ==============================================================================

# --- Messages (200-299) -------------------------------------------------------

PC_DEMANDE_MISSION = CGM(
    value=200,
    name="PC_DEMANDE_MISSION",
    short_description="La station au sol demande de lancer la mission",
    long_description="Une fois le point GPS choisi, le bouton sur le Dashboard demande a Valhalla de demarrer la mission",
    potential_sender="pc"
)

PC_DEMANDE_MISSION_1_VALHALLA = CGM(
    value=201,
    name="PC_DEMANDE_MISSION_1_VALHALLA",
    short_description="Lancement mission 1 sur Valhalla",
    long_description="",
    potential_sender="pc"
)

PC_CONFIGURE_VALHALLA = CGM(
    value=203,
    name="PC_CONFIGURE_VALHALLA",
    short_description="Le Dashboard demande à Valhalla de se connecter en WiFi pour récupérer la config",
    long_description="Déclenche une connexion WebSocket ponctuelle entre Valhalla et le Dashboard",
    potential_sender="pc"
)

PC_A_DISARM_FORCE_VALHALLA = CGM(
    value=204,
    name="PC_A_DISARM_FORCE_VALHALLA",
    short_description="Arrêt d'urgence : désarmement forcé de Valhalla",
    long_description="",
    potential_sender="pc"
)

PC_DEMANDE_MISSION_2_VALHALLA = CGM(
    value=205,
    name="PC_DEMANDE_MISSION_2_VALHALLA",
    short_description="Lancement mission 2 sur Valhalla",
    long_description="",
    potential_sender="pc"
)

PC_DEMANDE_MISSION_3_VALHALLA = CGM(
    value=206,
    name="PC_DEMANDE_MISSION_3_VALHALLA",
    short_description="Lancement mission 3 sur Valhalla",
    long_description="",
    potential_sender="pc"
)

PC_DEMANDE_MISSION_4_VALHALLA = CGM(
    value=207,
    name="PC_DEMANDE_MISSION_4_VALHALLA",
    short_description="Lancement mission 4 sur Valhalla",
    long_description="",
    potential_sender="pc"
)

PC_DEMANDE_MISSION_5_VALHALLA = CGM(
    value=208,
    name="PC_DEMANDE_MISSION_5_VALHALLA",
    short_description="Lancement mission 5 sur Valhalla",
    long_description="",
    potential_sender="pc"
)

ESP32_PING = CGM(
    value=209,
    name="ESP32_PING",
    short_description="Valhalla envoie un ping ESP32 pour tester la connectivité",
    long_description="Déclenché par le Dashboard. Valkyrie doit répondre par ESP32_PONG (110).",
    potential_sender="valhalla"
)

# ==============================================================================
# VALHALLA  (sender : valhalla --> GCS)
# ==============================================================================

# --- Successes (100-199) ------------------------------------------------------

VALHALLA_POINT_ATTEINT = CGM(
    value=101,
    name="VALHALLA_POINT_ATTEINT",
    short_description="Valhalla est arrive au point GPS",
    long_description="Valhalla va maintenant descendre et attendre Valkyrie",
    potential_sender="valhalla"
)

VALHALLA_ARMED = CGM(
    value=102,
    name="VALHALLA_ARMED",
    short_description="Valhalla armé",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_TOOKOFF = CGM(
    value=103,
    name="VALHALLA_TOOKOFF",
    short_description="Valhalla a décollé",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_LANDING = CGM(
    value=104,
    name="VALHALLA_LANDING",
    short_description="Valhalla entame son atterrissage",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_CONFIG_OK = CGM(
    value=106,
    name="VALHALLA_CONFIG_OK",
    short_description="Valhalla a bien reçu et enregistré la configuration",
    long_description="La configuration JSON a été sauvegardée et relayée à Valkyrie via ESP32",
    potential_sender="valhalla"
)

# --- Messages (200-299) -------------------------------------------------------

DEMANDE_TAKEOFF_VALKYRIE = CGM(
    value=202,
    name="DEMANDE_TAKEOFF_VALKYRIE",
    short_description="Valhalla ordonne à Valkyrie de décoller",
    long_description="",
    potential_sender="valhalla"
)

# --- Failures (400-499) -------------------------------------------------------

VALHALLA_ARM_FAIL = CGM(
    value=400,
    name="VALHALLA_ARM_FAIL",
    short_description="Valhalla n'a pas pu s'armer",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_MODE_CHANGE_FAIL = CGM(
    value=401,
    name="VALHALLA_MODE_CHANGE_FAIL",
    short_description="Valhalla n'a pas pu changer de mode de vol",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_TAKEOFF_FAIL = CGM(
    value=402,
    name="VALHALLA_TAKEOFF_FAIL",
    short_description="Valhalla n'a pas pu décoller",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_NO_TARGET_FOUND = CGM(
    value=403,
    name="VALHALLA_NO_TARGET_FOUND",
    short_description="Valhalla n'a pas trouvé de cible GPS valide",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_CONFIG_FAIL = CGM(
    value=407,
    name="VALHALLA_CONFIG_FAIL",
    short_description="Valhalla n'a pas pu récupérer la configuration (timeout WiFi ou erreur)",
    long_description="",
    potential_sender="valhalla"
)

# ==============================================================================
# VALKYRIE  (sender : valkyrie --> ESP32 --> Valhalla --> GCS)
# ==============================================================================

# --- Successes (100-199) ------------------------------------------------------

VALKYRIE_TOOKOFF = CGM(
    value=105,
    name="VALKYRIE_TOOKOFF",
    short_description="Valkyrie a décollé",
    long_description="",
    potential_sender="valkyrie"
)

VALKYRIE_ARMED = CGM(
    value=108,
    name="VALKYRIE_ARMED",
    short_description="Valkyrie armé",
    long_description="",
    potential_sender="valkyrie"
)

ESP32_PONG = CGM(
    value=110,
    name="ESP32_PONG",
    short_description="Valkyrie répond au ping ESP32 de Valhalla",
    long_description="Réponse automatique à ESP32_PING (209). Indique que le lien ESP-NOW est fonctionnel.",
    potential_sender="valkyrie"
)

VALKYRIE_LANDED = CGM(
    value=107,
    name="VALKYRIE_LANDED",
    short_description="Valkyrie a atterri avec succès sur l'ArUco",
    long_description="Precision Land terminé, moteurs désarmés sur la cible",
    potential_sender="valkyrie"
)

# --- Failures (400-499) -------------------------------------------------------

VALKYRIE_ARM_FAIL = CGM(
    value=404,
    name="VALKYRIE_ARM_FAIL",
    short_description="Valkyrie n'a pas pu s'armer",
    long_description="",
    potential_sender="valkyrie"
)

VALKYRIE_MODE_CHANGE_FAIL = CGM(
    value=405,
    name="VALKYRIE_MODE_CHANGE_FAIL",
    short_description="Valkyrie n'a pas pu changer de mode de vol",
    long_description="",
    potential_sender="valkyrie"
)

VALKYRIE_TAKEOFF_FAIL = CGM(
    value=406,
    name="VALKYRIE_TAKEOFF_FAIL",
    short_description="Valkyrie n'a pas pu décoller",
    long_description="",
    potential_sender="valkyrie"
)

VALKYRIE_MISSION_INVALID = CGM(
    value=408,
    name="VALKYRIE_MISSION_INVALID",
    short_description="Numéro de mission invalide reçu par Valkyrie via ESP32",
    long_description="CMD:START:N reçu mais N est absent, non entier ou hors limite [1-5]",
    potential_sender="valkyrie"
)

VALKYRIE_NO_TARGET_FOUND = CGM(
    value=409,
    name="VALKYRIE_NO_TARGET_FOUND",
    short_description="Valkyrie n'a pas trouvé la cible ArUco après quadrillage complet",
    long_description="Tous les points du quadrillage parcourus sans détecter l'ArUco cible",
    potential_sender="valkyrie"
)

VALHALLA_ESP32_FAIL = CGM(
    value=410,
    name="VALHALLA_ESP32_FAIL",
    short_description="Valhalla ne peut pas se connecter à son ESP32",
    long_description="Connexion UART/USB vers l'ESP32 de Valhalla échouée. Retry en cours.",
    potential_sender="valhalla"
)

VALKYRIE_ESP32_FAIL = CGM(
    value=411,
    name="VALKYRIE_ESP32_FAIL",
    short_description="Valkyrie ne peut pas se connecter à son ESP32",
    long_description="Connexion UART/USB vers l'ESP32 de Valkyrie échouée. Retry en cours.",
    potential_sender="valkyrie"
)

# --- Successes (100-199) ------------------------------------------------------

VALKYRIE_PRECISION_LAND_STARTING = CGM(
    value=109,
    name="VALKYRIE_PRECISION_LAND_STARTING",
    short_description="Valkyrie centré, passage en LAND",
    long_description="Le centrage sur la cible ArUco est validé. Valkyrie bascule en mode LAND pour la descente de précision.",
    potential_sender="valkyrie"
)

VALKYRIE_YAW_ALIGNED = CGM(
    value=111,
    name="VALKYRIE_YAW_ALIGNED",
    short_description="Valkyrie aligné yaw (pince vers la cible)",
    long_description="L'alignement du cap du drone a convergé dans la tolérance. La pince est orientée vers la cible avant la descente.",
    potential_sender="valkyrie"
)

VALKYRIE_FOLLOW_STARTED = CGM(
    value=112,
    name="VALKYRIE_FOLLOW_STARTED",
    short_description="Valkyrie mode FOLLOW activé",
    long_description="Valkyrie a réussi à passer en mode FOLLOW et commence à suivre Valhalla à 2m au-dessus.",
    potential_sender="valkyrie"
)

# --- Messages (200-299) -------------------------------------------------------

VALKYRIE_OUTER_ARUCO_DETECTED = CGM(
    value=210,
    name="VALKYRIE_OUTER_ARUCO_DETECTED",
    short_description="Marqueur ArUco extérieur détecté",
    long_description="Le marqueur e-ArUco outer (DICT_7X7_50 ID=5) est visible depuis l'altitude de quadrillage.",
    potential_sender="valkyrie"
)

VALKYRIE_INNER_ARUCO_DETECTED = CGM(
    value=211,
    name="VALKYRIE_INNER_ARUCO_DETECTED",
    short_description="Marqueur ArUco intérieur détecté",
    long_description="Le marqueur e-ArUco inner (DICT_4X4_50 ID=17) est visible. Valkyrie est à faible altitude au-dessus de la cible.",
    potential_sender="valkyrie"
)

# --- Warnings (300-399) -------------------------------------------------------

VALKYRIE_YAW_ALIGN_TIMEOUT = CGM(
    value=300,
    name="VALKYRIE_YAW_ALIGN_TIMEOUT",
    short_description="Timeout alignement yaw -- LAND quand même",
    long_description="L'alignement du cap n'a pas convergé dans le délai imparti. Valkyrie passe en LAND sans alignement optimal.",
    potential_sender="valkyrie"
)

VALKYRIE_LAND_ABORTED = CGM(
    value=301,
    name="VALKYRIE_LAND_ABORTED",
    short_description="LAND avorté -- cible perdue en descente",
    long_description="La cible ArUco a été perdue pendant la descente. Valkyrie remonte à l'altitude de quadrillage et retente le centrage.",
    potential_sender="valkyrie"
)

VALKYRIE_LOITER_LOST_TARGET = CGM(
    value=302,
    name="VALKYRIE_LOITER_LOST_TARGET",
    short_description="Cible perdue en LOITER -- requadrillage",
    long_description="La cible ArUco a été perdue trop longtemps en phase de centrage. Valkyrie relance un quadrillage complet.",
    potential_sender="valkyrie"
)

VALKYRIE_FOLLOW_GPS_LOST = CGM(
    value=303,
    name="VALKYRIE_FOLLOW_GPS_LOST",
    short_description="GPS Valhalla perdu en FOLLOW -- RTL",
    long_description="Le signal GPS de Valhalla (reçu via ESP32) est perdu depuis trop longtemps. Valkyrie déclenche un RTL.",
    potential_sender="valkyrie"
)

# ==============================================================================
# URGENCES  (sender : pc --> valhalla --> valkyrie)
# ==============================================================================

VALHALLA_WAITING_MISSION = CGM(
    value=215,
    name="VALHALLA_WAITING_MISSION",
    short_description="Valhalla en attente d'un ordre de mission",
    long_description="Valhalla a terminé ses initialisations et est prêt à recevoir une commande.",
    potential_sender="valhalla"
)

VALKYRIE_WAITING_MISSION = CGM(
    value=216,
    name="VALKYRIE_WAITING_MISSION",
    short_description="Valkyrie en attente d'un ordre de mission",
    long_description="Valkyrie a terminé ses initialisations et est prêt à recevoir une commande via ESP-NOW.",
    potential_sender="valkyrie"
)

PC_URGENCY_LANDING_VALHALLA = CGM(
    value=212,
    name="PC_URGENCY_LANDING_VALHALLA",
    short_description="Atterrissage d'urgence Valhalla (RTL + retour attente)",
    long_description="Le Dashboard ordonne à Valhalla de couper sa mission, de rentrer en RTL et de revenir en boucle d'attente.",
    potential_sender="pc"
)

PC_A_DISARM_FORCE_VALKYRIE = CGM(
    value=213,
    name="PC_A_DISARM_FORCE_VALKYRIE",
    short_description="Désarmement forcé Valkyrie relayé par Valhalla",
    long_description="Valhalla relaie l'ordre de désarmement immédiat à Valkyrie via ESP-NOW.",
    potential_sender="valhalla"
)

PC_URGENCY_LANDING_VALKYRIE = CGM(
    value=214,
    name="PC_URGENCY_LANDING_VALKYRIE",
    short_description="Atterrissage d'urgence Valkyrie relayé par Valhalla",
    long_description="Valhalla relaie l'ordre RTL à Valkyrie via ESP-NOW. Valkyrie coupe sa mission et rentre.",
    potential_sender="valhalla"
)

PC_OPEN_GRIPPER_VALKYRIE = CGM(
    value=217,
    name="PC_OPEN_GRIPPER_VALKYRIE",
    short_description="Ordre d'ouverture de la pince Valkyrie",
    long_description="Le Dashboard demande l'ouverture manuelle de la pince. Valhalla relaie via ESP-NOW à Valkyrie.",
    potential_sender="pc"
)

PC_CLOSE_GRIPPER_VALKYRIE = CGM(
    value=218,
    name="PC_CLOSE_GRIPPER_VALKYRIE",
    short_description="Ordre de fermeture de la pince Valkyrie",
    long_description="Le Dashboard demande la fermeture manuelle de la pince. Valhalla relaie via ESP-NOW à Valkyrie.",
    potential_sender="pc"
)

PC_CALIB_GRIPPER_VALKYRIE = CGM(
    value=219,
    name="PC_CALIB_GRIPPER_VALKYRIE",
    short_description="Calibration de la pince Valkyrie",
    long_description="Le Dashboard demande la calibration initiale de la pince (homing servo). Valhalla relaie via ESP-NOW à Valkyrie.",
    potential_sender="pc"
)

VALKYRIE_GRIP_OK = CGM(
    value=113,
    name="VALKYRIE_GRIP_OK",
    short_description="Valkyrie a saisi l'objet avec succès",
    long_description="La pince s'est fermée et les interrupteurs de contact ont confirmé la saisie de l'objet.",
    potential_sender="valkyrie"
)

PC_CONFIGURE_VALKYRIE = CGM(
    value=220,
    name="PC_CONFIGURE_VALKYRIE",
    short_description="Connexion WiFi ponctuelle Valkyrie (config / logs)",
    long_description="Le Dashboard demande à Valkyrie de se connecter en WiFi pour une session ponctuelle (récupération de logs, config). Valhalla relaie via ESP-NOW.",
    potential_sender="pc"
)

PC_DEMANDE_MISSION_1_VALKYRIE = CGM(
    value=221,
    name="PC_DEMANDE_MISSION_1_VALKYRIE",
    short_description="Lancement mission 1 sur Valkyrie (radio directe)",
    long_description="Le GCS demande directement à Valkyrie de lancer la mission 1 via liaison MAVLink radio (sans ESP32).",
    potential_sender="pc"
)

PC_DEMANDE_MISSION_2_VALKYRIE = CGM(
    value=222,
    name="PC_DEMANDE_MISSION_2_VALKYRIE",
    short_description="Lancement mission 2 sur Valkyrie (radio directe)",
    long_description="Le GCS demande directement à Valkyrie de lancer la mission 2 via liaison MAVLink radio (sans ESP32).",
    potential_sender="pc"
)

PC_DEMANDE_MISSION_3_VALKYRIE = CGM(
    value=223,
    name="PC_DEMANDE_MISSION_3_VALKYRIE",
    short_description="Lancement mission 3 sur Valkyrie (radio directe)",
    long_description="Le GCS demande directement à Valkyrie de lancer la mission 3 via liaison MAVLink radio (sans ESP32).",
    potential_sender="pc"
)

PC_DEMANDE_MISSION_4_VALKYRIE = CGM(
    value=224,
    name="PC_DEMANDE_MISSION_4_VALKYRIE",
    short_description="Lancement mission 4 sur Valkyrie (radio directe)",
    long_description="Le GCS demande directement à Valkyrie de lancer la mission 4 via liaison MAVLink radio (sans ESP32).",
    potential_sender="pc"
)

PC_DEMANDE_MISSION_5_VALKYRIE = CGM(
    value=225,
    name="PC_DEMANDE_MISSION_5_VALKYRIE",
    short_description="Lancement mission 5 sur Valkyrie (radio directe)",
    long_description="Le GCS demande directement à Valkyrie de lancer la mission 5 via liaison MAVLink radio (sans ESP32).",
    potential_sender="pc"
)
