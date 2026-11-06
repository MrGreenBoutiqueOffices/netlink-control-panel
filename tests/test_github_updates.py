"""Actual independent updater with ephemeral signatures, fake network/NVS/flash."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_signed_updates import envelope, key_fixture, record_fixture

ROOT = Path(__file__).resolve().parents[1]
STUB = r"""
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <map>
using esp_err_t=int; using esp_ota_handle_t=unsigned;using esp_timer_handle_t=void*;
using QueueHandle_t=void*;using TaskHandle_t=void*;
constexpr int ESP_OK=0,ESP_OTA_IMG_VALID=1,ESP_OTA_IMG_PENDING_VERIFY=2,ESP_OTA_IMG_NEW=3;
constexpr int ESP_PARTITION_TYPE_APP=0,ESP_PARTITION_TYPE_DATA=1;
constexpr int ESP_PARTITION_SUBTYPE_APP_OTA_0=0,ESP_PARTITION_SUBTYPE_APP_OTA_1=1,ESP_PARTITION_SUBTYPE_DATA_OTA=2;
constexpr size_t OTA_WITH_SEQUENTIAL_WRITES=0xffffffff;
constexpr int ESP_IMAGE_HEADER_MAGIC=0xe9;
#define CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE 1
struct esp_partition_t {uint32_t address,size;};using esp_ota_img_states_t=int;
struct esp_image_header_t {uint8_t bytes[24];};
struct esp_timer_create_args_t {void (*callback)(void*);const char* name;};
extern unsigned clockMs,begins,writes,confirms,boots;extern bool pending,failSave,failFlash;
extern std::string runningHash,targetHash;
extern std::map<std::string,std::vector<uint8_t>> stored;
inline uint32_t millis(){return clockMs;}
inline void *ps_malloc(size_t size){return malloc(size);}
inline void configTime(int,int,const char*,const char*){}
inline void esp_restart(){++boots;}
inline int esp_timer_create(const esp_timer_create_args_t*,esp_timer_handle_t*){return 0;}
inline int esp_timer_start_once(esp_timer_handle_t,uint64_t){return 0;}
inline int esp_timer_stop(esp_timer_handle_t){return 0;}
inline const esp_partition_t *esp_partition_find_first(int type,int sub,const char*){static esp_partition_t p[3]={{0x10000,0x300000},{0x310000,0x300000},{0xe000,0x2000}};return &p[type==1?2:sub];}
inline const esp_partition_t *esp_ota_get_running_partition(){return esp_partition_find_first(0,0,nullptr);}
inline const esp_partition_t *esp_ota_get_next_update_partition(const void*){return esp_partition_find_first(0,1,nullptr);}
inline int esp_ota_get_state_partition(const esp_partition_t*,esp_ota_img_states_t* s){*s=pending?ESP_OTA_IMG_PENDING_VERIFY:ESP_OTA_IMG_VALID;return 0;}
inline int esp_partition_get_sha256(const esp_partition_t *p,uint8_t *out){const std::string &h=p->address==0x10000?runningHash:targetHash;for(int i=0;i<32;i++){unsigned n;sscanf(h.substr(2*i,2).c_str(),"%2x",&n);out[i]=n;}return 0;}
inline int esp_ota_set_boot_partition(const esp_partition_t*){return 0;}
inline int esp_ota_mark_app_valid_cancel_rollback(){++confirms;pending=false;return 0;}
inline int esp_ota_begin(const esp_partition_t*,size_t,esp_ota_handle_t *h){*h=++begins;return 0;}
inline int esp_ota_write(esp_ota_handle_t,const void*,size_t){++writes;return failFlash?-1:0;}
inline int esp_ota_abort(esp_ota_handle_t){return 0;}
inline int esp_ota_end(esp_ota_handle_t){return 0;}
class Preferences {
 public:
 bool begin(const char*,bool){return true;}
 size_t getBytesLength(const char *key){return stored[key].size();}
 size_t getBytes(const char *key,void *out,size_t n){if(stored[key].size()!=n)return 0;memcpy(out,stored[key].data(),n);return n;}
 size_t putBytes(const char *key,const void *p,size_t n){if(failSave)return 0;stored[key]=std::vector<uint8_t>((const uint8_t*)p,(const uint8_t*)p+n);return n;}
};
"""

PROGRAM = r"""
#include "panel_updater.h"
#include "github_http.h"
#include <cassert>
#include <deque>
#include <fstream>
#include <iterator>
unsigned clockMs=100,begins=0,writes=0,confirms=0,boots=0,fetches=0;
bool pending=false,failSave=false,failFlash=false;
std::string runningHash(64,'0'),targetHash(64,'b');
std::map<std::string,std::vector<uint8_t>> stored;
std::map<std::string,std::string> assets;
std::deque<GithubDownload::Event> events;
extern UpdatePolicy testPolicy();
bool GithubDownload::begin(){return true;}
bool GithubDownload::start(const char *url,size_t limit,bool,uint32_t){
 if(running || !githubUpdateUrl(url))return false;
 ++fetches;running=true;cancelled=false;
 const std::string data=assets[url];
 for(size_t at=0;at<data.size();at+=512){Event e;e.length=std::min(size_t(512),data.size()-at);memcpy(e.bytes,data.data()+at,e.length);::events.push_back(e);}
 Event end;end.done=true;end.ok=!data.empty() && data.size()<=limit;::events.push_back(end);return true;
}
bool GithubDownload::poll(Event &event){
 if(::events.empty())return false;event=::events.front();::events.pop_front();
 if(event.done){running=false;if(cancelled)event.ok=false;}return true;
}
static void ticks(PanelUpdater &u,bool healthy=true,bool wifi=true,unsigned count=40){for(unsigned i=0;i<count;i++){clockMs+=100;u.tick(healthy,wifi);}}
static UpdateAttempt attempt(){UpdateAttempt a;memcpy(&a,stored["attempt"].data(),sizeof(a));assert(a.valid());return a;}
int main(int argc,char **argv){
 assert(argc==3);std::string folder=argv[1],mode=argv[2];
 for(const char *name:{"latest","601","602","603"}){std::ifstream file(folder+"/"+name,std::ios::binary);std::string data((std::istreambuf_iterator<char>(file)),{});std::string url=!strcmp(name,"latest")?PanelLatestRelease:std::string("https://api.github.com/repos/")+PanelRepository+"/releases/assets/"+name;assets[url]=data;}
 if(mode=="http"){
  assert(githubUpdateUrl("https://api.github.com/repos/a/b"));
  for(const char *url:{"http://github.com/a","https://github.com.evil/a","https://github.com@evil/a","https://github.com:443/a","https://github.com/a\r\nX:y","https://github.com/a#fragment","https://evil/github.com"})assert(!githubUpdateUrl(url));
  auto parse=[](const std::string &s){GithubHttpHeaders h;for(char c:s)h.accept(c);return h;};
  auto h=parse("HTTP/1.1 200 OK\r\nContent-Length: 123\r\n\r\n");assert(h.complete && !h.failed && h.length==123);
  h=parse("HTTP/1.0 302 Found\r\nLocation: https://github.com/a\r\n\r\n");assert(h.redirect() && !strcmp(h.location,"https://github.com/a"));
  for(const char *s:{"Content-Length: 1\r\nContent-Length: 1","Transfer-Encoding: chunked","Content-Encoding: gzip","Content-Length: -1","Content-Length: 3145729","Content-Length: 99999999999999"," invalid"}){h=parse(std::string("HTTP/1.1 200 OK\r\n")+s+"\r\n\r\n");assert(h.failed);}
  h=parse("HTTP/1.1 200 OK\r\nX: "+std::string(2200,'a')+"\r\n\r\n");assert(h.failed);
  UpdateAttempt a;a.phase=UpdatePhase::Downloading;a.checksum=a.crc();assert(a.valid() && a.reconcile(runningHash.c_str(),false)==UpdatePhase::Interrupted);a.image[3]='f';assert(!a.valid());return 0;
 }
 if(mode=="corrupt"){stored["attempt"]={1,2,3};PanelOta o(testPolicy());o.bootStart();PanelUpdater u(o,true);u.begin();assert(!u.check(true,true) && begins==0);return 0;}
 if(mode=="unsigned"){assets[std::string("https://api.github.com/repos/")+PanelRepository+"/releases/assets/602"]="{}";}
 if(mode=="signature"){auto &v=assets[std::string("https://api.github.com/repos/")+PanelRepository+"/releases/assets/602"];v[v.find("signature")+15]='!';}
 if(mode=="manifest"){assets[std::string("https://api.github.com/repos/")+PanelRepository+"/releases/assets/601"]+=" ";}
 if(mode=="release"){assets[PanelLatestRelease]="{}";}
 if(mode=="hash"){assets[std::string("https://api.github.com/repos/")+PanelRepository+"/releases/assets/603"].back()='x';}
 PanelOta o(testPolicy());o.bootStart();PanelUpdater u(o,mode!="untrusted");u.begin();
 assert(!u.check(false,true) && begins==0);assert(!u.check(true,false) && begins==0);
 if(mode=="untrusted"){assert(!u.check(true,true) && fetches==0);return 0;}
 assert(u.check(true,true));assert(!u.check(true,true));ticks(u);
 if(mode=="unsigned" || mode=="signature" || mode=="manifest" || mode=="release"){assert(!u.available() && begins==0 && !u.busy());return 0;}
 assert(u.available() && !u.busy());assert(!u.install(false,true,true) && begins==0);
 if(mode=="storage")failSave=true;
 if(mode=="flash")failFlash=true;
 bool installed=u.install(true,true,true);
 if(mode=="storage"){assert(!installed && begins==0);return 0;}
 assert(installed && begins==1);assert(!u.install(true,true,true));assert(attempt().phase==UpdatePhase::Downloading);
 if(mode=="cancel"){
  assert(u.cancelable() && u.cancel());assert(!o.receiving() && !o.committed());ticks(u);
  assert(attempt().phase==UpdatePhase::Interrupted && !u.busy() && !u.cancel());return 0;
 }
 if(mode=="powerloss"){
  events.clear();PanelOta restarted(testPolicy());restarted.bootStart();PanelUpdater next(restarted,true);next.begin();
  assert(attempt().phase==UpdatePhase::Interrupted && !next.busy());
  assert(next.check(true,true));ticks(next);assert(next.available());assert(next.install(true,true,true));
  assert(begins==2);ticks(next);assert(restarted.committed());return 0;
 }
 if(mode=="interrupted")ticks(u,true,false);else ticks(u);
 if(mode=="interrupted" || mode=="flash" || mode=="hash"){assert(!o.committed() && !u.busy() && attempt().phase==UpdatePhase::Failed);return 0;}
 assert(o.committed() && attempt().phase==UpdatePhase::BootPending && writes>0);
 // A reboot loses the transfer handle; outcome uses actual boot state and the stored expected hash.
 if(mode!="rollback")runningHash=targetHash;
 pending=mode!="rollback";
 PanelOta candidate(testPolicy());candidate.bootStart();PanelUpdater boot(candidate,true);boot.begin();
 if(mode=="rollback"){assert(!boot.busy() && attempt().phase==UpdatePhase::RolledBack && confirms==0);return 0;}
 assert(boot.busy() && !boot.check(true,true));
 if(mode=="unhealthy"){ticks(boot,false,false,1000);assert(confirms==0 && candidate.pending());return 0;}
 ticks(boot,true,false);assert(confirms==1 && !candidate.pending() && attempt().phase==UpdatePhase::Succeeded && !boot.busy());
}
"""


class GithubUpdateTests(unittest.TestCase):
    def test_actual_independent_lifecycle_and_failure_boundaries(self):
        compiler = shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        private, der, trust = key_fixture()
        firmware = bytearray(2048)
        firmware[0] = 0xE9
        firmware[12] = 9
        firmware[256:256] = b"NETLINK_PANEL_IMAGE_V1|lilygo-s3-long-cst3530:p1:ota3m-v1|v0.9.0;"
        record = record_fixture(trust)
        record.update(size=len(firmware), version="0.9.0", sha256=hashlib.sha256(firmware).hexdigest())
        manifest = {
            "schema": 1,
            "source": {
                "repository": "MrGreenBoutiqueOffices/netlink-control-panel",
                "tag": "v0.9.0",
                "commit": record["commit"],
            },
            "firmware": {name: record[name] for name in ["size", "sha256", "image_sha256", "version"]},
            "compatibility": {
                name: record[name]
                for name in ["board_profile", "board_revision", "protocol_min", "protocol_max", "partition_layout"]
            },
            "artifacts": {"firmware.bin": {"size": len(firmware), "sha256": record["sha256"]}},
            "signature": {"status": "signed"},
        }
        manifest["firmware"]["profile"] = "lilygo-s3-long-cst3530:p1:ota3m-v1"
        manifest_bytes = json.dumps(manifest).encode()
        record["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        authorization = json.dumps(envelope(private, record)).encode()
        latest = {
            "id": 10,
            "tag_name": "v0.9.0",
            "draft": False,
            "prerelease": False,
            "assets": [
                {"id": asset_id, "name": name, "size": len(data), "state": "uploaded"}
                for asset_id, name, data in [
                    (601, "manifest.json", manifest_bytes),
                    (602, "authorization.json", authorization),
                    (603, "firmware.bin", firmware),
                ]
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name, data in [
                ("latest", json.dumps(latest).encode()),
                ("601", manifest_bytes),
                ("602", authorization),
                ("603", firmware),
            ]:
                (directory / name).write_bytes(data)
            (directory / "stub.h").write_text(STUB)
            for name in [
                "Arduino.h",
                "Preferences.h",
                "esp_ota_ops.h",
                "esp_timer.h",
                "sdkconfig.h",
                "esp_app_format.h",
                "freertos/FreeRTOS.h",
                "freertos/queue.h",
                "freertos/task.h",
            ]:
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('#include "stub.h"\n')
            key_id = bytes.fromhex(trust["keys"][0]["id"])
            key_source = "\n".join(
                f"const uint8_t {name}[]={{" + ",".join(map(str, data)) + "};"
                for name, data in [("kid", key_id), ("der", der)]
            )
            source = directory / "test.cpp"
            source.write_text(
                PROGRAM
                + key_source
                + '\nUpdatePolicy testPolicy(){static UpdateKey k={kid,der,sizeof(der),false};return {true,"test-rev1",2,10,&k,1};}\n'
            )
            binary = directory / "test"
            result = subprocess.run(
                [
                    compiler,
                    "-std=c++11",
                    "-I",
                    str(directory),
                    "-I",
                    str(ROOT / "firmware/src"),
                    "-I",
                    str(ROOT / "firmware/.pio/libdeps/panel-bench/ArduinoJson/src"),
                    "-I",
                    str(ROOT / "firmware/.vendor/mbedtls/include"),
                    str(source),
                    str(ROOT / "firmware/src/panel_ota.cpp"),
                    str(ROOT / "firmware/src/panel_updater.cpp"),
                    str(ROOT / "firmware/src/signed_update.cpp"),
                    str(ROOT / "firmware/.vendor/mbedtls/build/library/libmbedcrypto.a"),
                    "-o",
                    str(binary),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for mode in [
                "http",
                "corrupt",
                "release",
                "unsigned",
                "signature",
                "manifest",
                "untrusted",
                "storage",
                "flash",
                "hash",
                "interrupted",
                "powerloss",
                "cancel",
                "rollback",
                "unhealthy",
                "success",
            ]:
                with self.subTest(mode=mode):
                    result = subprocess.run([str(binary), str(directory), mode], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class WifiOnlyProvisioningTests(unittest.TestCase):
    def test_wifi_only_sends_credentials_without_a_host_or_pairing_file(self):
        from netlink_panel.wifi import provision

        with (
            patch("builtins.input", return_value="test-network"),
            patch("netlink_panel.wifi.getpass.getpass", return_value="test-password"),
            patch("netlink_panel.wifi.serial.Serial"),
            patch("netlink_panel.wifi.report") as report,
            patch(
                "netlink_panel.wifi.request",
                side_effect=[{"capabilities": ["wifi_only_provision_v1"], "panel_id": "test-panel"}, {"ok": True}],
            ) as request,
        ):
            self.assertEqual(provision(SimpleNamespace(wifi_only=True, port="test")), 0)
            self.assertEqual(
                request.call_args_list[1].args[1],
                {"type": "wifi_config", "id": 2, "ssid": "test-network", "password": "test-password"},
            )
            self.assertNotIn("password", str(report.call_args))
