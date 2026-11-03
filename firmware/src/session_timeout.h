#pragma once
#include <stdint.h>

constexpr uint32_t ControlSessionTimeoutMs = 3500;
constexpr uint32_t OtaTransferTimeoutMs = 15000;
// Retain the inactive-slot handle briefly while an authenticated peer reconnects.
constexpr uint32_t OtaResumeTimeoutMs = 60000;

constexpr bool sessionExpired(bool receivingOta, uint32_t silenceMs) {
  return silenceMs > (receivingOta ? OtaTransferTimeoutMs : ControlSessionTimeoutMs);
}
