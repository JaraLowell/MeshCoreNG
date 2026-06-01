#pragma once

#include <Arduino.h>
#include <Mesh.h>

#define ATLAS_PACKET_POSITION       0x01
#define ATLAS_PACKET_NEIGHBORS      0x02
#define ATLAS_PACKET_PATH_SAMPLE    0x03
#define ATLAS_PACKET_DENSE_STATS    0x04

#define ATLAS_POSITION_ALTITUDE     0x01
#define ATLAS_POSITION_SPEED        0x02
#define ATLAS_POSITION_HEADING      0x04

#define ATLAS_MAX_NEIGHBORS         12
#define ATLAS_MAX_PATH_HOPS         24

struct AtlasConfig {
  uint8_t enabled;
  uint8_t position_enabled;
  uint8_t neighbors_enabled;
  uint8_t path_sample_enabled;
  uint8_t export_enabled;
  uint32_t position_min_interval_secs;
  uint32_t position_max_interval_secs;
  uint32_t position_distance_meters;
  uint16_t position_heading_degrees;
  uint16_t position_speed_cm_s;
  uint32_t neighbors_interval_secs;
  uint8_t path_sample_percent;
};

struct AtlasPosition {
  int32_t latitude_e7;
  int32_t longitude_e7;
  uint32_t timestamp;
  uint8_t flags;
  int16_t altitude_meters;
  uint16_t speed_cm_s;
  uint16_t heading_degrees;
};

struct AtlasPositionState {
  uint8_t valid;
  AtlasPosition last;
};

struct AtlasNeighbor {
  uint32_t node_id;
  int8_t last_rssi;
  int8_t last_snr_quarter_db;
  uint32_t last_heard;
};

struct AtlasPathSample {
  uint32_t source;
  uint32_t destination;
  uint8_t hop_count;
  uint8_t hops[ATLAS_MAX_PATH_HOPS];
  uint32_t latency_ms;
  uint8_t has_latency;
};

struct AtlasDenseStats {
  uint32_t heard_count;
  uint32_t duplicate_count;
  uint32_t forward_count;
  uint32_t suppression_count;
  uint32_t route_cache_hits;
  uint32_t route_cache_misses;
  uint32_t tx_airtime_ms;
  uint32_t rx_airtime_ms;
};

class AtlasObserverSink {
public:
  virtual void onAtlasEvent(const char* json_line) = 0;
};

class AtlasObserver {
  AtlasObserverSink* _sink;
  uint8_t _json_enabled;

public:
  AtlasObserver() : _sink(NULL), _json_enabled(0) { }

  void begin(AtlasObserverSink* sink) { _sink = sink; }
  void setJsonEnabled(bool enabled) { _json_enabled = enabled ? 1 : 0; }
  bool isJsonEnabled() const { return _json_enabled != 0; }

  void emitPosition(const AtlasPosition& position);
  void emitNeighbor(const AtlasNeighbor& neighbor);
  void emitPath(const AtlasPathSample& path);
  void emitDenseStats(const AtlasDenseStats& stats);
};

class Atlas {
public:
  static void setDefaults(AtlasConfig& config);
  static size_t encodePosition(uint8_t* dest, size_t max_len, const AtlasPosition& position);
  static size_t encodeNeighbors(uint8_t* dest, size_t max_len, const AtlasNeighbor* neighbors, uint8_t count);
  static size_t encodePathSample(uint8_t* dest, size_t max_len, const AtlasPathSample& sample);
  static size_t encodeDenseStats(uint8_t* dest, size_t max_len, const AtlasDenseStats& stats);
  static bool shouldReportPosition(const AtlasConfig& config, const AtlasPositionState& state, const AtlasPosition& next);
  static mesh::Packet* createZeroHopPacket(mesh::PacketManager* mgr, uint8_t atlas_type, const uint8_t* data, size_t len);
};
