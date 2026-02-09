#include <WiFi.h>

// --- Configuration Wi-Fi ---
const char* ssid = "VOTRE_SSID";
const char* password = "VOTRE_MOT_DE_PASSE";
// --------------------------

// --- Configuration RPi 1 (Serveur Source) ---
const char* rpi1_ip = "192.168.1.10"; // <--- IP du RPi 1
const int rpi1_port = 8000;
WiFiClient source_client; // Client pour RPi 1
// ---------------------------------------------

// --- Configuration ESP32-2 (Serveur Relais) ---
WiFiServer relay_server(8001); // Ouvre un serveur sur le port 8001
WiFiClient relay_client;       // Client connecté (ESP32-2)
// ----------------------------------------------

void setup_wifi() {
    // Connexion au réseau Wi-Fi... (omise pour concision)
    // ...
}

void setup() {
    Serial.begin(115200);
    setup_wifi();

    // Démarrage du serveur relais (ESP32-2 se connectera ici)
    relay_server.begin();
    Serial.println("Serveur Relais démarré, en attente de l'ESP32-2...");

    // Tenter la connexion au RPi 1 (Source)
    if (!source_client.connect(rpi1_ip, rpi1_port)) {
        Serial.println("Échec de la connexion au RPi 1 Source !");
    } else {
        Serial.println("Connecté au RPi 1 Source.");
    }
}

void loop() {
    // Étape 1 : Accepter la connexion de l'ESP32-2 (si elle n'est pas déjà là)
    if (!relay_client.connected()) {
        relay_client = relay_server.available();
        if (relay_client) {
            Serial.println("ESP32-2 (Client) connecté au Relais !");
        }
    }

    // Étape 2 : Relayer le flux du RPi 1 vers l'ESP32-2
    if (source_client.connected() && relay_client.connected()) {
        // Relai brut des données
        while (source_client.available()) {
            // Lecture/Écriture brute (octet par octet, efficace pour le relai)
            size_t bytes_read = source_client.read();
            if (bytes_read > 0) {
                // Buffer de taille fixe pour le relai (peut être optimisé)
                uint8_t buffer[bytes_read]; 
                // Relire dans le buffer pour l'écriture
                source_client.readBytes(buffer, bytes_read); 
                relay_client.write(buffer, bytes_read);
            }
        }
    } else if (!source_client.connected()) {
        // Reconnexion au RPi 1 si perdu
        if (!source_client.connect(rpi1_ip, rpi1_port)) {
            delay(1000);
        } else {
            Serial.println("Reconnecté au RPi 1.");
        }
    }
}