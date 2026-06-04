#pragma once

#include "helpers/bridges/BridgeBase.h"

#ifdef WITH_BLE_BRIDGE

#if defined(NRF52_PLATFORM)
#include <bluefruit.h>
#elif defined(ESP32)
#include <BLE2902.h>
#include <BLEAdvertisedDevice.h>
#include <BLEClient.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#else
#error "BLEBridge requires nRF52 Bluefruit or ESP32 BLE"
#endif

#if defined(ESP32)
class BLEBridge : public BridgeBase,
                  public BLEServerCallbacks,
                  public BLECharacteristicCallbacks,
                  public BLEClientCallbacks,
                  public BLEAdvertisedDeviceCallbacks {
#else
class BLEBridge : public BridgeBase {
#endif
public:
  BLEBridge(NodePrefs *prefs, mesh::PacketManager *mgr, mesh::RTCClock *rtc);

  void begin() override;
  void end() override;
  void loop() override;
  void sendPacket(mesh::Packet *packet) override;
  void onPacketReceived(mesh::Packet *packet) override;
  void getStatusStr(char *reply) const;

private:
  static constexpr uint16_t BLE_BRIDGE_OVERHEAD = BRIDGE_MAGIC_SIZE + BRIDGE_LENGTH_SIZE + BRIDGE_CHECKSUM_SIZE;
  static constexpr uint16_t MAX_BLE_BRIDGE_PACKET_SIZE = (MAX_TRANS_UNIT + 1) + BLE_BRIDGE_OVERHEAD;
  static constexpr uint16_t BLE_UART_FIFO_DEPTH = 512;

  static BLEBridge *_instance;

#if defined(NRF52_PLATFORM)
  static void scanCallback(ble_gap_evt_adv_report_t *report);
  static void peripheralConnectCallback(uint16_t conn_handle);
  static void peripheralDisconnectCallback(uint16_t conn_handle, uint8_t reason);
  static void centralConnectCallback(uint16_t conn_handle);
  static void centralDisconnectCallback(uint16_t conn_handle, uint8_t reason);
  static void peripheralRxCallback(uint16_t conn_handle);
  static void centralRxCallback(BLEClientUart &uart);

  BLEUart _peripheral_uart;
  BLEClientUart _central_uart;
  uint16_t _peripheral_conn_handle;
  uint16_t _central_conn_handle;
#elif defined(ESP32)
  static void clientNotifyCallback(BLERemoteCharacteristic *characteristic, uint8_t *data, size_t len, bool notify);

  BLEServer *_server;
  BLEService *_service;
  BLECharacteristic *_server_tx_characteristic;
  BLECharacteristic *_server_rx_characteristic;
  BLEClient *_client;
  BLERemoteCharacteristic *_client_rx_characteristic;
  BLERemoteCharacteristic *_client_tx_characteristic;
  BLEAdvertisedDevice *_advertised_device;
#endif

  bool _central_connected;
  bool _central_discovered;
  bool _peripheral_connected;
  bool _should_connect;
  unsigned long _next_scan_at;
  unsigned long _last_write_at;
  uint32_t _tx_frames;
  uint32_t _rx_frames;
  uint32_t _rx_bad_checksum;
  uint32_t _rx_parse_fail;
  uint32_t _tx_seen_drop;
  uint32_t _tx_no_link;

  uint8_t _peripheral_rx_buffer[MAX_BLE_BRIDGE_PACKET_SIZE];
  uint16_t _peripheral_rx_buffer_pos;
  uint8_t _central_rx_buffer[MAX_BLE_BRIDGE_PACKET_SIZE];
  uint16_t _central_rx_buffer_pos;

  void startAdvertising();
  void startScanning();
  bool connectToAdvertisedDevice();
  void xorCrypt(uint8_t *data, size_t len);
  void readFrom(Stream &stream, uint8_t *buffer, uint16_t &buffer_pos);
  void readBytes(const uint8_t *data, size_t len, uint8_t *buffer, uint16_t &buffer_pos);
  void handleByte(uint8_t b, uint8_t *buffer, uint16_t &buffer_pos);

#if defined(NRF52_PLATFORM)
  void sendFrame(BLEUart &uart, uint16_t conn_handle, const uint8_t *buffer, size_t len);
  void sendFrame(BLEClientUart &uart, const uint8_t *buffer, size_t len);
#elif defined(ESP32)
  void sendServerFrame(const uint8_t *buffer, size_t len);
  void sendClientFrame(const uint8_t *buffer, size_t len);

  void onConnect(BLEServer *server) override;
  void onDisconnect(BLEServer *server) override;
  void onConnect(BLEClient *client) override;
  void onDisconnect(BLEClient *client) override;
  void onWrite(BLECharacteristic *characteristic) override;
  void onWrite(BLECharacteristic *characteristic, esp_ble_gatts_cb_param_t *param) override;
  void onResult(BLEAdvertisedDevice advertised_device) override;
#endif
};

#endif
