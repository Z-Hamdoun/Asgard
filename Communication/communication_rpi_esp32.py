import serial
import sys
import time
from pymavlink import mavutil

# --- CONFIGURATION DU PORT SERIE ---
# Assurez-vous que ce port et ce Baud Rate correspondent a l'ESP32 Serial1.begin()!
SERIAL_PORT = '/dev/serial0'  # Souvent le lien symbolique vers le bon UART
BAUD_RATE = 921600         # Vitesse haute pour la liaison RPI ↔ ESP32

def init_serial_connection() -> serial.Serial:
    """Initialise et retourne l'objet de connexion serie.
    Le type de retour est un gestionnaire de flux, qui permet de contrôler et d'intéragir avec le matériel UART
    """
    try:
        # Configuration : Port, Vitesse, et Timeout de 1 seconde pour la lecture
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) 
        ser.flush() # Vide le buffer d'entree/sortie
        print(f"Port serie {SERIAL_PORT} ouvert avec succes a {BAUD_RATE} bauds.")
        return ser
    except serial.SerialException as e:
        print(f"Erreur d'initialisation du port serie: {e}")
        print("   -> Verifiez le cablage (TX/RX), les droits d'acces, et la configuration du RPI (raspi-config).")
        sys.exit(1) # Quitter si la connexion echoue

def parse_data(line) -> dict:
    """Analyse la ligne de donnees 'Clé:Valeur' envoyee par l'ESP32."""
    data = {}
    
    # L'ESP32 est cense envoyer 'POS:10.5,SPD:2.4'
    if ':' not in line:
        return data # Ignorer les lignes sans separateur Cle:Valeur

    # Supposons le format CSV simple
    parts = line.split(',')
    
    for part in parts:
        try:
            key, val = part.split(':', 1) # Diviser en deux parties max
            data[key.strip()] = val.strip()
        except ValueError:
            continue # Ignorer les parties mal formees
            
    return data

def main():
    ser = init_serial_connection()
    # 1. Initialiser le 'master' MAVLink a partir de la connexion serie
    master = mavutil.mavlink_connection(ser) 
    
    print("\n--- En attente des messages MAVLink ---")
    
    while True:
        # 2. Utiliser la methode de lecture bloquante de MAVLink
        msg = master.recv_match(type=['ATTITUDE', 'GLOBAL_POSITION_INT'], blocking=True)
        
        if msg:
            # 3. L'objet msg est un message MAVLink decode
            print(f"[{msg.get_type()}] Recu d'un drone (ID: {msg.get_srcSystem()}):")

            if msg.get_type() == 'ATTITUDE':
                print(f"   -> Roulis: {msg.roll:.2f} deg, Tangage: {msg.pitch:.2f} deg")

        time.sleep(0.01)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterruption de l'utilisateur. Programme arrete.")
        # Le port serie sera ferme automatiquement si vous avez une reference 'ser' non globale