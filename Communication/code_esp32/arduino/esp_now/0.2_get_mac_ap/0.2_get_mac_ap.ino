#include "WiFi.h"

// Permet de donner l'adresse mac en mode AP
// crédit : 
// https://wolles-elektronikkiste.de/en/esp-now-serial


#include <WiFi.h> 

void setup(){
    Serial.begin(115200);
    delay(1000);
    WiFi.mode(WIFI_AP); 
    while (!(WiFi.AP.started())) {
        delay(10);
    }
    Serial.print("MAC-Address: ");
    String mac = WiFi.softAPmacAddress();
    Serial.println(mac);
    
    Serial.print("Formated: ");
    Serial.print("{");
    int index = 0;
    for (int i=0; i<6; i++) {
        Serial.print("0x");
        Serial.print(mac.substring(index, index+2));
        if (i<5) {
            Serial.print(", ");
        }
        index += 3;
    }
    Serial.println("}");
   
}
 
void loop(){}
