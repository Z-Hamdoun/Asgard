#include <WiFi.h>

const char* ssid = "MonESPReseau";
const char* password = "MonMotDePasse";

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to Wi-Fi!");
}

void loop() {
  // Le code de communication (client TCP/UDP) vers 192.168.4.1 ira ici.
  // C'est également ici que vous ferez le pont avec la liaison série.
}