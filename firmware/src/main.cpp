// Bench firmware: demo state and diagnostic touch only, never movement commands.
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Arduino_GFX_Library.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <esp_system.h>
#include "hyn_core.h"
#include "session_policy.h"
#include "panel_ota.h"
#include "frame_writer.h"
#include "session_timeout.h"
#include "panel_demo.h"
#include "production_protocol.h"
#include <mbedtls/base64.h>

#include "generated_update_trust.h"
PanelOta ota(compiledUpdatePolicy(), PANEL_UPDATE_IDENTITY);
PanelDemo demo;
ProductionSession production;
char bootId[17];
char otaStatus[40] = {};

bool startupHealthy();

constexpr int WIDTH = 640, HEIGHT = 180;
constexpr uint16_t BG = 0x0842, FG = 0xef7b, PANEL_ACCENT = 0x77b5, MUTED = 0x9cf3;
Arduino_ESP32QSPI bus(12, 17, 13, 18, 21, 14);
Arduino_AXS15231 display(&bus, 16, 0, false, 180, 640);
Arduino_Canvas canvas(WIDTH, HEIGHT, nullptr);
Preferences preferences;
class SettingsStorage {
 public:
  Preferences nvs;
  bool ready = false;
  static const char *key(int slot) { return slot == 0 ? "ui0" : "ui1"; }
  bool read(int slot, uint8_t *bytes, size_t size) { return ready && nvs.getBytesLength(key(slot)) == size && nvs.getBytes(key(slot), bytes, size) == size; }
  bool write(int slot, const uint8_t *bytes, size_t size) { return ready && nvs.putBytes(key(slot), bytes, size) == size; }
} settingsStorage;
PanelSettingsJournal<SettingsStorage> settings(settingsStorage);
PanelSettings gestureSettings;

void persistLocalSettings() {
  PanelSettings value=demo.settings();
  if(value==gestureSettings)return;
  if(!settings.save(value))demo.applySettings(settings.applied);
}
void describeSettings(JsonObject out) {
  out["schema"]=1;out["revision"]=settings.revision;
  out["brightness"]=settings.applied.brightness;out["rotated"]=settings.applied.rotated;out["dim_minutes"]=settings.applied.dimMinutes;
  out["writable"]=settingsStorage.ready && settings.writable;out["write_failed"]=settings.writeFailed;
}
WiFiClientSecure wifiClient;
IPAddress serverAddress;
String wifiSSID, wifiPassword, wifiKey;
uint16_t serverPort = 8769;
bool wifiEnabled = false, applyWifiPending = false;
uint32_t lastWifiRetry = 0, lastTLSRetry = 0;
volatile uint16_t lastWifiDisconnectReason = 0;
int lastRenderedOtaPercent = -1;
wl_status_t previousWifiStatus = WL_NO_SHIELD;
uint16_t *nativePixels = nullptr;
uint16_t *demoSnapshot = nullptr;
uint32_t demoSnapshotId = 0;
const char *demoSnapshotScreen = "";
bool screenReady = false, linked = false, hadTouch = true;
uint32_t lastHost = 0, lastHeartbeat = 0, lastTouchPoll = 0;
int demoHeight = 740, demoBrightness = 60;
char panelId[24];
const char *lastAction = "Tik op een knop";
Transport active = Transport::None;
struct Inbox { char data[1025]; size_t used = 0; bool dropping = false; } usbInbox, wifiInbox;

bool startupHealthy() {
  const hyn_ts_data *touch = get_touch_data();
  return screenReady && touch && touch->hw_info.fw_chip_type != 0;
}

void render();
void releaseSession(bool preserveTransfer = false) {
  if (!preserveTransfer) ota.abort();
  linked = false;
  production.clear();
  if(demo.readOnly)demo.setDeviceState(PanelDeviceState{});
  active = Transport::None;
  wifiClient.stop();
  wifiInbox = Inbox{};
  lastAction = "Verbinding verbroken";
  render();
}

void sendTo(Transport target, JsonDocument &message) {
  static char frame[1025];
  if (message["v"] != 2) message["v"] = 1;
  if (target == Transport::USB) writeJsonFrame(message, Serial, frame, sizeof(frame));
  else if (target == Transport::Wifi && wifiClient.connected()) {
    if (!writeJsonFrame(message, wifiClient, frame, sizeof(frame))) wifiClient.stop();
  }
}

void ack(Transport source, int id, bool ok) {
  StaticJsonDocument<128> response;
  response["type"] = "ack"; response["id"] = id; response["ok"] = ok;
  sendTo(source, response);
}

void render() {
  if (!screenReady) return;
  demo.draw(canvas.getFramebuffer());
  if (ota.receiving() || ota.pending() || ota.committed()) {
    demo.drawStatus(canvas.getFramebuffer(), ota.committed()?PanelDemo::Updated:PanelDemo::Updating, ota.receiving()?ota.percent():100, ota.pending());
  }
  // AXS15231B has no hardware axis swap. Flush a complete native frame.
  uint16_t *pixels = canvas.getFramebuffer();
  for (int y = 0; y < HEIGHT; y++)
    for (int x = 0; x < WIDTH; x++)
      nativePixels[x * HEIGHT + (HEIGHT - 1 - y)] = pixels[y * WIDTH + x];
  display.draw16bitRGBBitmap(0, 0, nativePixels, 180, 640);
}

bool validWifi(JsonDocument &config) {
  for (const char *field : {"ssid", "password", "host", "key"})
    if (!config[field].is<const char *>()) return false;
  size_t s = strlen(config["ssid"]), p = strlen(config["password"]), k = strlen(config["key"]);
  IPAddress address;
  if (s < 1 || s > 32 || p < 8 || p > 63 || k != 64 || !address.fromString(config["host"].as<const char *>())) return false;
  if (address[0] == 0 || address[0] == 127 || address[0] >= 224) return false;
  if (!config["port"].is<int>() || config["port"].as<int>() < 1024 || config["port"].as<int>() > 65535) return false;
  for (const char *c = config["key"].as<const char *>(); *c; c++) if (!isxdigit(*c)) return false;
  return true;
}

void loadWifi() {
  StaticJsonDocument<1536> config;
  String stored = preferences.getString("config", "");
  wifiEnabled = !deserializeJson(config, stored) && validWifi(config);
  if (!wifiEnabled) return;
  wifiSSID = config["ssid"].as<String>(); wifiPassword = config["password"].as<String>();
  wifiKey = config["key"].as<String>(); serverAddress.fromString(config["host"].as<const char *>());
  serverPort = config["port"].as<int>();
}

void applyWifi() {
  applyWifiPending = false;
  wifiClient.stop(); wifiInbox = Inbox{};
  WiFi.disconnect(true);
  loadWifi();
  if (wifiEnabled) {
    WiFi.persistent(false);
    WiFi.setHostname(panelId);
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(wifiSSID.c_str(), wifiPassword.c_str());
    wifiClient.setPreSharedKey(panelId, wifiKey.c_str());
    wifiClient.setHandshakeTimeout(1);
    lastWifiRetry = millis();
    lastTLSRetry = millis() - 5000;
  } else { WiFi.mode(WIFI_OFF); }
  render();
}

void receive(Transport source, const char *line) {
  StaticJsonDocument<1536> message;
  if (deserializeJson(message, line)) return;
  if (message["v"].is<int>() && message["v"].as<int>() == 2) {
    const char *kind = message["type"] | "";
    if (!strcmp(kind, "heartbeat")) {
      if (linked && source == active && production.matches(message)) lastHost = millis();
      return;
    }
    if (!strcmp(kind, "hello")) {
      // A production handshake must never interrupt an update or steal another session.
      if (ota.receiving() || ota.pending() || ota.committed() ||
          (linked && (source != active || !production.matches(message)))) {
        StaticJsonDocument<256> error;error["session"]=message["session"];error["v"]=2;error["type"]="error";error["id"]=message["id"];error["code"]="busy";sendTo(source,error);return;
      }
    } else if (!linked || source != active) return;
    StaticJsonDocument<1536> response;
    StaticJsonDocument<512> boot;ota.describe(boot.to<JsonObject>());
    bool accepted = production.handle(message,response,millis(),panelId,PANEL_FIRMWARE_VERSION,bootId,startupHealthy(),boot["state"] | "unknown");
    if(accepted && !strcmp(kind,"hello"))response["capabilities"].add("panel.config.status.v1");
    if(accepted && !strcmp(kind,"state.get"))describeSettings(response["state"]["panel_config"].to<JsonObject>());
    if (response["id"].is<int>()) sendTo(source,response);
    if (accepted) { active=source;linked=true;lastHost=millis();demo.setDeviceState(production.devices); }
    return;
  }
  if (!message["v"].is<int>() || message["v"].as<int>() != 1 || !message["type"].is<const char *>()) return;
  if (linked && production.connected()) return; // v1 never renews or mutates a production session.
  const char *type = message["type"];
  if (!strcmp(type, "heartbeat")) {
    if (linked && source == active) lastHost = millis();
    return;
  }
  if (!message["id"].is<int>() || message["id"].as<int>() <= 0) return;
  int id = message["id"];
  if (ota.committed()) { ack(source, id, false); return; }
  if (!strcmp(type, "hello")) {
    if (!canHandshake(active, source)) { ack(source, id, false); return; }
    if (source == Transport::USB && (active == Transport::Wifi || ota.receiving())) releaseSession();
    active = source; linked = true; lastHost = millis();
    StaticJsonDocument<2048> response;
    response["type"] = "hello"; response["id"] = id; response["panel_id"] = panelId;
    response["firmware"] = PANEL_FIRMWARE_VERSION; response["simulated"] = false;
    response["display_ready"] = screenReady;
    response["transport"] = source == Transport::USB ? "usb" : "wifi";
    JsonArray capabilities = response["capabilities"].to<JsonArray>();
    capabilities.add("demo_state"); capabilities.add("wifi_provision"); capabilities.add("tls_psk");
    capabilities.add("ota_v1"); capabilities.add("ota_resume_v1"); capabilities.add("demo_ui_v1"); capabilities.add("frame_snapshot_v1");
    response["self_test_ok"] = startupHealthy();
    response["uptime_ms"] = millis();
    response["reset_reason"] = static_cast<int>(esp_reset_reason());
    ota.describe(response["ota"].to<JsonObject>());
    response["wifi"]["last_disconnect_reason"] = lastWifiDisconnectReason;
    response["wifi"]["configured"] = wifiEnabled;
    response["wifi"]["connected"] = wifiEnabled && WiFi.status() == WL_CONNECTED;
    if (wifiEnabled && WiFi.status() == WL_CONNECTED) {
      response["wifi"]["ip"] = WiFi.localIP().toString(); response["wifi"]["rssi"] = WiFi.RSSI();
    }
    sendTo(source, response);
    lastAction = source == Transport::USB ? "USB-test actief" : "Wifi-test actief";
    render();
  } else if (!linked || source != active) {
    ack(source, id, false);
  } else if (!strncmp(type, "ota_", 4)) {
    if (source != Transport::Wifi) { ack(source, id, false); return; }
    StaticJsonDocument<384> response;
    ota.handle(message, response, startupHealthy());
    if (response["ok"].as<bool>()) lastHost = millis();
    sendTo(source, response);
    if (ota.receiving()) snprintf(otaStatus, sizeof(otaStatus), "Firmware laden: %d%%", ota.percent());
    else strlcpy(otaStatus, ota.committed() ? "Firmware starten..." : (response["ok"].as<bool>() ? "Firmware gecontroleerd" : "Update afgebroken"), sizeof(otaStatus));
    lastAction = otaStatus;
    // Limit full-frame redraws while transferring many small chunks.
    const int progressBucket = ota.percent() / 10;
    if (strcmp(type, "ota_chunk") || progressBucket != lastRenderedOtaPercent) {
      render(); lastRenderedOtaPercent = progressBucket;
    }
  } else if (ota.receiving() || ota.pending()) {
    ack(source, id, false);
  } else if (!strcmp(type, "demo_ui")) {
    const char *op = message["op"] | "status";
    bool ok = true;
    if (!strcmp(op, "scene")) ok = message["scene"].is<int>() && demo.scene(message["scene"], millis());
    else if (!strcmp(op, "tap") || !strcmp(op, "press") || !strcmp(op, "drag")) {
      int x = message["x"] | -1, y = message["y"] | -1, held = message["held_ms"] | 80;
      ok = message["x"].is<int>() && message["y"].is<int>() && x >= 0 && x < WIDTH && y >= 0 && y < HEIGHT && held >= 30 && held <= 2500;
      if (ok) {
        if (!strcmp(op, "press")) demo.touchDown(x, y, millis());
        else if (!strcmp(op, "drag")) demo.touchMove(x, y, millis());
        else { demo.touchDown(x, y, millis() - held); demo.touchUp(millis()); }
      }
    } else if (!strcmp(op, "release")) demo.touchUp(millis());
    else if (!strcmp(op, "reset")) demo.scene(0, millis());
    else if (!strcmp(op, "height")) { int mm = message["height_mm"] | -1; ok = message["height_mm"].is<int>() && PanelDemo::validHeight(mm); if(ok) demo.setHeight(mm); }
    else if (strcmp(op, "status")) ok = false;
    if (ok && strcmp(op, "status")) render();
    StaticJsonDocument<768> response; response["type"] = "ack"; response["id"] = id; response["ok"] = ok;
    response["mode"] = "standalone_demo"; response["screen"] = demo.name(); response["height_mm"] = demo.height; response["target_mm"] = demo.target;
    response["min_height_mm"] = PanelDemo::MinHeightMm; response["max_height_mm"] = PanelDemo::MaxHeightMm;
    response["sit_mm"] = demo.sit; response["stand_mm"] = demo.stand; response["monitor"] = demo.monitor;
    describeSettings(response["panel_config"].to<JsonObject>());
    response["brightness"] = demo.brightness; response["rotated"] = demo.rotated; response["connected"] = demo.connected;
    sendTo(source, response); lastHost = millis();
  } else if (!strcmp(type, "demo_frame")) {
    int offset = message["offset"] | -1;
    if (!message["offset"].is<int>() || offset < 0 || offset >= WIDTH * HEIGHT * 2 || offset % 512) { ack(source, id, false); return; }
    if (!offset) {
      if (!demoSnapshot) demoSnapshot = static_cast<uint16_t *>(ps_malloc(WIDTH * HEIGHT * 2));
      if (!demoSnapshot) { ack(source, id, false); return; }
      render(); memcpy(demoSnapshot, canvas.getFramebuffer(), WIDTH * HEIGHT * 2);
      ++demoSnapshotId; demoSnapshotScreen = demo.name();
    }
    if (!demoSnapshot) { ack(source, id, false); return; }
    size_t length = min(512, WIDTH * HEIGHT * 2 - offset), encoded = 0; unsigned char data[685];
    bool ok = mbedtls_base64_encode(data, sizeof(data), &encoded, reinterpret_cast<uint8_t *>(demoSnapshot) + offset, length) == 0;
    data[encoded] = 0;
    StaticJsonDocument<1024> response; response["type"] = "ack"; response["id"] = id; response["ok"] = ok;
    response["offset"] = offset; response["format"] = "rgb565le"; response["snapshot_id"] = demoSnapshotId; response["snapshot_screen"] = demoSnapshotScreen; response["data"] = reinterpret_cast<const char *>(data);
    sendTo(source, response); lastHost = millis();
  } else if (!strcmp(type, "wifi_config") && source == Transport::USB) {
    if (!validWifi(message)) { ack(source, id, false); return; }
    // Persist one NVS blob, excluding protocol fields. Never echo credentials.
    message.remove("type"); message.remove("id"); message.remove("v");
    String stored; serializeJson(message, stored);
    bool ok = preferences.putString("config", stored) == stored.length();
    ack(source, id, ok);
    if (ok) applyWifiPending = true;
  } else if (!strcmp(type, "wifi_clear") && source == Transport::USB) {
    bool ok = !preferences.isKey("config") || preferences.remove("config");
    ack(source, id, ok);
    if (ok) applyWifiPending = true;
  } else if (!strcmp(type, "demo_state")) {
    bool valid = screenReady && message["height_mm"].is<int>() && message["brightness"].is<int>();
    int h = message["height_mm"], b = message["brightness"];
    valid = valid && PanelDemo::validHeight(h) && b >= 0 && b <= 100;
    if (valid) { demoHeight = h; demoBrightness = b; demo.setHeight(h); demo.monitor = b; render(); }
    ack(source, id, valid);
  } else { ack(source, id, false); }
}

void readStream(Stream &stream, Inbox &inbox, Transport source) {
  for (int budget = 0; budget < 2048 && stream.available(); budget++) {
    char c = static_cast<char>(stream.read());
    if (c == '\n') {
      if (!inbox.dropping && inbox.used) { inbox.data[inbox.used] = 0; receive(source, inbox.data); }
      inbox.used = 0; inbox.dropping = false;
    } else if (!inbox.dropping) {
      if (inbox.used < sizeof(inbox.data) - 1) inbox.data[inbox.used++] = c;
      else { inbox.dropping = true; inbox.used = 0; }
    }
  }
}

void setup() {
  // Reserve enough USB TX space for complete 1025-byte JSON frames.
  // The default 256-byte queue can truncate a bulk response.
  Serial.setTxBufferSize(4096);
  Serial.begin(115200);
  snprintf(bootId,sizeof(bootId),"%08lx%08lx",static_cast<unsigned long>(esp_random()),static_cast<unsigned long>(esp_random()));
  Serial.setTxTimeoutMs(100);
  WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info) {
    if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) lastWifiDisconnectReason = info.wifi_sta_disconnected.reason;
  });
  snprintf(panelId, sizeof(panelId), "panel-%012llx", ESP.getEfuseMac());
  settingsStorage.ready=settingsStorage.nvs.begin("panel-ui",false);
  settings.load();demo.applySettings(settings.applied);
  ota.bootStart();
  pinMode(1, OUTPUT); digitalWrite(1, LOW);
  nativePixels = static_cast<uint16_t *>(ps_malloc(WIDTH * HEIGHT * sizeof(uint16_t)));
  screenReady = nativePixels && canvas.begin() && display.begin(32000000);
  if(screenReady) { digitalWrite(1,HIGH);demo.screen=PanelDemo::Boot;render(); }
  touch_init(15, 10, 11, 2); // Verify actual CST3530 board revision before flashing.
  digitalWrite(1, HIGH);
  if (preferences.begin("panel-wifi", false)) applyWifi();
  demo.scene(0,millis());
  demo.applySettings(settings.applied);
  render();
}

void loop() {
  ota.tick();
  if(production.expire(millis()))demo.setDeviceState(production.devices);
  // USB always has priority and can recover/reconfigure a bad Wi-Fi setup.
  readStream(Serial, usbInbox, Transport::USB);
  if (applyWifiPending) applyWifi();
  uint32_t now = millis();
  if (linked && (sessionExpired(ota.receiving(), now - lastHost) || (active == Transport::Wifi && !wifiClient.connected()))) releaseSession(active == Transport::Wifi);
  if (!linked && wifiClient.connected() && now - lastTLSRetry > 3500) releaseSession(true);
  if (wifiEnabled) {
    wl_status_t status = WiFi.status();
    if (status != previousWifiStatus) { previousWifiStatus = status; render(); }
    if (status != WL_CONNECTED && now - lastWifiRetry > 15000) { lastWifiRetry = now; WiFi.reconnect(); }
    // Bounded TLS attempts only while no USB or Wi-Fi control session exists.
    if (status == WL_CONNECTED && active == Transport::None && demo.screen != PanelDemo::Moving && !wifiClient.connected() && now - lastTLSRetry > 5000) {
      lastTLSRetry = now;
      wifiClient.connect(serverAddress, serverPort, 1000);
      wifiInbox = Inbox{};
    }
    if (wifiClient.connected()) readStream(wifiClient, wifiInbox, Transport::Wifi);
  }
  now = millis();
  if (linked && now - lastHeartbeat >= 1000) {
    lastHeartbeat = now;
    StaticJsonDocument<128> heartbeat;
    heartbeat["type"] = "heartbeat"; heartbeat["uptime_ms"] = now;
    if (production.connected()) { heartbeat["v"]=2;heartbeat["session"]=production.session; }
    sendTo(active, heartbeat);
  }
  if (now - lastTouchPoll >= 30) {
    lastTouchPoll = now;
    hyn_ts_data *touch = get_touch_data();
    bool pressed = touch && touch->rp_buf.rep_num > 0;
    demo.setBusy(ota.receiving() || ota.pending() || ota.committed());
    if (pressed && !hadTouch) {
      int x = touch->rp_buf.pos_info[0].pos_y, y = 179 - touch->rp_buf.pos_info[0].pos_x;
      gestureSettings=demo.settings();
      demo.touchDown(x, y, now);
      if (linked && !production.connected() && !demo.busy) {
        StaticJsonDocument<160> event; event["type"] = "touch"; event["action"] = "demo_touch";
        event["x"] = x; event["y"] = y; sendTo(active, event);
      }
    }
    if (pressed && hadTouch) demo.touchMove(touch->rp_buf.pos_info[0].pos_y, 179 - touch->rp_buf.pos_info[0].pos_x, now);
    if (!pressed && hadTouch) { demo.touchUp(now);persistLocalSettings(); }
    hadTouch = pressed;
  }
  demo.setBusy(ota.receiving() || ota.pending() || ota.committed());
  if (demo.tick(millis())) render();
  delay(1);
}
