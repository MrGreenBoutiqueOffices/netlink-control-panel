#pragma once

enum class Transport { None, USB, Wifi };

constexpr bool canHandshake(Transport current, Transport incoming) {
  return incoming != Transport::None && !(incoming == Transport::Wifi && current == Transport::USB);
}
