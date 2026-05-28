import traceback
import time
import os

class Logger:
    """Classe permettant une meilleure gestion des logs."""
    def __init__(self,
            log_file: str | None = None,
            clear_existing_logs: bool = True
        ):
        """Classe permettant une meilleure gestion des logs.

        Args:
            log_file (str | None): Chemin du fichier de log.
            clear_existing_logs (bool): Indique si on veut supprimer les logs déjà présents où non.
        """
        if log_file == "None":
            log_file = None # Au cas où, notamment pour les parsers
        if log_file is not None:
            try:
                if clear_existing_logs:
                    with open(log_file, "w", encoding="utf-8") as file:
                        pass  # Efface le contenu
                else:
                    # On regarde s'il y a déjà du contenu ou pas
                    empty_file = False
                    with open(log_file, "r", encoding="utf-8") as file:
                        content = file.read()
                        if not content:
                            empty_file = True
                    if not empty_file: # S'il y a déjà du contenu
                        with open(log_file, "a", encoding="utf-8") as file:
                            # On sépare les logs
                            file.write("\n\n")
                            file.write("--------")
                            file.write("New logs")
                            file.write("--------")
                            file.write("\n\n")
            except Exception as e:
                print("Incorrect log file. Impossible to write :")
                raise e
        self._log_file = log_file
        self._time_boot = time.time()

    def log(self,
            details: any = None,
            wanna_print: bool = True,
            exception: bool = False
        ) -> None:
        """Fonction faisant un log.

        Args:
            details: Ce qu'on veut log. Par défaut, log une Exception.
            wanna_print (bool): Indique si on veut print le log ou non.
            exception (bool): Indique si on veut print une Exception ou non.
        """
        if exception:
            str_to_print = traceback.format_exc()
        else:
            str_to_print = f"{details}"
        if wanna_print:
            print(str_to_print)
        if self._log_file:
            with open(self._log_file, "a", encoding="utf-8") as file:  # "a" = append
                file.write(f"{int((time.time() - self._time_boot) * 1e3)} ms\n")
                file.write(f"{str_to_print}\n")
                file.write("\n")


def make_logger(filepath: str, max_sessions: int = 3) -> Logger:
    """Crée un Logger avec rotation automatique des sessions.

    Si le fichier contient déjà max_sessions sessions (séparées par
    '--------New logs--------'), il est effacé et la numérotation repart de zéro.

    Args:
        filepath:     Chemin du fichier .log à créer ou à compléter.
        max_sessions: Nombre maximum de sessions conservées (défaut 3).
    """
    clear = True
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # Chaque séparateur correspond à une session supplémentaire après la première
            nb_separateurs = content.count("--------New logs--------")
            clear = (nb_separateurs >= max_sessions - 1)
        except Exception:
            clear = True

    return Logger(log_file=filepath, clear_existing_logs=clear)
