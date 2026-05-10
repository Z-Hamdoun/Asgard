import serial
import time
import threading
import json

PORT_ESP_A = '/dev/ttyACM0'  # Celui qui va ENVOYER
PORT_ESP_B = '/dev/ttyACM1'  # Celui qui va RECEVOIR
BAUDRATE = 115200

def ecouter_port(ser, nom_port):
    """Thread qui écoute en permanence un ESP32"""
    print(f"[{nom_port}] Écoute activée sur {ser.port}...")
    while True:
        try:
            # CORRECTION : Lecture bloquante (sans in_waiting)
            # C'est infiniment plus fiable sur l'USB Natif sous Ubuntu
            data = ser.readline()
            if data:
                ligne = data.decode('utf-8', errors='ignore').strip()
                if ligne:
                    # On affiche tout ce que les ESP32 "disent" sur leur câble USB
                    if nom_port == "ESP_B":
                        print(f"\n✅ [RX - ESP_B] A REÇU : {ligne}")
                    else:
                        print(f"\n⚠️ [TX - ESP_A] A PARLÉ : {ligne}")
        except Exception:
            break

def main():
    print("--- Démarrage du Diagnostic ESP-NOW Transparent ---")
    
    try:
        # Ouverture des ports
        ser_A = serial.Serial(PORT_ESP_A, BAUDRATE, timeout=1)
        ser_B = serial.Serial(PORT_ESP_B, BAUDRATE, timeout=1)
        
        # CORRECTION : Forcer les signaux DTR/RTS pour réveiller le port USB Natif
        ser_A.dtr = True
        ser_A.rts = True
        ser_B.dtr = True
        ser_B.rts = True
        
        # Nettoyage complet des tampons
        ser_A.reset_input_buffer()
        ser_B.reset_input_buffer()
        ser_A.reset_output_buffer()
        ser_B.reset_output_buffer()
        
    except Exception as e:
        print(f"ERREUR d'ouverture des ports USB : {e}")
        return

    # Lancement des DEUX threads d'écoute
    t_a = threading.Thread(target=ecouter_port, args=(ser_A, "ESP_A"), daemon=True)
    t_b = threading.Thread(target=ecouter_port, args=(ser_B, "ESP_B"), daemon=True)
    t_a.start()
    t_b.start()

    print("[SYS] Lancement de l'écoute. Pause de 3s pour l'initialisation...")
    time.sleep(3) 

    # --- CORRECTION : ASTUCE DE RÉVEIL ---
    # Le 1er paquet est souvent "mangé" par le port USB natif.
    print("[SYS] Envoi d'un octet de réveil...")
    ser_A.write(b"\n")
    ser_A.flush()
    time.sleep(0.5)

    # 1er test : Envoi d'une commande courte
    print(f"\n[SYS] Envoi d'une commande START sur ESP_A...")
    # On l'envoie 2 fois au cas où des ondes radio se perdent
    ser_A.write(b"CMD:START\n")
    ser_A.flush()
    time.sleep(0.1)
    ser_A.write(b"CMD:START\n")
    ser_A.flush() # Force l'envoi immédiat sur le câble USB
    
    time.sleep(2)

    # 2ème test : Envoi d'un JSON de configuration complet
    print(f"\n[SYS] Envoi d'une configuration JSON sur ESP_A...")
    config_test = {"lat_mission": 48.716, "lng_mission": 2.164, "alt": 15.5}
    json_str = json.dumps(config_test, separators=(',', ':'))
    message_cfg = f"CFG:{json_str}\n" 
    
    ser_A.write(message_cfg.encode('utf-8'))
    ser_A.flush()
    time.sleep(0.1)
    ser_A.write(message_cfg.encode('utf-8'))
    ser_A.flush()

    # On attend pour voir si l'ESP B réagit, ou si l'ESP A plante
    print("\n[SYS] Attente des retours radio (Pause de 4s)...")
    time.sleep(4)
    
    print("\n[SYS] Test terminé. Fermeture des ports.")
    ser_A.close()
    ser_B.close()

if __name__ == "__main__":
    main()