#include "SensorMesh.h"

#include <helpers/LocationReport.h>
#include <helpers/TxtDataHelpers.h>

#ifdef DISPLAY_CLASS
  #include "UITask.h"
  static UITask ui_task(display);
#endif

#ifndef LOCATION_TRACKER_INTERVAL_SECS
  #define LOCATION_TRACKER_INTERVAL_SECS 0
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
      next_location_report = futureMillis(((uint32_t)LOCATION_TRACKER_INTERVAL_SECS) * 1000);
    }
#endif
  }

protected:
  /* ========================== custom logic here ========================== */
  Trigger low_batt, critical_batt;
  TimeSeriesData  battery_data;
  unsigned long next_location_report;

#if LOCATION_TRACKER_INTERVAL_SECS > 0 && ENV_INCLUDE_GPS == 1
  void sendLocationReport() {
    LocationProvider* location = sensors.getLocationProvider();
    if (!location || !location->isEnabled() || !location->isValid()) return;

    meshcore::LocationReport report;
    memcpy(report.node_id, self_id.pub_key, sizeof(report.node_id));
    report.lat_microdeg = (int32_t)location->getLatitude();
    report.lon_microdeg = (int32_t)location->getLongitude();
    report.altitude_m = (int16_t)(location->getAltitude() / 1000);
    report.satellites = (uint8_t)min(255L, location->satellitesCount());
    report.battery_mv = (uint16_t)min(65535, (int)board.getBattMilliVolts());
    report.timestamp = (uint32_t)getRTCClock()->getCurrentTime();
    StrHelper::strncpy(report.name, getNodeName(), sizeof(report.name));

    uint8_t payload[meshcore::LOCATION_REPORT_MAX_ENCODED_LEN];
    size_t len = meshcore::encodeLocationReport(payload, sizeof(payload), report);
    if (len == 0) return;

    mesh::Packet* pkt = obtainNewPacket();
    if (!pkt) return;
    pkt->header = (PAYLOAD_TYPE_LOCATION << PH_TYPE_SHIFT);
    memcpy(pkt->payload, payload, len);
    pkt->payload_len = len;

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
  ui_task.begin(the_mesh.getNodePrefs(), FIRMWARE_BUILD_DATE, FIRMWARE_VERSION);
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
}
