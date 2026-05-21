# Dutch Region Database

The Dutch Region Database is a read-only lookup table for Dutch MeshCore region codes. It is generated from the MeshWiki page [Lijst van regio's](https://meshwiki.nl/wiki/Lijst_van_regio%27s), which currently contains 2484 locations across 12 provinces.

The database is intended for location lookup, CLI assistance, and companion-app integration. It is not the editable runtime region map used by `region put`, `region allowf`, or `region denyf`.

## Design Goals

- Store the database in firmware flash as `const`/`PROGMEM` data.
- Avoid `std::vector`, `String`, runtime JSON parsing, and heap-loaded arrays.
- Keep lookup code usable on low-memory ESP32 boards.
- Avoid heap fragmentation by returning pointers into static pools and caller-provided stack records.
- Keep the generated source deterministic so OTA firmware updates can replace the database as part of a normal firmware image.

## Generated Files

The generator is:

```sh
python3 tools/generate_dutch_region_db.py
```

Generated outputs are written to `src/helpers`:

- `DutchRegionDb.Generated.h`
- `DutchRegionDb.Generated.cpp`
- `DutchRegionDb.Generated.json`

The generated manifest records the source URL, wiki revision, last-modified timestamp, and table sizes.

## Flash Format

The generated data is split into compact static arrays:

- `kNamePool`: UTF-8 location names in one null-terminated byte pool.
- `kCodePool`: UTF-8 region-code strings in one null-terminated byte pool.
- `kProvinces`: 12 province IDs with short province abbreviations.
- `kCodes`: unique region-code IDs mapped to offsets in `kCodePool`.
- `kEntries`: one packed entry per location.
- `kExtraRegionCodes`: shared list of optional extra region-code IDs.

Each location entry uses fixed-width integer IDs and offsets:

```cpp
struct DutchRegionDbEntry {
  uint16_t name_offset;
  uint16_t province_id;
  uint16_t primary_region;
  uint16_t extra_offset;
  uint8_t extra_count;
} __attribute__((packed));
```

The generated database currently contains:

- `2484` entries
- `12` provinces
- `1611` unique region-code strings
- `4187` extra region-code references
- `24177` bytes of name strings
- `15984` bytes of region-code strings

## Runtime API

Use `DutchRegionDb` from `src/helpers/DutchRegionDb.h`.

Common operations:

- `DutchRegionDb::entryCount()`
- `DutchRegionDb::provinceCount()`
- `DutchRegionDb::regionCodeCount()`
- `DutchRegionDb::findByNamePrefix(prefix, start_index)`
- `DutchRegionDb::readEntry(index, entry)`
- `DutchRegionDb::readRecord(index, record)`
- `DutchRegionDb::codeText(code_id)`
- `DutchRegionDb::extraRegionCode(entry, extra_index)`

`readRecord()` returns pointers into the static string pools. Callers must not modify or free these pointers.

## CLI Commands

The lookup database is exposed through the `regiondb` CLI namespace:

```text
regiondb
regiondb info
regiondb provinces
regiondb find <prefix> [start_index]
regiondb get <index>
regiondb code <code_id>
```

Example:

```text
regiondb find gron
```

The response includes the entry index, location name, province abbreviation, primary region code, and the number of extra codes. Apps can call `regiondb get <index>` to retrieve the complete code list.

## Companion Apps

Companion apps can use the database through the existing text CLI transport. No new binary companion frame is required.

Recommended flow:

1. Send `regiondb info` and cache the `rev` and `modified` values.
2. Use `regiondb find <prefix>` for search-as-you-type.
3. If multiple matches are needed, repeat `regiondb find <prefix> <next_index>`.
4. Use `regiondb get <index>` after the user selects a location.
5. Resolve any internal code IDs with `regiondb code <code_id>` if needed by the UI.

Apps should treat returned codes as lookup results. They should only update the editable region map when the user explicitly chooses to apply a location.

## Updating The Database

To regenerate from the live MeshWiki page:

```sh
python3 tools/generate_dutch_region_db.py
```

To regenerate from a saved HTML file:

```sh
python3 tools/generate_dutch_region_db.py --html /path/to/Lijst_van_regios.html
```

Commit the generator and generated files together. The generated manifest should change whenever the source page revision, modified timestamp, counts, or generated sizes change.
