#pragma once

#include <helpers/ui/DisplayDriver.h>
#include <helpers/CommonCLI.h>
#include <helpers/SensorManager.h>
#include <MeshCore.h>

#ifndef LOCATION_TRACKER_INTERVAL_SECS
  #define LOCATION_TRACKER_INTERVAL_SECS 0
#endif

class UITask {
  DisplayDriver* _display;
  unsigned long _next_read, _next_refresh, _auto_off;
  int _prevBtnState;
  NodePrefs* _node_prefs;
  SensorManager* _sensors;
  mesh::MainBoard* _board;
  char _version_info[32];

  void renderCurrScreen();
public:
  UITask(DisplayDriver& display) : _display(&display) { _next_read = _next_refresh = _auto_off = 0; _sensors = NULL; _board = NULL; }
  void begin(NodePrefs* node_prefs, SensorManager* sensors, mesh::MainBoard* board, const char* build_date, const char* firmware_version);

  void loop();
};
