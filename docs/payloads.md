# Payload Format

Inside each [MeshCore Packet](./packet_format.md) is a payload, identified by the payload type in the packet header. The types of payloads are:

* Node advertisement.
* Acknowledgment.
* Returned path.
* Request (destination/source hashes + MAC).
* Response to REQ or ANON_REQ.
* Plain text message.
* Anonymous request.
* Group text message (unverified).
* Group datagram (unverified).
* Multi-part packet
* Control data packet
* Atlas telemetry packet.
* Location tracker report over group data.
* Custom packet (raw bytes, custom encryption).

This document defines the structure of each of these payload types.

NOTE: unless a section says otherwise, 16-bit and 32-bit integer fields are Little Endian.

## Important concepts:

* Node hash: the first byte of the node's public key

# Node advertisement
This kind of payload notifies receivers that a node exists, and gives information about the node

| Field         | Size (bytes)    | Description                                              |
|---------------|-----------------|----------------------------------------------------------|
| public key    | 32              | Ed25519 public key of the node                           |
| timestamp     | 4               | unix timestamp of advertisement                          |
| signature     | 64              | Ed25519 signature of public key, timestamp, and app data |
| appdata       | rest of payload | optional, see below                                      |

Appdata

| Field         | Size (bytes)    | Description                                           |
|---------------|-----------------|-------------------------------------------------------|
| flags         | 1               | specifies which of the fields are present, see below  |
| latitude      | 4 (optional)    | decimal latitude multiplied by 1000000, integer       |
| longitude     | 4 (optional)    | decimal longitude multiplied by 1000000, integer      |
| feature 1     | 2  (optional)   | reserved for future use                               |
| feature 2     | 2  (optional)   | reserved for future use                               |
| name          | rest of appdata | name of the node                                      |

Appdata Flags

| Value  | Name           | Description                           |
|--------|----------------|---------------------------------------|
| `0x01` | is chat node   | advert is for a chat node             |
| `0x02` | is repeater    | advert is for a repeater              |
| `0x03` | is room server | advert is for a room server           |
| `0x04` | is sensor      | advert is for a sensor server         |
| `0x10` | has location   | appdata contains lat/long information |
| `0x20` | has feature 1  | Reserved for future use.              |
| `0x40` | has feature 2  | Reserved for future use.              |
| `0x80` | has name       | appdata contains a node name          |

# Location tracker report

Current MeshCoreNG GPS tracker builds send compact tracker reports as public-channel `PAYLOAD_TYPE_GRP_DATA` (`0x06`) datagrams with `data_type=0x0200` (`DATA_TYPE_MESHCORENG_TRACKER`). This keeps tracker reports compatible with older repeaters that already forward group datagrams.

The group datagram body uses the normal MeshCore group-data wrapper:

| Field     | Size (bytes) | Description                           |
|-----------|--------------|---------------------------------------|
| data_type | 2            | little-endian `0x0200`                |
| data_len  | 1            | length of the tracker report body     |
| data      | variable     | compact tracker report shown below    |

The tracker report body uses big-endian integer fields:

| Field      | Size (bytes) | Description                            |
|------------|--------------|----------------------------------------|
| magic      | 4            | `MCL1`                                 |
| version    | 1            | currently `1`                          |
| flags      | 1            | reserved                               |
| node_id    | 4            | first 4 bytes of the sender identity   |
| lat        | 4            | signed microdegrees                    |
| lon        | 4            | signed microdegrees                    |
| altitude   | 2            | signed metres                          |
| speed      | 2            | centimetres per second                 |
| heading    | 2            | centidegrees                           |
| satellites | 1            | GPS satellite count                    |
| battery    | 2            | millivolts                             |
| timestamp  | 4            | Unix time from node RTC                |
| name_len   | 1            | 0-24                                   |
| name       | variable     | UTF-8 node name                        |

Tracker group datagrams are flood-routed like other public group data. The older native `PAYLOAD_TYPE_LOCATION` (`0x0D`) format used the same `MCL1` body directly as its app payload; it is kept as a legacy decode format for existing deployments, but new MeshCoreNG tracker builds should use the group-data format above.

# Acknowledgement

An acknowledgement that a message was received. Note that for returned path messages, an acknowledgement can be sent in the "extra" payload (see [Returned Path](#returned-path)) instead of as a separate acknowledgement packet. CLI commands do not cause acknowledgement responses, neither discrete nor extra.

| Field    | Size (bytes) | Description                                                |
|----------|--------------|------------------------------------------------------------|
| checksum | 4            | CRC checksum of message timestamp, text, and sender pubkey |


# Returned path, request, response, and plain text message

Returned path, request, response, and plain text messages are all formatted in the same way. See the subsection for more details about the ciphertext's associated plaintext representation.

| Field            | Size (bytes)    | Description                                          |
|------------------|-----------------|------------------------------------------------------|
| destination hash | 1               | first byte of destination node public key            |
| source hash      | 1               | first byte of source node public key                 |
| cipher MAC       | 2               | MAC for encrypted data in next field                 |
| ciphertext       | rest of payload | encrypted message, see subsections below for details |

## Returned path

Returned path messages provide a description of the route a packet took from the original author. Receivers will send returned path messages to the author of the original message.

| Field       | Size (bytes) | Description                                                                                                          |
|-------------|--------------|----------------------------------------------------------------------------------------------------------------------|
| path length | 1            | length of next field                                                                                                 |
| path        | see above    | a list of node hashes (one byte each)                                                                                |
| extra type  | 1            | extra, bundled payload type, eg., acknowledgement or response. Same values as in [Packet Format](./packet_format.md) |
| extra       | rest of data | extra, bundled payload content, follows same format as main content defined by this document                         |

## Request

| Field        | Size (bytes)    | Description                              |
|--------------|-----------------|------------------------------------------|
| timestamp    | 4               | sender time (unix timestamp)             |
| request data | rest of payload | application-defined request payload body |

For the common chat/server helpers in `BaseChatMesh`, the current request type values are:

| Value  | Name      | Description                                        |
|--------|-----------|----------------------------------------------------|
| `0x01` | get stats | get stats of repeater or room server               |
| `0x02` | keepalive | keep-alive request used for maintained connections |

### Get stats

Gets information about the node, possibly including the following:

* Battery level (millivolts)
* Current transmit queue length
* Current free queue length
* Last RSSI value
* Number of received packets
* Number of sent packets
* Total airtime (seconds)
* Total uptime (seconds)
* Number of packets sent as flood
* Number of packets sent directly
* Number of packets received as flood
* Number of packets received directly
* Error flags
* Last SNR value
* Number of direct route duplicates
* Number of flood route duplicates
* Number posted (?)
* Number of post pushes (?)

### Get telemetry data

Not defined in `BaseChatMesh`. Sensor- and application-specific request payloads may be implemented by higher-level firmware.

### Get Telemetry

Not defined in `BaseChatMesh`.

### Get Min/Max/Ave  (Sensor nodes)

Not defined in `BaseChatMesh`.

### Get Access List

Not defined in `BaseChatMesh`.

### Get Neighbors

Not defined in `BaseChatMesh`.

### Get Owner Info

Not defined in `BaseChatMesh`.


## Response

| Field   | Size (bytes)    | Description                       |
|---------|-----------------|-----------------------------------|
| content | rest of payload | application-defined response body |

Response contents are opaque application data. There is no single generic response envelope beyond the encrypted payload wrapper shown above.

## Plain text message

| Field              | Size (bytes)    | Description                                                                       |
|--------------------|-----------------|-----------------------------------------------------------------------------------|
| timestamp          | 4               | send time (unix timestamp)                                                        |
| txt_type + attempt | 1               | upper six bits are txt_type (see below), lower two bits are attempt number (0..3) |
| message            | rest of payload | the message content, see next table                                               |

txt_type

| Value  | Description               | Message content                                                          |
|--------|---------------------------|--------------------------------------------------------------------------|
| `0x00` | plain text message        | the plain text of the message                                            |
| `0x01` | CLI command               | the command text of the message                                          |
| `0x02` | signed plain text message | first four bytes is sender pubkey prefix, followed by plain text message |

Human-readable text payloads are validated before firmware UI/app callbacks render them. Implementations may reject or hide malformed UTF-8, excessive replacement/control characters, binary-looking high-entropy text and impossible timestamps. This validation is a display/forwarding policy for text payloads only; it does not change the packet format and does not apply to binary datagram, raw/custom, request, response or unknown/future payload types.

# Anonymous request

| Field            | Size (bytes)    | Description                               |
|------------------|-----------------|-------------------------------------------|
| destination hash | 1               | first byte of destination node public key |
| public key       | 32              | sender's Ed25519 public key               |
| cipher MAC       | 2               | MAC for encrypted data in next field      |
| ciphertext       | rest of payload | encrypted message, see below for details  |

## Room server login

| Field          | Size (bytes)    | Description                                                                   |
|----------------|-----------------|-------------------------------------------------------------------------------|
| timestamp      | 4               | sender time (unix timestamp)                                                  |
| sync timestamp | 4               | sender's "sync messages SINCE x" timestamp                                    |
| password       | rest of message | password for room                                                             |

## Repeater/Sensor login

| Field          | Size (bytes)    | Description                                                                   |
|----------------|-----------------|-------------------------------------------------------------------------------|
| timestamp      | 4               | sender time (unix timestamp)                                                  |
| password       | rest of message | password for repeater/sensor                                                  |

## Repeater - Regions request

| Field          | Size (bytes) | Description                  |
|----------------|--------------|------------------------------|
| timestamp      | 4            | sender time (unix timestamp) |
| req type       | 1            | 0x01 (request sub type)      |
| reply path len | 1            | path len for reply           |
| reply path     | (variable)   | reply path                   |

## Repeater - Owner info request

| Field          | Size (bytes) | Description                  |
|----------------|--------------|------------------------------|
| timestamp      | 4            | sender time (unix timestamp) |
| req type       | 1            | 0x02 (request sub type)      |
| reply path len | 1            | path len for reply           |
| reply path     | (variable)   | reply path                   |

## Repeater - Clock and status request

| Field          | Size (bytes) | Description                  |
|----------------|--------------|------------------------------|
| timestamp      | 4            | sender time (unix timestamp) |
| req type       | 1            | 0x03 (request sub type)      |
| reply path len | 1            | path len for reply           |
| reply path     | (variable)   | reply path                   |


# Group text message

| Field        | Size (bytes)    | Description                                  |
|--------------|-----------------|----------------------------------------------|
| channel hash | 1               | first byte of SHA256 of channel's shared key |
| cipher MAC   | 2               | MAC for encrypted data in next field         |
| ciphertext   | rest of payload | encrypted message, see below for details     |

The plaintext contained in the ciphertext matches the format described in [plain text message](#plain-text-message). Specifically, it consists of a four byte timestamp, a flags byte, and the message. The flags byte will generally be `0x00` because it is a "plain text message". The message will be of the form `<sender name>: <message body>` (eg., `user123: I'm on my way`).

Nodes that can decrypt a group text packet may apply the same human-readable text validation before displaying or forwarding it. Companion radio firmware sanitizes malformed decryptable group text before queuing it to the app and does not expose a separate malformed-drop command. Repeater firmware can be configured with `set malformed.drop on` to drop malformed decryptable default-public-channel group text before retransmission. Group datagrams remain binary payloads and are not subject to this text filter.

# Group datagram

| Field        | Size (bytes)    | Description                                  |
|--------------|-----------------|----------------------------------------------|
| channel hash | 1               | first byte of SHA256 of channel's shared key |
| cipher MAC   | 2               | MAC for encrypted data in next field         |
| ciphertext   | rest of payload | encrypted data, see below for details        |

The data contained in the ciphertext uses the format below:

| Field     | Size (bytes)    | Description                                              |
|-----------|-----------------|----------------------------------------------------------|
| data type | 2               | Identifier for type of data. (See number_allocations.md) |
| data len  | 1               | byte length of data                                      |
| data      | rest of payload | (depends on data type)                                   |


# Control data

| Field        | Size (bytes)    | Description                                |
|--------------|-----------------|--------------------------------------------|
| flags        | 1               | upper 4 bits is sub_type                   |
| data         | rest of payload | typically unencrypted data                 |

## DISCOVER_REQ (sub_type)

| Field        | Size (bytes)    | Description                                  |
|--------------|-----------------|----------------------------------------------|
| flags        | 1               | 0x8 (upper 4 bits), prefix_only (lowest bit) |
| type_filter  | 1               | bit for each ADV_TYPE_*                      |
| tag          | 4               | randomly generate by sender                  |
| since        | 4               | (optional) epoch timestamp (0 by default)    |

## DISCOVER_RESP (sub_type)

| Field        | Size (bytes)    | Description                                |
|--------------|-----------------|--------------------------------------------|
| flags        | 1               | 0x9 (upper 4 bits), node_type (lower 4)    |
| snr          | 1               | signed, SNR*4                              |
| tag          | 4               | reflected back from DISCOVER_REQ           |
| pubkey       | 8 or 32         | node's ID (or prefix)                      |


# Atlas telemetry

Atlas telemetry is an optional, disabled-by-default foundation for future topology and network-health export. It is intended for low-rate local export and future Atlas tooling. Enabling Atlas does not change existing routing behavior, and firmware should not flood Atlas packets by default.

The first byte of the payload is the Atlas subtype:

| Value | Name                  | Description                         |
|-------|-----------------------|-------------------------------------|
| 0x01  | POSITION              | Compact node position               |
| 0x02  | NEIGHBORS             | Low-rate neighbor summary           |
| 0x03  | PATH_SAMPLE           | Sampled route telemetry             |
| 0x04  | DENSE_STATS           | Network-health counters             |

POSITION:

| Field       | Size | Description                                      |
|-------------|------|--------------------------------------------------|
| subtype     | 1    | 0x01                                             |
| flags       | 1    | bit 0 altitude, bit 1 speed, bit 2 heading       |
| latitude    | 4    | signed integer, degrees * 1e7                    |
| longitude   | 4    | signed integer, degrees * 1e7                    |
| timestamp   | 4    | epoch seconds                                    |
| altitude    | 2    | optional signed meters                           |
| speed       | 2    | optional cm/s                                    |
| heading     | 2    | optional degrees                                 |

NEIGHBORS uses `subtype,count` followed by compact entries: 4-byte node id, 1-byte RSSI, 1-byte SNR*4, 4-byte last-heard timestamp.

PATH_SAMPLE uses source id, destination id, hop count, hop bytes and an optional latency in milliseconds. Implementations should sample only a small percentage of packets and leave sampling disabled by default.

DENSE_STATS contains 32-bit counters for heard, duplicate, forward, suppression, route-cache hits/misses, TX airtime and RX airtime.

# Custom packet

Custom packets have no defined format.
