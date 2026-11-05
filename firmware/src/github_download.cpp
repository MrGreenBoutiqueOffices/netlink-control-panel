#include "github_download.h"
#include "github_release.h"
#include "github_roots.h"
#include "github_http.h"
#include <WiFiClientSecure.h>

class GithubDownload::Sink : public Stream {
 public:
  GithubDownload &owner;
  Event event;
  size_t count=0;
  uint32_t started;
  explicit Sink(GithubDownload &owner):owner(owner),started(millis()) {}
  int available() override { return 0; }
  int read() override { return -1; }
  int peek() override { return -1; }
  void flush() override {}
  size_t write(uint8_t value) override { return write(&value,1); }
  size_t write(const uint8_t *data,size_t size) override {
    if(owner.cancelled || millis()-started>owner.timeoutMs || size>owner.limit-count)return 0;
    for(size_t i=0;i<size;i++) {
      event.bytes[event.length++]=data[i];
      if(event.length==sizeof(event.bytes)) { if(!owner.deliver(event))return 0;event.length=0; }
    }
    count+=size;return size;
  }
};

bool GithubDownload::begin() {
  events=xQueueCreate(4,sizeof(Event));
  if(!events)return false;
  if(xTaskCreate([](void *context){static_cast<GithubDownload *>(context)->run();},"github-download",12288,this,1,&task)!=pdPASS) {
    vQueueDelete(events);events=nullptr;return false;
  }
  return true;
}
bool GithubDownload::start(const char *address,size_t maximum,bool binary,uint32_t deadline) {
  if(!task || running || !githubUpdateUrl(address))return false;
  strlcpy(url,address,sizeof(url));limit=maximum;asset=binary;timeoutMs=deadline;cancelled=false;running=true;
  xTaskNotifyGive(task);return true;
}
bool GithubDownload::poll(Event &event) {
  if(!events || xQueueReceive(events,&event,0)!=pdTRUE)return false;
  if(event.done)running=false;
  return true;
}
bool GithubDownload::deliver(Event &event) {
  while(!cancelled) if(xQueueSend(events,&event,pdMS_TO_TICKS(100))==pdTRUE)return true;
  return false;
}
void GithubDownload::run() {
  for(;;) {
    ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
    String address=url;
    bool ok=false;
    uint32_t started=millis();
    for(unsigned redirect=0;redirect<=3 && !cancelled;redirect++) {
      if(millis()-started>timeoutMs || !githubUpdateUrl(address.c_str()))break;
      int slash=address.indexOf('/',8);
      String host=address.substring(8,slash),path=address.substring(slash);
      WiFiClientSecure tls;
      tls.setCACert(GithubRootCAs);tls.setHandshakeTimeout(8);tls.setTimeout(5);
      if(!tls.connect(host.c_str(),443,5000))break;
      String request="GET "+path+" HTTP/1.0\r\nHost: "+host+"\r\nUser-Agent: NetLink-Panel/1\r\nAccept: ";
      request+=asset?"application/octet-stream":"application/vnd.github+json";
      request+="\r\nX-GitHub-Api-Version: 2022-11-28\r\nConnection: close\r\n\r\n";
      if(tls.write(reinterpret_cast<const uint8_t *>(request.c_str()),request.length())!=request.length())break;
      GithubHttpHeaders headers;
      while(!headers.complete && !headers.failed && !cancelled && millis()-started<=timeoutMs) {
        if(tls.available())headers.accept(tls.read());
        else if(!tls.connected())break;
        else vTaskDelay(pdMS_TO_TICKS(1));
      }
      if(!headers.complete || headers.failed || cancelled)break;
      if(headers.redirect()) {address=headers.location;continue;}
      if(headers.code!=200 || !headers.hasLength || !headers.length || headers.length>limit)break;
      Sink sink(*this);sink.started=started;
      while(sink.count<headers.length && !cancelled && millis()-started<=timeoutMs) {
        int available=tls.available();
        if(available) {
          uint8_t data[512];size_t n=min(size_t(available),min(sizeof(data),headers.length-sink.count));
          int got=tls.read(data,n);
          if(got<=0 || sink.write(data,got)!=size_t(got))break;
        } else if(!tls.connected())break;
        else vTaskDelay(pdMS_TO_TICKS(1));
      }
      ok=sink.count==headers.length && millis()-started<=timeoutMs && !cancelled;
      if(ok && sink.event.length)ok=deliver(sink.event);
      break;
    }
    Event end;end.done=true;end.ok=ok;
    // Completion must be delivered even after cancellation, before another job.
    while(xQueueSend(events,&end,pdMS_TO_TICKS(100))!=pdTRUE) {}
  }
}
