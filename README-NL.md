## MeshCoreNG

MeshCoreNG is een Next Gen variant van MeshCore.

Kort gezegd: MeshCore laat LoRa-apparaten berichten naar elkaar doorgeven zonder internet. MeshCoreNG bouwt daarop verder en probeert vooral repeaters slimmer te maken, zodat grotere en drukkere netwerken beter blijven werken.

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
- Geen breuk met bestaande MeshCore clients.

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

### 6. Internetbrug — LoRa over grote afstanden zonder LoRa ertussen

LoRa is geweldig voor lokale meshnetwerken, maar het heeft een fysieke grens. Als twee groepen gebruikers te ver van elkaar zitten om via LoRa contact te maken — andere steden, andere bergen, ander land — dan zijn ze gewoon eilanden. Ze kunnen elkaar niet bereiken, hoe goed hun repeaters ook werken.

MeshCoreNG heeft daarvoor nu een **TCP internetbrug**. Een ESP32-repeater met WiFi-toegang verbindt zich via internet met een centrale server. Pakketten die hij ontvangt via LoRa stuurt hij door naar alle andere repeaters op die server. Pakketten die van het internet binnenkomen, gooit hij terug in zijn eigen LoRa-mesh.

Het resultaat: twee compleet gescheiden LoRa-netwerken, hoe ver ook van elkaar, kunnen berichten uitwisselen alsof ze één netwerk zijn.

```
[LoRa mesh A]  ←→  [Repeater A + WiFi]  ──internet──  [Repeater B + WiFi]  ←→  [LoRa mesh B]
```

Gebruikers en apps merken er niks van. Ze gebruiken gewoon LoRa zoals altijd. De brug haalt alleen de afstandslimiet weg.

**Route 1: ESP32-repeater met WiFi**

Repeaters met WiFi verbinden zichzelf rechtstreeks via internet met de server.

```text
set wifi.ssid     MijnWiFi
set wifi.password geheim123
set bridge.server mijnserver.example.com
set bridge.port   4200
set bridge.enabled on
```

Alle 38 ESP32-repeater varianten hebben nu een bijbehorende `_bridge_tcp` firmware. Zie [docs/cli_commands.md](./docs/cli_commands.md) voor alle instelmogelijkheden.

**Route 2: Repeater via USB (geen WiFi nodig)**

Sommige repeaters hebben geen WiFi — zoals nRF52-boards (RAK4631), RP2040-boards, STM32-boards en ESP32-boards op locaties zonder WiFi-bereik. Die kunnen toch meedoen via USB.

De repeater draait gewone `_bridge_rs232` firmware en stuurt pakketten via de seriële poort naar een PC of Raspberry Pi. Op die PC draait een klein Python-script dat de verbinding met de TCP-server verzorgt.

```
[LoRa mesh]  ←→  [Repeater + RS232Bridge]  ←USB→  [PC/RPi + usb_bridge_client.py]  ←internet→  [tcp_bridge_server.py]
```

Instellen op de repeater (RS232 bridge firmware):

```text
set bridge.enabled on
```

Script starten op de PC of Raspberry Pi:

```bash
pip install pyserial
python3 tools/usb_bridge_client.py --serial /dev/ttyUSB0 --baud 115200 \
                                    --server mijnserver.example.com --port 4200
```

Op Windows gebruik je `--serial COM3` in plaats van `/dev/ttyUSB0`. Het script staat in deze repository bij [tools/usb_bridge_client.py](./tools/usb_bridge_client.py).

**Server starten** (op een VPS, Raspberry Pi of gewone pc met Python 3.7+):

```bash
python3 tools/tcp_bridge_server.py --port 4200
```

Het serverscript staat in deze repository bij [tools/tcp_bridge_server.py](./tools/tcp_bridge_server.py). Het heeft geen externe dependencies. WiFi-repeaters en USB-repeaters kunnen tegelijk via dezelfde server verbonden zijn.

### 7. Veiligere power saving voor repeaters

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

### 8. Nederlandse regio-database

MeshCoreNG heeft nu een compacte Nederlandse regio-database, gegenereerd uit de MeshWiki-lijst met Nederlandse regio's.

De database bevat 2484 Nederlandse plaatsen verdeeld over 12 provincies, met primaire en extra MeshCore regiocodes. De database wordt als statische data in de firmware-flash gecompileerd. Hij wordt dus niet in RAM geladen, gebruikt geen runtime JSON parsing, en gebruikt geen dynamische `String` of `std::vector` opslag.

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

## Wat is bewust nog niet gedaan?

We hebben nog geen automatische “AI mesh” gebouwd.

Nog niet automatisch:

- advert interval aanpassen
- hop limit aanpassen
- relay delay aanpassen
- node roles gebruiken
- routekeuzes maken op link quality
- zones of regions in het packet protocol toevoegen

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
```

**Internetbrug (TCP):**

```text
set wifi.ssid     <netwerknaam>
set wifi.password <wachtwoord>
set bridge.server <hostnaam of IP>
set bridge.port   4200
set bridge.enabled on
get bridge.type
```

**Nederlandse regio-database:**

```text
regiondb info
regiondb provinces
regiondb find <prefix>
regiondb get <index>
regiondb code <code_id>
```

Meer CLI-uitleg staat in [docs/cli_commands.md](./docs/cli_commands.md).

## Compatibiliteit

MeshCoreNG blijft compatible met het bestaande MeshCore ecosysteem.

- Geen packet format wijziging voor deze dense-mesh stappen.
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

MeshCoreNG heeft nu een GitHub Pages webflasher voor ESP32 repeater builds:

- MeshCoreNG webflasher: https://michtronics.github.io/MeshCoreNG/flasher/

De flasher gebruikt ESP Web Tools en werkt vanuit Chrome of Edge met Web Serial. Hij is bedoeld voor ESP32-family boards. nRF52, RP2040 en STM32 boards gebruiken nog steeds hun normale firmwarebestanden en flashing tools.

De firmwarebestanden die de webflasher gebruikt komen uit GitHub Release assets. De release/CI workflow bouwt de ESP32 repeater-varianten, hangt de merged `.bin` bestanden aan de release, en de GitHub Pages workflow downloadt daarna die releasebestanden om de ESP Web Tools manifests onder `/flasher/` te maken.

Wil je later nog een ESP32-board toevoegen aan de webflasher, dan voeg je de PlatformIO environment name, display name, chip family en beschrijving toe aan `webflasher/boards.json`. De bijbehorende release asset moet een naam hebben zoals `<env>-*-merged.bin`.

Wanneer er een nieuwe GitHub Release wordt gepubliceerd, gebruikt de GitHub Pages workflow die release-tag, downloadt hij de firmware assets uit die release, en werkt hij de webflasher bij zodat precies die bestanden gebruikt worden. Bij een normale `main` build of handmatige Pages run gebruikt hij de nieuwste gepubliceerde release.

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
