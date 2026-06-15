#include "LowBatteryBootGuard.h"

#include <Arduino.h>

void guardLowBatteryBoot(mesh::MainBoard& board, uint8_t enabled, uint16_t threshold_mv, uint16_t valid_min_mv, uint16_t retry_secs) {
  if (!enabled || threshold_mv == 0) {
    return;
  }

  while (true) {
    uint16_t mv = board.getBattMilliVolts();

    if (mv < valid_min_mv || mv >= threshold_mv) {
      return;
    }

    Serial.print("LOWBAT: boot guard active, battery=");
    Serial.print(mv);
    Serial.print("mV threshold=");
    Serial.print((unsigned)threshold_mv);
    Serial.print("mV; retry in ");
    Serial.print((unsigned)retry_secs);
    Serial.println("s");

    board.sleep(retry_secs);

    // Some board sleep implementations are no-ops or return immediately.
    delay(1000);
  }
}

void guardLowBatteryBoot(mesh::MainBoard& board) {
#if LOW_BAT_BOOT_GUARD_MV > 0
  guardLowBatteryBoot(board, 1, LOW_BAT_BOOT_GUARD_MV, LOW_BAT_BOOT_VALID_MIN_MV, LOW_BAT_BOOT_RETRY_SECS);
#else
  (void)board;
#endif
}

bool guardRuntimeLowBattery(mesh::MainBoard& board, uint8_t enabled, uint16_t threshold_mv, uint16_t valid_min_mv, uint32_t retry_secs) {
  if (!enabled || threshold_mv == 0 || board.isExternalPowered()) {
    return false;
  }

  uint16_t mv = board.getBattMilliVolts();
  if (mv < valid_min_mv || mv >= threshold_mv) {
    return false;
  }

  Serial.print("LOWBAT: runtime guard active, battery=");
  Serial.print(mv);
  Serial.print("mV threshold=");
  Serial.print((unsigned)threshold_mv);
  Serial.print("mV; sleep for ");
  Serial.print((unsigned long)retry_secs);
  Serial.println("s");

  board.sleep(retry_secs);

  // Some board sleep implementations are no-ops or return immediately.
  delay(1000);
  return true;
}
