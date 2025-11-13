#include <WiFi.h>

const char* ssid = "MonESPReseau";
const char* password = "MonMotDePasse";

void setup() {
  Serial.begin(115200);
  WiFi.softAP(ssid, password);
  Serial.print("AP IP address: ");
  Serial.println(WiFi.softAPIP()); // Affichera 192.168.4.1
}

void loop() {
  // Le code de communication, par exemple un serveur TCP/UDP, ira ici.
}