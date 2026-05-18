#include "TCPBridge.h"

#ifdef WITH_TCP_BRIDGE

#include <WiFi.h>
#include <WiFiClient.h>
#include <string.h>

static WiFiClient _client;

TCPBridge::TCPBridge(NodePrefs *prefs, mesh::PacketManager *mgr, mesh::RTCClock *rtc)
    : BridgeBase(prefs, mgr, rtc) {}

bool TCPBridge::connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  if (_prefs->wifi_ssid[0] == '\0') {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: wifi.ssid not configured\n");
    return false;
  }
  BRIDGE_DEBUG_PRINTLN("TCP bridge: connecting to WiFi '%s'...\n", _prefs->wifi_ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(_prefs->wifi_ssid, _prefs->wifi_password);

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > WIFI_CONNECT_TIMEOUT_MS) {
      BRIDGE_DEBUG_PRINTLN("TCP bridge: WiFi connect timeout\n");
      return false;
    }
    delay(200);
  }
  BRIDGE_DEBUG_PRINTLN("TCP bridge: WiFi connected, IP=%s\n", WiFi.localIP().toString().c_str());
  return true;
}

bool TCPBridge::connectServer() {
  if (_prefs->bridge_server[0] == '\0') {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: bridge.server not configured\n");
    return false;
  }
  BRIDGE_DEBUG_PRINTLN("TCP bridge: connecting to %s:%d...\n", _prefs->bridge_server, _prefs->bridge_port);
  if (_client.connect(_prefs->bridge_server, _prefs->bridge_port)) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: connected to server\n");
    _last_heartbeat_ms = 0;
    return true;
  }
  BRIDGE_DEBUG_PRINTLN("TCP bridge: server connect failed\n");
  return false;
}

void TCPBridge::tryConnect() {
  if (connectWifi()) {
    connectServer();
  }
}

void TCPBridge::begin() {
  BRIDGE_DEBUG_PRINTLN("TCP bridge: starting...\n");
  tryConnect();
  _initialized = true;
}

void TCPBridge::end() {
  BRIDGE_DEBUG_PRINTLN("TCP bridge: stopping...\n");
  _client.stop();
  WiFi.disconnect(true);
  _initialized = false;
}

void TCPBridge::loop() {
  if (!_initialized) return;

  // Reconnect if needed
  if (!_client.connected()) {
    uint32_t now = millis();
    if (now - _last_reconnect_ms >= RECONNECT_INTERVAL_MS) {
      _last_reconnect_ms = now;
      _rx_buffer_pos = 0;
      tryConnect();
    }
    return;
  }

  uint32_t now = millis();
  if (_last_heartbeat_ms == 0 || now - _last_heartbeat_ms >= HEARTBEAT_INTERVAL_MS) {
    sendHeartbeat();
    _last_heartbeat_ms = now;
  }

  // Read incoming bytes and assemble packets (same state machine as RS232Bridge)
  while (_client.available()) {
    uint8_t b = (uint8_t)_client.read();

    if (_rx_buffer_pos < 2) {
      if ((_rx_buffer_pos == 0 && b == ((BRIDGE_PACKET_MAGIC >> 8) & 0xFF)) ||
          (_rx_buffer_pos == 1 && b == (BRIDGE_PACKET_MAGIC & 0xFF))) {
        _rx_buffer[_rx_buffer_pos++] = b;
      } else {
        _rx_buffer_pos = 0;
        if (b == ((BRIDGE_PACKET_MAGIC >> 8) & 0xFF)) {
          _rx_buffer[_rx_buffer_pos++] = b;
        }
      }
    } else {
      _rx_buffer[_rx_buffer_pos++] = b;

      if (_rx_buffer_pos >= 4) {
        uint16_t len = (_rx_buffer[2] << 8) | _rx_buffer[3];

        if (len > (MAX_TRANS_UNIT + 1)) {
          BRIDGE_DEBUG_PRINTLN("TCP bridge: RX invalid length %d, resetting\n", len);
          _rx_buffer_pos = 0;
          continue;
        }

        if (_rx_buffer_pos == len + TCP_OVERHEAD) {
          uint16_t received_checksum = (_rx_buffer[4 + len] << 8) | _rx_buffer[5 + len];

          if (validateChecksum(_rx_buffer + 4, len, received_checksum)) {
            if (isControlPayload(_rx_buffer + 4, len)) {
              BRIDGE_DEBUG_PRINTLN("TCP bridge: RX control len=%d crc=0x%04x\n", len, received_checksum);
              _rx_buffer_pos = 0;
              continue;
            }
            BRIDGE_DEBUG_PRINTLN("TCP bridge: RX len=%d crc=0x%04x\n", len, received_checksum);
            mesh::Packet *pkt = _mgr->allocNew();
            if (pkt) {
              if (pkt->readFrom(_rx_buffer + 4, len)) {
                onPacketReceived(pkt);
              } else {
                BRIDGE_DEBUG_PRINTLN("TCP bridge: RX failed to parse packet\n");
                _mgr->free(pkt);
              }
            } else {
              BRIDGE_DEBUG_PRINTLN("TCP bridge: RX failed to allocate packet\n");
            }
          } else {
            BRIDGE_DEBUG_PRINTLN("TCP bridge: RX checksum mismatch, rcv=0x%04x\n", received_checksum);
          }
          _rx_buffer_pos = 0;
        }
      }
    }
  }
}

bool TCPBridge::sendPayloadFrame(const uint8_t *payload, uint16_t len) {
  if (!_initialized || !_client.connected()) return false;
  if (len > (MAX_TRANS_UNIT + 1)) return false;

  uint8_t buffer[MAX_TCP_PACKET_SIZE];
  buffer[0] = (BRIDGE_PACKET_MAGIC >> 8) & 0xFF;
  buffer[1] = BRIDGE_PACKET_MAGIC & 0xFF;
  buffer[2] = (len >> 8) & 0xFF;
  buffer[3] = len & 0xFF;
  memcpy(buffer + 4, payload, len);

  uint16_t checksum = fletcher16(buffer + 4, len);
  buffer[4 + len] = (checksum >> 8) & 0xFF;
  buffer[5 + len] = checksum & 0xFF;

  return _client.write(buffer, len + TCP_OVERHEAD) == len + TCP_OVERHEAD;
}

void TCPBridge::sendHeartbeat() {
  uint8_t payload[9];
  payload[0] = 'M';
  payload[1] = 'C';
  payload[2] = 'N';
  payload[3] = 'G';
  payload[4] = CONTROL_TYPE_HEARTBEAT;
  uint32_t uptime = millis();
  payload[5] = (uptime >> 24) & 0xFF;
  payload[6] = (uptime >> 16) & 0xFF;
  payload[7] = (uptime >> 8) & 0xFF;
  payload[8] = uptime & 0xFF;

  if (sendPayloadFrame(payload, sizeof(payload))) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: heartbeat\n");
  }
}

bool TCPBridge::isControlPayload(const uint8_t *payload, uint16_t len) const {
  return len >= 5 && payload[0] == 'M' && payload[1] == 'C' && payload[2] == 'N' && payload[3] == 'G';
}

void TCPBridge::sendPacket(mesh::Packet *packet) {
  if (!_initialized || !packet) return;
  if (!_client.connected()) return;

  if (!_seen_packets.hasSeen(packet)) {
    uint8_t payload[MAX_TRANS_UNIT + 1];
    uint16_t len = packet->writeTo(payload);

    if (len > (MAX_TRANS_UNIT + 1)) {
      BRIDGE_DEBUG_PRINTLN("TCP bridge: TX packet too large (len=%d)\n", len);
      return;
    }

    if (sendPayloadFrame(payload, len)) {
      BRIDGE_DEBUG_PRINTLN("TCP bridge: TX len=%d\n", len);
    }
  }
}

void TCPBridge::onPacketReceived(mesh::Packet *packet) {
  handleReceivedPacket(packet);
}

void TCPBridge::getStatusStr(char *reply) const {
  bool wifiOk = (WiFi.status() == WL_CONNECTED);
  bool serverOk = _client.connected();

  if (!wifiOk) {
    sprintf(reply, "> WiFi: disconnected | Server: disconnected");
    return;
  }

  char ip[16];
  WiFi.localIP().toString().toCharArray(ip, sizeof(ip));
  sprintf(reply, "> WiFi: connected | IP: %s | RSSI: %d dBm | Server: %s",
          ip, WiFi.RSSI(), serverOk ? "connected" : "disconnected");
}

#endif
