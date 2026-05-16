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
