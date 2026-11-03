#include "panel_ota.h"
#include "session_timeout.h"
#include <mbedtls/base64.h>
#include <ctype.h>
#include <string.h>
#include <sdkconfig.h>
#include <esp_app_format.h>

#if !CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE
#error The panel OTA build requires a rollback-enabled ESP-IDF bootloader.
#endif

// Arduino's default hook confirms an OTA before setup(). Defer this until the
// paired host verifies the running hash and the panel's startup self-check.
extern "C" bool verifyRollbackLater() { return true; }

static const char imageMarker[] = "NETLINK_PANEL_IMAGE_V1|" PANEL_OTA_PROFILE "|v" PANEL_FIRMWARE_VERSION ";";

static void hexDigest(const uint8_t *digest, char *output) {
  for (int i = 0; i < 32; i++) sprintf(output + 2 * i, "%02x", digest[i]);
  output[64] = 0;
}

static bool validDigest(JsonVariant value) {
  if (!value.is<const char *>() || strlen(value.as<const char *>()) != 64) return false;
  for (const char *c = value.as<const char *>(); *c; c++)
    if (!(*c >= '0' && *c <= '9') && !(*c >= 'a' && *c <= 'f')) return false;
  return true;
}

static bool profileMatches(const esp_partition_t *part, uint32_t address, uint32_t size) {
  return part && part->address == address && part->size == size;
}

void PanelOta::bootStart() {
  const esp_partition_t *running = esp_ota_get_running_partition();
  esp_ota_img_states_t state;
  pendingBoot = esp_ota_get_state_partition(running, &state) == ESP_OK &&
                (state == ESP_OTA_IMG_PENDING_VERIFY || state == ESP_OTA_IMG_NEW);
  if (pendingBoot) {
    esp_timer_create_args_t args = {};
    args.callback = [](void *) { esp_restart(); }; // Bootloader rejects an unconfirmed image on reset.
    args.name = "ota-boot-check";
    if (esp_timer_create(&args, &bootTimer) != ESP_OK || esp_timer_start_once(bootTimer, 90000000) != ESP_OK)
      esp_restart();
  }
  uint8_t digest[32];
  if (esp_partition_get_sha256(running, digest) == ESP_OK) hexDigest(digest, runningSha);
  supported = runningSha[0] &&
      profileMatches(esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_0, nullptr), 0x10000, 0x300000) &&
      profileMatches(esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_1, nullptr), 0x310000, 0x300000) &&
      profileMatches(esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_OTA, nullptr), 0xe000, 0x2000);
}

void PanelOta::describe(JsonObject result) {
  esp_ota_img_states_t state;
  bool valid = esp_ota_get_state_partition(esp_ota_get_running_partition(), &state) == ESP_OK && state == ESP_OTA_IMG_VALID;
  result["supported"] = supported;
  result["profile"] = PANEL_OTA_PROFILE;
  result["image_sha256"] = runningSha;
  result["image_marker"] = imageMarker; // Also retains this identity in the compiled binary.
  result["state"] = pendingBoot ? "pending" : (valid ? "valid" : "untracked");
  result["max_size"] = 0x300000;
  result["receiving"] = receiving();
}

bool PanelOta::anchorRunning() {
  if (pendingBoot) return false;
  // A first USB flash can have empty otadata. Record the running, verified
  // image as VALID before replacing the other slot, so it is a rollback target.
  esp_ota_img_states_t state;
  const esp_partition_t *running = esp_ota_get_running_partition();
  if (esp_ota_get_state_partition(running, &state) == ESP_OK && state == ESP_OTA_IMG_VALID) return true;
  return esp_ota_set_boot_partition(running) == ESP_OK && esp_ota_mark_app_valid_cancel_rollback() == ESP_OK;
}

void PanelOta::abort() {
  if (guard.running) esp_ota_abort(handleId);
  guard.reset(); target = nullptr;
  if (hashActive) { mbedtls_sha256_free(&hash); hashActive = false; }
}

void PanelOta::fail(JsonDocument &response, const char *reason) {
  abort();
  response["ok"] = false;
  response["error"] = reason;
}

void PanelOta::handle(JsonDocument &message, JsonDocument &response, bool healthy) {
  response["type"] = "ack"; response["id"] = message["id"]; response["ok"] = false;
  const char *type = message["type"];
  if (!supported || committed()) { response["error"] = "ota_unavailable"; return; }
  if (!strcmp(type, "ota_confirm")) {
    if (receiving() || !healthy || !validDigest(message["image_sha256"]) || strcmp(message["image_sha256"], runningSha)) {
      response["error"] = "boot_check_failed"; return;
    }
    bool ok = pendingBoot ? esp_ota_mark_app_valid_cancel_rollback() == ESP_OK : anchorRunning();
    if (ok) { pendingBoot = false; if (bootTimer) esp_timer_stop(bootTimer); }
    response["ok"] = ok; response["state"] = ok ? "valid" : "pending";
    return;
  }
  if (!strcmp(type, "ota_abort")) { abort(); response["ok"] = true; return; }
  if (!strcmp(type, "ota_begin")) {
    if (pendingBoot || !healthy) { response["error"] = "ota_busy_or_unhealthy"; return; }
    if (!message["size"].is<uint32_t>() || !validDigest(message["sha256"]) || !validDigest(message["image_sha256"]) ||
        !message["profile"].is<const char *>() || strcmp(message["profile"], PANEL_OTA_PROFILE) || !message["version"].is<const char *>()) {
      response["error"] = "invalid_manifest"; return;
    }
    const char *version = message["version"];
    if (!strlen(version) || strlen(version) > 31) { response["error"] = "invalid_version"; return; }
    for (const char *c = version; *c; c++)
      if (!isalnum(static_cast<unsigned char>(*c)) && *c != '.' && *c != '_' && *c != '-') { response["error"] = "invalid_version"; return; }
    char requestedMarker[160];
    snprintf(requestedMarker, sizeof(requestedMarker), "NETLINK_PANEL_IMAGE_V1|" PANEL_OTA_PROFILE "|v%s;", version);
    if (receiving()) {
      // The flash handle and running hash survive TLS loss, never a reboot.
      // Do not erase or replace a different in-flight image on reconnect.
      if (message["size"].as<uint32_t>() != guard.expected || strcmp(message["sha256"], expectedSha) ||
          strcmp(message["image_sha256"], expectedImageSha) || strcmp(requestedMarker, marker)) {
        response["error"] = "different_transfer_active"; return;
      }
      lastChunk = millis(); response["ok"] = true; response["next_offset"] = guard.offset;
      return;
    }
    target = esp_ota_get_next_update_partition(nullptr);
    uint32_t size = message["size"];
    if (!target || target == esp_ota_get_running_partition() || size < 288 || size > target->size) {
      response["error"] = "invalid_image_size"; target = nullptr; return;
    }
    if (!anchorRunning() || esp_ota_begin(target, OTA_WITH_SEQUENTIAL_WRITES, &handleId) != ESP_OK) {
      response["error"] = "flash_begin_failed"; target = nullptr; return;
    }
    guard.begin(size, target->size);
    strlcpy(expectedSha, message["sha256"], sizeof(expectedSha));
    strlcpy(expectedImageSha, message["image_sha256"], sizeof(expectedImageSha));
    snprintf(marker, sizeof(marker), "NETLINK_PANEL_IMAGE_V1|" PANEL_OTA_PROFILE "|v%s;", version);
    markerSeen = false; matchedMarker = 0;
    mbedtls_sha256_init(&hash); mbedtls_sha256_starts_ret(&hash, 0); hashActive = true;
    lastChunk = millis(); response["ok"] = true; response["next_offset"] = 0;
    return;
  }
  if (!receiving()) { response["error"] = "no_transfer"; return; }
  if (!strcmp(type, "ota_chunk")) {
    uint8_t chunk[TransferGuard::ChunkSize]; size_t length = 0;
    if (!message["offset"].is<uint32_t>() || !message["data"].is<const char *>()) { fail(response, "invalid_chunk"); return; }
    const char *data = message["data"];
    if (strlen(data) > 684 || mbedtls_base64_decode(chunk, sizeof(chunk), &length, reinterpret_cast<const unsigned char *>(data), strlen(data)) != 0 ||
        !guard.accepts(message["offset"], length)) { fail(response, "invalid_chunk_offset_or_size"); return; }
    if (!guard.offset && (length < sizeof(esp_image_header_t) || chunk[0] != ESP_IMAGE_HEADER_MAGIC || chunk[12] != 9 || chunk[13] != 0)) {
      fail(response, "wrong_chip_image"); return;
    }
    if (esp_ota_write(handleId, chunk, length) != ESP_OK || mbedtls_sha256_update_ret(&hash, chunk, length) != 0) {
      fail(response, "flash_write_failed"); return;
    }
    for (size_t i = 0; i < length && !markerSeen; i++) {
      if (chunk[i] == marker[matchedMarker]) matchedMarker++;
      else matchedMarker = chunk[i] == marker[0] ? 1 : 0;
      if (matchedMarker == strlen(marker)) markerSeen = true;
    }
    guard.advance(length); lastChunk = millis(); response["ok"] = true; response["next_offset"] = guard.offset;
    return;
  }
  if (!strcmp(type, "ota_finish")) {
    if (!guard.complete() || !markerSeen) { fail(response, "incomplete_or_wrong_profile"); return; }
    uint8_t digest[32]; char actual[65];
    mbedtls_sha256_finish_ret(&hash, digest); hexDigest(digest, actual);
    mbedtls_sha256_free(&hash); hashActive = false;
    if (strcmp(actual, expectedSha)) { fail(response, "hash_mismatch"); return; }
    // esp_ota_end validates the ESP image but does NOT change boot selection.
    esp_err_t endResult = esp_ota_end(handleId); guard.running = false;
    if (endResult != ESP_OK || esp_partition_get_sha256(target, digest) != ESP_OK) { fail(response, "image_validation_failed"); return; }
    hexDigest(digest, actual);
    if (strcmp(actual, expectedImageSha)) { fail(response, "image_hash_mismatch"); return; }
    if (esp_ota_set_boot_partition(target) != ESP_OK) { fail(response, "activation_failed"); return; }
    guard.reset(); target = nullptr;
    response["ok"] = true; response["state"] = "rebooting";
    rebootAt = millis();
    return;
  }
  fail(response, "unknown_ota_action");
}

void PanelOta::tick() {
  if (receiving() && millis() - lastChunk > OtaResumeTimeoutMs) abort();
  if (committed() && millis() - rebootAt > 200) esp_restart();
}
