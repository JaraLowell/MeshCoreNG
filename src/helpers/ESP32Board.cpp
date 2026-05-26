#ifdef ESP_PLATFORM

#include "ESP32Board.h"

#include <HTTPClient.h>
#include <Update.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

#if defined(ADMIN_PASSWORD)

#ifndef OTA_MANIFEST_URL
#define OTA_MANIFEST_URL "https://michtronics.github.io/MeshCoreNG/flasher/ota-manifest.txt"
#endif

struct Esp32OtaAsset {
  String version;
  String url;
  String name;
  int size;
};

static bool connectOtaWifi(const char* ssid, const char* password, char reply[]) {
  if (!ssid || ssid[0] == 0) {
    strcpy(reply, "Error: set wifi.ssid first");
    return false;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(250);
  }
  if (WiFi.status() != WL_CONNECTED) {
    strcpy(reply, "Error: WiFi connect failed");
    return false;
  }
  return true;
}

static bool parseOtaLine(const String& line, const char* target, Esp32OtaAsset* asset) {
  if (line.length() == 0 || line[0] == '#') return false;
  int p1 = line.indexOf('|');
  int p2 = line.indexOf('|', p1 + 1);
  int p3 = line.indexOf('|', p2 + 1);
  int p4 = line.indexOf('|', p3 + 1);
  if (p1 <= 0 || p2 <= p1 || p3 <= p2 || p4 <= p3) return false;
  if (line.substring(0, p1) != target) return false;

  asset->version = line.substring(p1 + 1, p2);
  asset->size = line.substring(p2 + 1, p3).toInt();
  asset->url = line.substring(p3 + 1, p4);
  asset->name = line.substring(p4 + 1);
  asset->name.trim();
  return asset->url.length() > 0 && asset->size > 0;
}

static bool fetchOtaAsset(const char* target, Esp32OtaAsset* asset, char reply[]) {
  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  http.setTimeout(15000);
  http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  if (!http.begin(client, OTA_MANIFEST_URL)) {
    strcpy(reply, "Error: manifest begin failed");
    return false;
  }

  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    snprintf(reply, 160, "Error: manifest HTTP %d", code);
    http.end();
    return false;
  }

  String body = http.getString();
  int start = 0;
  while (start < body.length()) {
    int end = body.indexOf('\n', start);
    if (end < 0) end = body.length();
    String line = body.substring(start, end);
    if (parseOtaLine(line, target, asset)) {
      http.end();
      return true;
    }
    start = end + 1;
  }

  http.end();
  snprintf(reply, 160, "Error: no OTA for %s", target);
  return false;
}

static bool downloadAndInstallOta(const Esp32OtaAsset& asset, char reply[]) {
  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  http.setTimeout(30000);
  http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  if (!http.begin(client, asset.url)) {
    strcpy(reply, "Error: firmware begin failed");
    return false;
  }

  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    snprintf(reply, 160, "Error: firmware HTTP %d", code);
    http.end();
    return false;
  }

  int size = http.getSize();
  if (size <= 0) size = asset.size;
  if (!Update.begin(size)) {
    snprintf(reply, 160, "Error: OTA begin %s", Update.errorString());
    http.end();
    return false;
  }

  size_t written = Update.writeStream(*http.getStreamPtr());
  bool ok = written == (size_t)size && Update.end(true);
  if (!ok) {
    snprintf(reply, 160, "Error: OTA write %u/%u %s", (uint32_t)written, (uint32_t)size, Update.errorString());
    http.end();
    return false;
  }

  http.end();
  snprintf(reply, 160, "OK: installed %s, reboot", asset.version.c_str());
  return true;
}

#endif

#if defined(ADMIN_PASSWORD) && !defined(DISABLE_WIFI_OTA) && \
    __has_include(<AsyncTCP.h>) && __has_include(<ESPAsyncWebServer.h>) && __has_include(<AsyncElegantOTA.h>)
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <AsyncElegantOTA.h>

#include <SPIFFS.h>

bool ESP32Board::startOTAUpdate(const char* id, char reply[]) {
  inhibit_sleep = true;   // prevent sleep during OTA
  WiFi.softAP("MeshCore-OTA", NULL);

  sprintf(reply, "Started: http://%s/update", WiFi.softAPIP().toString().c_str());
  MESH_DEBUG_PRINTLN("startOTAUpdate: %s", reply);

  static char id_buf[60];
  sprintf(id_buf, "%s (%s)", id, getManufacturerName());
  static char home_buf[90];
  sprintf(home_buf, "<H2>Hi! I am a MeshCore Repeater. ID: %s</H2>", id);

  AsyncWebServer* server = new AsyncWebServer(80);

  server->on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "text/html", home_buf);
  });
  server->on("/log", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/packet_log", "text/plain");
  });

  AsyncElegantOTA.setID(id_buf);
  AsyncElegantOTA.begin(server);    // Start ElegantOTA
  server->begin();

  return true;
}

#else
bool ESP32Board::startOTAUpdate(const char* id, char reply[]) {
  return false; // not supported
}
#endif

#if defined(ADMIN_PASSWORD)
bool ESP32Board::checkOnlineOTAUpdate(const char* target, const char* current_version, const char* wifi_ssid, const char* wifi_password, char reply[]) {
  if (!connectOtaWifi(wifi_ssid, wifi_password, reply)) return false;

  Esp32OtaAsset asset;
  if (!fetchOtaAsset(target, &asset, reply)) return false;

  bool update_available = asset.version != current_version;
  snprintf(reply, 160, "target=%s current=%s latest=%s update=%s size=%u",
           target, current_version, asset.version.c_str(), update_available ? "yes" : "no", (uint32_t)asset.size);
  return true;
}

bool ESP32Board::startOnlineOTAUpdate(const char* target, const char* current_version, const char* wifi_ssid, const char* wifi_password, char reply[]) {
  inhibit_sleep = true;
  if (!connectOtaWifi(wifi_ssid, wifi_password, reply)) return false;

  Esp32OtaAsset asset;
  if (!fetchOtaAsset(target, &asset, reply)) return false;
  if (asset.version == current_version) {
    snprintf(reply, 160, "OK: already %s", current_version);
    return true;
  }

  return downloadAndInstallOta(asset, reply);
}

#else

bool ESP32Board::checkOnlineOTAUpdate(const char* target, const char* current_version, const char* wifi_ssid, const char* wifi_password, char reply[]) {
  return false;
}

bool ESP32Board::startOnlineOTAUpdate(const char* target, const char* current_version, const char* wifi_ssid, const char* wifi_password, char reply[]) {
  return false;
}

#endif

#endif
