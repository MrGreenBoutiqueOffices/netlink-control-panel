#pragma once
#include <stdint.h>
#include <stddef.h>
#include "device_state.h"
#include "panel_settings.h"

// Self-contained local simulation. It has no desk, monitor or network transport.
class PanelDemo {
 public:
  static constexpr int MinHeightMm = 620;
  static constexpr int MaxHeightMm = 1270;
  static constexpr bool validHeight(int mm) { return mm >= MinHeightMm && mm <= MaxHeightMm; }
  static constexpr int clampHeight(int mm) { return mm < MinHeightMm ? MinHeightMm : mm > MaxHeightMm ? MaxHeightMm : mm; }
  enum Screen { Desk, Confirm, Moving, Offline, Menu, Monitor, Presets, Settings, SettingsRotated, Boot, Connecting, Updating, Updated, UpdateFailed, Obstructed, Calibrate, Sleep, Updates };
  Screen screen = Desk;
  int height = 740, sit = 740, stand = 1120, target = 780;
  int monitor = 70, brightness = 100, input = 0, dimMinutes = 1;
  bool monitorOn = true, connected = true, rotated = false;
  int progress = 64;
  bool checkingUpdate = false;
  enum UpdateAction { NoUpdateAction, CheckUpdate, InstallUpdate };
  UpdateAction updateAction=NoUpdateAction;
  char updateStatus[80]="Controleer op nieuwe firmware", updateVersion[32]={};
  bool updateAvailable=false;
  int updateProgress=0;
  void updateView(const char *status,const char *version,bool available,int progress);
  bool idleForUpdate() const { return !finger && !manualHold && !calibrating && screen!=Moving && screen!=Confirm; }
  bool dirty = true, dimmed = false, busy = false;
  bool readOnly = false;
  PanelDeviceState deviceState;
  PanelSettings settings() const { PanelSettings value;value.brightness=brightness;value.dimMinutes=dimMinutes;value.rotated=rotated;return value; }
  void applySettings(const PanelSettings &value) { if(!value.valid())return;brightness=value.brightness;dimMinutes=value.dimMinutes;rotated=value.rotated;if(screen==Settings || screen==SettingsRotated)screen=rotated?SettingsRotated:Settings;dirty=true; }
  void setDeviceState(const PanelDeviceState &value);
  void draw(uint16_t *pixels) const;
  void drawStatus(uint16_t *pixels, Screen phase, int percent, bool checking = false) const;
  void touchDown(int x, int y, uint32_t now);
  void touchUp(uint32_t now);
  void touchMove(int x, int y, uint32_t now);
  bool tick(uint32_t now);
  void setBusy(bool value);
  bool scene(int index, uint32_t now, bool preserveSettings = false);
  void setHeight(int value);
  void freeze(uint32_t now) { freezeUntil = now + 5000; }
  const char *name() const;
 private:
  int downX = 0, downY = 0, motionKind = 0, savedPreset = 0;
  uint32_t downAt = 0, lastTick = 0, lastTouch = 0, freezeUntil = 0;
  bool finger = false, consumed = false, manualHold = false, calibrating = false;
  void move(int value, int kind);
  void tap(int x, int y, uint32_t held);
};
