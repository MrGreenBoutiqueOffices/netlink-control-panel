#pragma once
#include <Preferences.h>
#include "panel_ota.h"
#include "github_download.h"
#include "github_release.h"
#include "update_attempt.h"

class PanelUpdater {
 public:
  explicit PanelUpdater(PanelOta &ota,bool trusted):ota(ota),trusted(trusted) {}
  void begin();
  bool check(bool idle,bool wifi);
  bool install(bool idle,bool wifi,bool healthy);
  void tick(bool healthy,bool wifi);
  bool busy() const;
  bool available() const { return stage==Ready; }
  int percent() const { return stage==Download?ota.percent():(stage==Finishing || stage==BootCheck?100:0); }
  const char *status() const { return message; }
  const char *version() const { return authorization.version; }
 private:
  enum Stage { Idle, Clock, Release, Authorization, Manifest, Ready, Download, Finishing, BootCheck, Failed };
  Stage stage=Idle;
  PanelOta &ota;
  bool trusted=false,storageReady=false,failedJob=false;
  Preferences nvs;
  GithubDownload network;
  GithubRelease release;
  UpdateAuthorization authorization={};
  UpdateAttempt attempt;
  char message[80]="Controleer op nieuwe firmware";
  char envelope[1025]={};
  uint8_t *metadata=nullptr;
  size_t used=0,capacity=0;
  uint32_t started=0,healthySince=0;
  bool save(UpdatePhase phase);
  bool fetch(const char *url,Stage next,size_t limit,bool asset=true);
  void complete(bool healthy);
  bool writeChunk(const GithubDownload::Event &event,bool healthy);
  void fail(const char *reason);
};
