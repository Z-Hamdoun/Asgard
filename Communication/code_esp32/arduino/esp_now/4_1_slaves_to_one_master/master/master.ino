
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <Arduino.h>
#include <MAVLink.h>
#include <mavlink/common/mavlink.h>
#include <map>

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

// Liste d'ID MAVLink possibles pour identifier les drones
uint8_t possible_drone_id[] = {11, 12, 13, 14, 15, 21, 22, 23, 24, 25};

// Délai entre deux envois de statut RSSI (en ms)
const int timeout_send_rssi_data_ms = 1000;

// Structure décrivant l'état d'un lien radio (MAC <-> drone)
struct LinkStatus {
  uint8_t sysid;        // ID MAVLink du drone
  signed rssi;          // force du signal RSSI
  unsigned long next_send_ms;  // prochain moment où envoyer les données
  bool need_to_send;    // indicateur si besoin d'envoyer
};

// Dictionnaire simplifié : table des liens actifs
std::map<String, LinkStatus> links_status;

// Flag global pour savoir si on doit envoyer des statuts
bool need_to_send_status = false;


// Fonction de réception des données
void OnDataRecv(const esp_now_recv_info* info, const uint8_t* incomingData, int len) {
  signed rssi = info->rx_ctrl->rssi;

  // Convertir l'adresse MAC en string clé
  char macStr[18];
  snprintf(macStr, sizeof(macStr), "%02X:%02X:%02X:%02X:%02X:%02X",
           info->src_addr[0], info->src_addr[1], info->src_addr[2],
           info->src_addr[3], info->src_addr[4], info->src_addr[5]);
  String macKey = String(macStr);

  if (links_status.find(macKey) == links_status.end()) {
    mavlink_message_t msg;
    uint8_t src_sysid = 0, src_compid = 0;
    uint32_t src_msgid = 0;

    bool success = extract_info_frames(incomingData, (size_t)len, &src_sysid, &src_compid, &src_msgid);
    if (!success) {
      // not a full/valid MAVLink frame header — ignore
      return;
    }

    // populate msg minimally so subsequent logic can use sysid/msgid
    msg.sysid = src_sysid;
    msg.compid = src_compid;
    msg.msgid = src_msgid;
    

    // Vérifie si l'ID reçu fait partie des drones connus
    for (uint8_t i = 0; i < sizeof(possible_drone_id); i++) {
      if (msg.sysid == possible_drone_id[i]) {
        LinkStatus ls;
        ls.sysid = msg.sysid;
        ls.rssi = rssi;
        ls.next_send_ms = millis();
        ls.need_to_send = false;
        links_status[macKey] = ls;
        break;
      }
    }
  }
  
  // Si déjà connu et temps d'envoi dépassé
  LinkStatus &ls = links_status[macKey];
  if (millis() >= ls.next_send_ms) {
    ls.rssi = rssi;
    ls.need_to_send = true;
    ls.next_send_ms = millis() + timeout_send_rssi_data_ms;
    need_to_send_status = true;
  }

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

// from a const uint8_t* incomingData : 
// check if first byte is the starting byte
// check if length of data (second byte) is at least the length of the first paquet
// extract : sender_id (6th), comp_id (7th), msg_type (8-10th)

bool extract_info_frames(const uint8_t* incomingData, size_t len, uint8_t *out_sysid, uint8_t *out_compid, uint32_t *out_msgid) {
  if (!incomingData || len == 0) return false;
  if (!out_sysid || !out_compid || !out_msgid) return false;

  // Check start byte
  if (incomingData[0] != MAVLINK_STX) return false;

  // Need at least header bytes to read payload length and indexes up to msgid
  if (len < MAVLINK_NUM_HEADER_BYTES) return false;

  uint8_t payload_len = incomingData[1];

  // Compute expected full frame length (without optional signature)
  size_t expected_len = (size_t)payload_len + MAVLINK_NUM_HEADER_BYTES + MAVLINK_NUM_CHECKSUM_BYTES;

  // If incompat flags indicate signature present (bit 0), include signature bytes
  if ((incomingData[2] & 0x01) && (sizeof(incomingData) > 2)) {
    expected_len += 13;
  }

  if (len < expected_len) return false; // not a full packet yet

  // Extract sysid (6th byte -> index 5), compid (7th byte -> index 6)
  *out_sysid = incomingData[5];
  *out_compid = incomingData[6];

  // Extract 3-byte msgid (little-endian) at indices 7,8,9
  uint32_t msgid = 0;
  msgid  = (uint32_t)incomingData[7];
  msgid |= (uint32_t)incomingData[8] << 8;
  msgid |= (uint32_t)incomingData[9] << 16;
  *out_msgid = msgid;

  return true;
}

bool mavlink_read_frame(Stream &serial, uint8_t *out_buf, uint16_t *out_len) {
    while (serial.available()) {
      uint8_t c = serial.read();

      if (!mav_in_frame) {
        if (c == MAVLINK_STX) {  // 0xFD for MAVLink v2
          mav_in_frame = true;
          mav_index = 0;
          mav_buf[mav_index++] = c;
        }
      } 
      else {
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

// List of MAC, SysID, time_sent

void send_radio_status_to_serial(LinkStatus &link_status) {
  uint8_t compid = MAV_COMP_ID_TELEMETRY_RADIO;  // 190

  mavlink_message_t msg;
  mavlink_msg_radio_status_pack(
      link_status.sysid, 
      compid,
      &msg,

      link_status.rssi,  // rssi
      0,                 // remrssi
      0,                 // txbuf
      0,                 // noise
      0,                 // remnoise
      0,                 // rxerrors
      0                  // fixed
  );


/**
 * @brief Pack a radio_status message
 * @param system_id ID of this system
 * @param component_id ID of this component (e.g. 200 for IMU)
 * @param msg The MAVLink message to compress the data into
 *
 * @param rssi  Local (message sender) received signal strength indication in device-dependent units/scale. Values: [0-254], UINT8_MAX: invalid/unknown.
 * @param remrssi  Remote (message receiver) signal strength indication in device-dependent units/scale. Values: [0-254], UINT8_MAX: invalid/unknown.
 * @param txbuf [%] Remaining free transmitter buffer space.
 * @param noise  Local background noise level. These are device dependent RSSI values (scale as approx 2x dB on SiK radios). Values: [0-254], UINT8_MAX: invalid/unknown.
 * @param remnoise  Remote background noise level. These are device dependent RSSI values (scale as approx 2x dB on SiK radios). Values: [0-254], UINT8_MAX: invalid/unknown.
 * @param rxerrors  Count of radio packet receive errors (since boot).
 * @param fixed  Count of error corrected radio packets (since boot).
 * @return length of the message in bytes (excluding serial stream start sign)
 */

  uint8_t buf[MAVLINK_MAX_PACKET_LEN];
  uint16_t len = mavlink_msg_to_send_buffer(buf, &msg);
  Serial.write(buf, len);
}

uint8_t frame[MAVLINK_BUF_SIZE];
uint16_t frame_len;


void loop() {
  if (mavlink_read_frame(Serial, frame, &frame_len)) {
    esp_now_send(MacAdress, (uint8_t *) &frame, frame_len);
  }
  if (need_to_send_status) {
    for (auto &pair : links_status) {
      LinkStatus &link_status = pair.second;
      if (link_status.need_to_send) {
        send_radio_status_to_serial(link_status);
        link_status.need_to_send = false;
      }
    }
    need_to_send_status = false;
  }
}
