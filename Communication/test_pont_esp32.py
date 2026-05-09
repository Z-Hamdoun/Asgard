import serial
import time
import threading
import json

PORT_ESP_A = '/dev/ttyACM0'  # Celui qui va ENVOYER
PORT_ESP_B = '/dev/ttyACM1'  # Celui qui va RECEVOIR
BAUDRATE = 115200

def ecouter_esp_b(ser_b):
    """Thread qui écoute en permanence le 2ème ESP32"""
    print(f"[RX] Écoute activée sur {PORT_ESP_B}...")
    while True:
        try:
            if ser_b.in_waiting > 0:
                ligne = ser_b.readline().decode('utf-8', errors='ignore').strip()
                if ligne:
                    print("\n" + "="*50)
                    print(f"SUCCÈS ! Données reçues via ESP-NOW :")
                    print(f" -> Message brut : {ligne}")
                    print("="*50 + "\n")
        except Exception as e:
            print(f"[RX] Erreur : {e}")
            break
        time.sleep(0.01)

def main():
    print("--- Démarrage du Test ESP-NOW Transparent ---")
    
    try:
        ser_A = serial.Serial(PORT_ESP_A, BAUDRATE, timeout=1)
        ser_B = serial.Serial(PORT_ESP_B, BAUDRATE, timeout=1)
        
        # Astuce indispensable pour les ESP32-C3 (Force l'activation du port série USB natif)
        ser_A.setDTR(False); time.sleep(0.05); ser_A.setDTR(True)
        ser_B.setDTR(False); time.sleep(0.05); ser_B.setDTR(True)
        
    except Exception as e:
        print(f"ERREUR d'ouverture des ports USB : {e}")
        return

    # Lancement du thread d'écoute sur l'ESP B
    thread_rx = threading.Thread(target=ecouter_esp_b, args=(ser_B,), daemon=True)
    thread_rx.start()

    time.sleep(2) # Laisse le temps aux ESP32 de s'initialiser

    # 1er test : Envoi d'une commande
    print(f"\n[TX] Envoi d'une commande START sur {PORT_ESP_A}...")
    ser_A.write("CMD:START\n".encode('utf-8'))
    time.sleep(1)

    # 2ème test : Envoi d'un JSON de configuration complet
    print(f"[TX] Envoi d'une configuration JSON sur {PORT_ESP_A}...")
    config_test = {"lat_mission": 48.716, "lng_mission": 2.164, "alt": 15.5}
    json_str = json.dumps(config_test, separators=(',', ':'))
    
    message_cfg = f"CFG:{json_str}\n" 
    ser_A.write(message_cfg.encode('utf-8'))

    # On attend un peu pour laisser le temps au print de s'afficher
    time.sleep(2)
    
    ser_A.close()
    ser_B.close()
    print("Test terminé.")

if __name__ == "__main__":
    main()