#include "TCPBridge.h"

#ifdef WITH_TCP_BRIDGE

#include <WiFi.h>
#include <WiFiClient.h>
#include <string.h>
#include <time.h>

#ifndef FIRMWARE_VERSION
#define FIRMWARE_VERSION "unknown"
#endif

static WiFiClient _client;

namespace {

uint32_t fnv1a32(const uint8_t *data, size_t len) {
  uint32_t hash = 2166136261UL;
  for (size_t i = 0; i < len; i++) {
    hash ^= data[i];
    hash *= 16777619UL;
  }
  return hash;
}

}  // namespace

TCPBridge::TCPBridge(NodePrefs *prefs, mesh::PacketManager *mgr, mesh::RTCClock *rtc)
    : BridgeBase(prefs, mgr, rtc), 
      _transport_flood_limiter(20, 120),   // default: 20 transport packets per 2 min
      _control_flood_limiter(20, 120) {}   // default: 20 control packets per 2 min

void TCPBridge::begin() {
  BRIDGE_DEBUG_PRINTLN("TCP bridge: starting...\n");
  _state = State::IDLE;
  _rx_buffer_pos = 0;
  _reconnect_interval_ms = RECONNECT_INTERVAL_MS;
  _last_reconnect_ms = millis() - RECONNECT_INTERVAL_MS;  // connect on first loop()
  _last_heartbeat_ms = 0;
  _transport_dropped_count = 0;
  _control_dropped_count = 0;
  _ntp_synced = false;
  _last_ntp_sync_ms = 0;
  
  // Configure selective rate limiters from preferences
  if (_prefs->tcp_flood_limit_enable) {
    _transport_flood_limiter.setLimits(_prefs->tcp_flood_transport_max, _prefs->tcp_flood_transport_window);
    _control_flood_limiter.setLimits(_prefs->tcp_flood_control_max, _prefs->tcp_flood_control_window);
  }
  
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
        syncTimeWithNTP(false);
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
        syncTimeWithNTP(false);
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
        sendCaps();
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
      refreshNTP(now);
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

        if (len > MAX_TCP_PAYLOAD_SIZE) {
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
              handleControlPayload(_rx_buffer + 4, len);
              _rx_buffer_pos = 0;
              continue;
            }
            
            // Selective flood protection by packet category
            if (_prefs->tcp_flood_limit_enable) {
              uint32_t now_secs = _rtc->getCurrentTime();
              bool drop_packet = false;
              
              if (isTransportPacket(_rx_buffer + 4, len)) {
                // Transport/message packets: strict rate limit
                if (!_transport_flood_limiter.allow(now_secs)) {
                  _transport_dropped_count++;
                  drop_packet = true;
                  BRIDGE_DEBUG_PRINTLN("TCP bridge: transport flood limit exceeded, dropping (dropped=%lu)\n",
                                       (unsigned long)_transport_dropped_count);
                }
              } else if (isControlPacket(_rx_buffer + 4, len)) {
                // Control/admin packets: higher limit or bypass
                if (_prefs->tcp_flood_control_max > 0) {  // 0 = bypass
                  if (!_control_flood_limiter.allow(now_secs)) {
                    _control_dropped_count++;
                    drop_packet = true;
                    BRIDGE_DEBUG_PRINTLN("TCP bridge: control flood limit exceeded, dropping (dropped=%lu)\n",
                                         (unsigned long)_control_dropped_count);
                  }
                }
                // else: control max = 0, bypass flood protection
              }
              // Other packet types not explicitly classified default to no limit
              
              if (drop_packet) {
                _rx_buffer_pos = 0;
                continue;
              }
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
  if (len > MAX_TCP_PAYLOAD_SIZE) return false;

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

void TCPBridge::sendCaps() {
  uint8_t payload[7];
  payload[0] = 'M';
  payload[1] = 'C';
  payload[2] = 'N';
  payload[3] = 'G';
  payload[4] = CONTROL_TYPE_CAPS;
  payload[5] = 1;    // caps version
  payload[6] = 0x01; // bridge packet v2 envelope

  if (sendPayloadFrame(payload, sizeof(payload))) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: sent caps bridge-v2\n");
  }
}

void TCPBridge::handleControlPayload(const uint8_t *payload, uint16_t len) {
  if (len < 5) return;

  if (payload[4] == CONTROL_TYPE_BRIDGE_PACKET) {
    handleBridgePacketPayload(payload, len);
  } else if (payload[4] == CONTROL_TYPE_COMMAND) {
    handleCommandPayload(payload, len);
  }
}

void TCPBridge::handleBridgePacketPayload(const uint8_t *payload, uint16_t len) {
  if (len < BRIDGE_V2_OVERHEAD) return;
  if (payload[5] != BRIDGE_PACKET_VERSION) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: RX bridge packet version %d unsupported\n", payload[5]);
    return;
  }

  uint8_t ttl = payload[6];
  uint32_t origin_id = ((uint32_t)payload[7] << 24) |
                       ((uint32_t)payload[8] << 16) |
                       ((uint32_t)payload[9] << 8) |
                       payload[10];
  uint8_t flags = payload[11];
  uint16_t packet_len = ((uint16_t)payload[12] << 8) | payload[13];

  if (ttl == 0) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: RX bridge packet TTL expired\n");
    return;
  }
  if (origin_id != 0 && origin_id == getBridgeId()) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: RX bridge packet from self origin=0x%08lx\n", (unsigned long)origin_id);
    return;
  }
  if (packet_len == 0 || len < (uint16_t)(BRIDGE_V2_OVERHEAD + packet_len)) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: RX bridge packet invalid mesh length %d\n", packet_len);
    return;
  }

  mesh::Packet *pkt = _mgr->allocNew();
  if (!pkt) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: RX bridge packet failed to allocate packet\n");
    return;
  }
  if (pkt->readFrom(payload + BRIDGE_V2_OVERHEAD, packet_len)) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: RX bridge packet ttl=%d origin=0x%08lx flags=0x%02x len=%d\n",
                         ttl, (unsigned long)origin_id, flags, packet_len);
    onPacketReceived(pkt);
  } else {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: RX bridge packet failed to parse mesh packet\n");
    _mgr->free(pkt);
  }
}

void TCPBridge::handleCommandPayload(const uint8_t *payload, uint16_t len) {
  if (!_command_handler || len < 11) return;

  uint32_t request_id = ((uint32_t)payload[5] << 24) |
                        ((uint32_t)payload[6] << 16) |
                        ((uint32_t)payload[7] << 8) |
                        payload[8];
  uint8_t password_len = payload[9];
  uint8_t command_len = payload[10];
  if (command_len == 0 || len < (uint16_t)(11 + password_len + command_len)) {
    sendCommandReply(request_id, "Err - invalid remote command");
    return;
  }

  char password[32];
  size_t password_copy_len = password_len;
  if (password_copy_len >= sizeof(password)) password_copy_len = sizeof(password) - 1;
  memcpy(password, payload + 11, password_copy_len);
  password[password_copy_len] = 0;

  char command[96];
  size_t copy_len = command_len;
  if (copy_len >= sizeof(command)) copy_len = sizeof(command) - 1;
  memcpy(command, payload + 11 + password_len, copy_len);
  command[copy_len] = 0;

  char reply[192];
  reply[0] = 0;
  _command_handler->handleTcpBridgeCommand(password, command, reply, sizeof(reply));
  if (reply[0] == 0) {
    strncpy(reply, "OK", sizeof(reply));
    reply[sizeof(reply) - 1] = 0;
  }
  sendCommandReply(request_id, reply);
}

void TCPBridge::sendCommandReply(uint32_t request_id, const char *reply) {
  uint8_t payload[MAX_TRANS_UNIT + 1];
  payload[0] = 'M';
  payload[1] = 'C';
  payload[2] = 'N';
  payload[3] = 'G';
  payload[4] = CONTROL_TYPE_COMMAND_REPLY;
  payload[5] = (request_id >> 24) & 0xFF;
  payload[6] = (request_id >> 16) & 0xFF;
  payload[7] = (request_id >> 8) & 0xFF;
  payload[8] = request_id & 0xFF;

  size_t reply_len = strlen(reply);
  if (reply_len > (MAX_TRANS_UNIT + 1) - 10) {
    reply_len = (MAX_TRANS_UNIT + 1) - 10;
  }
  payload[9] = (uint8_t)reply_len;
  memcpy(payload + 10, reply, reply_len);
  sendPayloadFrame(payload, 10 + reply_len);
}

bool TCPBridge::isControlPayload(const uint8_t *payload, uint16_t len) const {
  return len >= 5 && payload[0] == 'M' && payload[1] == 'C' &&
         payload[2] == 'N' && payload[3] == 'G';
}

bool TCPBridge::isTransportPacket(const uint8_t *payload, uint16_t len) const {
  if (len < 1) return false;
  
  uint8_t header = payload[0];
  uint8_t route_type = header & PH_ROUTE_MASK;
  uint8_t payload_type = (header >> PH_TYPE_SHIFT) & PH_TYPE_MASK;
  
  // Transport packets: transport routes OR message payload types
  bool is_transport_route = (route_type == ROUTE_TYPE_TRANSPORT_FLOOD || 
                             route_type == ROUTE_TYPE_TRANSPORT_DIRECT);
  bool is_message_type = (payload_type == PAYLOAD_TYPE_TXT_MSG ||
                          payload_type == PAYLOAD_TYPE_GRP_TXT ||
                          payload_type == PAYLOAD_TYPE_GRP_DATA ||
                          payload_type == PAYLOAD_TYPE_REQ ||
                          payload_type == PAYLOAD_TYPE_RESPONSE ||
                          payload_type == PAYLOAD_TYPE_ANON_REQ ||
                          payload_type == PAYLOAD_TYPE_MULTIPART);
  
  return is_transport_route || is_message_type;
}

bool TCPBridge::isControlPacket(const uint8_t *payload, uint16_t len) const {
  if (len < 1) return false;
  
  uint8_t header = payload[0];
  uint8_t payload_type = (header >> PH_TYPE_SHIFT) & PH_TYPE_MASK;
  
  // Control/admin packets: discovery, adverts, ACKs, traces, atlas
  return (payload_type == PAYLOAD_TYPE_CONTROL ||
          payload_type == PAYLOAD_TYPE_ADVERT ||
          payload_type == PAYLOAD_TYPE_ACK ||
          payload_type == PAYLOAD_TYPE_TRACE ||
          payload_type == PAYLOAD_TYPE_PATH ||
          payload_type == PAYLOAD_TYPE_ATLAS);
}

void TCPBridge::sendPacket(mesh::Packet *packet) {
  if (!_initialized || !packet) return;
  if (_state != State::RUNNING) return;
  if (!shouldExportPacket(packet)) return;

  if (!_seen_packets.hasSeen(packet)) {
    sendBridgePacket(packet);
  }
}

bool TCPBridge::sendBridgePacket(mesh::Packet *packet) {
  uint8_t payload[MAX_TCP_PAYLOAD_SIZE];
  uint16_t mesh_len = packet->writeTo(payload + BRIDGE_V2_OVERHEAD);

  if (mesh_len > (MAX_TRANS_UNIT + 1)) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: TX packet too large (len=%d)\n", mesh_len);
    return false;
  }

  uint8_t ttl = _prefs->bridge_tcp_ttl;
  if (ttl == 0) ttl = 1;

  payload[0] = 'M';
  payload[1] = 'C';
  payload[2] = 'N';
  payload[3] = 'G';
  payload[4] = CONTROL_TYPE_BRIDGE_PACKET;
  payload[5] = BRIDGE_PACKET_VERSION;
  payload[6] = ttl;
  uint32_t id = getBridgeId();
  payload[7] = (id >> 24) & 0xFF;
  payload[8] = (id >> 16) & 0xFF;
  payload[9] = (id >> 8) & 0xFF;
  payload[10] = id & 0xFF;
  payload[11] = packet->wasReceivedFromBridge() ? 0 : BRIDGE_PACKET_FLAG_RF_RX;
  payload[12] = (mesh_len >> 8) & 0xFF;
  payload[13] = mesh_len & 0xFF;

  uint16_t len = mesh_len + BRIDGE_V2_OVERHEAD;
  if (sendPayloadFrame(payload, len)) {
    BRIDGE_DEBUG_PRINTLN("TCP bridge: TX bridge packet ttl=%d origin=0x%08lx len=%d\n",
                         ttl, (unsigned long)id, mesh_len);
    return true;
  }
  return false;
}

bool TCPBridge::shouldExportPacket(const mesh::Packet *packet) const {
  if (!packet) return false;
  if (packet->wasReceivedFromBridge()) return false;

  if (_prefs->bridge_export_max_hops > 0 &&
      packet->getPathHashCount() > _prefs->bridge_export_max_hops) {
    return false;
  }

  switch (_prefs->bridge_export_filter) {
    case BRIDGE_EXPORT_FLOOD:
      return packet->isRouteFlood();
    case BRIDGE_EXPORT_CHANNELS:
      return isChannelPacket(packet);
    case BRIDGE_EXPORT_MESSAGES:
      return isMessagePacket(packet);
    case BRIDGE_EXPORT_ALL:
    default:
      return true;
  }
}

bool TCPBridge::isChannelPacket(const mesh::Packet *packet) const {
  if (!packet || !packet->isRouteFlood()) return false;
  uint8_t type = packet->getPayloadType();
  return type == PAYLOAD_TYPE_GRP_TXT || type == PAYLOAD_TYPE_GRP_DATA;
}

bool TCPBridge::isMessagePacket(const mesh::Packet *packet) const {
  if (!packet) return false;
  uint8_t type = packet->getPayloadType();
  switch (type) {
    case PAYLOAD_TYPE_REQ:
    case PAYLOAD_TYPE_RESPONSE:
    case PAYLOAD_TYPE_TXT_MSG:
    case PAYLOAD_TYPE_ACK:
    case PAYLOAD_TYPE_PATH:
    case PAYLOAD_TYPE_GRP_TXT:
    case PAYLOAD_TYPE_GRP_DATA:
    case PAYLOAD_TYPE_ANON_REQ:
      return true;
    default:
      return false;
  }
}

uint32_t TCPBridge::getBridgeId() {
  if (_bridge_id != 0) return _bridge_id;

  uint8_t mac[6] = {};
  WiFi.macAddress(mac);
  _bridge_id = fnv1a32(mac, sizeof(mac));
  if (_bridge_id == 0 || _bridge_id == 2166136261UL) {
    size_t name_len = 0;
    while (name_len < sizeof(_prefs->node_name) && _prefs->node_name[name_len] != '\0') {
      name_len++;
    }
    _bridge_id = fnv1a32((const uint8_t *)_prefs->node_name, name_len);
  }
  if (_bridge_id == 0) _bridge_id = 1;
  return _bridge_id;
}

void TCPBridge::onPacketReceived(mesh::Packet *packet) {
  handleReceivedPacket(packet);
}

void TCPBridge::getStatusStr(char *reply) const {
  bool wifiOk = (WiFi.status() == WL_CONNECTED);
  bool serverOk = (_state == State::RUNNING);

  if (!wifiOk) {
    const char *stateStr = (_state == State::WIFI_WAIT) ? "connecting..." : "disconnected";
    const char *ntpStr = _prefs->ntp_enabled ? "not synced" : "disabled";
    sprintf(reply, "> WiFi: %s | Server: disconnected | NTP: %s", stateStr, ntpStr);
    return;
  }

  char ip[16];
  WiFi.localIP().toString().toCharArray(ip, sizeof(ip));
  const char *serverStr = serverOk ? "connected"
                        : (_state == State::SERVER_WAIT) ? "connecting..."
                        : "disconnected";
  const char *ntpStr = _prefs->ntp_enabled ? (_ntp_synced ? "synced" : "not synced") : "disabled";
  
  // Show flood protection stats if enabled and packets were dropped
  if (_prefs->tcp_flood_limit_enable && (_transport_dropped_count > 0 || _control_dropped_count > 0)) {
    sprintf(reply, "> WiFi: connected | IP: %s | RSSI: %d dBm | Server: %s | NTP: %s | Dropped: %lu transport, %lu control",
            ip, WiFi.RSSI(), serverStr, ntpStr,
            (unsigned long)_transport_dropped_count,
            (unsigned long)_control_dropped_count);
  } else {
    sprintf(reply, "> WiFi: connected | IP: %s | RSSI: %d dBm | Server: %s | NTP: %s",
            ip, WiFi.RSSI(), serverStr, ntpStr);
  }
}

void TCPBridge::syncTimeWithNTP(bool force) {
  if (!_prefs->ntp_enabled || WiFi.status() != WL_CONNECTED) return;

  uint32_t now_ms = millis();
  if (!force && _last_ntp_sync_ms != 0 && (now_ms - _last_ntp_sync_ms) < 5000) return;

  const char *server = _prefs->ntp_server[0] ? _prefs->ntp_server : "pool.ntp.org";
  BRIDGE_DEBUG_PRINTLN("TCP bridge: syncing time with NTP server %s\n", server);

  configTime(0, 0, server);

  struct tm timeinfo;
  bool ntp_ok = false;
  const uint32_t kMinValidEpoch = 1767225600UL;  // 2026-01-01 00:00:00 UTC

  for (int i = 0; i < 10; i++) {
    if (getLocalTime(&timeinfo, 500)) {
      uint32_t epoch = (uint32_t)mktime(&timeinfo);
      if (epoch >= kMinValidEpoch) {
        if (_rtc) {
          _rtc->setCurrentTime(epoch);
        }
        _ntp_synced = true;
        _last_ntp_sync_ms = millis();
        BRIDGE_DEBUG_PRINTLN("TCP bridge: NTP synced epoch=%lu\n", (unsigned long)epoch);
        ntp_ok = true;
        break;
      }
    }
  }

  if (!ntp_ok) {
    _last_ntp_sync_ms = millis();
    BRIDGE_DEBUG_PRINTLN("TCP bridge: NTP sync failed\n");
  }
}

void TCPBridge::refreshNTP(uint32_t now_ms) {
  if (!_prefs->ntp_enabled || WiFi.status() != WL_CONNECTED) return;

  uint32_t interval_ms = _prefs->ntp_interval_secs;
  if (interval_ms == 0) interval_ms = 3600;
  interval_ms *= 1000UL;

  if (_last_ntp_sync_ms == 0 || (now_ms - _last_ntp_sync_ms) >= interval_ms) {
    syncTimeWithNTP(true);
  }
}

#endif
