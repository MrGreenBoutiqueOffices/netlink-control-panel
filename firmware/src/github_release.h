#pragma once
#include <ArduinoJson.h>
#include <stdio.h>
#include <string.h>
#include "signed_update.h"

constexpr const char *PanelRepository = "MrGreenBoutiqueOffices/netlink-control-panel";
constexpr const char *PanelLatestRelease = "https://api.github.com/repos/MrGreenBoutiqueOffices/netlink-control-panel/releases/latest";

// Only canonical HTTPS authorities; no ports, credentials, fragments or suffix matches.
inline bool githubUpdateUrl(const char *url) {
  if (!url || strlen(url)>2048 || strncmp(url,"https://",8)) return false;
  const char *end=strchr(url+8,'/'); if(!end)return false;
  const char *hosts[]={"api.github.com","github.com","release-assets.githubusercontent.com","objects.githubusercontent.com"};
  for(const char *host:hosts) if(size_t(end-url-8)==strlen(host) && !memcmp(url+8,host,strlen(host))) {
    for(const char *p=end;*p;p++) if(static_cast<unsigned char>(*p)<=32 || *p=='#' || *p=='\\')return false;
    return true;
  }
  return false;
}

struct GithubRelease {
  uint64_t id=0;
  char tag[33]={};
  char firmware[256]={}, manifest[256]={}, authorization[256]={};
  uint32_t firmwareSize=0;
  bool parse(JsonDocument &doc) {
    *this=GithubRelease{};
    if(!doc["id"].is<uint64_t>() || !(id=doc["id"]) || !doc["draft"].is<bool>() || !doc["prerelease"].is<bool>() || doc["draft"]!=false || doc["prerelease"]!=false ||
       !doc["tag_name"].is<const char *>() || !doc["assets"].is<JsonArray>())return false;
    const char *t=doc["tag_name"];if(t[0]!='v' || strlen(t)>32 || strlen(t)<2)return false;
    for(const char *p=t+1;*p;p++)if(!((*p>='0' && *p<='9') || *p=='.'))return false;
    strcpy(tag,t);
    unsigned found=0;
    for(JsonObject asset:doc["assets"].as<JsonArray>()) {
      const char *name=asset["name"] | "";char *out=nullptr;unsigned bit=0;uint32_t limit=0;
      if(!strcmp(name,"firmware.bin")){out=firmware;bit=1;limit=0x300000;}
      if(!strcmp(name,"manifest.json")){out=manifest;bit=2;limit=16384;}
      if(!strcmp(name,"authorization.json")){out=authorization;bit=4;limit=1024;}
      if(!out)continue;
      if((found&bit) || !asset["id"].is<uint64_t>() || !asset["id"].as<uint64_t>() ||
         !asset["size"].is<uint32_t>() || !asset["size"].as<uint32_t>() || asset["size"].as<uint32_t>()>limit ||
         strcmp(asset["state"] | "","uploaded"))return false;
      snprintf(out,256,"https://api.github.com/repos/%s/releases/assets/%llu",PanelRepository,
        static_cast<unsigned long long>(asset["id"].as<uint64_t>()));
      if(bit==1)firmwareSize=asset["size"];
      found|=bit;
    }
    return found==7;
  }
};

// Manifest bytes are hashed against the signed record before calling this function.
inline bool githubManifestMatches(JsonDocument &doc,const GithubRelease &release,const UpdateAuthorization &a) {
  return doc["schema"]==1 &&
    !strcmp(doc["firmware"]["profile"] | "","lilygo-s3-long-cst3530:p1:ota3m-v1") &&
    !strcmp(doc["compatibility"]["board_profile"] | "","lilygo-s3-long-cst3530") &&
    !strcmp(doc["compatibility"]["board_revision"] | "",a.boardRevision) &&
    !strcmp(doc["compatibility"]["partition_layout"] | "","ota3m-v1") &&
    doc["compatibility"]["protocol_min"]==a.protocolMin && doc["compatibility"]["protocol_max"]==a.protocolMax && a.counter==release.id && release.firmwareSize==a.size &&
    !strcmp(release.tag+1,a.version) && !strcmp(doc["source"]["repository"] | "",PanelRepository) &&
    !strcmp(doc["source"]["tag"] | "",release.tag) && !strcmp(doc["source"]["commit"] | "",a.commit) &&
    doc["firmware"]["size"]==a.size && !strcmp(doc["firmware"]["version"] | "",a.version) &&
    !strcmp(doc["firmware"]["sha256"] | "",a.sha256) && !strcmp(doc["firmware"]["image_sha256"] | "",a.imageSha256) &&
    doc["artifacts"]["firmware.bin"]["size"]==a.size && !strcmp(doc["artifacts"]["firmware.bin"]["sha256"] | "",a.sha256) &&
    !strcmp(doc["signature"]["status"] | "","signed");
}
