## MeshCoreNG

MeshCoreNG is een Next Gen variant van MeshCore.

Kort gezegd: MeshCore laat LoRa-apparaten berichten naar elkaar doorgeven zonder internet. MeshCoreNG bouwt daarop verder en probeert vooral repeaters slimmer te maken, zodat grotere en drukkere netwerken beter blijven werken.

Website en webflasher: https://michtronics.github.io/MeshCoreNG/

Het doel is niet om MeshCore opnieuw te bouwen. Het doel is om stap voor stap verbeteringen toe te voegen, zonder bestaande clients of het bestaande protocol kapot te maken.

## Waarom dit in Nederland belangrijk is

MeshCoreNG wordt ontwikkeld vanuit Nederland. Juist hier zie je snel het probleem waar dense-mesh firmware mee moet omgaan.

Nederland is klein, dichtbebouwd en druk. In steden en dorpen kunnen veel LoRa-nodes en repeaters elkaar tegelijk horen. Dat klinkt gunstig, maar bij een flood mesh kan het ook betekenen dat te veel repeaters hetzelfde bericht opnieuw uitzenden. Daardoor raakt het kanaal sneller vol.

Daar komt bij dat we op EU868 met airtime- en duty-cycle beperkingen werken. Elke onnodige heruitzending kost dus echt capaciteit. In een rustig buitengebied wil je juist maximale propagatie, maar in een Nederlandse stad wil je vooral voorkomen dat het netwerk zichzelf overschreeuwt.

MeshCoreNG probeert precies dat probleem aan te pakken: betrouwbaar blijven in rustige gebieden, maar rustiger en slimmer worden in drukke Nederlandse meshes.

## Wat willen we bereiken?

MeshCore werkt goed als simpel flood mesh netwerk: een bericht wordt door repeaters verder verspreid. Dat is sterk en betrouwbaar, vooral in kleine of rustige netwerken.

Maar in een druk netwerk kan flooding ook te veel radioverkeer veroorzaken. Dan gaan veel repeaters hetzelfde bericht opnieuw uitzenden. Dat kost airtime, verhoogt kans op botsingen, en kan een netwerk trager maken.

MeshCoreNG wil dit beter maken:

- Minder onnodige heruitzendingen.
- Minder drukte op het LoRa-kanaal.
- Repeaters die beter meten wat er gebeurt.
- Dense city meshes die stabieler blijven.
- Sparse rural meshes die nog steeds goed blijven doorgeven.
- Betere bridge-opties voor gecontroleerde RF-eilanden.
- Makkelijker flashen en firmware downloaden via de browser.
- Region-aware tools voor grotere deployments.
- Een telemetry-basis voor toekomstige kaarten, dashboards en observers.
- Geen breuk met bestaande MeshCore clients.

## Betrouwbaarheid van nodes

MeshCoreNG bevat nu ook een algemene low-battery boot guard voor boards met een batterijmeter. Direct na `board.begin()` leest de firmware de batterijspanning van het board. Als die meting geldig maar te laag is, gaat de node slapen en probeert hij later opnieuw, in plaats van meteen radio, display, GPS, sensors of bridge-code te starten. Dit helpt vooral bij boards die na een diep ontladen batterij aan een lader blijven rebooten.

Standaardgedrag:

- lager dan `2500mV`: behandelen als ongeldige of niet-ondersteunde batterijmeting
- `2500mV` tot `3299mV`: slapen en opnieuw proberen
- `3300mV` of hoger: normaal doorstarten

Repeater-, GPS tracker / sensor- en room server-builds kunnen dit via de CLI instellen met `set boot.lowbat.guard`, `set boot.lowbat.mv`, `set boot.lowbat.valid_min` en `set boot.lowbat.retry`. Deze waarden zijn ook per build aan te passen met `LOW_BAT_BOOT_GUARD_MV`, `LOW_BAT_BOOT_VALID_MIN_MV` en `LOW_BAT_BOOT_RETRY_SECS`.

Daarnaast hebben repeater-, GPS tracker / sensor- en room server-builds nu een runtime low-battery guard. Die controleert tijdens normaal draaien periodiek de batterijspanning. Als de node niet extern gevoed wordt en de batterij onder de runtime-drempel komt, gaat de node slapen voordat WiFi, bridge, GPS, display of radio de batterij verder leegtrekken. Instellen kan met `set runtime.lowbat.guard`, `set runtime.lowbat.mv`, `set runtime.lowbat.valid_min` en `set runtime.lowbat.retry`. Zie [docs/battery_boot_guard.md](./docs/battery_boot_guard.md).

GPS tracker varianten met een display houden het display nu aan en tonen tracker-informatie zoals GPS fix-status, satellieten, positie of waiting-status, TX interval en batterijspanning. Native tracker-packets bevatten ook snelheid en heading wanneer de GPS-provider die kan leveren, en de TCP bridge map kan de gereden route tonen. Zie [docs/location_tracker.md](./docs/location_tracker.md).

## Wat hebben we nu gedaan?

We hebben de eerste echte dense-mesh basis toegevoegd aan de repeater firmware.

### 1. Minder flood advert lawaai

Flood adverts zijn netwerk-advertenties die via repeaters verspreid kunnen worden. In een druk netwerk kunnen die veel airtime kosten.

Daarom heeft MeshCoreNG nu:

- `flood.advert.base`
- standaardwaarde `0.308`

Simpel uitgelegd:

- `0` betekent: ontvangen flood adverts niet verder doorsturen.
- `0.308` betekent: dense mesh standaard, minder doorsturen bij meer hops.
- `1` betekent: alles doorsturen zoals normaal.

Dit helpt vooral in drukke repeater-netwerken waar veel nodes elkaar al kunnen horen.

### 2. Dense stats

We kunnen nu beter zien wat een repeater doet.

Met:

```text
get dense.stats
```

zie je onder andere:

- hoeveel flood adverts zijn ontvangen
- hoeveel flood adverts zijn doorgestuurd
- hoeveel flood adverts zijn gedropt
- hoeveel duplicate flood packets er zijn
- hoeveel airtime RX/TX ongeveer gebruikt wordt
- hoeveel CAD/channel-busy events er zijn
- density level
- congestion level

Met:

```text
clear dense.stats
```

reset je deze tellers. De stats staan alleen in RAM en verdwijnen ook bij reboot.

### 3. Handmatige relay probability

We hebben een extra knop toegevoegd:

```text
get flood.relay.prob
set flood.relay.prob <0..255>
```

Simpel uitgelegd:

- `0` betekent: flood packets niet verder relayn.
- `128` betekent: ongeveer de helft relayn.
- `255` betekent: normaal alles relayn wat toegestaan is.

De standaard is `255`, zodat bestaande netwerken hetzelfde blijven werken.

### 4. Dynamic mode voorbereiding

Er is nu ook:

```text
get flood.dynamic.enable
set flood.dynamic.enable on
set flood.dynamic.enable off
```

Belangrijk: in deze versie verandert dynamic mode nog niet automatisch het gedrag.

Voor nu is het vooral voorbereiding en observatie. We willen eerst echte data verzamelen uit echte netwerken voordat we de firmware automatisch slimmer laten beslissen.

Standaard staat dynamic mode uit.

### 5. Betere channel-busy detectie

De repeater gebruikt nu hardware CAD/channel scan waar mogelijk. Daardoor kan de firmware beter zien of het kanaal druk is voordat hij zelf gaat zenden.

Dat helpt tegen botsingen en onnodig zenden op een bezet LoRa-kanaal.

### 6. Node-based retransmit spreading

In een dense repeatergroep kunnen repeaters nog steeds te netjes tegelijk lopen: meerdere repeaters ontvangen hetzelfde pakket op hetzelfde moment, maken een vergelijkbare `txdelay` keuze, en beginnen bijna tegelijk opnieuw te zenden. MeshCoreNG telt daarom nu een heel kleine deterministische node-offset op bij de bestaande random retransmit delay voor flood verkeer.

De flood retransmit delay is nu:

```text
random txdelay spreiding + stabiele node-offset
```

Die stabiele offset komt uit de node-identiteit die al in de firmware staat. Hij blijft gelijk na een reboot, veroorzaakt geen extra netwerkverkeer, verandert niets aan het protocol of packet format, en wordt alleen gebruikt voor flood retransmit scheduling. Als `txdelay` op `0` staat, wordt de offset niet toegevoegd. Het oude zero-delay gedrag blijft dus beschikbaar. Je kunt alleen de stabiele offset ook uitzetten met `set flood.node.delay off`.

Dit is iets anders dan CAD retry timing:

- `txdelay` spreidt repeaters voordat een flood packet in de TX queue komt.
- De node-offset voorkomt dat repeaters steeds precies in hetzelfde ritme blijven hangen.
- CAD retry gebeurt later, nadat de radio ziet dat het kanaal bezet is. De huidige CAD retry window is 120-360 ms.

Praktisch tunen:

| Repeaterrol | Advies |
|---|---|
| Lokale / lage repeater | Een lagere `txdelay` houdt de lokale mesh sneller. |
| Hoge / backbone repeater | Een hogere `txdelay` geeft lokale repeaters eerst kans om lokaal verkeer af te handelen. |
| Erg drukke stadsmesh | Laat `txdelay` aan zodat random spreiding plus node-offset gelijktijdige retransmits vermindert. |

### 7. Duplicate-hearing retransmit suppression

Dense meshes hebben ook voordeel van het annuleren van werk dat niet meer nodig is. Als een repeater een flood retransmit plant en daarna genoeg andere repeaters hetzelfde packet hoort doorsturen voordat zijn eigen timer afloopt, kan MeshCoreNG die geplande retransmit onderdrukken.

Simpel voorbeeld:

```text
nieuw flood packet gehoord
retransmit gepland
twee duplicate forwards van hetzelfde packet gehoord
eigen retransmit annuleren
```

De standaarddrempel is voorzichtig: er moeten twee duplicate forwards gehoord worden voordat de retransmit wordt geannuleerd. Als er geen duplicates binnenkomen, zendt de repeater gewoon zoals voorheen. Sparse netwerken houden dus hun bereik. Lokaal gemaakte packets, direct routing, ACKs, path/control packets en trace/control verkeer worden niet onderdrukt. Je kunt dit gedrag uitzetten met `set flood.dup.suppress off`.

Dit vermindert dubbele floods, airtime-verspilling en botsingskans zonder extra packets, zonder synchronisatie, en zonder protocolwijziging.

### 8. Internetbrug — optioneel transport voor gescheiden RF-netwerken

MeshCoreNG blijft RF-first. De bridge is optioneel transport/backhaul voor specifieke deployments, geen vervanging voor lokale RF-werking.

De bridge is bedoeld voor:
- gescheiden geografische MeshCore RF-regio's die bewust geselecteerd verkeer moeten uitwisselen
- remote RF-gateways met gecontroleerde backhaul
- tijdelijke backhaul bij events, testen of storingen
- observer-, meet- en onderzoeksopstellingen
- private infrastructuur van een bekende groep

De bridge is niet bedoeld als:
- wereldwijde flooding-backbone
- altijd-aan globale relay
- onbeperkte packet-replicatie
- manier om normale RF-planning en segmentatie te omzeilen

Geselecteerd verkeer kan optioneel tussen gescheiden MeshCore-deployments worden getransporteerd. Operators bepalen zelf welke bridge-server, repeaters, regio's en verkeersbronnen bij hun netwerk passen.

```
[RF-eiland A]  <-->  [Bridge-repeater]  <-->  [private/gecontroleerde bridge-server]  <-->  [Bridge-repeater]  <-->  [RF-eiland B]
```

RF-locality blijft belangrijk. Bridge alleen wat nodig is, houd lokaal verkeer lokaal waar dat kan, gebruik regionale segmentatie en voorkom full-network flooding over bridge-links.

Geplande of onderzochte bescherming voor multi-bridge omgevingen omvat path fingerprints, lichte path hashes, bridge loop detection, duplicate suppression, TTL/hop-controls en bridge scoping.

**Route 1: ESP32-repeater met WiFi**

Repeaters met WiFi kunnen verbinden met een geselecteerde bridge-server.

```text
set wifi.ssid     MijnWiFi
set wifi.password geheim123
set bridge.server mijnserver.example.com
set bridge.port   4200
set bridge.password bridgeSecret
set bridge.enabled on
```

**Upgrade-notitie:** MeshCoreNG blijft compatibel met de TCP bridge preferences van voor de grote merge van de originele MeshCore v1.16.0 firmware. Bij een update vanaf oudere MeshCoreNG bridge-builds worden opgeslagen WiFi- en TCP bridge-instellingen automatisch uit de legacy-layout gemigreerd. Als een node al een keer met een build heeft opgestart die verschoven/lege waarden heeft opgeslagen, vul dan eenmalig `wifi.ssid`, `wifi.password`, `bridge.server`, `bridge.port`, eventueel `bridge.password` en `bridge.enabled` opnieuw in.

Bridge-repeaters sturen bridge-originated flood traffic standaard niet opnieuw via LoRa RF uit. Voor gecontroleerde deployments waarbij bridge-verkeer bewust het lokale RF-mesh in mag, zet je dit expliciet aan:

```text
set bridge.rf on
```

Voor eenmalige lokale RF-injectie van bridge-originated packets gebruik je:

```text
set bridge.rf local
```

Bridge RF-forwarding loopt nog steeds via het normale repeater-forwardingpad. Regioregels, duplicate checks, loop detection, hop-limieten, relay probability, retransmit delay en de normale RF TX queue blijven gelden.

Voor gecontroleerde RF-eilanden of backbone-links gebruik je de bridge export- en profile-controls in plaats van de TCP bridge een echte MeshCore route-hop te maken:

```text
set bridge.profile island    # RF-eiland bridge: source both, RF local, messages tot 4 RF hops
set bridge.profile repeater  # gecontroleerde backhaul: source both, RF on, export all
get bridge.profile           # toont het laatst toegepaste profiel: default, island of repeater
get bridge.export
get bridge.export.maxhops
get bridge.tcp.ttl
```

TCP bridge v2 gebruikt een kleine TCP-only envelope met origin- en TTL-metadata. De MeshCore route/path in het packet wordt niet aangepast.

Alle 38 ESP32-repeater varianten hebben nu een bijbehorende `_bridge_tcp` firmware. Zie [docs/cli_commands.md](./docs/cli_commands.md) voor alle instelmogelijkheden.

**Bridge firmwaretypes**

MeshCoreNG heeft meerdere bridge-routes:

| Build type | Transport | Typisch gebruik |
| --- | --- | --- |
| `_bridge_tcp` | ESP32 WiFi TCP-client | Een WiFi-repeater verbindt direct met een gecontroleerde bridge-server. |
| `_bridge_tcp_ble` | ESP32 WiFi TCP-client + BLE UART bridge | Geselecteerde 8MB/16MB ESP32 WiFi+BLE-repeaters kunnen TCP en BLE bridge transport in een firmware draaien. |
| `_bridge_rs232` | Serial/UART bridge | Boards zonder WiFi gebruiken een PC/Raspberry Pi host-script of een directe bedrade UART-link naar een andere repeater. |
| `_bridge_espnow` | ESP-NOW | Lokale ESP32 bridge-experimenten waarbij WiFi-infrastructuur niet het hoofdtransport is. |
| `_bridge_ble` | BLE UART bridge | nRF52- en ESP32-BLE-repeaters kunnen een korte-afstand bridge maken zonder WiFi, USB of extra UART-bedrading. |

Gebruik `get bridge.type` om te controleren welke bridge-modus in de firmware zit. Sommige bridge-builds hebben ook `get bridge.status`, `get node.info` en waar ondersteund een kleine HTTP-statuspagina. De Python TCP bridge-server statuspagina toont verbonden nodes, recente packet type/route/hop logs, sensor adverts, tracker locaties en JSON endpoints zoals `/status.json`, `/packets.json`, `/sensors.json` en `/locations.json`. De tracker map op `/map` toont de laatste trackerpositie, snelheid, heading en de routegeschiedenis die de server in geheugen heeft.

De BLE bridge is beschikbaar voor nRF52 BLE-varianten met Bluefruit en ESP32-varianten met BLE-support. Hij draait tegelijk als central en peripheral, zodat beide repeaters de BLE-link kunnen starten. Flash dezelfde `_bridge_ble` firmware op beide repeaters, zet eventueel op beide kanten dezelfde `bridge.secret` voor een private bridge-pair, en zet daarna `set bridge.enabled on`. Gecombineerde `_bridge_tcp_ble` builds zijn toegevoegd voor ESP32-boards met genoeg flash; 4MB ESP32-boards blijven per board testkandidaten omdat TCP+BLE daar krap kan worden.

**Route 2: Repeater via USB of directe UART**

Sommige repeaters hebben geen WiFi, zoals nRF52-boards (RAK4631), RP2040-boards, STM32-boards en ESP32-boards op locaties zonder WiFi-bereik. Die kunnen een PC of Raspberry Pi via USB als bridge-transporthost gebruiken.

De repeater draait gewone `_bridge_rs232` firmware en stuurt bridge-verkeer via de seriële poort. Op de aangesloten computer draait een klein Python-script dat de TCP-verbinding met de geselecteerde bridge-server verzorgt.

```
[LoRa RF deployment]  <-->  [Repeater + RS232 bridge]  <--USB-->  [PC/RPi + usb_bridge_client.py]  <-->  [bridge-server]
```

Instellen op de repeater (RS232 bridge firmware):

```text
set bridge.enabled on
```

Script starten op de PC of Raspberry Pi:

```bash
pip install pyserial
python3 tools/usb_bridge_client.py --serial /dev/ttyUSB0 --baud 115200 \
                                    --server mijnserver.example.com --port 4200 \
                                    --bridge-password bridgeSecret
```

Op Windows gebruik je `--serial COM3` in plaats van `/dev/ttyUSB0`. Het script staat in deze repository bij [tools/usb_bridge_client.py](./tools/usb_bridge_client.py).

Dezelfde `_bridge_rs232` firmware kan ook als directe bedrade UART bridge tussen twee repeaters gebruikt worden, zonder WiFi en zonder USB-host:

```text
Repeater A TX  -> Repeater B RX
Repeater A RX  -> Repeater B TX
Repeater A GND -> Repeater B GND
```

Gebruik 3.3V TTL UART-niveaus. Sluit geen echte +/-12V RS232 direct op de board-pinnen aan.

Voor Seeed SenseCAP Solar gebruikt de RS232 bridge build `Serial1` op `D6`/`D7`:

```text
D6 = TX = GNSS_TX
D7 = RX = GNSS_RX
```

Verbind SenseCAP Solar repeaters als `D6/TX -> D7/RX`, `D7/RX -> D6/TX` en `GND -> GND`. Deze pinnen worden gedeeld met de GNSS UART, dus verwacht niet dat GNSS/GPS tegelijk dezelfde UART gebruikt.

**Server starten** (op een VPS, Raspberry Pi of gewone pc met Python 3.7+):

```bash
python3 tools/tcp_bridge_server.py --port 4200
# optioneel toegangswachtwoord:
python3 tools/tcp_bridge_server.py --port 4200 --password bridgeSecret
```

Het serverscript staat in deze repository bij [tools/tcp_bridge_server.py](./tools/tcp_bridge_server.py). Het heeft geen externe dependencies. WiFi-repeaters en USB-repeaters kunnen tegelijk via dezelfde gecontroleerde bridge-server verbonden zijn.

**Route 3: Python roomserver via de bridge**

MeshCoreNG bevat ook een minimale Python roomserver voor gecontroleerde bridge-deployments. Die verbindt met de TCP bridge-server als extra bridge-client, adverteert zichzelf als MeshCore roomserver, accepteert room-logins, bewaart recente posts, stuurt ACKs en pusht nog niet gesynchroniseerde posts terug naar clients.

```
[MeshCore clients via LoRa] <--> [Bridge-repeater] <--> [bridge-server] <--> [python_room_server.py]
```

Bridge-server starten:

```bash
python3 tools/tcp_bridge_server.py --port 4200
```

Python roomserver starten:

```bash
pip install cryptography
python3 tools/python_room_server.py --server mijnserver.example.com --port 4200 \
  --bridge-password bridgeSecret \
  --name "Python Room" --password geheim \
  --state /home/pi/meshcore/python_room_server_state.json
```

Op de bridge-repeater moet RF-forwarding voor bridge flood packets aan staan:

```text
set bridge.enabled on
set bridge.rf on
```

De roomserver bewaart zijn identiteit en recente posts standaard in `python_room_server_state.json`. Bewaar dat bestand, of gebruik een vast `--state <pad>` zoals hierboven, als clients dezelfde room na een restart moeten blijven herkennen. Optionele scoped flood traffic kan met `--scope <regionaam>` wanneer de repeaters bijpassende regio-forwarding gebruiken.

### 9. Veiligere power saving voor repeaters

Power saving voor repeaters is nu duidelijker en beter te controleren.

```text
powersaving
powersaving on
powersaving off
get power.stats
clear power.stats
```

De standaard is `off`. Dat is bewust zo, want veel repeaters zijn vaste relay- of backbone-nodes en moeten niet ineens gaan slapen.

Als je power saving aanzet, slaapt een repeater alleen wanneer er geen uitgaand werk klaarstaat. Bridge/WiFi-modus blokkeert slaap. ESP32-boards worden wakker via LoRa DIO1/timer waar dat ondersteund wordt. nRF52-boards gebruiken event/interrupt sleep.

### 10. Optionele dagelijkse reboot-timer

Repeater-only en TCP bridge repeater builds kunnen optioneel rebooten op basis van uptime. Dit is handig voor onbeheerde repeaters waarbij je bijvoorbeeld één voorspelbare refresh per dag wilt.

De functie staat standaard uit:

```text
set reboot.daily on
set reboot.interval 24
get reboot
```

Het interval stel je in uren in van `1` tot `168`. Wanneer de timer verloopt, wacht de repeater tot de outbound TX queue idle is en reboot daarna het board. RS232 en ESP-NOW bridge builds hebben deze timer niet.

### 11. Nederlandse regio-database

MeshCoreNG heeft nu een compacte Nederlandse regio-database, gegenereerd uit de MeshWiki-lijst met Nederlandse regio's.

De database bevat 2484 Nederlandse plaatsen verdeeld over 12 provincies, met primaire en extra MeshCore regiocodes. De database wordt als statische data in de firmware-flash gecompileerd. Hij wordt dus niet in RAM geladen, gebruikt geen runtime JSON parsing, en gebruikt geen dynamische `String` of `std::vector` opslag.

Hij staat standaard aan via de gedeelde PlatformIO buildflag `WITH_DUTCH_REGION_DB=1`, waardoor normale MeshCoreNG-varianten dezelfde default krijgen. Krappe varianten kunnen hem uitzetten door die flag te overriden.

Dit is handig voor:

- de juiste Nederlandse regiocode opzoeken via de CLI
- companion apps die locatie-gebaseerde regioselectie willen aanbieden
- toekomstige OTA updates, omdat de database bij compile-time opnieuw gegenereerd wordt en in de firmware image zit

Voorbeelden:

```text
regiondb info
regiondb provinces
regiondb find gron
regiondb get 45
```

Alle technische details staan in [docs/dutch_region_db.md](./docs/dutch_region_db.md).
De Nederlandse community heeft ook een praktische tool voor regiocodes op [mesh-up.nl/tools/regiocodes-instellen](https://www.mesh-up.nl/tools/regiocodes-instellen/).

### 11b. Region-profielen voor releases

MeshCoreNG kan bij het bouwen een standaard region-profiel meekrijgen. Dat profiel wordt alleen gebruikt op een verse installatie zonder opgeslagen `/regions2`. Bestaande repeaters met handmatig ingestelde regions worden niet overschreven.

Het protocol, de radio-instellingen en packet-format blijven gelijk. Het verschil zit alleen in de meegeleverde default regions en, bij Nederlandse builds, de Nederlandse lookup-database.

| Profiel | Buildkeuze | Doel |
| --- | --- | --- |
| Nederlands | `REGION_PROFILE=nl` | Nederlandse defaults plus `regiondb` lookup |
| Duits | `REGION_PROFILE=de` | Duitse MeshCore regionnamen, zonder Nederlandse database |
| NL-DE Border | `REGION_PROFILE=border` | Gedeelde scopes voor repeaters rond de Nederlands-Duitse grens |

Voor release-builds:

```sh
FIRMWARE_VERSION=v1.0.0 REGION_PROFILE=nl bash build.sh build-repeater-firmwares
FIRMWARE_VERSION=v1.0.0 REGION_PROFILE=de bash build.sh build-repeater-firmwares
FIRMWARE_VERSION=v1.0.0 REGION_PROFILE=border bash build.sh build-repeater-firmwares
```

De bestandsnamen krijgen een profielsuffix, bijvoorbeeld `-nl`, `-de` of `-nl-de-border`. Zo kun je in de webflasher en GitHub Release duidelijk aangeven welke firmware voor welke regio bedoeld is.

Belangrijk voor samenwerking: regions matchen exact. Daarom bevat het border-profiel bewust zowel Nederlandse scopes zoals `nl`, `nl-gr`, `nl-ov`, `nl-ge`, `nl-nb`, `nl-li` als Duitse scopes zoals `de`, `de-nord`, `de-west`, `de-mitte`, `de-hb`, `de-he`, `de-ni`, `de-nw`, `ostfriesland`, `bremesh`, `emsland`, `bentheim`, `osnabrueck`, `ruhrgebiet`, `rheinland` en `taunus`.

### 12. Regionale mesh filtering

MeshCoreNG ondersteunt ook een praktisch hiërarchisch regio-systeem voor repeaters. Een regio is een naam voor een radioscope, zoals `eu`, `nl`, `nl-nh` of `nl-nh-bov`. Een repeater kan ingesteld worden om alleen de scopes door te sturen die logisch zijn voor zijn locatie en rol.

Dit staat los van de Nederlandse regio-database hierboven. De database helpt je om geldige regiocodes te vinden; de regio-tree bepaalt wat jouw repeater wel of niet doorstuurt.

#### Waarom regio's belangrijk zijn

Zonder regio's werkt een flood mesh heel simpel:

```text
elke repeater hoort verkeer
elke repeater herhaalt verkeer
hetzelfde pakket komt steeds opnieuw voorbij
```

Dat werkt prima in een klein netwerk. In een druk meshnetwerk wordt het duur. Airtime is beperkt, zeker op EU868. Als repeaters in Noord-Holland, Zuid-Holland, Friesland en Limburg allemaal elk lokaal bericht blijven doorsturen, raakt het kanaal vol met verkeer dat voor de meeste luisteraars niet nuttig is.

Met regio's kan verkeer lokaal blijven wanneer dat kan:

- lokale berichten blijven in de lokale mesh
- regionaal verkeer kan nog steeds door een provincie heen
- nationaal of Europees verkeer kan bewust door backbone-repeaters gedragen worden
- drukke stedelijke netwerken krijgen minder dubbele heruitzendingen
- rustige buitengebieden kunnen nog steeds bredere scopes gebruiken wanneer bereik belangrijk is

Het doel is dus niet om het netwerk kleiner te maken. Het doel is dat niet elke repeater elke taak hoeft te doen.

#### Dense mesh scaling

Een dense mesh gaat meestal langzaam slechter werken: eerst worden berichten trager, daarna nemen botsingen toe, en uiteindelijk besteden repeaters meer airtime aan dubbele pakketten dan aan nuttig verkeer. Regionale filtering geeft beheerders een handmatige manier om die druk te verminderen.

Voorbeeld:

| Repeaterrol | Typisch toegestane regio's | Waarom |
| --- | --- | --- |
| Lokale stadsrepeater | alleen lokale regio | Houdt buurtverkeer lokaal |
| Provincie-repeater | lokaal + provincie | Verbindt lokale meshes in de buurt |
| Backbone-repeater | lokaal + provincie + land | Draagt bewust breder verkeer |
| Gateway of hoog punt | land of Europa waar nodig | Verbindt grotere gebieden met een duidelijke rol |

Zo wordt een landelijk meshnetwerk realistischer: niet elke repeater hoeft een nationale backbone te zijn.

#### Voorbeeld van een Nederlandse regio-tree

Voorbeeldhiërarchie:

```text
eu
└── nl
    ├── nl-nh
    │   ├── nl-nh-sbc
    │   └── nl-nh-bov
    └── nl-hhw
```

Betekenis:

| Regio | Betekenis |
| --- | --- |
| `eu` | Europa |
| `nl` | Nederland |
| `nl-nh` | Noord-Holland |
| `nl-hhw` | Heerhugowaard / lokale omgeving |
| `nl-nh-sbc` | Schagen/Bergen/Castricum-achtige lokale regio |
| `nl-nh-bov` | Specifieke lokale regio |

Parent-child regio's vormen de boomstructuur. In de praktijk voeg je eerst brede regio's toe, daarna provincies, daarna lokale gebieden. Een child hangt onder een parent, zodat beheerders en tools kunnen begrijpen welke scope bedoeld is.

Zie dit als scope-inheritance: `nl-nh-bov` is een lokale regio binnen `nl-nh`, die weer binnen `nl` valt, die weer binnen `eu` valt. De boom maakt die relatie duidelijk voor mensen, tools en toekomstige routinglogica. Het forwarding-beleid blijft bewust expliciet: je staat de parent, de child of allebei toe afhankelijk van wat deze repeater moet dragen.

#### Forwarding filters

Doorsturen wordt per regio ingesteld:

| Command | Doel | Voorbeeld |
| --- | --- | --- |
| `region put <naam> [parent]` | Voeg een regio toe en hang hem eventueel onder een parent | `region put nl-nh nl` |
| `region allowf <naam>` | Sta flood forwarding toe voor die regio | `region allowf nl-nh` |
| `region denyf <naam>` | Blokkeer flood forwarding voor die regio | `region denyf eu` |
| `region home <naam>` | Stel de thuisregio van deze node in | `region home nl-nh-bov` |
| `region tree` | Toon de ingestelde boom en flags | `region tree` |
| `region save` | Sla wijzigingen op zodat ze na reboot blijven bestaan | `region save` |

`allowf` betekent dat deze repeater flood packets voor die regio mag doorsturen. `denyf` betekent dat hij flood traffic voor die regio niet moet doorsturen. Dit is de belangrijkste airtime-besparing.

Belangrijk: zet bewust aan welke niveaus je echt wilt dragen. Een lokale repeater die alleen `nl-nh-bov` hoeft te helpen, hoeft alleen die lokale regio toe te staan. Een backbone-repeater die ook `nl` of `eu` moet dragen, krijgt die bredere regio's bewust toegestaan.

#### Home region

De home region is de regio waar deze node bij hoort. Dat helpt beheerders, tools en toekomstige routinglogica om te begrijpen waar de repeater staat.

Voorbeeld:

```text
region home nl-nh-bov
```

Voor een gewone lokale repeater kies je de meest specifieke juiste regio als home region. Voor een backbone-repeater op een hoog punt kies je nog steeds de fysieke lokale regio als home region; daarna sta je apart de bredere regio's toe die hij moet doorsturen.

#### Voorbeeldconfiguratie

Dit voorbeeld maakt een kleine Nederlandse hiërarchie en staat forwarding toe voor elk niveau:

```text
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

Voor een drukke lokale repeater kun je smaller filteren:

```text
region allowf nl-nh-bov
region denyf eu
region denyf nl
region save
```

Die repeater besteedt dan minder airtime aan breed verkeer. Een nabijgelegen backbone-repeater kan de bredere regio's nog steeds dragen.

#### Problemen oplossen

| Probleem | Controleer |
| --- | --- |
| Regio is weg na reboot | Voer `region save` uit na wijzigingen |
| Repeater stuurt te veel verkeer door | Gebruik `region tree` en blokkeer brede regio's die niet nodig zijn |
| Lokaal verkeer komt niet ver genoeg | Controleer of nabijgelegen repeaters dezelfde lokale regio toestaan |
| Backbone-verkeer ontbreekt | Controleer of minstens enkele bewuste backbone-repeaters `nl` of `eu` toestaan |
| Verkeerde parent in de boom | Voer `region put <child> <juiste-parent>` opnieuw uit en sla op |

#### Toekomstige slimme routing

De regio-tree is ook een basis voor slimmere firmware later:

- slimme repeaters die filters aanpassen bij drukte
- regionale routing in plaats van alleen pure flooding
- automatische filtering op basis van gemeten airtime
- GPS-geholpen regio-suggesties
- dicht landelijk meshnetwerk met lokale, provinciale en nationale lagen
- airtime-aware forwarding waarbij backbone-repeaters meer dragen en lokale repeaters rustiger blijven

Voor nu houdt MeshCoreNG dit handmatig en voorspelbaar. Beheerders kunnen vandaag al een nuttige hiërarchie bouwen, en toekomstige firmware kan later van die structuur gebruikmaken.

### 13. Atlas telemetry foundation

Atlas is een telemetry-basis die standaard uit staat. Het is bedoeld voor toekomstige topology-, kaart-, observer- en netwerkgezondheidstools.

Atlas voegt geen internetdienst toe, verandert het normale routinggedrag niet en hoort standaard geen extra flood traffic te veroorzaken. Phase 1 richt zich op compacte structuren en lokale export van informatie die de firmware al heeft.

Handige commando's:

```text
atlas enable on
atlas position on
atlas neighbors on
atlas pathsample 1
atlas export on
get atlas.stats
observer export json
```

`atlas pathsample` accepteert `on`, `off` of een percentage van `0` tot `10`. `observer export json` geeft alleen een JSON-achtige event array terug wanneer zowel Atlas als Atlas export aan staan.

Atlas gebruikt `PAYLOAD_TYPE_ATLAS` (`0x0C`) met subtypes voor position, neighbors, path samples en dense stats. Meer details staan in [docs/atlas.md](./docs/atlas.md), [docs/payloads.md](./docs/payloads.md) en [docs/packet_format.md](./docs/packet_format.md).

De richting is dat firmware nette lokale data exporteert, terwijl externe tools zwaardere integraties doen zoals MQTT, Home Assistant, dashboards, databases en kaarten.

## Wat is bewust nog niet gedaan?

We hebben nog geen automatische “AI mesh” gebouwd.

Nog niet automatisch:

- advert interval aanpassen
- hop limit aanpassen
- relay delay aanpassen
- node roles gebruiken
- routekeuzes maken op link quality
- het packet protocol aanpassen voor zones of regio's

Dat is bewust. Eerst meten, dan pas automatisch sturen.

Als we te snel te veel automatisch maken, kan een sparse netwerk slechter worden of kan gedrag onvoorspelbaar worden. MeshCoreNG kiest daarom voor kleine veilige stappen.

## Waarom is dit nuttig?

In makkelijke taal:

MeshCoreNG probeert minder te roepen als iedereen elkaar al hoort.

In een rustig gebied wil je juist dat berichten goed ver komen. In een drukke stad wil je niet dat elke repeater elk bericht steeds opnieuw rondstuurt.

De nieuwe dense stats laten zien hoe druk het netwerk is. De nieuwe instellingen geven ons controle om dat gedrag voorzichtig te tunen.

## Handige repeater commands

```text
get dense.stats
clear dense.stats

get flood.advert.base
set flood.advert.base 0
set flood.advert.base 0.308
set flood.advert.base 1

get flood.relay.prob
set flood.relay.prob 0
set flood.relay.prob 128
set flood.relay.prob 255

get flood.dynamic.enable
set flood.dynamic.enable on
set flood.dynamic.enable off

get radio.fem.rxgain
set radio.fem.rxgain on
set radio.fem.rxgain off
```

`radio.fem.rxgain` is voor boards met een aanstuurbare externe FEM/LNA RX-route, zoals Heltec V4.3. Dit staat los van `radio.rxgain`, dat de interne boosted RX gain van de radiochip regelt.

**Internetbrug (TCP):**

```text
set wifi.ssid     <netwerknaam>
set wifi.password <wachtwoord>
set bridge.server <hostnaam of IP>
set bridge.port   4200
set bridge.password <bridge wachtwoord>
set ntp.enabled on
set ntp.server nl.pool.ntp.org
set ntp.interval 3600
set bridge.enabled on
set bridge.rf on
set bridge.profile island
get bridge.export
get bridge.tcp.ttl
get bridge.type
get bridge.status
get node.info
```

**Dagelijkse reboot-timer:**

```text
set reboot.daily on
set reboot.interval 24
get reboot
```

**Nederlandse regio-database:**

```text
regiondb info
regiondb provinces
regiondb find <prefix>
regiondb get <index>
regiondb code <code_id>
```

**Regionale mesh filtering:**

```text
region put <naam> [parent]
region allowf <naam>
region denyf <naam>
region home <naam>
region tree
region save
```

**Atlas telemetry:**

```text
atlas enable on
atlas export on
get atlas.stats
observer export json
```

**Malformed chat afhandeling:**

Companion radio firmware valideert menselijke chat voordat die naar apps of displays gaat. Ongeldige UTF-8, binary-achtige tekst, te veel control characters, replacement characters, onmogelijke timestamps en tekst met een heel lage confidence score worden bij de chat/UI-laag gefilterd. Binary datagrams, raw/custom packets, requests, responses en toekomstige packet types blijven binary-safe.

Standaard wordt malformed companion chat als compacte placeholder getoond, zodat rommeltekst niet in de Android/app kant gerenderd wordt. Payloads die niet geïnspecteerd kunnen worden, binary channel datagrams en onbekende/toekomstige packet types worden niet blind gedropt.

Repeater firmware kan ook ingesteld worden om malformed default-public-channel group text te droppen voordat het opnieuw wordt uitgezonden:

```text
get malformed.drop
set malformed.drop on
set malformed.drop off
```

Dit staat standaard aan op repeaters. Repeaters droppen alleen tekstpackets die ze kunnen inspecteren en als malformed kunnen classificeren. Encrypted/private group text die de repeater niet kan decrypten, binary datagrams en onbekende/toekomstige packet types blijven volgens de normale forwardingregels lopen.

Meer CLI-uitleg staat in [docs/cli_commands.md](./docs/cli_commands.md).

## Compatibiliteit

MeshCoreNG blijft compatible met het bestaande MeshCore ecosysteem.

- Geen packet format wijziging voor deze dense-mesh stappen.
- Chat-sanitatie geldt alleen voor menselijke chatweergave/forwarding policy; binary transport blijft ondersteund.
- Bestaande MeshCore clients blijven werken.
- Bestaande MeshCore firmware kan nog steeds met MeshCoreNG praten.
- De standaardinstellingen blijven veilig voor normale en sparse netwerken.

## Hoe begin je?

- Flash MeshCoreNG repeater firmware op een ondersteund device.
- Gebruik een bestaande MeshCore client om te verbinden.
- Gebruik de CLI om dense stats te bekijken.
- Begin veilig met standaardwaarden.

Voor developers:

- Installeer [PlatformIO](https://docs.platformio.org) in [Visual Studio Code](https://code.visualstudio.com).
- Clone en open deze MeshCoreNG repository.
- Kijk naar de voorbeelden:
  - [Companion Radio](./examples/companion_radio)
  - [KISS Modem](./examples/kiss_modem)
  - [Simple Repeater](./examples/simple_repeater)
  - [Simple Room Server](./examples/simple_room_server)
  - [Simple Secure Chat](./examples/simple_secure_chat)
  - [Simple Sensor](./examples/simple_sensor)

## MeshCoreNG webflasher

MeshCoreNG heeft nu een GitHub Pages webflasher voor ondersteunde release-builds:

- MeshCoreNG webflasher: https://michtronics.github.io/MeshCoreNG/flasher/
- MeshCoreNG website en docs: https://michtronics.github.io/MeshCoreNG/

De flasher werkt vanuit Chrome of Edge met Web Serial. ESP32-family boards flashen vanuit merged `.bin` bestanden, en nRF52 boards flashen vanuit serial DFU `.zip` bestanden wanneer die assets gepubliceerd zijn. RP2040 en STM32 boards gebruiken nog steeds hun normale firmwarebestanden en flashing tools.

Huidig gedrag per firmwaretype:

| Device family | Release asset | Flasher-gedrag |
| --- | --- | --- |
| ESP32 | merged `.bin` | Direct flashen via Web Serial. |
| nRF52 | serial DFU `.zip` | Serial DFU flashing wanneer bootloader en asset dat ondersteunen. |
| RP2040 | `.uf2` of release download | Download-only totdat er eventueel een browser-flow komt. |
| STM32/Wio-E5 | `.bin`, `.hex` of release download | Download-only; gebruik normale vendor- of DFU-workflow. |
| Andere download targets | release asset | Download-only met board-specifieke instructies. |

`Download` in `website/public/flasher/boards.json` betekent dat de firmware via de flasherpagina zichtbaar en downloadbaar is, maar dat het board niet via dezelfde Web Serial flow geflasht wordt.

ESP32 repeater builds die je via deze site flasht hebben malformed public chat dropping standaard aan. Controleer of wijzig dit na het flashen met `get malformed.drop`, `set malformed.drop on` of `set malformed.drop off`.

De firmwarebestanden die de webflasher gebruikt komen uit GitHub Release assets. De release/CI workflow bouwt de firmwarevarianten en hangt de firmwarebestanden aan de release. De GitHub Pages workflow spiegelt de flashbare assets onder `/flasher/firmware/`, omdat browsers GitHub Release asset-bytes niet direct met `fetch()` kunnen ophalen door CORS.

Release tag build-patronen:

| Tag patroon | Wat het bouwt |
|---|---|
| `repeater-*` | Alle `_repeater` varianten. |
| `companion-*` | Alle `_companion_radio_ble` en `_companion_radio_usb` varianten. |
| `room-server-*` | Alle `_room_server` varianten. |
| `bridge-tcp-*` | Alle `_repeater_bridge_tcp` varianten. |
| `bridge-rs232-*` | Alle `_repeater_bridge_rs232` varianten. |
| `bridge-ble-*` | Alle `_repeater_bridge_ble` varianten. |
| `bridge-tcp-ble-*` | Alle `_repeater_bridge_tcp_ble` varianten. |

Wil je later nog een board toevoegen aan de webflasher, dan voeg je de PlatformIO environment name, display name, chip family en beschrijving toe aan `website/public/flasher/boards.json`. ESP32 release-assets moeten een naam hebben zoals `<env>-*-merged.bin`; nRF52 DFU release-assets moeten een naam hebben zoals `<env>-*.zip`.

Wio Tracker L1 en Wio Tracker L1 E-Ink/L1 Pro firmware entries zijn toegevoegd zodat companion-, repeater- en room-server varianten via de flasherpagina gevonden kunnen worden wanneer release assets bestaan. Deze boards zijn nRF52-based: serial DFU `.zip` bestanden kunnen via de webflasher wanneer de bootloader dat ondersteunt; vendor DFU of bootloader recovery blijft board-specifiek.

Wanneer er een nieuwe GitHub Release wordt gepubliceerd, gebruikt de GitHub Pages workflow die release-tag, downloadt hij de firmware assets uit die release, en werkt hij de webflasher bij zodat precies die bestanden gebruikt worden. Bij een normale `main` build of handmatige Pages run gebruikt hij de nieuwste gepubliceerde release.

Meer details staan in [website/docs/flasher.md](./website/docs/flasher.md).

## MeshCore flasher en clients

MeshCoreNG heeft nog geen eigen clients.

Gebruik voorlopig de upstream MeshCore tools en clients:

- MeshCore flasher: https://meshcore.io/flasher
- Web client: https://app.meshcore.nz
- Config tool: https://config.meshcore.io
- MeshCore docs: https://docs.meshcore.io

## Credits

MeshCoreNG bestaat dankzij het werk van de MeshCore community.

- [MeshCore](https://github.com/meshcore-dev/MeshCore) is het originele project, protocol, firmwarebasis en ecosysteem.
- [MeshCore-Evo](https://github.com/mattzzw/MeshCore-Evo) gaf inspiratie voor dense-mesh repeaterverbeteringen en minder flood advert verkeer.

## Richting voor de toekomst

De volgende logische stappen zijn:

- Betere rolling-window statistieken verder verfijnen.
- Link quality per buur meten.
- Node rollen toevoegen, zoals client, relay, backbone en sensor.
- Alleen lage-prioriteit verkeer verminderen bij drukte.
- Later pas automatische tuning aanzetten.
- Nog later voorbereiden op hybride routed + flooded mesh.
- Optionele TLS-versleuteling voor de TCP internetbrug, zodat verkeer over het internet beter beveiligd is.

Het einddoel is een schaalbaarder LoRa MANET netwerk: simpel waar het kan, slimmer waar het nodig is — en met de TCP brug ook bereikbaar waar geen LoRa is.

## License

MeshCoreNG is gebaseerd op MeshCore en wordt verspreid onder de MIT License.
