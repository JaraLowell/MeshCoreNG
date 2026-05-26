#include "RegionProfiles.h"

#ifndef REGION_PROFILE_NL
#define REGION_PROFILE_NL 0
#endif

#ifndef REGION_PROFILE_DE
#define REGION_PROFILE_DE 0
#endif

#ifndef REGION_PROFILE_NL_DE_BORDER
#define REGION_PROFILE_NL_DE_BORDER 0
#endif

struct RegionProfileEntry {
  const char* name;
  const char* parent;
  bool is_default;
};

static bool putAllowed(RegionMap& regions, const RegionProfileEntry& entry) {
  RegionEntry* parent = NULL;
  if (entry.parent && entry.parent[0]) {
    parent = regions.findByName(entry.parent);
    if (!parent) return false;
  } else {
    parent = &regions.getWildcard();
  }

  RegionEntry* region = regions.putRegion(entry.name, parent->id);
  if (!region) return false;

  region->flags &= ~REGION_DENY_FLOOD;
  if (entry.is_default) {
    regions.setDefaultRegion(region);
  }
  return true;
}

static bool applyProfile(RegionMap& regions, const RegionProfileEntry* entries, size_t count) {
  for (size_t i = 0; i < count; i++) {
    if (!putAllowed(regions, entries[i])) return false;
  }
  return true;
}

const char* getRegionProfileName() {
#if REGION_PROFILE_NL_DE_BORDER
  return "nl-de-border";
#elif REGION_PROFILE_DE
  return "de";
#elif REGION_PROFILE_NL
  return "nl";
#else
  return "none";
#endif
}

bool applyDefaultRegionProfile(RegionMap& regions) {
#if REGION_PROFILE_NL_DE_BORDER
  static const RegionProfileEntry entries[] = {
    {"europe", NULL, true},
    {"eu", NULL, false},
    {"nl", "europe", false},
    {"de", "europe", false},
    {"de-west", "de", false},
    {"de-nord", "de", false},
    {"de-ni", "de-nord", false},
    {"de-nw", "de-west", false},
    {"ffnw", "de-nord", false},
    {"emsland", "de-ni", false},
    {"bentheim", "de-ni", false},
    {"osnabrueck", "de-ni", false},
    {"ruhrgebiet", "de-nw", false},
    {"rheinland", "de-nw", false},
    {"nl-gr", "nl", false},
    {"nl-dr", "nl", false},
    {"nl-ov", "nl", false},
    {"nl-ge", "nl", false},
    {"nl-nb", "nl", false},
    {"nl-li", "nl", false},
  };
  return applyProfile(regions, entries, sizeof(entries) / sizeof(entries[0]));
#elif REGION_PROFILE_DE
  static const RegionProfileEntry entries[] = {
    {"europe", NULL, false},
    {"eu", NULL, false},
    {"de", "europe", true},
    {"de-nord", "de", false},
    {"de-ost", "de", false},
    {"de-sued", "de", false},
    {"de-west", "de", false},
    {"de-mitte", "de", false},
    {"de-bw", "de-sued", false},
    {"de-by", "de-sued", false},
    {"de-be", "de-ost", false},
    {"de-bb", "de-ost", false},
    {"de-hb", "de-nord", false},
    {"de-hh", "de-nord", false},
    {"de-he", "de-mitte", false},
    {"de-mv", "de-nord", false},
    {"de-ni", "de-nord", false},
    {"de-nw", "de-west", false},
    {"de-rp", "de-west", false},
    {"de-sl", "de-west", false},
    {"de-sn", "de-ost", false},
    {"de-st", "de-ost", false},
    {"de-sh", "de-nord", false},
    {"de-th", "de-mitte", false},
    {"ffnw", "de-nord", false},
    {"emsland", "de-ni", false},
    {"bentheim", "de-ni", false},
    {"osnabrueck", "de-ni", false},
    {"ruhrgebiet", "de-nw", false},
    {"rheinland", "de-nw", false},
    {"rhein-main", "de-he", false},
  };
  return applyProfile(regions, entries, sizeof(entries) / sizeof(entries[0]));
#elif REGION_PROFILE_NL
  static const RegionProfileEntry entries[] = {
    {"eu", NULL, false},
    {"europe", NULL, false},
    {"nl", "eu", true},
    {"nl-gr", "nl", false},
    {"nl-fr", "nl", false},
    {"nl-dr", "nl", false},
    {"nl-ov", "nl", false},
    {"nl-ge", "nl", false},
    {"nl-fl", "nl", false},
    {"nl-ut", "nl", false},
    {"nl-nh", "nl", false},
    {"nl-zh", "nl", false},
    {"nl-ze", "nl", false},
    {"nl-nb", "nl", false},
    {"nl-li", "nl", false},
  };
  return applyProfile(regions, entries, sizeof(entries) / sizeof(entries[0]));
#else
  return false;
#endif
}
