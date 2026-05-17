#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// Adresse de broadcast : FF:FF:FF:FF:FF:FF
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

char rx_buffer[250];
int rx_index = 0;

// ============================================================================
// CALLBACK : RÉCEPTION RADIO -> ENVOI VERS RASPBERRY PI (USB CDC)
// ============================================================================
void OnDataRecv(const esp_now_recv_info * info, const uint8_t *incomingData, int len) {
    for(int i=0; i<len; i++) {
        Serial.write(incomingData[i]);
    }
    Serial.write('\n');
}

// ============================================================================
// CALLBACK : ENVOI RADIO
// ============================================================================
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {

}

void setup() {
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
// LECTURE RASPBERRY PI (USB CDC) -> ENVOI RADIO
// ============================================================================
void loop() {
    while (Serial.available() > 0) {
        char c = Serial.read();

        // Si on détecte la fin d'une ligne envoyée par Python
        if (c == '\n') {
            rx_buffer[rx_index] = '\0';
            String msg = String(rx_buffer);
            msg.trim();

            if (msg.length() > 0) {
                esp_now_send(broadcastAddress, (uint8_t *)msg.c_str(), msg.length());
            }

            rx_index = 0;

        }
        else if (c != '\r') {
            if (rx_index < 248) {
                rx_buffer[rx_index] = c;
                rx_index++;
            } else {
                rx_index = 0; // message trop long : on vide et on repart
            }
        }
    }
}
