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
        """
        Retourne une représentation textuelle concise de l'objet CGM.
        Inclut le niveau, la valeur et une petite description.
        """
        return self.short_description()

    def __int__(self) -> int:
        """
        Permet de convertir un objet CGM en entier correspondant à sa valeur.
        """
        return self.value
    
    def __eq__(self, other) -> bool:
        if isinstance(other, CGM):
            return self.value == other.value
        elif isinstance(other, int):
            return self.value == other
        return False
    
    def __hash__(self) -> int:
        """
        Rend l'objet hashable pour pouvoir l'insérer dans des set (comme self.cgm sur MAVLinCS).
        On utilise la valeur (qui est unique) comme empreinte.
        """
        return hash(self.value)
    # ----------------------------

    def header(self) -> str:
        """
        Retourne une représentation concise pour l'en-tête.
        Inclut le niveau, la valeur et le nom.
        """
        return f'[{self.level.value} {self.value}]'

    def short_description(self) -> str:
        """
        Génère une description courte de l'objet CGM.
        """
        text = self.header()
        text += f"[{self.short_description_str}]"
        return text

    def long_description(self) -> str:
        """
        Génère une description longue de l'objet CGM.
        Ajoute des informations supplémentaires.
        """
        text = f'[{self.level.value} {self.value}: {self.name}]'
        if self.potential_sender is not None:
            text += f'[Sender: {self.potential_sender}]'
        text += f"[{self.long_description_str}]"
        return text

    @staticmethod
    def get(value: int) -> Optional['CGM']:
        """
        Récupère un objet CGM à partir de sa valeur numérique.
        Retourne EMPTY si aucun CGM n'existe avec cette valeur.
        """
        return CGM.__dict.get(value, EMPTY)
    
    @staticmethod
    def get_name(name: str) -> Optional['CGM']:
        """
        Récupère un objet CGM à partir de son nom.
        Retourne EMPTY si aucun CGM n'existe avec ce nom.
        """
        return CGM.__dict_name.get(name, EMPTY)

    @staticmethod
    def get_all_level(level: Level) -> list['CGM']:
        """
        Récupère tous les objets CGM ayant un niveau donné, triés par valeur.
        """
        return sorted(
            [cgm for cgm in CGM.__dict.values() if cgm.level == level],
            key=lambda CGM: CGM.value
        )

    @staticmethod
    def get_all() -> list['CGM']:
        """
        Retourne une liste de tous les objets CGM créés.
        """
        return list(CGM.__dict.values())

EMPTY = CGM(
    value=0,
    name="EMPTY",
    short_description="empty",
    long_description="empty",
    potential_sender="pc"
)

PC_DEMANDE_MISSION = CGM(
    value=200,
    name="PC_DEMANDE_MISSION",
    short_description="La station au sol demande de lancer la mission",
    long_description="Une fois le point GPS choisi, le bouton sur le Dashboard demande a Valhalla de demarrer la mission",
    potential_sender="pc"
)

PC_DEMANDE_TAKEOFF_VALHALLA = CGM(
    value=201,
    name="PC_DEMANDE_TAKEOFF_VALHALLA",
    short_description="",
    long_description="",
    potential_sender="pc"
)

DEMANDE_TAKEOFF_VALKYRIE = CGM(
    value=202,
    name="DEMANDE_TAKEOFF_VALKYRIE",
    short_description="",
    long_description="",
    potential_sender="valhalla"
)


VALHALLA_POINT_ATTEINT = CGM(
    value=101,
    name="VALHALLA_POINT_ATTEINT",
    short_description="Valhalla est arrive au point GPS",
    long_description="Valhalla va maintenant descendre et attendre valkyrie",
    potential_sender="valhalla"
)

VALHALLA_ARMED = CGM(
    value=102,
    name="VALHALLA_ARMED",
    short_description="",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_TOOKOFF = CGM(
    value=103,
    name="VALHALLA_TOOKOFF",
    short_description="",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_LANDING = CGM(
    value=104,
    name="VALHALLA_LANDING",
    short_description="",
    long_description="",
    potential_sender="valhalla"
)

VALKYRIE_TOOKOFF = CGM(
    value=105,
    name="VALKYRIE_TOOKOFF",
    short_description="",
    long_description="",
    potential_sender="valkyrie"
)



VALHALLA_ARM_FAIL = CGM(
    value=400,
    name="VALHALLA_ARM_FAIL",
    short_description="",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_MODE_CHANGE_FAIL = CGM(
    value=401,
    name="VALHALLA_MODE_CHANGE_FAIL",
    short_description="",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_TAKEOFF_FAIL = CGM(
    value=402,
    name="VALHALLA_TAKEOFF_FAIL",
    short_description="",
    long_description="",
    potential_sender="valhalla"
)

VALHALLA_NO_TARGET_FOUND = CGM(
    value=403,
    name="VALHALLA_NO_TARGET_FOUND",
    short_description="",
    long_description="",
    potential_sender="valhalla"
)

VALKYRIE_ARM_FAIL = CGM(
    value=404,
    name="VALKYRIE_ARM_FAIL",
    short_description="",
    long_description="",
    potential_sender="valkyrie"
)

VALKYRIE_MODE_CHANGE_FAIL = CGM(
    value=405,
    name="VALKYRIE_MODE_CHANGE_FAIL",
    short_description="",
    long_description="",
    potential_sender="valkyrie"
)

VALKYRIE_TAKEOFF_FAIL = CGM(
    value=406,
    name="VALKYRIE_TAKEOFF_FAIL",
    short_description="",
    long_description="",
    potential_sender="valkyrie"
)

PC_CONFIGURE_VALHALLA = CGM(
    value=203,
    name="PC_CONFIGURE_VALHALLA",
    short_description="Le Dashboard demande à Valhalla de se connecter en WiFi pour récupérer la config",
    long_description="Déclenche une connexion WebSocket ponctuelle entre Valhalla et le Dashboard",
    potential_sender="pc"
)

VALHALLA_CONFIG_OK = CGM(
    value=106,
    name="VALHALLA_CONFIG_OK",
    short_description="Valhalla a bien reçu et enregistré la configuration",
    long_description="La configuration JSON a été sauvegardée et relayée à Valkyrie via ESP32",
    potential_sender="valhalla"
)

VALHALLA_CONFIG_FAIL = CGM(
    value=407,
    name="VALHALLA_CONFIG_FAIL",
    short_description="Valhalla n'a pas pu récupérer la configuration (timeout WiFi ou erreur)",
    long_description="",
    potential_sender="valhalla"
)

PC_A_DISARM_FORCE_VALHALLA = CGM(
    value=204,
    name="PC_A_DISARM_FORCE_VALHALLA",
    short_description="",
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
