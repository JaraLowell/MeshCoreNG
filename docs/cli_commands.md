# CLI Commands

This document provides an overview of CLI commands that can be sent to MeshCore Repeaters, Room Servers and Sensors.

## Navigation

- [Operational](#operational)
- [Neighbors](#neighbors-repeater-only)
- [Statistics](#statistics)
- [Logging](#logging)
- [Information](#info)
- [Configuration](#configuration)
  - [Radio](#radio)
  - [System](#system)
  - [Routing](#routing)
  - [ACL](#acl)
  - [Region Management](#region-management-v110)
  - [Dutch Region Database](#dutch-region-database)
  - [Region Examples](#region-examples)
  - [GPS](#gps-when-gps-support-is-compiled-in)
  - [Sensors](#sensors-when-sensor-support-is-compiled-in)
  - [Bridge](#bridge-when-bridge-support-is-compiled-in)

---

## Operational

### Reboot the node
**Usage:** 
- `reboot`

---

### Reset the clock and reboot
**Usage:**
- `clkreboot`

---

### Sync the clock with the remote device
**Usage:** 
- `clock sync`

---

### Display current time in UTC
**Usage:**
- `clock`

---

### Set the time to a specific timestamp
**Usage:** 
- `time <epoch_seconds>`

**Parameters:**
- `epoch_seconds`: Unix epoch time

---

### Send a flood advert
**Usage:** 
- `advert`

---

### Send a zero-hop advert
**Usage:**
- `advert.zerohop`

---

### Start an Over-The-Air (OTA) firmware update
**Usage:**
- `start ota`

---

### Erase/Factory Reset
**Usage:**
- `erase`

**Serial Only:** Yes

**Warning:** _**This is destructive!**_

---

## Neighbors (Repeater Only)

### List nearby neighbors
**Usage:** 
- `neighbors`

**Note:** The output of this command is limited to the 8 most recent adverts.

**Note:** Each line is encoded as `{pubkey-prefix}:{timestamp}:{snr*4}`

---

### Remove a neighbor
**Usage:** 
- `neighbor.remove <pubkey_prefix>`

**Parameters:** 
- `pubkey_prefix`: The public key of the node to remove from the neighbors list. This can be a short prefix or the full key. All neighbors matching the provided prefix will be removed.

**Note:** You can remove all neighbors by sending a space character as the prefix. The space indicates an empty prefix, which matches all existing neighbors.

---

### Discover zero hop neighbors

**Usage:** 
- `discover.neighbors`

---

## Statistics

### Clear Stats
**Usage:** `clear stats`

---

### Dense Mesh Stats
**Usage:**
- `get dense.stats`
- `clear dense.stats`

Shows repeater dense-mesh counters in one place: flood adverts received, forwarded and dropped, CAD busy/timeout events, and flood/direct duplicate counters.

MeshCoreNG v2 also includes a rolling window for neighbor count, unique/duplicate flood RX, suppressed flood TX, RX/TX airtime, congestion level, and density level. These counters are RAM-only and do not change the packet protocol.

**Serial Only:** `get dense.stats`

---

### Power Saving Stats
**Usage:**
- `get power.stats`
- `clear power.stats`

Shows repeater power-saving counters: sleep attempts, sleep skipped because outbound work was pending, sleep skipped because a bridge/WiFi mode was active, wakeups caused by LoRa RX when the board reports that reason, and a compact board support indicator.

These counters are RAM-only and reset on reboot or with `clear power.stats`.

**Serial Only:** `get power.stats`

---

### System Stats - Battery, Uptime, Queue Length and Debug Flags
**Usage:** 
- `stats-core`

**Serial Only:** Yes

---

### Radio Stats - Noise floor, Last RSSI/SNR, Airtime, Receive errors
**Usage:** `stats-radio`

**Serial Only:** Yes

---

### Packet stats - Packet counters: Received, Sent
**Usage:** `stats-packets`

**Serial Only:** Yes

---

## Logging

### Begin capture of rx log to node storage
**Usage:** `log start`

---

### End capture of rx log to node storage
**Usage:** `log stop`

---

### Erase captured log
**Usage:** `log erase`

---

### Print the captured log to the serial terminal
**Usage:** `log`

**Serial Only:** Yes

---

## Info

### Get the Version
**Usage:** `ver`

---

### Show the hardware name
**Usage:** `board`

---

## Configuration

### Radio

#### View or change this node's radio parameters
**Usage:**
- `get radio`
- `set radio <freq>,<bw>,<sf>,<cr>`

**Parameters:**
- `freq`: Frequency in MHz
- `bw`: Bandwidth in kHz
- `sf`: Spreading factor (5-12)
- `cr`: Coding rate (5-8)

**Set by build flag:** `LORA_FREQ`, `LORA_BW`, `LORA_SF`, `LORA_CR`

**Default:** `869.525,250,11,5`

**Note:** Requires reboot to apply

---

#### View or change this node's transmit power
**Usage:**
- `get tx`
- `set tx <dbm>`

**Parameters:**
- `dbm`: Power level in dBm (1-22)

**Set by build flag:** `LORA_TX_POWER`

**Default:** Varies by board

**Notes:** This setting only controls the power level of the LoRa chip. Some nodes have an additional power amplifier stage which increases the total output. Refer to the node's manual for the correct setting to use. **Setting a value too high may violate the laws in your country.**

---

#### View or change the boosted receive gain mode
**Usage:**
- `get radio.rxgain`
- `set radio.rxgain <state>`

**Parameters:**
- `state`: `on`|`off`

**Default:** `off`

**Note:** Only available on SX1262 and SX1268 based boards.

---

#### Change the radio parameters for a set duration
**Usage:** 
- `tempradio <freq>,<bw>,<sf>,<cr>,<timeout_mins>`

**Parameters:**
- `freq`: Frequency in MHz (300-2500)
- `bw`: Bandwidth in kHz (7.8-500)
- `sf`: Spreading factor (5-12)
- `cr`: Coding rate (5-8)
- `timeout_mins`: Duration in minutes (must be > 0)

**Note:** This is not saved to preferences and will clear on reboot

---

#### View or change this node's frequency
**Usage:**
- `get freq`
- `set freq <frequency>`

**Parameters:**
- `frequency`: Frequency in MHz

**Default:** `869.525`

**Note:** Requires reboot to apply
**Serial Only:** `set freq <frequency>`

---

#### View or change this node's rx boosted gain mode (SX12xx only, v1.14.1+)
**Usage:**
- `get radio.rxgain`
- `set radio.rxgain <state>`

**Parameters:**
  - `state`: `on`|`off`

**Default:** `on`

**Temporary Note:** If you upgraded from an older version to 1.14.1 without erasing flash, this setting is `off` because of [#2118](https://github.com/meshcore-dev/MeshCore/issues/2118)

---

### System

#### View or change this node's name
**Usage:**
- `get name`
- `set name <name>`

**Parameters:**
- `name`: Node name

**Set by build flag:** `ADVERT_NAME`

**Default:** Varies by board

**Note:** Max length varies. If a location is set, the max length is 24 bytes; 32 otherwise. Emoji and unicode characters may take more than one byte.

---

#### View or change this node's latitude
**Usage:**
- `get lat`
- `set lat <degrees>`

**Set by build flag:** `ADVERT_LAT`

**Default:** `0`

**Parameters:**
- `degrees`: Latitude in degrees

---

#### View or change this node's longitude
**Usage:**
- `get lon`
- `set lon <degrees>`

**Set by build flag:** `ADVERT_LON`

**Default:** `0`

**Parameters:**
- `degrees`: Longitude in degrees

---

#### View or change this node's identity (Private Key)
**Usage:**
- `get prv.key`
- `set prv.key <private_key>`

**Parameters:**
- `private_key`: Private key in hex format (64 hex characters)

**Serial Only:**
- `get prv.key`: Yes
- `set prv.key`: No

**Note:** Requires reboot to take effect after setting

---

#### Change this node's admin password
**Usage:**
- `password <new_password>`

**Parameters:**
- `new_password`: New admin password

**Set by build flag:** `ADMIN_PASSWORD`

**Default:** `password`

**Note:** Command reply echoes the updated password for confirmation.

**Note:** Any node using this password will be added to the admin ACL list.

---

#### View or change this node's guest password
**Usage:**
- `get guest.password`
- `set guest.password <password>`

**Parameters:**
- `password`: Guest password

**Set by build flag:** `ROOM_PASSWORD` (Room Server only)

**Default:** `<blank>`

---

#### View or change this node's owner info
**Usage:**
- `get owner.info`
- `set owner.info <text>`

**Parameters:**
- `text`: Owner information text

**Default:** `<blank>`

**Note:** `|` characters are translated to newlines

**Note:** Requires firmware 1.12.+

---

#### Fine-tune the battery reading
**Usage:**
- `get adc.multiplier`
- `set adc.multiplier <value>`

**Parameters:**
- `value`: ADC multiplier (0.0-10.0)

**Default:** `0.0` (value defined by board)

**Note:** Returns "Error: unsupported by this board" if hardware doesn't support it

---

#### View this node's public key
**Usage:** `get public.key`

---

#### View this node's firmware version
**Usage:** `ver`

---

#### View this node's configured role
**Usage:** `get role`

---

#### View or change this node's power saving flag (Repeater Only)
**Usage:**
- `powersaving`
- `powersaving on`
- `powersaving off`

**Parameters:** 
- `on`: enable power saving
- `off`: disable power saving

**Default:** `off`

**Note:** Power saving is repeater-only. When enabled, sleep is attempted only when there is no pending outbound work. Bridge/WiFi modes prevent sleep because the bridge must stay awake.

On ESP32 boards with supported LoRa DIO1 wake wiring, sleep can wake by LoRa RX or by timer. On nRF52 boards sleep is event/interrupt driven and the seconds parameter is ignored by the board sleep implementation.

---

### Routing

#### View or change this node's repeat flag
**Usage:**
- `get repeat`
- `set repeat <state>`

**Parameters:**
  - `state`: `on`|`off`

**Default:** `on`

---

#### View or change this node's advert path hash size
**Usage:**
- `get path.hash.mode`
- `set path.hash.mode <value>`

**Parameters:**
- `value`: Path hash size (0-2)
  - `0`: 1 Byte hash size (256 unique ids)[64 max flood]
  - `1`: 2 Byte hash size (65,536 unique ids)[32 max flood]
  - `2`: 3 Byte hash size (16,777,216 unique ids)[21 max flood]
  - `3`: DO NOT USE (Reserved) 

**Default:** `0`

**Note:** the 'path.hash.mode' sets the low-level ID/hash encoding size used when the repeater adverts. This setting has no impact on what packet ID/hash size this repeater forwards, all sizes should be forwarded on firmware >= 1.14. This feature was added in firmware 1.14

**Temporary Note:** adverts with ID/hash sizes of 2 or 3 bytes may have limited flood propogation in your network while this feature is new as v1.13.0 firmware and older will drop packets with multibyte path ID/hashes as only 1-byte hashes are suppored. Consider your install base of firmware >=1.14 has reached a criticality for effective network flooding before implementing higher ID/hash sizes. 

---

#### View or change this node's loop detection
**Usage:**
- `get loop.detect`
- `set loop.detect <state>`

**Parameters:**
- `state`: 
  - `off`: no loop detection is performed
  - `minimal`: packets are dropped if repeater's ID/hash appears 4 or more times (1-byte), 2 or more (2-byte), 1 or more (3-byte)
  - `moderate`: packets are dropped if repeater's ID/hash appears 2 or more times (1-byte), 1 or more (2-byte), 1 or more (3-byte)
  - `strict`: packets are dropped if repeater's ID/hash appears 1 or more times (1-byte), 1 or more (2-byte), 1 or more (3-byte)
  
**Default:** `off`

**Note:** When it is enabled, repeaters will now reject flood packets which look like they are in a loop. This has been happening recently in some meshes when there is just a single 'bad' repeater firmware out there (prob some forked or custom firmware). If the payload is messed with, then forwarded, the same packet ends up causing a packet storm, repeated up to the max 64 hops. This feature was added in firmware 1.14

**Example:** If preference is `loop.detect minimal`, and a 1-byte path size packet is received, the repeater will see if its own ID/hash is already in the path. If it's already encoded 4 times, it will reject the packet.  If the packet uses 2-byte path size, and repeater's own ID/hash is already encoded 2 times, it rejects. If the packet uses 3-byte path size, and the repeater's own ID/hash is already encoded 1 time, it rejects. 

---

#### View or change the retransmit delay factor for flood traffic
**Usage:**
- `get txdelay`
- `set txdelay <value>`

**Parameters:**
- `value`: Transmit delay factor (0-2)

**Default:** `0.5`

**Dense mesh behavior:** This delay is applied before a flood packet is queued for transmit. When `txdelay` is above `0`, MeshCoreNG also adds a small stable per-node offset derived from the node identity. This keeps nearby repeaters from becoming synchronized while preserving the existing random `txdelay` spread.

`set txdelay 0` keeps the previous zero-delay behavior and does not add the node offset. CAD retry is separate: it happens after the radio detects a busy channel, with the current retry window of 120-360 ms.

---

#### View or change the retransmit delay factor for direct traffic
**Usage:**
- `get direct.txdelay`
- `set direct.txdelay <value>`

**Parameters:**
- `value`: Direct transmit delay factor (0-2)

**Default:** `0.2`

---

#### [Experimental] View or change the processing delay for received traffic
**Usage:**
- `get rxdelay`
- `set rxdelay <value>`

**Parameters:**
- `value`: Receive delay base (0-20)

**Default:** `0.0`

---

#### View or change the duty cycle limit
**Usage:**
- `get dutycycle`
- `set dutycycle <value>`

**Parameters:**
- `value`: Duty cycle percentage (1-100)

**Default:** `50%` (equivalent to airtime factor 1.0)

**Examples:**
- `set dutycycle 100` — no duty cycle limit
- `set dutycycle 50` — 50% duty cycle (default)
- `set dutycycle 10` — 10% duty cycle
- `set dutycycle 1` — 1% duty cycle (strictest EU requirement)

> **Note:** Added in firmware v1.15.0

---

#### View or change the airtime factor (duty cycle limit)
> **Deprecated** as of firmware v1.15.0. Use [`get/set dutycycle`](#view-or-change-the-duty-cycle-limit) instead.

**Usage:**
- `get af`
- `set af <value>`

**Parameters:**
- `value`: Airtime factor (0-9). After each transmission, the repeater enforces a silent period of approximately the on-air transmission time multiplied by the value. This results in a long-term duty cycle of roughly 1 divided by (1 plus the value). For example:
  - `af = 1` → ~50% duty
  - `af = 2` → ~33% duty
  - `af = 3` → ~25% duty
  - `af = 9` → ~10% duty
  You are responsible for choosing a value that is appropriate for your jurisdiction and channel plan (for example EU 868 Mhz 10% duty cycle regulation).

**Default:** `1.0`

---

#### View or change the local interference threshold
**Usage:**
- `get int.thresh`
- `set int.thresh <value>`

**Parameters:**
- `value`: Interference threshold value

**Default:** `1` (Repeater) - `0` (other roles)

---

#### View or change the AGC Reset Interval
**Usage:**
- `get agc.reset.interval`
- `set agc.reset.interval <value>`

**Parameters:**
- `value`: Interval in seconds rounded down to a multiple of 4 (17 becomes 16). 0 to disable.

**Default:** `0.0`

---

#### Enable or disable Multi-Acks support
**Usage:**
- `get multi.acks`
- `set multi.acks <state>`

**Parameters:**
- `state`: `0` (disable) or `1` (enable)

**Default:** `0`

---

#### View or change the flood advert interval
**Usage:**
- `get flood.advert.interval`
- `set flood.advert.interval <hours>`

**Parameters:**
- `hours`: Interval in hours (3-168)

**Default:** `0`

---

#### View or change flood advert forwarding probability
**Usage:**
- `get flood.advert.base`
- `set flood.advert.base <value>`

**Parameters:**
- `value`: Probability base from `0` to `1`. Repeater forwarding probability is `value^(hops - 1)`.

Simple start advice:
- `0`: do not forward received flood adverts.
- `0.308`: dense mesh default; quickly reduces advert noise as hop count grows.
- `1`: forward every flood advert, matching unrestricted forwarding.

**Default:** `0.308` (Repeater)

---

#### View or change flood relay probability
**Usage:**
- `get flood.relay.prob`
- `set flood.relay.prob <value>`

**Parameters:**
- `value`: Integer probability from `0` to `255`, applied to eligible flood forwarding after normal deny, loop, max-hop, and advert-base checks.

Simple start advice:
- `0`: suppress eligible flood forwarding.
- `128`: forward about half of eligible flood packets.
- `255`: normal eligible flood forwarding.

**Default:** `255`

---

#### View or change dense dynamic mode
**Usage:**
- `get flood.dynamic.enable`
- `set flood.dynamic.enable on`
- `set flood.dynamic.enable off`

**Note:** In v2 this is telemetry/recommendation mode only. It does not automatically change advert interval, hop limits, or rebroadcast delay.

**Default:** `off`

---

#### View or change the zero-hop advert interval
**Usage:**
- `get advert.interval`
- `set advert.interval <minutes>`

**Parameters:**
- `minutes`: Interval in minutes rounded down to the nearest multiple of 2 (61 becomes 60) (60-240)

**Default:** `0`

---

#### Limit the number of hops for a flood message
**Usage:**
- `get flood.max`
- `set flood.max <value>`

**Parameters:**
- `value`: Maximum flood hop count (0-64)

**Default:** `64`

---

### ACL

#### Add, update or remove permissions for a companion
**Usage:** 
- `setperm <pubkey> <permissions>`

**Parameters:**
- `pubkey`: Companion public key
- `permissions`: 
  - `0`: Guest
  - `1`: Read-only
  - `2`: Read-write
  - `3`: Admin

**Note:** Removes the entry when `permissions` is omitted

---

#### View the current ACL
**Usage:** 
- `get acl`

**Serial Only:** Yes

---

#### View or change this room server's 'read-only' flag
**Usage:**
- `get allow.read.only`
- `set allow.read.only <state>`

**Parameters:**
- `state`: `on` (enable) or `off` (disable)

**Default:** `off`

---

### Region Management (v1.10.+)

Regions form a local forwarding hierarchy. They let repeaters decide which flood scopes they should carry, so dense meshes can keep local traffic local and reserve wide-area forwarding for repeaters that are meant to act as backbone nodes.

Example hierarchy:

```text
eu
└── nl
    ├── nl-nh
    │   ├── nl-nh-sbc
    │   └── nl-nh-bov
    └── nl-hhw
```

`region allowf <name>` allows flood forwarding for that region on this repeater. `region denyf <name>` blocks flood forwarding for that region on this repeater. Use `region home <name>` to mark the node's own most specific region.

Parent-child regions express scope inheritance: `nl-nh-bov` belongs inside `nl-nh`, which belongs inside `nl`. Forwarding flags are still explicit per region, so allow the parent, child, or both based on the repeater's intended role.

#### Bulk-load region lists
**Usage:** 
- `region load`
- `region load <name> [flood_flag]`

**Parameters:**
- `name`: A name of a region. `*` represents the wildcard region

**Note:** `flood_flag`: Optional `F` to allow flooding

**Note:** Indentation creates parent-child relationships (max 8 levels)

**Note:** `region load` with an empty name will not work remotely (it's interactive)

---

#### Save any changes to regions made since reboot
**Usage:** 
- `region save`

**Purpose:** Persist the current region map, forwarding flags, home region and default region to local storage.

**Behavior:** Region changes are RAM-only until saved. Run this after a working configuration is confirmed.

---

#### Allow a region
**Usage:** 
- `region allowf <name>`

**Parameters:** 
- `name`: Region name (or `*` for wildcard)

**Purpose:** Allow this node to forward flood packets for the selected region.

**Example:**
- `region allowf nl-nh-bov`

**Note:** Setting on wildcard `*` allows packets without region transport codes

---

#### Block a region
**Usage:** 
- `region denyf <name>`

**Parameters:** 
- `name`: Region name (or `*` for wildcard)

**Purpose:** Stop this node from forwarding flood packets for the selected region.

**Example:**
- `region denyf eu`

**Note:** Setting on wildcard `*` drops packets without region transport codes

---

#### Show information for a region
**Usage:** 
- `region get <name>`

**Parameters:**
- `name`: Region name (or `*` for wildcard)

---

#### View or change the home region for this node
**Usage:** 
- `region home`
- `region home <name>`

**Parameters:**
- `name`: Region name

**Purpose:** Mark this node's own region. Use the most specific correct region for the repeater's physical location.

**Example:**
- `region home nl-nh-bov`

---

#### View or change the default scope region for this node
**Usage:** 
- `region default`
- `region default {name|<null>}`

**Parameters:**
- `name`: Region name,  or <null> to reset/clear

---

#### Create a new region
**Usage:** 
- `region put <name> [parent_name]`

**Parameters:**
- `name`: Region name
- `parent_name`: Parent region name (optional, defaults to wildcard)

**Purpose:** Add a region to the hierarchy. Parent-child relationships make the tree readable for operators and tools.

**Examples:**
- `region put eu`
- `region put nl eu`
- `region put nl-nh nl`
- `region put nl-nh-bov nl-nh`

---

#### Remove a region
**Usage:** 
- `region remove <name>`

**Parameters:**
- `name`: Region name

**Note:** Must remove all child regions before the region can be removed 

---

#### View all regions
**Usage:** 
- `region list <filter>`

**Serial Only:** Yes

**Parameters:**
- `filter`: `allowed`|`denied`

**Note:** Requires firmware 1.12.+

---

#### Dump all defined regions and flood permissions
**Usage:** 
- `region`
- `region tree`

**Purpose:** Show the configured region hierarchy. `F` means flood forwarding is allowed for that region. `^` marks the home region.

**Serial Only:** For firmware older than 1.12.0

---

#### Example Dutch hierarchy
**Usage:**
```
region put eu
region put nl eu
region put nl-nh nl
region put nl-hhw nl
region put nl-nh-sbc nl-nh
region put nl-nh-bov nl-nh

region allowf eu
region allowf nl
region allowf nl-nh
region allowf nl-hhw
region allowf nl-nh-sbc
region allowf nl-nh-bov

region home nl-nh-bov
region tree
region save
```

**Operational note:** Local repeaters can deny broad regions such as `eu` or `nl` to save airtime. Backbone repeaters can intentionally allow broader regions to connect local meshes.

---

### Dutch Region Database

The Dutch region database is a read-only flash lookup table generated from MeshWiki. It does not consume heap memory and does not change the editable region map until a client chooses to apply a returned code. It is enabled by the `WITH_DUTCH_REGION_DB` build flag. See [Dutch Region Database](./dutch_region_db.md) for the generated format and maintainer workflow.

#### Database metadata
**Usage:**
- `regiondb`
- `regiondb info`

**Example response:**
```
nl-db entries=2484 provinces=12 codes=1611 rev=100 modified=2026-03-23T14:07:28Z
```

#### List province counts
**Usage:**
- `regiondb provinces`

**Example response:**
```
gr:197,fr:413,dr:225,ov:178,fl:19,ge:330,ut:104,nh:238,zh:184,ze:126,nb:279,li:191
```

#### Find a Dutch location by name prefix
**Usage:**
- `regiondb find <prefix> [start_index]`

**Example:**
- `regiondb find gron`

**Example response:**
```
45 Groningen [gr] nl-grq +1
```

Use `start_index` to continue searching after a previous match.

#### Read a Dutch location by index
**Usage:**
- `regiondb get <index>`

**Example response:**
```
45 Groningen [gr] nl-grq,nl-gr-grq
```

#### Resolve an internal code ID
**Usage:**
- `regiondb code <code_id>`

**Example response:**
```
1 nl-grq
```

**Note:** `regiondb` is lookup-only. Use the normal `region` commands to change the runtime region map.

---

### Region Examples

**Example 1: Using F Flag with Named Public Region**
```
region load
#Europe F
<blank line to end region load>
region save
```

**Explanation:**
- Creates a region named `#Europe` with flooding enabled
- Packets from this region will be flooded to other nodes

---

**Example 2: Using Wildcard with F Flag**
```
region load 
* F
<blank line to end region load>
region save
```

**Explanation:**
- Creates a wildcard region `*` with flooding enabled
- Enables flooding for all regions automatically
- Applies only to packets without transport codes

---

**Example 3: Using Wildcard Without F Flag**
```
region load 
*
<blank line to end region load>
region save
```
**Explanation:**
- Creates a wildcard region `*` without flooding
- This region exists but doesn't affect packet distribution
- Used as a default/empty region

---

**Example 4: Nested Public Region with F Flag**
```
region load 
#Europe F
  #UK
    #London
    #Manchester
  #France
    #Paris
    #Lyon
<blank line to end region load>
region save
```

**Explanation:**
- Creates `#Europe` region with flooding enabled
- Adds nested child regions (`#UK`, `#France`)
- The nesting records the intended hierarchy; set `F` or use `region allowf` on child regions that should also forward flood traffic

---

**Example 5: Wildcard with Nested Public Regions**
```
region load 
* F
  #NorthAmerica
    #USA
      #NewYork
      #California
    #Canada
      #Ontario
      #Quebec
<blank line to end region load>
region save
```

**Explanation:**
- Creates wildcard region `*` with flooding enabled
- Adds nested `#NorthAmerica` hierarchy
- Enables flooding for all child regions automatically
- Useful for global networks with specific regional rules

---
### GPS (When GPS support is compiled in)

#### View or change GPS state
**Usage:**
- `gps`
- `gps <state>`

**Parameters:**
- `state`: `on`|`off`

**Default:** `off`

**Note:** Output format:
- `off` when the GPS hardware is disabled
- `on, {active|deactivated}, {fix|no fix}, {sat count} sats` when the GPS hardware is enabled

---

#### Sync this node's clock with GPS time
**Usage:** 
- `gps sync`

---

#### Set this node's location based on the GPS coordinates
**Usage:** 
- `gps setloc`

---

#### View or change the GPS advert policy
**Usage:**
- `gps advert`
- `gps advert <policy>`

**Parameters:** 
- `policy`: `none`|`share`|`prefs` 
  - `none`: don't include location in adverts
  - `share`: share gps location (from SensorManager)
  - `prefs`: location stored in node's lat and lon settings

**Default:** `prefs`

---

### Sensors (When sensor support is compiled in)

#### View the list of sensors on this node
**Usage:** `sensor list [start]`

**Parameters:**
- `start`: Optional starting index (defaults to 0)

**Note:** Output format: `<var_name>=<value>\n`

---

#### View or change thevalue of a sensor
**Usage:** 
- `sensor get <key>`
- `sensor set <key> <value>`

**Parameters:**
- `key`: Sensor setting name
- `value`: The value to set the sensor to

---

### Bridge (When bridge support is compiled in)

Three bridge types are available, each compiled in separately:

| Bridge | Build flag | Platform | Use case |
|---|---|---|---|
| **RS232** | `-D WITH_RS232_BRIDGE=Serial2` | All | Wired serieel naar ander apparaat |
| **ESPNow** | `-D WITH_ESPNOW_BRIDGE=1` | ESP32 | Lokaal WiFi tussen ESP32 boards |
| **TCP** | `-D WITH_TCP_BRIDGE=1` | ESP32 | Meerdere repeaters via internet |

#### TCP bridge instellen (internet-verbinding tussen repeaters)

De TCP bridge verbindt repeaters via internet. Vereist een centrale server (zie `tools/tcp_bridge_server.py`).

**1. Server starten (VPS, Raspberry Pi of PC met internet):**
```bash
python3 tools/tcp_bridge_server.py --port 4200
```

**2. Elke repeater instellen via CLI:**
```
set wifi.ssid     MijnWiFi
set wifi.password geheim123
set bridge.server mijnserver.example.com
set bridge.port   4200
set bridge.enabled on
```

**3. Beschikbare firmware-varianten** (compileer met PlatformIO):
- `Heltec_v3_repeater_bridge_tcp`
- `Heltec_WSL3_repeater_bridge_tcp`
- `heltec_v4_repeater_bridge_tcp`
- `Tbeam_SX1262_repeater_bridge_tcp`
- `Tbeam_SX1276_repeater_bridge_tcp`
- `T_Beam_S3_Supreme_SX1262_repeater_bridge_tcp`
- `LilyGo_TBeam_1W_repeater_bridge_tcp`
- `LilyGo_T3S3_sx1262_repeater_bridge_tcp`
- *(en vele andere, zie de `variants/*/platformio.ini` bestanden)*

---

#### View the compiled bridge type
**Usage:** `get bridge.type`

---

#### View or change the bridge enabled flag
**Usage:**
- `get bridge.enabled`
- `set bridge.enabled <state>`

**Parameters:**
- `state`: `on`|`off`

**Default:** `off`

---

#### Add a delay to packets routed through this bridge
**Usage:**
- `get bridge.delay`
- `set bridge.delay <ms>`

**Parameters:**
- `ms`: Delay in milliseconds (0-10000)

**Default:** `500`

---

#### View or change the source of packets bridged to the external interface
**Usage:**
- `get bridge.source`
- `set bridge.source <source>`

**Parameters:**
- `source`: 
  - `logRx`: bridges received packets
  - `logTx`: bridges transmitted packets

**Default:** `logTx`

---

#### View or change the speed of the bridge (RS-232 only)
**Usage:**
- `get bridge.baud`
- `set bridge.baud <rate>`

**Parameters:**
- `rate`: Baud rate (`9600`, `19200`, `38400`, `57600`, or `115200`)

**Default:** `115200`

---

#### View or change the channel used for bridging (ESPNow only)
**Usage:**
- `get bridge.channel`
- `set bridge.channel <channel>`

**Parameters:**
- `channel`: Channel number (1-14)

---

#### Set the ESP-Now secret
**Usage:** 
- `get bridge.secret`
- `set bridge.secret <secret>`

**Parameters:**
- `secret`: ESP-NOW bridge secret, up to 15 characters

**Default:** Varies by board

---

#### Set the WiFi SSID (TCP bridge only)
**Usage:**
- `get wifi.ssid`
- `set wifi.ssid <ssid>`

**Parameters:**
- `ssid`: Name of the WiFi network the repeater should join, up to 31 characters

**Note:** Requires `WITH_TCP_BRIDGE` firmware build flag. Reboot to apply.

---

#### Set the WiFi password (TCP bridge only)
**Usage:**
- `set wifi.password <password>`

**Parameters:**
- `password`: WiFi network password, up to 63 characters

**Note:** `get wifi.password` always returns `***` for security.

---

#### Set the TCP bridge server (TCP bridge only)
**Usage:**
- `get bridge.server`
- `set bridge.server <host>`

**Parameters:**
- `host`: Hostname or IP address of the central TCP bridge server

**Note:** Requires `WITH_TCP_BRIDGE` firmware build flag.

---

#### Set the TCP bridge port (TCP bridge only)
**Usage:**
- `get bridge.port`
- `set bridge.port <port>`

**Parameters:**
- `port`: TCP port number (1–65535)

**Default:** 4200

---

#### View the bootloader version (nRF52 only)
**Usage:** `get bootloader.ver`

---

#### View power management support
**Usage:** `get pwrmgt.support`

---

#### View the current power source
**Usage:** `get pwrmgt.source`

**Note:** Returns an error on boards without power management support.

---

#### View the boot reset and shutdown reasons
**Usage:** `get pwrmgt.bootreason`

**Note:** Returns an error on boards without power management support.

---

#### View the boot voltage
**Usage:** `get pwrmgt.bootmv`

**Note:** Returns an error on boards without power management support.

---
