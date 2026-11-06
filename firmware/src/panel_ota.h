#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <esp_ota_ops.h>
#include <esp_timer.h>
#include <mbedtls/sha256.h>
#include "ota_policy.h"
#include "signed_update.h"

#include "panel_version.h"
#define PANEL_OTA_PROFILE "lilygo-s3-long-cst3530:p1:ota3m-v1"

class PanelOta {
 public:
  explicit PanelOta(UpdatePolicy policy, const char *identity = "bench") : policy(policy), buildIdentity(identity) {}
  void bootStart();
  void describe(JsonObject result);
  void handle(JsonDocument &message, JsonDocument &response, bool healthy);
  bool authorize(JsonDocument &envelope, UpdateAuthorization &output) const;
  bool confirmLocal(const char *expectedImageSha, bool healthy);
  void abort();
  void tick();
  bool receiving() const { return guard.running; }
  bool pending() const { return pendingBoot; }
  bool committed() const { return rebootAt != 0; }
  int percent() const { return guard.expected ? 100 * guard.offset / guard.expected : 0; }
 private:
  UpdatePolicy policy;
  const char *buildIdentity;
  uint8_t authorizationIdentity[32] = {};
  bool authorizedTransfer = false;
  void begin(JsonDocument &message, JsonDocument &response, bool healthy, const UpdateAuthorization *authorization);
  bool anchorRunning();
  void fail(JsonDocument &response, const char *reason);
  TransferGuard guard;
  esp_ota_handle_t handleId = 0;
  const esp_partition_t *target = nullptr;
  mbedtls_sha256_context hash;
  bool hashActive = false, supported = false, pendingBoot = false, markerSeen = false;
  char runningSha[65] = {}, expectedSha[65] = {}, expectedImageSha[65] = {}, marker[160] = {};
  size_t matchedMarker = 0;
  uint32_t lastChunk = 0, rebootAt = 0;
  esp_timer_handle_t bootTimer = nullptr;
};
