
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <Arduino.h>
#include <MAVLink.h>
//#include <mavlink/common/mavlink.h>

// L'adresse Mac du récepteur
#include "../../card_info.h" // Adjust the path as needed
#define ESPNOW_WIFI_CHANNEL GLOBAL_WIFI_CHANNEL

#define MacAdress MAC_BROADCAST

#define DATARATE WIFI_PHY_RATE_9M       // Testé à 70 mètres en intérieur
//#define DATARATE WIFI_PHY_RATE_2M_L
//#define DATARATE WIFI_PHY_RATE_LORA_500K  // Testé à 90 mètres en intérieur + obstacles

#define BAUD_RATE  460800
#define debug true


// Ensure your BUFFER_SIZE is at least this (MAVLink v2 max total: 10 + 255 + 2 + 13 = 280)
#define BUFFER_SIZE 300

//#define LED_PIN LED_BUILTIN   // or any GPIO you want


const uint32_t timeout_micros = (int)(1.0 / BAUD_RATE * 1E6) * 20;

uint8_t buf_recv[BUFFER_SIZE];
uint32_t send_timeout = 0;

// Crée une variable pour stocker les informations du partage
esp_now_peer_info_t peerInfo;
#ifdef MacAdress2
  esp_now_peer_info_t peerInfo2;
#endif

// Fonction de réception des données
void OnDataRecv(const esp_now_recv_info* info, const uint8_t* incomingData, int len) {
  memcpy(&buf_recv, incomingData, sizeof(buf_recv));
  Serial.write(buf_recv, len);
}

void setup() {
  Serial.setRxBufferSize(1024);
  Serial.setTxBufferSize(1024);
  #ifdef LED_PIN
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
  #endif  digitalWrite(LED_PIN, LOW);
  Serial.begin(BAUD_RATE);
  WiFi.mode(WIFI_STA); // Active le wifi 
  esp_wifi_set_channel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  delay(1000);
  #ifdef LED_PIN
    digitalWrite(LED_PIN, HIGH);
  #endif

  #ifdef DATARATE // par défaut le datarate est fixé à 1Mbps
    esp_wifi_config_espnow_rate(WIFI_IF_STA, DATARATE);
  #endif
  
  #ifdef debug
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

    Serial.println("ESP MASTER");
    #ifdef DATARATE
      Serial.println(DATARATE);
    #endif
  #endif
  // Initialisation de ESP-NOW
  if (esp_now_init() != ESP_OK) {
    #ifdef debug
      Serial.println("Error initializing ESP-NOW");
    #endif
    return;
  }


  esp_now_register_recv_cb(OnDataRecv);
  //esp_now_register_send_cb(OnDataSent); // permet d'envoyer l'accusé de réception

  memcpy(peerInfo.peer_addr, MacAdress, 6);
  peerInfo.channel = ESPNOW_WIFI_CHANNEL;
  peerInfo.encrypt = false; // Ajoute un pair

  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    #ifdef debug
      Serial.println("Error initializing ESP-NOW");
    #endif
    return;
  }


  #ifdef MacAdress2
    memcpy(peerInfo2.peer_addr, MacAdress2, 6);
    peerInfo2.channel = ESPNOW_WIFI_CHANNEL;
    peerInfo2.encrypt = false; // Ajoute un pair

  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    #ifdef debug
      Serial.println("Error initializing ESP-NOW");
    #endif
    return;
  }
  #endif

  #ifdef LED_PIN
    digitalWrite(LED_PIN, LOW);
  #endif
}



#define MAVLINK_BUF_SIZE 300

uint8_t mav_buf[MAVLINK_BUF_SIZE];
uint16_t mav_index = 0;
uint16_t mav_expected_len = 0;
bool mav_in_frame = false;

bool mavlink_read_frame(Stream &serial, uint8_t *out_buf, uint16_t *out_len) {
    while (serial.available()) {
        uint8_t c = serial.read();

        if (!mav_in_frame) {
            if (c == MAVLINK_STX) {  // 0xFD for MAVLink v2
                mav_in_frame = true;
                mav_index = 0;
                mav_buf[mav_index++] = c;
            }
        } else {
            mav_buf[mav_index++] = c;

            if (mav_index == 2) {
                // payload length is at byte 1
                uint8_t payload_len = mav_buf[1];
                mav_expected_len = payload_len + MAVLINK_NUM_HEADER_BYTES + MAVLINK_NUM_CHECKSUM_BYTES;
                if (mav_expected_len > sizeof(mav_buf)) {
                    // invalid, reset
                    mav_in_frame = false;
                    mav_index = 0;
                    mav_expected_len = 0;
                }
            }

            if (mav_expected_len && mav_index >= mav_expected_len) {
                memcpy(out_buf, mav_buf, mav_index);
                *out_len = mav_index;

                // reset parser state
                mav_in_frame = false;
                mav_index = 0;
                mav_expected_len = 0;

                return true;
            }

            // sanity overflow
            if (mav_index >= sizeof(mav_buf)) {
                mav_in_frame = false;
                mav_index = 0;
                mav_expected_len = 0;
            }
        }
    }
    return false; // no full frame yet
}


uint8_t frame[MAVLINK_BUF_SIZE];
uint16_t frame_len;


void loop() {
  if (mavlink_read_frame(Serial, frame, &frame_len)) {
    esp_now_send(MacAdress, (uint8_t *) &frame, frame_len);
  }
}
