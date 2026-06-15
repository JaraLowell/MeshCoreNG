#pragma once

#include <stdint.h>

/**
 * @brief Simple rate limiter that tracks packet count over a time window
 * 
 * Used to limit the rate of incoming packets from various sources to prevent
 * flooding the mesh network. When the limit is exceeded, the allow() method
 * returns false to indicate that the packet should be dropped.
 */
class RateLimiter {
  uint32_t _start_timestamp;
  uint32_t _secs;
  uint16_t _maximum, _count;

public:
  /**
   * @brief Construct a new Rate Limiter
   * @param maximum Maximum number of packets allowed in the time window
   * @param secs Time window in seconds
   */
  RateLimiter(uint16_t maximum, uint32_t secs): _maximum(maximum), _secs(secs), _start_timestamp(0), _count(0) { }

  /**
   * @brief Check if a packet should be allowed based on rate limit
   * @param now Current timestamp in seconds
   * @return true if packet is allowed, false if rate limit exceeded
   */
  bool allow(uint32_t now) {
    if (now < _start_timestamp + _secs) {
      _count++;
      if (_count > _maximum) return false;   // deny
    } else {   // time window now expired
      _start_timestamp = now;
      _count = 1;
    }
    return true;
  }

  /**
   * @brief Update the rate limit parameters
   * @param maximum Maximum number of packets allowed in the time window
   * @param secs Time window in seconds
   */
  void setLimits(uint16_t maximum, uint32_t secs) {
    _maximum = maximum;
    _secs = secs;
    _count = 0;  // reset on configuration change
    _start_timestamp = 0;
  }

  /**
   * @brief Get current packet count in the current window
   * @return Current count
   */
  uint16_t getCount() const {
    return _count;
  }

  /**
   * @brief Reset the rate limiter
   */
  void reset() {
    _count = 0;
    _start_timestamp = 0;
  }
};
