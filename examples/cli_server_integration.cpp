/**
 * Example: CLI Server Integration
 * 
 * This example shows how to integrate the CLI Server into your firmware
 * for remote management over WiFi/TCP.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <helpers/esp32/CLIServer.h>
#include <helpers/CommonCLI.h>

// Your existing mesh/node setup
extern CommonCLI cli;
extern NodePrefs prefs;

// CLI Server instance
CLIServer* cliServer = nullptr;

void setup() {
  Serial.begin(115200);
  
  // ... your existing setup code ...
  
  // Initialize CLI server if WiFi is configured and enabled
  if (prefs.cli_server_enabled && prefs.wifi_ssid[0] != '\0') {
    Serial.println("Starting CLI server...");
    cliServer = new CLIServer(&prefs, &cli);
    
    // Wait for WiFi connection (handled elsewhere in your code)
    // When WiFi connects, start the CLI server
  }
}

void loop() {
  // ... your existing loop code ...
  
  // Process CLI server if running
  if (cliServer && WiFi.status() == WL_CONNECTED) {
    // Start server if not running
    if (!cliServer->isRunning()) {
      if (cliServer->begin()) {
        Serial.print("CLI Server started on port ");
        Serial.println(prefs.cli_server_port);
        Serial.print("Connect with: telnet ");
        Serial.print(WiFi.localIP());
        Serial.print(" ");
        Serial.println(prefs.cli_server_port);
      }
    }
    
    // Process server loop
    cliServer->loop();
  }
}

/**
 * Configuration via Serial CLI:
 * 
 * 1. Connect via serial/USB
 * 2. Configure WiFi and CLI server:
 *    > set wifi.ssid YourWiFiNetwork
 *    > set wifi.password YourPassword
 *    > set cli.server.enabled on
 *    > set cli.server.port 2323
 *    > set cli.server.password secret123
 * 3. Reboot the device
 * 4. Connect remotely:
 *    $ telnet 192.168.1.100 2323
 *    Password: secret123
 *    > ver
 *    > stats-core
 */
