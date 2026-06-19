#include "SensorMesh.h"

#include <helpers/LowBatteryBootGuard.h>
#include <helpers/LocationReport.h>
#include <helpers/TxtDataHelpers.h>
#include <Utils.h>

#ifdef DISPLAY_CLASS
  #include "UITask.h"
  static UITask ui_task(display);
#endif

#ifndef LOCATION_TRACKER_INTERVAL_SECS
  #define LOCATION_TRACKER_INTERVAL_SECS 0
#endif
#ifndef LOCATION_TRACKER_ADAPTIVE_INTERVAL
  #define LOCATION_TRACKER_ADAPTIVE_INTERVAL 0
#endif
#ifndef LOCATION_TRACKER_STATIONARY_INTERVAL_SECS
  #define LOCATION_TRACKER_STATIONARY_INTERVAL_SECS 300
#endif
#ifndef LOCATION_TRACKER_SLOW_INTERVAL_SECS
  #define LOCATION_TRACKER_SLOW_INTERVAL_SECS LOCATION_TRACKER_INTERVAL_SECS
#endif
#ifndef LOCATION_TRACKER_FAST_INTERVAL_SECS
  #define LOCATION_TRACKER_FAST_INTERVAL_SECS 20
#endif
#ifndef LOCATION_TRACKER_STATIONARY_SPEED_CMS
  #define LOCATION_TRACKER_STATIONARY_SPEED_CMS 50
#endif
#ifndef LOCATION_TRACKER_FAST_SPEED_CMS
  #define LOCATION_TRACKER_FAST_SPEED_CMS 500
#endif

class MyMesh : public SensorMesh {
public:
  MyMesh(mesh::MainBoard& board, mesh::Radio& radio, mesh::MillisecondClock& ms, mesh::RNG& rng, mesh::RTCClock& rtc, mesh::MeshTables& tables)
     : SensorMesh(board, radio, ms, rng, rtc, tables), 
       battery_data(12*24, 5*60)    // 24 hours worth of battery data, every 5 minutes
  {
    next_location_report = 0;
  }

  void loopApp() {
#if LOCATION_TRACKER_INTERVAL_SECS > 0 && ENV_INCLUDE_GPS == 1
    if (next_location_report == 0 || millisHasNowPassed(next_location_report)) {
      sendLocationReport();
      next_location_report = futureMillis(getLocationTrackerIntervalSecs() * 1000);
    }
#endif
  }

protected:
  /* ========================== custom logic here ========================== */
  Trigger low_batt, critical_batt;
  TimeSeriesData  battery_data;
  unsigned long next_location_report;

#if LOCATION_TRACKER_INTERVAL_SECS > 0 && ENV_INCLUDE_GPS == 1
  mesh::GroupChannel trackerChannel() {
    static const uint8_t tracker_group_secret[16] = {
      0x5F, 0x30, 0x3A, 0xC5, 0x07, 0x5F, 0x80, 0x0F,
      0x0F, 0x47, 0x11, 0x31, 0x99, 0xD5, 0x10, 0x53
    };

    mesh::GroupChannel channel;
    memset(channel.secret, 0, sizeof(channel.secret));
    memcpy(channel.secret, tracker_group_secret, sizeof(tracker_group_secret));
    mesh::Utils::sha256(channel.hash, sizeof(channel.hash), tracker_group_secret, sizeof(tracker_group_secret));
    return channel;
  }

  uint32_t getLocationTrackerIntervalSecs() {
#if LOCATION_TRACKER_ADAPTIVE_INTERVAL
    LocationProvider* location = sensors.getLocationProvider();
    if (location && location->isEnabled() && location->isValid()) {
      uint16_t speed_cms = location->getSpeedCmS();
      if (speed_cms < LOCATION_TRACKER_STATIONARY_SPEED_CMS) return LOCATION_TRACKER_STATIONARY_INTERVAL_SECS;
      if (speed_cms >= LOCATION_TRACKER_FAST_SPEED_CMS) return LOCATION_TRACKER_FAST_INTERVAL_SECS;
      return LOCATION_TRACKER_SLOW_INTERVAL_SECS;
    }
#endif
    return LOCATION_TRACKER_INTERVAL_SECS;
  }

  void sendLocationReport() {
    LocationProvider* location = sensors.getLocationProvider();
    if (!location || !location->isEnabled() || !location->isValid()) return;

    meshcore::LocationReport report;
    memcpy(report.node_id, self_id.pub_key, sizeof(report.node_id));
    report.lat_microdeg = (int32_t)location->getLatitude();
    report.lon_microdeg = (int32_t)location->getLongitude();
    report.altitude_m = (int16_t)(location->getAltitude() / 1000);
    report.speed_cms = location->getSpeedCmS();
    report.heading_cdeg = location->getHeadingCdeg();
    report.satellites = (uint8_t)min(255L, location->satellitesCount());
    report.battery_mv = (uint16_t)min(65535, (int)board.getBattMilliVolts());
    report.timestamp = (uint32_t)getRTCClock()->getCurrentTime();
    StrHelper::strncpy(report.name, getNodeName(), sizeof(report.name));

    uint8_t payload[meshcore::LOCATION_REPORT_MAX_ENCODED_LEN];
    size_t len = meshcore::encodeLocationReport(payload, sizeof(payload), report);
    if (len == 0) return;

    uint8_t group_data[3 + meshcore::LOCATION_REPORT_MAX_ENCODED_LEN];
    group_data[0] = (uint8_t)(DATA_TYPE_MESHCORENG_TRACKER & 0xFF);
    group_data[1] = (uint8_t)(DATA_TYPE_MESHCORENG_TRACKER >> 8);
    group_data[2] = (uint8_t)len;
    memcpy(&group_data[3], payload, len);

    mesh::GroupChannel channel = trackerChannel();
    mesh::Packet* pkt = createGroupDatagram(PAYLOAD_TYPE_GRP_DATA, channel, group_data, 3 + len);
    if (!pkt) return;

    NodePrefs* prefs = getNodePrefs();
    sendFlood(pkt, (uint32_t)0, prefs->path_hash_mode + 1);
  }
#endif

  void onSensorDataRead() override {
    float batt_voltage = getVoltage(TELEM_CHANNEL_SELF);

    battery_data.recordData(getRTCClock(), batt_voltage);   // record battery
    alertIf(batt_voltage < 3.4f, critical_batt, HIGH_PRI_ALERT, "Battery is critical!");
    alertIf(batt_voltage < 3.6f, low_batt, LOW_PRI_ALERT, "Battery is low");
  }

  int querySeriesData(uint32_t start_secs_ago, uint32_t end_secs_ago, MinMaxAvg dest[], int max_num) override {
    battery_data.calcMinMaxAvg(getRTCClock(), start_secs_ago, end_secs_ago, &dest[0], TELEM_CHANNEL_SELF, LPP_VOLTAGE);
    return 1;
  }

  bool handleCustomCommand(uint32_t sender_timestamp, char* command, char* reply) override {
    if (strcmp(command, "magic") == 0) {    // example 'custom' command handling
      strcpy(reply, "**Magic now done**");
      return true;   // handled
    }
    return false;  // not handled
  }
  /* ======================================================================= */
};

StdRNG fast_rng;
SimpleMeshTables tables;

MyMesh the_mesh(board, radio_driver, *new ArduinoMillis(), fast_rng, rtc_clock, tables);

void halt() {
  while (1) ;
}

static char command[160];
static unsigned long next_runtime_lowbat_check = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  board.begin();

#ifdef DISPLAY_CLASS
  if (display.begin()) {
    display.startFrame();
    display.print("Please wait...");
    display.endFrame();
  }
#endif

  if (!radio_init()) { halt(); }

  fast_rng.begin(radio_driver.getRngSeed());

  FILESYSTEM* fs;
#if defined(NRF52_PLATFORM) || defined(STM32_PLATFORM)
  InternalFS.begin();
  fs = &InternalFS;
  IdentityStore store(InternalFS, "");
#elif defined(ESP32)
  SPIFFS.begin(true);
  fs = &SPIFFS;
  IdentityStore store(SPIFFS, "/identity");
#elif defined(RP2040_PLATFORM)
  LittleFS.begin();
  fs = &LittleFS;
  IdentityStore store(LittleFS, "/identity");
  store.begin();
#else
  #error "need to define filesystem"
#endif
  if (!store.load("_main", the_mesh.self_id)) {
    MESH_DEBUG_PRINTLN("Generating new keypair");
    the_mesh.self_id = radio_new_identity();   // create new random identity
    int count = 0;
    while (count < 10 && (the_mesh.self_id.pub_key[0] == 0x00 || the_mesh.self_id.pub_key[0] == 0xFF)) {  // reserved id hashes
      the_mesh.self_id = radio_new_identity(); count++;
    }
    store.save("_main", the_mesh.self_id);
  }

  Serial.print("Sensor ID: ");
  mesh::Utils::printHex(Serial, the_mesh.self_id.pub_key, PUB_KEY_SIZE); Serial.println();

  command[0] = 0;

  sensors.begin();

  the_mesh.begin(fs);

#ifdef DISPLAY_CLASS
  ui_task.begin(the_mesh.getNodePrefs(), &sensors, &board, FIRMWARE_BUILD_DATE, FIRMWARE_VERSION);
#endif

  // send out initial zero hop Advertisement to the mesh
#if ENABLE_ADVERT_ON_BOOT == 1
  the_mesh.sendSelfAdvertisement(16000, false);
#endif
}

void loop() {
  int len = strlen(command);
  while (Serial.available() && len < sizeof(command)-1) {
    char c = Serial.read();
    if (c != '\n') {
      command[len++] = c;
      command[len] = 0;
    }
    Serial.print(c);
  }
  if (len == sizeof(command)-1) {  // command buffer full
    command[sizeof(command)-1] = '\r';
  }

  if (len > 0 && command[len - 1] == '\r') {  // received complete line
    command[len - 1] = 0;  // replace newline with C string null terminator
    char reply[768];
    the_mesh.handleCommand(0, command, reply);  // NOTE: there is no sender_timestamp via serial!
    if (reply[0]) {
      if (reply[0] == '{') {
        Serial.println(reply);
      } else {
        Serial.print("  -> "); Serial.println(reply);
      }
    }

    command[0] = 0;  // reset command buffer
  }

  the_mesh.loop();
  the_mesh.loopApp();
  sensors.loop();
#ifdef DISPLAY_CLASS
  ui_task.loop();
#endif
  rtc_clock.tick();

  NodePrefs* prefs = the_mesh.getNodePrefs();
  if (next_runtime_lowbat_check == 0 || the_mesh.millisHasNowPassed(next_runtime_lowbat_check)) {
    next_runtime_lowbat_check = millis() + LOW_BAT_RUNTIME_CHECK_SECS * 1000UL;
    if (guardRuntimeLowBattery(board, prefs->low_bat_runtime_guard_enabled, prefs->low_bat_runtime_guard_mv,
                               prefs->low_bat_runtime_valid_min_mv, prefs->low_bat_runtime_retry_secs)) {
      return;
    }
  }
}
