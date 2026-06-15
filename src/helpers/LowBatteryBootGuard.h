#pragma once

#include <MeshCore.h>

#ifndef LOW_BAT_BOOT_GUARD_MV
#define LOW_BAT_BOOT_GUARD_MV 3300
#endif

#ifndef LOW_BAT_BOOT_VALID_MIN_MV
#define LOW_BAT_BOOT_VALID_MIN_MV 2500
#endif

#ifndef LOW_BAT_BOOT_RETRY_SECS
#define LOW_BAT_BOOT_RETRY_SECS 60
#endif

#ifndef LOW_BAT_RUNTIME_GUARD_MV
#define LOW_BAT_RUNTIME_GUARD_MV 3300
#endif

#ifndef LOW_BAT_RUNTIME_WARN_MV
#define LOW_BAT_RUNTIME_WARN_MV 3500
#endif

#ifndef LOW_BAT_RUNTIME_VALID_MIN_MV
#define LOW_BAT_RUNTIME_VALID_MIN_MV 2500
#endif

#ifndef LOW_BAT_RUNTIME_RETRY_SECS
#define LOW_BAT_RUNTIME_RETRY_SECS 1800
#endif

#ifndef LOW_BAT_RUNTIME_CHECK_SECS
#define LOW_BAT_RUNTIME_CHECK_SECS 30
#endif

void guardLowBatteryBoot(mesh::MainBoard& board);
void guardLowBatteryBoot(mesh::MainBoard& board, uint8_t enabled, uint16_t threshold_mv, uint16_t valid_min_mv, uint16_t retry_secs);
bool guardRuntimeLowBattery(mesh::MainBoard& board, uint8_t enabled, uint16_t threshold_mv, uint16_t valid_min_mv, uint32_t retry_secs);
