## MeshCoreNG

MeshCoreNG ist eine Next-Gen-Variante von MeshCore.

Kurz gesagt: MeshCore laesst LoRa-Geraete Nachrichten ohne Internet weitergeben. MeshCoreNG baut darauf auf und macht vor allem Repeater besser kontrollierbar, damit groessere und dichtere Netze stabiler bleiben.

Website und Webflasher: https://michtronics.github.io/MeshCoreNG/

Das Ziel ist nicht, MeshCore neu zu bauen. Das Ziel ist, Schritt fuer Schritt Verbesserungen hinzuzufuegen, ohne bestehende Clients oder das bestehende Protokoll kaputt zu machen.

## Warum das fuer Deutschland wichtig ist

Deutschland hat sehr unterschiedliche Mesh-Situationen: grosse Staedte, laendliche Regionen, Mittelgebirge, Ballungsraeume, lange Nord-Sued- und Ost-West-Strecken und viele regionale Communities. Ein einzelner Flood-Mesh-Ansatz kann in ruhigen Gegenden gut funktionieren, aber in dichten Repeatergruppen schnell zu viel Airtime verbrauchen.

Auf EU868 sind Airtime und Duty-Cycle begrenzt. Jede unnoetige Wiederholung kostet echte Kapazitaet. In einer ruhigen Gegend soll ein Packet weit kommen. In einer dichten Stadt oder in einem aktiven Grenzgebiet soll aber nicht jeder Repeater jedes lokale Packet immer wieder ueberall hintragen.

MeshCoreNG versucht genau dieses Problem anzugehen: zuverlaessig in ruhigen Gebieten bleiben, aber in dichten Meshes ruhiger und smarter werden.

## Was wollen wir erreichen?

MeshCore funktioniert gut als einfaches Flood-Mesh-Netzwerk: Eine Nachricht wird von Repeatern weitergetragen. Das ist stark und zuverlaessig, besonders in kleinen oder ruhigen Netzen.

In einem dichten Netz kann Flooding aber auch zu viel Funkverkehr erzeugen. Dann senden viele Repeater dieselbe Nachricht erneut aus. Das kostet Airtime, erhoeht die Kollisionschance und kann ein Netz traeger machen.

MeshCoreNG will das besser machen:

- Weniger unnoetige Wiederholungen.
- Weniger Last auf dem LoRa-Kanal.
- Repeater, die besser messen, was passiert.
- Dichte City-Meshes, die stabiler bleiben.
- Sparse/rurale Meshes, die weiterhin gut weiterleiten.
- Bessere Bridge-Optionen fuer kontrollierte RF-Inseln.
- Firmware einfacher per Browser flashen oder herunterladen.
- Region-aware Tools fuer groessere Deployments.
- Eine Telemetrie-Basis fuer zukuenftige Karten, Dashboards und Observer.
- Kein Bruch mit bestehenden MeshCore-Clients.

## Was haben wir jetzt gemacht?

Wir haben die erste echte Dense-Mesh-Basis zur Repeater-Firmware hinzugefuegt.

### 1. Weniger Flood-Advert-Last

Flood-Adverts sind Netzwerk-Ankuendigungen, die ueber Repeater verteilt werden koennen. In einem dichten Netz koennen sie viel Airtime kosten.

Deshalb hat MeshCoreNG jetzt:

- `flood.advert.base`
- Standardwert `0.308`

Einfach erklaert:

- `0` bedeutet: empfangene Flood-Adverts nicht weiterleiten.
- `0.308` bedeutet: Dense-Mesh-Default, weniger Weiterleitung bei mehr Hops.
- `1` bedeutet: alles wie normal weiterleiten.

Das hilft besonders in dichten Repeater-Netzen, in denen viele Nodes sich bereits gegenseitig hoeren koennen.

### 2. Dense-Mesh-Statistiken

Wir koennen jetzt besser sehen, was ein Repeater tut.

Mit:

```text
get dense.stats
```

siehst du unter anderem:

- empfangene Flood-Adverts
- weitergeleitete Flood-Adverts
- verworfene Flood-Adverts
- doppelt gehoerte Flood-Packets
- ungefaehre RX/TX-Airtime
- CAD/channel-busy Events
- Density-Level
- Congestion-Level

Mit:

```text
clear dense.stats
```

setzt du diese Zaehler zurueck. Die Stats liegen nur im RAM und verschwinden auch nach einem Neustart.

### 3. Manuelle Relay-Wahrscheinlichkeit

Wir haben einen zusaetzlichen Regler hinzugefuegt:

```text
get flood.relay.prob
set flood.relay.prob <0..255>
```

Einfach erklaert:

- `0` bedeutet: Flood-Packets nicht weiter relayn.
- `128` bedeutet: ungefaehr die Haelfte relayn.
- `255` bedeutet: normal alles relayn, was erlaubt ist.

Der Standard ist `255`, damit bestehende Netze gleich weiter funktionieren.

### 4. Vorbereitung fuer dynamische Steuerung

```text
get flood.dynamic.enable
set flood.dynamic.enable on
set flood.dynamic.enable off
```

Wichtig: In dieser Version veraendert Dynamic Mode noch nicht automatisch das Verhalten.

Im Moment ist es vor allem Vorbereitung und Beobachtung. Wir wollen zuerst echte Daten aus echten Netzen sammeln, bevor die Firmware automatisch smartere Entscheidungen trifft.

Standardmaessig ist Dynamic Mode aus.

### 5. Bessere Channel-Busy-Erkennung

Der Repeater nutzt jetzt Hardware CAD/channel scan, wo die Hardware das unterstuetzt. Dadurch kann die Firmware besser sehen, ob der Kanal busy ist, bevor sie selbst sendet.

Das hilft gegen Kollisionen und unnoetiges Senden auf einem belegten LoRa-Kanal.

### 6. Node-basierte Retransmit-Streuung

In dichten Repeatergruppen koennen mehrere Repeater dasselbe Packet gleichzeitig hoeren und fast gleichzeitig erneut senden. MeshCoreNG addiert deshalb einen kleinen stabilen Offset pro Node zum zufaelligen Flood-Retransmit-Delay.

Der Flood-Retransmit-Delay ist jetzt:

```text
zufaellige txdelay-Streuung + stabiler Node-Offset
```

Der stabile Offset kommt aus der Node-Identitaet, die bereits in der Firmware gespeichert ist. Er bleibt ueber Neustarts stabil, erzeugt keinen extra Traffic, aendert weder Protokoll noch Packet-Format und wird nur fuer Flood-Retransmit-Scheduling verwendet. Wenn `txdelay` auf `0` steht, wird der Offset nicht hinzugefuegt. Das alte Zero-Delay-Verhalten bleibt also verfuegbar. Nur der stabile Offset kann auch separat mit `set flood.node.delay off` deaktiviert werden.

Das ist etwas anderes als CAD-Retry-Timing:

- `txdelay` verteilt Repeater, bevor ein Flood-Packet in die TX-Queue kommt.
- Der Node-Offset verhindert, dass Repeater immer wieder im exakt gleichen Rhythmus haengen bleiben.
- CAD-Retry passiert spaeter, nachdem die Radio-Hardware erkennt, dass der Kanal belegt ist. Das aktuelle CAD-Retry-Fenster ist 120-360 ms.

Praktisches Tuning:

| Repeater-Rolle | Empfehlung |
| --- | --- |
| Lokaler / niedriger Repeater | Ein niedrigeres `txdelay` haelt das lokale Mesh schneller. |
| Hoher / Backbone-Repeater | Ein hoeheres `txdelay` gibt lokalen Repeatern zuerst die Chance, lokalen Traffic abzuarbeiten. |
| Sehr dichtes Stadtmesh | `txdelay` eingeschaltet lassen, damit zufaellige Streuung plus Node-Offset gleichzeitige Retransmits reduziert. |

```text
get flood.node.delay
set flood.node.delay on
set flood.node.delay off
```

### 7. Duplicate-Hearing Retransmit Suppression

Dense Meshes profitieren auch davon, Arbeit abzubrechen, die nicht mehr noetig ist. Wenn ein Repeater einen Flood-Retransmit plant und danach genug andere Repeater dasselbe Packet weiterleiten hoert, bevor sein eigener Timer ablaeuft, kann MeshCoreNG diesen geplanten Retransmit unterdruecken.

Einfaches Beispiel:

```text
neues Flood-Packet gehoert
Retransmit geplant
zwei gleiche Forwards von anderen Repeatern gehoert
eigener Retransmit wird abgebrochen
```

Der Standard-Schwellenwert ist vorsichtig: Es muessen zwei duplicate forwards gehoert werden, bevor der Retransmit abgebrochen wird. Wenn keine Duplikate hereinkommen, sendet der Repeater wie gewohnt. Sparse Netze behalten also ihre Reichweite. Lokal erzeugte Packets, direct routing, ACKs, path/control packets und trace/control traffic werden nicht unterdrueckt. Dieses Verhalten kann mit `set flood.dup.suppress off` ausgeschaltet werden.

Das reduziert doppelte Floods, Airtime-Verschwendung und Kollisionswahrscheinlichkeit ohne extra Packets, ohne Synchronisation und ohne Protokollaenderung.

```text
get flood.dup.suppress
set flood.dup.suppress on
set flood.dup.suppress off
```

### 8. Internetbruecke — optionaler Transport fuer getrennte RF-Netze

MeshCoreNG bleibt RF-first. Die Bruecke ist optionaler Transport/Backhaul fuer bestimmte Deployments, kein Ersatz fuer lokale RF-Struktur.

Die Bruecke ist gedacht fuer:
- getrennte geographische MeshCore-RF-Bereiche, die bewusst ausgewaehlten Traffic austauschen sollen
- entfernte RF-Gateways mit kontrolliertem Backhaul
- temporaeren Backhaul bei Tests, Events oder Ausfaellen
- Beobachtung, Messung und Forschung
- private Infrastruktur einer bekannten Gruppe

Die Bruecke ist nicht gedacht als:
- weltweite Flooding-Backbone
- dauerhaftes globales Relay
- unbegrenzte Packet-Replikation
- Umgehung normaler RF-Planung und Segmentierung

Ausgewaehlter Traffic kann optional zwischen getrennten MeshCore-Deployments transportiert werden. Betreiber entscheiden, welcher Bridge-Server, welche Repeater, Regionen und Traffic-Quellen fuer ihr Netz passend sind.

```text
[RF-Insel A] <-> [Bridge-Repeater] <-> [privater/kontrollierter Bridge-Server] <-> [Bridge-Repeater] <-> [RF-Insel B]
```

RF-Lokalitaet bleibt wichtig. Bridge nur, was wirklich benoetigt wird, halte lokalen Traffic lokal, nutze regionale Segmentierung und vermeide Full-Network-Flooding ueber Bridge-Links.

Geplante oder untersuchte Schutzmechanismen fuer Multi-Bridge-Umgebungen sind Path-Fingerprints, leichte Path-Hashes, Bridge-Loop-Erkennung, Duplicate Suppression, TTL/Hop-Controls und Bridge-Scoping.

**Route 1: ESP32-Repeater mit WiFi**

Repeater mit WiFi koennen sich mit einem ausgewaehlten Bridge-Server verbinden.

```text
set wifi.ssid     MeinWLAN
set wifi.password geheim123
set bridge.server server.example.org
set bridge.port   4200
set bridge.password bridgeSecret
set bridge.enabled on
```

Bridge-Repeater leiten Bridge-originated Flood-Traffic standardmaessig nicht erneut ueber LoRa RF weiter. Fuer kontrollierte Deployments, bei denen Bridge-Traffic bewusst in das lokale RF-Mesh eingespeist werden soll, muss das explizit aktiviert werden:

```text
set bridge.rf on
```

Bridge RF-Forwarding laeuft weiterhin ueber den normalen Repeater-Forwarding-Pfad. Regionsregeln, Duplicate Checks, Loop Detection, Hop-Limits, Relay Probability, Retransmit Delay und die normale RF TX Queue bleiben aktiv.

Alle 38 ESP32-Repeater-Varianten haben jetzt eine passende `_bridge_tcp` Firmware. Siehe [docs/cli_commands.md](./docs/cli_commands.md) fuer alle Einstellmoeglichkeiten.

**Bridge-Firmwaretypen**

MeshCoreNG hat mehrere Bridge-Routen:

| Build-Typ | Transport | Typischer Einsatz |
| --- | --- | --- |
| `_bridge_tcp` | ESP32 WiFi TCP-Client | Ein WiFi-faehiger Repeater verbindet direkt zu einem kontrollierten Bridge-Server. |
| `_bridge_rs232` | Serial/UART Bridge | Boards ohne WiFi nutzen ein PC/Raspberry-Pi-Host-Script oder eine direkte drahtgebundene UART-Verbindung zu einem anderen Repeater. |
| `_bridge_espnow` | ESP-NOW | Lokale ESP32-Bridge-Experimente, bei denen WiFi-Infrastruktur nicht der Haupttransport ist. |

Mit `get bridge.type` laesst sich pruefen, welcher Bridge-Modus in der Firmware enthalten ist. Manche Bridge-Builds stellen auch `get bridge.status`, `get node.info` und, wo unterstuetzt, eine kleine HTTP-Statusseite bereit.

**Route 2: Repeater ueber USB oder direkte UART**

Manche Repeater haben kein WiFi, zum Beispiel nRF52-Boards (RAK4631), RP2040-Boards, STM32-Boards oder ESP32-Boards an Standorten ohne WiFi-Abdeckung. Diese Boards koennen einen PC oder Raspberry Pi per USB als Bridge-Transporthost nutzen.

Der Repeater laeuft mit normaler `_bridge_rs232` Firmware und sendet Bridge-Traffic ueber die serielle Schnittstelle. Auf dem angeschlossenen Rechner uebernimmt ein kleines Python-Script die TCP-Verbindung zum ausgewaehlten Bridge-Server.

```text
[LoRa RF Deployment] <--> [Repeater + RS232 Bridge] <--USB--> [PC/RPi + usb_bridge_client.py] <--> [Bridge-Server]
```

Auf dem Repeater (RS232-Bridge-Firmware):

```text
set bridge.enabled on
```

Script auf PC oder Raspberry Pi starten:

```bash
pip install pyserial
python3 tools/usb_bridge_client.py --serial /dev/ttyUSB0 --baud 115200 \
                                    --server server.example.org --port 4200 \
                                    --bridge-password bridgeSecret
```

Unter Windows wird statt `/dev/ttyUSB0` typischerweise `COM3` oder ein anderer COM-Port genutzt. Das Script steht in dieser Repository unter [tools/usb_bridge_client.py](./tools/usb_bridge_client.py).

Dieselbe `_bridge_rs232` Firmware kann auch als direkte drahtgebundene UART-Bridge zwischen zwei Repeatern genutzt werden, ohne WiFi und ohne USB-Host:

```text
Repeater A TX  -> Repeater B RX
Repeater A RX  -> Repeater B TX
Repeater A GND -> Repeater B GND
```

Nur 3.3V TTL-UART-Pegel verwenden. Echte +/-12V-RS232-Signale nicht direkt mit den Board-Pins verbinden.

Beim Seeed SenseCAP Solar nutzt der RS232-Bridge-Build `Serial1` auf `D6`/`D7`:

```text
D6 = TX = GNSS_TX
D7 = RX = GNSS_RX
```

SenseCAP-Solar-Repeater also so verbinden: `D6/TX -> D7/RX`, `D7/RX -> D6/TX` und `GND -> GND`. Diese Pins werden mit der GNSS-UART geteilt, daher kann GNSS/GPS diese UART nicht gleichzeitig nutzen.

Bridge-Server starten, zum Beispiel auf VPS, Raspberry Pi oder normalem PC mit Python 3.7+:

```bash
python3 tools/tcp_bridge_server.py --port 4200
# optionales Zugangspasswort:
python3 tools/tcp_bridge_server.py --port 4200 --password bridgeSecret
```

Das Server-Script steht in dieser Repository unter [tools/tcp_bridge_server.py](./tools/tcp_bridge_server.py). Es hat keine externen Dependencies. WiFi-Repeater und USB-Repeater koennen gleichzeitig mit demselben kontrollierten Bridge-Server verbunden sein.

**Route 3: Python-Roomserver ueber die Bridge**

MeshCoreNG enthaelt auch einen minimalen Python-Roomserver fuer kontrollierte Bridge-Deployments. Er verbindet sich als weiterer Bridge-Client mit dem TCP-Bridge-Server, annonciert sich als MeshCore-Roomserver, akzeptiert Room-Logins, speichert aktuelle Posts, sendet ACKs und pushed noch nicht synchronisierte Posts zurueck an Clients.

```text
[MeshCore Clients ueber LoRa] <--> [Bridge-Repeater] <--> [Bridge-Server] <--> [python_room_server.py]
```

Bridge-Server starten:

```bash
python3 tools/tcp_bridge_server.py --port 4200
```

Python-Roomserver starten:

```bash
pip install cryptography
python3 tools/python_room_server.py --server server.example.org --port 4200 \
  --bridge-password bridgeSecret \
  --name "Python Room" --password geheim \
  --state /home/pi/meshcore/python_room_server_state.json
```

Auf dem Bridge-Repeater muss RF-Forwarding fuer Bridge-Flood-Pakete aktiv sein:

```text
set bridge.enabled on
set bridge.rf on
```

Der Roomserver speichert seine Identitaet und aktuelle Posts standardmaessig in `python_room_server_state.json`. Diese Datei behalten, oder einen festen `--state <pfad>` wie oben verwenden, wenn Clients denselben Room nach einem Neustart wiedererkennen sollen. Optionaler scoped Flood-Traffic ist mit `--scope <regionsname>` moeglich, wenn die Repeater passende Region-Forwarding-Regeln verwenden.

### 9. Sichereres Power Saving fuer Repeater

Power Saving fuer Repeater ist klarer und einfacher zu kontrollieren.

```text
powersaving
powersaving on
powersaving off
get power.stats
clear power.stats
```

Der Default ist `off`. Das ist bewusst so, weil viele Repeater feste Relay- oder Backbone-Nodes sind und nicht ploetzlich schlafen sollen.

Wenn Power Saving aktiviert ist, schlaeft ein Repeater nur, wenn keine ausgehende Arbeit bereitsteht. Bridge/WiFi-Modus blockiert Sleep. ESP32-Boards wachen, wo unterstuetzt, ueber LoRa DIO1 oder Timer auf. nRF52-Boards nutzen Event/Interrupt-Sleep.

### 10. Optionaler taeglicher Reboot-Timer

Repeater-only und TCP-Bridge-Repeater-Builds koennen optional nach Uptime neu starten. Das ist nuetzlich fuer unbeaufsichtigte Repeater, wenn Betreiber zum Beispiel einmal pro Tag einen vorhersehbaren Neustart wollen.

Die Funktion ist standardmaessig aus:

```text
set reboot.daily on
set reboot.interval 24
get reboot
```

Das Intervall wird in Stunden von `1` bis `168` konfiguriert. Wenn der Timer ablaeuft, wartet der Repeater, bis die outbound TX queue idle ist, und startet dann das Board neu. RS232- und ESP-NOW-Bridge-Builds enthalten diesen Timer nicht.

### 11. Niederlaendische Region-Datenbank

MeshCoreNG hat jetzt eine kompakte niederlaendische Region-Datenbank, generiert aus der MeshWiki-Liste niederlaendischer Regionen.

Die Datenbank enthaelt 2484 niederlaendische Orte in 12 Provinzen, mit primaeren und zusaetzlichen MeshCore-Regioncodes. Die Datenbank wird als statische Daten in den Firmware-Flash kompiliert. Sie wird also nicht in RAM geladen, nutzt kein runtime JSON parsing und keine dynamische `String`- oder `std::vector`-Speicherung.

Sie ist standardmaessig ueber die gemeinsame PlatformIO Buildflag `WITH_DUTCH_REGION_DB=1` aktiv, wodurch normale MeshCoreNG-Varianten denselben Default bekommen. Knappe Varianten koennen sie durch Override dieser Flag deaktivieren.

Das ist praktisch fuer:

- den richtigen niederlaendischen Regioncode ueber die CLI suchen
- Companion-Apps, die ortsbasierte Regionsauswahl anbieten wollen
- zukuenftige OTA-Updates, weil die Datenbank bei compile-time neu generiert wird und im Firmware-Image sitzt

Beispiele:

```text
regiondb info
regiondb provinces
regiondb find gron
regiondb get 45
```

Alle technischen Details stehen in [docs/dutch_region_db.md](./docs/dutch_region_db.md).
Die niederlaendische Community hat auch ein praktisches Tool fuer Regioncodes auf [mesh-up.nl/tools/regiocodes-instellen](https://www.mesh-up.nl/tools/regiocodes-instellen/).

### 11b. Region-Profile fuer Releases

MeshCoreNG kann mit unterschiedlichen Region-Profilen gebaut werden. Diese Profile setzen nur die Standard-Regionen auf einer frischen Installation ohne gespeicherte `/regions2` Datei.

Bestehende Repeater-Konfigurationen mit manuell gesetzten Regions werden nicht ueberschrieben.

Das Protokoll, die Radioeinstellungen und das Packet-Format bleiben gleich. Der Unterschied liegt nur in den mitgelieferten Default-Regions und, bei niederlaendischen Builds, in der niederlaendischen Lookup-Datenbank.

| Profil | Build-Option | Zweck |
| --- | --- | --- |
| Niederlande | `REGION_PROFILE=nl` | Niederlaendische Defaults plus `regiondb` Lookup |
| Deutschland | `REGION_PROFILE=de` | Deutsche MeshCore-Regions ohne niederlaendische Datenbank |
| NL-DE Border | `REGION_PROFILE=border` | Gemeinsame Scopes fuer Grenzregionen |

Fuer Release-Builds:

```sh
FIRMWARE_VERSION=v1.0.0 REGION_PROFILE=nl bash build.sh build-repeater-firmwares
FIRMWARE_VERSION=v1.0.0 REGION_PROFILE=de bash build.sh build-repeater-firmwares
FIRMWARE_VERSION=v1.0.0 REGION_PROFILE=border bash build.sh build-repeater-firmwares
```

Die Dateinamen bekommen ein Profil-Suffix, zum Beispiel `-nl`, `-de` oder `-nl-de-border`. So kann im Webflasher und in GitHub Releases klar gezeigt werden, welche Firmware fuer welche Region gedacht ist.

Wichtig fuer Zusammenarbeit: Regions matchen exakt. Deshalb enthaelt das Border-Profil bewusst sowohl niederlaendische Scopes wie `nl`, `nl-gr`, `nl-ov`, `nl-ge`, `nl-nb`, `nl-li` als auch deutsche Scopes wie `de`, `de-nord`, `de-west`, `de-mitte`, `de-hb`, `de-he`, `de-ni`, `de-nw`, `ostfriesland`, `bremesh`, `emsland`, `bentheim`, `osnabrueck`, `ruhrgebiet`, `rheinland` und `taunus`.

#### Deutsches Profil

Das deutsche Profil folgt den auf meshcore-de.fyi dokumentierten Region-Namen. Es enthaelt keine niederlaendische Ortsdatenbank und spart dadurch Flash.

Basis-Scopes:

```text
europe
eu
de
de-nord
de-ost
de-sued
de-west
de-mitte
```

Bundeslaender:

```text
de-bw
de-by
de-be
de-bb
de-hb
de-hh
de-he
de-mv
de-ni
de-nw
de-rp
de-sl
de-sn
de-st
de-sh
de-th
```

Zusaetzliche Community-Scopes im Default-Profil:

```text
ostfriesland
bremesh
emsland
bentheim
osnabrueck
ruhrgebiet
rheinland
rhein-main
taunus
```

Quellen:

- https://meshcore-de.fyi/meshcore:allgemeines:regions:definieren
- https://meshcore-de.fyi/meshcore:allgemeines:regions:basis
- https://meshcore-de.fyi/meshcore:allgemeines:regions:reale-regions-in-repeatern

#### NL-DE Border Profil

Das Border-Profil ist fuer Repeater nahe der niederlaendisch-deutschen Grenze gedacht. Es kombiniert bewusst deutsche und niederlaendische Scopes, damit beide Communities sauber zusammenarbeiten koennen.

Enthaltene Grenz-Scopes:

```text
europe
eu
nl
de
de-west
de-nord
de-mitte
de-hb
de-he
de-ni
de-nw
ostfriesland
bremesh
emsland
bentheim
osnabrueck
ruhrgebiet
rheinland
taunus
nl-gr
nl-dr
nl-ov
nl-ge
nl-nb
nl-li
```

Wichtig: Region-Namen matchen exakt. `eu` und `europe` sind verschiedene Scopes. Das Border-Profil enthaelt beide Namen, damit niederlaendische und deutsche Setups leichter zusammenarbeiten.

### 12. Regionale Mesh-Filterung

MeshCoreNG unterstuetzt auch ein praktisches hierarchisches Region-System fuer Repeater. Eine Region ist ein Name fuer einen Radio-Scope, zum Beispiel `eu`, `de`, `de-nw` oder `ruhrgebiet`. Ein Repeater kann so eingestellt werden, dass er nur die Scopes weiterleitet, die fuer seinen Standort und seine Rolle logisch sind.

Das steht getrennt von der niederlaendischen Region-Datenbank oben. Die Datenbank hilft bei der Auswahl gueltiger Regionscodes; der Region-Tree bestimmt, was dein Repeater weiterleitet oder nicht.

#### Warum Regionen wichtig sind

Ohne Region-Filterung sieht ein Flood-Mesh grob so aus:

```text
Jeder Repeater hoert Traffic
Jeder Repeater wiederholt Traffic
Traffic breitet sich aus, bis Hop-Limit oder Reichweite endet
```

Das funktioniert in kleinen Netzen gut. In einem dichten Mesh wird es teuer. Airtime ist begrenzt, besonders auf EU868. Wenn Repeater in mehreren Staedten, Bundeslaendern oder Grenzregionen alle jedes lokale Packet weitertragen, wird der Kanal mit Traffic gefuellt, der fuer viele Empfaenger nicht nuetzlich ist.

Mit Regionen kann ein Betreiber sagen:

- lokaler Traffic bleibt lokal
- regionaler Traffic kann weiter laufen
- nationaler oder europaeischer Traffic kann bewusst ueber Backbone-Repeater getragen werden
- kleine lokale Repeater muessen nicht alles tragen

Das Ziel ist also nicht, das Netz kleiner zu machen. Das Ziel ist, dass nicht jeder Repeater jede Aufgabe machen muss.

#### Dense Mesh Scaling

Ein dichtes Mesh wird meistens schrittweise schlechter: erst werden Nachrichten langsamer, dann steigen Kollisionen, und irgendwann verbringen Repeater mehr Airtime mit doppelten Packets als mit nuetzlichem Traffic. Regionale Filterung gibt Betreibern ein manuelles Werkzeug, um diese Last zu reduzieren.

Beispiele:

| Repeater-Rolle | Typische Regions |
| --- | --- |
| Lokaler Stadt-Repeater | nur lokale Region |
| Bundesland-/Regional-Repeater | lokal + Region/Bundesland |
| Backbone-Repeater | lokal + Region/Bundesland + Land |
| Grenz-Repeater | bewusst ausgewaehlte Scopes beider Seiten |

So wird ein groesseres Mesh realisitischer: nicht jeder Repeater muss ein nationaler Backbone sein.

#### Beispiel fuer eine Region-Tree

Ein einfacher deutscher Tree koennte so aussehen:

```text
eu
└── de
    └── de-west
        └── de-nw
            └── ruhrgebiet
```

Ein Border-Tree koennte so aussehen:

```text
eu
├── nl
│   ├── nl-ov
│   └── nl-ge
└── de
    └── de-nord
        └── de-ni
            └── ostfriesland
```

Sieh das als Scope-Inheritance: `ruhrgebiet` ist eine lokale Region innerhalb von `de-nw`, die in `de-west` liegt, die wieder unter `de` liegt. Der Tree macht diese Beziehung fuer Menschen, Tools und zukuenftige Routinglogik sichtbar. Die Forwarding-Policy bleibt bewusst explizit: Du erlaubst Parent, Child oder beide, je nachdem, was dieser Repeater tragen soll.

#### Forwarding-Filter

Die wichtigsten Commands:

| Command | Bedeutung | Beispiel |
| --- | --- | --- |
| `region put <name> [parent]` | Region in den lokalen Tree eintragen | `region put ruhrgebiet de-nw` |
| `region allowf <name>` | Flood-Forwarding fuer Region erlauben | `region allowf ruhrgebiet` |
| `region denyf <name>` | Flood-Forwarding fuer Region blockieren | `region denyf eu` |
| `region home <name>` | Home-Region dieses Repeaters setzen | `region home ruhrgebiet` |
| `region tree` | Tree und Regeln anzeigen | `region tree` |
| `region save` | Aenderungen nach Reboot behalten | `region save` |

`allowf` bedeutet, dass dieser Repeater Flood-Packets fuer diese Region weiterleiten darf. `denyf` bedeutet, dass er Flood-Traffic fuer diese Region nicht weiterleiten soll. Das ist die wichtigste Airtime-Ersparnis.

Wichtig: Erlaube bewusst nur die Ebenen, die du wirklich tragen willst. Ein lokaler Repeater, der nur `ruhrgebiet` helfen soll, muss nicht automatisch `de`, `eu` oder andere breite Scopes weitertragen. Ein Backbone-Repeater kann diese breiteren Scopes bewusst erlauben.

#### Home Region

Die Home-Region ist die Region, zu der diese Node gehoert. Das hilft Betreibern, Tools und zukuenftiger Routinglogik zu verstehen, wo der Repeater steht.

Beispiel:

```text
region home ruhrgebiet
```

Fuer einen normalen lokalen Repeater waehlt man die spezifischste passende Region als Home-Region. Fuer einen Backbone- oder Hochpunkt-Repeater waehlt man trotzdem die physisch lokale Region als Home-Region; danach erlaubt man separat die breiteren Scopes, die er tragen soll.

#### Beispielkonfiguration

Fuer einen lokalen NRW-Repeater:

```text
region put eu
region put de eu
region put de-west de
region put de-nw de-west
region put ruhrgebiet de-nw

region allowf ruhrgebiet
region home ruhrgebiet
region save
```

Fuer einen staerkeren Regional-/Backbone-Repeater:

```text
region put eu
region put de eu
region put de-west de
region put de-nw de-west
region put ruhrgebiet de-nw

region allowf ruhrgebiet
region allowf de-nw
region allowf de-west
region denyf eu

region home ruhrgebiet
region save
```

Dieser Repeater traegt dann lokale und regionale westdeutsche Scopes, aber nicht automatisch jeden europaeischen Scope.

Fuer einen sehr lokalen Repeater kannst du enger filtern:

```text
region allowf ruhrgebiet
region denyf de
region denyf eu
region save
```

Dieser Repeater verbringt dann weniger Airtime mit breitem Traffic. Ein naher Backbone-Repeater kann die breiteren Scopes weiterhin tragen.

#### Probleme loesen

| Problem | Pruefen |
| --- | --- |
| Region ist nach Reboot weg | Nach Aenderungen `region save` ausfuehren |
| Region wird nicht angezeigt | `region tree` pruefen |
| Traffic kommt nicht weit genug | Pruefen, ob nahe Repeater dieselbe lokale Region erlauben |
| Backbone-Traffic fehlt | Pruefen, ob einige bewusste Backbone-Repeater `de` oder `eu` erlauben |
| Zu viel Airtime | Breite Scopes auf lokalen Repeatern blockieren |

#### Zukuenftiges Smart Routing

Das Region-System ist bewusst einfach und manuell. Es schafft aber eine Grundlage fuer spaetere Verbesserungen:

- smartere Repeater, die Filter bei Last anpassen
- Observer-Tools, die regionale Airtime sichtbar machen
- Atlas-Karten mit Region-Sicht
- Airtime-aware Forwarding, bei dem Backbone-Repeater mehr tragen und lokale Repeater ruhiger bleiben

### 13. Atlas Telemetrie

Atlas ist eine standardmaessig deaktivierte Telemetrie-Basis fuer spaetere Topologie-, Karten-, Observer- und Netzwerkzustands-Tools.

Atlas fuegt keinen Internetdienst hinzu, aendert das normale Routingverhalten nicht und soll standardmaessig keinen zusaetzlichen Flood-Traffic erzeugen. Phase 1 konzentriert sich auf kompakte Strukturen und lokalen Export von Informationen, die die Firmware bereits kennt.

Nuetzliche Kommandos:

```text
atlas enable on
atlas position on
atlas neighbors on
atlas pathsample 1
atlas export on
atlas export status
atlas export test
get atlas.stats
observer export json
```

`atlas pathsample` akzeptiert `on`, `off` oder einen Prozentwert von `0` bis `10`. `observer export json` liefert Observer JSONL v1 nur ueber lokale serielle Ausgabe, wenn Atlas Export aktiviert ist. `atlas export test` erzeugt deterministische Testevents fuer Atlas Ingest.

Atlas nutzt `PAYLOAD_TYPE_ATLAS` (`0x0C`) mit Subtypes fuer Position, Neighbors, Path Samples und Dense Stats. Mehr Details stehen in [docs/atlas.md](./docs/atlas.md), [docs/payloads.md](./docs/payloads.md) und [docs/packet_format.md](./docs/packet_format.md).

Die Richtung ist: Die Firmware exportiert saubere lokale Daten, waehrend externe Tools schwerere Integrationen wie MQTT, Home Assistant, Dashboards, Datenbanken und Karten uebernehmen.

## Was bewusst noch nicht gemacht wurde

Wir haben noch kein automatisches "AI Mesh" gebaut.

Noch nicht automatisch:

- Advert-Intervalle anpassen
- Hop-Limits anpassen
- Relay-Delay anpassen
- Node-Rollen verwenden
- Routing-Entscheidungen nach Link Quality treffen
- das Packet-Protokoll fuer Zonen oder Regionen aendern

Das ist bewusst. Erst messen, dann automatisch steuern.

Wenn zu schnell zu viel automatisiert wird, kann ein duennes Netz schlechter werden oder das Verhalten unvorhersehbar werden. MeshCoreNG waehlt deshalb kleine, sichere Schritte.

## Warum das nuetzlich ist

Einfach gesagt:

MeshCoreNG versucht weniger zu rufen, wenn sich sowieso schon alle hoeren.

In einer ruhigen Gegend sollen Nachrichten weit kommen. In einer dichten Stadt soll aber nicht jeder Repeater jedes Packet immer wieder erneut aussenden.

Die neuen Dense-Stats zeigen, wie belastet das Netz wirkt. Die neuen Einstellungen geben Betreibern Kontrolle, um dieses Verhalten vorsichtig zu tunen.

## Nuetzliche Repeater-Kommandos

```text
get dense.stats
clear dense.stats

get flood.advert.base
set flood.advert.base 0.308

get flood.relay.prob
set flood.relay.prob 255

get flood.dynamic.enable
set flood.dynamic.enable off

get flood.node.delay
set flood.node.delay on

get flood.dup.suppress
set flood.dup.suppress on
```

Power Saving:

```text
powersaving
powersaving on
powersaving off
get power.stats
clear power.stats
```

Internetbruecke:

```text
set wifi.ssid     <netzwerkname>
set wifi.password <passwort>
set bridge.server <hostname oder IP>
set bridge.port   4200
set bridge.password <bridge passwort>
set bridge.enabled on
set bridge.rf on
get bridge.type
get bridge.status
get node.info
```

Taeglicher Reboot-Timer:

```text
set reboot.daily on
set reboot.interval 24
get reboot
```

Regionen:

```text
region tree
region list allowed
region list denied
region put <name> [parent]
region allowf <name>
region denyf <name>
region home <name>
region default <name>
region save
```

Atlas Telemetrie:

```text
atlas enable on
atlas export on
get atlas.stats
observer export json
```

Malformed Chat Handling:

Companion-Radio-Firmware validiert menschliche Chattexte, bevor sie an Apps oder Displays weitergegeben werden. Ungueltige UTF-8-Daten, binary-aehnlicher Text, zu viele Control Characters, unmoegliche Timestamps und sehr niedrige Confidence Scores werden in der Chat/UI-Schicht gefiltert. Binary Datagrams, Raw/Custom Packets, Requests, Responses und zukuenftige Packet-Typen bleiben binary-safe.

Standardmaessig wird malformed companion chat als kompakter Platzhalter angezeigt, damit Datenmuell nicht in Android/App-Seite gerendert wird. Payloads, die nicht inspiziert werden koennen, binary channel datagrams und unbekannte oder zukuenftige Packet-Typen werden nicht blind gedroppt.

Repeater-Firmware kann malformed default-public-channel group text droppen, bevor er erneut gesendet wird:

```text
get malformed.drop
set malformed.drop on
set malformed.drop off
```

Das ist auf Repeatern standardmaessig aktiviert. Repeater droppen nur Textpackets, die sie inspizieren und als malformed klassifizieren koennen. Encrypted/private group text, den der Repeater nicht decrypten kann, binary datagrams und unbekannte oder zukuenftige Packet-Typen werden weiterhin nach den normalen Forwarding-Regeln behandelt.

Mehr CLI-Erklaerung steht in [docs/cli_commands.md](./docs/cli_commands.md).

## MeshCoreNG Webflasher

MeshCoreNG hat einen GitHub Pages Webflasher:

- https://michtronics.github.io/MeshCoreNG/flasher/
- https://michtronics.github.io/MeshCoreNG/

Der Webflasher nutzt Chrome oder Edge mit Web Serial. ESP32-Family Boards werden mit merged `.bin` Dateien geflasht. nRF52 Boards nutzen DFU `.zip` Dateien, wenn diese als Release-Assets vorhanden sind.

RP2040- und STM32-Boards nutzen weiterhin ihre normalen Firmware-Dateien und Flashing-Tools.

Aktuelles Verhalten nach Firmware-Asset-Typ:

| Device-Family | Release-Asset | Flasher-Verhalten |
| --- | --- | --- |
| ESP32 | merged `.bin` | Direktes Flashen ueber Web Serial. |
| nRF52 | serial DFU `.zip` | Serial DFU, wenn Bootloader und Asset das unterstuetzen. |
| RP2040 | `.uf2` oder Release-Download | Download-only, bis ein zukuenftiger Browser-Flow ergaenzt wird. |
| STM32/Wio-E5 | `.bin`, `.hex` oder Release-Download | Download-only; normale Vendor- oder DFU-Workflows nutzen. |
| Andere Download-Targets | Release-Asset | Download-only mit board-spezifischen Hinweisen. |

`Download` in `website/public/flasher/boards.json` bedeutet, dass die Firmware auf der Flasher-Seite sichtbar und herunterladbar ist, aber nicht ueber denselben Web-Serial-Flow geflasht wird.

ESP32-Repeater-Builds, die ueber diese Seite geflasht werden, haben malformed public chat dropping standardmaessig aktiviert. Pruefen oder aendern geht nach dem Flashen mit `get malformed.drop`, `set malformed.drop on` oder `set malformed.drop off`.

Die Firmware-Dateien kommen aus GitHub Release Assets. Der Release/CI-Workflow baut die Firmware-Varianten und haengt die Firmware-Dateien an die Release. Der GitHub Pages Workflow spiegelt flashbare Assets unter `/flasher/firmware/`, damit Browser sie ohne GitHub-Release-CORS-Probleme laden koennen.

Wenn spaeter ein weiteres Board zum Webflasher hinzugefuegt werden soll, muessen PlatformIO Environment Name, Display Name, Chip-Family und Beschreibung in `website/public/flasher/boards.json` ergaenzt werden. ESP32 Release-Assets brauchen Namen wie `<env>-*-merged.bin`; nRF52 DFU Release-Assets brauchen Namen wie `<env>-*.zip`.

Wio Tracker L1 und Wio Tracker L1 E-Ink/L1 Pro Firmware-Eintraege sind enthalten, damit Companion-, Repeater- und Room-Server-Varianten auf der Flasher-Seite gefunden werden, wenn Release-Assets existieren. Diese Boards sind nRF52-basiert: serial DFU `.zip` Dateien koennen ueber den Webflasher genutzt werden, wenn der Bootloader diesen Weg unterstuetzt; Vendor-DFU oder Bootloader-Recovery bleiben board-spezifisch.

Wenn eine neue GitHub Release veroeffentlicht wird, nutzt der GitHub Pages Workflow diese Release-Tag, laedt die Firmware-Assets aus dieser Release herunter und aktualisiert den Webflasher so, dass genau diese Dateien verwendet werden. Bei einem normalen `main` Build oder manuellem Pages-Run wird die neueste veroeffentlichte Release genutzt.

Mehr Details stehen in [website/docs/flasher.md](./website/docs/flasher.md).

## Kompatibilitaet

MeshCoreNG bleibt kompatibel mit dem bestehenden MeshCore-Oekosystem.

- Keine Packet-Format-Aenderung fuer die Dense-Mesh-Schritte.
- Chat-Sanitizing gilt nur fuer menschliche Chat-Anzeige und Forwarding-Policy; binary transport bleibt unterstuetzt.
- Bestehende MeshCore-Clients bleiben nutzbar.
- Bestehende MeshCore-Firmware kann weiterhin mit MeshCoreNG sprechen.
- Region-Profile veraendern nur Default-Scopes und Lookup-Daten.
- Standardwerte bleiben vorsichtig, damit duenne Netze nicht ploetzlich schlechter werden.

## Erste Schritte

Fuer Nutzer:

- MeshCoreNG Repeater-Firmware auf ein unterstuetztes Geraet flashen.
- Mit einem bestehenden MeshCore-Client verbinden.
- `get dense.stats` und `region tree` pruefen.
- Region-Scopes bewusst erlauben oder blockieren.

Fuer Entwickler:

- [PlatformIO](https://docs.platformio.org) installieren.
- Repository in [Visual Studio Code](https://code.visualstudio.com) oeffnen.
- Beispiele anschauen:
  - [Companion Radio](./examples/companion_radio)
  - [KISS Modem](./examples/kiss_modem)
  - [Simple Repeater](./examples/simple_repeater)
  - [Simple Room Server](./examples/simple_room_server)
  - [Simple Secure Chat](./examples/simple_secure_chat)
  - [Simple Sensor](./examples/simple_sensor)

## MeshCore Tools und Clients

MeshCoreNG hat noch keine eigenen Clients. Nutze vorerst die upstream MeshCore Tools:

- MeshCore Flasher: https://meshcore.io/flasher
- Web Client: https://app.meshcore.nz
- Config Tool: https://config.meshcore.io
- MeshCore Docs: https://docs.meshcore.io

## Credits

MeshCoreNG basiert auf MeshCore und der Arbeit der MeshCore-Community.

- [MeshCore](https://github.com/meshcore-dev/MeshCore) ist das originale Projekt, Protokoll und Firmware-Oekosystem.
- [MeshCore-Evo](https://github.com/mattzzw/MeshCore-Evo) gab Inspiration fuer Dense-Mesh-Repeaterverbesserungen.

## Richtung fuer die Zukunft

Die naechsten logischen Schritte sind:

- Rolling-Window-Statistiken weiter verfeinern.
- Link Quality pro Nachbar messen.
- Node-Rollen hinzufuegen, zum Beispiel Client, Relay, Backbone und Sensor.
- Nur Low-Priority-Traffic bei Last reduzieren.
- Automatische Tuning-Entscheidungen erst spaeter aktivieren.
- Noch spaeter auf hybrides routed + flooded Mesh vorbereiten.
- Optionale TLS-Verschluesselung fuer die TCP-Internetbruecke ergaenzen, damit Traffic ueber das Internet besser geschuetzt ist.

Das Endziel ist ein skalierbareres LoRa MANET: einfach, wo es einfach bleiben kann, smarter, wo es noetig ist, und mit der TCP-Bruecke auch dort erreichbar, wo kein LoRa vorhanden ist.

## License

MeshCoreNG basiert auf MeshCore und wird unter der MIT License veroeffentlicht.
