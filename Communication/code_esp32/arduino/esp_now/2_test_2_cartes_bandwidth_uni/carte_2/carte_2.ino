#include "ESP32_NOW_Serial.h"
#include "MacAddress.h"
#include "WiFi.h"
#include "esp_wifi.h"
#include "../../card_info.h" // Adjust the path as needed

#define ESPNOW_WIFI_CHANNEL GLOBAL_WIFI_CHANNEL

//const MacAddress peer_mac({0x94, 0x3C, 0xC6, 0x34, 0xCF, 0xA4}); // counterpart MAC address
const MacAddress peer_mac(MAC_CARTE_1); // counterpart MAC address

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

    // Start the ESP-NOW communication
    Serial.println("ESP-NOW communication starting...");
    NowSerial.begin(115200);
    Serial.printf("ESP-NOW version: %d, max data length: %d\n", ESP_NOW.getVersion(), ESP_NOW.getMaxDataLen());
    Serial.println("You can now send data to the peer device using the Serial Monitor.\n");
}

// L'objectif de ce code est de mesurer la bande passante en émission uniquement
// Ce même code sera compilé sur les deux cartes
// Lorsque l'utilisateur entre "test" dans le moniteur série, la carte envoie un flux continu de données à la carte réceptrice pendant 5 secondes
// La carte réceptrice ne répond pas, elle se contente de recevoir les données en vérifiant que les paquets sont dans le bon ordre et sans manques
// Elle affiche le nombre d'octets reçus et le laps de temps écoulé


String incomingData = "";
int expectedLength = -1;  // -1 means "waiting for length byte"
unsigned long messagesSent = 0;
unsigned long messagesLostSEND = 0;


void loop() {
    while (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        if (command == "test") {
            Serial.println("Starting bandwidth test for 5 seconds...");
            unsigned long startTime = millis();
            unsigned long bytesSent = 0;
            unsigned long messageIncrement = 0;
            while (millis() - startTime < 5000) {
                String testData = String(messageIncrement) + ":ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
                // limit to testData 250 characters to avoid fragmentation
                testData = testData.substring(0, 249);
                size_t dataLength = testData.length();
                if (sendPacket((const uint8_t*)testData.c_str(), dataLength) > 0) {
                    bytesSent += dataLength;
                    messagesSent++;
                }
                else {
                    Serial.println("Failed to send data");
                    messagesLostSEND++;
                }
                messageIncrement++;
                delay(1); // Small delay to avoid overwhelming the receiver
            }
            unsigned long elapsedTime = millis() - startTime;
            sendPacket((const uint8_t *)"End Test", 8); // Notify the receiver that the test has ended

            Serial.printf("Test completed. Sent %lu bytes in %lu ms (%.2f KB/s)\n", bytesSent, elapsedTime, (bytesSent / (elapsedTime / 1000.0)) / 1024.0);
            Serial.printf("Messages sent: %lu, Messages lost: %lu, Loss ratio: %.2f%%\n", messagesSent, messagesLostSEND, (messagesLostSEND / (float)(messagesSent + messagesLostSEND)) * 100.0);
            messagesSent = 0;
            messagesLostSEND = 0;
        } else {
            Serial.println("Unknown command. Type 'test' to start the bandwidth test.");
        }
    }

    // Check if ":" is in the incoming data to identify it it is a test data
    String incomingData = "";
    while (NowSerial.available()) {
        char c = NowSerial.read();
        incomingData += c;
        if (c == '\n') {
            break;
        }
    }

    while (NowSerial.available()) {
    if (expectedLength < 0) {
      // We don't yet know how many bytes to expect → read length prefix
      expectedLength = NowSerial.read();
      incomingData = "";  // clear buffer
    } else {
      // We know how many bytes to expect → read them
      while (NowSerial.available() && incomingData.length() < expectedLength) {
        char c = NowSerial.read();
        incomingData += c;
      }

      // If we got the full payload
      if (incomingData.length() == expectedLength) {
        handleMessage(incomingData);  // <-- your own function
        expectedLength = -1;          // reset, wait for next packet
      }
    }
  }
    delay(1);
}


uint8_t sendPacket(const uint8_t *data, uint8_t len) {
    // len must be <= 250 for ESP-NOW
    uint8_t writtenLen = NowSerial.write(len);       // send length prefix
    uint8_t writtenPayload = NowSerial.write(data, len); // send payload
    return (writtenLen < writtenPayload) ? writtenLen : writtenPayload;
}


unsigned long expectedMessageIncrement = 0;
unsigned long messagesReceived = 0;
unsigned long messagesLostRCV = 0;
unsigned long firstMessageTime = 0;
unsigned long lastMessageTime = 0;
unsigned long totalBytesReceived = 0;

void handleMessage(const String &message) {
    // incomingData.trim();
    int colonIndex = message.indexOf(':');
    if (colonIndex != -1) {
        String numberPart = incomingData.substring(0, colonIndex);
        unsigned long receivedIncrement = numberPart.toInt();
        if (receivedIncrement == expectedMessageIncrement) {
            expectedMessageIncrement++;
            messagesReceived++;
        } else {
            Serial.printf("Data loss or out of order detected. Expected: %lu, Received: %lu\n", expectedMessageIncrement, receivedIncrement);
            expectedMessageIncrement = receivedIncrement + 1; // Resynchronize
            messagesLostRCV += (receivedIncrement - expectedMessageIncrement + 1);
        }
        if (receivedIncrement == 0) {
            firstMessageTime = millis();
            totalBytesReceived = 0;
        }
        lastMessageTime = millis();
        totalBytesReceived += message.length();
    }
    else if (message == "End Test") {
        Serial.println("Test ended by sender.");
        unsigned long testDuration = lastMessageTime - firstMessageTime;
        Serial.printf("Received %lu bytes in %lu ms (%.2f KB/s)\n", totalBytesReceived, testDuration, (totalBytesReceived / (testDuration / 1000.0)) / 1024.0);
        // Out of curiosity print the amount of messages received, lost and the ratio
        Serial.printf("Messages received: %lu, Messages lost: %lu, Loss ratio: %.2f%%\n", messagesReceived, messagesLostRCV, (messagesLostRCV / (float)(messagesReceived + messagesLostRCV)) * 100.0);
        messagesReceived = 0;
        messagesLostRCV = 0;
        totalBytesReceived = 0;
        firstMessageTime = 0;
        lastMessageTime = 0;
        expectedMessageIncrement = 0;
    }
}