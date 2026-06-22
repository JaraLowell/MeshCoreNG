# WiFi TCP bridge instellen

Deze handleiding is voor een repeater waarop de `_bridge_tcp` firmware is geflasht. De bridge biedt optionele gecontroleerde backhaul tussen geselecteerde MeshCore RF-deployments via een TCP server.

MeshCoreNG blijft RF-first. Gebruik de bridge voor afgebakende deployments zoals gescheiden RF-eilanden, remote RF-gateways, tijdelijke backhaul, testen, onderzoek of private infrastructuur. Gebruik dit niet als wereldwijde flooding-backbone of onbeperkt packet-replicatiesysteem.

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

Om een bridge-wachtwoord voor TCP-clients te vereisen:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --password bridgeSecret
```

De server start standaard ook een statuspagina:

```text
http://localhost:8080/
```

Open die pagina op de server zelf, of vervang `localhost` door het IP-adres van de server vanaf een andere machine op hetzelfde netwerk. De pagina toont online en recent geziene bridge-nodes, firmwareversie, heartbeat-status, packet counters, RF-neighbour count per node wanneer nieuwe firmware die meestuurt, bridge-neighbour count vanuit de server, en RF dutycycle-budgetverbruik.

De statuspagina houdt per bekende bridge-node een 24-uurs verkeersvenster in geheugen bij. `RX 24h` en `TX 24h` tonen het aantal ontvangen en verzonden packets per node in de laatste 24 uur. Nodes die disconnecten blijven als `offline` zichtbaar zolang ze nog packet-history binnen dat 24-uurs venster hebben. Deze tellers beginnen opnieuw als het Python bridge-serverproces opnieuw start.

Elke bridge-client heeft een eigen begrensde TCP transmit queue. Binnenkomende bridge-packets worden onafhankelijk per andere verbonden node in de queue gezet, zodat een trage TCP-client de fanout naar de rest van de bridge niet blokkeert. De node-kaarten tonen queue depth, queue drops, skipped duplicates, send errors en hoe lang geleden de laatste TCP TX was. Deze counters gaan over levering naar de TCP-socket; RF-forwarding kan daarna nog steeds door de repeater worden tegengehouden door dutycycle, duplicate checks, CAD/channel busy, TTL, hop-limieten of bridge profile-instellingen.

De tegels `Duty used` en `Duty left` tonen het RF TX dutycycle-uurbudget van die node als timers. Nieuwe bridge firmware stuurt cumulatief gemeten RF TX airtime mee in de heartbeat; de server bewaart een baseline zodra hij de node ziet en toont daarna echte RF TX tijd sinds dat moment. `Duty left` wordt berekend uit het ingestelde uurbudget. Bij `set dutycycle 10` is het RF TX-budget 10% van een uur, dus 360 seconden. Als `Duty used` dan `3m 00s` toont, is de helft van het budget op en toont `Duty left` ook `3m 00s`. Oudere bridge firmware zonder cumulatieve RF TX airtime valt terug op de oudere duty-budget telemetry, die tussen heartbeats alweer kan aanvullen.

De server controleert ook GitHub releases en toont bij een node een `update` badge wanneer de gemelde firmwareversie ouder is dan de nieuwste firmware-release waar al `.bin` assets aan hangen. Alleen een tag is dus niet genoeg, omdat de node pas bijgewerkt kan worden wanneer de firmwarebestanden echt bestaan. Standaard wordt `MichTronics/MeshCoreNG` een keer per uur gecontroleerd. Gebruik `--firmware-update-repo owner/repo` om een andere repository te gebruiken, of `--firmware-update-interval 0` om de check uit te zetten.

Voor testen en monitoren kun je de server starten met statusregels en heartbeat-timeout:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --status-interval 10 --client-timeout 90 --log-packets
```

De TCP bridge firmware stuurt elke 30 seconden een heartbeat naar de server. De server gebruikt normale pakketten en heartbeats om de `idle` timer van de client bij te werken. Als een node stroom verliest en er geen heartbeat meer binnenkomt voor `--client-timeout`, verbreekt de server die oude verbinding.

Remote beheer staat op een aparte pagina:

```text
http://localhost:8080/manage
```

Kies een node, vul het eigen MeshCore admin-wachtwoord van die node in, en stuur een normaal CLI-commando zoals `get bridge.status`. Repeaters met verschillende admin-wachtwoorden kunnen zo vanaf dezelfde pagina beheerd worden, omdat het wachtwoord per commando wordt ingevoerd en door de gekozen repeater wordt gecontroleerd.

Wil je de HTTP-pagina zelf ook met een apart wachtwoord beschermen, start de server dan met:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --admin-password webAdminSecret
```

Dit beschermt toegang tot de remote beheerpagina. Het vervangt niet het admin-wachtwoord per node.

Gebruik bij lokaal testen het LAN-IP van deze machine als `bridge.server`. Gebruik bij een gecontroleerde remote deployment het bereikbare IP-adres of de domeinnaam van de server.

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
set bridge.password bridgeSecret
```

Gebruik in plaats van `192.168.1.123` het IP-adres of de hostname van jouw TCP bridge server.
Sla `set bridge.password` over als de server zonder `--password` is gestart.

::: tip Upgrade vanaf oudere firmware
Na de grote merge van de originele MeshCore v1.16.0 firmware kan de opgeslagen preferences-layout afwijken van oudere MeshCoreNG builds. Daardoor kunnen WiFi- en TCP bridge-instellingen na de eerste update leeg/default lijken. Vul in dat geval `wifi.ssid`, `wifi.password`, `bridge.server`, `bridge.port`, eventueel `bridge.password` en `bridge.enabled` opnieuw in en sla de instellingen op. Normale volgende OTA-updates met een niet-merged `.bin` zouden deze instellingen daarna behouden.
:::

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
get bridge.password
get bridge.enabled
```

Verwachte bridge type:

```text
> tcp
```

`get wifi.password` en `get bridge.password` tonen niet het echte wachtwoord, maar `***`.

## 6. Geselecteerde repeaters koppelen

Flash op elke locatie de bedoelde bridge-repeater met `_bridge_tcp` firmware en configureer die repeaters naar dezelfde TCP server en poort:

```text
set bridge.server mijnserver.example.com
set bridge.port 4200
set bridge.password bridgeSecret
set bridge.enabled on
```

Geselecteerd bridge-verkeer uit het ene RF-deployment gaat via TCP naar de server en wordt beschikbaar voor de andere bedoelde bridge-repeaters. Houd bridge-groepen afgebakend, behoud RF-locality en voorkom onnodige rebroadcast in RF-netwerken.

Best practices:

- Bridge alleen noodzakelijke channels, topics of verkeersbronnen.
- Gebruik regionale segmentatie bij grotere deployments.
- Gebruik private bridge-servers of private bridge-groepen waar mogelijk.
- Vermijd full-network flooding over bridge-links.
- Monitor duplicate counters, airtime en congestion nadat de bridge is ingeschakeld.

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
- De server is bereikbaar vanaf hetzelfde WiFi-netwerk of gecontroleerde remote netwerk.
- Een firewall laat TCP poort `4200` door.

### Server blijft een node tonen nadat de stroom eraf is

Gebruik de heartbeat-timeout:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --status-interval 10 --client-timeout 90
```

De statusregel toont `idle`, `hb_age` en `hb`. Als `idle` groter wordt dan `--client-timeout`, verbreekt de server de oude TCP sessie.

Voor lokaal testen met maximaal een node per IP kun je ook dit gebruiken:

```bash
python3 tools/tcp_bridge_server.py --port 4200 --replace-same-ip
```

Gebruik `--replace-same-ip` niet als meerdere bridge nodes vanaf hetzelfde publieke IP of achter dezelfde NAT kunnen verbinden.

### TCP bridge is niet versleuteld

De huidige TCP bridge verstuurt verkeer zonder TLS. Gebruik dit op een vertrouwd netwerk of beperk toegang tot de server met firewallregels.
