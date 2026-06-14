#pragma once

#include "helpers/bridges/BridgeBase.h"
#include "helpers/RateLimiter.h"

#ifdef WITH_TCP_BRIDGE

#include <WiFiUdp.h>
#include <NTPClient.h>

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
class TCPBridge : public BridgeBase {
public:
  TCPBridge(NodePrefs *prefs, mesh::PacketManager *mgr, mesh::RTCClock *rtc);

  void begin() override;
  void end() override;
  void loop() override;
  void sendPacket(mesh::Packet *packet) override;
  void onPacketReceived(mesh::Packet *packet) override;
  void getStatusStr(char *reply) const;
  
  /**
   * @brief Get the total number of packets dropped due to flood protection (all categories)
   * @return Total number of dropped packets
   */
  uint32_t getFloodDroppedCount() const { return _transport_dropped_count + _control_dropped_count; }
  
  /**
   * @brief Get the number of transport packets dropped due to flood protection
   * @return Number of transport packets dropped
   */
  uint32_t getTransportDroppedCount() const { return _transport_dropped_count; }
  
  /**
   * @brief Get the number of control packets dropped due to flood protection
   * @return Number of control packets dropped
   */
  uint32_t getControlDroppedCount() const { return _control_dropped_count; }
  
  /**
   * @brief Get the current packet count in the transport flood limiter window
   * @return Current transport packet count
   */
  uint16_t getFloodCurrentCount() const { return _transport_flood_limiter.getCount(); }
  
  /**
   * @brief Get the current transport packet count in the flood limiter window
   * @return Current transport packet count
   */
  uint16_t getTransportCurrentCount() const { return _transport_flood_limiter.getCount(); }
  
  /**
   * @brief Get the current control packet count in the flood limiter window
   * @return Current control packet count
   */
  uint16_t getControlCurrentCount() const { return _control_flood_limiter.getCount(); }

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

  // Selective flood protection with separate limiters per packet category
  RateLimiter _transport_flood_limiter;  // for transport/message packets
  RateLimiter _control_flood_limiter;    // for control/admin packets  
  uint32_t    _transport_dropped_count = 0;
  uint32_t    _control_dropped_count = 0;
  
  // NTP time synchronization
  WiFiUDP      _ntp_udp;
  NTPClient    _ntp_client;
  bool         _ntp_synced = false;
  uint32_t     _last_ntp_sync = 0;

  bool sendPayloadFrame(const uint8_t *payload, uint16_t len);
  void sendAuth();
  void sendNodeInfo();
  void sendHeartbeat();
  bool isControlPayload(const uint8_t *payload, uint16_t len) const;
  bool isTransportPacket(const uint8_t *payload, uint16_t len) const;
  bool isControlPacket(const uint8_t *payload, uint16_t len) const;
  void readIncoming();
  void syncTimeWithNTP();
  void refreshNTP();
};

#endif
