// Attend un HEARTBEAT du drone et note son sysid
// Envoie des VISION_POSITION_ESTIMATE à 10 Hz
// Set HOME et l'origine EKF toutes les 5 sec
// Ecoute en arrière plan les roll, pitch et yaw (pour VISION_POSITION_ESTIMATE)



#include <Arduino.h>
#include <mavlink/ardupilotmega/mavlink.h>

#define BAUD_RATE 115200
#define LAT_ORIGINE  -31.9508512
#define LON_ORIGINE  115.863278
#define ALT_ORIGINE  10

volatile float roll = 0.0, pitch = 0.0, yaw = 0.0;
uint64_t boot_time_us;
uint8_t fc_sysid = 0;
bool heartbeat_received = false;

mavlink_message_t msg;
mavlink_status_t status;

void taskReceiveMAVLink(void *pvParameters);
void sendVisionPosition();

void setup() {
  Serial.begin(BAUD_RATE);
  boot_time_us = micros();

  xTaskCreatePinnedToCore(
    taskReceiveMAVLink,
    "MAVLink Receive",
    4096,
    NULL,
    2,
    NULL,
    1
  );

  Serial.println("Waiting for HEARTBEAT from flight controller...");
  while (!heartbeat_received) delay(100);
  Serial.print("HEARTBEAT received. FC sysid = ");
  Serial.println(fc_sysid);
}

void loop() {
  sendVisionPosition();

  static unsigned long last_cmd_time = 0;
  if (millis() - last_cmd_time > 5000) {
    last_cmd_time = millis();

    // ==== COMMAND_INT ====
    mavlink_message_t cmd_msg;
    mavlink_msg_command_int_pack(
      1, 200, &cmd_msg,
      fc_sysid, 1,
      0,
      179,
      0, 0,
      0, 0, 0, 0,
      (int32_t)(LAT_ORIGINE * 1e7),
      (int32_t)(LON_ORIGINE * 1e7),
      ALT_ORIGINE
    );
    uint8_t buf1[MAVLINK_MAX_PACKET_LEN];
    uint16_t len1 = mavlink_msg_to_send_buffer(buf1, &cmd_msg);
    Serial.write(buf1, len1);

    // ==== SET_GPS_GLOBAL_ORIGIN ====
    mavlink_message_t origin_msg;
    uint64_t usec = micros() - boot_time_us;
    mavlink_msg_set_gps_global_origin_pack(
      1, 200, &origin_msg,
      fc_sysid,
      (int32_t)(LAT_ORIGINE * 1e7),
      (int32_t)(LON_ORIGINE * 1e7),
      (int32_t)(ALT_ORIGINE * 1000),
      usec
    );
    uint8_t buf2[MAVLINK_MAX_PACKET_LEN];
    uint16_t len2 = mavlink_msg_to_send_buffer(buf2, &origin_msg);
    Serial.write(buf2, len2);

    Serial.println("Sent COMMAND_INT + SET_GPS_GLOBAL_ORIGIN");
  }
}

void sendVisionPosition() {
  static unsigned long last_send = 0;
  if (millis() - last_send >= 100) {  // 10 Hz
    last_send = millis();

    float covariance[21];
    for (int i = 0; i < 21; i++) covariance[i] = NAN;
    uint64_t usec = micros() - boot_time_us;

    mavlink_message_t vision_msg;
    mavlink_msg_vision_position_estimate_pack(
      1, 197, &vision_msg,
      usec,
      1.0, 2.0, 3.0,
      roll, pitch, yaw,
      covariance,
      0
    );
    uint8_t buffer[MAVLINK_MAX_PACKET_LEN];
    uint16_t len = mavlink_msg_to_send_buffer(buffer, &vision_msg);
    Serial.write(buffer, len);
  }
}

void taskReceiveMAVLink(void *pvParameters) {
  for (;;) {
    while (Serial.available() > 0) {
      uint8_t byte = Serial.read();
      if (mavlink_parse_char(MAVLINK_COMM_0, byte, &msg, &status)) {

        if (msg.msgid == MAVLINK_MSG_ID_HEARTBEAT) {
          if (!heartbeat_received && msg.compid == 1) {
            fc_sysid = msg.sysid;
            heartbeat_received = true;
          }
        }

        if (msg.msgid == MAVLINK_MSG_ID_ATTITUDE) {
          mavlink_attitude_t attitude;
          mavlink_msg_attitude_decode(&msg, &attitude);
          roll = attitude.roll;
          pitch = attitude.pitch;
          yaw = attitude.yaw;
        }
      }
    }
    vTaskDelay(1);
  }
}
