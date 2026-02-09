// Détection de frames par timeout

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// L'adresse Mac du récepteur
#include "../../card_info.h" // Adjust the path as needed
#define ESPNOW_WIFI_CHANNEL GLOBAL_WIFI_CHANNEL
#define MacAdress MAC_CARTE_2 // counterpart MAC address
//#define MacAdress MAC_BROADCAST // counterpart MAC address

#define DATARATE WIFI_PHY_RATE_6M
//#define DATARATE WIFI_PHY_RATE_2M_L
#define BAUD_RATE  115200
#define debug true

#define BUFFER_SIZE 1400 // max of 250 bytes


const uint32_t timeout_micros = (int)(1.0 / BAUD_RATE * 1E6) * 20;

uint8_t buf_recv[BUFFER_SIZE];
uint8_t buf_send[BUFFER_SIZE];
uint16_t buf_size = 0;
uint32_t send_timeout = 0;

esp_now_peer_info_t peerInfo; // Crée une variable pour stocker les informations du partage

void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  return;
}

// Fonction de réception des données
void OnDataRecv(const esp_now_recv_info* info, const uint8_t* incomingData, int len) {
  memcpy(&buf_recv, incomingData, sizeof(buf_recv));
  Serial.write(buf_recv, len);
}

void setup() {
  Serial.begin(BAUD_RATE);
  WiFi.mode(WIFI_STA); // Active le wifi 
  esp_wifi_set_channel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  delay(1000);

  //esp_wifi_config_espnow_rate(WIFI_IF_STA, DATARATE);
  if (debug){
    Serial.print("Board MAC : ");
    Serial.println(WiFi.macAddress());

    Serial.print("Remote board : ");
    Serial.printf("%02X%02X%02X%02X%02X%02X\n",
                  MacAdress[0], MacAdress[1], MacAdress[2],
                  MacAdress[3], MacAdress[4], MacAdress[5]);

    Serial.println();
    Serial.print("IDF Version : ");
    Serial.println(ESP_IDF_VERSION);

    Serial.print("IDF5 Version : ");
    Serial.println(ESP_IDF_VERSION_VAL(5, 0, 0));
  }
  // Initialisation de ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }


  esp_now_register_recv_cb(OnDataRecv);
  //esp_now_register_send_cb(OnDataSent); // permet d'envoyer l'accusé de réception

  memcpy(peerInfo.peer_addr, MacAdress, 6);
  peerInfo.channel = ESPNOW_WIFI_CHANNEL;
  peerInfo.encrypt = false; // Ajoute un pair

  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Failed to add peer");
    return;
  } // Affiche s'il y a eu un problème lors de l'ajout du pair
}


char serialBuffer[1470];
int bufferIndex = 0;


void loop() {
  if (Serial.available()) {
    while (Serial.available() && buf_size < BUFFER_SIZE) {
      buf_send[buf_size] = Serial.read();
      send_timeout = micros() + timeout_micros;
      buf_size++;
    }
  }

  if (buf_size == BUFFER_SIZE || (buf_size > 0 && micros() >= send_timeout)) {
    esp_err_t result = esp_now_send(MacAdress, (uint8_t *) &buf_send, buf_size);
    buf_size = 0;
  }
}
