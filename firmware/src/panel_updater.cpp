#include "panel_updater.h"
#include "panel_version.h"
#include <mbedtls/base64.h>
#include <time.h>

bool PanelUpdater::busy() const {
  return network.active() || stage==Clock || stage==Release || stage==Authorization || stage==Manifest ||
    stage==Download || stage==Finalizing || stage==Finishing || stage==BootCheck;
}
bool PanelUpdater::save(UpdatePhase phase) {
  attempt.phase=phase;attempt.checksum=attempt.crc();
  return storageReady && nvs.putBytes("attempt",&attempt,sizeof(attempt))==sizeof(attempt);
}
void PanelUpdater::begin() {
  storageReady=nvs.begin("panel-update",false);
  if(!storageReady || !network.begin()) { storageReady=false;fail("Updateopslag niet beschikbaar");return; }
  size_t length=nvs.getBytesLength("attempt");
  if(!length)return;
  if(length!=sizeof(attempt) || nvs.getBytes("attempt",&attempt,sizeof(attempt))!=sizeof(attempt) || !attempt.valid()) {
    storageReady=false;fail("Updateopslag ongeldig; USB-herstel nodig");return;
  }
  StaticJsonDocument<768> boot;ota.describe(boot.to<JsonObject>());
  const char *running=boot["image_sha256"] | "";
  UpdatePhase reconciled=attempt.reconcile(running,ota.pending());
  if(reconciled==UpdatePhase::BootPending) {stage=BootCheck;presentation=PanelUpdateView::Verifying;strlcpy(message,"Nieuwe firmware lokaal controleren",sizeof(message));return;}
  if(reconciled!=attempt.phase && !save(reconciled)) {fail("Update-uitkomst niet opgeslagen");return;}
  presentation=reconciled==UpdatePhase::Succeeded?PanelUpdateView::Current:PanelUpdateView::InstallFailed;
  if(reconciled==UpdatePhase::Succeeded)strlcpy(message,"Update geslaagd",sizeof(message));
  if(reconciled==UpdatePhase::RolledBack)strlcpy(message,"Vorige firmware hersteld",sizeof(message));
  if(reconciled==UpdatePhase::Interrupted)strlcpy(message,"Update onderbroken; controleer opnieuw",sizeof(message));
  if(reconciled==UpdatePhase::Failed)strlcpy(message,"Update mislukt; controleer opnieuw",sizeof(message));
}
void PanelUpdater::fail(const char *reason) {
  presentation=stage==Download || stage==Finalizing || stage==Finishing || stage==BootCheck?PanelUpdateView::InstallFailed:PanelUpdateView::CheckFailed;
  network.cancel();
  ota.abort();
  free(metadata);metadata=nullptr;used=capacity=0;
  if(stage==Download || stage==Finalizing || stage==Finishing)save(UpdatePhase::Failed);
  stage=Failed;failedJob=true;strlcpy(message,reason,sizeof(message));
}
bool PanelUpdater::fetch(const char *url,Stage next,size_t limit,bool asset) {
  free(metadata);metadata=nullptr;used=0;capacity=limit;
  if(next!=Download) {
    metadata=static_cast<uint8_t *>(ps_malloc(limit+1));
    if(!metadata) {fail("Onvoldoende geheugen voor update");return false;}
  }
  if(!network.start(url,limit,asset,next==Download?180000:30000)) {fail("Updatebron niet beschikbaar");return false;}
  stage=next;started=millis();failedJob=false;return true;
}
bool PanelUpdater::check(bool idle,bool wifi) {
  if(busy())return false;
  auto reject=[&](const char *reason) {
    stage=Failed;presentation=PanelUpdateView::CheckFailed;strlcpy(message,reason,sizeof(message));return false;
  };
  if(!idle || ota.receiving() || ota.pending() || ota.committed())return reject("Wacht tot het paneel vrij is");
  if(!storageReady)return reject("Updateopslag niet beschikbaar");
  if(!trusted)return reject("Updatesleutel nog niet ingesteld");
  if(!wifi)return reject("Verbind eerst met wifi");
  release=GithubRelease{};authorization=UpdateAuthorization{};envelope[0]=0;
  strlcpy(message,"GitHub-release controleren...",sizeof(message));
  // Certificate validity needs a clock. No TLS request is made without it.
  configTime(0,0,"time.cloudflare.com","pool.ntp.org");
  stage=Clock;presentation=PanelUpdateView::Checking;started=millis();return true;
}
bool PanelUpdater::install(bool idle,bool wifi,bool healthy) {
  if(stage!=Ready || network.active() || !idle || !wifi || !healthy || ota.receiving() || ota.pending() || ota.committed())return false;
  attempt=UpdateAttempt{};
  strlcpy(attempt.image,authorization.imageSha256,sizeof(attempt.image));strlcpy(attempt.version,authorization.version,sizeof(attempt.version));
  for(size_t i=0;i<32;i++)sprintf(attempt.identity+2*i,"%02x",authorization.identity[i]);
  // Persist intent before touching the inactive slot.
  if(!save(UpdatePhase::Downloading)) {fail("Updatepoging niet opgeslagen");return false;}
  StaticJsonDocument<1536> request;StaticJsonDocument<384> response;
  if(deserializeJson(request,envelope)) {fail("Updateautorisatie ongeldig");return false;}
  request["type"]="ota_begin_signed";request["id"]=1;
  ota.handle(request,response,healthy);
  if(response["ok"]!=true) {save(UpdatePhase::Failed);fail("Update kan niet worden gestart");return false;}
  if(!fetch(release.firmware,Download,authorization.size)) {save(UpdatePhase::Failed);return false;}
  presentation=PanelUpdateView::Downloading;strlcpy(message,"Firmware downloaden...",sizeof(message));return true;
}
void PanelUpdater::complete(bool healthy) {
  if(stage==Release) {
    // Discard unneeded release notes and API links before allocating the JSON tree.
    StaticJsonDocument<384> filter;filter["id"]=true;filter["tag_name"]=true;filter["draft"]=true;filter["prerelease"]=true;
    for(const char *name:{"id","name","state","size"})filter["assets"][0][name]=true;
    DynamicJsonDocument doc(12288);
    if(deserializeJson(doc,reinterpret_cast<const char *>(metadata),used,DeserializationOption::Filter(filter)) || !release.parse(doc)) {
      fail("Geen volledige ondertekende release");return;
    }
    fetch(release.authorization,Authorization,1024);return;
  }
  if(stage==Authorization) {
    StaticJsonDocument<1536> doc;
    if(deserializeJson(doc,reinterpret_cast<const char *>(metadata),used) || !ota.authorize(doc,authorization)) {fail("Handtekening of hardware klopt niet");return;}
    memcpy(envelope,metadata,used);envelope[used]=0;
    fetch(release.manifest,Manifest,16384);return;
  }
  if(stage==Manifest) {
    uint8_t digest[32];char actual[65];mbedtls_sha256_ret(metadata,used,digest,0);
    for(size_t i=0;i<32;i++)sprintf(actual+2*i,"%02x",digest[i]);
    DynamicJsonDocument doc(16384);
    if(strcmp(actual,authorization.manifestSha256) || deserializeJson(doc,reinterpret_cast<const char *>(metadata),used) ||
       !githubManifestMatches(doc,release,authorization)) {fail("Release komt niet overeen met handtekening");return;}
    free(metadata);metadata=nullptr;capacity=used=0;
    if(!strcmp(authorization.version,PANEL_FIRMWARE_VERSION)) {stage=Idle;presentation=PanelUpdateView::Current;strlcpy(message,"Je hebt de nieuwste firmware",sizeof(message));return;}
    stage=Ready;presentation=PanelUpdateView::Available;strlcpy(message,"Nieuwe firmware beschikbaar",sizeof(message));return;
  }
  if(stage==Download) {
    if(used!=authorization.size || !ota.receiving() || !healthy) {fail("Firmwaredownload onvolledig");return;}
    stage=Finalizing;presentation=PanelUpdateView::Installing;return;
  }
  if(stage==Finalizing) {
    if(!healthy) {fail("Lokale firmwarecontrole mislukt");return;}
    // Persist expected candidate before changing boot selection. A reset before
    // activation reconciles to the still-running old image on the next boot.
    if(!save(UpdatePhase::BootPending)) {fail("Bootcontrole niet opgeslagen");return;}
    StaticJsonDocument<128> request;StaticJsonDocument<384> response;
    request["type"]="ota_finish";request["id"]=1;ota.handle(request,response,healthy);
    if(response["ok"]!=true) {fail("Firmwarecontrole mislukt");return;}
    stage=Finishing;presentation=PanelUpdateView::Installed;strlcpy(message,"Update starten...",sizeof(message));
  }
}
bool PanelUpdater::cancel() {
  if(!cancelable())return false;
  network.cancel();ota.abort();save(UpdatePhase::Interrupted);
  stage=Idle;presentation=PanelUpdateView::Idle;failedJob=true;strlcpy(message,"Update geannuleerd",sizeof(message));return true;
}
void PanelUpdater::tick(bool healthy,bool wifi) {
  if(stage==Finalizing) {complete(healthy);return;}
  if(stage==BootCheck) {
    if(!healthy)healthySince=0;
    else if(!healthySince)healthySince=millis();
    else if(millis()-healthySince>=3000) {
      if(!ota.confirmLocal(attempt.image,true))return; // Existing 90s rollback timer remains armed on failure.
      if(!save(UpdatePhase::Succeeded)) {fail("Update-uitkomst niet opgeslagen");return;}
      stage=Idle;presentation=PanelUpdateView::Current;strlcpy(message,"Update geslaagd",sizeof(message));
    }
    return;
  }
  if(stage==Clock) {
    if(!wifi) {fail("Wifi niet verbonden");return;}
    if(time(nullptr)>1704067200)fetch(PanelLatestRelease,Release,65536,false);
    else if(millis()-started>15000)fail("Tijd niet beschikbaar; probeer opnieuw");
  }
  if(network.active() && (!wifi || millis()-started>(stage==Download?180000U:30000U)))fail("Download onderbroken; probeer opnieuw");
  GithubDownload::Event event;
  // Bounded work per loop keeps touch, rendering and USB processing responsive.
  for(int budget=0;budget<4 && network.poll(event);budget++) {
    if(event.done) {
      if(!failedJob) {if(event.ok)complete(healthy);else fail("GitHub niet bereikbaar of download afgebroken");}
      break;
    }
    if(failedJob)continue;
    if(event.length>capacity-used) {fail("Updatebestand te groot");continue;}
    if(stage==Download) {
      if(!writeChunk(event,healthy)) {fail("Firmware schrijven mislukt");continue;}
    } else memcpy(metadata+used,event.bytes,event.length);
    used+=event.length;
    if(metadata)metadata[used]=0;
  }
}

// Keep chunk encoding off the metadata/crypto call stack.
bool PanelUpdater::writeChunk(const GithubDownload::Event &event,bool healthy) {
  StaticJsonDocument<1536> request;StaticJsonDocument<384> response;
  unsigned char encoded[685];size_t length=0;
  if(mbedtls_base64_encode(encoded,sizeof(encoded),&length,event.bytes,event.length))return false;
  encoded[length]=0;
  request["type"]="ota_chunk";request["id"]=1;request["offset"]=used;request["data"]=reinterpret_cast<char *>(encoded);
  ota.handle(request,response,healthy);
  return response["ok"]==true;
}
