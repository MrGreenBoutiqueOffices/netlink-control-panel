"""Test the actual firmware status lease and render the read-only UI."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PROGRAM = r"""
#include "production_protocol.h"
#include "panel_demo.h"
#include <cassert>
#include <cstdio>
#include <string>
void frame(PanelDemo &demo,const char *directory,const char *name) {
  uint16_t pixels[640*180];demo.draw(pixels);
  FILE *out=fopen((std::string(directory)+"/"+name+".ppm").c_str(),"wb");assert(out);fprintf(out,"P6\n640 180\n255\n");
  for(auto c:pixels) {unsigned char rgb[3]={static_cast<unsigned char>(((c>>11)&31)*255/31),static_cast<unsigned char>(((c>>5)&63)*255/63),static_cast<unsigned char>((c&31)*255/31)};fwrite(rgb,1,3,out);}fclose(out);
}
int main(int argc,char **argv) {
  ProductionSession session;StaticJsonDocument<1536> in,out;
  assert(!deserializeJson(in,R"({"type":"hello","id":1,"session":"0123456789abcdef0123456789abcdef","protocol_min":2,"protocol_max":2})"));
  assert(session.handle(in,out,0,"panel-test","0.7.0","0123456789abcdef",true,"valid"));
  assert(!deserializeJson(in,R"({"type":"device.state","id":2,"session":"0123456789abcdef0123456789abcdef","revision":1,"valid_for_ms":2000,"desk":{"height_mm":1086,"fresh":true},"monitor":{"bus":"20","brightness":83,"power":"off","source":"USBC","fresh":true}})"));
  assert(session.handle(in,out,100,"panel-test","0.7.0","0123456789abcdef",true,"valid"));
  assert(session.devices.heightMm==1086 && session.devices.heightKnown && session.devices.monitorBrightness==83);
  assert(!session.expire(2099));assert(session.expire(2100));assert(!session.devices.heightKnown && !session.devices.monitorKnown);
  // A stale or malformed message cannot renew the lease or replace accepted data.
  assert(!session.handle(in,out,2200,"panel-test","0.7.0","0123456789abcdef",true,"valid"));assert(session.deviceLease==0);
  in["revision"]=2;in["monitor"]["power"]="invalid";assert(!session.handle(in,out,2300,"panel-test","0.7.0","0123456789abcdef",true,"valid"));
  in["monitor"]["power"]="standby";in["desk"]["height_mm"]=610;assert(session.handle(in,out,2400,"panel-test","0.7.0","0123456789abcdef",true,"valid"));
  assert(session.devices.heightMm==610); // observed height is never clamped to the command limits.
  session.clear();assert(!session.connected() && !session.devices.heightKnown);
  if(argc==2) {
    PanelDemo demo;PanelDeviceState value;value.heightKnown=value.heightFresh=value.monitorKnown=value.monitorFresh=true;
    value.heightMm=1086;value.monitorBrightness=83;strcpy(value.monitorBus,"20");strcpy(value.monitorPower,"off");strcpy(value.monitorSource,"USBC");
    demo.setDeviceState(value);frame(demo,argv[1],"height-current");demo.screen=PanelDemo::Monitor;frame(demo,argv[1],"monitor-current");
    value.heightFresh=value.monitorFresh=false;demo.setDeviceState(value);demo.screen=PanelDemo::Desk;frame(demo,argv[1],"height-last-known");
    demo.setDeviceState(PanelDeviceState{});frame(demo,argv[1],"height-unknown");demo.screen=PanelDemo::Monitor;frame(demo,argv[1],"monitor-unknown");
  }
}
"""


class DeviceStateTests(unittest.TestCase):
    def test_atomic_status_validation_expiry_and_renderer(self):
        root = Path(__file__).resolve().parents[1]
        library = root / "firmware/.pio/libdeps/panel-bench/ArduinoJson/src"
        if not shutil.which("c++") or not (library / "ArduinoJson.h").exists():
            self.skipTest("Build firmware for the pinned ArduinoJson headers")
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "device.cpp"
            binary = source.with_suffix("")
            source.write_text(PROGRAM)
            subprocess.run(
                [
                    "c++",
                    "-std=c++11",
                    "-I",
                    str(root / "firmware/src"),
                    "-I",
                    str(library),
                    str(source),
                    str(root / "firmware/src/panel_demo.cpp"),
                    str(root / "firmware/src/demo_assets.cpp"),
                    "-o",
                    str(binary),
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run([str(binary), temp], check=True, capture_output=True)
            self.assertEqual(len(list(Path(temp).glob("*.ppm"))), 5)
            for path in Path(temp).glob("*.ppm"):
                self.assertTrue(path.read_bytes().startswith(b"P6\n640 180\n255\n"))
