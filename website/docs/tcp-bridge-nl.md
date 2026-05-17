# WiFi TCP bridge instellen

Deze handleiding is voor een repeater waarop de `_bridge_tcp` firmware is geflasht. De bridge verbindt twee of meer LoRa-netwerken via een centrale TCP server.

## Wat je nodig hebt

- Een ESP32 repeater met WiFi en `_bridge_tcp` firmware.
- De USB poort van de repeater, bijvoorbeeld `/dev/ttyACM0`.
- `meshcli` op je computer.
- Een TCP bridge server die bereikbaar is vanaf de repeater.

## 1. Start de TCP bridge server

Start de server op een machine die bereikbaar is vanaf de bridge-repeaters. Dat kan een VPS, Raspberry Pi of lokale computer zijn.

```bash
python3 tools/tcp_bridge_server.py --port 4200
```

Gebruik bij lokaal testen het LAN-IP van deze machine als `bridge.server`. Gebruik bij internetgebruik een publiek IP-adres of domeinnaam.

## 2. Verbind met de repeater

Een TCP bridge build is een repeater, geen serial companion. Gebruik daarom `-r`:

```bash
meshcli -s /dev/ttyACM0 -r
```

Als je deze fout ziet:

```text
No response from meshcore node, disconnecting
Are you sure your node is a serial companion ?
To connect to a repeater, use -r option.
```

dan miste je `-r`. Start opnieuw met:

```bash
meshcli -s /dev/ttyACM0 -r
```

## 3. Stel WiFi en TCP bridge in

Voer deze commando's in via `meshcli`:

```text
set bridge.enabled off
set wifi.ssid MijnWiFiNaam
set wifi.password MijnWiFiWachtwoord
set bridge.server 192.168.1.123
set bridge.port 4200
```

Gebruik in plaats van `192.168.1.123` het IP-adres of de hostname van jouw TCP bridge server.

Voor een server op internet:

```text
set bridge.server mijnserver.example.com
```

## 4. Herstart na WiFi-wijzigingen

Na `set wifi.ssid` en `set wifi.password` moet de repeater opnieuw starten voordat de WiFi-instellingen actief worden.

```text
reboot
```

Verbind daarna opnieuw:

```bash
meshcli -s /dev/ttyACM0 -r
```

Zet daarna de bridge aan:

```text
set bridge.enabled on
```

## 5. Controleer de instellingen

```text
get bridge.type
get wifi.ssid
get bridge.server
get bridge.port
get bridge.enabled
```

Verwachte bridge type:

```text
> tcp
```

`get wifi.password` toont niet het echte wachtwoord, maar `***`.

## 6. Meerdere repeaters koppelen

Flash op beide locaties een repeater met `_bridge_tcp` firmware en configureer ze allebei naar dezelfde TCP server en poort:

```text
set bridge.server mijnserver.example.com
set bridge.port 4200
set bridge.enabled on
```

Pakketten die de ene repeater via LoRa ontvangt, gaan via TCP naar de server en worden door de andere repeater weer in zijn lokale LoRa-netwerk gezet.

## Problemen oplossen

### Permission denied op `/dev/ttyACM0`

Voeg je gebruiker toe aan de `dialout` groep:

```bash
sudo usermod -aG dialout $USER
```

Log daarna uit en opnieuw in.

### Verkeerde seriele poort

Controleer welke poort verschijnt nadat je de repeater aansluit:

```bash
ls /dev/ttyACM*
ls /dev/ttyUSB*
```

Gebruik daarna de juiste poort met `meshcli -s <poort> -r`.

### Bridge komt niet online

Controleer:

- Als de CLI traag of rommelig wordt tijdens configureren, voer `set bridge.enabled off` uit, reboot, en stel daarna eerst WiFi en server in voordat je de bridge weer aanzet.
- De repeater is herstart na het instellen van WiFi.
- `get bridge.enabled` staat op `on`.
- `get bridge.server` en `get bridge.port` kloppen.
- De TCP bridge server draait.
- De server is bereikbaar vanaf hetzelfde WiFi-netwerk of via internet.
- Een firewall laat TCP poort `4200` door.

### TCP bridge is niet versleuteld

De huidige TCP bridge verstuurt verkeer zonder TLS. Gebruik dit op een vertrouwd netwerk of beperk toegang tot de server met firewallregels.
