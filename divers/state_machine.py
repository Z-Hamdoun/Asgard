class State:
    """
    Classe abstraite qui définit ce qu'est un État.
    Tous les états hériteront de celle-ci.
    """
    @property
    def name(self):
        return self.__class__.__name__

    def on_enter(self, drone):
        """Exécuté UNE FOIS quand on entre dans l'état"""
        logging.info(f"--> Entrée dans l'état : {self.name}")

    def on_execute(self, drone):
        """
        Exécuté EN BOUCLE tant qu'on est dans l'état.
        C'est ici que se trouve la logique (PnP, PID, etc.).
        Doit retourner :
            - self (si on reste dans l'état)
            - Une nouvelle instance de State (si on change d'état)
        """
        return self

    def on_exit(self, drone):
        """Exécuté UNE FOIS quand on quitte l'état"""
        logging.info(f"<-- Sortie de l'état : {self.name}")