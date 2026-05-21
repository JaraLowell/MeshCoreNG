#pragma once

#include <Arduino.h>

#if defined(__GNUC__)
#define DUTCH_REGION_DB_PACKED __attribute__((packed))
#else
#define DUTCH_REGION_DB_PACKED
#endif

struct DutchRegionDbProvince {
  uint16_t id;
  char abbr[3];
  const char* name;
};

struct DutchRegionDbCode {
  uint16_t id;
  uint16_t text_offset;
};

struct DutchRegionDbEntry {
  uint16_t name_offset;
  uint16_t province_id;
  uint16_t primary_region;
  uint16_t extra_offset;
  uint8_t extra_count;
} DUTCH_REGION_DB_PACKED;

struct DutchRegionDbRecord {
  const char* name;
  uint16_t province_id;
  uint16_t primary_region;
  uint16_t extra_count;
};

class DutchRegionDb {
public:
  static uint16_t sourceRevision();
  static const char* sourceModified();
  static uint16_t provinceCount();
  static uint16_t regionCodeCount();
  static uint16_t entryCount();

  static const DutchRegionDbProvince* provinceById(uint16_t province_id);
  static const char* codeText(uint16_t region_code_id);
  static bool readEntry(uint16_t index, DutchRegionDbEntry& dest);
  static bool readRecord(uint16_t index, DutchRegionDbRecord& dest);
  static uint16_t extraRegionCode(const DutchRegionDbEntry& entry, uint8_t extra_index);

  static int findByName(const char* name);
  static int findByNamePrefix(const char* prefix, uint16_t start_index = 0);
  static uint16_t countByProvince(uint16_t province_id);
};
