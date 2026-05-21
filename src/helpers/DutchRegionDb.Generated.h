#pragma once

#include <Arduino.h>
#include "DutchRegionDb.h"

namespace DutchRegionDbData {

extern const uint8_t kNamePool[] PROGMEM;
extern const uint8_t kCodePool[] PROGMEM;
extern const DutchRegionDbProvince kProvinces[] PROGMEM;
extern const DutchRegionDbCode kCodes[] PROGMEM;
extern const DutchRegionDbEntry kEntries[] PROGMEM;
extern const uint16_t kExtraRegionCodes[] PROGMEM;

constexpr uint16_t kSourceRevision = 100;
constexpr char kSourceModified[] = "2026-03-23T14:07:28Z";
constexpr uint16_t kProvinceCount = 12;
constexpr uint16_t kCodeCount = 1611;
constexpr uint16_t kEntryCount = 2484;
constexpr uint16_t kExtraRegionCodeCount = 4187;
constexpr uint16_t kNamePoolSize = 24177;
constexpr uint16_t kCodePoolSize = 15984;

}  // namespace DutchRegionDbData
