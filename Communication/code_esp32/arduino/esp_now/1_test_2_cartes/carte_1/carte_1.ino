#include "ESP32_NOW_Serial.h"
#include "MacAddress.h"
#include "WiFi.h"
#include "esp_wifi.h"
#include "../../card_info.h" // Adjust the path as needed

#define ESPNOW_WIFI_CHANNEL GLOBAL_WIFI_CHANNEL

//const MacAddress peer_mac({0x94, 0x3C, 0xC6, 0x34, 0xCF, 0xA4}); // counterpart MAC address
const MacAddress peer_mac(MAC_CARTE_2); // counterpart MAC address

ESP_NOW_Serial_Class NowSerial(peer_mac, ESPNOW_WIFI_CHANNEL, WIFI_IF_STA);

void setup() {
    Serial.begin(115200);

    Serial.print("Channel: ");
    Serial.println(ESPNOW_WIFI_CHANNEL);
    WiFi.mode(WIFI_STA);
    WiFi.setChannel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);

    while (!(WiFi.STA.started())) {
        delay(100);
    }

    Serial.print("MAC Address: ");
    Serial.println(WiFi.macAddress());

    Serial.print("Peer Address: ");
    Serial.println(peer_mac);

    // Start the ESP-NOW communication
    Serial.println("ESP-NOW communication starting...");
    NowSerial.begin(115200);
    Serial.printf("ESP-NOW version: %d, max data length: %d\n", ESP_NOW.getVersion(), ESP_NOW.getMaxDataLen());
    Serial.println("You can now send data to the peer device using the Serial Monitor.\n");
}

void loop() {
    while (NowSerial.available()) {
        Serial.write(NowSerial.read());
    }
    while (Serial.available() && NowSerial.availableForWrite()) {
        if (NowSerial.write(Serial.read()) <= 0) {
            Serial.println("Failed to send data");
            break;
        }
    }
    delay(1);
}