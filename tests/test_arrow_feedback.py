"""Arrow press colour must follow the active gesture, not the selected target."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PROGRAM = r"""
#include "panel_demo.h"
#include <cassert>
#include <cstdio>
#include <string>
static uint16_t normal[640*180], pressed[640*180], released[640*180];
static void sameButtons(bool rotated) {
  for(int y=8;y<172;++y)for(int x=8;x<632;++x)if(x<140 || x>=500) {
    int i=y*640+x;if(rotated)i=640*180-1-i;
    assert(released[i]==normal[i] && "arrow remains highlighted after release");
  }
}
static void frame(const char *dir,const char *name,uint16_t *pixels) {
  FILE *out=fopen((std::string(dir)+"/"+name+".ppm").c_str(),"wb");assert(out);fprintf(out,"P6\n640 180\n255\n");
  for(int i=0;i<640*180;++i) {unsigned c=pixels[i];unsigned char rgb[3]={static_cast<unsigned char>(((c>>11)&31)*255/31),static_cast<unsigned char>(((c>>5)&63)*255/63),static_cast<unsigned char>((c&31)*255/31)};fwrite(rgb,1,3,out);}fclose(out);
}
int main(int argc,char **argv) {
  for(bool rotated:{false,true})for(int direction:{-1,1})for(int operation=0;operation<4;++operation) {
    PanelDemo d;d.rotated=rotated;d.draw(normal);int x=direction>0?560:74,y=80;
    if(rotated){x=639-x;y=179-y;}
    d.touchDown(x,y,100);d.draw(pressed);assert(d.screen==PanelDemo::Confirm && d.target==740+direction*10 && d.height==740);
    int pixel=20*640+(direction>0?515:20);if(rotated)pixel=640*180-1-pixel;
    assert(pressed[pixel]!=normal[pixel] && "held arrow has no press feedback");
    if(operation==1)d.tick(700); // hold/release
    if(operation==2)d.touchMove(rotated?639-300:300,rotated?179-80:80,200); // leave button
    if(operation==3)d.setBusy(true); // interrupted gesture
    int target=d.target;d.touchUp(800);d.tick(900);d.draw(released);sameButtons(rotated);
    assert(d.height==740 && d.target==target);
    if(argc==2 && !rotated && direction==1 && operation==0) {frame(argv[1],"arrow-held",pressed);frame(argv[1],"arrow-released",released);}
  }
  PanelDemo preset;preset.draw(normal);preset.touchDown(300,130,100);preset.touchUp(180);preset.draw(released);sameButtons(false);
}
"""


class ArrowFeedbackTests(unittest.TestCase):
    def test_release_hold_leave_busy_rotation_and_preset_colours(self):
        compiler = shutil.which("c++")
        if compiler is None:
            self.skipTest("C++ compiler unavailable")
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "arrows.cpp"
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
