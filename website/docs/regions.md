# Regions

## Overview

MeshCoreNG has two region-related features:

- A generated Dutch region database for looking up known MeshCore region codes.
- A runtime region map for controlling which scopes a repeater should forward.

The lookup database helps operators find correct codes. The runtime region map decides forwarding policy on a device.

## Dutch region database

The Dutch region database is generated from the Dutch MeshWiki region list and compiled into firmware flash. It is read-only at runtime and does not allocate a large RAM database.

Useful commands:

```text
regiondb info
regiondb provinces
regiondb find gron
regiondb get 45
regiondb code <code_id>
```

This is useful for installers, companion apps and operators who need to choose a region code without carrying a separate lookup file.

## Runtime forwarding regions

Runtime regions are editable scopes such as `eu`, `nl`, `nl-nh` or a local town/area code.

```text
region put eu
region put nl eu
region put nl-nh nl
region put nl-nh-bov nl-nh
region allowf nl-nh-bov
region home nl-nh-bov
region tree
region save
```

`allowf` means this repeater may forward flood traffic for that region. `denyf` blocks forwarding for that region. Use `region save` after changes so the map survives reboot.

## Practical guidance

Local repeaters should usually allow only their local scope. Backbone or high-site repeaters can intentionally allow broader scopes such as province, country or regional bridge groups.

Avoid enabling broad scopes everywhere. The point is to preserve RF airtime by keeping local traffic local and forwarding wide-area traffic only where it is actually needed.

## Region profiles

Region profile support allows builds to ship with known defaults for a deployment. This is useful for community firmware images where devices should start with the correct regional assumptions while still allowing operators to inspect and adjust runtime policy.
