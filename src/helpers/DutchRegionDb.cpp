#include "DutchRegionDb.h"

#if WITH_DUTCH_REGION_DB
#include "DutchRegionDb.Generated.h"

#include <ctype.h>
#include <string.h>

static int asciiLower(int c) {
  return (c >= 'A' && c <= 'Z') ? c + ('a' - 'A') : c;
}

static int asciiStrcasecmp(const char* a, const char* b) {
  while (*a && *b) {
    int ca = asciiLower((uint8_t)*a++);
    int cb = asciiLower((uint8_t)*b++);
    if (ca != cb) return ca - cb;
  }
  return asciiLower((uint8_t)*a) - asciiLower((uint8_t)*b);
}

static bool asciiStartsWithIgnoreCase(const char* value, const char* prefix) {
  while (*prefix) {
    if (!*value) return false;
    if (asciiLower((uint8_t)*value++) != asciiLower((uint8_t)*prefix++)) return false;
  }
  return true;
}

uint16_t DutchRegionDb::sourceRevision() {
  return DutchRegionDbData::kSourceRevision;
}

const char* DutchRegionDb::sourceModified() {
  return DutchRegionDbData::kSourceModified;
}

uint16_t DutchRegionDb::provinceCount() {
  return DutchRegionDbData::kProvinceCount;
}

uint16_t DutchRegionDb::regionCodeCount() {
  return DutchRegionDbData::kCodeCount;
}

uint16_t DutchRegionDb::entryCount() {
  return DutchRegionDbData::kEntryCount;
}

const DutchRegionDbProvince* DutchRegionDb::provinceById(uint16_t province_id) {
  if (province_id == 0 || province_id > DutchRegionDbData::kProvinceCount) return NULL;
  return &DutchRegionDbData::kProvinces[province_id - 1];
}

const char* DutchRegionDb::codeText(uint16_t region_code_id) {
  if (region_code_id == 0 || region_code_id > DutchRegionDbData::kCodeCount) return NULL;
  const DutchRegionDbCode& code = DutchRegionDbData::kCodes[region_code_id - 1];
  return reinterpret_cast<const char*>(&DutchRegionDbData::kCodePool[code.text_offset]);
}

bool DutchRegionDb::readEntry(uint16_t index, DutchRegionDbEntry& dest) {
  if (index >= DutchRegionDbData::kEntryCount) return false;
  dest = DutchRegionDbData::kEntries[index];
  return true;
}

bool DutchRegionDb::readRecord(uint16_t index, DutchRegionDbRecord& dest) {
  DutchRegionDbEntry entry;
  if (!readEntry(index, entry)) return false;

  dest.name = reinterpret_cast<const char*>(&DutchRegionDbData::kNamePool[entry.name_offset]);
  dest.province_id = entry.province_id;
  dest.primary_region = entry.primary_region;
  dest.extra_count = entry.extra_count;
  return true;
}

uint16_t DutchRegionDb::extraRegionCode(const DutchRegionDbEntry& entry, uint8_t extra_index) {
  if (extra_index >= entry.extra_count) return 0;
  return DutchRegionDbData::kExtraRegionCodes[entry.extra_offset + extra_index];
}

int DutchRegionDb::findByName(const char* name) {
  if (!name || !*name) return -1;

  for (uint16_t i = 0; i < DutchRegionDbData::kEntryCount; i++) {
    DutchRegionDbRecord record;
    readRecord(i, record);
    if (asciiStrcasecmp(record.name, name) == 0) return i;
  }
  return -1;
}

int DutchRegionDb::findByNamePrefix(const char* prefix, uint16_t start_index) {
  if (!prefix || !*prefix) return -1;

  for (uint16_t i = start_index; i < DutchRegionDbData::kEntryCount; i++) {
    DutchRegionDbRecord record;
    readRecord(i, record);
    if (asciiStartsWithIgnoreCase(record.name, prefix)) return i;
  }
  return -1;
}

uint16_t DutchRegionDb::countByProvince(uint16_t province_id) {
  uint16_t count = 0;
  for (uint16_t i = 0; i < DutchRegionDbData::kEntryCount; i++) {
    DutchRegionDbEntry entry;
    readEntry(i, entry);
    if (entry.province_id == province_id) count++;
  }
  return count;
}
#else
uint16_t DutchRegionDb::sourceRevision() { return 0; }
const char* DutchRegionDb::sourceModified() { return ""; }
uint16_t DutchRegionDb::provinceCount() { return 0; }
uint16_t DutchRegionDb::regionCodeCount() { return 0; }
uint16_t DutchRegionDb::entryCount() { return 0; }
const DutchRegionDbProvince* DutchRegionDb::provinceById(uint16_t province_id) { return NULL; }
const char* DutchRegionDb::codeText(uint16_t region_code_id) { return NULL; }
bool DutchRegionDb::readEntry(uint16_t index, DutchRegionDbEntry& dest) { return false; }
bool DutchRegionDb::readRecord(uint16_t index, DutchRegionDbRecord& dest) { return false; }
uint16_t DutchRegionDb::extraRegionCode(const DutchRegionDbEntry& entry, uint8_t extra_index) { return 0; }
int DutchRegionDb::findByName(const char* name) { return -1; }
int DutchRegionDb::findByNamePrefix(const char* prefix, uint16_t start_index) { return -1; }
uint16_t DutchRegionDb::countByProvince(uint16_t province_id) { return 0; }
#endif
