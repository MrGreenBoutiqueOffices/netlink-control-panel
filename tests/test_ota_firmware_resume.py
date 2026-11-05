"""Compile the actual firmware OTA handler against bounded fake SDK flash calls."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

STUB = r"""
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <cstdlib>
using esp_err_t = int;
constexpr int ESP_OK = 0;
using esp_ota_handle_t = unsigned;
using esp_timer_handle_t = void*;
struct esp_partition_t { uint32_t address, size; };
using esp_ota_img_states_t = int;
constexpr int ESP_OTA_IMG_VALID=1, ESP_OTA_IMG_PENDING_VERIFY=2, ESP_OTA_IMG_NEW=3;
constexpr int ESP_PARTITION_TYPE_APP=0, ESP_PARTITION_TYPE_DATA=1;
constexpr int ESP_PARTITION_SUBTYPE_APP_OTA_0=0, ESP_PARTITION_SUBTYPE_APP_OTA_1=1, ESP_PARTITION_SUBTYPE_DATA_OTA=2;
constexpr size_t OTA_WITH_SEQUENTIAL_WRITES=0xffffffff;
constexpr int ESP_IMAGE_HEADER_MAGIC=0xe9;
struct esp_image_header_t { uint8_t bytes[24]; };
struct esp_timer_create_args_t { void (*callback)(void*); const char* name; };
struct mbedtls_sha256_context {};
extern unsigned begins, writes, aborts, clockMs;
inline uint32_t millis() { return clockMs; }
inline void esp_restart() { std::abort(); }
inline int esp_timer_create(const esp_timer_create_args_t*, esp_timer_handle_t*) { return 0; }
inline int esp_timer_start_once(esp_timer_handle_t, uint64_t) { return 0; }
inline int esp_timer_stop(esp_timer_handle_t) { return 0; }
inline const esp_partition_t* esp_ota_get_running_partition() { static esp_partition_t p{0x10000,0x300000}; return &p; }
inline const esp_partition_t* esp_partition_find_first(int type,int sub,const char*) { static esp_partition_t p[3]={{0x10000,0x300000},{0x310000,0x300000},{0xe000,0x2000}}; return &p[type==1 ? 2 : sub]; }
inline const esp_partition_t* esp_ota_get_next_update_partition(const void*) { return esp_partition_find_first(0,1,nullptr); }
inline int esp_ota_get_state_partition(const esp_partition_t*,esp_ota_img_states_t* s) { *s=ESP_OTA_IMG_VALID; return 0; }
inline int esp_partition_get_sha256(const esp_partition_t*,uint8_t* d) { memset(d,0,32); return 0; }
inline int esp_ota_set_boot_partition(const esp_partition_t*) { return 0; }
inline int esp_ota_mark_app_valid_cancel_rollback() { return 0; }
inline int esp_ota_begin(const esp_partition_t*,size_t,esp_ota_handle_t* h) { *h=++begins; return 0; }
inline int esp_ota_write(esp_ota_handle_t,const void*,size_t) { ++writes; return 0; }
inline int esp_ota_abort(esp_ota_handle_t) { ++aborts; return 0; }
inline int esp_ota_end(esp_ota_handle_t) { return 0; }
inline void mbedtls_sha256_init(mbedtls_sha256_context*) {}
inline int mbedtls_sha256_starts_ret(mbedtls_sha256_context*,int) { return 0; }
inline int mbedtls_sha256_update_ret(mbedtls_sha256_context*,const void*,size_t) { return 0; }
inline int mbedtls_sha256_finish_ret(mbedtls_sha256_context*,uint8_t* d) { memset(d,0,32); return 0; }
inline void mbedtls_sha256_free(mbedtls_sha256_context*) {}
inline int mbedtls_base64_decode(uint8_t* out,size_t,size_t* n,const unsigned char*,size_t) { memset(out,0,512); out[0]=0xe9;out[12]=9;*n=512;return 0; }
#define CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE 1
"""

PROGRAM = r"""
#include "panel_ota.h"
#include <cassert>
unsigned begins=0,writes=0,aborts=0,clockMs=100;
int main() {
  PanelOta ota(benchUpdatePolicy()); ota.bootStart();
  StaticJsonDocument<1536> m; StaticJsonDocument<512> r;
  auto begin=[&]() { m.clear(); m["type"]="ota_begin";m["id"]=1;m["size"]=1024;m["sha256"]=std::string(64, 'a');m["image_sha256"]=std::string(64,'b');m["profile"]=PANEL_OTA_PROFILE;m["version"]="0.3.2";r.clear();ota.handle(m,r,true); };
  auto chunk=[&](int offset) { m.clear();m["type"]="ota_chunk";m["id"]=2;m["offset"]=offset;m["data"]="fixture";r.clear();ota.handle(m,r,true); };
  begin(); assert(r["ok"]==true && begins==1);
  chunk(0); assert(r["ok"]==true && writes==1 && r["next_offset"]==512);
  begin();
  if (r["ok"]!=true || r["next_offset"]!=512 || begins!=1) { std::puts("Lost ACK cannot resume the existing OTA handle without erasing");return 2; }
  m["sha256"]=std::string(64,'c'); r.clear();ota.handle(m,r,true);
  assert(r["ok"]==false && ota.receiving() && begins==1 && writes==1);
  begin();assert(r["ok"]==true && r["next_offset"]==512);
  m["version"]="different";r.clear();ota.handle(m,r,true);assert(r["ok"]==false && ota.receiving());
  begin();chunk(512);assert(r["ok"]==true && writes==2 && r["next_offset"]==1024);
  begin();assert(r["ok"]==true && r["next_offset"]==1024 && begins==1);
  clockMs+=60001;ota.tick();assert(!ota.receiving() && aborts==1);
  begin();assert(r["ok"]==true && r["next_offset"]==0 && begins==2);
  chunk(512);assert(r["ok"]==false && !ota.receiving() && writes==2);
}
"""


class FirmwareResumeTests(unittest.TestCase):
    def test_actual_ota_handler_resumes_only_the_same_manifest_without_duplicate_flash(self):
        root = Path(__file__).resolve().parents[1]
        compiler = shutil.which("c++")
        if compiler is None:
            self.skipTest("C++ compiler unavailable")
        library = root / "firmware/.pio/libdeps/panel-bench/ArduinoJson/src"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "stub.h").write_text(STUB)
            for header in (
                "Arduino.h",
                "esp_ota_ops.h",
                "esp_timer.h",
                "sdkconfig.h",
                "esp_app_format.h",
                "mbedtls/sha256.h",
                "mbedtls/base64.h",
            ):
                path = directory / header
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('#include "stub.h"\n')
            source = directory / "resume.cpp"
            source.write_text("#include <string>\n" + PROGRAM)
            binary = directory / "resume"
            subprocess.run(
                [
                    compiler,
                    "-std=c++11",
                    "-I",
                    str(directory),
                    "-I",
                    str(root / "firmware/src"),
                    "-I",
                    str(library),
                    str(source),
                    str(root / "firmware/src/panel_ota.cpp"),
                    str(root / "firmware/src/signed_update.cpp"),
                    "-I",
                    str(root / "firmware/.vendor/mbedtls/include"),
                    str(root / "firmware/.vendor/mbedtls/build/library/libmbedcrypto.a"),
                    "-o",
                    str(binary),
                ],
                check=True,
                capture_output=True,
            )
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
