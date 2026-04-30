#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include "card_info.h"

#define ESPNOW_WIFI_CHANNEL GLOBAL_WIFI_CHANNEL
#define REMOTE_MAC MAC_CARTE_2 // L'adresse de l'AUTRE ESP32

esp_now_peer_info_t peerInfo;

// --- CALLBACK RÉCEPTION (ESP-NOW -> RPI) ---
void OnDataRecv(const esp_now_recv_info* info, const uint8_t* incomingData, int len) {
  // On envoie directement les données reçues au Raspberry Pi via le port Série
  Serial.write(incomingData, len);
}

// --- CALLBACK ENVOI (Optionnel, pour le debug) ---
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  // Optionnel : clignoter une LED si status == ESP_NOW_SEND_SUCCESS
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) return;

  // Enregistrement du callback de réception
  esp_now_register_recv_cb(OnDataRecv);

  // Configuration du pair (l'autre ESP32)
  memcpy(peerInfo.peer_addr, REMOTE_MAC, 6);
  peerInfo.channel = ESPNOW_WIFI_CHANNEL;
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) return;
}

void loop() {
  // --- TRANSMISSION (RPI -> ESP-NOW) ---
  // On vérifie si le Raspberry Pi a envoyé quelque chose sur le port série
  if (Serial.available() > 0) {
    uint8_t buffer[250]; // ESP-NOW est limité à 250 octets par message
    int len = Serial.readBytes(buffer, sizeof(buffer));
    
    // On envoie ces données à l'autre ESP32
    esp_now_send(REMOTE_MAC, buffer, len);
  }
}