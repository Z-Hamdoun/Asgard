// Librairies pour ESP Now et le wifi
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// L'adresse Mac du récepteur
#include "../../card_info.h"  // Adjust the path as needed
#define ESPNOW_WIFI_CHANNEL GLOBAL_WIFI_CHANNEL
#define MacAdress MAC_CARTE_1  // counterpart MAC address
//#define MacAdress MAC_BROADCAST // counterpart MAC address

#define DATARATE WIFI_PHY_RATE_54M

//char to_compare[1450] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890";
char to_compare[1450] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890";

int Compteu = 0;

long Mon_message_rcv_int;
char* Mon_message_rcv_char;

esp_now_peer_info_t peerInfo;  // Crée une variable pour stocker les informations du partage
char mon_message[1470]; //= String(Compteu) + ":bonsoirr";

void OnDataSent(const wifi_tx_info_t* info, esp_now_send_status_t status) {
  //Serial.print("\r\nLast Packet Send Status:\t");
  /*if (status == ESP_NOW_SEND_SUCCESS) {
    Serial.print("Delivery : ");
    Serial.println(String(Mon_message_send.Compteur));
  }*/
  return;
}

// Fonction de réception des données


long next_int = 0;
long good_packets = 0;
long bytes_received = 0;
long start_time = 0;
char payload[1470];


void OnDataRecv(const esp_now_recv_info* info, const uint8_t* data, int len) {
  int number = parseData(data, len, payload, sizeof(payload));

  // Serial.print("Number : ");
  // Serial.println(number);

  //Serial.print("Data : ");
  //Serial.println(payload);

  //Serial.print("Payload length : ");
  //Serial.println(strlen(payload));
  bool payload_correct = true;
  for (int i = 0; to_compare[i] != '\0'; i++) {
    if (payload[i] != to_compare[i]) {
      payload_correct = false;
      break;
    }
  }

  if (payload_correct) {
    if (number == next_int || true) {
      if (number == 0) {
        start_time = millis();
      }
      good_packets++;
      bytes_received += len;
      unsigned long current_time = millis();
      if (current_time > start_time + 5000) {
        Serial.printf("Current number : %lu\n", number);

        Serial.print("Total Bytes : ");
        Serial.println(bytes_received);

        Serial.print("Total packets : ");
        Serial.println(good_packets);

        Serial.printf("Test completed. Sent %lu bytes in %lu ms (%.2f KB/s)\n", bytes_received, 5000, (bytes_received / ((5000) / 1000.0)) / 1024.0);
        Serial.printf("Test completed. Sent %lu bytes in %lu ms (%.2f Kbps)\n", bytes_received, 5000, (8*bytes_received / ((5000) / 1000.0)) / 1024.0);
        
        bytes_received = 0;
        good_packets = 0;
        start_time = current_time;
      }
    } else {
      //Serial.printf("Bad number, expected : %lu, got : %lu, adjusting", next_int, number);
      next_int = number + 1;
    }
  } else {
    Serial.println("No Success : (obj, payload)");
    Serial.println(to_compare);
    Serial.println(payload);
  }
  Compteu++;
  sprintf(mon_message, "%d:%s", Compteu, to_compare);
  esp_now_send(MacAdress, (uint8_t *)mon_message, strlen(mon_message));
  //Serial.print("Raw message : ");
  //Serial.write((char*)data);
  //Serial.println();
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);  // Active le wifi
  esp_wifi_set_channel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  delay(1000);

//  esp_wifi_config_espnow_rate(WIFI_IF_STA, DATARATE);

  Serial.print("Board MAC : ");
  Serial.println(WiFi.macAddress());

  Serial.print("Remote board : ");
  //Serial.println((char*)MacAdress);
  Serial.printf("%02X%02X%02X%02X%02X%02X\n",
                MacAdress[0], MacAdress[1], MacAdress[2],
                MacAdress[3], MacAdress[4], MacAdress[5]);

  Serial.println();
  Serial.print("IDF Version : ");
  Serial.println(ESP_IDF_VERSION);

  Serial.print("IDF5 Version : ");
  Serial.println(ESP_IDF_VERSION_VAL(5, 0, 0));
  // Initialisation de ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }


  esp_now_register_recv_cb(OnDataRecv);
  esp_now_register_send_cb(OnDataSent);  // permet d'envoyer l'accusé de réception

  memcpy(peerInfo.peer_addr, MacAdress, 6);
  peerInfo.channel = ESPNOW_WIFI_CHANNEL;
  peerInfo.encrypt = false;  // Ajoute un pair

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }  // Affiche s'il y a eu un problème lors de l'ajout du pair
}

void loop() {
  Compteu++;
  sprintf(mon_message, "%d:%s", Compteu, to_compare);
  esp_err_t result = esp_now_send(MacAdress, (uint8_t *)mon_message, strlen(mon_message)); // Envoie les données de Mon_message

  //if (result != ESP_OK) {
  //  Serial.println("Error sending the data");
  //}
  delay(1000);
}


int parseData(const uint8_t* data, size_t len, char* payloadBuffer, size_t payloadBufferSize) {
  if (!data || len == 0 || !payloadBuffer || payloadBufferSize == 0) {
    return 0;  // invalid input
  }

  // Find the colon in the buffer using a loop instead of memchr
  int colonPos = -1;
  for (int i = 0; i < len; i++) {
    if (data[i] == ':') {
      colonPos = i;
      break;
    }
  }

  if (colonPos == -1) {
    // Colon not found
    payloadBuffer[0] = '\0';
    return 0;
  }

  // Extract the number part and convert to integer
  int extractedNumber = 0;
  for (int i = 0; i < colonPos; i++) {
    if (data[i] < '0' || data[i] > '9') {
      // Invalid character in number part
      payloadBuffer[0] = '\0';
      return 0;
    }
    extractedNumber = extractedNumber * 10 + (data[i] - '0');
  }

  // Extract the payload part
  int payloadLen = len - colonPos - 1;
  if (payloadLen > 0) {
    int copyLen = (payloadLen < payloadBufferSize - 1) ? payloadLen : payloadBufferSize - 1;
    for (int i = 0; i < copyLen; i++) {
      payloadBuffer[i] = data[colonPos + 1 + i];
    }
    payloadBuffer[copyLen] = '\0';
  } else {
    payloadBuffer[0] = '\0';
  }

  return extractedNumber;
}
