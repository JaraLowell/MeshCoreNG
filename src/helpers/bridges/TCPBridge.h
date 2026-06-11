#pragma once

#include "helpers/bridges/BridgeBase.h"
#include <stddef.h>

#ifdef WITH_TCP_BRIDGE

/**
 * @brief Bridge implementation that tunnels mesh packets over a TCP connection
 *
 * Connects to a central TCP server (see tools/tcp_bridge_server.py) and exchanges
 * mesh packets with other repeaters connected to the same server. This allows
 * geographically separated LoRa mesh networks to act as one.
 *
 * The ESP32 connects to a WiFi access point in STA mode, then opens a TCP socket
 * to the configured server. Packets received from the local mesh are forwarded to
 * the server; packets arriving from the server are injected into the local mesh.
 *
 * Packet framing is identical to RS232Bridge:
 *   [2 bytes] Magic header (0xC03E)
 *   [2 bytes] Payload length
 *   [n bytes] Mesh packet payload
 *   [2 bytes] Fletcher-16 checksum over payload
 *
 * Configuration via CLI:
 *   set wifi.ssid <ssid>         WiFi network to join
 *   set wifi.password <pw>       WiFi password
 *   set bridge.server <host>     TCP server hostname or IP
 *   set bridge.port <port>       TCP server port (default 4200)
 *   set bridge.password <pw>     Optional TCP bridge server password
 *   set bridge.enabled on        Enable the bridge
 *
 * Firmware build flag: -D WITH_TCP_BRIDGE
 */
class TCPBridgeCommandHandler {
public:
  virtual void handleTcpBridgeCommand(const char *command, char *reply, size_t reply_size) = 0;
};

class TCPBridge : public BridgeBase {
public:
  TCPBridge(NodePrefs *prefs, mesh::PacketManager *mgr, mesh::RTCClock *rtc);

  void begin() override;
  void end() override;
  void loop() override;
  void sendPacket(mesh::Packet *packet) override;
  void onPacketReceived(mesh::Packet *packet) override;
  void getStatusStr(char *reply) const;
  void setCommandHandler(TCPBridgeCommandHandler *handler) { _command_handler = handler; }

private:
  static constexpr uint16_t TCP_OVERHEAD =
      BRIDGE_MAGIC_SIZE + BRIDGE_LENGTH_SIZE + BRIDGE_CHECKSUM_SIZE;
  static constexpr uint16_t MAX_TCP_PACKET_SIZE = (MAX_TRANS_UNIT + 1) + TCP_OVERHEAD;
  static constexpr uint32_t RECONNECT_INTERVAL_MS    = 5000;
  static constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS  = 15000;
  static constexpr uint32_t SERVER_CONNECT_TIMEOUT_MS = 500;
  static constexpr uint32_t SERVER_RECONNECT_INTERVAL_MS = 30000;
  static constexpr uint32_t HEARTBEAT_INTERVAL_MS    = 30000;
  static constexpr uint8_t  CONTROL_TYPE_HEARTBEAT   = 0x01;
  static constexpr uint8_t  CONTROL_TYPE_NODE_INFO   = 0x02;
  static constexpr uint8_t  CONTROL_TYPE_AUTH        = 0x03;
  static constexpr uint8_t  CONTROL_TYPE_COMMAND     = 0x10;
  static constexpr uint8_t  CONTROL_TYPE_COMMAND_REPLY = 0x11;

  enum class State : uint8_t {
    IDLE,           // waiting for reconnect timer
    WIFI_WAIT,      // WiFi.begin() called, polling for connection
    SERVER_WAIT,    // calling _client.connect() (brief blocking)
    RUNNING,        // fully connected, normal operation
  };

  State    _state          = State::IDLE;
  uint32_t _last_reconnect_ms = 0;
  uint32_t _reconnect_interval_ms = RECONNECT_INTERVAL_MS;
  uint32_t _wifi_start_ms  = 0;
  uint32_t _last_heartbeat_ms = 0;

  uint8_t  _rx_buffer[MAX_TCP_PACKET_SIZE];
  uint16_t _rx_buffer_pos = 0;
  TCPBridgeCommandHandler *_command_handler = nullptr;

  bool sendPayloadFrame(const uint8_t *payload, uint16_t len);
  void sendAuth();
  void sendNodeInfo();
  void sendHeartbeat();
  void handleControlPayload(const uint8_t *payload, uint16_t len);
  void handleCommandPayload(const uint8_t *payload, uint16_t len);
  void sendCommandReply(uint32_t request_id, const char *reply);
  bool isControlPayload(const uint8_t *payload, uint16_t len) const;
  void readIncoming();
};

#endif
