#pragma once
#include <ArduinoJson.h>
#include <stdint.h>
#include <string.h>

// Transport-independent v2 endpoint. No actuation, provisioning or demo writes.
class ProductionSession {
 public:
  char session[33] = {};
  uint32_t revision = 0;
  bool connected() const { return session[0] != 0; }
  void clear() { session[0] = 0; revision = 0; }
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
      strcpy(session,message["session"]);revision=0;
      out.clear();out["v"]=2;out["type"]="hello";out["id"]=message["id"];out["session"]=session;
      out["panel_id"]=panel;out["board_profile"]="lilygo-s3-long-cst3530";
      out["board_revision"]="unverified";out["firmware"]=firmware;
      out["protocol_min"]=2;out["protocol_max"]=2;out["boot_id"]=boot;
      out["boot_state"]=bootState;out["self_test_ok"]=healthy;
      JsonArray caps=out.createNestedArray("capabilities");caps.add("panel.status.v1");
      out.createNestedArray("actions"); // No MQTT adapter yet: advertise no actions.
      return true;
    }
    if (!matches(message)) { out["code"]="session_required";return false; }
    out["session"]=session;
    if (!strcmp(type,"state.get")) {
      out.clear();out["v"]=2;out["type"]="state.snapshot";out["id"]=message["id"];out["session"]=session;
      out["revision"]=++revision;out["sampled_uptime_ms"]=now;out["valid_for_ms"]=3500;
      out["state"]["self_test_ok"]=healthy;out["state"]["mode"]="standalone_demo";
      out["state"]["desk"]=nullptr;out["state"]["monitor"]=nullptr;
      return true;
    }
    if (!strcmp(type,"action.request")) {
      out["type"]="action.result";out["stage"]="rejected";out["code"]="unsupported_action";
      return false;
    }
    out["code"]="unsupported_message";return false;
  }
};
