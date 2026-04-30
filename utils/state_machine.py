from abc import ABC

class State(ABC):
    @property
    def name(self):
        return self.__class__.__name__

    def on_enter(self, drone):
        """Exécuté UNE FOIS quand on entre dans l'état"""
        pass

    def on_execute(self, drone):
        """Exécuté EN BOUCLE. Doit retourner self ou un nouvel État."""
        return self

    def on_exit(self, drone):
        """Exécuté UNE FOIS quand on quitte l'état"""
        pass