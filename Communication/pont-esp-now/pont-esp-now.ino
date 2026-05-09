#include <esp_now.h>
#include <WiFi.h>

// Adresse de broadcast : envoie à tous les ESP32 aux alentours
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ============================================================================
// ESP-NOW vers RPI
// ============================================================================
void OnDataRecv(const esp_now_recv_info * info, const uint8_t *incomingData, int len) {
    // On écrit les données brutes sur le port Série (vers Python)
    for(int i=0; i<len; i++) {
        Serial.write(incomingData[i]);
    }
    // On ajoute un retour à la ligne pour que Python (readline) sache que c'est fini
    Serial.print('\n'); 
}

void setup() {
    Serial.begin(115200);
    WiFi.mode(WIFI_STA);

    if (esp_now_init() != ESP_OK) return;
    esp_now_register_recv_cb(OnDataRecv);

    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, broadcastAddress, 6);
    peerInfo.channel = 0;  
    peerInfo.encrypt = false;
    esp_now_add_peer(&peerInfo);
}

// ============================================================================
// RPI vers ESP-NOW
// ============================================================================
void loop() {
    if (Serial.available()) {
        // On lit tout le texte envoye par Python jusqu'au retour a la ligne
        String msg = Serial.readStringUntil('\n');
        msg.trim(); // Nettoyage
        
        if (msg.length() > 0) {
            // Sécurité : ESP-NOW ne supporte que 250 octets max par paquet
            if(msg.length() > 240) {
                msg = msg.substring(0, 240);
            }
            // Envoi dans les airs
            esp_now_send(broadcastAddress, (uint8_t *)msg.c_str(), msg.length());
        }
    }
}