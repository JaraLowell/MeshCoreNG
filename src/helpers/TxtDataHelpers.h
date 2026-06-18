#pragma once

#include <stddef.h>
#include <stdint.h>

#define TXT_TYPE_PLAIN          0      // a plain text message
#define TXT_TYPE_CLI_DATA       1      // a CLI command
#define TXT_TYPE_SIGNED_PLAIN   2      // plain text, signed by sender
#define DATA_TYPE_RESERVED      0x0000 // reserved for future use
#define DATA_TYPE_DEV           0xFFFF // developer namespace for experimenting with group/channel datagrams and building apps

#ifndef TXT_MALFORMED_PLACEHOLDER
#define TXT_MALFORMED_PLACEHOLDER "[Malformed packet filtered]"
#endif

#ifndef MIN_CHAT_MESSAGE_CONFIDENCE
#define MIN_CHAT_MESSAGE_CONFIDENCE 55
#endif

struct TextQualityMetrics {
  size_t payload_len;
  size_t text_len;
  uint16_t printable_ascii;
  uint16_t whitespace;
  uint16_t control_chars;
  uint16_t replacement_chars;
  uint16_t non_ascii;
  uint16_t trailing_nonzero;
  uint8_t entropy_score;
  bool valid_utf8;
  bool timestamp_sane;
};

class StrHelper {
public:
  static void strncpy(char* dest, const char* src, size_t buf_sz);
  static void strzcpy(char* dest, const char* src, size_t buf_sz);   // pads with trailing nulls
  static void stripSurroundingQuotes(char* str, size_t buf_sz);      // removes a single leading/trailing ' or "
  static const char* ftoa(float f);
  static const char* ftoa3(float f); //Converts float to string with 3 decimal places
  static bool isBlank(const char* str);
  static uint32_t fromHex(const char* src);
  static bool isValidUTF8(const uint8_t* data, size_t len);
  static bool isTimestampSane(uint32_t timestamp, uint32_t now);
  static uint8_t messageConfidenceScore(const uint8_t* data, size_t len, uint32_t timestamp, uint32_t now,
                                        TextQualityMetrics* metrics = NULL);
  static void sanitizeTextForDisplay(char* text);
};
