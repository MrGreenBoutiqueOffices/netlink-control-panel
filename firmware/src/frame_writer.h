#pragma once
#include <ArduinoJson.h>

template <typename Sink>
bool writeJsonFrame(JsonDocument &message, Sink &sink, char *buffer, size_t capacity) {
  const size_t length = measureJson(message);
  if (length > 1024 || length >= capacity) return false;
  if (serializeJson(message, buffer, capacity) != length) return false;
  buffer[length] = '\n';
  return sink.write(reinterpret_cast<const uint8_t *>(buffer), length + 1) == length + 1;
}
