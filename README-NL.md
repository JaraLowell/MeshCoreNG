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

De firmwarebestanden die de webflasher gebruikt worden door GitHub Actions gebouwd. De workflow bouwt de ESP32 repeater-varianten uit [webflasher/boards.json](./webflasher/boards.json), maakt ESP Web Tools manifests, en publiceert alles naar GitHub Pages onder `/flasher/`.

Wil je later nog een ESP32-board toevoegen aan de webflasher, dan voeg je de PlatformIO environment name, display name, chip family en beschrijving toe aan `webflasher/boards.json`. GitHub bouwt die variant daarna mee in de Pages workflow.

Wanneer er een nieuwe GitHub Release wordt gepubliceerd, bouwt dezelfde GitHub Actions workflow verse firmware met de release-tag als firmwareversie. Daarna wordt de webflasher bijgewerkt zodat hij die nieuw gebouwde releasebestanden gebruikt. Je kunt dezelfde flow ook starten met tags zoals `newrelease-*` of `v*`.

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

Het einddoel is een schaalbaarder LoRa MANET netwerk: simpel waar het kan, slimmer waar het nodig is.

## License

MeshCoreNG is gebaseerd op MeshCore en wordt verspreid onder de MIT License.
