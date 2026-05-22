import serial
import time
import argparse
import json

BAUDRATE = 115200


def run_rx(port):
    print(f"[RX] Démarrage de l'écoute sur {port}...")
    try:
        ser = serial.Serial(port, BAUDRATE, timeout=1)
        ser.dtr = True
        ser.rts = True
        ser.reset_input_buffer()

        while True:
            data = ser.readline()
            if data:
                ligne = data.decode("utf-8", errors="ignore").strip()
                if ligne:
                    print(f"✅ [REÇU] : {ligne}")
    except KeyboardInterrupt:
        print("\n[RX] Arrêt manuel.")
    except Exception as e:
        print(f"[RX] ERREUR : {e}")
    finally:
        if "ser" in locals() and ser.is_open:
            ser.close()


def run_tx(port):
    print(f"[TX] Démarrage de l'émission sur {port}...")
    try:
        ser = serial.Serial(port, BAUDRATE, timeout=1)
        ser.dtr = True
        ser.rts = True
        ser.reset_output_buffer()
        time.sleep(2)  # Temps de stabilisation du port série

        print("[TX] Envoi de l'octet de réveil...")
        ser.write(b"\n")
        ser.flush()
        time.sleep(0.5)

        print("[TX] Envoi de la commande START...")
        ser.write(b"CMD:START\n")
        ser.flush()
        time.sleep(2)

        print("[TX] Envoi de la configuration JSON...")
        config_test = {"lat_mission": 48.716, "lng_mission": 2.164, "alt": 15.5}
        json_str = json.dumps(config_test, separators=(",", ":"))
        message_cfg = f"CFG:{json_str}\n"

        ser.write(message_cfg.encode("utf-8"))
        ser.flush()
        print(f"[TX] Message envoyé : {message_cfg.strip()}")

    except Exception as e:
        print(f"[TX] ERREUR : {e}")
    finally:
        if "ser" in locals() and ser.is_open:
            ser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test du pont ESP-NOW")
    parser.add_argument(
        "--mode",
        choices=["tx", "rx"],
        required=True,
        help="Mode d'exécution : tx (émetteur) ou rx (récepteur)",
    )
    parser.add_argument("--port", default="/dev/ttyAMA1", help="Port série de l'ESP32")

    args = parser.parse_args()

    if args.mode == "rx":
        run_rx(args.port)
    else:
        run_tx(args.port)
