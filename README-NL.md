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

### 8. Internetbrug — LoRa over grote afstanden zonder LoRa ertussen

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

### 10. Nederlandse regio-database

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

### 10b. Region-profielen voor releases

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

Belangrijk voor samenwerking: regions matchen exact. Daarom bevat het border-profiel bewust zowel Nederlandse scopes zoals `nl`, `nl-gr`, `nl-ov`, `nl-ge`, `nl-nb`, `nl-li` als Duitse scopes zoals `de`, `de-nord`, `de-west`, `de-ni`, `de-nw`, `ffnw`, `emsland`, `bentheim`, `osnabrueck`, `ruhrgebiet` en `rheinland`.

### 11. Regionale mesh filtering

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

**Regionale mesh filtering:**

```text
region put <naam> [parent]
region allowf <naam>
region denyf <naam>
region home <naam>
region tree
region save
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

ESP32 repeater builds die je via deze site flasht hebben malformed public chat dropping standaard aan. Controleer of wijzig dit na het flashen met `get malformed.drop`, `set malformed.drop on` of `set malformed.drop off`.

De firmwarebestanden die de webflasher gebruikt komen uit GitHub Release assets. De release/CI workflow bouwt de firmwarevarianten en hangt de firmwarebestanden aan de release. De GitHub Pages workflow spiegelt de flashbare assets onder `/flasher/firmware/`, omdat browsers GitHub Release asset-bytes niet direct met `fetch()` kunnen ophalen door CORS.

Wil je later nog een board toevoegen aan de webflasher, dan voeg je de PlatformIO environment name, display name, chip family en beschrijving toe aan `website/public/flasher/boards.json`. ESP32 release-assets moeten een naam hebben zoals `<env>-*-merged.bin`; nRF52 DFU release-assets moeten een naam hebben zoals `<env>-*.zip`.

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
