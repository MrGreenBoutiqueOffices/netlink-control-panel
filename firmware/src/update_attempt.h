#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

// One NVS blob is committed atomically. An interrupted download always restarts
// from byte zero, with a fresh signed preflight and a new inactive-slot handle.
enum class UpdatePhase : uint8_t { Empty, Downloading, BootPending, Succeeded, Interrupted, RolledBack, Failed };
struct UpdateAttempt {
  uint32_t schema=1;
  UpdatePhase phase=UpdatePhase::Empty;
  uint8_t reserved[3]={};
  char image[65]={}, version[32]={}, identity[65]={};
  uint8_t alignment[2]={};
  uint32_t checksum=0;
  uint32_t crc() const {
    uint32_t value=0xffffffff;
    const uint8_t *p=reinterpret_cast<const uint8_t *>(this);
    for(size_t i=0;i<offsetof(UpdateAttempt,checksum);i++) {
      value^=p[i];for(int bit=0;bit<8;bit++)value=(value>>1)^(0xedb88320U & (0U-(value&1)));
    }
    return ~value;
  }
  bool valid() const {
    return schema==1 && phase<=UpdatePhase::Failed && checksum==crc() && image[64]==0 && version[31]==0 && identity[64]==0;
  }
  UpdatePhase reconcile(const char *running,bool pending) const {
    if(phase==UpdatePhase::Downloading)return UpdatePhase::Interrupted;
    if(phase!=UpdatePhase::BootPending)return phase;
    if(strcmp(image,running))return UpdatePhase::RolledBack;
    return pending?UpdatePhase::BootPending:UpdatePhase::Succeeded;
  }
};
