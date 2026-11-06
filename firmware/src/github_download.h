#pragma once
#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include <atomic>

// Network work never calls the renderer, flash writer or NVS. Only the Arduino
// loop owns those. A four-chunk queue bounds memory and provides backpressure.
class GithubDownload {
 public:
  struct Event { uint16_t length=0; bool done=false, ok=false; uint8_t bytes[512]={}; };
  bool begin();
  bool start(const char *url,size_t limit,bool asset,uint32_t timeoutMs);
  bool poll(Event &event);
  void cancel() { cancelled=true; }
  bool active() const { return running; }
 private:
  QueueHandle_t events=nullptr;
  TaskHandle_t task=nullptr;
  char url[2049]={};
  size_t limit=0;
  uint32_t timeoutMs=0;
  bool asset=false,running=false;
  std::atomic<bool> cancelled{false};
  void run();
  bool deliver(Event &event);
  class Sink;
};
