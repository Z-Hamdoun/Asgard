#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// Adresse de broadcast : FF:FF:FF:FF:FF:FF
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// Tampon de lecture USB manuel (Sécurité pour ESP32-C3)
char rx_buffer[250];
int rx_index = 0;

// ============================================================================
// CALLBACK : RÉCEPTION RADIO -> ENVOI VERS RASPBERRY PI (USB)
// ============================================================================
void OnDataRecv(const esp_now_recv_info * info, const uint8_t *incomingData, int len) {
    // Mode transparent : on écrit directement les données brutes
    for(int i=0; i<len; i++) {
        Serial.write(incomingData[i]);
    }
    Serial.print('\n'); // Fin de message pour Python (readline)
}

// ============================================================================
// CALLBACK : ENVOI RADIO 
// ============================================================================
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {

}

void setup() {
    // Agrandissement des buffers pour l'USB Natif (Crucial !)
    Serial.setRxBufferSize(1024);
    Serial.setTxBufferSize(1024);
    Serial.begin(115200);
    
    delay(1000);
    
    // Initialisation du Wi-Fi sur le canal 1 explicitement
    WiFi.mode(WIFI_STA);
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

    // Initialisation ESP-NOW
    if (esp_now_init() != ESP_OK) {
        return; // Si échec, on s'arrête en silence
    }

    // Enregistrement des callbacks
    esp_now_register_recv_cb(OnDataRecv);
    esp_now_register_send_cb((esp_now_send_cb_t)OnDataSent);

    // Configuration du "Peer" (Destinataire Broadcast)
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, broadcastAddress, 6);
    peerInfo.channel = 1;  
    peerInfo.encrypt = false;
    
    esp_now_add_peer(&peerInfo);
}

// ============================================================================
// LECTURE RASPBERRY PI (USB) -> ENVOI RADIO
// ============================================================================
void loop() {
    // LECTURE OCTET PAR OCTET (Plus sûr que readStringUntil sur C3)
    while (Serial.available() > 0) {
        char c = Serial.read();
        
        // Si on détecte la fin d'une ligne envoyée par Python
        if (c == '\n') {
            rx_buffer[rx_index] = '\0'; // Fermer la chaîne de caractères
            String msg = String(rx_buffer);
            msg.trim(); 
            
            // S'il y a vraiment du texte, on l'envoie en radio
            if (msg.length() > 0) {
                esp_now_send(broadcastAddress, (uint8_t *)msg.c_str(), msg.length());
            }
            
            // Réinitialiser le buffer pour le prochain message
            rx_index = 0;
            
        } 
        // Sinon, on ajoute la lettre au buffer (en ignorant les retours chariot Windows)
        else if (c != '\r') {
            if (rx_index < 248) {
                rx_buffer[rx_index] = c;
                rx_index++;
            }
        }
    }
}