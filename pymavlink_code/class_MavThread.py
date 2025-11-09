import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from threading import Event, Thread
from pymavlink import mavutil

from divers.class_Logger import Logger


class MavThread:
    def __init__(self,
            master: mavutil.mavfile,
            logger: Logger = Logger()
        ):
        """Gère les Threads.
        
        Args:
            master (mavutil.mavfile): Master.
            logger (Logger): Logger utilisé.
        """
        self.logger = logger
        self.master = master
        # Thread d'envoi de HEARTBEATS
        self._heartbeat_thread = None
        # Thread de réception de messages
        self._mavlink_messages_thread = None
        # Events gérant la fermeture des threads
        self._disable_listening_thread = Event()
        self._listening_thread_disabled = Event()
        self._listening_thread_disabled.set()
        self._disable_heartbeat_thread = Event()
        self._heartbeat_thread_disabled = Event()
        self._heartbeat_thread_disabled.set()
    
    def start_listening_thread(self) -> None:
        """Ouvre le Thread d'écoute des messages MAVLink."""
        if self._listening_thread_disabled.is_set():
            self._listening_thread_disabled.clear()
            self._disable_listening_thread.clear()
            self._mavlink_messages_thread = Thread(target=self._mavlink_messages_thread_func, args=(), daemon=True)
            self._mavlink_messages_thread.start() # On commence à écouter les messages
    
    def start_heartbeat_thread(self) -> None:
        """Ouvre le Thread d'envoi de HEARTBEAT."""
        if self._heartbeat_thread_disabled.is_set():
            self._heartbeat_thread_disabled.clear()
            self._disable_heartbeat_thread.clear()
            self._heartbeat_thread = Thread(target=self._heartbeat_thread_func, args=(), daemon=True)
            self._heartbeat_thread.start() # On commence à envoyer les heartbeats
    
    def start_threads(self) -> None:
        """Ouvre les Threads"""
        self.start_listening_thread()
        self.start_heartbeat_thread()
    
    def stop_listening_thread(self) -> bool:
        """Stoppe le Thread d'écoute des messages MAVLink.
        
        Returns:
            bool: Si le Thread s'est bien arrêté ou non.
        """
        if not self._listening_thread_disabled.is_set():
            self._disable_listening_thread.set()
            return self._listening_thread_disabled.wait()
        return True

    def stop_heartbeat_thread(self) -> bool:
        """Stoppe le Thread d'envoi de HEARTBEAT.
        
        Returns:
            bool: Si le Thread s'est bien arrêté ou non.
        """
        if not self._heartbeat_thread_disabled.is_set():
            self._disable_heartbeat_thread.set()
            return self._heartbeat_thread_disabled.wait()
        return True
    
    def stop_threads(self) -> tuple[bool, bool]:
        """Stoppe les Threads en cours d'exécution.
        
        Returns:
            tuple:
                - **listening_disabled** (*bool*) – Listening Thread disabled ou non.
                - **heartbeat_disabled** (*bool*) – Heartbeat Thread disabled ou non.
        """
        listening_disabled = self.stop_listening_thread()
        heartbeat_disabled = self.stop_heartbeat_thread()
        return listening_disabled, heartbeat_disabled
    
    def _mavlink_messages_thread_func(self):
        """Thread qui écoute les messages MAVLink."""
        while not self._disable_listening_thread.is_set(): # Tant que nous voulons rester connecté
            try:
                self.master.recv_match(blocking=True, timeout=0.5)
            except Exception:
                if not self._disable_listening_thread.is_set():
                    self.logger.log(exception=True)
                    self._disable_listening_thread.wait(timeout=0.1) # Evite le lag
        self._listening_thread_disabled.set()
    
    def _heartbeat_thread_func(self):
        """Thread qui envoie des HEARTBEATs à 1 Hz."""
        if self.master.source_component in [mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER, mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER2, mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER3, mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER4]:
            mav_type = mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER
        elif self.master.source_component == mavutil.mavlink.MAV_COMP_ID_GPS:
            mav_type = mavutil.mavlink.MAV_TYPE_GPS
        else:
            mav_type = mavutil.mavlink.MAV_TYPE_GCS
        
        while not self._disable_heartbeat_thread.is_set(): # As long as we want to be connected.
            try:
                self.master.mav.heartbeat_send(mav_type, mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
            except Exception:
                if not self._disable_heartbeat_thread.is_set():
                    self.logger.log(exception=True)
            self._disable_heartbeat_thread.wait(timeout=1) # 1 Hz
        self._heartbeat_thread_disabled.set()
