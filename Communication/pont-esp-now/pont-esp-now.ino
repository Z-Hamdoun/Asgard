#include <esp_now.h>
#include <WiFi.h>

// Adresse de broadcast : FF:FF:FF:FF:FF:FF
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ============================================================================
// CALLBACK : QUAND ON REÇOIT UNE ONDE RADIO
// ============================================================================
void OnDataRecv(const esp_now_recv_info * info, const uint8_t *incomingData, int len) {
    Serial.print("[RADIO-RX] J'ai recu par les airs : ");
    for(int i=0; i<len; i++) {
        Serial.print((char)incomingData[i]);
    }
    Serial.println();
}

// ============================================================================
// CALLBACK : QUAND ON A FINI D'ENVOYER UNE ONDE RADIO
// ============================================================================
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
    Serial.print("[RADIO-TX] Statut de l'envoi radio : ");
    Serial.println(status == ESP_NOW_SEND_SUCCESS ? "OK" : "ECHEC");
}

void setup() {
    Serial.begin(115200);
    Serial.setTimeout(100); // Accélère la lecture USB
    delay(2000); // On laisse le temps à l'USB de s'initialiser
    
    Serial.println("\n=== BOOT ESP32-C3 ===");
    
    // Initialisation du Wi-Fi
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    delay(100);

    // Initialisation ESP-NOW
    if (esp_now_init() != ESP_OK) {
        Serial.println("!!! ERREUR : Initialisation ESP-NOW impossible !!!");
        return;
    }
    Serial.println("- ESP-NOW Initialise avec succes");

    // Enregistrement des callbacks
    esp_now_register_recv_cb(OnDataRecv);
    
    // CORRECTION ICI : On force le cast (esp_now_send_cb_t) pour satisfaire le compilateur de la version 3.x
    esp_now_register_send_cb((esp_now_send_cb_t)OnDataSent);

    // Configuration du "Peer" (Le destinataire)
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, broadcastAddress, 6);
    peerInfo.channel = 0;  
    peerInfo.encrypt = false;
    
    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("!!! ERREUR : Impossible d'ajouter l'adresse Broadcast !!!");
        return;
    }
    Serial.println("- Adresse Broadcast ajoutee");
    Serial.println("=== PRET A TRANSMETTRE ===");
}

void loop() {
    // Si Python nous envoie quelque chose par le câble USB
    if (Serial.available()) {
        String msg = Serial.readStringUntil('\n');
        msg.trim(); 
        
        if (msg.length() > 0) {
            Serial.print("[USB-RX] J'ai lu sur le cable USB : ");
            Serial.println(msg);
            
            if(msg.length() > 240) {
                msg = msg.substring(0, 240);
            }
            
            // On tire l'onde radio !
            esp_err_t result = esp_now_send(broadcastAddress, (uint8_t *)msg.c_str(), msg.length());
            
            if (result != ESP_OK) {
                Serial.println("[RADIO-TX] ERREUR : La puce a refuse d'envoyer l'onde !");
            }
        }
    }
}