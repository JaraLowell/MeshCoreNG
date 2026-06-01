#include "Atlas.h"

static void putU16(uint8_t* dest, size_t& i, uint16_t v) {
  memcpy(&dest[i], &v, sizeof(v));
  i += sizeof(v);
}

static void putU32(uint8_t* dest, size_t& i, uint32_t v) {
  memcpy(&dest[i], &v, sizeof(v));
  i += sizeof(v);
}

static uint32_t atlasAbs32(int32_t v) {
  return v < 0 ? (uint32_t)(-v) : (uint32_t)v;
}

void Atlas::setDefaults(AtlasConfig& config) {
  memset(&config, 0, sizeof(config));
  config.position_min_interval_secs = 300;
  config.position_max_interval_secs = 1800;
  config.position_distance_meters = 500;
  config.position_heading_degrees = 30;
  config.position_speed_cm_s = 500;
  config.neighbors_interval_secs = 3600;
  config.path_sample_percent = 1;
}

size_t Atlas::encodePosition(uint8_t* dest, size_t max_len, const AtlasPosition& position) {
  size_t needed = 1 + 1 + 4 + 4 + 4;
  if (position.flags & ATLAS_POSITION_ALTITUDE) needed += 2;
  if (position.flags & ATLAS_POSITION_SPEED) needed += 2;
  if (position.flags & ATLAS_POSITION_HEADING) needed += 2;
  if (max_len < needed) return 0;

  size_t i = 0;
  dest[i++] = ATLAS_PACKET_POSITION;
  dest[i++] = position.flags;
  putU32(dest, i, (uint32_t)position.latitude_e7);
  putU32(dest, i, (uint32_t)position.longitude_e7);
  putU32(dest, i, position.timestamp);
  if (position.flags & ATLAS_POSITION_ALTITUDE) putU16(dest, i, (uint16_t)position.altitude_meters);
  if (position.flags & ATLAS_POSITION_SPEED) putU16(dest, i, position.speed_cm_s);
  if (position.flags & ATLAS_POSITION_HEADING) putU16(dest, i, position.heading_degrees);
  return i;
}

size_t Atlas::encodeNeighbors(uint8_t* dest, size_t max_len, const AtlasNeighbor* neighbors, uint8_t count) {
  if (count > ATLAS_MAX_NEIGHBORS) count = ATLAS_MAX_NEIGHBORS;
  size_t needed = 2 + ((size_t)count * 10);
  if (max_len < needed) return 0;

  size_t i = 0;
  dest[i++] = ATLAS_PACKET_NEIGHBORS;
  dest[i++] = count;
  for (uint8_t n = 0; n < count; n++) {
    putU32(dest, i, neighbors[n].node_id);
    dest[i++] = (uint8_t)neighbors[n].last_rssi;
    dest[i++] = (uint8_t)neighbors[n].last_snr_quarter_db;
    putU32(dest, i, neighbors[n].last_heard);
  }
  return i;
}

size_t Atlas::encodePathSample(uint8_t* dest, size_t max_len, const AtlasPathSample& sample) {
  uint8_t hop_count = sample.hop_count > ATLAS_MAX_PATH_HOPS ? ATLAS_MAX_PATH_HOPS : sample.hop_count;
  size_t needed = 1 + 4 + 4 + 1 + hop_count + 1 + (sample.has_latency ? 4 : 0);
  if (max_len < needed) return 0;

  size_t i = 0;
  dest[i++] = ATLAS_PACKET_PATH_SAMPLE;
  putU32(dest, i, sample.source);
  putU32(dest, i, sample.destination);
  dest[i++] = hop_count;
  memcpy(&dest[i], sample.hops, hop_count);
  i += hop_count;
  dest[i++] = sample.has_latency ? 1 : 0;
  if (sample.has_latency) putU32(dest, i, sample.latency_ms);
  return i;
}

size_t Atlas::encodeDenseStats(uint8_t* dest, size_t max_len, const AtlasDenseStats& stats) {
  if (max_len < 33) return 0;
  size_t i = 0;
  dest[i++] = ATLAS_PACKET_DENSE_STATS;
  putU32(dest, i, stats.heard_count);
  putU32(dest, i, stats.duplicate_count);
  putU32(dest, i, stats.forward_count);
  putU32(dest, i, stats.suppression_count);
  putU32(dest, i, stats.route_cache_hits);
  putU32(dest, i, stats.route_cache_misses);
  putU32(dest, i, stats.tx_airtime_ms);
  putU32(dest, i, stats.rx_airtime_ms);
  return i;
}

bool Atlas::shouldReportPosition(const AtlasConfig& config, const AtlasPositionState& state, const AtlasPosition& next) {
  if (!config.enabled || !config.position_enabled) return false;
  if (!state.valid) return true;
  if (next.timestamp < state.last.timestamp + config.position_min_interval_secs) return false;
  if (next.timestamp >= state.last.timestamp + config.position_max_interval_secs) return true;

  uint32_t lat_delta = atlasAbs32(next.latitude_e7 - state.last.latitude_e7);
  uint32_t lon_delta = atlasAbs32(next.longitude_e7 - state.last.longitude_e7);
  uint32_t threshold_e7 = config.position_distance_meters * 90UL;
  if (lat_delta + lon_delta >= threshold_e7) return true;

  uint16_t heading_delta = next.heading_degrees > state.last.heading_degrees ?
      next.heading_degrees - state.last.heading_degrees :
      state.last.heading_degrees - next.heading_degrees;
  if (heading_delta > 180) heading_delta = 360 - heading_delta;
  if (heading_delta >= config.position_heading_degrees) return true;

  uint16_t speed_delta = next.speed_cm_s > state.last.speed_cm_s ?
      next.speed_cm_s - state.last.speed_cm_s :
      state.last.speed_cm_s - next.speed_cm_s;
  return speed_delta >= config.position_speed_cm_s;
}

mesh::Packet* Atlas::createZeroHopPacket(mesh::PacketManager* mgr, uint8_t atlas_type, const uint8_t* data, size_t len) {
  (void)atlas_type;
  if (mgr == NULL || data == NULL || len > MAX_PACKET_PAYLOAD) return NULL;
  mesh::Packet* packet = mgr->allocNew();
  if (packet == NULL) return NULL;
  packet->header = (PAYLOAD_TYPE_ATLAS << PH_TYPE_SHIFT) | ROUTE_TYPE_DIRECT;
  packet->path_len = 0;
  memcpy(packet->payload, data, len);
  packet->payload_len = len;
  return packet;
}

void AtlasObserver::emitPosition(const AtlasPosition& position) {
  if (!_json_enabled || _sink == NULL) return;
  char line[160];
  snprintf(line, sizeof(line),
      "{\"event\":\"POSITION\",\"lat_e7\":%ld,\"lon_e7\":%ld,\"alt\":%d,\"speed\":%u,\"heading\":%u,\"time\":%lu}",
      (long)position.latitude_e7, (long)position.longitude_e7, (int)position.altitude_meters,
      (uint32_t)position.speed_cm_s, (uint32_t)position.heading_degrees, (unsigned long)position.timestamp);
  _sink->onAtlasEvent(line);
}

void AtlasObserver::emitNeighbor(const AtlasNeighbor& neighbor) {
  if (!_json_enabled || _sink == NULL) return;
  char line[128];
  snprintf(line, sizeof(line),
      "{\"event\":\"NEIGHBOR\",\"node\":%lu,\"rssi\":%d,\"snr\":%.2f,\"last_heard\":%lu}",
      (unsigned long)neighbor.node_id, (int)neighbor.last_rssi,
      ((float)neighbor.last_snr_quarter_db) / 4.0f, (unsigned long)neighbor.last_heard);
  _sink->onAtlasEvent(line);
}

void AtlasObserver::emitPath(const AtlasPathSample& path) {
  if (!_json_enabled || _sink == NULL) return;
  char line[160];
  snprintf(line, sizeof(line),
      "{\"event\":\"PATH\",\"source\":%lu,\"destination\":%lu,\"hops\":%u,\"latency_ms\":%lu}",
      (unsigned long)path.source, (unsigned long)path.destination, (uint32_t)path.hop_count,
      (unsigned long)(path.has_latency ? path.latency_ms : 0));
  _sink->onAtlasEvent(line);
}

void AtlasObserver::emitDenseStats(const AtlasDenseStats& stats) {
  if (!_json_enabled || _sink == NULL) return;
  char line[192];
  snprintf(line, sizeof(line),
      "{\"event\":\"DENSE_STATS\",\"heard\":%lu,\"dup\":%lu,\"fwd\":%lu,\"suppress\":%lu,\"tx_air_ms\":%lu,\"rx_air_ms\":%lu}",
      (unsigned long)stats.heard_count, (unsigned long)stats.duplicate_count,
      (unsigned long)stats.forward_count, (unsigned long)stats.suppression_count,
      (unsigned long)stats.tx_airtime_ms, (unsigned long)stats.rx_airtime_ms);
  _sink->onAtlasEvent(line);
}
