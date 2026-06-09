#include "LocationReport.h"

#include <string.h>

namespace meshcore {

static void putU16(uint8_t *dest, uint16_t value) {
  dest[0] = (uint8_t)(value >> 8);
  dest[1] = (uint8_t)value;
}

static void putU32(uint8_t *dest, uint32_t value) {
  dest[0] = (uint8_t)(value >> 24);
  dest[1] = (uint8_t)(value >> 16);
  dest[2] = (uint8_t)(value >> 8);
  dest[3] = (uint8_t)value;
}

static uint16_t getU16(const uint8_t *src) {
  return ((uint16_t)src[0] << 8) | src[1];
}

static uint32_t getU32(const uint8_t *src) {
  return ((uint32_t)src[0] << 24) | ((uint32_t)src[1] << 16) | ((uint32_t)src[2] << 8) | src[3];
}

size_t encodeLocationReport(uint8_t *dest, size_t dest_len, const LocationReport &report) {
  size_t name_len = 0;
  while (name_len < LOCATION_REPORT_MAX_NAME_LEN && report.name[name_len] != '\0') {
    name_len++;
  }
  size_t needed = LOCATION_REPORT_MAX_ENCODED_LEN - LOCATION_REPORT_MAX_NAME_LEN + name_len;
  if (dest_len < needed) return 0;

  size_t i = 0;
  dest[i++] = 'M';
  dest[i++] = 'C';
  dest[i++] = 'L';
  dest[i++] = '1';
  dest[i++] = LOCATION_REPORT_VERSION;
  dest[i++] = report.flags;
  memcpy(&dest[i], report.node_id, sizeof(report.node_id));
  i += sizeof(report.node_id);
  putU32(&dest[i], (uint32_t)report.lat_microdeg);
  i += 4;
  putU32(&dest[i], (uint32_t)report.lon_microdeg);
  i += 4;
  putU16(&dest[i], (uint16_t)report.altitude_m);
  i += 2;
  putU16(&dest[i], report.speed_cms);
  i += 2;
  putU16(&dest[i], report.heading_cdeg);
  i += 2;
  dest[i++] = report.satellites;
  putU16(&dest[i], report.battery_mv);
  i += 2;
  putU32(&dest[i], report.timestamp);
  i += 4;
  dest[i++] = (uint8_t)name_len;
  memcpy(&dest[i], report.name, name_len);
  i += name_len;
  return i;
}

bool decodeLocationReport(LocationReport &report, const uint8_t *src, size_t src_len) {
  constexpr size_t min_len = LOCATION_REPORT_MAX_ENCODED_LEN - LOCATION_REPORT_MAX_NAME_LEN;
  if (src_len < min_len) return false;
  if (src[0] != 'M' || src[1] != 'C' || src[2] != 'L' || src[3] != '1') return false;
  if (src[4] != LOCATION_REPORT_VERSION) return false;

  size_t i = 4;
  report.version = src[i++];
  report.flags = src[i++];
  memcpy(report.node_id, &src[i], sizeof(report.node_id));
  i += sizeof(report.node_id);
  report.lat_microdeg = (int32_t)getU32(&src[i]);
  i += 4;
  report.lon_microdeg = (int32_t)getU32(&src[i]);
  i += 4;
  report.altitude_m = (int16_t)getU16(&src[i]);
  i += 2;
  report.speed_cms = getU16(&src[i]);
  i += 2;
  report.heading_cdeg = getU16(&src[i]);
  i += 2;
  report.satellites = src[i++];
  report.battery_mv = getU16(&src[i]);
  i += 2;
  report.timestamp = getU32(&src[i]);
  i += 4;
  uint8_t name_len = src[i++];
  if (name_len > LOCATION_REPORT_MAX_NAME_LEN || i + name_len > src_len) return false;
  memcpy(report.name, &src[i], name_len);
  report.name[name_len] = '\0';
  return true;
}

}  // namespace meshcore
