#pragma once
#include <ArduinoJson.h>
#include <stdint.h>
#include <string.h>
#include "device_state.h"

// Transport-independent v2 endpoint. No actuation, provisioning or demo writes.
class ProductionSession {
 public:
  char session[33] = {};
  uint32_t revision = 0, deviceRevision = 0, deviceAt = 0, deviceLease = 0;
  PanelDeviceState devices;
  bool connected() const { return session[0] != 0; }
  void clear() { session[0] = 0; revision = deviceRevision = deviceLease = 0;devices=PanelDeviceState{}; }
  bool expire(uint32_t now) {
    if(!deviceLease || uint32_t(now-deviceAt)<deviceLease)return false;
    deviceLease=0;devices=PanelDeviceState{};return true;
  }
  static bool bounded(JsonVariantConst value,size_t max) {
    if(!value.is<const char*>())return false;const char *s=value.as<const char*>();
    if(!*s || strlen(s)>max)return false;for(;*s;++s)if(*s<32 || *s>126)return false;return true;
  }
  static bool token(const char *value) {
    if (!value || strlen(value) != 32) return false;
    for (const char *p=value; *p; ++p) if (!((*p>='0' && *p<='9') || (*p>='a' && *p<='f'))) return false;
    return true;
  }
  bool matches(JsonDocument &message) const {
    return connected() && message["session"].is<const char *>() && !strcmp(message["session"], session);
  }
  // true means this valid request may renew session liveness.
  bool handle(JsonDocument &message, JsonDocument &out, uint32_t now,
              const char *panel, const char *firmware, const char *boot,
              bool healthy, const char *bootState) {
    out.clear();out["v"]=2;
    if (!message["id"].is<int>() || message["id"].as<int>()<=0) return false;
    out["id"]=message["id"];
    if (token(message["session"] | "")) out["session"]=message["session"];
    out["type"]="error";out["code"]="invalid_request";
    if (!message["type"].is<const char *>()) return false;
    const char *type=message["type"];
    if (!strcmp(type,"hello")) {
      if (!token(message["session"] | "")) return false;
      if (!message["protocol_min"].is<int>() || !message["protocol_max"].is<int>() ||
          message["protocol_min"].as<int>()>2 || message["protocol_max"].as<int>()<2 ||
          message["protocol_min"].as<int>()<1 || message["protocol_max"].as<int>()<message["protocol_min"].as<int>()) {
        out["code"]="incompatible_protocol";return false;
      }
      clear();strcpy(session,message["session"]);
      out.clear();out["v"]=2;out["type"]="hello";out["id"]=message["id"];out["session"]=session;
      out["panel_id"]=panel;out["board_profile"]="lilygo-s3-long-cst3530";
      out["board_revision"]="unverified";out["firmware"]=firmware;
      out["protocol_min"]=2;out["protocol_max"]=2;out["boot_id"]=boot;
      out["boot_state"]=bootState;out["self_test_ok"]=healthy;
      JsonArray caps=out.createNestedArray("capabilities");caps.add("panel.status.v1");caps.add("device.state.v1");
      out.createNestedArray("actions"); // No MQTT adapter yet: advertise no actions.
      return true;
    }
    if (!matches(message)) { out["code"]="session_required";return false; }
    out["session"]=session;
    if (!strcmp(type,"state.get")) {
      out.clear();out["v"]=2;out["type"]="state.snapshot";out["id"]=message["id"];out["session"]=session;
      out["revision"]=++revision;out["sampled_uptime_ms"]=now;out["valid_for_ms"]=3500;
      out["state"]["self_test_ok"]=healthy;out["state"]["mode"]=deviceRevision?"read_only":"standalone_demo";
      out["state"]["desk"]=nullptr;out["state"]["monitor"]=nullptr;
      return true;
    }
    if (!strcmp(type,"device.state")) {
      if(!message["revision"].is<uint32_t>() || message["revision"].as<uint32_t>()<=deviceRevision ||
         !message["valid_for_ms"].is<int>() || message["valid_for_ms"].as<int>()<1 || message["valid_for_ms"].as<int>()>3000 ||
         !message.containsKey("desk") || !message.containsKey("monitor"))return false;
      PanelDeviceState next;
      if(!message["desk"].isNull()) {
        JsonVariantConst desk=message["desk"];
        if(!desk.is<JsonObjectConst>() || !desk["height_mm"].is<int>() || desk["height_mm"].as<int>()<0 || desk["height_mm"].as<int>()>3000 || !desk["fresh"].is<bool>())return false;
        next.heightKnown=true;next.heightMm=desk["height_mm"];next.heightFresh=desk["fresh"];
      }
      if(!message["monitor"].isNull()) {
        JsonVariantConst mon=message["monitor"];
        if(!mon.is<JsonObjectConst>() || !bounded(mon["bus"],8) || !mon["fresh"].is<bool>() ||
           !mon.as<JsonObjectConst>().containsKey("brightness") || !mon.as<JsonObjectConst>().containsKey("power") || !mon.as<JsonObjectConst>().containsKey("source"))return false;
        const char *bus=mon["bus"];for(const char *c=bus;*c;++c)if(*c<'0' || *c>'9')return false;
        if(!mon["brightness"].isNull()) { if(!mon["brightness"].is<int>() || mon["brightness"].as<int>()<0 || mon["brightness"].as<int>()>100)return false;next.monitorBrightness=mon["brightness"]; }
        if(!mon["power"].isNull()) { const char *power=mon["power"] | "";if(strcmp(power,"on") && strcmp(power,"off") && strcmp(power,"standby"))return false;strcpy(next.monitorPower,power); }
        if(!mon["source"].isNull()) { if(!bounded(mon["source"],24))return false;strcpy(next.monitorSource,mon["source"]); }
        next.monitorKnown=true;next.monitorFresh=mon["fresh"];strcpy(next.monitorBus,bus);
      }
      devices=next;deviceRevision=message["revision"];deviceAt=now;deviceLease=message["valid_for_ms"];
      out.clear();out["v"]=2;out["type"]="device.state.ack";out["id"]=message["id"];out["session"]=session;out["revision"]=deviceRevision;
      return true;
    }
    if (!strcmp(type,"action.request")) {
      out["type"]="action.result";out["stage"]="rejected";out["code"]="unsupported_action";
      return false;
    }
    out["code"]="unsupported_message";return false;
  }
};
