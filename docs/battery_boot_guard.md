# Low Battery Guards

Some battery-powered boards can get stuck in a boot loop when the battery is deeply discharged. The board starts, enables enough hardware to draw more current, the voltage drops again, and the device resets before it can recover cleanly.

MeshCoreNG has generic low-battery guards for firmware apps that use `MainBoard`.

## Boot guard

Directly after `board.begin()`, the firmware reads the board battery voltage with `getBattMilliVolts()`.

If the board reports a valid battery voltage below the boot threshold, the firmware does not continue into radio, display, GPS, sensor, bridge, or mesh startup. Instead it prints a short serial message and sleeps before checking again.

This gives USB power or a charger time to bring the battery above the minimum voltage before the full firmware load starts.

## Defaults

The default values are:

```text
LOW_BAT_BOOT_GUARD_MV=3300
LOW_BAT_BOOT_VALID_MIN_MV=2500
LOW_BAT_BOOT_RETRY_SECS=60
```

Meaning:

- below `2500mV`: treat the reading as invalid or unsupported and continue booting
- `2500mV` to `3299mV`: sleep and retry
- `3300mV` or higher: continue normal boot

Boards without a useful battery meter usually return `0` or another invalid value, so they are not blocked by the guard.

## Where it is enabled

The guard is enabled in the main firmware app types:

- repeater
- GPS tracker / sensor
- room server
- companion radio
- KISS modem
- secure chat

This means every board variant that reports a valid battery voltage through its board implementation automatically gets the same protection.

## CLI tuning

Repeater, GPS tracker / sensor, and room server firmware builds expose the guard through the normal MeshCore CLI:

```text
get boot.lowbat.guard
set boot.lowbat.guard on
set boot.lowbat.guard off

get boot.lowbat.mv
set boot.lowbat.mv 3300

get boot.lowbat.valid_min
set boot.lowbat.valid_min 2500

get boot.lowbat.retry
set boot.lowbat.retry 60
```

`boot.lowbat.mv` is the boot threshold. Setting it to `0` disables the threshold, but `set boot.lowbat.guard off` is clearer.

The CLI values are stored in the normal node preferences and are applied on the next boot after preferences are loaded. Non-CommonCLI firmware apps use the build-time defaults.

## Build-time tuning

The values can be changed per firmware environment with build flags:

```text
-D LOW_BAT_BOOT_GUARD_MV=3300
-D LOW_BAT_BOOT_VALID_MIN_MV=2500
-D LOW_BAT_BOOT_RETRY_SECS=60
```

To disable the guard for a specific build:

```text
-D LOW_BAT_BOOT_GUARD_MV=0
```

## Serial output

When the guard is active, serial output looks like:

```text
LOWBAT: boot guard active, battery=3180mV threshold=3300mV; retry in 60s
```

Once the measured voltage is high enough, the firmware continues normal startup.

## Runtime guard

Repeater, GPS tracker / sensor, and room server builds also have a runtime low-battery guard. During the normal main loop, the firmware checks the battery voltage. If the reading is valid, the board is not externally powered, and the voltage is below the runtime threshold, the node sleeps before continuing work.

This protects battery nodes that boot successfully but later drain too far while running. It is especially important for WiFi/bridge, GPS, display, and sensor deployments.

Default runtime values:

```text
LOW_BAT_RUNTIME_GUARD_MV=3300
LOW_BAT_RUNTIME_WARN_MV=3500
LOW_BAT_RUNTIME_VALID_MIN_MV=2500
LOW_BAT_RUNTIME_RETRY_SECS=1800
LOW_BAT_RUNTIME_CHECK_SECS=30
```

Runtime CLI:

```text
get runtime.lowbat.guard
set runtime.lowbat.guard on
set runtime.lowbat.guard off

get runtime.lowbat.mv
set runtime.lowbat.mv 3300

get runtime.lowbat.warn
set runtime.lowbat.warn 3500

get runtime.lowbat.valid_min
set runtime.lowbat.valid_min 2500

get runtime.lowbat.retry
set runtime.lowbat.retry 1800
```

When the runtime guard is active, serial output looks like:

```text
LOWBAT: runtime guard active, battery=3220mV threshold=3300mV; sleep for 1800s
```

The runtime guard checks periodically, not on every loop iteration. The default check interval is 30 seconds and can be changed per build with `LOW_BAT_RUNTIME_CHECK_SECS`.
