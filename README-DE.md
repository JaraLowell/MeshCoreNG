## MeshCoreNG

MeshCoreNG ist eine Next-Gen-Variante von MeshCore.

Kurz gesagt: MeshCore laesst LoRa-Geraete Nachrichten ohne Internet weitergeben. MeshCoreNG baut darauf auf und macht vor allem Repeater besser kontrollierbar, damit groessere und dichtere Netze stabiler bleiben.

Website und Webflasher: https://michtronics.github.io/MeshCoreNG/

Das Ziel ist nicht, MeshCore neu zu bauen oder bestehende Clients zu brechen. Das Ziel ist, vorsichtige Verbesserungen hinzuzufuegen, ohne das bestehende Protokoll oder Packet-Format unnoetig zu veraendern.

## Warum das fuer Deutschland wichtig ist

Deutschland hat sehr unterschiedliche Mesh-Situationen: grosse Staedte, laendliche Regionen, Mittelgebirge, Ballungsraeume, lange Nord-Sued- und Ost-West-Strecken und viele regionale Communities. Ein einzelner Flood-Mesh-Ansatz kann in ruhigen Gegenden gut funktionieren, aber in dichten Repeatergruppen schnell zu viel Airtime verbrauchen.

Auf EU868 sind Airtime und Duty-Cycle begrenzt. Jede unnoetige Wiederholung kostet echte Kapazitaet. In einer ruhigen Gegend soll ein Packet weit kommen. In einer dichten Stadt oder in einem aktiven Grenzgebiet soll aber nicht jeder Repeater jedes lokale Packet immer wieder ueberall hintragen.

MeshCoreNG versucht genau diesen Spagat: zuverlaessig in duennen Netzen, ruhiger und besser messbar in dichten Netzen.

## Ziele

MeshCoreNG soll:

- unnoetige Flood-Wiederholungen reduzieren
- die Last auf dem LoRa-Kanal senken
- Repeater-Zustand besser sichtbar machen
- dichte Stadt- und Regionalnetze stabiler halten
- duenne Netze weiterhin zuverlaessig weiterleiten lassen
- mit bestehenden MeshCore-Clients und MeshCore-Firmware kompatibel bleiben

## Wichtige Funktionen

### 1. Weniger Flood-Advert-Last

Flood-Adverts sind Netzwerk-Ankuendigungen, die ueber Repeater verteilt werden koennen. In dichten Netzen koennen sie viel Airtime verbrauchen.

MeshCoreNG hat dafuer:

```text
get flood.advert.base
set flood.advert.base 0
set flood.advert.base 0.308
set flood.advert.base 1
```

Einfach erklaert:

- `0`: empfangene Flood-Adverts nicht weiterleiten
- `0.308`: Dense-Mesh-Default, weniger Weiterleitung bei mehr Hops
- `1`: alles wie klassisches Flooding weiterleiten

### 2. Dense-Mesh-Statistiken

Mit:

```text
get dense.stats
clear dense.stats
```

kann ein Repeater zeigen, wie dicht und belastet seine Umgebung wirkt. Die Werte sind RAM-only und verschwinden nach einem Neustart.

Typische Informationen:

- empfangene Flood-Adverts
- weitergeleitete Flood-Adverts
- verworfene Flood-Adverts
- doppelt gehoerte Flood-Packets
- ungefaehre RX/TX-Airtime
- Density-Level
- Congestion-Level

### 3. Manuelle Relay-Wahrscheinlichkeit

```text
get flood.relay.prob
set flood.relay.prob <0..255>
```

Beispiele:

- `0`: Flood-Packets nicht weiterleiten
- `128`: ungefaehr die Haelfte weiterleiten
- `255`: alles weiterleiten, was durch die Filter erlaubt ist

Der Default ist `255`, damit bestehende Netze nicht ploetzlich Reichweite verlieren.

### 4. Vorbereitung fuer dynamische Steuerung

```text
get flood.dynamic.enable
set flood.dynamic.enable on
set flood.dynamic.enable off
```

Wichtig: Dynamic Mode veraendert in dieser Version noch nicht automatisch das Verhalten. Er ist Vorbereitung fuer spaetere, vorsichtige automatische Entscheidungen auf Basis echter Messwerte.

### 5. Bessere Channel-Busy-Erkennung

Wo die Hardware es unterstuetzt, nutzt die Firmware CAD/Channel-Scan, bevor sie sendet. Das hilft gegen Kollisionen und unnoetiges Senden auf einem belegten Kanal.

### 6. Node-basierte Retransmit-Streuung

In dichten Repeatergruppen koennen mehrere Repeater dasselbe Packet gleichzeitig hoeren und fast gleichzeitig erneut senden. MeshCoreNG addiert deshalb einen kleinen stabilen Offset pro Node zum zufaelligen Flood-Retransmit-Delay.

```text
zufaellige txdelay-Streuung + stabiler Node-Offset
```

Der Offset kommt aus der Node-Identitaet, bleibt ueber Neustarts stabil, erzeugt keinen extra Traffic und aendert kein Packet-Format. Wenn `txdelay` auf `0` steht, wird der Offset nicht hinzugefuegt.

```text
get flood.node.delay
set flood.node.delay on
set flood.node.delay off
```

### 7. Duplicate-Hearing Retransmit Suppression

Wenn ein Repeater ein Flood-Packet erneut senden will, danach aber genug andere Repeater dasselbe Packet weiterleiten hoert, kann er seine eigene geplante Wiederholung abbrechen.

Einfaches Beispiel:

```text
neues Flood-Packet gehoert
Retransmit geplant
zwei gleiche Forwards von anderen Repeatern gehoert
eigener Retransmit wird abgebrochen
```

Das spart Airtime in dichten Netzen. Wenn keine Duplikate gehoert werden, sendet der Repeater wie gewohnt. Duenne Netze behalten dadurch ihre Reichweite.

```text
get flood.dup.suppress
set flood.dup.suppress on
set flood.dup.suppress off
```

### 8. TCP-Internetbruecke

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

ESP32 TCP-Bridge konfigurieren:

```text
set wifi.ssid     MeinWLAN
set wifi.password geheim123
set bridge.server server.example.org
set bridge.port   4200
set bridge.enabled on
```

Fuer Boards ohne WiFi gibt es RS232/USB-Bridge-Firmware. Auf einem PC oder Raspberry Pi laeuft dann:

```bash
pip install pyserial
python3 tools/usb_bridge_client.py --serial /dev/ttyUSB0 --baud 115200 \
                                    --server server.example.org --port 4200
```

Unter Windows wird statt `/dev/ttyUSB0` typischerweise `COM3` oder ein anderer COM-Port genutzt.

## Region-Profile

MeshCoreNG kann mit unterschiedlichen Region-Profilen gebaut werden. Diese Profile setzen nur die Standard-Regionen auf einer frischen Installation ohne gespeicherte `/regions2` Datei.

Bestehende Repeater-Konfigurationen werden nicht ueberschrieben. Das Funkprotokoll, Packet-Format und die MeshCore-Kompatibilitaet bleiben gleich.

| Profil | Build-Option | Zweck |
| --- | --- | --- |
| Niederlande | `REGION_PROFILE=nl` | Niederlaendische Defaults plus `regiondb` Lookup |
| Deutschland | `REGION_PROFILE=de` | Deutsche MeshCore-Regions ohne niederlaendische Datenbank |
| NL-DE Border | `REGION_PROFILE=border` | Gemeinsame Scopes fuer Grenzregionen |
| Ohne Profil | `REGION_PROFILE=none` | Keine Default-Regionen und keine niederlaendische Datenbank |

## Deutsches Profil

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
ffnw
emsland
bentheim
osnabrueck
ruhrgebiet
rheinland
rhein-main
```

Quellen:

- https://meshcore-de.fyi/meshcore:allgemeines:regions:definieren
- https://meshcore-de.fyi/meshcore:allgemeines:regions:basis
- https://meshcore-de.fyi/meshcore:allgemeines:regions:reale-regions-in-repeatern

## NL-DE Border Profil

Das Border-Profil ist fuer Repeater nahe der niederlaendisch-deutschen Grenze gedacht. Es kombiniert bewusst deutsche und niederlaendische Scopes, damit beide Communities sauber zusammenarbeiten koennen.

Enthaltene Grenz-Scopes:

```text
europe
eu
nl
de
de-west
de-nord
de-ni
de-nw
ffnw
emsland
bentheim
osnabrueck
ruhrgebiet
rheinland
nl-gr
nl-dr
nl-ov
nl-ge
nl-nb
nl-li
```

Wichtig: Region-Namen matchen exakt. `eu` und `europe` sind verschiedene Scopes. Das Border-Profil enthaelt beide Namen, damit niederlaendische und deutsche Setups leichter zusammenarbeiten.

## Regionale Mesh-Filterung

Regionen sind Forwarding-Scopes. Ein Repeater kann entscheiden, welche Scopes er weiterleiten soll.

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

Beispiel fuer einen deutschen Repeater in NRW:

```text
region put europe
region put de europe
region put de-west de
region put de-nw de-west
region put ruhrgebiet de-nw

region allowf de-nw
region allowf ruhrgebiet
region denyf europe

region default de-nw
region home ruhrgebiet
region save
```

Beispiel fuer einen Grenz-Repeater:

```text
region put europe
region put nl europe
region put de europe
region put de-nord de
region put de-ni de-nord
region put ffnw de-nord
region put nl-ov nl
region put nl-ge nl

region allowf de-ni
region allowf ffnw
region allowf nl-ov
region allowf nl-ge
region denyf europe

region default ffnw
region save
```

Ein lokaler Repeater sollte nur die lokalen und regionalen Scopes tragen, die er wirklich braucht. Ein Backbone- oder Hochpunkt-Repeater kann bewusst breitere Scopes erlauben.

## Niederlaendische Region-Datenbank

Builds mit `REGION_PROFILE=nl` und `REGION_PROFILE=border` enthalten die niederlaendische Lookup-Datenbank. Das ist eine statische Flash-Datenbank fuer niederlaendische Orte und Regioncodes. Sie ist nur eine Hilfe zur Auswahl, nicht die aktive Forwarding-Map.

```text
regiondb info
regiondb provinces
regiondb find <prefix>
regiondb get <index>
regiondb code <code_id>
```

Im deutschen Profil ist diese Datenbank deaktiviert:

```text
REGION_PROFILE=de -> WITH_DUTCH_REGION_DB=0
```

## Build und Release

Lokale Beispiele:

```bash
FIRMWARE_VERSION=v1.0.0 REGION_PROFILE=nl bash build.sh build-repeater-firmwares
FIRMWARE_VERSION=v1.0.0 REGION_PROFILE=de bash build.sh build-repeater-firmwares
FIRMWARE_VERSION=v1.0.0 REGION_PROFILE=border bash build.sh build-repeater-firmwares
```

Ein einzelnes Target bauen:

```bash
FIRMWARE_VERSION=v1.0.0 REGION_PROFILE=de bash build.sh build-firmware Generic_E22_sx1262_repeater
```

Die Firmware-Dateinamen bekommen ein Profil-Suffix:

```text
-nl
-de
-nl-de-border
-none
```

In GitHub Actions koennen Repeater- und Bridge-Workflows beim manuellen Start ein Region-Profil auswaehlen. Tag-Releases verwenden ohne Auswahl weiterhin `nl` als Default.

## Webflasher

MeshCoreNG hat einen GitHub Pages Webflasher:

- https://michtronics.github.io/MeshCoreNG/flasher/
- https://michtronics.github.io/MeshCoreNG/

Der Webflasher nutzt Chrome oder Edge mit Web Serial. ESP32-Family Boards werden mit merged `.bin` Dateien geflasht. nRF52 Boards nutzen DFU `.zip` Dateien, wenn diese als Release-Assets vorhanden sind.

Die Firmware-Dateien kommen aus GitHub Release Assets. Die GitHub Pages Workflow spiegelt flashbare Assets unter `/flasher/firmware/`, damit Browser sie ohne GitHub-Release-CORS-Probleme laden koennen.

## Malformed Chat Handling

Companion-Radio-Firmware validiert menschliche Chattexte, bevor sie an Apps oder Displays weitergegeben werden. Ungueltige UTF-8-Daten, binary-aehnlicher Text, zu viele Control Characters, unmoegliche Timestamps und sehr niedrige Confidence Scores werden in der Chat/UI-Schicht gefiltert.

Repeater-Firmware kann malformed default-public-channel group text droppen, bevor er erneut gesendet wird:

```text
get malformed.drop
set malformed.drop on
set malformed.drop off
```

Binary Datagrams, private/encrypted Group Texts, Requests, Responses und unbekannte zukunftige Packet-Typen bleiben binary-safe und werden nicht blind verworfen.

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

Internetbruecke:

```text
set wifi.ssid     <netzwerkname>
set wifi.password <passwort>
set bridge.server <hostname oder IP>
set bridge.port   4200
set bridge.enabled on
get bridge.type
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

## Kompatibilitaet

MeshCoreNG bleibt kompatibel mit dem bestehenden MeshCore-Oekosystem.

- Keine Packet-Format-Aenderung fuer die Dense-Mesh-Schritte.
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

MeshCoreNG wird unter der MIT License veroeffentlicht.
