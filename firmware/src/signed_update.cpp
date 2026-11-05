#include "signed_update.h"
#include <string.h>
#include <stdio.h>
#include <mbedtls/md.h>
#include <mbedtls/pk.h>

namespace {
const uint8_t domain[] = "NETLINK-PANEL-OTA\0\x01";
uint64_t integer(const uint8_t *p, size_t length) {
  uint64_t result = 0;
  while (length--) result = (result << 8) | *p++;
  return result;
}
bool identifier(const uint8_t *&p, const uint8_t *end, char *out, size_t maximum) {
  if (p == end) return false;
  size_t n = *p++;
  if (!n || n > maximum || size_t(end-p) < n) return false;
  for (size_t i = 0; i < n; i++) {
    uint8_t c = p[i];
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == ':' || c == '-')) return false;
  }
  memcpy(out, p, n); out[n] = 0; p += n; return true;
}
bool canonicalSignature(const uint8_t *p, size_t n) {
  if (n < 8 || n > 72 || p[0] != 0x30 || p[1] != n-2) return false;
  size_t at = 2;
  for (int i = 0; i < 2; i++) {
    if (at+2 > n || p[at++] != 2) return false;
    size_t count = p[at++];
    if (!count || count > 33 || at+count > n || (p[at]&0x80) ||
        (count == 1 && p[at] == 0) || (count > 1 && p[at] == 0 && !(p[at+1]&0x80))) return false;
    at += count;
  }
  return at == n;
}
void hex(const uint8_t *p, char *out) {
  for (size_t i=0; i<32; i++) sprintf(out+2*i, "%02x", p[i]);
  out[64]=0;
}
}

bool verifyUpdate(const uint8_t *record, size_t length, const uint8_t *signature, size_t signatureLength,
                  const UpdatePolicy &policy, UpdateAuthorization &output) {
  constexpr size_t prefix = sizeof(domain)-1;
  if (!policy.signedOnly || !policy.boardRevision || !strcmp(policy.boardRevision,"unverified") || !*policy.boardRevision ||
      !record || !signature || length < prefix+152 || length > 340 || memcmp(record,domain,prefix) ||
      !canonicalSignature(signature,signatureLength) || policy.keyCount > 4) return false;
  const uint8_t *p = record+prefix, *end = record+length;
  const UpdateKey *key = nullptr;
  for (size_t i=0;i<policy.keyCount;i++) if (!memcmp(policy.keys[i].id,p,16)) {
    if (key) return false; // Ambiguous configuration must fail closed.
    key = &policy.keys[i];
  }
  if (!key || key->revoked || !key->der || key->length > 128) return false;
  p += 16;
  uint64_t counter = integer(p,8); p += 8;
  uint16_t low = integer(p,2); p += 2;
  uint16_t high = integer(p,2); p += 2;
  UpdateAuthorization candidate = {};
  candidate.size = integer(p,4); p += 4;
  if (!counter || counter < policy.minimumCounter || !low || low > high || policy.protocol < low || policy.protocol > high ||
      candidate.size < 288 || candidate.size > 0x300000) return false;
  hex(p,candidate.sha256); p+=32; hex(p,candidate.imageSha256); p+=32;
  hex(p,candidate.manifestSha256); p+=32;
  for (size_t i=0;i<20;i++) sprintf(candidate.commit+2*i,"%02x",p[i]);
  p+=20; candidate.counter=counter;
  char board[65], revision[33], layout[33];
  if (!identifier(p,end,candidate.version,31) || !identifier(p,end,board,64) || !identifier(p,end,revision,32) ||
      !identifier(p,end,layout,32) || p != end || strcmp(board,"lilygo-s3-long-cst3530") ||
      strcmp(revision,policy.boardRevision) || strcmp(layout,"ota3m-v1")) return false;
  candidate.protocolMin=low;candidate.protocolMax=high;strcpy(candidate.boardRevision,revision);
  const mbedtls_md_info_t *sha = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  uint8_t fingerprint[32];
  if (!sha || mbedtls_md(sha,key->der,key->length,fingerprint) || memcmp(fingerprint,key->id,16) ||
      mbedtls_md(sha,record,length,candidate.identity)) return false;
  mbedtls_pk_context publicKey; mbedtls_pk_init(&publicKey);
  bool valid = mbedtls_pk_parse_public_key(&publicKey,key->der,key->length) == 0 &&
      mbedtls_pk_get_type(&publicKey) == MBEDTLS_PK_ECKEY &&
      mbedtls_pk_ec(publicKey)->grp.id == MBEDTLS_ECP_DP_SECP256R1 &&
      mbedtls_pk_verify(&publicKey,MBEDTLS_MD_SHA256,candidate.identity,32,signature,signatureLength) == 0;
  mbedtls_pk_free(&publicKey);
  if (valid) output = candidate;
  return valid;
}
