#pragma once

#include <stddef.h>
#include <stdint.h>

namespace meshcore {

static constexpr uint8_t LOCATION_REPORT_VERSION = 1;
static constexpr size_t LOCATION_REPORT_MAX_NAME_LEN = 24;
static constexpr size_t LOCATION_REPORT_MAX_ENCODED_LEN = 4 + 1 + 1 + 4 + 4 + 4 + 2 + 2 + 2 + 1 + 2 + 4 + 1 + LOCATION_REPORT_MAX_NAME_LEN;

struct LocationReport {
  uint8_t version = LOCATION_REPORT_VERSION;
  uint8_t flags = 0;
  uint8_t node_id[4] = {0, 0, 0, 0};
  int32_t lat_microdeg = 0;
  int32_t lon_microdeg = 0;
  int16_t altitude_m = 0;
  uint16_t speed_cms = 0;
  uint16_t heading_cdeg = 0;
  uint8_t satellites = 0;
  uint16_t battery_mv = 0;
  uint32_t timestamp = 0;
  char name[LOCATION_REPORT_MAX_NAME_LEN + 1] = {};
};

size_t encodeLocationReport(uint8_t *dest, size_t dest_len, const LocationReport &report);
bool decodeLocationReport(LocationReport &report, const uint8_t *src, size_t src_len);

}  // namespace meshcore
