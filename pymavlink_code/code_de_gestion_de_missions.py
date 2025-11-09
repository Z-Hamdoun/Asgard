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
                 level: str,
                 description: str):
        """
        Initialise un nouvel objet CGM.
        
        Args:
            value (int): La valeur numérique unique associée au CGM.
            name (str): Le nom du CGM.
            level (str): Type de CGM (ex : SUCCESS).
            description (str): Une courte description du CGM.
        """
        self.value = value
        self.name = name
        self.level = level
        self.description = f"[{level}][{name}] {description}"
        
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
        return self.description

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
        elif isinstance(other, str):
            return self.name == other
        return False
    
    def __hash__(self):
        return hash(self.value)

    @staticmethod
    def get(value: int) -> 'CGM':
        """
        Récupère un objet CGM à partir de sa valeur numérique.
        Retourne EMPTY si aucun CGM n'existe avec cette valeur.
        """
        return CGM.__dict.get(value, EMPTY)
    
    @staticmethod
    def get_name(name: str) -> 'CGM':
        """
        Récupère un objet CGM à partir de son nom.
        Retourne EMPTY si aucun CGM n'existe avec ce nom.
        """
        return CGM.__dict_name.get(name, EMPTY)

EMPTY = CGM(
    value=0,
    name="EMPTY",
    level="EMPTY",
    description="empty"
)

EXAMPLE = CGM(
    value=100,
    name="EXAMPLE",
    level="LOG",
    description="Exemple."
)
