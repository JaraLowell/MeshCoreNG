#include "TCPBridge.h"

#ifdef WITH_TCP_BRIDGE

#include <WiFi.h>
#include <WiFiClient.h>
#include <string.h>

#ifndef FIRMWARE_VERSION
#define FIRMWARE_VERSION "unknown"
#endif

static WiFiClient _client;

TCPBridge::TCPBridge(NodePrefs *prefs, mesh::PacketManager *mgr, mesh::RTCClock *rtc)
    : BridgeBase(prefs, mgr, rtc) {}

void TCPBridge::begin() {
  BRIDGE_DEBUG_PRINTLN("TCP bridge: starting...\n");
  _state = State::IDLE;
  _rx_buffer_pos = 0;
  _reconnect_interval_ms = RECONNECT_INTERVAL_MS;
  _last_reconnect_ms = millis() - RECONNECT_INTERVAL_MS;  // connect on first loop()
  _last_heartbeat_ms = 0;
  _initialized = true;
}

void TCPBridge::end() {
  BRIDGE_DEBUG_PRINTLN("TCP bridge: stopping...\n");
  _client.stop();
  WiFi.disconnect(true);
  _state = State::IDLE;
  _initialized = false;
}

void TCPBridge::loop() {
  if (!_initialized) return;

  uint32_t now = millis();

  switch (_state) {

    case State::IDLE:
      if (now - _last_reconnect_ms < _reconnect_interval_ms) return;
      _last_reconnect_ms = now;
      _reconnect_interval_ms = RECONNECT_INTERVAL_MS;
      _rx_buffer_pos = 0;

      if (_prefs->wifi_ssid[0] == '\0') return;

      if (WiFi.status() == WL_CONNECTED) {
        _state = State::SERVER_WAIT;
      } else {
        WiFi.persistent(false);
        WiFi.mode(WIFI_STA);
#if defined(WITH_BLE_BRIDGE)
        WiFi.setSleep(true);
#else
        WiFi.setSleep(false);
#endif
        WiFi.begin(_prefs->wifi_ssid, _prefs->wifi_password);
        _wifi_start_ms = now;
        _state = State::WIFI_WAIT;
        BRIDGE_DEBUG_PRINTLN("TCP bridge: connecting to WiFi '%s'...\n", _prefs->wifi_ssid);
      }
      break;

    case State::WIFI_WAIT:
      if (WiFi.status() == WL_CONNECTED) {
        BRIDGE_DEBUG_PRINTLN("TCP bridge: WiFi connected, IP=%s\n",
                             WiFi.localIP().toString().c_str());
        _state = State::SERVER_WAIT;
      } else if (now - _wifi_start_ms >= WIFI_CONNECT_TIMEOUT_MS) {
        BRIDGE_DEBUG_PRINTLN("TCP bridge: WiFi connect timeout\n");
        WiFi.disconnect(false);
        _state = State::IDLE;
        _last_reconnect_ms = now;
        _reconnect_interval_ms = RECONNECT_INTERVAL_MS;
      }
      break;

    case State::SERVER_WAIT:
      if (_prefs->bridge_server[0] == '\0') {
        _state = State::IDLE;
        return;
      }
      BRIDGE_DEBUG_PRINTLN("TCP bridge: connecting to %s:%d...\n",
                           _prefs->bridge_server, _prefs->bridge_port);
      if (_client.connect(_prefs->bridge_server, _prefs->bridge_port,
                          SERVER_CONNECT_TIMEOUT_MS)) {
        BRIDGE_DEBUG_PRINTLN("TCP bridge: connected to server\n");
        _last_heartbeat_ms = 0;
        _state = State::RUNNING;
        sendAuth();
        sendNodeInfo();
      } else {
        BRIDGE_DEBUG_PRINTLN("TCP bridge: server connect failed\n");
        _state = State::IDLE;
        _last_reconnect_ms = now;
        _reconnect_interval_ms = SERVER_RECONNECT_INTERVAL_MS;
      }
      break;

    case State::RUNNING:
      if (!_client.connected()) {
        BRIDGE_DEBUG_PRINTLN("TCP bridge: connection lost\n");
        _client.stop();
        _state = State::IDLE;
        _last_reconnect_ms = now - RECONNECT_INTERVAL_MS;  // retry soon
        return;
      }

      if (_last_heartbeat_ms == 0 || now - _last_heartbeat_ms >= HEARTBEAT_INTERVAL_MS) {
        sendHeartbeat();
        _last_heartbeat_ms = now;
      }

      readIncoming();
      break;
  }
}

void TCPBridge::readIncoming() {
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
          uint16_t received_checksum =
              (_rx_buffer[4 + len] << 8) | _rx_buffer[5 + len];

          if (validateChecksum(_rx_buffer + 4, len, received_checksum)) {
            if (isControlPayload(_rx_buffer + 4, len)) {
              BRIDGE_DEBUG_PRINTLN("TCP bridge: RX control len=%d crc=0x%04x\n",
                                   len, received_checksum);
              _rx_buffer_pos = 0;
              continue;
            }
            BRIDGE_DEBUG_PRINTLN("TCP bridge: RX len=%d crc=0x%04x\n", len,
                                 received_checksum);
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
            BRIDGE_DEBUG_PRINTLN("TCP bridge: RX checksum mismatch, rcv=0x%04x\n",
                                 received_checksum);
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

void TCPBridge::sendAuth() {
  if (_prefs->bridge_password[0] == '\0') return;

  uint8_t payload[6 + sizeof(_prefs->bridge_password)];
  payload[0] = 'M';
  payload[1] = 'C';
  payload[2] = 'N';
  payload[3] = 'G';
  payload[4] = CONTROL_TYPE_AUTH;

  size_t password_len = 0;
  while (password_len < sizeof(_prefs->bridge_password) &&
         _prefs->bridge_password[password_len] != '\0') {
    password_len++;
  }
  payload[5] = (uint8_t)password_len;
  memcpy(payload + 6, _prefs->bridge_password, password_len);

  if (sendPayloadFrame(payload, 6 + password_len)) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: sent auth\n");
  }
}

void TCPBridge::sendNodeInfo() {
  uint8_t payload[7 + sizeof(_prefs->node_name) + 32];
  payload[0] = 'M';
  payload[1] = 'C';
  payload[2] = 'N';
  payload[3] = 'G';
  payload[4] = CONTROL_TYPE_NODE_INFO;

  size_t name_len = 0;
  while (name_len < sizeof(_prefs->node_name) && _prefs->node_name[name_len] != '\0') {
    name_len++;
  }
  payload[5] = (uint8_t)name_len;
  memcpy(payload + 6, _prefs->node_name, name_len);

  const char *version = FIRMWARE_VERSION;
  size_t version_len = 0;
  while (version_len < 32 && version[version_len] != '\0') {
    version_len++;
  }
  payload[6 + name_len] = (uint8_t)version_len;
  memcpy(payload + 7 + name_len, version, version_len);

  if (sendPayloadFrame(payload, 7 + name_len + version_len)) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: sent node name '%s' version '%s'\n",
                         _prefs->node_name, version);
  }
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
  return len >= 5 && payload[0] == 'M' && payload[1] == 'C' &&
         payload[2] == 'N' && payload[3] == 'G';
}

void TCPBridge::sendPacket(mesh::Packet *packet) {
  if (!_initialized || !packet) return;
  if (_state != State::RUNNING) return;

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
  bool serverOk = (_state == State::RUNNING);

  if (!wifiOk) {
    const char *stateStr = (_state == State::WIFI_WAIT) ? "connecting..." : "disconnected";
    sprintf(reply, "> WiFi: %s | Server: disconnected", stateStr);
    return;
  }

  char ip[16];
  WiFi.localIP().toString().toCharArray(ip, sizeof(ip));
  const char *serverStr = serverOk ? "connected"
                        : (_state == State::SERVER_WAIT) ? "connecting..."
                        : "disconnected";
  sprintf(reply, "> WiFi: connected | IP: %s | RSSI: %d dBm | Server: %s",
          ip, WiFi.RSSI(), serverStr);
}

#endif
