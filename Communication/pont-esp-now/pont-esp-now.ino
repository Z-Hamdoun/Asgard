#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// Adresse de broadcast : FF:FF:FF:FF:FF:FF
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ============================================================================
// CONFIGURATION UART MATÉRIEL (ESP32-C3)
// ============================================================================
// On assigne manuellement l'UART aux broches 20 et 21
#define RPI_RX_PIN 20 // L'ESP32 ÉCOUTE ici (à relier au TX de la RPi)
#define RPI_TX_PIN 21 // L'ESP32 PARLE ici (à relier au RX de la RPi)

HardwareSerial SerialRPI(0); 

char rx_buffer[250];
int rx_index = 0;

// ============================================================================
// CALLBACK : RÉCEPTION RADIO -> ENVOI VERS RASPBERRY PI (UART)
// ============================================================================
void OnDataRecv(const esp_now_recv_info * info, const uint8_t *incomingData, int len) {
    for(int i=0; i<len; i++) {
        SerialRPI.write(incomingData[i]);
    }
    SerialRPI.write('\n');
}

// ============================================================================
// CALLBACK : ENVOI RADIO
// ============================================================================
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
    // Vide, pour ne pas polluer l'UART
}

void setup() {
    SerialRPI.setRxBufferSize(1024);
    SerialRPI.setTxBufferSize(1024);
    
    // On active l'UART en forçant l'utilisation des broches 20 et 21
    SerialRPI.begin(115200, SERIAL_8N1, RPI_RX_PIN, RPI_TX_PIN);

    delay(1000);

    // Initialisation du Wi-Fi sur le canal 1 explicitement
    WiFi.mode(WIFI_STA);
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

    // Initialisation ESP-NOW
    if (esp_now_init() != ESP_OK) {
        return; // Si échec, on s'arrête en silence
    }

    esp_now_register_recv_cb(OnDataRecv);
    esp_now_register_send_cb((esp_now_send_cb_t)OnDataSent);

    // Configuration du "Peer" (Destinataire Broadcast)
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, broadcastAddress, 6);
    peerInfo.channel = 1;
    peerInfo.encrypt = false;

    esp_now_add_peer(&peerInfo);
    
    SerialRPI.println("[SYS] ESP32-C3 PRET (UART MATERIEL 20/21)");
}

// ============================================================================
// LECTURE RASPBERRY PI (UART) -> ENVOI RADIO
// ============================================================================
void loop() {
    while (SerialRPI.available() > 0) {
        char c = SerialRPI.read();

        // Si on détecte la fin d'une ligne
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