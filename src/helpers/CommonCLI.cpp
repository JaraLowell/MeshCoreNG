#include <Arduino.h>
#include "CommonCLI.h"
#include "TxtDataHelpers.h"
#include "AdvertDataHelpers.h"
#include "TxtDataHelpers.h"
#include <RTClib.h>

#ifndef BRIDGE_MAX_BAUD
#define BRIDGE_MAX_BAUD 115200
#endif

#ifndef FIRMWARE_TARGET
#define FIRMWARE_TARGET "unknown"
#endif

// Believe it or not, this std C function is busted on some platforms!
static uint32_t _atoi(const char* sp) {
  uint32_t n = 0;
  while (*sp && *sp >= '0' && *sp <= '9') {
    n *= 10;
    n += (*sp++ - '0');
  }
  return n;
}

static bool isValidName(const char *n) {
  while (*n) {
    if (*n == '[' || *n == ']' || *n == '\\' || *n == ':' || *n == ',' || *n == '?' || *n == '*') return false;
    n++;
  }
  return true;
}

static bool parseOnOff(const char* value, uint8_t* dest) {
  if (strcmp(value, "on") == 0 || strcmp(value, "1") == 0 || strcmp(value, "enable") == 0 || strcmp(value, "enabled") == 0) {
    *dest = 1;
    return true;
  }
  if (strcmp(value, "off") == 0 || strcmp(value, "0") == 0 || strcmp(value, "disable") == 0 || strcmp(value, "disabled") == 0) {
    *dest = 0;
    return true;
  }
  return false;
}

void CommonCLI::loadPrefs(FILESYSTEM* fs) {
  if (fs->exists("/com_prefs")) {
    loadPrefsInt(fs, "/com_prefs");   // new filename
  } else if (fs->exists("/node_prefs")) {
    loadPrefsInt(fs, "/node_prefs");
    savePrefs(fs);  // save to new filename
    fs->remove("/node_prefs");  // remove old
  }
}

void CommonCLI::loadPrefsInt(FILESYSTEM* fs, const char* filename) {
#if defined(RP2040_PLATFORM)
  File file = fs->open(filename, "r");
#else
  File file = fs->open(filename);
#endif
  if (file) {
    uint8_t pad[8];
    size_t prefs_size = file.size();
    bool legacy_meshcoreng_v109_tail = prefs_size == 529 + sizeof(AtlasConfig);

    file.read((uint8_t *)&_prefs->airtime_factor, sizeof(_prefs->airtime_factor));    // 0
    file.read((uint8_t *)&_prefs->node_name, sizeof(_prefs->node_name));              // 4
    file.read(pad, 4);                                                                // 36
    file.read((uint8_t *)&_prefs->node_lat, sizeof(_prefs->node_lat));                // 40
    file.read((uint8_t *)&_prefs->node_lon, sizeof(_prefs->node_lon));                // 48
    file.read((uint8_t *)&_prefs->password[0], sizeof(_prefs->password));             // 56
    file.read((uint8_t *)&_prefs->freq, sizeof(_prefs->freq));                        // 72
    file.read((uint8_t *)&_prefs->tx_power_dbm, sizeof(_prefs->tx_power_dbm));        // 76
    file.read((uint8_t *)&_prefs->disable_fwd, sizeof(_prefs->disable_fwd));          // 77
    file.read((uint8_t *)&_prefs->advert_interval, sizeof(_prefs->advert_interval));  // 78
    file.read(pad, 1);                                                                // 79 : 1 byte unused (was rx_boosted_gain in v1.14.1, moved to end for upgrade compat)
    file.read((uint8_t *)&_prefs->rx_delay_base, sizeof(_prefs->rx_delay_base));      // 80
    file.read((uint8_t *)&_prefs->tx_delay_factor, sizeof(_prefs->tx_delay_factor));  // 84
    file.read((uint8_t *)&_prefs->guest_password[0], sizeof(_prefs->guest_password)); // 88
    file.read((uint8_t *)&_prefs->direct_tx_delay_factor, sizeof(_prefs->direct_tx_delay_factor)); // 104
    file.read(pad, 4); // 108 : 4 bytes unused
    file.read((uint8_t *)&_prefs->sf, sizeof(_prefs->sf));                                         // 112
    file.read((uint8_t *)&_prefs->cr, sizeof(_prefs->cr));                                         // 113
    file.read((uint8_t *)&_prefs->allow_read_only, sizeof(_prefs->allow_read_only));               // 114
    file.read((uint8_t *)&_prefs->multi_acks, sizeof(_prefs->multi_acks));                         // 115
    file.read((uint8_t *)&_prefs->bw, sizeof(_prefs->bw));                                         // 116
    file.read((uint8_t *)&_prefs->agc_reset_interval, sizeof(_prefs->agc_reset_interval));         // 120
    file.read((uint8_t *)&_prefs->path_hash_mode, sizeof(_prefs->path_hash_mode));                 // 121
    file.read((uint8_t *)&_prefs->loop_detect, sizeof(_prefs->loop_detect));                       // 122
    file.read(pad, 1);                                                                             // 123
    file.read((uint8_t *)&_prefs->flood_max, sizeof(_prefs->flood_max));                           // 124
    file.read((uint8_t *)&_prefs->flood_advert_interval, sizeof(_prefs->flood_advert_interval));   // 125
    file.read((uint8_t *)&_prefs->interference_threshold, sizeof(_prefs->interference_threshold)); // 126
    file.read((uint8_t *)&_prefs->bridge_enabled, sizeof(_prefs->bridge_enabled));                 // 127
    file.read((uint8_t *)&_prefs->bridge_delay, sizeof(_prefs->bridge_delay));                     // 128
    file.read((uint8_t *)&_prefs->bridge_pkt_src, sizeof(_prefs->bridge_pkt_src));                 // 130
    file.read((uint8_t *)&_prefs->bridge_baud, sizeof(_prefs->bridge_baud));                       // 131
    file.read((uint8_t *)&_prefs->bridge_channel, sizeof(_prefs->bridge_channel));                 // 135
    file.read((uint8_t *)&_prefs->bridge_secret, sizeof(_prefs->bridge_secret));                   // 136
    file.read((uint8_t *)&_prefs->powersaving_enabled, sizeof(_prefs->powersaving_enabled));       // 152
    file.read(pad, 3);                                                                             // 153
    file.read((uint8_t *)&_prefs->gps_enabled, sizeof(_prefs->gps_enabled));                       // 156
    file.read((uint8_t *)&_prefs->gps_interval, sizeof(_prefs->gps_interval));                     // 157
    file.read((uint8_t *)&_prefs->advert_loc_policy, sizeof (_prefs->advert_loc_policy));          // 161
    file.read((uint8_t *)&_prefs->discovery_mod_timestamp, sizeof(_prefs->discovery_mod_timestamp)); // 162
    file.read((uint8_t *)&_prefs->adc_multiplier, sizeof(_prefs->adc_multiplier));                 // 166
    file.read((uint8_t *)_prefs->owner_info, sizeof(_prefs->owner_info));                          // 170
    file.read((uint8_t *)&_prefs->rx_boosted_gain, sizeof(_prefs->rx_boosted_gain));              // 290
    float default_flood_advert_base = _prefs->flood_advert_base;

    if (legacy_meshcoreng_v109_tail) {
      float flood_advert_base = default_flood_advert_base;
      if (file.read((uint8_t *)&flood_advert_base, sizeof(flood_advert_base)) == sizeof(flood_advert_base)) {
        _prefs->flood_advert_base = flood_advert_base;                                             // 291 legacy MeshCoreNG <= bridge-tcp-v1.0.9
      }
      uint8_t flood_relay_prob = _prefs->flood_relay_prob;
      if (file.read((uint8_t *)&flood_relay_prob, sizeof(flood_relay_prob)) == sizeof(flood_relay_prob)) {
        _prefs->flood_relay_prob = flood_relay_prob;                                               // 295 legacy
      }
      uint8_t flood_dynamic_enable = _prefs->flood_dynamic_enable;
      if (file.read((uint8_t *)&flood_dynamic_enable, sizeof(flood_dynamic_enable)) == sizeof(flood_dynamic_enable)) {
        _prefs->flood_dynamic_enable = flood_dynamic_enable;                                       // 296 legacy
      }
      char wifi_ssid[32] = {};
      if (file.read((uint8_t *)wifi_ssid, sizeof(wifi_ssid)) == sizeof(wifi_ssid)) {
        memcpy(_prefs->wifi_ssid, wifi_ssid, sizeof(wifi_ssid));                                   // 297 legacy
      }
      char wifi_password[64] = {};
      if (file.read((uint8_t *)wifi_password, sizeof(wifi_password)) == sizeof(wifi_password)) {
        memcpy(_prefs->wifi_password, wifi_password, sizeof(wifi_password));                       // 329 legacy
      }
      char bridge_server[64] = {};
      if (file.read((uint8_t *)bridge_server, sizeof(bridge_server)) == sizeof(bridge_server)) {
        memcpy(_prefs->bridge_server, bridge_server, sizeof(bridge_server));                       // 393 legacy
      }
      uint16_t bridge_port = _prefs->bridge_port;
      if (file.read((uint8_t *)&bridge_port, sizeof(bridge_port)) == sizeof(bridge_port)) {
        _prefs->bridge_port = bridge_port;                                                         // 457 legacy
      }
      uint8_t malformed_drop = _prefs->malformed_drop;
      if (file.read((uint8_t *)&malformed_drop, sizeof(malformed_drop)) == sizeof(malformed_drop)) {
        _prefs->malformed_drop = malformed_drop;                                                   // 459 legacy
      }
      uint8_t flood_node_delay_enable = _prefs->flood_node_delay_enable;
      if (file.read((uint8_t *)&flood_node_delay_enable, sizeof(flood_node_delay_enable)) == sizeof(flood_node_delay_enable)) {
        _prefs->flood_node_delay_enable = flood_node_delay_enable;                                 // 460 legacy
      }
      uint8_t flood_dup_suppress_enable = _prefs->flood_dup_suppress_enable;
      if (file.read((uint8_t *)&flood_dup_suppress_enable, sizeof(flood_dup_suppress_enable)) == sizeof(flood_dup_suppress_enable)) {
        _prefs->flood_dup_suppress_enable = flood_dup_suppress_enable;                             // 461 legacy
      }
      AtlasConfig atlas = _prefs->atlas;
      if (file.read((uint8_t *)&atlas, sizeof(atlas)) == sizeof(atlas)) {
        _prefs->atlas = atlas;                                                                     // 462 legacy
      }
      uint8_t daily_reboot_enabled = _prefs->daily_reboot_enabled;
      if (file.read((uint8_t *)&daily_reboot_enabled, sizeof(daily_reboot_enabled)) == sizeof(daily_reboot_enabled)) {
        _prefs->daily_reboot_enabled = daily_reboot_enabled;                                       // 462 + sizeof(AtlasConfig) legacy
      }
      uint8_t daily_reboot_interval_hours = _prefs->daily_reboot_interval_hours;
      if (file.read((uint8_t *)&daily_reboot_interval_hours, sizeof(daily_reboot_interval_hours)) == sizeof(daily_reboot_interval_hours)) {
        _prefs->daily_reboot_interval_hours = daily_reboot_interval_hours;                         // 463 + sizeof(AtlasConfig) legacy
      }
      uint8_t bridge_rf = _prefs->bridge_rf;
      if (file.read((uint8_t *)&bridge_rf, sizeof(bridge_rf)) == sizeof(bridge_rf)) {
        _prefs->bridge_rf = bridge_rf;                                                             // 464 + sizeof(AtlasConfig) legacy
      }
      char bridge_password[64] = {};
      if (file.read((uint8_t *)bridge_password, sizeof(bridge_password)) == sizeof(bridge_password)) {
        memcpy(_prefs->bridge_password, bridge_password, sizeof(bridge_password));                  // 465 + sizeof(AtlasConfig) legacy
      }
    } else {
      uint8_t flood_max_unscoped = _prefs->flood_max_unscoped;
      if (file.read((uint8_t *)&flood_max_unscoped, sizeof(flood_max_unscoped)) == sizeof(flood_max_unscoped)) {
        _prefs->flood_max_unscoped = flood_max_unscoped;                                           // 291
      }
      uint8_t flood_max_advert = _prefs->flood_max_advert;
      if (file.read((uint8_t *)&flood_max_advert, sizeof(flood_max_advert)) == sizeof(flood_max_advert)) {
        _prefs->flood_max_advert = flood_max_advert;                                               // 292
      }
      float flood_advert_base = default_flood_advert_base;
      if (file.read((uint8_t *)&flood_advert_base, sizeof(flood_advert_base)) == sizeof(flood_advert_base)) {
        _prefs->flood_advert_base = flood_advert_base;                                             // 293
      }
      uint8_t flood_relay_prob = _prefs->flood_relay_prob;
      if (file.read((uint8_t *)&flood_relay_prob, sizeof(flood_relay_prob)) == sizeof(flood_relay_prob)) {
        _prefs->flood_relay_prob = flood_relay_prob;                                               // 297
      }
      uint8_t flood_dynamic_enable = _prefs->flood_dynamic_enable;
      if (file.read((uint8_t *)&flood_dynamic_enable, sizeof(flood_dynamic_enable)) == sizeof(flood_dynamic_enable)) {
        _prefs->flood_dynamic_enable = flood_dynamic_enable;                                       // 298
      }
      char wifi_ssid[32] = {};
      if (file.read((uint8_t *)wifi_ssid, sizeof(wifi_ssid)) == sizeof(wifi_ssid)) {
        memcpy(_prefs->wifi_ssid, wifi_ssid, sizeof(wifi_ssid));                                   // 299
      }
      char wifi_password[64] = {};
      if (file.read((uint8_t *)wifi_password, sizeof(wifi_password)) == sizeof(wifi_password)) {
        memcpy(_prefs->wifi_password, wifi_password, sizeof(wifi_password));                       // 331
      }
      char bridge_server[64] = {};
      if (file.read((uint8_t *)bridge_server, sizeof(bridge_server)) == sizeof(bridge_server)) {
        memcpy(_prefs->bridge_server, bridge_server, sizeof(bridge_server));                       // 395
      }
      uint16_t bridge_port = _prefs->bridge_port;
      if (file.read((uint8_t *)&bridge_port, sizeof(bridge_port)) == sizeof(bridge_port)) {
        _prefs->bridge_port = bridge_port;                                                         // 459
      }
      uint8_t malformed_drop = _prefs->malformed_drop;
      if (file.read((uint8_t *)&malformed_drop, sizeof(malformed_drop)) == sizeof(malformed_drop)) {
        _prefs->malformed_drop = malformed_drop;                                                   // 461
      }
      uint8_t flood_node_delay_enable = _prefs->flood_node_delay_enable;
      if (file.read((uint8_t *)&flood_node_delay_enable, sizeof(flood_node_delay_enable)) == sizeof(flood_node_delay_enable)) {
        _prefs->flood_node_delay_enable = flood_node_delay_enable;                                 // 462
      }
      uint8_t flood_dup_suppress_enable = _prefs->flood_dup_suppress_enable;
      if (file.read((uint8_t *)&flood_dup_suppress_enable, sizeof(flood_dup_suppress_enable)) == sizeof(flood_dup_suppress_enable)) {
        _prefs->flood_dup_suppress_enable = flood_dup_suppress_enable;                             // 463
      }
      AtlasConfig atlas = _prefs->atlas;
      if (file.read((uint8_t *)&atlas, sizeof(atlas)) == sizeof(atlas)) {
        _prefs->atlas = atlas;                                                                     // 464
      }
      uint8_t daily_reboot_enabled = _prefs->daily_reboot_enabled;
      if (file.read((uint8_t *)&daily_reboot_enabled, sizeof(daily_reboot_enabled)) == sizeof(daily_reboot_enabled)) {
        _prefs->daily_reboot_enabled = daily_reboot_enabled;                                       // 464 + sizeof(AtlasConfig)
      }
      uint8_t daily_reboot_interval_hours = _prefs->daily_reboot_interval_hours;
      if (file.read((uint8_t *)&daily_reboot_interval_hours, sizeof(daily_reboot_interval_hours)) == sizeof(daily_reboot_interval_hours)) {
        _prefs->daily_reboot_interval_hours = daily_reboot_interval_hours;                         // 465 + sizeof(AtlasConfig)
      }
      uint8_t bridge_rf = _prefs->bridge_rf;
      if (file.read((uint8_t *)&bridge_rf, sizeof(bridge_rf)) == sizeof(bridge_rf)) {
        _prefs->bridge_rf = bridge_rf;                                                             // 466 + sizeof(AtlasConfig)
      }
      char bridge_password[64] = {};
      if (file.read((uint8_t *)bridge_password, sizeof(bridge_password)) == sizeof(bridge_password)) {
        memcpy(_prefs->bridge_password, bridge_password, sizeof(bridge_password));                  // 467 + sizeof(AtlasConfig)
      }
      uint8_t fem_rx_gain = _prefs->fem_rx_gain;
      if (file.read((uint8_t *)&fem_rx_gain, sizeof(fem_rx_gain)) == sizeof(fem_rx_gain)) {
        _prefs->fem_rx_gain = fem_rx_gain;                                                         // 531 + sizeof(AtlasConfig)
      }
      uint8_t low_bat_boot_guard_enabled = _prefs->low_bat_boot_guard_enabled;
      if (file.read((uint8_t *)&low_bat_boot_guard_enabled, sizeof(low_bat_boot_guard_enabled)) == sizeof(low_bat_boot_guard_enabled)) {
        _prefs->low_bat_boot_guard_enabled = low_bat_boot_guard_enabled;                           // 532 + sizeof(AtlasConfig)
      }
      uint16_t low_bat_boot_guard_mv = _prefs->low_bat_boot_guard_mv;
      if (file.read((uint8_t *)&low_bat_boot_guard_mv, sizeof(low_bat_boot_guard_mv)) == sizeof(low_bat_boot_guard_mv)) {
        _prefs->low_bat_boot_guard_mv = low_bat_boot_guard_mv;                                     // 533 + sizeof(AtlasConfig)
      }
      uint16_t low_bat_boot_valid_min_mv = _prefs->low_bat_boot_valid_min_mv;
      if (file.read((uint8_t *)&low_bat_boot_valid_min_mv, sizeof(low_bat_boot_valid_min_mv)) == sizeof(low_bat_boot_valid_min_mv)) {
        _prefs->low_bat_boot_valid_min_mv = low_bat_boot_valid_min_mv;                             // 535 + sizeof(AtlasConfig)
      }
      uint16_t low_bat_boot_retry_secs = _prefs->low_bat_boot_retry_secs;
      if (file.read((uint8_t *)&low_bat_boot_retry_secs, sizeof(low_bat_boot_retry_secs)) == sizeof(low_bat_boot_retry_secs)) {
        _prefs->low_bat_boot_retry_secs = low_bat_boot_retry_secs;                                 // 537 + sizeof(AtlasConfig)
      }
      char ntp_server[64] = {};
      if (file.read((uint8_t *)ntp_server, sizeof(ntp_server)) == sizeof(ntp_server)) {
        memcpy(_prefs->ntp_server, ntp_server, sizeof(ntp_server));                                 // 539 + sizeof(AtlasConfig)
      }
      uint8_t ntp_enabled = _prefs->ntp_enabled;
      if (file.read((uint8_t *)&ntp_enabled, sizeof(ntp_enabled)) == sizeof(ntp_enabled)) {
        _prefs->ntp_enabled = ntp_enabled;                                                         // 603 + sizeof(AtlasConfig)
      }
      uint32_t ntp_interval_secs = _prefs->ntp_interval_secs;
      if (file.read((uint8_t *)&ntp_interval_secs, sizeof(ntp_interval_secs)) == sizeof(ntp_interval_secs)) {
        _prefs->ntp_interval_secs = ntp_interval_secs;                                             // 604 + sizeof(AtlasConfig)
      }
      uint8_t low_bat_runtime_guard_enabled = _prefs->low_bat_runtime_guard_enabled;
      if (file.read((uint8_t *)&low_bat_runtime_guard_enabled, sizeof(low_bat_runtime_guard_enabled)) == sizeof(low_bat_runtime_guard_enabled)) {
        _prefs->low_bat_runtime_guard_enabled = low_bat_runtime_guard_enabled;                      // 608 + sizeof(AtlasConfig)
      }
      uint16_t low_bat_runtime_guard_mv = _prefs->low_bat_runtime_guard_mv;
      if (file.read((uint8_t *)&low_bat_runtime_guard_mv, sizeof(low_bat_runtime_guard_mv)) == sizeof(low_bat_runtime_guard_mv)) {
        _prefs->low_bat_runtime_guard_mv = low_bat_runtime_guard_mv;                                // 609 + sizeof(AtlasConfig)
      }
      uint16_t low_bat_runtime_warn_mv = _prefs->low_bat_runtime_warn_mv;
      if (file.read((uint8_t *)&low_bat_runtime_warn_mv, sizeof(low_bat_runtime_warn_mv)) == sizeof(low_bat_runtime_warn_mv)) {
        _prefs->low_bat_runtime_warn_mv = low_bat_runtime_warn_mv;                                  // 611 + sizeof(AtlasConfig)
      }
      uint16_t low_bat_runtime_valid_min_mv = _prefs->low_bat_runtime_valid_min_mv;
      if (file.read((uint8_t *)&low_bat_runtime_valid_min_mv, sizeof(low_bat_runtime_valid_min_mv)) == sizeof(low_bat_runtime_valid_min_mv)) {
        _prefs->low_bat_runtime_valid_min_mv = low_bat_runtime_valid_min_mv;                        // 613 + sizeof(AtlasConfig)
      }
      uint32_t low_bat_runtime_retry_secs = _prefs->low_bat_runtime_retry_secs;
      if (file.read((uint8_t *)&low_bat_runtime_retry_secs, sizeof(low_bat_runtime_retry_secs)) == sizeof(low_bat_runtime_retry_secs)) {
        _prefs->low_bat_runtime_retry_secs = low_bat_runtime_retry_secs;                            // 615 + sizeof(AtlasConfig)
      }
    }
    // next: 619 + sizeof(AtlasConfig)

    // sanitise bad pref values
    _prefs->rx_delay_base = constrain(_prefs->rx_delay_base, 0, 20.0f);
    _prefs->tx_delay_factor = constrain(_prefs->tx_delay_factor, 0, 2.0f);
    _prefs->direct_tx_delay_factor = constrain(_prefs->direct_tx_delay_factor, 0, 2.0f);
    _prefs->airtime_factor = constrain(_prefs->airtime_factor, 0, 9.0f);
    _prefs->freq = constrain(_prefs->freq, 150.0f, 2500.0f);
    _prefs->bw = constrain(_prefs->bw, 7.8f, 500.0f);
    _prefs->sf = constrain(_prefs->sf, 5, 12);
    _prefs->cr = constrain(_prefs->cr, 5, 8);
    _prefs->tx_power_dbm = constrain(_prefs->tx_power_dbm, -9, 30);
    _prefs->multi_acks = constrain(_prefs->multi_acks, 0, 1);
    _prefs->adc_multiplier = constrain(_prefs->adc_multiplier, 0.0f, 10.0f);
    _prefs->path_hash_mode = constrain(_prefs->path_hash_mode, 0, 2);   // NOTE: mode 3 reserved for future

    // sanitise bad bridge pref values
    _prefs->bridge_enabled = constrain(_prefs->bridge_enabled, 0, 1);
    _prefs->bridge_delay = constrain(_prefs->bridge_delay, 0, 10000);
    _prefs->bridge_pkt_src = constrain(_prefs->bridge_pkt_src, 0, 2);
    _prefs->bridge_rf = constrain(_prefs->bridge_rf, 0, 2);
    _prefs->bridge_baud = constrain(_prefs->bridge_baud, 9600, BRIDGE_MAX_BAUD);
    _prefs->bridge_channel = constrain(_prefs->bridge_channel, 0, 14);
    if (_prefs->bridge_port == 0) _prefs->bridge_port = 4200;

    _prefs->powersaving_enabled = constrain(_prefs->powersaving_enabled, 0, 1);
    _prefs->malformed_drop = constrain(_prefs->malformed_drop, 0, 1);
    _prefs->fem_rx_gain = constrain(_prefs->fem_rx_gain, 0, 1);
    _prefs->low_bat_boot_guard_enabled = constrain(_prefs->low_bat_boot_guard_enabled, 0, 1);
    _prefs->low_bat_boot_guard_mv = constrain(_prefs->low_bat_boot_guard_mv, 0, 6000);
    _prefs->low_bat_boot_valid_min_mv = constrain(_prefs->low_bat_boot_valid_min_mv, 0, 6000);
    _prefs->low_bat_boot_retry_secs = constrain(_prefs->low_bat_boot_retry_secs, 5, 3600);
    if (_prefs->ntp_server[0] == 0) {
      StrHelper::strncpy(_prefs->ntp_server, "pool.ntp.org", sizeof(_prefs->ntp_server));
    }
    _prefs->ntp_enabled = constrain(_prefs->ntp_enabled, 0, 1);
    _prefs->ntp_interval_secs = constrain(_prefs->ntp_interval_secs, 60UL, 86400UL);
    _prefs->low_bat_runtime_guard_enabled = constrain(_prefs->low_bat_runtime_guard_enabled, 0, 1);
    _prefs->low_bat_runtime_guard_mv = constrain(_prefs->low_bat_runtime_guard_mv, 0, 6000);
    _prefs->low_bat_runtime_warn_mv = constrain(_prefs->low_bat_runtime_warn_mv, 0, 6000);
    _prefs->low_bat_runtime_valid_min_mv = constrain(_prefs->low_bat_runtime_valid_min_mv, 0, 6000);
    _prefs->low_bat_runtime_retry_secs = constrain(_prefs->low_bat_runtime_retry_secs, 5UL, 86400UL);

    _prefs->gps_enabled = constrain(_prefs->gps_enabled, 0, 1);
    _prefs->advert_loc_policy = constrain(_prefs->advert_loc_policy, 0, 2);

    // sanitise settings
    _prefs->rx_boosted_gain = constrain(_prefs->rx_boosted_gain, 0, 1); // boolean
    if (!(_prefs->flood_advert_base >= 0.0f && _prefs->flood_advert_base <= 1.0f)) {
      _prefs->flood_advert_base = default_flood_advert_base;
    }
    _prefs->flood_dynamic_enable = constrain(_prefs->flood_dynamic_enable, 0, 1);
    _prefs->flood_node_delay_enable = constrain(_prefs->flood_node_delay_enable, 0, 1);
    _prefs->flood_dup_suppress_enable = constrain(_prefs->flood_dup_suppress_enable, 0, 1);
    _prefs->atlas.enabled = constrain(_prefs->atlas.enabled, 0, 1);
    _prefs->atlas.position_enabled = constrain(_prefs->atlas.position_enabled, 0, 1);
    _prefs->atlas.neighbors_enabled = constrain(_prefs->atlas.neighbors_enabled, 0, 1);
    _prefs->atlas.path_sample_enabled = constrain(_prefs->atlas.path_sample_enabled, 0, 1);
    _prefs->atlas.export_enabled = constrain(_prefs->atlas.export_enabled, 0, 1);
    _prefs->atlas.path_sample_percent = constrain(_prefs->atlas.path_sample_percent, 0, 10);
    _prefs->daily_reboot_enabled = constrain(_prefs->daily_reboot_enabled, 0, 1);
    if (_prefs->daily_reboot_interval_hours == 0) _prefs->daily_reboot_interval_hours = 24;
    _prefs->daily_reboot_interval_hours = constrain(_prefs->daily_reboot_interval_hours, 1, 168);

    file.close();
  }
}

void CommonCLI::savePrefs(FILESYSTEM* fs) {
#if defined(NRF52_PLATFORM) || defined(STM32_PLATFORM)
  fs->remove("/com_prefs");
  File file = fs->open("/com_prefs", FILE_O_WRITE);
#elif defined(RP2040_PLATFORM)
  File file = fs->open("/com_prefs", "w");
#else
  File file = fs->open("/com_prefs", "w", true);
#endif
  if (file) {
    uint8_t pad[8];
    memset(pad, 0, sizeof(pad));

    file.write((uint8_t *)&_prefs->airtime_factor, sizeof(_prefs->airtime_factor));    // 0
    file.write((uint8_t *)&_prefs->node_name, sizeof(_prefs->node_name));              // 4
    file.write(pad, 4);                                                                // 36
    file.write((uint8_t *)&_prefs->node_lat, sizeof(_prefs->node_lat));                // 40
    file.write((uint8_t *)&_prefs->node_lon, sizeof(_prefs->node_lon));                // 48
    file.write((uint8_t *)&_prefs->password[0], sizeof(_prefs->password));             // 56
    file.write((uint8_t *)&_prefs->freq, sizeof(_prefs->freq));                        // 72
    file.write((uint8_t *)&_prefs->tx_power_dbm, sizeof(_prefs->tx_power_dbm));        // 76
    file.write((uint8_t *)&_prefs->disable_fwd, sizeof(_prefs->disable_fwd));          // 77
    file.write((uint8_t *)&_prefs->advert_interval, sizeof(_prefs->advert_interval));  // 78
    file.write(pad, 1);                                                                // 79 : 1 byte unused (rx_boosted_gain moved to end)
    file.write((uint8_t *)&_prefs->rx_delay_base, sizeof(_prefs->rx_delay_base));      // 80
    file.write((uint8_t *)&_prefs->tx_delay_factor, sizeof(_prefs->tx_delay_factor));  // 84
    file.write((uint8_t *)&_prefs->guest_password[0], sizeof(_prefs->guest_password)); // 88
    file.write((uint8_t *)&_prefs->direct_tx_delay_factor, sizeof(_prefs->direct_tx_delay_factor)); // 104
    file.write(pad, 4); // 108 : 4 byte unused
    file.write((uint8_t *)&_prefs->sf, sizeof(_prefs->sf));                                         // 112
    file.write((uint8_t *)&_prefs->cr, sizeof(_prefs->cr));                                         // 113
    file.write((uint8_t *)&_prefs->allow_read_only, sizeof(_prefs->allow_read_only));               // 114
    file.write((uint8_t *)&_prefs->multi_acks, sizeof(_prefs->multi_acks));                         // 115
    file.write((uint8_t *)&_prefs->bw, sizeof(_prefs->bw));                                         // 116
    file.write((uint8_t *)&_prefs->agc_reset_interval, sizeof(_prefs->agc_reset_interval));         // 120
    file.write((uint8_t *)&_prefs->path_hash_mode, sizeof(_prefs->path_hash_mode));                 // 121
    file.write((uint8_t *)&_prefs->loop_detect, sizeof(_prefs->loop_detect));                       // 122
    file.write(pad, 1);                                                                             // 123
    file.write((uint8_t *)&_prefs->flood_max, sizeof(_prefs->flood_max));                           // 124
    file.write((uint8_t *)&_prefs->flood_advert_interval, sizeof(_prefs->flood_advert_interval));   // 125
    file.write((uint8_t *)&_prefs->interference_threshold, sizeof(_prefs->interference_threshold)); // 126
    file.write((uint8_t *)&_prefs->bridge_enabled, sizeof(_prefs->bridge_enabled));                 // 127
    file.write((uint8_t *)&_prefs->bridge_delay, sizeof(_prefs->bridge_delay));                     // 128
    file.write((uint8_t *)&_prefs->bridge_pkt_src, sizeof(_prefs->bridge_pkt_src));                 // 130
    file.write((uint8_t *)&_prefs->bridge_baud, sizeof(_prefs->bridge_baud));                       // 131
    file.write((uint8_t *)&_prefs->bridge_channel, sizeof(_prefs->bridge_channel));                 // 135
    file.write((uint8_t *)&_prefs->bridge_secret, sizeof(_prefs->bridge_secret));                   // 136
    file.write((uint8_t *)&_prefs->powersaving_enabled, sizeof(_prefs->powersaving_enabled));       // 152
    file.write(pad, 3);                                                                             // 153
    file.write((uint8_t *)&_prefs->gps_enabled, sizeof(_prefs->gps_enabled));                       // 156
    file.write((uint8_t *)&_prefs->gps_interval, sizeof(_prefs->gps_interval));                     // 157
    file.write((uint8_t *)&_prefs->advert_loc_policy, sizeof(_prefs->advert_loc_policy));           // 161
    file.write((uint8_t *)&_prefs->discovery_mod_timestamp, sizeof(_prefs->discovery_mod_timestamp)); // 162
    file.write((uint8_t *)&_prefs->adc_multiplier, sizeof(_prefs->adc_multiplier));                 // 166
    file.write((uint8_t *)_prefs->owner_info, sizeof(_prefs->owner_info));                          // 170
    file.write((uint8_t *)&_prefs->rx_boosted_gain, sizeof(_prefs->rx_boosted_gain));              // 290
    file.write((uint8_t *)&_prefs->flood_max_unscoped, sizeof(_prefs->flood_max_unscoped));        // 291
    file.write((uint8_t *)&_prefs->flood_max_advert, sizeof(_prefs->flood_max_advert));            // 292
    file.write((uint8_t *)&_prefs->flood_advert_base, sizeof(_prefs->flood_advert_base));          // 293
    file.write((uint8_t *)&_prefs->flood_relay_prob, sizeof(_prefs->flood_relay_prob));            // 297
    file.write((uint8_t *)&_prefs->flood_dynamic_enable, sizeof(_prefs->flood_dynamic_enable));    // 298
    file.write((uint8_t *)&_prefs->wifi_ssid, sizeof(_prefs->wifi_ssid));                          // 299
    file.write((uint8_t *)&_prefs->wifi_password, sizeof(_prefs->wifi_password));                  // 331
    file.write((uint8_t *)&_prefs->bridge_server, sizeof(_prefs->bridge_server));                  // 395
    file.write((uint8_t *)&_prefs->bridge_port, sizeof(_prefs->bridge_port));                      // 459
    file.write((uint8_t *)&_prefs->malformed_drop, sizeof(_prefs->malformed_drop));                // 461
    file.write((uint8_t *)&_prefs->flood_node_delay_enable, sizeof(_prefs->flood_node_delay_enable)); // 462
    file.write((uint8_t *)&_prefs->flood_dup_suppress_enable, sizeof(_prefs->flood_dup_suppress_enable)); // 463
    file.write((uint8_t *)&_prefs->atlas, sizeof(_prefs->atlas));                                  // 464
    file.write((uint8_t *)&_prefs->daily_reboot_enabled, sizeof(_prefs->daily_reboot_enabled));    // 464 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->daily_reboot_interval_hours, sizeof(_prefs->daily_reboot_interval_hours)); // 465 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->bridge_rf, sizeof(_prefs->bridge_rf));                          // 466 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->bridge_password, sizeof(_prefs->bridge_password));              // 467 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->fem_rx_gain, sizeof(_prefs->fem_rx_gain));                      // 531 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->low_bat_boot_guard_enabled, sizeof(_prefs->low_bat_boot_guard_enabled)); // 532 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->low_bat_boot_guard_mv, sizeof(_prefs->low_bat_boot_guard_mv));  // 533 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->low_bat_boot_valid_min_mv, sizeof(_prefs->low_bat_boot_valid_min_mv)); // 535 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->low_bat_boot_retry_secs, sizeof(_prefs->low_bat_boot_retry_secs)); // 537 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->ntp_server, sizeof(_prefs->ntp_server));                        // 539 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->ntp_enabled, sizeof(_prefs->ntp_enabled));                      // 603 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->ntp_interval_secs, sizeof(_prefs->ntp_interval_secs));          // 604 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->low_bat_runtime_guard_enabled, sizeof(_prefs->low_bat_runtime_guard_enabled)); // 608 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->low_bat_runtime_guard_mv, sizeof(_prefs->low_bat_runtime_guard_mv)); // 609 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->low_bat_runtime_warn_mv, sizeof(_prefs->low_bat_runtime_warn_mv)); // 611 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->low_bat_runtime_valid_min_mv, sizeof(_prefs->low_bat_runtime_valid_min_mv)); // 613 + sizeof(AtlasConfig)
    file.write((uint8_t *)&_prefs->low_bat_runtime_retry_secs, sizeof(_prefs->low_bat_runtime_retry_secs)); // 615 + sizeof(AtlasConfig)
    // next: 619 + sizeof(AtlasConfig)

    file.close();
  }
}

#define MIN_LOCAL_ADVERT_INTERVAL   60

void CommonCLI::savePrefs() {
  if (_prefs->advert_interval * 2 < MIN_LOCAL_ADVERT_INTERVAL) {
    _prefs->advert_interval = 0;  // turn it off, now that device has been manually configured
  }
  _callbacks->savePrefs();
}

uint8_t CommonCLI::buildAdvertData(uint8_t node_type, uint8_t* app_data) {
  if (_prefs->advert_loc_policy == ADVERT_LOC_NONE) {
    AdvertDataBuilder builder(node_type, _prefs->node_name);
    return builder.encodeTo(app_data);
  } else if (_prefs->advert_loc_policy == ADVERT_LOC_SHARE) {
    AdvertDataBuilder builder(node_type, _prefs->node_name, _sensors->node_lat, _sensors->node_lon);
    return builder.encodeTo(app_data);
  } else {
    AdvertDataBuilder builder(node_type, _prefs->node_name, _prefs->node_lat, _prefs->node_lon);
    return builder.encodeTo(app_data);
  }
}

void CommonCLI::handleCommand(uint32_t sender_timestamp, char* command, char* reply) {
    if (memcmp(command, "poweroff", 8) == 0 || memcmp(command, "shutdown", 8) == 0) {
      _board->powerOff();  // doesn't return
    } else if (memcmp(command, "reboot", 6) == 0) {
      _board->reboot();  // doesn't return
    } else if (memcmp(command, "clkreboot", 9) == 0) {
      // Reset clock
      getRTCClock()->setCurrentTime(1715770351);  // 15 May 2024, 8:50pm
      _board->reboot();  // doesn't return
     } else if (memcmp(command, "advert.zerohop", 14) == 0 && (command[14] == 0 || command[14] == ' ')) {
      // send zerohop advert
      _callbacks->sendSelfAdvertisement(1500, false);  // longer delay, give CLI response time to be sent first
      strcpy(reply, "OK - zerohop advert sent");
    } else if (memcmp(command, "advert", 6) == 0) {
      // send flood advert
      _callbacks->sendSelfAdvertisement(1500, true);  // longer delay, give CLI response time to be sent first
      strcpy(reply, "OK - Advert sent");
    } else if (memcmp(command, "clock sync", 10) == 0) {
      uint32_t curr = getRTCClock()->getCurrentTime();
      if (sender_timestamp > curr) {
        getRTCClock()->setCurrentTime(sender_timestamp + 1);
        uint32_t now = getRTCClock()->getCurrentTime();
        DateTime dt = DateTime(now);
        sprintf(reply, "OK - clock set: %02d:%02d - %d/%d/%d UTC", dt.hour(), dt.minute(), dt.day(), dt.month(), dt.year());
      } else {
        strcpy(reply, "ERR: clock cannot go backwards");
      }
    } else if (memcmp(command, "ntp.sync", 8) == 0 && (command[8] == 0 || command[8] == ' ')) {
      _callbacks->startNtpSync(reply);
    } else if (memcmp(command, "start ota", 9) == 0) {
      if (!_board->startOTAUpdate(_prefs->node_name, reply)) {
        if (reply[0] == 0) strcpy(reply, "Error");
      }
    } else if (memcmp(command, "ota.check", 9) == 0) {
      if (!_board->checkOnlineOTAUpdate(FIRMWARE_TARGET, _callbacks->getFirmwareVer(), _prefs->wifi_ssid, _prefs->wifi_password, reply)) {
        if (reply[0] == 0) strcpy(reply, "Error");
      }
    } else if (memcmp(command, "ota.update", 10) == 0) {
      if (!_board->startOnlineOTAUpdate(FIRMWARE_TARGET, _callbacks->getFirmwareVer(), _prefs->wifi_ssid, _prefs->wifi_password, reply)) {
        if (reply[0] == 0) strcpy(reply, "Error");
      }
    } else if (memcmp(command, "clock", 5) == 0) {
      uint32_t now = getRTCClock()->getCurrentTime();
      DateTime dt = DateTime(now);
      sprintf(reply, "%02d:%02d - %d/%d/%d UTC", dt.hour(), dt.minute(), dt.day(), dt.month(), dt.year());
    } else if (memcmp(command, "time ", 5) == 0) {  // set time (to epoch seconds)
      uint32_t secs = _atoi(&command[5]);
      uint32_t curr = getRTCClock()->getCurrentTime();
      if (secs > curr) {
        getRTCClock()->setCurrentTime(secs);
        uint32_t now = getRTCClock()->getCurrentTime();
        DateTime dt = DateTime(now);
        sprintf(reply, "OK - clock set: %02d:%02d - %d/%d/%d UTC", dt.hour(), dt.minute(), dt.day(), dt.month(), dt.year());
      } else {
        strcpy(reply, "(ERR: clock cannot go backwards)");
      }
    } else if (memcmp(command, "neighbors", 9) == 0) {
      _callbacks->formatNeighborsReply(reply);
    } else if (memcmp(command, "neighbor.remove ", 16) == 0) {
      const char* hex = &command[16];
      uint8_t pubkey[PUB_KEY_SIZE];
      int hex_len = min((int)strlen(hex), PUB_KEY_SIZE*2);
      int pubkey_len = hex_len / 2;
      if (mesh::Utils::fromHex(pubkey, pubkey_len, hex)) {
        _callbacks->removeNeighbor(pubkey, pubkey_len);
        strcpy(reply, "OK");
      } else {
        strcpy(reply, "ERR: bad pubkey");
      }
    } else if (memcmp(command, "tempradio ", 10) == 0) {
      strcpy(tmp, &command[10]);
      const char *parts[5];
      int num = mesh::Utils::parseTextParts(tmp, parts, 5);
      float freq  = num > 0 ? strtof(parts[0], nullptr) : 0.0f;
      float bw    = num > 1 ? strtof(parts[1], nullptr) : 0.0f;
      uint8_t sf  = num > 2 ? atoi(parts[2]) : 0;
      uint8_t cr  = num > 3 ? atoi(parts[3]) : 0;
      int temp_timeout_mins  = num > 4 ? atoi(parts[4]) : 0;
      if (freq >= 150.0f && freq <= 2500.0f && sf >= 5 && sf <= 12 && cr >= 5 && cr <= 8 && bw >= 7.0f && bw <= 500.0f && temp_timeout_mins > 0) {
        _callbacks->applyTempRadioParams(freq, bw, sf, cr, temp_timeout_mins);
        sprintf(reply, "OK - temp params for %d mins", temp_timeout_mins);
      } else {
        strcpy(reply, "Error, invalid params");
      }
    } else if (memcmp(command, "password ", 9) == 0) {
      // change admin password
      StrHelper::strncpy(_prefs->password, &command[9], sizeof(_prefs->password));
      savePrefs();
      sprintf(reply, "password now: ");
      StrHelper::strncpy(&reply[14], _prefs->password, 160-15);   // echo back just to let admin know for sure!!
    } else if (memcmp(command, "clear dense.stats", 17) == 0) {
      _callbacks->clearDenseStats();
      strcpy(reply, "(OK - dense stats reset)");
    } else if (memcmp(command, "clear spam.stats", 16) == 0) {
      _callbacks->clearSpamStats();
      strcpy(reply, "(OK - spam stats reset)");
    } else if (memcmp(command, "clear power.stats", 17) == 0) {
      _callbacks->clearPowerStats();
      strcpy(reply, "(OK - power stats reset)");
    } else if (memcmp(command, "clear stats", 11) == 0) {
      _callbacks->clearStats();
      strcpy(reply, "(OK - stats reset)");
    } else if (memcmp(command, "observer export json", 20) == 0) {
      if (sender_timestamp != 0) {
        strcpy(reply, "Error: observer export is serial-only");
      } else if (_prefs->atlas.export_enabled) {
        _callbacks->formatAtlasObserverReply(reply);
      } else {
        reply[0] = 0;
      }
    } else if (memcmp(command, "atlas ", 6) == 0) {
      const char* config = &command[6];
      if (memcmp(config, "enable ", 7) == 0) {
        if (parseOnOff(&config[7], &_prefs->atlas.enabled)) {
          savePrefs();
          strcpy(reply, "OK");
        } else {
          strcpy(reply, "Error: expected on or off");
        }
      } else if (memcmp(config, "position ", 9) == 0) {
        if (parseOnOff(&config[9], &_prefs->atlas.position_enabled)) {
          savePrefs();
          strcpy(reply, "OK");
        } else {
          strcpy(reply, "Error: expected on or off");
        }
      } else if (memcmp(config, "neighbors ", 10) == 0) {
        if (parseOnOff(&config[10], &_prefs->atlas.neighbors_enabled)) {
          savePrefs();
          strcpy(reply, "OK");
        } else {
          strcpy(reply, "Error: expected on or off");
        }
      } else if (memcmp(config, "pathsample ", 11) == 0) {
        const char* value = &config[11];
        if (parseOnOff(value, &_prefs->atlas.path_sample_enabled)) {
          savePrefs();
          strcpy(reply, "OK");
        } else if (*value >= '0' && *value <= '9') {
          uint8_t pct = atoi(value);
          if (pct <= 10) {
            _prefs->atlas.path_sample_percent = pct;
            _prefs->atlas.path_sample_enabled = pct > 0;
            savePrefs();
            strcpy(reply, "OK");
          } else {
            strcpy(reply, "Error: sample percent must be 0-10");
          }
        } else {
          strcpy(reply, "Error: expected on/off or 0-10");
        }
      } else if (memcmp(config, "export status", 13) == 0) {
        sprintf(reply, "atlas export %s", _prefs->atlas.export_enabled ? "on" : "off");
      } else if (sender_timestamp == 0 && memcmp(config, "export test", 11) == 0) {
        strcpy(reply,
            "{\"v\":1,\"type\":\"position\",\"time\":1770000000,\"node\":\"PD4MV\",\"node_id\":\"abcd1234\",\"lat\":52.7034,\"lon\":5.2912,\"alt\":12,\"speed\":36,\"heading\":90}\n"
            "{\"v\":1,\"type\":\"neighbor\",\"time\":1770000000,\"node\":\"PD4MV\",\"node_id\":\"abcd1234\",\"neighbors\":[{\"node_id\":\"beef5678\",\"rssi\":-97,\"snr\":7.5,\"last_heard\":1769999980}]}\n"
            "{\"v\":1,\"type\":\"path\",\"time\":1770000000,\"src\":\"abcd1234\",\"dst\":\"beef5678\",\"hops\":[\"abcd1234\",\"11223344\",\"beef5678\"],\"latency_ms\":1850}\n"
            "{\"v\":1,\"type\":\"dense_stats\",\"time\":1770000000,\"node\":\"PD4MV\",\"node_id\":\"abcd1234\",\"heard\":1234,\"duplicates\":321,\"forwards\":456,\"suppressed\":789,\"airtime_ms\":123456}\n"
            "{\"v\":1,\"type\":\"node_seen\",\"time\":1770000000,\"node\":\"PD4MV\",\"node_id\":\"abcd1234\"}");
      } else if (memcmp(config, "export test", 11) == 0) {
        strcpy(reply, "Error: atlas export test is serial-only");
      } else if (memcmp(config, "export ", 7) == 0) {
        if (parseOnOff(&config[7], &_prefs->atlas.export_enabled)) {
          savePrefs();
          strcpy(reply, "OK");
        } else {
          strcpy(reply, "Error: expected on or off");
        }
      } else {
        strcpy(reply, "Unknown atlas command");
      }
    } else if (memcmp(command, "get ", 4) == 0) {
      handleGetCmd(sender_timestamp, command, reply);
    } else if (memcmp(command, "set ", 4) == 0) {
      handleSetCmd(sender_timestamp, command, reply);
    } else if (sender_timestamp == 0 && strcmp(command, "erase") == 0) {
      bool s = _callbacks->formatFileSystem();
      sprintf(reply, "File system erase: %s", s ? "OK" : "Err");
    } else if (memcmp(command, "ver", 3) == 0) {
      sprintf(reply, "%s (Build: %s)", _callbacks->getFirmwareVer(), _callbacks->getBuildDate());
    } else if (memcmp(command, "board", 5) == 0) {
      sprintf(reply, "%s", _board->getManufacturerName());
    } else if (memcmp(command, "sensor get ", 11) == 0) {
      const char* key = command + 11;
      const char* val = _sensors->getSettingByKey(key);
      if (val != NULL) {
        sprintf(reply, "> %s", val);
      } else {
        strcpy(reply, "null");
      }
    } else if (memcmp(command, "sensor set ", 11) == 0) {
      strcpy(tmp, &command[11]);
      const char *parts[2];
      int num = mesh::Utils::parseTextParts(tmp, parts, 2, ' ');
      const char *key = (num > 0) ? parts[0] : "";
      const char *value = (num > 1) ? parts[1] : "null";
      if (_sensors->setSettingValue(key, value)) {
        strcpy(reply, "ok");
      } else {
        strcpy(reply, "can't find custom var");
      }
    } else if (memcmp(command, "sensor list", 11) == 0) {
      char* dp = reply;
      int start = 0;
      int end = _sensors->getNumSettings();
      if (strlen(command) > 11) {
        start = _atoi(command+12);
      }
      if (start >= end) {
        strcpy(reply, "no custom var");
      } else {
        sprintf(dp, "%d vars\n", end);
        dp = strchr(dp, 0);
        int i;
        for (i = start; i < end && (dp-reply < 134); i++) {
          sprintf(dp, "%s=%s\n",
            _sensors->getSettingName(i),
            _sensors->getSettingValue(i));
          dp = strchr(dp, 0);
        }
        if (i < end) {
          sprintf(dp, "... next:%d", i);
        } else {
          *(dp-1) = 0; // remove last CR
        }
      }
    } else if (memcmp(command, "regiondb", 8) == 0 && (command[8] == 0 || command[8] == ' ')) {
#if WITH_DUTCH_REGION_DB
      handleDutchRegionDbCmd(command, reply);
#else
      strcpy(reply, "Err - Dutch region database disabled");
#endif
    } else if (memcmp(command, "region", 6) == 0) {
      handleRegionCmd(command, reply);
#if ENV_INCLUDE_GPS == 1
    } else if (memcmp(command, "gps on", 6) == 0) {
      if (_sensors->setSettingValue("gps", "1")) {
        _prefs->gps_enabled = 1;
        savePrefs();
        strcpy(reply, "ok");
      } else {
        strcpy(reply, "gps toggle not found");
      }
    } else if (memcmp(command, "gps off", 7) == 0) {
      if (_sensors->setSettingValue("gps", "0")) {
        _prefs->gps_enabled = 0;
        savePrefs();
        strcpy(reply, "ok");
      } else {
        strcpy(reply, "gps toggle not found");
      }
    } else if (memcmp(command, "gps sync", 8) == 0) {
      LocationProvider * l = _sensors->getLocationProvider();
      if (l != NULL) {
        l->syncTime();
        strcpy(reply, "ok");
      } else {
        strcpy(reply, "gps provider not found");
      }
    } else if (memcmp(command, "gps setloc", 10) == 0) {
      _prefs->node_lat = _sensors->node_lat;
      _prefs->node_lon = _sensors->node_lon;
      savePrefs();
      strcpy(reply, "ok");
    } else if (memcmp(command, "gps advert", 10) == 0) {
      if (strlen(command) == 10) {
        switch (_prefs->advert_loc_policy) {
          case ADVERT_LOC_NONE:
            strcpy(reply, "> none");
            break;
          case ADVERT_LOC_PREFS:
            strcpy(reply, "> prefs");
            break;
          case ADVERT_LOC_SHARE:
            strcpy(reply, "> share");
            break;
          default:
            strcpy(reply, "error");
        }
      } else if (memcmp(command+11, "none", 4) == 0) {
        _prefs->advert_loc_policy = ADVERT_LOC_NONE;
        savePrefs();
        strcpy(reply, "ok");
      } else if (memcmp(command+11, "share", 5) == 0) {
        _prefs->advert_loc_policy = ADVERT_LOC_SHARE;
        savePrefs();
        strcpy(reply, "ok");
      } else if (memcmp(command+11, "prefs", 5) == 0) {
        _prefs->advert_loc_policy = ADVERT_LOC_PREFS;
        savePrefs();
        strcpy(reply, "ok");
      } else {
        strcpy(reply, "error");
      }
    } else if (memcmp(command, "gps", 3) == 0) {
      LocationProvider * l = _sensors->getLocationProvider();
      if (l != NULL) {
        bool enabled = l->isEnabled(); // is EN pin on ?
        bool fix = l->isValid();       // has fix ?
        int sats = l->satellitesCount();
        bool active = !strcmp(_sensors->getSettingByKey("gps"), "1");
        if (enabled) {
          sprintf(reply, "on, %s, %s, %d sats",
            active?"active":"deactivated",
            fix?"fix":"no fix",
            sats);
        } else {
          strcpy(reply, "off");
        }
      } else {
        strcpy(reply, "Can't find GPS");
      }
#endif
    } else if (memcmp(command, "powersaving on", 14) == 0) {
#if defined(NRF52_PLATFORM)
      _prefs->powersaving_enabled = 1;
      savePrefs();
      strcpy(reply, "on - Immediate effect");
#elif defined(ESP32) && !defined(WITH_BRIDGE)
      _prefs->powersaving_enabled = 1;
      savePrefs();
      strcpy(reply, "on - After 2 minutes");
#elif defined(WITH_BRIDGE)
      strcpy(reply, "Bridge not supported");
#else
      strcpy(reply, "Board not supported");
#endif
    } else if (memcmp(command, "powersaving off", 15) == 0) {
      _prefs->powersaving_enabled = 0;
      savePrefs();
      strcpy(reply, "off");
    } else if (memcmp(command, "powersaving", 11) == 0) {
      if (_prefs->powersaving_enabled) {
        strcpy(reply, "on");
      } else {
        strcpy(reply, "off");
      }
    } else if (memcmp(command, "log start", 9) == 0) {
      _callbacks->setLoggingOn(true);
      strcpy(reply, "   logging on");
    } else if (memcmp(command, "log stop", 8) == 0) {
      _callbacks->setLoggingOn(false);
      strcpy(reply, "   logging off");
    } else if (memcmp(command, "log erase", 9) == 0) {
      _callbacks->eraseLogFile();
      strcpy(reply, "   log erased");
    } else if (sender_timestamp == 0 && memcmp(command, "log", 3) == 0) {
      _callbacks->dumpLogFile();
      strcpy(reply, "   EOF");
    } else if (sender_timestamp == 0 && memcmp(command, "stats-packets", 13) == 0 && (command[13] == 0 || command[13] == ' ')) {
      _callbacks->formatPacketStatsReply(reply);
    } else if (sender_timestamp == 0 && memcmp(command, "stats-radio", 11) == 0 && (command[11] == 0 || command[11] == ' ')) {
      _callbacks->formatRadioStatsReply(reply);
    } else if (sender_timestamp == 0 && memcmp(command, "stats-core", 10) == 0 && (command[10] == 0 || command[10] == ' ')) {
      _callbacks->formatStatsReply(reply);
    } else {
      strcpy(reply, "Unknown command");
    }
}

void CommonCLI::handleSetCmd(uint32_t sender_timestamp, char* command, char* reply) {
  const char* config = &command[4];
  if (memcmp(config, "dutycycle ", 10) == 0) {
    float dc = atof(&config[10]);
    if (dc < 1 || dc > 100) {
      strcpy(reply, "ERROR: dutycycle must be 1-100");
    } else {
      _prefs->airtime_factor = (100.0f / dc) - 1.0f;
      savePrefs();
      float actual = 100.0f / (_prefs->airtime_factor + 1.0f);
      int a_int = (int)actual;
      int a_frac = (int)((actual - a_int) * 10.0f + 0.5f);
      sprintf(reply, "OK - %d.%d%%", a_int, a_frac);
    }
  } else if (memcmp(config, "af ", 3) == 0) {
    _prefs->airtime_factor = atof(&config[3]);
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "int.thresh ", 11) == 0) {
    _prefs->interference_threshold = atoi(&config[11]);
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "agc.reset.interval ", 19) == 0) {
    _prefs->agc_reset_interval = atoi(&config[19]) / 4;
    savePrefs();
    sprintf(reply, "OK - interval rounded to %d", ((uint32_t) _prefs->agc_reset_interval) * 4);
  } else if (memcmp(config, "multi.acks ", 11) == 0) {
    _prefs->multi_acks = atoi(&config[11]);
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "allow.read.only ", 16) == 0) {
    _prefs->allow_read_only = memcmp(&config[16], "on", 2) == 0;
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "flood.advert.interval ", 22) == 0) {
    int hours = _atoi(&config[22]);
    if ((hours > 0 && hours < 3) || (hours > 168)) {
      strcpy(reply, "Error: interval range is 3-168 hours");
    } else {
      _prefs->flood_advert_interval = (uint8_t)(hours);
      _callbacks->updateFloodAdvertTimer();
      savePrefs();
      strcpy(reply, "OK");
    }
  } else if (memcmp(config, "advert.interval ", 16) == 0) {
    int mins = _atoi(&config[16]);
    if ((mins > 0 && mins < MIN_LOCAL_ADVERT_INTERVAL) || (mins > 240)) {
      sprintf(reply, "Error: interval range is %d-240 minutes", MIN_LOCAL_ADVERT_INTERVAL);
    } else {
      _prefs->advert_interval = (uint8_t)(mins / 2);
      _callbacks->updateAdvertTimer();
      savePrefs();
      strcpy(reply, "OK");
    }
  } else if (memcmp(config, "guest.password ", 15) == 0) {
    StrHelper::strncpy(_prefs->guest_password, &config[15], sizeof(_prefs->guest_password));
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "prv.key ", 8) == 0) {
    uint8_t prv_key[PRV_KEY_SIZE];
    bool success = mesh::Utils::fromHex(prv_key, PRV_KEY_SIZE, &config[8]);
    // only allow rekey if key is valid
    if (success && mesh::LocalIdentity::validatePrivateKey(prv_key)) {
      mesh::LocalIdentity new_id;
      new_id.readFrom(prv_key, PRV_KEY_SIZE);
      _callbacks->saveIdentity(new_id);
      strcpy(reply, "OK, reboot to apply! New pubkey: ");
      mesh::Utils::toHex(&reply[33], new_id.pub_key, PUB_KEY_SIZE);
    } else {
      strcpy(reply, "Error, bad key");
    }
  } else if (memcmp(config, "name ", 5) == 0) {
    if (isValidName(&config[5])) {
      StrHelper::strncpy(_prefs->node_name, &config[5], sizeof(_prefs->node_name));
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error, bad chars");
    }
  } else if (memcmp(config, "repeat ", 7) == 0) {
    _prefs->disable_fwd = memcmp(&config[7], "off", 3) == 0;
    savePrefs();
    strcpy(reply, _prefs->disable_fwd ? "OK - repeat is now OFF" : "OK - repeat is now ON");
  } else if (memcmp(config, "malformed.drop ", 15) == 0) {
    _prefs->malformed_drop = memcmp(&config[15], "on", 2) == 0 || memcmp(&config[15], "drop", 4) == 0;
    savePrefs();
    strcpy(reply, _prefs->malformed_drop ? "OK - malformed chat drop is ON" : "OK - malformed chat drop is OFF");
  } else if (memcmp(config, "malformed ", 10) == 0) {
    _prefs->malformed_drop = memcmp(&config[10], "on", 2) == 0 || memcmp(&config[10], "drop", 4) == 0;
    savePrefs();
    strcpy(reply, _prefs->malformed_drop ? "OK - malformed chat drop is ON" : "OK - malformed chat drop is OFF");
#if defined(USE_SX1262) || defined(USE_SX1268) || defined(USE_LR1110)
  } else if (memcmp(config, "radio.rxgain ", 13) == 0) {
    _prefs->rx_boosted_gain = memcmp(&config[13], "on", 2) == 0;
    strcpy(reply, "OK");
    savePrefs();
    _callbacks->setRxBoostedGain(_prefs->rx_boosted_gain);
#endif
  } else if (memcmp(config, "radio.fem.rxgain ", 17) == 0) {
    uint8_t enabled = 0;
    if (!parseOnOff(&config[17], &enabled)) {
      strcpy(reply, "Error: expected on or off");
    } else if (!_board->setFemRxGain(enabled)) {
      strcpy(reply, "Error: FEM RX gain not supported");
    } else {
      _prefs->fem_rx_gain = enabled;
      savePrefs();
      strcpy(reply, "OK");
    }
  } else if (memcmp(config, "boot.lowbat.guard ", 18) == 0) {
    uint8_t enabled = 0;
    if (parseOnOff(&config[18], &enabled)) {
      _prefs->low_bat_boot_guard_enabled = enabled;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: expected on or off");
    }
  } else if (memcmp(config, "boot.lowbat.mv ", 15) == 0) {
    const char* value = &config[15];
    uint16_t mv = (uint16_t)_atoi(value);
    if (*value >= '0' && *value <= '9' && (mv == 0 || (mv >= 2500 && mv <= 6000))) {
      _prefs->low_bat_boot_guard_mv = mv;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: threshold must be 0 or 2500-6000 mV");
    }
  } else if (memcmp(config, "boot.lowbat.valid_min ", 22) == 0) {
    const char* value = &config[22];
    uint16_t mv = (uint16_t)_atoi(value);
    if (*value >= '0' && *value <= '9' && mv <= 6000) {
      _prefs->low_bat_boot_valid_min_mv = mv;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: valid_min must be 0-6000 mV");
    }
  } else if (memcmp(config, "boot.lowbat.retry ", 18) == 0) {
    const char* value = &config[18];
    uint16_t secs = (uint16_t)_atoi(value);
    if (*value >= '0' && *value <= '9' && secs >= 5 && secs <= 3600) {
      _prefs->low_bat_boot_retry_secs = secs;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: retry must be 5-3600 seconds");
    }
  } else if (memcmp(config, "runtime.lowbat.guard ", 21) == 0) {
    uint8_t enabled = 0;
    if (parseOnOff(&config[21], &enabled)) {
      _prefs->low_bat_runtime_guard_enabled = enabled;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: expected on or off");
    }
  } else if (memcmp(config, "runtime.lowbat.mv ", 18) == 0) {
    const char* value = &config[18];
    uint16_t mv = (uint16_t)_atoi(value);
    if (*value >= '0' && *value <= '9' && (mv == 0 || (mv >= 2500 && mv <= 6000))) {
      _prefs->low_bat_runtime_guard_mv = mv;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: threshold must be 0 or 2500-6000 mV");
    }
  } else if (memcmp(config, "runtime.lowbat.warn ", 20) == 0) {
    const char* value = &config[20];
    uint16_t mv = (uint16_t)_atoi(value);
    if (*value >= '0' && *value <= '9' && mv <= 6000) {
      _prefs->low_bat_runtime_warn_mv = mv;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: warning threshold must be 0-6000 mV");
    }
  } else if (memcmp(config, "runtime.lowbat.valid_min ", 25) == 0) {
    const char* value = &config[25];
    uint16_t mv = (uint16_t)_atoi(value);
    if (*value >= '0' && *value <= '9' && mv <= 6000) {
      _prefs->low_bat_runtime_valid_min_mv = mv;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: valid_min must be 0-6000 mV");
    }
  } else if (memcmp(config, "runtime.lowbat.retry ", 21) == 0) {
    const char* value = &config[21];
    uint32_t secs = _atoi(value);
    if (*value >= '0' && *value <= '9' && secs >= 5 && secs <= 86400) {
      _prefs->low_bat_runtime_retry_secs = secs;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: retry must be 5-86400 seconds");
    }
  } else if (memcmp(config, "radio ", 6) == 0) {
    strcpy(tmp, &config[6]);
    const char *parts[4];
    int num = mesh::Utils::parseTextParts(tmp, parts, 4);
    float freq  = num > 0 ? strtof(parts[0], nullptr) : 0.0f;
    float bw    = num > 1 ? strtof(parts[1], nullptr) : 0.0f;
    uint8_t sf  = num > 2 ? atoi(parts[2]) : 0;
    uint8_t cr  = num > 3 ? atoi(parts[3]) : 0;
    if (freq >= 150.0f && freq <= 2500.0f && sf >= 5 && sf <= 12 && cr >= 5 && cr <= 8 && bw >= 7.0f && bw <= 500.0f) {
      _prefs->sf = sf;
      _prefs->cr = cr;
      _prefs->freq = freq;
      _prefs->bw = bw;
      _callbacks->savePrefs();
      strcpy(reply, "OK - reboot to apply");
    } else {
      strcpy(reply, "Error, invalid radio params");
    }
  } else if (memcmp(config, "lat ", 4) == 0) {
    _prefs->node_lat = atof(&config[4]);
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "lon ", 4) == 0) {
    _prefs->node_lon = atof(&config[4]);
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "rxdelay ", 8) == 0) {
    float db = atof(&config[8]);
    if (db >= 0 && db <= 20.0f) {
      _prefs->rx_delay_base = db;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error, must be 0-20");
    }
  } else if (memcmp(config, "txdelay ", 8) == 0) {
    float f = atof(&config[8]);
    if (f >= 0 && f <= 2.0f) {
      _prefs->tx_delay_factor = f;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error, must be 0-2");
    }
  } else if (memcmp(config, "flood.max.unscoped ", 19) == 0) {
    uint8_t m = atoi(&config[19]);
    if (m <= 64) {
      _prefs->flood_max_unscoped = m;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error, max 64");
    }
  } else if (memcmp(config, "flood.max.advert ", 17) == 0) {
    uint8_t m = atoi(&config[17]);
    if (m <= 64) {
      _prefs->flood_max_advert = m;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error, max 64");
    }
  } else if (memcmp(config, "flood.max ", 10) == 0) {
    uint8_t m = atoi(&config[10]);
    if (m <= 64) {
      _prefs->flood_max = m;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error, max 64");
    }
  } else if (memcmp(config, "flood.advert.base ", 18) == 0) {
    float f = atof(&config[18]);
    if (f >= 0.0f && f <= 1.0f) {
      _prefs->flood_advert_base = f;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: base must be between 0 and 1");
    }
  } else if (memcmp(config, "flood.relay.prob ", 17) == 0) {
    const char* value = &config[17];
    int p = atoi(value);
    if (*value >= '0' && *value <= '9' && p >= 0 && p <= 255) {
      _prefs->flood_relay_prob = (uint8_t)p;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: probability must be 0-255");
    }
  } else if (memcmp(config, "flood.dynamic.enable ", 21) == 0) {
    const char* value = &config[21];
    if (parseOnOff(value, &_prefs->flood_dynamic_enable)) {
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: expected on or off");
    }
  } else if (memcmp(config, "flood.node.delay ", 17) == 0 || memcmp(config, "node.delay ", 11) == 0) {
    const char* value = (config[0] == 'f') ? &config[17] : &config[11];
    if (parseOnOff(value, &_prefs->flood_node_delay_enable)) {
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: expected on or off");
    }
  } else if (memcmp(config, "flood.dup.suppress ", 19) == 0 || memcmp(config, "dup.suppress ", 13) == 0) {
    const char* value = (config[0] == 'f') ? &config[19] : &config[13];
    if (parseOnOff(value, &_prefs->flood_dup_suppress_enable)) {
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: expected on or off");
    }
  } else if (memcmp(config, "atlas.enable ", 13) == 0 || memcmp(config, "atlas ", 6) == 0) {
    const char* value = (config[6] == 'e') ? &config[13] : &config[6];
    if (parseOnOff(value, &_prefs->atlas.enabled)) {
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: expected on or off");
    }
  } else if (memcmp(config, "atlas.position ", 15) == 0) {
    const char* value = &config[15];
    if (parseOnOff(value, &_prefs->atlas.position_enabled)) {
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: expected on or off");
    }
  } else if (memcmp(config, "atlas.neighbors ", 16) == 0) {
    const char* value = &config[16];
    if (parseOnOff(value, &_prefs->atlas.neighbors_enabled)) {
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: expected on or off");
    }
  } else if (memcmp(config, "atlas.pathsample ", 17) == 0) {
    const char* value = &config[17];
    if (parseOnOff(value, &_prefs->atlas.path_sample_enabled)) {
      savePrefs();
      strcpy(reply, "OK");
    } else if (*value >= '0' && *value <= '9') {
      uint8_t pct = atoi(value);
      if (pct <= 10) {
        _prefs->atlas.path_sample_percent = pct;
        _prefs->atlas.path_sample_enabled = pct > 0;
        savePrefs();
        strcpy(reply, "OK");
      } else {
        strcpy(reply, "Error: sample percent must be 0-10");
      }
    } else {
      strcpy(reply, "Error: expected on/off or 0-10");
    }
  } else if (memcmp(config, "atlas.export ", 13) == 0) {
    const char* value = &config[13];
    if (parseOnOff(value, &_prefs->atlas.export_enabled)) {
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: expected on or off");
    }
  } else if (memcmp(config, "direct.txdelay ", 15) == 0) {
    float f = atof(&config[15]);
    if (f >= 0 && f <= 2.0f) {
      _prefs->direct_tx_delay_factor = f;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error, must be 0-2");
    }
  } else if (memcmp(config, "owner.info ", 11) == 0) {
    config += 11;
    char *dp = _prefs->owner_info;
    while (*config && dp - _prefs->owner_info < sizeof(_prefs->owner_info)-1) {
      *dp++ = (*config == '|') ? '\n' : *config;    // translate '|' to newline chars
      config++;
    }
    *dp = 0;
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "path.hash.mode ", 15) == 0) {
    config += 15;
    uint8_t mode = atoi(config);
    if (mode < 3) {
      _prefs->path_hash_mode = mode;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error, must be 0,1, or 2");
    }
  } else if (memcmp(config, "loop.detect ", 12) == 0) {
    config += 12;
    uint8_t mode;
    if (memcmp(config, "off", 3) == 0) {
      mode = LOOP_DETECT_OFF;
    } else if (memcmp(config, "minimal", 7) == 0) {
      mode = LOOP_DETECT_MINIMAL;
    } else if (memcmp(config, "moderate", 8) == 0) {
      mode = LOOP_DETECT_MODERATE;
    } else if (memcmp(config, "strict", 6) == 0) {
      mode = LOOP_DETECT_STRICT;
    } else {
      mode = 0xFF;
      strcpy(reply, "Error, must be: off, minimal, moderate, or strict");
    }
    if (mode != 0xFF) {
      _prefs->loop_detect = mode;
      savePrefs();
      strcpy(reply, "OK");
    }
  } else if (memcmp(config, "tx ", 3) == 0) {
    _prefs->tx_power_dbm = atoi(&config[3]);
    savePrefs();
    _callbacks->setTxPower(_prefs->tx_power_dbm);
    strcpy(reply, "OK");
  } else if (sender_timestamp == 0 && memcmp(config, "freq ", 5) == 0) {
    _prefs->freq = atof(&config[5]);
    savePrefs();
    strcpy(reply, "OK - reboot to apply");
#ifdef WITH_BRIDGE
  } else if (memcmp(config, "bridge.enabled ", 15) == 0) {
    _prefs->bridge_enabled = memcmp(&config[15], "on", 2) == 0;
    _callbacks->setBridgeState(_prefs->bridge_enabled);
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "bridge.delay ", 13) == 0) {
    int delay = _atoi(&config[13]);
    if (delay >= 0 && delay <= 10000) {
      _prefs->bridge_delay = (uint16_t)delay;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: delay must be between 0-10000 ms");
    }
  } else if (memcmp(config, "bridge.source ", 14) == 0) {
    if (memcmp(&config[14], "rx", 2) == 0 || memcmp(&config[14], "logRx", 5) == 0) {
      _prefs->bridge_pkt_src = 1;
      savePrefs();
      strcpy(reply, "OK");
    } else if (memcmp(&config[14], "tx", 2) == 0 || memcmp(&config[14], "logTx", 5) == 0) {
      _prefs->bridge_pkt_src = 0;
      savePrefs();
      strcpy(reply, "OK");
    } else if (memcmp(&config[14], "both", 4) == 0 || memcmp(&config[14], "all", 3) == 0) {
      _prefs->bridge_pkt_src = 2;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: source must be tx, rx, or both");
    }
  } else if (memcmp(config, "bridge.rf ", 10) == 0) {
    if (memcmp(&config[10], "off", 3) == 0) {
      _prefs->bridge_rf = BRIDGE_RF_OFF;
      savePrefs();
      strcpy(reply, "OK");
    } else if (memcmp(&config[10], "on", 2) == 0 || memcmp(&config[10], "flood", 5) == 0) {
      _prefs->bridge_rf = BRIDGE_RF_FLOOD;
      savePrefs();
      strcpy(reply, "OK");
    } else if (memcmp(&config[10], "local", 5) == 0 || memcmp(&config[10], "ttl1", 4) == 0) {
      _prefs->bridge_rf = BRIDGE_RF_LOCAL;
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: mode must be off, on, flood, local, or ttl1");
    }
#endif
#ifdef WITH_RS232_BRIDGE
  } else if (memcmp(config, "bridge.baud ", 12) == 0) {
    uint32_t baud = atoi(&config[12]);
    if (baud >= 9600 && baud <= BRIDGE_MAX_BAUD) {
      _prefs->bridge_baud = (uint32_t)baud;
      _callbacks->restartBridge();
      savePrefs();
      strcpy(reply, "OK");
    } else {
      sprintf(reply, "Error: baud rate must be between 9600-%d",BRIDGE_MAX_BAUD);
    }
#endif
#ifdef WITH_ESPNOW_BRIDGE
  } else if (memcmp(config, "bridge.channel ", 15) == 0) {
    int ch = atoi(&config[15]);
    if (ch > 0 && ch < 15) {
      _prefs->bridge_channel = (uint8_t)ch;
      _callbacks->restartBridge();
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: channel must be between 1-14");
    }
#endif
#if defined(WITH_ESPNOW_BRIDGE) || defined(WITH_BLE_BRIDGE)
  } else if (memcmp(config, "bridge.secret ", 14) == 0) {
    StrHelper::strncpy(_prefs->bridge_secret, &config[14], sizeof(_prefs->bridge_secret));
    _callbacks->restartBridge();
    savePrefs();
    strcpy(reply, "OK");
#endif
#ifdef WITH_TCP_BRIDGE
  } else if (memcmp(config, "wifi.ssid ", 10) == 0) {
    StrHelper::strncpy(_prefs->wifi_ssid, &config[10], sizeof(_prefs->wifi_ssid));
    savePrefs();
    strcpy(reply, "OK - reboot to apply");
  } else if (memcmp(config, "wifi.password ", 14) == 0) {
    StrHelper::strncpy(_prefs->wifi_password, &config[14], sizeof(_prefs->wifi_password));
    savePrefs();
    strcpy(reply, "OK - reboot to apply");
  } else if (memcmp(config, "bridge.server ", 14) == 0) {
    StrHelper::strncpy(_prefs->bridge_server, &config[14], sizeof(_prefs->bridge_server));
    _callbacks->restartBridge();
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "bridge.password ", 16) == 0) {
    StrHelper::strncpy(_prefs->bridge_password, &config[16], sizeof(_prefs->bridge_password));
    _callbacks->restartBridge();
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "bridge.port ", 12) == 0) {
    int port = _atoi(&config[12]);
    if (port > 0 && port <= 65535) {
      _prefs->bridge_port = (uint16_t)port;
      _callbacks->restartBridge();
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: port must be between 1-65535");
    }
  } else if (memcmp(config, "ntp.enabled ", 12) == 0) {
    uint8_t enabled = 0;
    if (parseOnOff(&config[12], &enabled)) {
      _prefs->ntp_enabled = enabled;
      _callbacks->onNtpPrefsChanged();
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: expected on or off");
    }
  } else if (memcmp(config, "ntp.server ", 11) == 0) {
    StrHelper::strncpy(_prefs->ntp_server, &config[11], sizeof(_prefs->ntp_server));
    _callbacks->onNtpPrefsChanged();
    savePrefs();
    strcpy(reply, "OK");
  } else if (memcmp(config, "ntp.interval ", 13) == 0) {
    uint32_t interval = _atoi(&config[13]);
    if (interval >= 60 && interval <= 86400) {
      _prefs->ntp_interval_secs = interval;
      _callbacks->onNtpPrefsChanged();
      savePrefs();
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Error: interval must be 60-86400 seconds");
    }
#endif
  } else if (memcmp(config, "adc.multiplier ", 15) == 0) {
    _prefs->adc_multiplier = atof(&config[15]);
    if (_board->setAdcMultiplier(_prefs->adc_multiplier)) {
      savePrefs();
      if (_prefs->adc_multiplier == 0.0f) {
        strcpy(reply, "OK - using default board multiplier");
      } else {
        sprintf(reply, "OK - multiplier set to %.3f", _prefs->adc_multiplier);
      }
    } else {
      _prefs->adc_multiplier = 0.0f;
      strcpy(reply, "Error: unsupported by this board");
    };
  } else {
    strcpy(reply, "unknown config: ");
    StrHelper::strncpy(&reply[16], config, 160-17);
  }
}

void CommonCLI::handleGetCmd(uint32_t sender_timestamp, char* command, char* reply) {
  const char* config = &command[4];
  if (memcmp(config, "dutycycle", 9) == 0) {
    float dc = 100.0f / (_prefs->airtime_factor + 1.0f);
    int dc_int = (int)dc;
    int dc_frac = (int)((dc - dc_int) * 10.0f + 0.5f);
    sprintf(reply, "> %d.%d%%", dc_int, dc_frac);
  } else if (memcmp(config, "af", 2) == 0) {
    sprintf(reply, "> %s", StrHelper::ftoa(_prefs->airtime_factor));
  } else if (memcmp(config, "int.thresh", 10) == 0) {
    sprintf(reply, "> %d", (uint32_t) _prefs->interference_threshold);
  } else if (memcmp(config, "agc.reset.interval", 18) == 0) {
    sprintf(reply, "> %d", ((uint32_t) _prefs->agc_reset_interval) * 4);
  } else if (memcmp(config, "multi.acks", 10) == 0) {
    sprintf(reply, "> %d", (uint32_t) _prefs->multi_acks);
  } else if (memcmp(config, "allow.read.only", 15) == 0) {
    sprintf(reply, "> %s", _prefs->allow_read_only ? "on" : "off");
  } else if (memcmp(config, "flood.advert.interval", 21) == 0) {
    sprintf(reply, "> %d", ((uint32_t) _prefs->flood_advert_interval));
  } else if (memcmp(config, "flood.advert.base", 17) == 0) {
    sprintf(reply, "> %s", StrHelper::ftoa(_prefs->flood_advert_base));
  } else if (memcmp(config, "flood.relay.prob", 16) == 0) {
    sprintf(reply, "> %u", (uint32_t)_prefs->flood_relay_prob);
  } else if (memcmp(config, "flood.dynamic.enable", 20) == 0) {
    sprintf(reply, "> %s", _prefs->flood_dynamic_enable ? "on" : "off");
  } else if (memcmp(config, "flood.node.delay", 16) == 0 || memcmp(config, "node.delay", 10) == 0) {
    sprintf(reply, "> %s", _prefs->flood_node_delay_enable ? "on" : "off");
  } else if (memcmp(config, "flood.dup.suppress", 18) == 0 || memcmp(config, "dup.suppress", 12) == 0) {
    sprintf(reply, "> %s", _prefs->flood_dup_suppress_enable ? "on" : "off");
  } else if (sender_timestamp == 0 && memcmp(config, "dense.stats", 11) == 0) {
    _callbacks->formatDenseStatsReply(reply);
  } else if (sender_timestamp == 0 && memcmp(config, "atlas.stats", 11) == 0) {
    _callbacks->formatAtlasStatsReply(reply);
  } else if (memcmp(config, "atlas.position", 14) == 0) {
    sprintf(reply, "> %s", _prefs->atlas.position_enabled ? "on" : "off");
  } else if (memcmp(config, "atlas.neighbors", 15) == 0) {
    sprintf(reply, "> %s", _prefs->atlas.neighbors_enabled ? "on" : "off");
  } else if (memcmp(config, "atlas.pathsample", 16) == 0) {
    sprintf(reply, "> %s,%u", _prefs->atlas.path_sample_enabled ? "on" : "off", (uint32_t)_prefs->atlas.path_sample_percent);
  } else if (memcmp(config, "atlas.export", 12) == 0) {
    sprintf(reply, "> %s", _prefs->atlas.export_enabled ? "on" : "off");
  } else if (memcmp(config, "atlas.enable", 12) == 0 || strcmp(config, "atlas") == 0) {
    sprintf(reply, "> %s", _prefs->atlas.enabled ? "on" : "off");
  } else if (memcmp(config, "spam.stats", 10) == 0) {
    _callbacks->formatSpamStatsReply(reply);
  } else if (memcmp(config, "repeater.health", 15) == 0 || memcmp(config, "repeater.status", 15) == 0) {
    _callbacks->formatRepeaterHealthReply(reply);
  } else if (sender_timestamp == 0 && memcmp(config, "power.stats", 11) == 0) {
    _callbacks->formatPowerStatsReply(reply);
  } else if (memcmp(config, "advert.interval", 15) == 0) {
    sprintf(reply, "> %d", ((uint32_t) _prefs->advert_interval) * 2);
  } else if (memcmp(config, "guest.password", 14) == 0) {
    sprintf(reply, "> %s", _prefs->guest_password);
  } else if (sender_timestamp == 0 && memcmp(config, "prv.key", 7) == 0) {  // from serial command line only
    uint8_t prv_key[PRV_KEY_SIZE];
    int len = _callbacks->getSelfId().writeTo(prv_key, PRV_KEY_SIZE);
    mesh::Utils::toHex(tmp, prv_key, len);
    sprintf(reply, "> %s", tmp);
  } else if (memcmp(config, "name", 4) == 0) {
    sprintf(reply, "> %s", _prefs->node_name);
  } else if (memcmp(config, "repeat", 6) == 0) {
    sprintf(reply, "> %s", _prefs->disable_fwd ? "off" : "on");
  } else if (memcmp(config, "malformed.drop", 14) == 0 || memcmp(config, "malformed", 9) == 0) {
    sprintf(reply, "> %s", _prefs->malformed_drop ? "on" : "off");
  } else if (memcmp(config, "lat", 3) == 0) {
    sprintf(reply, "> %s", StrHelper::ftoa(_prefs->node_lat));
  } else if (memcmp(config, "lon", 3) == 0) {
    sprintf(reply, "> %s", StrHelper::ftoa(_prefs->node_lon));
#if defined(USE_SX1262) || defined(USE_SX1268) || defined(USE_LR1110)
  } else if (memcmp(config, "radio.rxgain", 12) == 0) {
    sprintf(reply, "> %s", _prefs->rx_boosted_gain ? "on" : "off");
#endif
  } else if (memcmp(config, "radio.fem.rxgain", 16) == 0) {
    if (_board->supportsFemRxGain()) {
      sprintf(reply, "> %s", _board->getFemRxGain() ? "on" : "off");
    } else {
      strcpy(reply, "Error: FEM RX gain not supported");
    }
  } else if (memcmp(config, "boot.lowbat.guard", 17) == 0) {
    sprintf(reply, "> %s", _prefs->low_bat_boot_guard_enabled ? "on" : "off");
  } else if (memcmp(config, "boot.lowbat.mv", 14) == 0) {
    sprintf(reply, "> %u", (uint32_t)_prefs->low_bat_boot_guard_mv);
  } else if (memcmp(config, "boot.lowbat.valid_min", 21) == 0) {
    sprintf(reply, "> %u", (uint32_t)_prefs->low_bat_boot_valid_min_mv);
  } else if (memcmp(config, "boot.lowbat.retry", 17) == 0) {
    sprintf(reply, "> %u", (uint32_t)_prefs->low_bat_boot_retry_secs);
  } else if (memcmp(config, "runtime.lowbat.guard", 20) == 0) {
    sprintf(reply, "> %s", _prefs->low_bat_runtime_guard_enabled ? "on" : "off");
  } else if (memcmp(config, "runtime.lowbat.mv", 17) == 0) {
    sprintf(reply, "> %u", (uint32_t)_prefs->low_bat_runtime_guard_mv);
  } else if (memcmp(config, "runtime.lowbat.warn", 19) == 0) {
    sprintf(reply, "> %u", (uint32_t)_prefs->low_bat_runtime_warn_mv);
  } else if (memcmp(config, "runtime.lowbat.valid_min", 24) == 0) {
    sprintf(reply, "> %u", (uint32_t)_prefs->low_bat_runtime_valid_min_mv);
  } else if (memcmp(config, "runtime.lowbat.retry", 20) == 0) {
    sprintf(reply, "> %lu", (unsigned long)_prefs->low_bat_runtime_retry_secs);
  } else if (memcmp(config, "radio", 5) == 0) {
    char freq[16], bw[16];
    strcpy(freq, StrHelper::ftoa(_prefs->freq));
    strcpy(bw, StrHelper::ftoa3(_prefs->bw));
    sprintf(reply, "> %s,%s,%d,%d", freq, bw, (uint32_t)_prefs->sf, (uint32_t)_prefs->cr);
  } else if (memcmp(config, "rxdelay", 7) == 0) {
    sprintf(reply, "> %s", StrHelper::ftoa(_prefs->rx_delay_base));
  } else if (memcmp(config, "txdelay", 7) == 0) {
    sprintf(reply, "> %s", StrHelper::ftoa(_prefs->tx_delay_factor));
  } else if (memcmp(config, "flood.max.advert", 16) == 0) {
    sprintf(reply, "> %d", (uint32_t)_prefs->flood_max_advert);
  } else if (memcmp(config, "flood.max.unscoped", 18) == 0) {
    sprintf(reply, "> %d", (uint32_t)_prefs->flood_max_unscoped);
  } else if (memcmp(config, "flood.max", 9) == 0) {
    sprintf(reply, "> %d", (uint32_t)_prefs->flood_max);
  } else if (memcmp(config, "direct.txdelay", 14) == 0) {
    sprintf(reply, "> %s", StrHelper::ftoa(_prefs->direct_tx_delay_factor));
  } else if (memcmp(config, "owner.info", 10) == 0) {
    auto start = reply;
    *reply++ = '>';
    *reply++ = ' ';
    const char* sp = _prefs->owner_info;
    while (*sp && reply - start < 159) {
      *reply++ = (*sp == '\n') ? '|' : *sp;    // translate newline back to orig '|'
      sp++;
    }
    *reply = 0;  // set null terminator
  } else if (memcmp(config, "path.hash.mode", 14) == 0) {
    sprintf(reply, "> %d", (uint32_t)_prefs->path_hash_mode);
  } else if (memcmp(config, "loop.detect", 11) == 0) {
    if (_prefs->loop_detect == LOOP_DETECT_OFF) {
      strcpy(reply, "> off");
    } else if (_prefs->loop_detect == LOOP_DETECT_MINIMAL) {
      strcpy(reply, "> minimal");
    } else if (_prefs->loop_detect == LOOP_DETECT_MODERATE) {
      strcpy(reply, "> moderate");
    } else {
      strcpy(reply, "> strict");
    }
  } else if (memcmp(config, "tx", 2) == 0 && (config[2] == 0 || config[2] == ' ')) {
    sprintf(reply, "> %d", (int32_t) _prefs->tx_power_dbm);
  } else if (memcmp(config, "freq", 4) == 0) {
    sprintf(reply, "> %s", StrHelper::ftoa(_prefs->freq));
  } else if (memcmp(config, "public.key", 10) == 0) {
    strcpy(reply, "> ");
    mesh::Utils::toHex(&reply[2], _callbacks->getSelfId().pub_key, PUB_KEY_SIZE);
  } else if (memcmp(config, "firmware.target", 15) == 0) {
    sprintf(reply, "> %s", FIRMWARE_TARGET);
  } else if (memcmp(config, "role", 4) == 0) {
    sprintf(reply, "> %s", _callbacks->getRole());
  } else if (memcmp(config, "bridge.type", 11) == 0) {
    sprintf(reply, "> %s",
#if defined(WITH_TCP_BRIDGE) && defined(WITH_BLE_BRIDGE)
            "tcp+ble"
#elif defined(WITH_RS232_BRIDGE)
            "rs232"
#elif defined(WITH_ESPNOW_BRIDGE)
            "espnow"
#elif defined(WITH_TCP_BRIDGE)
            "tcp"
#elif defined(WITH_BLE_BRIDGE)
            "ble"
#else
            "none"
#endif
    );
#ifdef WITH_BRIDGE
  } else if (memcmp(config, "bridge.enabled", 14) == 0) {
    sprintf(reply, "> %s", _prefs->bridge_enabled ? "on" : "off");
  } else if (memcmp(config, "bridge.delay", 12) == 0) {
    sprintf(reply, "> %d", (uint32_t)_prefs->bridge_delay);
  } else if (memcmp(config, "bridge.source", 13) == 0) {
    sprintf(reply, "> %s", _prefs->bridge_pkt_src == 2 ? "both" : (_prefs->bridge_pkt_src ? "logRx" : "logTx"));
  } else if (memcmp(config, "bridge.rf", 9) == 0) {
    sprintf(reply, "> %s", _prefs->bridge_rf == BRIDGE_RF_LOCAL ? "local" : (_prefs->bridge_rf ? "on" : "off"));
#if defined(WITH_BLE_BRIDGE)
  } else if (memcmp(config, "bridge.status", 13) == 0) {
    _callbacks->formatBleBridgeStatusReply(reply);
#endif
#endif
#ifdef WITH_RS232_BRIDGE
  } else if (memcmp(config, "bridge.baud", 11) == 0) {
    sprintf(reply, "> %d", (uint32_t)_prefs->bridge_baud);
#endif
#ifdef WITH_ESPNOW_BRIDGE
  } else if (memcmp(config, "bridge.channel", 14) == 0) {
    sprintf(reply, "> %d", (uint32_t)_prefs->bridge_channel);
#endif
#if defined(WITH_ESPNOW_BRIDGE) || defined(WITH_BLE_BRIDGE)
  } else if (memcmp(config, "bridge.secret", 13) == 0) {
    sprintf(reply, "> %s", _prefs->bridge_secret);
#endif
#ifdef WITH_TCP_BRIDGE
  } else if (memcmp(config, "wifi.ssid", 9) == 0) {
    sprintf(reply, "> %s", _prefs->wifi_ssid);
  } else if (memcmp(config, "wifi.password", 13) == 0) {
    strcpy(reply, "> ***");
  } else if (memcmp(config, "wifi.status", 11) == 0) {
    _callbacks->formatTcpBridgeStatusReply(reply);
  } else if (memcmp(config, "bridge.server", 13) == 0) {
    sprintf(reply, "> %s", _prefs->bridge_server);
  } else if (memcmp(config, "bridge.password", 15) == 0) {
    strcpy(reply, "> ***");
  } else if (memcmp(config, "bridge.port", 11) == 0) {
    sprintf(reply, "> %d", (uint32_t)_prefs->bridge_port);
  } else if (memcmp(config, "ntp.enabled", 11) == 0) {
    sprintf(reply, "> %s", _prefs->ntp_enabled ? "on" : "off");
  } else if (memcmp(config, "ntp.server", 10) == 0) {
    sprintf(reply, "> %s", _prefs->ntp_server);
  } else if (memcmp(config, "ntp.interval", 12) == 0) {
    sprintf(reply, "> %lu", (unsigned long)_prefs->ntp_interval_secs);
  } else if (memcmp(config, "ntp.status", 10) == 0) {
    _callbacks->formatNtpStatusReply(reply);
#endif
  } else if (memcmp(config, "bootloader.ver", 14) == 0) {
  #ifdef NRF52_PLATFORM
      char ver[32];
      if (_board->getBootloaderVersion(ver, sizeof(ver))) {
          sprintf(reply, "> %s", ver);
      } else {
          strcpy(reply, "> unknown");
      }
  #else
      strcpy(reply, "ERROR: unsupported");
  #endif
  } else if (memcmp(config, "adc.multiplier", 14) == 0) {
    float adc_mult = _board->getAdcMultiplier();
    if (adc_mult == 0.0f) {
      strcpy(reply, "Error: unsupported by this board");
    } else {
      sprintf(reply, "> %.3f", adc_mult);
    }
  // Power management commands
  } else if (memcmp(config, "pwrmgt.support", 14) == 0) {
#ifdef NRF52_POWER_MANAGEMENT
    strcpy(reply, "> supported");
#else
    strcpy(reply, "> unsupported");
#endif
  } else if (memcmp(config, "pwrmgt.source", 13) == 0) {
#ifdef NRF52_POWER_MANAGEMENT
    strcpy(reply, _board->isExternalPowered() ? "> external" : "> battery");
#else
    strcpy(reply, "ERROR: Power management not supported");
#endif
  } else if (memcmp(config, "pwrmgt.bootreason", 17) == 0) {
#ifdef NRF52_POWER_MANAGEMENT
    sprintf(reply, "> Reset: %s; Shutdown: %s",
      _board->getResetReasonString(_board->getResetReason()),
      _board->getShutdownReasonString(_board->getShutdownReason()));
#else
    strcpy(reply, "ERROR: Power management not supported");
#endif
  } else if (memcmp(config, "pwrmgt.bootmv", 13) == 0) {
#ifdef NRF52_POWER_MANAGEMENT
    sprintf(reply, "> %u mV", _board->getBootVoltage());
#else
    strcpy(reply, "ERROR: Power management not supported");
#endif
  } else {
    sprintf(reply, "??: %s", config);
  }
}

#if WITH_DUTCH_REGION_DB
static char* appendCodeText(char* dp, const char* end, uint16_t code_id) {
  const char* code = DutchRegionDb::codeText(code_id);
  if (!code || dp >= end) return dp;
  int written = snprintf(dp, end - dp, "%s%s", dp[-1] == ' ' ? "" : ",", code);
  if (written <= 0) return dp;
  return dp + min(written, (int)(end - dp));
}

void CommonCLI::handleDutchRegionDbCmd(char* command, char* reply) {
  reply[0] = 0;

  const char* parts[4];
  int n = mesh::Utils::parseTextParts(command, parts, 4, ' ');
  if (n == 1 || (n >= 2 && strcmp(parts[1], "info") == 0)) {
    sprintf(reply, "nl-db entries=%u provinces=%u codes=%u rev=%u modified=%s",
      DutchRegionDb::entryCount(),
      DutchRegionDb::provinceCount(),
      DutchRegionDb::regionCodeCount(),
      DutchRegionDb::sourceRevision(),
      DutchRegionDb::sourceModified());
  } else if (n >= 2 && strcmp(parts[1], "provinces") == 0) {
    char* dp = reply;
    char* end = reply + 160;
    for (uint16_t i = 1; i <= DutchRegionDb::provinceCount(); i++) {
      const DutchRegionDbProvince* province = DutchRegionDb::provinceById(i);
      if (province) {
        int written = snprintf(dp, end - dp, "%s%s:%u", i == 1 ? "" : ",", province->abbr, DutchRegionDb::countByProvince(i));
        if (written <= 0 || written >= end - dp) break;
        dp += written;
      }
    }
  } else if (n >= 3 && strcmp(parts[1], "code") == 0) {
    uint16_t code_id = _atoi(parts[2]);
    const char* code = DutchRegionDb::codeText(code_id);
    if (code) {
      sprintf(reply, "%u %s", code_id, code);
    } else {
      strcpy(reply, "Err - unknown code");
    }
  } else if (n >= 3 && strcmp(parts[1], "find") == 0) {
    uint16_t start = n >= 4 ? _atoi(parts[3]) : 0;
    int index = DutchRegionDb::findByNamePrefix(parts[2], start);
    if (index >= 0) {
      DutchRegionDbRecord record;
      DutchRegionDb::readRecord(index, record);
      const DutchRegionDbProvince* province = DutchRegionDb::provinceById(record.province_id);
      const char* primary = DutchRegionDb::codeText(record.primary_region);
      sprintf(reply, "%d %s [%s] %s +%u",
        index,
        record.name,
        province ? province->abbr : "??",
        primary ? primary : "-",
        record.extra_count);
    } else {
      strcpy(reply, "Err - not found");
    }
  } else if (n >= 3 && strcmp(parts[1], "get") == 0) {
    uint16_t index = _atoi(parts[2]);
    DutchRegionDbEntry entry;
    DutchRegionDbRecord record;
    if (DutchRegionDb::readEntry(index, entry) && DutchRegionDb::readRecord(index, record)) {
      const DutchRegionDbProvince* province = DutchRegionDb::provinceById(record.province_id);
      char* dp = reply;
      char* end = reply + 160;
      int written = snprintf(dp, end - dp, "%u %s [%s] ",
        index,
        record.name,
        province ? province->abbr : "??");
      if (written > 0) {
        dp += min(written, (int)(end - dp));
        dp = appendCodeText(dp, end, entry.primary_region);
        for (uint8_t i = 0; i < entry.extra_count && dp < end - 1; i++) {
          dp = appendCodeText(dp, end, DutchRegionDb::extraRegionCode(entry, i));
        }
      }
    } else {
      strcpy(reply, "Err - not found");
    }
  } else {
    strcpy(reply, "Err - use info, provinces, find, get, code");
  }
}
#endif

static char* skipSpaces(char* s) {
  while (*s == ' ') s++;
  return s;
}

static void rtrimSpaces(char* s) {
  char* e = s + strlen(s);
  while (e > s && e[-1] == ' ') *--e = '\0';
}

static char* takeToken(char** cursor) {
  char* p = skipSpaces(*cursor);
  if (*p == '\0') { *cursor = p; return nullptr; }
  char* tok = p;
  while (*p && *p != ' ') p++;
  if (*p) *p++ = '\0';
  *cursor = p;
  return tok;
}

static char* splitNameJump(char* tok) {
  for (char* q = tok; *q; q++) {
    if (*q == '|' || *q == ',') {
      *q = '\0';
      char* jump = skipSpaces(q + 1);
      rtrimSpaces(jump);
      return jump;
    }
  }
  return nullptr;
}

static bool processRegionDefSegment(RegionMap* map, char* tok, RegionEntry** cursor, char* reply) {
  char* jump = splitNameJump(tok);
  char* name = skipSpaces(tok);
  if (*name == '\0') { snprintf(reply, 160, "Err - empty name"); return false; }
  if (jump && *jump == '\0') { snprintf(reply, 160, "Err - empty jump"); return false; }

  RegionEntry* r = map->putRegion(name, (*cursor)->id);
  if (r == NULL) { snprintf(reply, 160, "Err - put failed: %s", name); return false; }
  r->flags = 0;

  if (jump) {
    RegionEntry* j = map->findByNamePrefix(jump);
    if (j == NULL) { snprintf(reply, 160, "Err - unknown jump: %s", jump); return false; }
    *cursor = j;
  } else {
    *cursor = r;
  }
  return true;
}

void CommonCLI::handleRegionCmd(char* command, char* reply) {
  reply[0] = 0;

  // `region def`: must run before parseTextParts mutates the buffer
  char* cmd = skipSpaces(command);
  if (strncmp(cmd, "region def", 10) == 0 && (cmd[10] == ' ' || cmd[10] == '\0')) {
    char* payload = skipSpaces(cmd + 10);
    rtrimSpaces(payload);
    if (*payload == '\0') { snprintf(reply, 160, "Err - empty def"); return; }

    RegionEntry* cursor = &_region_map->getWildcard();
    for (char* tok; (tok = takeToken(&payload)) != nullptr; ) {
      if (!processRegionDefSegment(_region_map, tok, &cursor, reply)) return;
    }
    _region_map->exportTo(reply, 160);
    return;
  }

  const char* parts[4];
  int n = mesh::Utils::parseTextParts(command, parts, 4, ' ');
  if (n == 1 || (n == 2 && strcmp(parts[1], "tree") == 0)) {
    _region_map->exportTo(reply, 160);
  } else if (n >= 2 && strcmp(parts[1], "load") == 0) {
    _callbacks->startRegionsLoad();
  } else if (n >= 2 && strcmp(parts[1], "save") == 0) {
    _prefs->discovery_mod_timestamp = getRTCClock()->getCurrentTime();   // this node is now 'modified' (for discovery info)
    savePrefs();
    bool success = _callbacks->saveRegions();
    strcpy(reply, success ? "OK" : "Err - save failed");
  } else if (n >= 3 && strcmp(parts[1], "allowf") == 0) {
    auto region = _region_map->findByNamePrefix(parts[2]);
    if (region) {
      region->flags &= ~REGION_DENY_FLOOD;
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Err - unknown region");
    }
  } else if (n >= 3 && strcmp(parts[1], "denyf") == 0) {
    auto region = _region_map->findByNamePrefix(parts[2]);
    if (region) {
      region->flags |= REGION_DENY_FLOOD;
      strcpy(reply, "OK");
    } else {
      strcpy(reply, "Err - unknown region");
    }
  } else if (n >= 3 && strcmp(parts[1], "get") == 0) {
    auto region = _region_map->findByNamePrefix(parts[2]);
    if (region) {
      auto parent = _region_map->findById(region->parent);
      if (parent && parent->id != 0) {
        sprintf(reply, " %s (%s) %s", region->name, parent->name, (region->flags & REGION_DENY_FLOOD) ? "" : "F");
      } else {
        sprintf(reply, " %s %s", region->name, (region->flags & REGION_DENY_FLOOD) ? "" : "F");
      }
    } else {
      strcpy(reply, "Err - unknown region");
    }
  } else if (n >= 3 && strcmp(parts[1], "home") == 0) {
    auto home = _region_map->findByNamePrefix(parts[2]);
    if (home) {
      _region_map->setHomeRegion(home);
      sprintf(reply, " home is now %s", home->name);
    } else {
      strcpy(reply, "Err - unknown region");
    }
  } else if (n == 2 && strcmp(parts[1], "home") == 0) {
    auto home = _region_map->getHomeRegion();
    sprintf(reply, " home is %s", home ? home->name : "*");
  } else if (n >= 3 && strcmp(parts[1], "default") == 0) {
    if (strcmp(parts[2], "<null>") == 0) {
      _region_map->setDefaultRegion(NULL);
      _callbacks->onDefaultRegionChanged(NULL);
      _callbacks->saveRegions();  // persist in one atomic step
      sprintf(reply, " default scope is now <null>");
    } else {
      auto def = _region_map->findByNamePrefix(parts[2]);
      if (def == NULL) {
        def = _region_map->putRegion(parts[2], 0);  // auto-create the default region
      }
      if (def) {
        def->flags = 0;   // make sure allow flood enabled
        _region_map->setDefaultRegion(def);
        _callbacks->onDefaultRegionChanged(def);
        _callbacks->saveRegions();  // persist in one atomic step
        sprintf(reply, " default scope is now %s", def->name);
      } else {
        strcpy(reply, "Err - region table full");
      }
    }
  } else if (n == 2 && strcmp(parts[1], "default") == 0) {
    auto def = _region_map->getDefaultRegion();
    sprintf(reply, " default scope is %s", def ? def->name : "<null>");
  } else if (n >= 3 && strcmp(parts[1], "put") == 0) {
    auto parent = n >= 4 ? _region_map->findByNamePrefix(parts[3]) : &(_region_map->getWildcard());
    if (parent == NULL) {
      strcpy(reply, "Err - unknown parent");
    } else {
      auto region = _region_map->putRegion(parts[2], parent->id);
      if (region == NULL) {
        strcpy(reply, "Err - unable to put");
      } else {
        region->flags = 0;   // New default: enable flood
        strcpy(reply, "OK - (flood allowed)");
      }
    }
  } else if (n >= 3 && strcmp(parts[1], "remove") == 0) {
    auto region = _region_map->findByName(parts[2]);
    if (region) {
      if (_region_map->removeRegion(*region)) {
        strcpy(reply, "OK");
      } else {
        strcpy(reply, "Err - not empty");
      }
    } else {
      strcpy(reply, "Err - not found");
    }
  } else if (n >= 3 && strcmp(parts[1], "list") == 0) {
    uint8_t mask = 0;
    bool invert = false;
    
    if (strcmp(parts[2], "allowed") == 0) {
      mask = REGION_DENY_FLOOD;
      invert = false;  // list regions that DON'T have DENY flag
    } else if (strcmp(parts[2], "denied") == 0) {
      mask = REGION_DENY_FLOOD;
      invert = true;   // list regions that DO have DENY flag
    } else {
      strcpy(reply, "Err - use 'allowed' or 'denied'");
      return;
    }
    
    int len = _region_map->exportNamesTo(reply, 160, mask, invert);
    if (len == 0) {
      strcpy(reply, "-none-");
    }
  } else {
    strcpy(reply, "Err - ??");
  }
}
