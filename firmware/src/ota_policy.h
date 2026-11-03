#pragma once
#include <stddef.h>

// The exact transfer admission policy is also compiled and tested on the Mac.
class TransferGuard {
 public:
  static constexpr size_t ChunkSize = 512;
  bool begin(size_t size, size_t capacity) {
    if (running || size < 288 || size > capacity) return false;
    expected = size; offset = 0; running = true;
    return true;
  }
  bool accepts(size_t position, size_t length) const {
    return running && position == offset && length > 0 && length <= ChunkSize && length <= expected - offset;
  }
  void advance(size_t length) { offset += length; }
  bool complete() const { return running && offset == expected; }
  void reset() { running = false; expected = 0; offset = 0; }
  bool running = false;
  size_t expected = 0, offset = 0;
};
