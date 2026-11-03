#include "panel_demo.h"
#include "demo_assets.h"
#include "panel_version.h"
#include <stdio.h>
#include <string.h>

constexpr int PanelDemo::MinHeightMm;
constexpr int PanelDemo::MaxHeightMm;

namespace {
constexpr uint16_t rgb(int r,int g,int b) { return ((r>>3)<<11)|((g>>2)<<5)|(b>>3); }
constexpr uint16_t Bg=rgb(36,17,19), Card=rgb(59,30,32), Selected=rgb(73,43,43), Ink=rgb(241,239,228), Muted=rgb(180,158,135), Gold=rgb(196,175,124), Disabled=rgb(101,78,70), Cream=rgb(241,239,228), Brown=rgb(96,59,60);
void rect(uint16_t *p,int x,int y,int w,int h,uint16_t c) {
  for(int yy=y; yy<y+h && yy<180; ++yy) if(yy>=0)
    for(int xx=x;xx<x+w && xx<640;++xx) if(xx>=0) p[yy*640+xx]=c;
}
uint16_t blend(uint16_t a,uint16_t b,int alpha) {
  int r=(((a>>11)&31)*(15-alpha)+((b>>11)&31)*alpha+7)/15;
  int g=(((a>>5)&63)*(15-alpha)+((b>>5)&63)*alpha+7)/15;
  int blue=((a&31)*(15-alpha)+(b&31)*alpha+7)/15;
  return (r<<11)|(g<<5)|blue;
}
int width(const char *text,int font) {
  int advance=0;for(const unsigned char *c=(const unsigned char*)text;*c;++c) if(*c>=32 && *c<=126) advance+=demoFonts[font].glyphs[*c-32].advance;
  return (advance+8)/16;
}
void text(uint16_t *p,int x,int baseline,const char *value,int font,uint16_t color) {
  const DemoFont &f=demoFonts[font];int pen=x*16;
  for(const unsigned char *c=(const unsigned char*)value;*c;++c) {
    if(*c<32 || *c>126) continue;
    const DemoGlyph &g=f.glyphs[*c-32];
    for(int yy=0;yy<g.height;++yy) for(int xx=0;xx<g.width;++xx) {
      int index=yy*g.width+xx;uint8_t packed=f.pixels[g.offset+index/2];int alpha=index%2 ? packed&15 : packed>>4;
      int px=(pen+8)/16+g.x+xx, py=baseline+g.y+yy;
      if(alpha && px>=0 && px<640 && py>=0 && py<180) p[py*640+px]=blend(p[py*640+px],color,alpha);
    }
    pen+=g.advance;
  }
}
void formatHeight(char *out,int mm,bool decimal=true) {
  if(decimal || mm%10) snprintf(out,20,"%d,%d",mm/10,mm%10); else snprintf(out,20,"%d",mm/10);
}
void base(uint16_t *p,int frame) {
  size_t offset=0;
  for(size_t n=0;n+1<demoFrameWords[frame] && offset<640*180;n+=2) {
    uint16_t count=demoFrames[frame][n],color=demoFrames[frame][n+1];
    while(count-- && offset<640*180) p[offset++]=color;
  }
}
void region(uint16_t *p,int frame,int sx,int sy,int w,int h,int dx,int dy,bool flip=false) {
  size_t offset=0;
  for(size_t n=0;n+1<demoFrameWords[frame] && offset<640*180;n+=2) {
    uint16_t count=demoFrames[frame][n],color=demoFrames[frame][n+1];
    while(count-- && offset<640*180) {
      int x=offset%640,y=offset/640;++offset;
      if(x>=sx && x<sx+w && y>=sy && y<sy+h) {
        int xx=dx+x-sx,yy=dy+(flip ? h-1-(y-sy) : y-sy);
        if(xx>=0 && xx<640 && yy>=0 && yy<180) p[yy*640+xx]=color;
      }
    }
  }
}
void number(uint16_t *p,int x,int baseline,int value,int font,uint16_t fg,uint16_t unit,bool decimal=true) {
  char h[20];formatHeight(h,value,decimal);text(p,x,baseline,h,font,fg);text(p,x+width(h,font)+6,baseline,"cm",2,unit);
}
}

const char *PanelDemo::name() const {
  static const char *names[]={"bureau","bevestigen","bewegen","offline","menu","monitor","voorkeuren","paneel","paneel_gedraaid","opstarten","verbinden","bijwerken","bijgewerkt","update_mislukt","obstakel","afstellen","ruststand"};return dimmed?"ruststand":names[screen];
}
void PanelDemo::draw(uint16_t *p) const {
  int frame=screen==SettingsRotated?Settings:screen; if(screen==Desk && !connected) frame=Offline; if(dimmed)frame=Sleep;
  base(p,frame);
  char value[80],h[20],other[20];
  if(dimmed || screen==Sleep) {
    if(height!=740) { rect(p,240,65,180,55,Bg);formatHeight(h,height);int x=(640-width(h,9)-width("cm",1)-4)/2;text(p,x,108,h,9,Disabled);text(p,x+width(h,9)+4,108,"cm",1,Disabled); }
  } else if(screen==Desk || screen==Confirm || screen==Offline) {
    bool offline=!connected || screen==Offline;
    rect(p,150,26,170,62,Bg);number(p,154,79,height,7,offline?Muted:Ink,Muted);
    rect(p,150,7,220,18,Bg);
    const char *label=offline ? "LAATST BEKEND" : screen==Confirm ? "HUIDIG" : height==sit ? "ZITHOOGTE" : height==stand ? "STAHOOGTE" : "BUREAUHOOGTE";
    text(p,154,21,label,0,Muted);
    if(screen==Confirm) {
      rect(p,358,31,134,45,Bg);formatHeight(h,target);
      int x=486-width(h,5)-width("cm",2)-4;text(p,x,69,h,5,Gold);text(p,x+width(h,5)+4,69,"cm",2,Gold);
      if(target<height) {
        region(p,0,500,8,132,164,500,8);
        rect(p,8,8,132,164,Gold);
        region(p,1,536,72,61,35,44,72,true);
      }
    } else {
      for(int n=0;n<2;++n) {
        int x=n?266:148;int preset=n?stand:sit;
        uint16_t bg=height==preset && !offline ? Selected : Card;
        uint16_t fg=offline?Disabled:(height==preset?Gold:Ink);
        rect(p,x,94,110,78,bg);text(p,x+12,122,n?"STAAN":"ZITTEN",0,offline?Disabled:(height==preset?Gold:Muted));
        formatHeight(h,preset,false);text(p,x+12,153,h,4,fg);
      }
      if(!offline) {
        rect(p,460,10,30,76,Bg);rect(p,472,15,4,64,Selected);rect(p,468,29,12,2,Gold);
        int level=74-(height-MinHeightMm)*53/(MaxHeightMm-MinHeightMm);rect(p,465,level,22,4,Ink);
      }
    }
  } else if(screen==Moving) {
    rect(p,35,65,275,81,Cream);number(p,40,128,height,8,Bg,Brown);
    if(manualHold) {
      rect(p,35,38,420,24,Cream);text(p,40,55,motionKind==3?"BUREAU OMHOOG - LOSLATEN OM TE STOPPEN":"BUREAU OMLAAG - LOSLATEN OM TE STOPPEN",0,Brown);
    } else if(target!=1120 || motionKind!=2) {
      rect(p,35,38,420,24,Cream);formatHeight(h,target,false);
      snprintf(value,sizeof(value),"NAAR %s - %s CM",motionKind==1?"ZITHOOGTE":motionKind==2?"STAHOOGTE":"DOELHOOGTE",h);text(p,40,55,value,0,Brown);
    }
  } else if(screen==Menu) {
    if(monitor!=70 || !monitorOn) { rect(p,154,50,200,22,Card);snprintf(value,sizeof(value),"%s - %d%%",monitorOn?"Aan":"Uit",monitor);text(p,158,64,value,1,Muted); }
    if(sit!=740 || stand!=1120) { rect(p,421,50,200,22,Card);formatHeight(h,sit,false);formatHeight(other,stand,false);snprintf(value,sizeof(value),"%s - %s cm",h,other);text(p,426,64,value,1,Muted); }
    if(dimMinutes!=1) { rect(p,154,136,200,22,Card);snprintf(value,sizeof(value),dimMinutes?"Dimmen na %d min":"Dimmen uit",dimMinutes);text(p,158,150,value,1,Muted); }
  } else if(screen==Monitor || screen==Settings || screen==SettingsRotated) {
    bool settings=screen==Settings || screen==SettingsRotated;int percent=settings?brightness:monitor;
    rect(p,334,19,132,58,Bg);snprintf(value,sizeof(value),"%d",percent);
    int x=458-width(value,6)-width("%",4);text(p,x,68,value,6,Ink);text(p,x+width(value,6),68,"%",4,Muted);
    rect(p,174,98,220,65,Bg);rect(p,180,130,208,6,Selected);int pos=180+208*percent/100;rect(p,180,130,pos-180,6,Gold);rect(p,pos-6,107,12,52,Ink);
    if(settings) {
      text(p,118,78,"Firmware " PANEL_FIRMWARE_VERSION,1,Muted);
      if(dimMinutes!=1) { rect(p,480,40,145,40,Card);snprintf(value,sizeof(value),dimMinutes?"Na %d min":"Uit",dimMinutes);text(p,486,68,value,4,Ink); }
      if(rotated) { rect(p,480,126,145,39,Card);text(p,486,152,"Gedraaid",4,Ink); }
    } else {
      if(!monitorOn) { rect(p,480,40,145,40,Card);text(p,496,68,"Uit",4,Ink); }
      if(input) { rect(p,480,126,145,39,Card);text(p,486,152,input==1?"HDMI 2":"DisplayPort",4,Ink); }
    }
  } else if(screen==Presets) {
    rect(p,112,70,288,80,Bg);number(p,118,122,height,6,Ink,Muted);
    for(int n=0;n<2;++n) {
      int y=n?94:8;uint16_t bg=savedPreset==n+1?Gold:Card;
      rect(p,408,y,224,78,bg);formatHeight(h,n?stand:sit,false);snprintf(value,sizeof(value),"%s - NU %s CM",n?"STAAN":"ZITTEN",h);
      text(p,422,y+27,value,0,savedPreset==n+1?Bg:Muted);formatHeight(h,height);snprintf(value,sizeof(value),savedPreset==n+1?"Opgeslagen":"%s opslaan",h);
      text(p,422,y+53,value,3,savedPreset==n+1?Bg:Ink);
    }
  }
  if(screen==Updating && !dimmed) {
    int percent=progress<0?0:progress>100?100:progress;
    rect(p,24,132,532,6,Selected);rect(p,24,132,532*percent/100,6,Gold);
    rect(p,570,120,70,50,Bg);snprintf(value,sizeof(value),"%d%%",percent);text(p,616-width(value,2),141,value,2,Ink);
    if(checkingUpdate) { rect(p,20,52,610,64,Bg);text(p,24,95,"Nieuwe firmware controleren",10,Ink);text(p,24,110,"Wacht op de bootbevestiging.",1,Muted); }
  }
  if(screen==Obstructed && height!=924 && !dimmed) {
    rect(p,20,108,425,25,Bg);formatHeight(h,height);snprintf(value,sizeof(value),"Bureau gestopt op %s cm. Haal het obstakel weg.",h);text(p,24,125,value,1,Muted);
  }
  int intensity=brightness;
  if(intensity<100) for(int i=0;i<640*180;++i) {
    uint16_t c=p[i];p[i]=((((c>>11)&31)*intensity/100)<<11)|((((c>>5)&63)*intensity/100)<<5)|((c&31)*intensity/100);
  }
  if(rotated) for(int i=0;i<640*180/2;++i) { uint16_t tmp=p[i];p[i]=p[640*180-1-i];p[640*180-1-i]=tmp; }
}
void PanelDemo::drawStatus(uint16_t *p,Screen phase,int percent,bool checking) const {
  PanelDemo view=*this;view.screen=phase;view.dimmed=false;view.progress=percent;view.checkingUpdate=checking;view.draw(p);
}
void PanelDemo::move(int value,int kind) {
  if(!connected || busy) return;
  value=clampHeight(value);
  if(height==value) { screen=Desk;dirty=true;return; }
  target=value;motionKind=kind;screen=Moving;lastTick=0;savedPreset=0;dirty=true;
}
void PanelDemo::setHeight(int value) { height=clampHeight(value);dirty=true; }
void PanelDemo::setBusy(bool value) {
  if(value && !busy) { if(screen==Moving)screen=Desk;manualHold=false;calibrating=false;consumed=true;dirty=true; }
  busy=value;
}
void PanelDemo::touchDown(int x,int y,uint32_t now) {
  if(x<0 || x>=640 || y<0 || y>=180 || busy || finger) return;
  if(rotated) { x=639-x;y=179-y; }
  finger=true;downX=x;downY=y;downAt=now;lastTouch=now;consumed=false;savedPreset=0;
  if(dimmed || screen==Sleep) { dimmed=false;if(screen==Sleep)screen=Desk;consumed=true;dirty=true; }
  else if(screen==Calibrate && x>=464 && x<632 && y>=8 && y<172) { calibrating=true;consumed=true;lastTick=now;dirty=true; }
  else if(screen==Moving) { screen=Desk;manualHold=false;consumed=true;lastTick=0;dirty=true; }
  else if((screen==Desk || screen==Confirm) && connected && y>=8 && y<172 && ((x>=8 && x<140) || (x>=500 && x<632))) {
    if(screen==Desk)target=height;
    motionKind=x<140?4:3;target+=x<140?-10:10;
    target=clampHeight(target);
    screen=Confirm;manualHold=true;consumed=true;lastTick=now;dirty=true;
  }
  else if((screen==Monitor || screen==Settings || screen==SettingsRotated) && x>=180 && x<388 && y>=98 && y<163) { tap(x,y,0);consumed=true; }
}
void PanelDemo::touchMove(int x,int y,uint32_t now) {
  if(rotated) { x=639-x;y=179-y; }
  if(calibrating && (x<464 || x>=632 || y<8 || y>=172)) { calibrating=false;consumed=true;lastTick=0; }

  if(finger && manualHold && (y<8 || y>=172 || (downX<140 ? (x<8 || x>=140) : (x<500 || x>=632)))) {
    manualHold=false;consumed=true;lastTick=0;dirty=true;return;
  }
  if(!finger || busy || (screen!=Monitor && screen!=Settings && screen!=SettingsRotated) || downX<180 || downX>=388 || downY<98 || downY>=163) return;
  if(screen==Monitor && !connected)return;
  if(x<180)x=180;if(x>388)x=388;
  int value=(x-180)*100/208;if((screen==Settings || screen==SettingsRotated) && value<10)value=10;
  int &setting=(screen==Settings || screen==SettingsRotated)?brightness:monitor;
  if(setting!=value) { setting=value;dirty=true; }lastTouch=now;
}
void PanelDemo::touchUp(uint32_t now) {
  if(!finger) return;finger=false;
  if(calibrating) { calibrating=false;lastTick=0;consumed=true;dirty=true;if(height==MinHeightMm)screen=Desk; }
  if(manualHold) { manualHold=false;lastTick=0;consumed=true;dirty=true; }
  if(!busy && !consumed && now-downAt>=30) tap(downX,downY,now-downAt);
  lastTouch=now;
}
void PanelDemo::tap(int x,int y,uint32_t held) {
  dirty=true;
  if(screen>=Boot) {
    if(held>=1000 && x<450) { scene(screen==Sleep?Desk:int(screen)+1,downAt+held);return; }
    if(screen==UpdateFailed && x>=464 && x<632) { screen=y<86?Connecting:Desk;return; }
    if(screen==Obstructed && x>=464 && x<632) { screen=Desk;return; }
    if(screen==Updated) { screen=Desk;return; }
    return;
  }
  if(screen==Desk || screen==Offline || screen==Confirm) {
    if(screen!=Confirm && x>=384 && x<492 && y>=94 && y<172) {
      if(held>=1000) { connected=!connected;screen=connected?Desk:Offline; } else screen=Menu;
      return;
    }
    if(!connected) return;
    if(y>=94 && y<172) {
      if(screen==Confirm) { if(x>=148 && x<256)screen=Desk;else if(x>=264 && x<492)move(target,motionKind==1 || motionKind==2?motionKind:0); }
      else if(x>=148 && x<258) { sit=clampHeight(sit);target=sit;motionKind=1;screen=Confirm; }
      else if(x>=266 && x<376) { stand=clampHeight(stand);target=stand;motionKind=2;screen=Confirm; }
    }
  } else if(x>=8 && x<96 && y>=8 && y<172) {
    if(held>=1500) { *this=PanelDemo();lastTouch=0; }
    else { screen=(screen==Menu || screen==Monitor)?(connected?Desk:Offline):Menu;savedPreset=0; }
  } else if(screen==Menu) {
    if(x>=104 && x<364 && y>=8 && y<86)screen=Monitor;
    else if(x>=372 && x<632 && y>=8 && y<86)screen=Presets;
    else if(x>=104 && x<364 && y>=94 && y<172)screen=rotated?SettingsRotated:Settings;
    else if(x>=372 && x<632 && y>=94 && y<172 && held>=1000)scene(Boot,downAt+held);
  } else if(screen==Monitor || screen==Settings || screen==SettingsRotated) {
    bool settings=screen==Settings || screen==SettingsRotated;if(!settings && !connected)return;
    int &value=settings?brightness:monitor;
    if(y>=94 && y<172 && x>=104 && x<172) { value-=5;if(value<(settings?10:0))value=settings?10:0; }
    else if(y>=94 && y<172 && x>=396 && x<464) { value+=5;if(value>100)value=100; }
    else if(x>=180 && x<388 && y>=98 && y<163) { value=(x-180)*100/208;if(settings && value<10)value=10; }
    else if(x>=472 && x<632 && y>=8 && y<86) {
      if(settings) { dimMinutes=dimMinutes==1?2:dimMinutes==2?5:dimMinutes==5?0:1; } else monitorOn=!monitorOn;
    } else if(x>=472 && x<632 && y>=94 && y<172) { if(settings) { rotated=!rotated;screen=rotated?SettingsRotated:Settings; }else input=(input+1)%3; }
  } else if(screen==Presets && connected && x>=408 && x<632) {
    if(y>=8 && y<86) { sit=clampHeight(height);savedPreset=1; } else if(y>=94 && y<172) { stand=clampHeight(height);savedPreset=2; }
  }
}
bool PanelDemo::tick(uint32_t now) {
  if(!busy && dimMinutes && screen!=Moving && screen<=SettingsRotated && !finger && now-lastTouch>uint32_t(dimMinutes)*60000 && !dimmed) { dimmed=true;dirty=true; }
  if(calibrating && finger && screen==Calibrate && !busy && now-lastTick>=100) {
    int step=(now-lastTick)*35/1000;if(step>7)step=7;if(step<1)step=1;
    height=clampHeight(height-step);lastTick=now;dirty=true;
  }
  if(manualHold && finger && screen==Confirm && !busy && connected && now-downAt>=350 && now-lastTick>=180) {
    int next=clampHeight(target+(motionKind==3?10:-10));
    if(next!=target) { target=next;dirty=true; }lastTick=now;
  }
  if(screen==Moving && !busy && connected && (freezeUntil==0 || int32_t(now-freezeUntil)>=0)) {
    if(!lastTick)lastTick=now;
    if(now-lastTick>=100) {
      int step=(now-lastTick)*35/1000;if(step>7)step=7;if(step<1)step=1;lastTick=now;
      if(target>height) { height+=step;if(height>=target){height=target;screen=Desk;} }
      else { height-=step;if(height<=target){height=target;screen=Desk;} }
      dirty=true;
    }
  }
  bool result=dirty;dirty=false;return result;
}
bool PanelDemo::scene(int index,uint32_t now) {
  if(index<0 || index>16 || busy)return false;
  *this=PanelDemo();screen=Screen(index);lastTouch=now;
  if(screen==Moving) { height=942;target=1120;motionKind=2;freezeUntil=now+5000; }
  if(screen==Offline)connected=false;
  if(screen==Presets)height=1086;
  if(screen==SettingsRotated)rotated=true;
  if(screen==Obstructed)height=924;
  if(screen==Sleep) { dimmed=true;screen=Desk; }
  return true;
}
