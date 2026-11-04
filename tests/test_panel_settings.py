"""Exercise the exact firmware journal with interrupted writes and rebooted instances."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PROGRAM = r"""
#include "panel_settings.h"
#include "panel_demo.h"
#include <cassert>
#include <algorithm>
#include <string>
struct Storage {
  std::string slots[2]; int cut=-1, writes=0;bool failRead=false;
  bool read(int slot,uint8_t *out,size_t n) {if(failRead || slots[slot].size()!=n)return false;memcpy(out,slots[slot].data(),n);return true;}
  bool write(int slot,const uint8_t *bytes,size_t n) {++writes;slots[slot]=std::string(reinterpret_cast<const char*>(bytes),cut<0?n:std::min(n,size_t(cut)));return cut<0;}
};
static void tap(PanelDemo &d,int x,int y,uint32_t now) {d.touchDown(x,y,now);d.touchUp(now+80);}
int main() {
  Storage disk;PanelSettingsJournal<Storage> first(disk);first.load();
  assert(first.revision==0 && first.applied.brightness==100 && first.applied.dimMinutes==1 && !first.applied.rotated);
  PanelSettings one;one.brightness=35;one.rotated=true;one.dimMinutes=5;
  assert(first.save(one) && first.revision==1 && disk.writes==1);
  assert(first.save(one) && disk.writes==1); // identical touches never wear flash.
  PanelSettingsJournal<Storage> reboot(disk);reboot.load();assert(reboot.applied==one && reboot.revision==1);
  PanelSettings two=one;two.brightness=80;two.dimMinutes=0;
  for(int cut=0;cut<int(first.RecordSize);++cut) {
    Storage interrupted=disk;interrupted.cut=cut;PanelSettingsJournal<Storage> writer(interrupted);writer.load();
    assert(!writer.save(two) && writer.applied==one && writer.revision==1 && writer.writeFailed);
    PanelSettingsJournal<Storage> recovered(interrupted);recovered.load();assert(recovered.applied==one && recovered.revision==1);
  }
  // A successful second write survives; corruption of its checksum falls back to the preceding revision.
  assert(reboot.save(two) && reboot.revision==2);
  PanelSettingsJournal<Storage> again(disk);again.load();assert(again.applied==two && again.revision==2);
  for(size_t i=0;i<first.RecordSize;++i) {
    Storage corrupt=disk;corrupt.slots[1][i]^=1;PanelSettingsJournal<Storage> reader(corrupt);reader.load();assert(reader.applied==one && reader.revision==1);
  }
  // Interrupt an overwrite of the older slot, with two valid revisions already present.
  for(int cut=0;cut<int(first.RecordSize);++cut) {
    Storage interrupted=disk;interrupted.cut=cut;PanelSettingsJournal<Storage> writer(interrupted);writer.load();
    assert(!writer.save(one));PanelSettingsJournal<Storage> recovered(interrupted);recovered.load();assert(recovered.applied==two && recovered.revision==2);
  }
  disk.slots[0]="corrupt";disk.slots[1]="invalid";again.load();assert(again.applied==PanelSettings{} && again.revision==0);
  int count=disk.writes;PanelSettings invalid;invalid.brightness=0;assert(!again.save(invalid));invalid.brightness=101;assert(!again.save(invalid));invalid.brightness=50;invalid.dimMinutes=3;assert(!again.save(invalid));assert(disk.writes==count);
  // Future schemas cannot be overwritten by older firmware, even when an older readable record exists.
  Storage future;PanelSettingsJournal<Storage> old(future);old.load();assert(old.save(one));future.slots[1]=future.slots[0];future.slots[1][2]=2;
  PanelSettingsJournal<Storage> downgraded(future);downgraded.load();assert(downgraded.applied==one && !downgraded.writable && !downgraded.save(two));
  // Read-back failure never acknowledges a newly applied revision.
  Storage unreadable;PanelSettingsJournal<Storage> unavailable(unreadable);unavailable.load();unreadable.failRead=true;assert(!unavailable.save(one) && unavailable.revision==0 && unavailable.applied==PanelSettings{});
  // Rotation is shared by every pixel and touch mapping; wake does not activate a setting.
  PanelDemo d;d.applySettings(one);d.screen=PanelDemo::SettingsRotated;
  d.tick(300001);assert(d.dimmed);tap(d,639-130,179-130,300100);assert(!d.dimmed && d.brightness==35);
  tap(d,639-130,179-130,300300);assert(d.brightness==30 && d.rotated);
  tap(d,639-500,179-50,300500);assert(d.dimMinutes==0);d.tick(900000);assert(!d.dimmed);
  d.scene(PanelDemo::Desk,900100,true);assert(d.brightness==30 && d.rotated && d.dimMinutes==0);
  d.screen=PanelDemo::SettingsRotated;tap(d,639-50,179-90,900200);assert(d.screen==PanelDemo::Menu && d.rotated);
  d.touchDown(639-50,179-90,900400);d.touchUp(902000);assert(d.rotated && d.brightness==30 && d.dimMinutes==0);
}
"""


class PanelSettingsTests(unittest.TestCase):
    def test_reboot_validation_interruption_fallback_and_touch(self):
        compiler = shutil.which("c++")
        if compiler is None:
            self.skipTest("C++ compiler unavailable")
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "settings.cpp"
            binary = source.with_suffix("")
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
