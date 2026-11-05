"""Compile the same standalone UI state machine and renderer used on the board."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PROGRAM = r"""
#include "panel_demo.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <string>
static void tap(PanelDemo &d,int x,int y,unsigned now,unsigned held=80) { d.touchDown(x,y,now);d.touchUp(now+held); }
int main(int argc,char **argv) {
  uint16_t *memory=new uint16_t[640*180+2];memory[0]=0x1234;memory[640*180+1]=0x5678;
  if(argc==2) {
    for(int scene=0;scene<17;++scene) {
      PanelDemo d;assert(d.scene(scene,100));d.draw(memory+1);
      std::string path=std::string(argv[1])+"/scene-"+std::to_string(scene+1)+".ppm";
      FILE *out=fopen(path.c_str(),"wb");assert(out);fprintf(out,"P6\n640 180\n255\n");
      for(int i=1;i<=640*180;++i) { unsigned c=memory[i];unsigned char rgb[3]={static_cast<unsigned char>(((c>>11)&31)*255/31),static_cast<unsigned char>(((c>>5)&63)*255/63),static_cast<unsigned char>((c&31)*255/31)};fwrite(rgb,1,3,out); }
      fclose(out);assert(memory[0]==0x1234 && memory[640*180+1]==0x5678);
    }
    return 0;
  }
  PanelDemo d;
  // Both a short tap and hold/release edit the target, never the current height.
  tap(d,560,80,100);assert(d.screen==PanelDemo::Confirm && d.height==740 && d.target==750);
  d.touchDown(560,80,300);assert(d.screen==PanelDemo::Confirm && d.target==760 && d.height==740);
  d.tick(300);d.tick(800);assert(d.target>760 && d.height==740);
  d.touchUp(900);int selected=d.target;d.tick(2000);assert(d.target==selected && d.height==740 && d.screen==PanelDemo::Confirm);
  d.touchDown(74,80,2100);assert(d.target==selected-10 && d.height==740);
  d.tick(2600);d.touchUp(2700);assert(d.target<selected-10 && d.height==740);
  int lower=d.target;d.tick(4000);assert(d.target==lower && d.height==740);
  tap(d,200,130,4100);assert(d.screen==PanelDemo::Desk && d.height==740);
  tap(d,560,80,4300);assert(d.target==750);tap(d,350,130,4400);assert(d.screen==PanelDemo::Moving);
  d.tick(4500);d.tick(4700);assert(d.height>740 && d.height<750);
  d.touchDown(10,10,4800);assert(d.screen==PanelDemo::Desk);d.touchUp(4900);
  d=PanelDemo();tap(d,300,130,100);assert(d.screen==PanelDemo::Confirm && d.target==1120);tap(d,350,130,200);assert(d.screen==PanelDemo::Moving);
  for(unsigned now=200;now<20000;now+=100)d.tick(now);
  assert(d.height==1120 && d.screen==PanelDemo::Desk);
  d=PanelDemo();tap(d,420,130,100,1200);assert(!d.connected && d.screen==PanelDemo::Offline);
  tap(d,560,80,1400);assert(d.screen==PanelDemo::Offline);
  tap(d,420,130,1600);assert(d.screen==PanelDemo::Menu);
  tap(d,180,50,1800);assert(d.screen==PanelDemo::Monitor);tap(d,430,130,2000);assert(d.monitor==70);
  tap(d,50,90,2200);assert(d.screen==PanelDemo::Offline);tap(d,420,130,2300);tap(d,180,130,2400);assert(d.screen==PanelDemo::Settings);tap(d,130,130,2600);assert(d.brightness==95);
  d=PanelDemo();d.setHeight(1086);tap(d,420,130,100);tap(d,500,50,300);assert(d.screen==PanelDemo::Presets);
  tap(d,500,50,500);assert(d.sit==1086 && d.stand==1120);
  tap(d,500,130,700);assert(d.stand==1086);
  d=PanelDemo();tap(d,300,130,100);tap(d,350,130,200);d.setBusy(true);assert(d.screen==PanelDemo::Desk);
  tap(d,560,80,300);assert(d.screen==PanelDemo::Desk);d.setBusy(false);
  d=PanelDemo();assert(d.scene(5,100));d.touchDown(200,130,200);d.touchMove(360,130,300);d.touchUp(400);assert(d.monitor==86);
  d=PanelDemo();d.tick(60001);assert(d.dimmed);tap(d,420,130,61000);assert(!d.dimmed && d.screen==PanelDemo::Desk);
  tap(d,420,130,62000);assert(d.screen==PanelDemo::Menu);
  for(int scene=0;scene<17;++scene) { assert(d.scene(scene,100));d.draw(memory+1);assert(memory[0]==0x1234 && memory[640*180+1]==0x5678); }
  // Limits apply to taps, repeated holds, presets and confirmed travel.
  d=PanelDemo();d.setHeight(500);assert(d.height==620);
  d.setHeight(1300);assert(d.height==1270);
  d=PanelDemo();d.setHeight(1266);tap(d,560,80,100);assert(d.target==1270 && d.height==1266);
  d.touchDown(560,80,300);d.tick(1000);d.tick(2000);d.touchUp(2100);assert(d.target==1270 && d.height==1266);
  tap(d,350,130,2200);for(unsigned now=2300;now<3300;now+=100)d.tick(now);
  assert(d.height==1270 && d.screen==PanelDemo::Desk);
  d=PanelDemo();d.setHeight(624);tap(d,74,80,100);assert(d.target==620 && d.height==624);
  d.touchDown(74,80,300);d.tick(1000);d.tick(2000);d.touchUp(2100);assert(d.target==620 && d.height==624);
  tap(d,350,130,2200);for(unsigned now=2300;now<3300;now+=100)d.tick(now);
  assert(d.height==620 && d.screen==PanelDemo::Desk);
  d=PanelDemo();d.stand=2000;tap(d,300,130,100);assert(d.target==1270 && d.stand==1270);
  d=PanelDemo();d.sit=400;tap(d,200,130,100);assert(d.target==620 && d.sit==620);
  // New two-row menu targets and global 180-degree touch mapping.
  d=PanelDemo();tap(d,420,130,100);tap(d,180,130,300);assert(d.screen==PanelDemo::Settings);
  tap(d,500,130,500);assert(d.rotated && d.screen==PanelDemo::SettingsRotated);
  d.touchDown(639-200,179-130,600);d.touchMove(639-360,179-130,620);d.touchUp(640);assert(d.brightness==86);
  tap(d,639-50,179-90,700);assert(d.screen==PanelDemo::Menu && d.rotated);
  tap(d,639-180,179-50,900);assert(d.screen==PanelDemo::Monitor);
  tap(d,639-430,179-130,1100);assert(d.monitor==75);
  // Rotation affects every pixel, not just the settings screen.
  d=PanelDemo();PanelDemo flipped;flipped.rotated=true;
  uint16_t *normal=new uint16_t[640*180];d.draw(normal);flipped.draw(memory+1);
  for(int i=0;i<640*180;++i)assert(normal[i]==memory[640*180-i]);delete[] normal;
  assert(d.scene(16,100));assert(d.dimmed && std::string(d.name())=="ruststand");
  tap(d,400,80,300);assert(!d.dimmed && d.screen==PanelDemo::Desk);
  // Recalibration is a bounded local simulation that stops on release.
  assert(d.scene(15,100));d.touchDown(550,80,200);d.tick(400);int heldHeight=d.height;assert(heldHeight<740);
  d.touchUp(500);d.tick(1000);assert(d.height==heldHeight && d.screen==PanelDemo::Calibrate);
  assert(d.scene(13,100));tap(d,550,50,300);assert(d.screen==PanelDemo::Connecting);
  assert(d.scene(13,100));tap(d,550,130,300);assert(d.screen==PanelDemo::Desk);
  assert(d.scene(14,100));assert(d.height==924);tap(d,550,80,300);assert(d.screen==PanelDemo::Desk);
  assert(!d.scene(-1,100) && !d.scene(17,100));
  // Production readings are never substituted by a target or a demo preset.
  d=PanelDemo();PanelDeviceState live;live.heightKnown=true;live.heightFresh=true;live.heightMm=1086;
  live.monitorKnown=true;live.monitorFresh=false;live.monitorBrightness=83;
  snprintf(live.monitorBus,sizeof(live.monitorBus),"20");snprintf(live.monitorPower,sizeof(live.monitorPower),"off");snprintf(live.monitorSource,sizeof(live.monitorSource),"USBC");
  d.setDeviceState(live);assert(d.readOnly && d.height==1086);
  tap(d,560,80,100);d.tick(1000);assert(d.height==1086 && d.screen==PanelDemo::Desk);
  tap(d,200,130,1100);assert(d.screen==PanelDemo::Desk);
  tap(d,420,130,1200);assert(d.screen==PanelDemo::Menu);tap(d,180,50,1400);assert(d.screen==PanelDemo::Monitor);
  tap(d,430,130,1600);tap(d,550,50,1800);assert(d.deviceState.monitorBrightness==83 && std::string(d.deviceState.monitorPower)=="off");
  d.draw(memory+1);assert(memory[0]==0x1234 && memory[640*180+1]==0x5678);
  d.setDeviceState(PanelDeviceState{});assert(d.readOnly && !d.deviceState.heightKnown && d.height==0);
  d.draw(memory+1);assert(memory[0]==0x1234 && memory[640*180+1]==0x5678);
  // Updates are reachable with a tap, including in read-only production mode.
  d=PanelDemo();d.setDeviceState(live);tap(d,420,130,100);tap(d,500,130,300);
  assert(d.screen==PanelDemo::Updates && d.idleForUpdate());
  tap(d,200,145,500);assert(d.updateAction==PanelDemo::CheckUpdate);
  d.updateAction=PanelDemo::NoUpdateAction;tap(d,500,145,700);assert(d.updateAction==PanelDemo::NoUpdateAction);
  d.updateView("Nieuwe firmware beschikbaar","0.9.0",true,0);
  tap(d,500,145,900);assert(d.updateAction==PanelDemo::InstallUpdate);
  d.setBusy(true);d.updateAction=PanelDemo::NoUpdateAction;tap(d,50,90,1100);tap(d,200,145,1300);
  assert(d.screen==PanelDemo::Updates && d.updateAction==PanelDemo::NoUpdateAction);
  d.draw(memory+1);assert(memory[0]==0x1234 && memory[640*180+1]==0x5678);
  d.setBusy(false);tap(d,50,90,1500);assert(d.screen==PanelDemo::Menu);
  delete[] memory;
}
"""


class PanelDemoTests(unittest.TestCase):
    def test_standalone_navigation_motion_stop_offline_presets_and_frame_bounds(self):
        compiler = shutil.which("c++")
        if compiler is None:
            self.skipTest("C++ compiler unavailable")
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "demo.cpp"
            binary = Path(temp) / "demo"
            source.write_text(PROGRAM)
            subprocess.run(
                [
                    compiler,
                    "-std=c++11",
                    "-I",
                    str(root / "firmware/src"),
                    str(source),
                    str(root / "firmware/src/panel_demo.cpp"),
                    str(root / "firmware/src/demo_assets.cpp"),
                    "-o",
                    str(binary),
                ],
                check=True,
                capture_output=True,
            )
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
