// Envoi de données avec parsing des messages par la librairie MAVLink
// Bi directionnel : prend ce qui vient du réseau esp32 et l'envoie au fc
// Prend ce qui vient fc et l'envoie au réseau esp32 avec un tri de messages
// ici, on envoie tout sauf les STATUSTEXT provenant de sysid=11 et compid=191
// pas d'affichage LED

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <Arduino.h>
#include <mavlink/ardupilotmega/mavlink.h>

// L'adresse Mac du récepteur
#include "../../card_info.h"
#define ESPNOW_WIFI_CHANNEL GLOBAL_WIFI_CHANNEL
//#define MacAdress MAC_CARTE_2
#define MacAdress MAC_BROADCAST
// #define MacAdress2 MAC_CARTE_1

#define DATARATE WIFI_PHY_RATE_9M
//#define DATARATE WIFI_PHY_RATE_2M_L
#define BAUD_RATE  115200
#define debug true

// Ensure your BUFFER_SIZE is at least this (MAVLink v2 max total: 10 + 255 + 2 + 13 = 280)
#ifndef BUFFER_SIZE
  #define BUFFER_SIZE 300 //1470
#endif
#define LED_PIN LED_BUILTIN   // or any GPIO you want

const uint32_t timeout_micros = (int)(1.0 / BAUD_RATE * 1E6) * 20;

uint8_t buf_recv[BUFFER_SIZE];
uint8_t buf_send[BUFFER_SIZE];
uint8_t buf_size = 0;
uint32_t send_timeout = 0;

esp_now_peer_info_t peerInfo; // Crée une variable pour stocker les informations du partage
esp_now_peer_info_t peerInfo2; // Crée une variable pour stocker les informations du partage


// Fonction de réception des données
void OnDataRecv(const esp_now_recv_info* info, const uint8_t* incomingData, int len) {
  memcpy(&buf_recv, incomingData, sizeof(buf_recv));
  Serial.write(buf_recv, len);
}

void setup() {
  Serial.setRxBufferSize(1024);
  Serial.setTxBufferSize(1024);
  Serial.begin(BAUD_RATE);

  WiFi.mode(WIFI_STA); // Active le wifi 
  esp_wifi_set_channel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  delay(1000);

  esp_wifi_config_espnow_rate(WIFI_IF_STA, DATARATE);

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

  memcpy(peerInfo2.peer_addr, MacAdress2, 6);
  peerInfo2.channel = ESPNOW_WIFI_CHANNEL;
  peerInfo2.encrypt = false; // Ajoute un pair

  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Failed to add peer");
    return;
  }
  
  if (esp_now_add_peer(&peerInfo2) != ESP_OK){
    Serial.println("Failed to add peer");
    return;
  }
}

mavlink_status_t status;
mavlink_message_t msg;
int chan = 0;
uint8_t buf1[MAVLINK_MAX_PACKET_LEN];
uint8_t buf2[MAVLINK_MAX_PACKET_LEN];
uint8_t sequence = 0;
char mon_message[100];
int bytes_read_count = 0;
int bytes_last_sent = 0;

int read_since_last_send = 0;

void loop() {
  while(Serial.available()) {
    uint8_t byte = Serial.read();
    read_since_last_send ++;
    //bytes_read_count ++;
    if (mavlink_parse_char(chan, byte, &msg, &status)) {
      uint16_t len = mavlink_msg_to_send_buffer(buf1, &msg);
      
      if (!(msg.msgid == MAVLINK_MSG_ID_STATUSTEXT && msg.sysid == 11 && msg.compid == 191)) {
          esp_now_send(MacAdress, (uint8_t *) &buf1, len);
      }
      read_since_last_send = 0;
    }
  }
}
