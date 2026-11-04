#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <limits.h>

// UI-only configuration. Desk presets, device state and credentials are excluded.
struct PanelSettings {
  int brightness = 100, dimMinutes = 1;
  bool rotated = false;
  bool valid() const { return brightness >= 10 && brightness <= 100 && (dimMinutes == 0 || dimMinutes == 1 || dimMinutes == 2 || dimMinutes == 5); }
  bool operator==(const PanelSettings &other) const { return brightness == other.brightness && dimMinutes == other.dimMinutes && rotated == other.rotated; }
  bool operator!=(const PanelSettings &other) const { return !(*this == other); }
};

// Storage provides read(slot, bytes, size) and atomic write(slot, bytes, size).
// Alternating complete records retain the preceding revision if a write fails.
template<class Storage> class PanelSettingsJournal {
 public:
  static constexpr size_t RecordSize = 20;
  PanelSettings applied;
  uint32_t revision = 0;
  bool writable = true, writeFailed = false;
  explicit PanelSettingsJournal(Storage &value): storage(value) {}
  void load() {
    applied = PanelSettings{}; revision = 0; active = -1; writable = true; writeFailed = false;
    for(int slot = 0; slot < 2; ++slot) {
      uint8_t bytes[RecordSize] = {}; PanelSettings candidate; uint32_t rev = 0;
      if(!storage.read(slot, bytes, sizeof(bytes))) continue;
      // A future schema must not be silently replaced by a downgraded firmware.
      if(bytes[0] == 'N' && bytes[1] == 'P' && bytes[2] > 1) writable = false;
      if(decode(bytes, candidate, rev) && (active < 0 || rev > revision)) { applied = candidate; revision = rev; active = slot; }
    }
  }
  bool save(const PanelSettings &value) {
    if(!value.valid()) return false;
    if(value == applied) return true;
    if(!writable || revision == UINT32_MAX) { writeFailed = true; return false; }
    uint8_t bytes[RecordSize] = {}, verified[RecordSize] = {};
    encode(value, revision + 1, bytes);
    int slot = active == 0 ? 1 : 0;
    if(!storage.write(slot, bytes, sizeof(bytes)) || !storage.read(slot, verified, sizeof(verified)) || memcmp(bytes, verified, sizeof(bytes))) { writeFailed = true; return false; }
    applied = value; ++revision; active = slot; writeFailed = false; return true;
  }
 private:
  Storage &storage;
  int active = -1;
  static uint32_t number(const uint8_t *p) { return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24; }
  static void number(uint8_t *p, uint32_t n) { for(int i=0;i<4;++i)p[i]=uint8_t(n >> (8*i)); }
  static uint32_t checksum(const uint8_t *p) { uint32_t hash = 2166136261u; for(size_t i=0;i<RecordSize-4;++i)hash=(hash^p[i])*16777619u; return hash; }
  static void encode(const PanelSettings &value, uint32_t rev, uint8_t *p) {
    p[0]='N';p[1]='P';p[2]=1;p[3]=0;number(p+4,rev);p[8]=value.brightness;p[9]=value.rotated?1:0;p[10]=value.dimMinutes;number(p+16,checksum(p));
  }
  static bool decode(const uint8_t *p, PanelSettings &value, uint32_t &rev) {
    if(p[0]!='N' || p[1]!='P' || p[2]!=1 || p[3]!=0 || number(p+16)!=checksum(p))return false;
    for(int i=11;i<16;++i)if(p[i])return false;
    rev=number(p+4);value.brightness=p[8];value.rotated=p[9]!=0;value.dimMinutes=p[10];
    return rev>0 && p[9]<=1 && value.valid();
  }
};
