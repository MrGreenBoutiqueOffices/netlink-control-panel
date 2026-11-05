#pragma once
#include <stddef.h>
#include <stdint.h>
struct UpdateKey { const uint8_t *id; const uint8_t *der; size_t length; bool revoked; };
struct UpdatePolicy { bool signedOnly; const char *boardRevision; uint16_t protocol; uint64_t minimumCounter; const UpdateKey *keys; size_t keyCount; };
struct UpdateAuthorization {
  uint32_t size;
  char sha256[65], imageSha256[65], version[32], manifestSha256[65], commit[41];
  uint64_t counter;
  uint16_t protocolMin, protocolMax;
  char boardRevision[33];
  uint8_t identity[32];
};
inline UpdatePolicy benchUpdatePolicy() { return {false, "unverified", 2, 0, nullptr, 0}; }
// Pure preflight: never touches flash, boot selection or an existing transfer.
bool verifyUpdate(const uint8_t *record, size_t length, const uint8_t *signature, size_t signatureLength,
                  const UpdatePolicy &policy, UpdateAuthorization &output);
