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

PanelOta ota;
char otaStatus[40] = {};

bool startupHealthy();

constexpr int WIDTH = 640, HEIGHT = 180;
constexpr uint16_t BG = 0x0842, FG = 0xef7b, PANEL_ACCENT = 0x77b5, MUTED = 0x9cf3;
Arduino_ESP32QSPI bus(12, 17, 13, 18, 21, 14);
Arduino_AXS15231 display(&bus, 16, 0, false, 180, 640);
Arduino_Canvas canvas(WIDTH, HEIGHT, nullptr);
Preferences preferences;
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
  active = Transport::None;
  hadTouch = true;
  wifiClient.stop();
  wifiInbox = Inbox{};
  lastAction = "Verbinding verbroken";
  render();
}

void sendTo(Transport target, JsonDocument &message) {
  static char frame[1025];
  message["v"] = 1;
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
  canvas.fillScreen(BG);
  canvas.setTextWrap(false);
  canvas.setTextSize(2); canvas.setTextColor(PANEL_ACCENT);
  canvas.setCursor(18, 16); canvas.print("NETLINK");
  canvas.setTextColor(MUTED); canvas.setCursor(410, 16);
  canvas.print(linked ? (active == Transport::USB ? "USB verbonden" : "Wifi verbonden") :
               (wifiEnabled ? (WiFi.status() == WL_CONNECTED ? "Wifi gereed" : "Wifi zoeken") : "Wacht op USB"));
  canvas.setTextSize(1); canvas.setCursor(18, 42);
  canvas.print("DEMO - geen bureau aangesloten");
  canvas.setTextColor(FG); canvas.setTextSize(4); canvas.setCursor(18, 70);
  canvas.printf("%.1f", demoHeight / 10.0);
  canvas.setTextSize(2); canvas.print(" cm");
  canvas.setCursor(18, 134); canvas.printf("Monitor %d%%", demoBrightness);
  canvas.setTextSize(1); canvas.setTextColor(MUTED); canvas.setCursor(18, 162);
  if (wifiEnabled && WiFi.status() == WL_CONNECTED) canvas.print(WiFi.localIP().toString());
  const char *labels[] = {"ZITTEN", "STAAN", "MONITOR"};
  bool controlsEnabled = linked && !ota.receiving() && !ota.committed() && !ota.pending();
  for (int i = 0; i < 3; i++) {
    int x = 258 + i * 124;
    canvas.fillRoundRect(x, 62, 114, 64, 9, controlsEnabled ? 0x1946 : 0x1083);
    canvas.setCursor(x + 12, 86); canvas.setTextSize(2);
    canvas.setTextColor(controlsEnabled ? FG : MUTED); canvas.print(labels[i]);
  }
  canvas.setTextSize(1); canvas.setTextColor(MUTED); canvas.setCursor(258, 146);
  canvas.print(lastAction);
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
  if (!message["v"].is<int>() || message["v"].as<int>() != 1 || !message["type"].is<const char *>()) return;
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
    active = source; linked = true; lastHost = millis(); hadTouch = true;
    StaticJsonDocument<2048> response;
    response["type"] = "hello"; response["id"] = id; response["panel_id"] = panelId;
    response["firmware"] = PANEL_FIRMWARE_VERSION; response["simulated"] = false;
    response["display_ready"] = screenReady;
    response["transport"] = source == Transport::USB ? "usb" : "wifi";
    JsonArray capabilities = response["capabilities"].to<JsonArray>();
    capabilities.add("demo_state"); capabilities.add("wifi_provision"); capabilities.add("tls_psk");
    capabilities.add("ota_v1"); capabilities.add("ota_resume_v1");
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
    valid = valid && h >= 500 && h <= 1300 && b >= 0 && b <= 100;
    if (valid) { demoHeight = h; demoBrightness = b; render(); }
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
  Serial.begin(115200);
  WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info) {
    if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) lastWifiDisconnectReason = info.wifi_sta_disconnected.reason;
  });
  snprintf(panelId, sizeof(panelId), "panel-%012llx", ESP.getEfuseMac());
  ota.bootStart();
  pinMode(1, OUTPUT); digitalWrite(1, LOW);
  nativePixels = static_cast<uint16_t *>(ps_malloc(WIDTH * HEIGHT * sizeof(uint16_t)));
  screenReady = nativePixels && canvas.begin() && display.begin(32000000);
  touch_init(15, 10, 11, 2); // Verify actual CST3530 board revision before flashing.
  digitalWrite(1, HIGH);
  if (preferences.begin("panel-wifi", false)) applyWifi();
  render();
}

void loop() {
  ota.tick();
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
    if (status == WL_CONNECTED && active == Transport::None && !wifiClient.connected() && now - lastTLSRetry > 5000) {
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
    sendTo(active, heartbeat);
  }
  if (now - lastTouchPoll >= 30) {
    lastTouchPoll = now;
    hyn_ts_data *touch = get_touch_data();
    bool pressed = touch && touch->rp_buf.rep_num > 0;
    if (linked && !ota.receiving() && !ota.pending() && !ota.committed() && pressed && !hadTouch) {
      int x = touch->rp_buf.pos_info[0].pos_y, y = 179 - touch->rp_buf.pos_info[0].pos_x;
      int button = (x - 258) / 124;
      if (x >= 258 && button >= 0 && button < 3 && x < 258 + button * 124 + 114 && y >= 62 && y < 126) {
        const char *actions[] = {"sit_preview", "stand_preview", "monitor_preview"};
        StaticJsonDocument<128> event; event["type"] = "touch"; event["action"] = actions[button];
        sendTo(active, event); lastAction = actions[button]; render();
      }
    }
    hadTouch = pressed;
  }
  delay(1);
}
