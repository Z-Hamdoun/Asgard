import time
from pymavlink import mavutil

class Timesync_Handler:
    """Permet de gérer le protocole timesync"""
    def __init__(self,
            master: mavutil.mavfile,
            send_automatic_timesync: bool,
            timesync_delay: int,
            logger
        ):
        """Initialize l'objet.

        Args:
            master (mavutil.mavfile): Master.
            send_automatic_timesync (bool): Si on envoie des TIMESYNC automatiquement ou non.
            timesync_delay (int): Temps d'attente entre 2 TIMESYNC envoyés.
            logger (Logger): Logger utilisé.
        """
        self.logger = logger
        self.master = master
        self._latence_ms_by_sysidcompid = {}
        self._all_ts1_sent = []
        self._send_automatic_timesync = send_automatic_timesync
        self._timesync_delay = timesync_delay
        self._nb_heartbeat_since_last_timesync = timesync_delay # Variable permettant de compter les HEARTBEAT envoyés pour le TIMESYNC
    
    @property
    def ts1(self) -> int:
        """Sert pour le timesync"""
        return time.time_ns()
    
    def send_timesync(self) -> None:
        """Envoie un TIMESYNC en broadcast pour obtenir les latences de connexion"""
        # Pour regarder les différentes latences obtenues, utiliser latence = self.get_latence_ms_with_sysidcompid(key)
        self.master.mav.timesync_send(0, self.ts1)
    
    def _send_callback(self, m) -> None:
        """A appeler à chaque envoi de timesync"""
        if m.tc1 == 0: # On envoie une requête
            if m.ts1 not in self._all_ts1_sent:
                self._all_ts1_sent.append(m.ts1)
            if len(self._all_ts1_sent) > 10:
                self._all_ts1_sent.pop(0) # On évite d'avoir une liste trop grosse
    
    def _send_heartbeat_callback(self) -> None:
        """A appeler à chaque envoi de HEARTBEAT"""
        if self._send_automatic_timesync:
            if self._nb_heartbeat_since_last_timesync >= self._timesync_delay:
                self.send_timesync()
                self._nb_heartbeat_since_last_timesync = 1
            else:
                self._nb_heartbeat_since_last_timesync += 1
    
    def _receive(self, m) -> bool:
        """Recoit la réponse d'un timesync envoyé
        
        Returns:
            bool: Si c'est une réponse à l'un de nos timesync ou non.
        """
        tc1 = m.tc1
        ts1 = m.ts1
        if ts1 in self._all_ts1_sent and tc1 != 0: # C'est une réponse à l'un de nos timesync
            temps_aller_retour_ns = max(time.time_ns() - ts1, 0) # Eviter les bugs de retour d'horloge interne
            latence_ns = temps_aller_retour_ns // 2
            key = (m.get_srcSystem(), m.get_srcComponent())
            latence_ms = int(latence_ns // 1e6)
            self._latence_ms_by_sysidcompid[key] = latence_ms
            if not self._send_automatic_timesync:
                self.logger.log(f"<Nouvelle latence avec {key}: {latence_ms} ms>", wanna_print=False)
        else:
            if m.tc1 == 0: # C'est une requête
                self.master.mav.timesync_send(self.ts1, m.ts1)
    
    def get_latence_ms_with_sysidcompid(self, key: tuple[int, int]) -> int:
        """Renvoie la latence estimée d'un aller entre notre système et (sysid, compid) en ms.
        
        Args:
            key (tuple[int, int]): (sysid, compid)
        
        Returns:
            int: Latence en ms. NaN si aucune donnée reçue.
        """
        return self._latence_ms_by_sysidcompid.get(key, float('NaN'))
