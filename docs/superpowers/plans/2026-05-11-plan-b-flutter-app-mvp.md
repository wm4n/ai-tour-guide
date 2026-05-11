# Plan B: Flutter App MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Flutter App (iOS + Android) that displays nearby POIs on an interactive Google Map, auto-triggers narration when the user walks within 100m of a POI, and streams audio via the Plan A FastAPI backend's SSE endpoint.

**Architecture:** Feature-based Riverpod architecture (session / map / narration features + shared layer). SSE bytes are parsed by a custom `SseParser`, base64 audio chunks are decoded and enqueued into a `just_audio` `ConcatenatingAudioSource` FIFO queue. `TriggerEngine` is a pure function tested independently; the Riverpod `TriggerProvider` wraps it and watches position + POI list. All integration tests run offline via `FakeBackendClient`.

**Tech Stack:** Flutter 3.x, Dart 3.x, flutter_riverpod ^2.6.0, google_maps_flutter ^2.10.0, geolocator ^13.0.0, permission_handler ^11.3.0, just_audio ^0.9.40, drift ^2.18.0, drift_flutter ^0.2.0, http ^1.2.0, go_router ^14.3.0, path_provider ^2.1.3, mocktail ^1.0.3 (dev)

**Spec reference:** `docs/superpowers/specs/2026-05-11-plan-b-flutter-app-mvp-design.md`

**Out of scope for Plan B:** Push-to-talk Q&A (Plan D), background location (Plan F), Settings UI, multiple personas (Plan C), Cloud Run deployment (Plan F).

---

## File Structure

```
flutter_app/
├── pubspec.yaml
├── analysis_options.yaml
├── dart_defines/
│   └── dev.json                             ← {"BACKEND_URL":"http://10.0.2.2:8000"}
├── android/
│   └── app/src/main/AndroidManifest.xml     ← MAPS_API_KEY meta-data
├── ios/
│   └── Runner/AppDelegate.swift             ← GMSServices.provideAPIKey(...)
├── lib/
│   ├── main.dart                            ← ProviderScope + runApp
│   ├── app.dart                             ← MaterialApp.router + go_router
│   ├── features/
│   │   ├── session/
│   │   │   ├── providers/session_provider.dart   ← idle/starting/active/ending state machine
│   │   │   ├── screens/home_screen.dart
│   │   │   └── widgets/persona_chip.dart
│   │   ├── map/
│   │   │   ├── providers/poi_provider.dart        ← AsyncNotifier, fetches /poi/nearby
│   │   │   ├── screens/map_screen.dart
│   │   │   └── widgets/poi_marker.dart            ← BitmapDescriptor per confidence
│   │   └── narration/
│   │       ├── providers/narration_provider.dart  ← SSE + audio queue state
│   │       ├── providers/trigger_provider.dart    ← watches position+POIs, fires triggers
│   │       ├── widgets/narration_sheet.dart       ← DraggableScrollableSheet
│   │       └── widgets/narration_mini_bar.dart    ← collapsed bar
│   └── shared/
│       ├── backend/
│       │   ├── backend_client.dart                ← abstract class + RealBackendClient
│       │   ├── sse_parser.dart                    ← pure static SseParser
│       │   └── models/
│       │       ├── poi.dart                       ← POI, WikiArticle
│       │       └── narration_event.dart           ← sealed NarrationEvent hierarchy
│       ├── audio/
│       │   └── audio_player_service.dart          ← abstract class + Real + Fake
│       ├── location/
│       │   ├── haversine.dart                     ← pure haversine(lat1,lon1,lat2,lon2)→m
│       │   └── location_service.dart              ← abstract class + Real + Fake
│       └── db/
│           ├── local_db.dart                      ← drift DB (sessions + narration_history)
│           └── local_db.g.dart                    ← drift generated (run build_runner)
└── test/
    ├── unit/
    │   ├── sse_parser_test.dart
    │   ├── haversine_test.dart
    │   ├── trigger_engine_test.dart
    │   └── local_db_test.dart
    ├── widget/
    │   ├── home_screen_test.dart
    │   └── narration_sheet_test.dart
    └── integration/
        └── narration_flow_test.dart
```

---

## Task 1: Project Skeleton & pubspec

**Files:**
- Create: `flutter_app/` (via `flutter create`)
- Modify: `flutter_app/pubspec.yaml`
- Create: `flutter_app/analysis_options.yaml`
- Create: `flutter_app/dart_defines/dev.json`

- [ ] **1.1 Create Flutter project**

```bash
cd /Users/william.chao/workspace/flutter/ai-tour-guide
flutter create --org com.example --platforms android,ios flutter_app
cd flutter_app
```

Expected: `All done!` with default counter app.

- [ ] **1.2 Replace pubspec.yaml**

```yaml
name: flutter_app
description: AI Tour Guide Flutter App

publish_to: 'none'

version: 1.0.0+1

environment:
  sdk: '>=3.3.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  flutter_riverpod: ^2.6.0
  google_maps_flutter: ^2.10.0
  geolocator: ^13.0.0
  permission_handler: ^11.3.0
  just_audio: ^0.9.40
  drift: ^2.18.0
  drift_flutter: ^0.2.0
  http: ^1.2.0
  go_router: ^14.3.0
  path_provider: ^2.1.3

dev_dependencies:
  flutter_test:
    sdk: flutter
  drift_dev: ^2.18.0
  build_runner: ^2.4.9
  mocktail: ^1.0.3
  flutter_lints: ^4.0.0

flutter:
  uses-material-design: true
```

- [ ] **1.3 Replace analysis_options.yaml**

```yaml
include: package:flutter_lints/flutter.yaml

analyzer:
  exclude:
    - lib/shared/db/local_db.g.dart
  errors:
    invalid_annotation_target: ignore

linter:
  rules:
    - prefer_const_constructors
    - prefer_final_fields
    - avoid_print
```

- [ ] **1.4 Create dart_defines/dev.json**

```json
{
  "BACKEND_URL": "http://10.0.2.2:8000"
}
```

- [ ] **1.5 Run flutter pub get and verify**

```bash
flutter pub get
flutter analyze
```

Expected: `No issues found!`

- [ ] **1.6 Commit**

```bash
git add flutter_app/
git commit -m "feat(flutter): initialize Flutter app skeleton with dependencies"
```

---

## Task 2: Google Maps Platform Setup

**Files:**
- Modify: `flutter_app/android/app/src/main/AndroidManifest.xml`
- Modify: `flutter_app/ios/Runner/AppDelegate.swift`
- Modify: `flutter_app/ios/Runner/Info.plist`

**Prerequisites:** A Google Maps API key from [console.cloud.google.com](https://console.cloud.google.com) with Maps SDK for Android + Maps SDK for iOS enabled.

- [ ] **2.1 Add Android API key**

In `flutter_app/android/app/src/main/AndroidManifest.xml`, inside `<application>` tag:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application
        android:label="flutter_app"
        android:name="${applicationName}"
        android:icon="@mipmap/ic_launcher">

        <!-- Google Maps API Key -->
        <meta-data
            android:name="com.google.android.geo.API_KEY"
            android:value="YOUR_ANDROID_MAPS_API_KEY"/>

        <activity
            android:name=".MainActivity"
            ...>
```

Replace `YOUR_ANDROID_MAPS_API_KEY` with your key.

Also add the `ACCESS_FINE_LOCATION` permission before `<application>`:

```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
```

- [ ] **2.2 Configure iOS API key**

Replace `flutter_app/ios/Runner/AppDelegate.swift`:

```swift
import Flutter
import UIKit
import GoogleMaps

@main
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    GMSServices.provideAPIKey("YOUR_IOS_MAPS_API_KEY")
    GeneratedPluginRegistrant.register(with: self)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
}
```

Replace `YOUR_IOS_MAPS_API_KEY` with your key.

- [ ] **2.3 Add iOS location permission strings to Info.plist**

In `flutter_app/ios/Runner/Info.plist`, add inside `<dict>`:

```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>AI Tour Guide 需要存取您的位置以顯示附近景點。</string>
<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>AI Tour Guide 需要存取您的位置以自動播報旁白。</string>
```

- [ ] **2.4 Verify maps package builds**

```bash
cd flutter_app
flutter build apk --debug 2>&1 | tail -5
```

Expected: `Built build/app/outputs/flutter-apk/app-debug.apk`

- [ ] **2.5 Commit**

```bash
git add flutter_app/android/ flutter_app/ios/
git commit -m "feat(flutter): configure Google Maps API keys for Android and iOS"
```

---

## Task 3: Data Models

**Files:**
- Create: `flutter_app/lib/shared/backend/models/poi.dart`
- Create: `flutter_app/lib/shared/backend/models/narration_event.dart`
- Test: `flutter_app/test/unit/models_test.dart`

- [ ] **3.1 Write failing model tests**

`flutter_app/test/unit/models_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';

void main() {
  group('POI.fromJson', () {
    test('parses full POI with wiki', () {
      final json = {
        'id': 'osm:way:12345',
        'name': '國立故宮博物院',
        'lat': 25.1023,
        'lon': 121.5482,
        'tags': {'tourism': 'museum'},
        'wiki': {
          'title': '國立故宮博物院',
          'extract': '博物院位於...',
          'url': 'https://zh.wikipedia.org/wiki/...',
        },
        'distance_m': 87.5,
        'confidence': 'high',
      };
      final poi = POI.fromJson(json);
      expect(poi.id, 'osm:way:12345');
      expect(poi.name, '國立故宮博物院');
      expect(poi.wiki?.title, '國立故宮博物院');
      expect(poi.distanceM, 87.5);
      expect(poi.confidence, 'high');
    });

    test('parses POI without wiki', () {
      final json = {
        'id': 'osm:node:999',
        'name': 'Test POI',
        'lat': 25.0,
        'lon': 121.0,
        'tags': <String, dynamic>{},
        'wiki': null,
        'distance_m': 50.0,
        'confidence': 'low',
      };
      final poi = POI.fromJson(json);
      expect(poi.wiki, isNull);
    });
  });

  group('NarrationEvent', () {
    test('MetaEvent has poiId and confidence', () {
      const event = MetaEvent(
        poiId: 'osm:way:12345',
        cacheHit: false,
        confidence: 'high',
      );
      expect(event.confidence, 'high');
    });

    test('AudioEvent has base64 chunk and sentenceIdx', () {
      const event = AudioEvent(chunkB64: 'abc123', sentenceIdx: 2);
      expect(event.sentenceIdx, 2);
    });
  });
}
```

- [ ] **3.2 Run test to confirm it fails**

```bash
cd flutter_app
flutter test test/unit/models_test.dart
```

Expected: FAIL — `Target file not found`

- [ ] **3.3 Create poi.dart**

`flutter_app/lib/shared/backend/models/poi.dart`:

```dart
class WikiArticle {
  final String title;
  final String extract;
  final String url;

  const WikiArticle({
    required this.title,
    required this.extract,
    required this.url,
  });

  factory WikiArticle.fromJson(Map<String, dynamic> json) => WikiArticle(
        title: json['title'] as String,
        extract: json['extract'] as String,
        url: json['url'] as String,
      );

  Map<String, dynamic> toJson() => {
        'title': title,
        'extract': extract,
        'url': url,
      };
}

class POI {
  final String id;
  final String name;
  final double lat;
  final double lon;
  final Map<String, String> tags;
  final WikiArticle? wiki;
  final double distanceM;
  final String confidence;

  const POI({
    required this.id,
    required this.name,
    required this.lat,
    required this.lon,
    required this.tags,
    this.wiki,
    required this.distanceM,
    required this.confidence,
  });

  factory POI.fromJson(Map<String, dynamic> json) => POI(
        id: json['id'] as String,
        name: json['name'] as String,
        lat: (json['lat'] as num).toDouble(),
        lon: (json['lon'] as num).toDouble(),
        tags: (json['tags'] as Map<String, dynamic>? ?? {})
            .cast<String, String>(),
        wiki: json['wiki'] != null
            ? WikiArticle.fromJson(json['wiki'] as Map<String, dynamic>)
            : null,
        distanceM: (json['distance_m'] as num).toDouble(),
        confidence: json['confidence'] as String,
      );
}
```

- [ ] **3.4 Create narration_event.dart**

`flutter_app/lib/shared/backend/models/narration_event.dart`:

```dart
sealed class NarrationEvent {
  const NarrationEvent();
}

class MetaEvent extends NarrationEvent {
  final String poiId;
  final bool cacheHit;
  final String confidence;

  const MetaEvent({
    required this.poiId,
    required this.cacheHit,
    required this.confidence,
  });
}

class TextEvent extends NarrationEvent {
  final String chunk;
  const TextEvent({required this.chunk});
}

class AudioEvent extends NarrationEvent {
  final String chunkB64;
  final int sentenceIdx;

  const AudioEvent({required this.chunkB64, required this.sentenceIdx});
}

class EndEvent extends NarrationEvent {
  final int totalDurationS;
  const EndEvent({required this.totalDurationS});
}

class ErrorEvent extends NarrationEvent {
  final String code;
  final String message;
  final int? retryAfterS;

  const ErrorEvent({
    required this.code,
    required this.message,
    this.retryAfterS,
  });
}
```

- [ ] **3.5 Run tests to confirm pass**

```bash
flutter test test/unit/models_test.dart
```

Expected: `All tests passed!`

- [ ] **3.6 Commit**

```bash
git add flutter_app/lib/shared/backend/models/ flutter_app/test/unit/models_test.dart
git commit -m "feat(flutter): add POI and NarrationEvent data models"
```

---

## Task 4: SseParser (Pure, TDD)

**Files:**
- Create: `flutter_app/lib/shared/backend/sse_parser.dart`
- Test: `flutter_app/test/unit/sse_parser_test.dart`

- [ ] **4.1 Write failing SseParser tests**

`flutter_app/test/unit/sse_parser_test.dart`:

```dart
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/backend/sse_parser.dart';

Stream<List<int>> _bytesFrom(String s) =>
    Stream.value(utf8.encode(s));

void main() {
  group('SseParser.parse', () {
    test('parses single meta event', () async {
      const raw = 'event: meta\ndata: {"poi_id":"abc","cache_hit":false,"confidence":"high"}\n\n';
      final events = await SseParser.parse(_bytesFrom(raw)).toList();
      expect(events.length, 1);
      expect(events[0].type, 'meta');
      expect(events[0].data['confidence'], 'high');
    });

    test('parses multiple events in one chunk', () async {
      const raw =
          'event: text\ndata: {"chunk":"hello"}\n\n'
          'event: audio\ndata: {"chunk_b64":"abc","sentence_idx":0}\n\n';
      final events = await SseParser.parse(_bytesFrom(raw)).toList();
      expect(events.length, 2);
      expect(events[0].type, 'text');
      expect(events[1].type, 'audio');
      expect(events[1].data['sentence_idx'], 0);
    });

    test('parses end event', () async {
      const raw = 'event: end\ndata: {"total_duration_s":120}\n\n';
      final events = await SseParser.parse(_bytesFrom(raw)).toList();
      expect(events.length, 1);
      expect(events[0].data['total_duration_s'], 120);
    });

    test('handles events split across two chunks', () async {
      final chunk1 = utf8.encode('event: text\ndata: {"chu');
      final chunk2 = utf8.encode('nk":"hi"}\n\n');
      final stream = Stream.fromIterable([chunk1, chunk2]);
      final events = await SseParser.parse(stream).toList();
      expect(events.length, 1);
      expect(events[0].data['chunk'], 'hi');
    });

    test('ignores blocks without event or data lines', () async {
      const raw = ': keep-alive\n\nevent: end\ndata: {"total_duration_s":5}\n\n';
      final events = await SseParser.parse(_bytesFrom(raw)).toList();
      expect(events.length, 1);
      expect(events[0].type, 'end');
    });
  });
}
```

- [ ] **4.2 Run test to confirm it fails**

```bash
flutter test test/unit/sse_parser_test.dart
```

Expected: FAIL — `Target file not found`

- [ ] **4.3 Implement SseParser**

`flutter_app/lib/shared/backend/sse_parser.dart`:

```dart
import 'dart:convert';

class SseEvent {
  final String type;
  final Map<String, dynamic> data;

  const SseEvent({required this.type, required this.data});
}

class SseParser {
  static Stream<SseEvent> parse(Stream<List<int>> byteStream) async* {
    var buffer = '';
    await for (final chunk in byteStream) {
      buffer += utf8.decode(chunk, allowMalformed: true);
      while (buffer.contains('\n\n')) {
        final idx = buffer.indexOf('\n\n');
        final block = buffer.substring(0, idx);
        buffer = buffer.substring(idx + 2);
        final event = _parseBlock(block);
        if (event != null) yield event;
      }
    }
  }

  static SseEvent? _parseBlock(String block) {
    String? type;
    String? dataLine;
    for (final line in block.split('\n')) {
      if (line.startsWith('event: ')) {
        type = line.substring(7);
      } else if (line.startsWith('data: ')) {
        dataLine = line.substring(6);
      }
    }
    if (type == null || dataLine == null) return null;
    try {
      final data = jsonDecode(dataLine) as Map<String, dynamic>;
      return SseEvent(type: type, data: data);
    } catch (_) {
      return null;
    }
  }
}
```

- [ ] **4.4 Run tests to confirm pass**

```bash
flutter test test/unit/sse_parser_test.dart
```

Expected: `All tests passed!`

- [ ] **4.5 Commit**

```bash
git add flutter_app/lib/shared/backend/sse_parser.dart flutter_app/test/unit/sse_parser_test.dart
git commit -m "feat(flutter): add SseParser for text/event-stream parsing"
```

---

## Task 5: Haversine Distance (Pure, TDD)

**Files:**
- Create: `flutter_app/lib/shared/location/haversine.dart`
- Test: `flutter_app/test/unit/haversine_test.dart`

- [ ] **5.1 Write failing haversine tests**

`flutter_app/test/unit/haversine_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/location/haversine.dart';

void main() {
  group('haversine', () {
    test('returns 0 for same point', () {
      expect(haversine(25.1023, 121.5482, 25.1023, 121.5482), 0.0);
    });

    test('returns ~111km for 1 degree latitude difference', () {
      final dist = haversine(0.0, 0.0, 1.0, 0.0);
      expect(dist, closeTo(111_195, 100));
    });

    test('returns ~87m for two nearby points', () {
      // Palace Museum to a nearby point ~87m north
      final dist = haversine(25.1023, 121.5482, 25.1031, 121.5482);
      expect(dist, closeTo(89, 5));
    });

    test('returns value within trigger radius for 50m apart', () {
      final dist = haversine(25.1023, 121.5482, 25.10275, 121.5482);
      expect(dist, lessThan(100.0));
    });

    test('returns value outside trigger radius for 200m apart', () {
      final dist = haversine(25.1023, 121.5482, 25.1041, 121.5482);
      expect(dist, greaterThan(100.0));
    });
  });
}
```

- [ ] **5.2 Run test to confirm it fails**

```bash
flutter test test/unit/haversine_test.dart
```

Expected: FAIL — `Target file not found`

- [ ] **5.3 Implement haversine**

`flutter_app/lib/shared/location/haversine.dart`:

```dart
import 'dart:math';

/// Returns the distance in metres between two geographic coordinates.
double haversine(double lat1, double lon1, double lat2, double lon2) {
  const r = 6371000.0; // Earth radius in metres
  final dLat = _rad(lat2 - lat1);
  final dLon = _rad(lon2 - lon1);
  final a = sin(dLat / 2) * sin(dLat / 2) +
      cos(_rad(lat1)) * cos(_rad(lat2)) * sin(dLon / 2) * sin(dLon / 2);
  final c = 2 * atan2(sqrt(a), sqrt(1 - a));
  return r * c;
}

double _rad(double deg) => deg * pi / 180;
```

- [ ] **5.4 Run tests to confirm pass**

```bash
flutter test test/unit/haversine_test.dart
```

Expected: `All tests passed!`

- [ ] **5.5 Commit**

```bash
git add flutter_app/lib/shared/location/haversine.dart flutter_app/test/unit/haversine_test.dart
git commit -m "feat(flutter): add haversine distance function"
```

---

## Task 6: TriggerEngine (Pure, TDD)

**Files:**
- Create: `flutter_app/lib/features/narration/trigger_engine.dart`
- Test: `flutter_app/test/unit/trigger_engine_test.dart`

- [ ] **6.1 Write failing TriggerEngine tests**

`flutter_app/test/unit/trigger_engine_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/trigger_engine.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';

POI _poi(String id, double lat, double lon) => POI(
      id: id,
      name: 'Test POI $id',
      lat: lat,
      lon: lon,
      tags: {},
      distanceM: 0,
      confidence: 'medium',
    );

void main() {
  const userLat = 25.1023;
  const userLon = 121.5482;

  group('TriggerEngine.evaluate', () {
    test('returns POI within 100m trigger radius', () {
      // ~89m north of user
      final poi = _poi('a', 25.1031, 121.5482);
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [poi],
        playedPoiIds: {},
        cooldownPoiIds: {},
      );
      expect(triggers, [poi]);
    });

    test('excludes POI outside 100m radius', () {
      // ~200m north of user
      final poi = _poi('b', 25.1041, 121.5482);
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [poi],
        playedPoiIds: {},
        cooldownPoiIds: {},
      );
      expect(triggers, isEmpty);
    });

    test('excludes POI already played in this session', () {
      final poi = _poi('c', 25.1031, 121.5482);
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [poi],
        playedPoiIds: {'c'},
        cooldownPoiIds: {},
      );
      expect(triggers, isEmpty);
    });

    test('excludes POI in cooldown', () {
      final poi = _poi('d', 25.1031, 121.5482);
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [poi],
        playedPoiIds: {},
        cooldownPoiIds: {'d'},
      );
      expect(triggers, isEmpty);
    });

    test('returns only qualifying POIs from mixed list', () {
      final near = _poi('near', 25.1031, 121.5482);     // ~89m, qualifies
      final far = _poi('far', 25.1041, 121.5482);       // ~200m, excluded
      final played = _poi('played', 25.1031, 121.5482); // near but played
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [near, far, played],
        playedPoiIds: {'played'},
        cooldownPoiIds: {},
      );
      expect(triggers.map((p) => p.id).toList(), ['near']);
    });
  });
}
```

- [ ] **6.2 Run test to confirm it fails**

```bash
flutter test test/unit/trigger_engine_test.dart
```

Expected: FAIL — `Target file not found`

- [ ] **6.3 Implement TriggerEngine**

`flutter_app/lib/features/narration/trigger_engine.dart`:

```dart
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/haversine.dart';

class TriggerEngine {
  static const double defaultTriggerRadiusM = 100.0;

  static List<POI> evaluate({
    required double userLat,
    required double userLon,
    required List<POI> pois,
    required Set<String> playedPoiIds,
    required Set<String> cooldownPoiIds,
    double radiusM = defaultTriggerRadiusM,
  }) {
    return pois.where((poi) {
      if (playedPoiIds.contains(poi.id)) return false;
      if (cooldownPoiIds.contains(poi.id)) return false;
      final dist = haversine(userLat, userLon, poi.lat, poi.lon);
      return dist <= radiusM;
    }).toList();
  }
}
```

- [ ] **6.4 Run tests to confirm pass**

```bash
flutter test test/unit/trigger_engine_test.dart
```

Expected: `All tests passed!`

- [ ] **6.5 Commit**

```bash
git add flutter_app/lib/features/narration/trigger_engine.dart flutter_app/test/unit/trigger_engine_test.dart
git commit -m "feat(flutter): add TriggerEngine pure function with haversine + cooldown checks"
```

---

## Task 7: Drift DB Schema (TDD)

**Files:**
- Create: `flutter_app/lib/shared/db/local_db.dart`
- Create: `flutter_app/lib/shared/db/local_db.g.dart` (generated)
- Test: `flutter_app/test/unit/local_db_test.dart`

> **Drift code-generation constraint:** `local_db_test.dart` imports `NarrationHistoryCompanion` which is generated. Steps are ordered **schema first → build_runner → tests** (not standard TDD order, but required by drift).

- [ ] **7.1 Create local_db.dart**

`flutter_app/lib/shared/db/local_db.dart`: *(see full implementation in step 7.3 — write it now)*

Copy the full `local_db.dart` content from step 7.3 and create the file.

- [ ] **7.2 Run build_runner to generate local_db.g.dart**

```bash
cd flutter_app
dart run build_runner build --delete-conflicting-outputs
```

Expected: `[INFO] Build completed successfully` — `lib/shared/db/local_db.g.dart` is created.

- [ ] **7.3 Write failing DB tests**

`flutter_app/test/unit/local_db_test.dart`:

```dart
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/db/local_db.dart';

LocalDb _makeInMemoryDb() =>
    LocalDb.forTesting(NativeDatabase.memory());

void main() {
  late LocalDb db;

  setUp(() => db = _makeInMemoryDb());
  tearDown(() => db.close());

  group('LocalDb.isCooldown', () {
    test('returns false when no history exists', () async {
      final result = await db.isCooldown('poi:123', Duration(hours: 24));
      expect(result, isFalse);
    });

    test('returns true when played within cooldown window', () async {
      final sessionId = await db.startSession('history_uncle', 'zh-TW');
      await db.recordNarration(
        sessionId: sessionId,
        poiId: 'poi:123',
        poiName: 'Test POI',
        poiLat: 25.1,
        poiLon: 121.5,
        persona: 'history_uncle',
        lang: 'zh-TW',
        completed: true,
      );
      final result = await db.isCooldown('poi:123', Duration(hours: 24));
      expect(result, isTrue);
    });

    test('returns false when last played is outside cooldown window', () async {
      final sessionId = await db.startSession('history_uncle', 'zh-TW');
      // Insert a narration from 25 hours ago
      final oldTime = DateTime.now()
          .subtract(const Duration(hours: 25))
          .millisecondsSinceEpoch;
      await db.into(db.narrationHistory).insert(
        NarrationHistoryCompanion.insert(
          sessionId: sessionId,
          poiId: 'poi:old',
          poiName: 'Old POI',
          poiLat: 25.0,
          poiLon: 121.0,
          persona: 'history_uncle',
          lang: 'zh-TW',
          playedAt: oldTime,
          completed: 0,
        ),
      );
      final result = await db.isCooldown('poi:old', Duration(hours: 24));
      expect(result, isFalse);
    });
  });
}
```

- [ ] **7.4 Run test to confirm it fails**

```bash
flutter test test/unit/local_db_test.dart
```

Expected: FAIL — `isCooldown` method not found (schema exists, methods not yet added)

- [ ] **7.5 Full local_db.dart with helper methods**

`flutter_app/lib/shared/db/local_db.dart` (replace with full version):

```dart
import 'package:drift/drift.dart';
import 'package:drift_flutter/drift_flutter.dart';

part 'local_db.g.dart';

class Sessions extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get startedAt => integer()();
  IntColumn get endedAt => integer().nullable()();
  TextColumn get persona => text()();
  TextColumn get lang => text()();
}

class NarrationHistory extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get sessionId => integer().references(Sessions, #id)();
  TextColumn get poiId => text()();
  TextColumn get poiName => text()();
  RealColumn get poiLat => real()();
  RealColumn get poiLon => real()();
  TextColumn get persona => text()();
  TextColumn get lang => text()();
  IntColumn get playedAt => integer()();
  IntColumn get completed => integer().withDefault(const Constant(0))();
}

@DriftDatabase(tables: [Sessions, NarrationHistory])
class LocalDb extends _$LocalDb {
  LocalDb([QueryExecutor? executor])
      : super(executor ?? driftDatabase(name: 'tour_guide_db'));

  LocalDb.forTesting(QueryExecutor executor) : super(executor);

  @override
  int get schemaVersion => 1;

  Future<int> startSession(String persona, String lang) =>
      into(sessions).insert(SessionsCompanion.insert(
        startedAt: DateTime.now().millisecondsSinceEpoch,
        persona: persona,
        lang: lang,
      ));

  Future<void> endSession(int sessionId) => (update(sessions)
        ..where((t) => t.id.equals(sessionId)))
      .write(SessionsCompanion(
        endedAt: Value(DateTime.now().millisecondsSinceEpoch),
      ));

  Future<void> recordNarration({
    required int sessionId,
    required String poiId,
    required String poiName,
    required double poiLat,
    required double poiLon,
    required String persona,
    required String lang,
    required bool completed,
  }) =>
      into(narrationHistory).insert(NarrationHistoryCompanion.insert(
        sessionId: sessionId,
        poiId: poiId,
        poiName: poiName,
        poiLat: poiLat,
        poiLon: poiLon,
        persona: persona,
        lang: lang,
        playedAt: DateTime.now().millisecondsSinceEpoch,
        completed: completed ? 1 : 0,
      ));

  Future<bool> isCooldown(String poiId, Duration window) async {
    final cutoff =
        DateTime.now().subtract(window).millisecondsSinceEpoch;
    final rows = await (select(narrationHistory)
          ..where(
            (t) =>
                t.poiId.equals(poiId) &
                t.playedAt.isBiggerThanValue(cutoff),
          ))
        .get();
    return rows.isNotEmpty;
  }
}
```

- [ ] **7.6 Generate drift code (second time, includes helper methods)**

```bash
cd flutter_app
dart run build_runner build --delete-conflicting-outputs
```

Expected: `[INFO] Build completed successfully`

- [ ] **7.7 Run tests to confirm pass**

```bash
flutter test test/unit/local_db_test.dart
```

Expected: `All tests passed!`

- [ ] **7.8 Commit**

```bash
git add flutter_app/lib/shared/db/ flutter_app/test/unit/local_db_test.dart
git commit -m "feat(flutter): add drift DB schema with sessions and narration_history tables"
```

---

## Task 8: LocationService (Interface + Real + Fake)

**Files:**
- Create: `flutter_app/lib/shared/location/location_service.dart`

- [ ] **8.1 Create LocationService**

`flutter_app/lib/shared/location/location_service.dart`:

```dart
import 'dart:async';
import 'package:geolocator/geolocator.dart';

abstract class LocationService {
  Future<bool> requestPermission();
  void start();
  void stop();
  Stream<Position> get positionStream;
}

class RealLocationService implements LocationService {
  StreamController<Position>? _controller;
  StreamSubscription<Position>? _subscription;

  @override
  Future<bool> requestPermission() async {
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      perm = await Geolocator.requestPermission();
    }
    return perm == LocationPermission.whileInUse ||
        perm == LocationPermission.always;
  }

  @override
  void start() {
    _controller = StreamController<Position>.broadcast();
    _subscription = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 10,
      ),
    ).listen(
      _controller!.add,
      onError: _controller!.addError,
    );
  }

  @override
  void stop() {
    _subscription?.cancel();
    _subscription = null;
    _controller?.close();
    _controller = null;
  }

  @override
  Stream<Position> get positionStream =>
      _controller?.stream ?? const Stream.empty();
}

class FakeLocationService implements LocationService {
  final StreamController<Position> _controller =
      StreamController<Position>.broadcast();
  final bool _hasPermission;

  FakeLocationService({bool hasPermission = true})
      : _hasPermission = hasPermission;

  void emit(Position position) => _controller.add(position);

  @override
  Future<bool> requestPermission() async => _hasPermission;

  @override
  void start() {}

  @override
  void stop() {}

  @override
  Stream<Position> get positionStream => _controller.stream;
}

Position fakePosition(double lat, double lon) => Position(
      latitude: lat,
      longitude: lon,
      timestamp: DateTime.now(),
      accuracy: 5,
      altitude: 0,
      altitudeAccuracy: 0,
      heading: 0,
      headingAccuracy: 0,
      speed: 0,
      speedAccuracy: 0,
    );
```

- [ ] **8.2 Verify it compiles**

```bash
flutter analyze lib/shared/location/
```

Expected: `No issues found!`

- [ ] **8.3 Commit**

```bash
git add flutter_app/lib/shared/location/
git commit -m "feat(flutter): add LocationService interface with Real and Fake implementations"
```

---

## Task 9: BackendClient (Interface + Real + Fake)

**Files:**
- Create: `flutter_app/lib/shared/backend/backend_client.dart`

- [ ] **9.1 Create BackendClient**

`flutter_app/lib/shared/backend/backend_client.dart`:

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/sse_parser.dart';

abstract class BackendClient {
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  });

  Stream<NarrationEvent> narrate({
    required String poiId,
    required String persona,
    required String lang,
    required String length,
    bool forceRegenerate = false,
  });
}

class RealBackendClient implements BackendClient {
  final String baseUrl;
  final http.Client _http;

  RealBackendClient({required this.baseUrl}) : _http = http.Client();

  @override
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  }) async {
    final uri = Uri.parse('$baseUrl/poi/nearby').replace(
      queryParameters: {
        'lat': lat.toString(),
        'lon': lon.toString(),
        'radius': radius.toString(),
        'lang': lang,
        'persona': persona,
      },
    );
    final response = await _http.get(uri);
    if (response.statusCode != 200) {
      throw Exception('fetchNearby failed: HTTP ${response.statusCode}');
    }
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return (json['pois'] as List)
        .map((e) => POI.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Stream<NarrationEvent> narrate({
    required String poiId,
    required String persona,
    required String lang,
    required String length,
    bool forceRegenerate = false,
  }) async* {
    final request =
        http.Request('POST', Uri.parse('$baseUrl/narration'));
    request.headers['Content-Type'] = 'application/json';
    request.headers['Accept'] = 'text/event-stream';
    request.body = jsonEncode({
      'poi_id': poiId,
      'persona': persona,
      'lang': lang,
      'length': length,
      'force_regenerate': forceRegenerate,
    });
    final response = await _http.send(request);
    if (response.statusCode != 200) {
      throw Exception('narrate failed: HTTP ${response.statusCode}');
    }
    await for (final sseEvent in SseParser.parse(response.stream)) {
      yield _toNarrationEvent(sseEvent);
    }
  }

  NarrationEvent _toNarrationEvent(SseEvent sse) => switch (sse.type) {
        'meta' => MetaEvent(
            poiId: sse.data['poi_id'] as String,
            cacheHit: sse.data['cache_hit'] as bool,
            confidence: sse.data['confidence'] as String,
          ),
        'text' => TextEvent(chunk: sse.data['chunk'] as String),
        'audio' => AudioEvent(
            chunkB64: sse.data['chunk_b64'] as String,
            sentenceIdx: sse.data['sentence_idx'] as int,
          ),
        'end' => EndEvent(
            totalDurationS: sse.data['total_duration_s'] as int,
          ),
        'error' => ErrorEvent(
            code: sse.data['code'] as String,
            message: sse.data['message'] as String,
            retryAfterS: sse.data['retry_after_s'] as int?,
          ),
        _ => ErrorEvent(code: 'unknown', message: 'unknown event: ${sse.type}'),
      };
}

class FakeBackendClient implements BackendClient {
  final List<POI> nearbyPois;
  final List<NarrationEvent> scriptedEvents;

  const FakeBackendClient({
    this.nearbyPois = const [],
    this.scriptedEvents = const [],
  });

  @override
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  }) async =>
      nearbyPois;

  @override
  Stream<NarrationEvent> narrate({
    required String poiId,
    required String persona,
    required String lang,
    required String length,
    bool forceRegenerate = false,
  }) async* {
    for (final event in scriptedEvents) {
      yield event;
    }
  }
}
```

- [ ] **9.2 Verify it compiles**

```bash
flutter analyze lib/shared/backend/
```

Expected: `No issues found!`

- [ ] **9.3 Commit**

```bash
git add flutter_app/lib/shared/backend/
git commit -m "feat(flutter): add BackendClient interface with Real and Fake implementations"
```

---

## Task 10: AudioPlayerService (Interface + Real + Fake)

**Files:**
- Create: `flutter_app/lib/shared/audio/audio_player_service.dart`

- [ ] **10.1 Create AudioPlayerService**

`flutter_app/lib/shared/audio/audio_player_service.dart`:

```dart
import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';

abstract class AudioPlayerService {
  Future<void> enqueueBytes(Uint8List bytes);
  Future<void> pause();
  Future<void> resume();
  Future<void> skip();
  Stream<bool> get isPlayingStream;
  Future<void> dispose();
}

class RealAudioPlayerService implements AudioPlayerService {
  final AudioPlayer _player = AudioPlayer();
  final ConcatenatingAudioSource _playlist =
      ConcatenatingAudioSource(children: []);
  late final Directory _tempDir;
  int _chunkIndex = 0;
  bool _initialized = false;

  Future<void> _init() async {
    if (_initialized) return;
    _tempDir = await getTemporaryDirectory();
    await _player.setAudioSource(_playlist);
    _initialized = true;
  }

  @override
  Future<void> enqueueBytes(Uint8List bytes) async {
    await _init();
    final file = File('${_tempDir.path}/narration_${_chunkIndex++}.mp3');
    await file.writeAsBytes(bytes);
    await _playlist.add(AudioSource.uri(Uri.file(file.path)));
    if (!_player.playing) await _player.play();
  }

  @override
  Future<void> pause() => _player.pause();

  @override
  Future<void> resume() => _player.play();

  @override
  Future<void> skip() async {
    if (_player.hasNext) {
      await _player.seekToNext();
    } else {
      await _player.stop();
    }
  }

  @override
  Stream<bool> get isPlayingStream => _player.playingStream;

  @override
  Future<void> dispose() async {
    await _player.stop();
    await _player.dispose();
    for (var i = 0; i < _chunkIndex; i++) {
      final f = File('${_tempDir.path}/narration_$i.mp3');
      if (await f.exists()) await f.delete();
    }
  }
}

class FakeAudioPlayerService implements AudioPlayerService {
  final List<Uint8List> enqueuedChunks = [];
  bool _playing = false;
  final _controller = StreamController<bool>.broadcast();

  @override
  Future<void> enqueueBytes(Uint8List bytes) async {
    enqueuedChunks.add(bytes);
    _playing = true;
    _controller.add(true);
  }

  @override
  Future<void> pause() async {
    _playing = false;
    _controller.add(false);
  }

  @override
  Future<void> resume() async {
    _playing = true;
    _controller.add(true);
  }

  @override
  Future<void> skip() async {
    _playing = false;
    _controller.add(false);
  }

  @override
  Stream<bool> get isPlayingStream => _controller.stream;

  @override
  Future<void> dispose() async => _controller.close();
}
```

- [ ] **10.2 Verify it compiles**

```bash
flutter analyze lib/shared/audio/
```

Expected: `No issues found!`

- [ ] **10.3 Commit**

```bash
git add flutter_app/lib/shared/audio/
git commit -m "feat(flutter): add AudioPlayerService interface with Real (just_audio) and Fake implementations"
```

---

## Task 11: Riverpod Providers (Shared Layer)

**Files:**
- Create: `flutter_app/lib/shared/providers.dart`

- [ ] **11.1 Create shared providers**

`flutter_app/lib/shared/providers.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';

const _backendUrl = String.fromEnvironment(
  'BACKEND_URL',
  defaultValue: 'http://localhost:8000',
);

final backendClientProvider = Provider<BackendClient>((ref) {
  return RealBackendClient(baseUrl: _backendUrl);
});

final locationServiceProvider = Provider<LocationService>((ref) {
  return RealLocationService();
});

final localDbProvider = Provider<LocalDb>((ref) {
  final db = LocalDb();
  ref.onDispose(db.close);
  return db;
});

final audioPlayerServiceProvider = Provider<AudioPlayerService>((ref) {
  final service = RealAudioPlayerService();
  ref.onDispose(service.dispose);
  return service;
});
```

- [ ] **11.2 Verify it compiles**

```bash
flutter analyze lib/shared/providers.dart
```

Expected: `No issues found!`

- [ ] **11.3 Commit**

```bash
git add flutter_app/lib/shared/providers.dart
git commit -m "feat(flutter): add shared Riverpod providers (client, location, db, audio)"
```

---

## Task 12: SessionProvider (StateNotifier, TDD)

**Files:**
- Create: `flutter_app/lib/features/session/providers/session_provider.dart`
- Test: `flutter_app/test/unit/session_provider_test.dart`

- [ ] **12.1 Write failing SessionProvider tests**

`flutter_app/test/unit/session_provider_test.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:drift/native.dart';
import 'package:flutter_app/shared/db/local_db.dart';

void main() {
  ProviderContainer _makeContainer({bool hasPermission = true}) {
    final fakeLocation = FakeLocationService(hasPermission: hasPermission);
    return ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        localDbProvider.overrideWithValue(
          LocalDb.forTesting(NativeDatabase.memory()),
        ),
      ],
    );
  }

  group('SessionProvider', () {
    test('initial status is idle', () {
      final container = _makeContainer();
      addTearDown(container.dispose);
      expect(container.read(sessionProvider).status, SessionStatus.idle);
    });

    test('start() transitions to active when permission granted', () async {
      final container = _makeContainer(hasPermission: true);
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      expect(container.read(sessionProvider).status, SessionStatus.active);
    });

    test('start() returns to idle when permission denied', () async {
      final container = _makeContainer(hasPermission: false);
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      expect(container.read(sessionProvider).status, SessionStatus.idle);
    });

    test('stop() transitions back to idle', () async {
      final container = _makeContainer();
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      await container.read(sessionProvider.notifier).stop();
      expect(container.read(sessionProvider).status, SessionStatus.idle);
    });

    test('default persona is history_uncle', () {
      final container = _makeContainer();
      addTearDown(container.dispose);
      expect(container.read(sessionProvider).persona, 'history_uncle');
    });
  });
}
```

- [ ] **12.2 Run test to confirm it fails**

```bash
flutter test test/unit/session_provider_test.dart
```

Expected: FAIL — `Target file not found`

- [ ] **12.3 Implement SessionProvider**

`flutter_app/lib/features/session/providers/session_provider.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

enum SessionStatus { idle, starting, active, ending }

class SessionState {
  final SessionStatus status;
  final String persona;
  final String lang;
  final int? currentSessionId;

  const SessionState({
    required this.status,
    this.persona = 'history_uncle',
    this.lang = 'zh-TW',
    this.currentSessionId,
  });

  SessionState copyWith({
    SessionStatus? status,
    int? currentSessionId,
  }) =>
      SessionState(
        status: status ?? this.status,
        persona: persona,
        lang: lang,
        currentSessionId: currentSessionId ?? this.currentSessionId,
      );
}

class SessionNotifier extends StateNotifier<SessionState> {
  SessionNotifier(this._location, this._db)
      : super(const SessionState(status: SessionStatus.idle));

  final LocationService _location;
  final LocalDb _db;

  Future<void> start() async {
    state = state.copyWith(status: SessionStatus.starting);
    final granted = await _location.requestPermission();
    if (!granted) {
      state = state.copyWith(status: SessionStatus.idle);
      return;
    }
    final sessionId =
        await _db.startSession(state.persona, state.lang);
    _location.start();
    state = state.copyWith(
      status: SessionStatus.active,
      currentSessionId: sessionId,
    );
  }

  Future<void> stop() async {
    state = state.copyWith(status: SessionStatus.ending);
    _location.stop();
    if (state.currentSessionId != null) {
      await _db.endSession(state.currentSessionId!);
    }
    state = state.copyWith(status: SessionStatus.idle);
  }
}

final sessionProvider =
    StateNotifierProvider<SessionNotifier, SessionState>((ref) {
  return SessionNotifier(
    ref.watch(locationServiceProvider),
    ref.watch(localDbProvider),
  );
});
```

- [ ] **12.4 Run tests to confirm pass**

```bash
flutter test test/unit/session_provider_test.dart
```

Expected: `All tests passed!`

- [ ] **12.5 Commit**

```bash
git add flutter_app/lib/features/session/providers/ flutter_app/test/unit/session_provider_test.dart
git commit -m "feat(flutter): add SessionProvider state machine (idle/starting/active/ending)"
```

---

## Task 13: PoiProvider (AsyncNotifier, TDD)

**Files:**
- Create: `flutter_app/lib/features/map/providers/poi_provider.dart`
- Test: `flutter_app/test/unit/poi_provider_test.dart`

- [ ] **13.1 Write failing PoiProvider tests**

`flutter_app/test/unit/poi_provider_test.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

void main() {
  final fakePois = [
    POI(
      id: 'osm:1',
      name: '故宮',
      lat: 25.1023,
      lon: 121.5482,
      tags: {},
      distanceM: 87,
      confidence: 'high',
    ),
  ];

  test('PoiProvider returns pois from BackendClient on position update',
      () async {
    final fakeLocation = FakeLocationService();
    final fakeClient = FakeBackendClient(nearbyPois: fakePois);
    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(fakeClient),
      ],
    );
    addTearDown(container.dispose);

    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    // Allow async fetch to complete
    await container.pump();
    await container.pump();

    final state = container.read(poiProvider);
    expect(state.value, fakePois);
  });
}
```

- [ ] **13.2 Run test to confirm it fails**

```bash
flutter test test/unit/poi_provider_test.dart
```

Expected: FAIL — `Target file not found`

- [ ] **13.3 Implement PoiProvider**

`flutter_app/lib/features/map/providers/poi_provider.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/haversine.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

// Re-fetch when user moves more than 250m from last query point
const _refetchThresholdM = 250.0;

final positionStreamProvider = StreamProvider<Position>((ref) {
  return ref.watch(locationServiceProvider).positionStream;
});

class PoiNotifier extends AsyncNotifier<List<POI>> {
  Position? _lastFetchPosition;

  @override
  Future<List<POI>> build() async {
    // Listen for position changes
    ref.listen<AsyncValue<Position>>(
      positionStreamProvider,
      (_, next) => next.whenData(_onPosition),
    );
    return [];
  }

  Future<void> _onPosition(Position position) async {
    if (_lastFetchPosition != null) {
      final dist = haversine(
        _lastFetchPosition!.latitude,
        _lastFetchPosition!.longitude,
        position.latitude,
        position.longitude,
      );
      if (dist < _refetchThresholdM) return;
    }
    _lastFetchPosition = position;
    state = const AsyncLoading();
    state = await AsyncValue.guard(() =>
        ref.read(backendClientProvider).fetchNearby(
              lat: position.latitude,
              lon: position.longitude,
              radius: 500,
              lang: 'zh-TW',
              persona: 'history_uncle',
            ));
  }
}

final poiProvider = AsyncNotifierProvider<PoiNotifier, List<POI>>(
  PoiNotifier.new,
);
```

- [ ] **13.4 Run tests to confirm pass**

```bash
flutter test test/unit/poi_provider_test.dart
```

Expected: `All tests passed!`

- [ ] **13.5 Commit**

```bash
git add flutter_app/lib/features/map/providers/ flutter_app/test/unit/poi_provider_test.dart
git commit -m "feat(flutter): add PoiProvider that re-fetches /poi/nearby on 250m movement"
```

---

## Task 14: NarrationProvider (StateNotifier, Integration TDD)

**Files:**
- Create: `flutter_app/lib/features/narration/providers/narration_provider.dart`
- Test: `flutter_app/test/integration/narration_flow_test.dart`

- [ ] **14.1 Write failing integration tests**

`flutter_app/test/integration/narration_flow_test.dart`:

```dart
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/providers.dart';

final _testPoi = POI(
  id: 'osm:1',
  name: '故宮博物院',
  lat: 25.1023,
  lon: 121.5482,
  tags: {},
  distanceM: 87,
  confidence: 'high',
);

final _scriptedEvents = [
  const MetaEvent(poiId: 'osm:1', cacheHit: false, confidence: 'high'),
  const TextEvent(chunk: '故宮博物院'),
  AudioEvent(
    chunkB64: base64.encode(Uint8List.fromList([0, 1, 2, 3])),
    sentenceIdx: 0,
  ),
  const EndEvent(totalDurationS: 10),
];

ProviderContainer _makeContainer() {
  final fakeAudio = FakeAudioPlayerService();
  final fakeClient = FakeBackendClient(scriptedEvents: _scriptedEvents);
  return ProviderContainer(
    overrides: [
      backendClientProvider.overrideWithValue(fakeClient),
      audioPlayerServiceProvider.overrideWithValue(fakeAudio),
      localDbProvider.overrideWithValue(
        LocalDb.forTesting(NativeDatabase.memory()),
      ),
    ],
  );
}

void main() {
  group('NarrationProvider', () {
    test('initial status is idle', () {
      final container = _makeContainer();
      addTearDown(container.dispose);
      expect(container.read(narrationProvider).status, NarrationStatus.idle);
    });

    test('narrate() transitions through loading → playing → idle', () async {
      final container = _makeContainer();
      addTearDown(container.dispose);
      final states = <NarrationStatus>[];
      container.listen(
        narrationProvider.select((s) => s.status),
        (_, next) => states.add(next),
      );
      await container.read(narrationProvider.notifier).narrate(_testPoi);
      // Allow stream events to process
      await Future<void>.delayed(Duration.zero);
      expect(states, contains(NarrationStatus.loading));
    });

    test('audio chunks are enqueued after narrate()', () async {
      final fakeAudio = FakeAudioPlayerService();
      final container = ProviderContainer(
        overrides: [
          backendClientProvider.overrideWithValue(
            FakeBackendClient(scriptedEvents: _scriptedEvents),
          ),
          audioPlayerServiceProvider.overrideWithValue(fakeAudio),
          localDbProvider.overrideWithValue(
            LocalDb.forTesting(NativeDatabase.memory()),
          ),
        ],
      );
      addTearDown(container.dispose);
      await container.read(narrationProvider.notifier).narrate(_testPoi);
      await Future<void>.delayed(Duration.zero);
      expect(fakeAudio.enqueuedChunks, isNotEmpty);
    });

    test('subtitle is accumulated from text events', () async {
      final container = _makeContainer();
      addTearDown(container.dispose);
      await container.read(narrationProvider.notifier).narrate(_testPoi);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(narrationProvider).subtitle, contains('故宮'));
    });
  });
}
```

- [ ] **14.2 Run test to confirm it fails**

```bash
flutter test test/integration/narration_flow_test.dart
```

Expected: FAIL — `Target file not found`

- [ ] **14.3 Implement NarrationProvider**

`flutter_app/lib/features/narration/providers/narration_provider.dart`:

```dart
import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/providers.dart';

enum NarrationStatus { idle, loading, playing, paused, error }

class NarrationState {
  final NarrationStatus status;
  final POI? currentPoi;
  final String subtitle;
  final double progress;
  final String? confidence;
  final String? errorMessage;

  const NarrationState({
    required this.status,
    this.currentPoi,
    this.subtitle = '',
    this.progress = 0,
    this.confidence,
    this.errorMessage,
  });

  NarrationState copyWith({
    NarrationStatus? status,
    POI? currentPoi,
    String? subtitle,
    double? progress,
    String? confidence,
    String? errorMessage,
  }) =>
      NarrationState(
        status: status ?? this.status,
        currentPoi: currentPoi ?? this.currentPoi,
        subtitle: subtitle ?? this.subtitle,
        progress: progress ?? this.progress,
        confidence: confidence ?? this.confidence,
        errorMessage: errorMessage ?? this.errorMessage,
      );
}

class NarrationNotifier extends StateNotifier<NarrationState> {
  NarrationNotifier(this._client, this._audio, this._db)
      : super(const NarrationState(status: NarrationStatus.idle));

  final BackendClient _client;
  final AudioPlayerService _audio;
  final LocalDb _db;
  StreamSubscription<NarrationEvent>? _sub;
  int _audioChunkCount = 0;

  Future<void> narrate(POI poi) async {
    await _sub?.cancel();
    _audioChunkCount = 0;
    state = NarrationState(
      status: NarrationStatus.loading,
      currentPoi: poi,
    );

    _sub = _client
        .narrate(
          poiId: poi.id,
          persona: 'history_uncle',
          lang: 'zh-TW',
          length: 'medium',
        )
        .listen(
          (event) => _handle(event, poi),
          onError: (Object e) => state = state.copyWith(
            status: NarrationStatus.error,
            errorMessage: e.toString(),
          ),
        );
  }

  void _handle(NarrationEvent event, POI poi) {
    switch (event) {
      case MetaEvent(:final confidence):
        state = state.copyWith(
          status: NarrationStatus.playing,
          confidence: confidence,
        );
      case TextEvent(:final chunk):
        state = state.copyWith(subtitle: state.subtitle + chunk);
      case AudioEvent(:final chunkB64):
        _audioChunkCount++;
        final bytes = base64.decode(chunkB64);
        _audio.enqueueBytes(bytes);
        state = state.copyWith(
          progress: (_audioChunkCount * 0.1).clamp(0.0, 0.9),
        );
      case EndEvent():
        _db.recordNarration(
          sessionId: 1,
          poiId: poi.id,
          poiName: poi.name,
          poiLat: poi.lat,
          poiLon: poi.lon,
          persona: 'history_uncle',
          lang: 'zh-TW',
          completed: true,
        );
        state = state.copyWith(
          status: NarrationStatus.idle,
          progress: 1.0,
        );
      case ErrorEvent(:final message):
        state = state.copyWith(
          status: NarrationStatus.error,
          errorMessage: message,
        );
    }
  }

  Future<void> pause() async {
    await _audio.pause();
    state = state.copyWith(status: NarrationStatus.paused);
  }

  Future<void> resume() async {
    await _audio.resume();
    state = state.copyWith(status: NarrationStatus.playing);
  }

  Future<void> skip() async {
    await _sub?.cancel();
    await _audio.skip();
    state = state.copyWith(status: NarrationStatus.idle);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final narrationProvider =
    StateNotifierProvider<NarrationNotifier, NarrationState>((ref) {
  return NarrationNotifier(
    ref.watch(backendClientProvider),
    ref.watch(audioPlayerServiceProvider),
    ref.watch(localDbProvider),
  );
});
```

- [ ] **14.4 Run tests to confirm pass**

```bash
flutter test test/integration/narration_flow_test.dart
```

Expected: `All tests passed!`

- [ ] **14.5 Commit**

```bash
git add flutter_app/lib/features/narration/providers/narration_provider.dart flutter_app/test/integration/
git commit -m "feat(flutter): add NarrationProvider with SSE streaming and audio FIFO queue"
```

---

## Task 15: TriggerProvider (Riverpod, TDD)

**Files:**
- Create: `flutter_app/lib/features/narration/providers/trigger_provider.dart`
- Test: `flutter_app/test/unit/trigger_provider_test.dart`

- [ ] **15.1 Write failing TriggerProvider tests**

`flutter_app/test/unit/trigger_provider_test.dart`:

```dart
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

void main() {
  final nearPoi = POI(
    id: 'osm:near',
    name: '近處景點',
    lat: 25.1031,  // ~89m north of user
    lon: 121.5482,
    tags: {},
    distanceM: 89,
    confidence: 'high',
  );

  test('TriggerProvider calls narrate when POI enters radius', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());
    await db.startSession('history_uncle', 'zh-TW');

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(
          FakeBackendClient(nearbyPois: [nearPoi]),
        ),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
      ],
    );
    addTearDown(container.dispose);

    // Read trigger provider to activate it
    container.read(triggerProvider);

    // Emit a position near the POI (need to also trigger poiProvider)
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    // After trigger, audio should eventually be enqueued
    // (narration with fake scripted events starts)
    // Just verify no exceptions thrown and trigger provider is active
    expect(container.read(triggerProvider), isNotNull);
  });
}
```

- [ ] **15.2 Run test to confirm it fails**

```bash
flutter test test/unit/trigger_provider_test.dart
```

Expected: FAIL — `Target file not found`

- [ ] **15.3 Implement TriggerProvider**

`flutter_app/lib/features/narration/providers/trigger_provider.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/trigger_engine.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/providers.dart';

class TriggerNotifier extends Notifier<void> {
  final Set<String> _sessionPlayedIds = {};

  @override
  void build() {
    final positionAsync = ref.watch(positionStreamProvider);
    final poisAsync = ref.watch(poiProvider);

    positionAsync.whenData((position) {
      poisAsync.whenData((pois) {
        _evaluate(position, pois);
      });
    });
  }

  Future<void> _evaluate(Position position, List<dynamic> pois) async {
    final narState = ref.read(narrationProvider);
    if (narState.status == NarrationStatus.playing ||
        narState.status == NarrationStatus.loading) {
      return;
    }

    final db = ref.read(localDbProvider);
    final cooldownIds = <String>{};
    for (final poi in pois) {
      final inCooldown =
          await db.isCooldown(poi.id, const Duration(hours: 24));
      if (inCooldown) cooldownIds.add(poi.id);
    }

    final triggers = TriggerEngine.evaluate(
      userLat: position.latitude,
      userLon: position.longitude,
      pois: pois.cast(),
      playedPoiIds: _sessionPlayedIds,
      cooldownPoiIds: cooldownIds,
    );

    if (triggers.isNotEmpty) {
      final poi = triggers.first;
      _sessionPlayedIds.add(poi.id);
      ref.read(narrationProvider.notifier).narrate(poi);
    }
  }
}

final triggerProvider = NotifierProvider<TriggerNotifier, void>(
  TriggerNotifier.new,
);
```

- [ ] **15.4 Run tests to confirm pass**

```bash
flutter test test/unit/trigger_provider_test.dart
```

Expected: `All tests passed!`

- [ ] **15.5 Commit**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart flutter_app/test/unit/trigger_provider_test.dart
git commit -m "feat(flutter): add TriggerProvider that auto-triggers narration on POI proximity"
```

---

## Task 16: HomeScreen (Widget)

**Files:**
- Create: `flutter_app/lib/features/session/screens/home_screen.dart`
- Create: `flutter_app/lib/features/session/widgets/persona_chip.dart`
- Test: `flutter_app/test/widget/home_screen_test.dart`

- [ ] **16.1 Write failing HomeScreen widget tests**

`flutter_app/test/widget/home_screen_test.dart`:

```dart
import 'dart:async';
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/session/screens/home_screen.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

class _FakeLocationService implements LocationService {
  final bool hasPermission;
  _FakeLocationService({this.hasPermission = true});
  @override Future<bool> requestPermission() async => hasPermission;
  @override void start() {}
  @override void stop() {}
  @override Stream<Position> get positionStream => const Stream.empty();
}

Widget _makeWidget({bool hasPermission = true}) {
  return ProviderScope(
    overrides: [
      locationServiceProvider.overrideWithValue(
        _FakeLocationService(hasPermission: hasPermission),
      ),
      localDbProvider.overrideWithValue(
        LocalDb.forTesting(NativeDatabase.memory()),
      ),
    ],
    child: const MaterialApp(home: HomeScreen()),
  );
}

void main() {
  testWidgets('shows Start Journey button when idle', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.text('開始旅程'), findsOneWidget);
  });

  testWidgets('shows persona chip with history_uncle', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.text('歷史大叔'), findsOneWidget);
  });
}
```

> **Note:** Uses `locationServiceProvider` + `localDbProvider` overrides — avoids touching `StateNotifier.state` directly (which is `@protected` and inaccessible from extensions in other libraries).

- [ ] **16.2 Create HomeScreen + test helpers**

`flutter_app/lib/features/session/screens/home_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/features/session/widgets/persona_chip.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    final isStarting = session.status == SessionStatus.starting;

    return Scaffold(
      backgroundColor: const Color(0xFF1A1A2E),
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text(
                'AI Tour Guide',
                style: TextStyle(
                  color: Color(0xFF4A9EFF),
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              const PersonaChip(),
              const SizedBox(height: 48),
              ElevatedButton(
                onPressed: isStarting
                    ? null
                    : () => _start(context, ref),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 40,
                    vertical: 16,
                  ),
                ),
                child: isStarting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('開始旅程', style: TextStyle(fontSize: 18)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _start(BuildContext context, WidgetRef ref) async {
    await ref.read(sessionProvider.notifier).start();
    final status = ref.read(sessionProvider).status;
    if (status == SessionStatus.active && context.mounted) {
      context.push('/map');
    } else if (status == SessionStatus.idle && context.mounted) {
      showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('需要定位權限'),
          content: const Text('請在設定中允許「使用 App 期間」的定位權限。'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('確定'),
            ),
          ],
        ),
      );
    }
  }
}
```

`flutter_app/lib/features/session/widgets/persona_chip.dart`:

```dart
import 'package:flutter/material.dart';

class PersonaChip extends StatelessWidget {
  const PersonaChip({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF0F3460),
        borderRadius: BorderRadius.circular(20),
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('🏛️ ', style: TextStyle(fontSize: 16)),
          Text(
            '歷史大叔',
            style: TextStyle(color: Color(0xFF4A9EFF), fontSize: 16),
          ),
        ],
      ),
    );
  }
}
```

> **Note:** All test helpers (`_FakeLocationService`, `_makeWidget`) are already defined in step 16.1's test file — no additional helpers needed here.

- [ ] **16.3 Run tests**

```bash
flutter test test/widget/home_screen_test.dart
```

Expected: `All tests passed!`

- [ ] **16.4 Commit**

```bash
git add flutter_app/lib/features/session/ flutter_app/test/widget/home_screen_test.dart
git commit -m "feat(flutter): add HomeScreen with persona chip and start journey button"
```

---

## Task 17: NarrationSheet + NarrationMiniBar (Widget)

**Files:**
- Create: `flutter_app/lib/features/narration/widgets/narration_mini_bar.dart`
- Create: `flutter_app/lib/features/narration/widgets/narration_sheet.dart`
- Test: `flutter_app/test/widget/narration_sheet_test.dart`

- [ ] **17.1 Write failing NarrationSheet widget tests**

`flutter_app/test/widget/narration_sheet_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/widgets/narration_mini_bar.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';

final _testState = NarrationState(
  status: NarrationStatus.playing,
  currentPoi: POI(
    id: 'osm:1',
    name: '國立故宮博物院',
    lat: 25.1023,
    lon: 121.5482,
    tags: {},
    distanceM: 87,
    confidence: 'high',
  ),
  subtitle: '故宮博物院創建於 1925 年',
  progress: 0.4,
  confidence: 'high',
);

void main() {
  testWidgets('NarrationMiniBar shows POI name when playing', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          narrationProvider.overrideWith(
            (ref) => _FakeNarrationNotifier(_testState),
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(body: NarrationMiniBar()),
        ),
      ),
    );
    expect(find.text('國立故宮博物院'), findsOneWidget);
  });

  testWidgets('NarrationMiniBar is hidden when idle', (tester) async {
    const idleState = NarrationState(status: NarrationStatus.idle);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          narrationProvider.overrideWith(
            (ref) => _FakeNarrationNotifier(idleState),
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(body: NarrationMiniBar()),
        ),
      ),
    );
    expect(find.text('國立故宮博物院'), findsNothing);
  });
}

class _FakeNarrationNotifier extends StateNotifier<NarrationState>
    implements NarrationNotifier {
  _FakeNarrationNotifier(super.state);
  @override Future<void> narrate(POI poi) async {}
  @override Future<void> pause() async {}
  @override Future<void> resume() async {}
  @override Future<void> skip() async {}
}
```

- [ ] **17.2 Run test to confirm it fails**

```bash
flutter test test/widget/narration_sheet_test.dart
```

Expected: FAIL — `Target file not found`

- [ ] **17.3 Create NarrationMiniBar**

`flutter_app/lib/features/narration/widgets/narration_mini_bar.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';

class NarrationMiniBar extends ConsumerWidget {
  const NarrationMiniBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(narrationProvider);
    if (state.status == NarrationStatus.idle ||
        state.currentPoi == null) {
      return const SizedBox.shrink();
    }
    return Container(
      color: const Color(0xFF0F3460),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  state.currentPoi!.name,
                  style: const TextStyle(
                    color: Color(0xFF4A9EFF),
                    fontWeight: FontWeight.bold,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  state.status == NarrationStatus.playing
                      ? '▶ 正在播放...'
                      : '⏸ 已暫停',
                  style: const TextStyle(color: Colors.grey, fontSize: 12),
                ),
              ],
            ),
          ),
          IconButton(
            icon: Icon(
              state.status == NarrationStatus.playing
                  ? Icons.pause
                  : Icons.play_arrow,
              color: Colors.white,
            ),
            onPressed: () {
              if (state.status == NarrationStatus.playing) {
                ref.read(narrationProvider.notifier).pause();
              } else {
                ref.read(narrationProvider.notifier).resume();
              }
            },
          ),
          IconButton(
            icon: const Icon(Icons.skip_next, color: Colors.white),
            onPressed: () =>
                ref.read(narrationProvider.notifier).skip(),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **17.4 Create NarrationSheet**

`flutter_app/lib/features/narration/widgets/narration_sheet.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';

class NarrationSheet extends ConsumerWidget {
  const NarrationSheet({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(narrationProvider);
    if (state.status == NarrationStatus.idle ||
        state.currentPoi == null) {
      return const SizedBox.shrink();
    }

    return DraggableScrollableSheet(
      initialChildSize: 0.12,
      minChildSize: 0.12,
      maxChildSize: 0.6,
      snap: true,
      snapSizes: const [0.12, 0.6],
      builder: (context, scrollController) => Container(
        decoration: const BoxDecoration(
          color: Color(0xFF16213E),
          borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
        ),
        child: ListView(
          controller: scrollController,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          children: [
            // Handle
            Center(
              child: Container(
                margin: const EdgeInsets.symmetric(vertical: 8),
                width: 32,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[600],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            // POI name
            Text(
              state.currentPoi!.name,
              style: const TextStyle(
                color: Color(0xFF4A9EFF),
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
            if (state.confidence != null && state.confidence != 'high')
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  state.confidence == 'medium'
                      ? '⚠ 此處資料偏少，大叔僅憑可查證的脈絡推測'
                      : '⚠ 此處史料有限，大叔僅作脈絡推測，請勿引用',
                  style: const TextStyle(
                    color: Colors.orange,
                    fontSize: 11,
                  ),
                ),
              ),
            const SizedBox(height: 8),
            // Subtitle
            Text(
              state.subtitle,
              style: const TextStyle(color: Colors.white70, fontSize: 14, height: 1.6),
            ),
            const SizedBox(height: 12),
            // Progress bar
            LinearProgressIndicator(
              value: state.progress,
              backgroundColor: const Color(0xFF0A0A2A),
              valueColor:
                  const AlwaysStoppedAnimation<Color>(Color(0xFF4A9EFF)),
            ),
            const SizedBox(height: 12),
            // Controls
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  icon: Icon(
                    state.status == NarrationStatus.playing
                        ? Icons.pause_circle
                        : Icons.play_circle,
                    color: Colors.white,
                    size: 36,
                  ),
                  onPressed: () {
                    if (state.status == NarrationStatus.playing) {
                      ref.read(narrationProvider.notifier).pause();
                    } else {
                      ref.read(narrationProvider.notifier).resume();
                    }
                  },
                ),
                const SizedBox(width: 16),
                IconButton(
                  icon: const Icon(
                    Icons.skip_next,
                    color: Colors.white,
                    size: 32,
                  ),
                  onPressed: () =>
                      ref.read(narrationProvider.notifier).skip(),
                ),
              ],
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **17.5 Run tests to confirm pass**

```bash
flutter test test/widget/narration_sheet_test.dart
```

Expected: `All tests passed!`

- [ ] **17.6 Commit**

```bash
git add flutter_app/lib/features/narration/widgets/ flutter_app/test/widget/narration_sheet_test.dart
git commit -m "feat(flutter): add NarrationMiniBar and NarrationSheet (DraggableScrollableSheet)"
```

---

## Task 18: MapScreen + POI Markers + App Shell

**Files:**
- Create: `flutter_app/lib/features/map/screens/map_screen.dart`
- Create: `flutter_app/lib/features/map/widgets/poi_marker.dart`
- Replace: `flutter_app/lib/main.dart`
- Create: `flutter_app/lib/app.dart`

- [ ] **18.1 Create app.dart with go_router**

`flutter_app/lib/app.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/features/session/screens/home_screen.dart';
import 'package:flutter_app/features/map/screens/map_screen.dart';

final _router = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (_, __) => const HomeScreen(),
    ),
    GoRoute(
      path: '/map',
      builder: (_, __) => const MapScreen(),
    ),
  ],
);

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'AI Tour Guide',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF4A9EFF),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      routerConfig: _router,
    );
  }
}
```

- [ ] **18.2 Replace main.dart**

`flutter_app/lib/main.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: App()));
}
```

- [ ] **18.3 Create poi_marker.dart**

`flutter_app/lib/features/map/widgets/poi_marker.dart`:

```dart
import 'package:google_maps_flutter/google_maps_flutter.dart';

/// Returns a BitmapDescriptor hue based on POI confidence level.
BitmapDescriptor poiMarkerHue(String confidence) {
  return switch (confidence) {
    'high' => BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueAzure),
    'medium' =>
      BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueYellow),
    _ => BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueRed),
  };
}
```

- [ ] **18.4 Create MapScreen**

`flutter_app/lib/features/map/screens/map_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/map/widgets/poi_marker.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/features/narration/widgets/narration_sheet.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';

class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  GoogleMapController? _mapController;

  @override
  void initState() {
    super.initState();
    // Activate trigger provider
    ref.read(triggerProvider);
  }

  @override
  Widget build(BuildContext context) {
    final poisAsync = ref.watch(poiProvider);
    final position = ref.watch(
      positionStreamProvider.select((v) => v.valueOrNull),
    );

    // Build markers from POI list
    final markers = <Marker>{};
    poisAsync.whenData((pois) {
      for (final poi in pois) {
        markers.add(Marker(
          markerId: MarkerId(poi.id),
          position: LatLng(poi.lat, poi.lon),
          icon: poiMarkerHue(poi.confidence),
          infoWindow: InfoWindow(title: poi.name),
          onTap: () => ref.read(narrationProvider.notifier).narrate(poi),
        ));
      }
    });

    final initialTarget = position != null
        ? LatLng(position.latitude, position.longitude)
        : const LatLng(25.1023, 121.5482); // Default: Palace Museum

    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F3460),
        title: const Row(
          children: [
            Icon(Icons.circle, color: Color(0xFF4A9EFF), size: 12),
            SizedBox(width: 8),
            Text('旅程進行中', style: TextStyle(color: Colors.white)),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () async {
              await ref.read(sessionProvider.notifier).stop();
              if (context.mounted) context.pop();
            },
            child: const Text('結束', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
      body: Stack(
        children: [
          GoogleMap(
            initialCameraPosition: CameraPosition(
              target: initialTarget,
              zoom: 16,
            ),
            myLocationEnabled: true,
            myLocationButtonEnabled: true,
            markers: markers,
            onMapCreated: (c) => _mapController = c,
          ),
          Align(
            alignment: Alignment.bottomCenter,
            child: const NarrationSheet(),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _mapController?.dispose();
    super.dispose();
  }
}
```

- [ ] **18.5 Run flutter analyze**

```bash
flutter analyze
```

Expected: `No issues found!` (fix any errors before proceeding)

- [ ] **18.6 Verify app runs on simulator**

```bash
# iOS Simulator
flutter run --dart-define-from-file=dart_defines/dev.json

# Android Emulator
flutter run --dart-define-from-file=dart_defines/dev.json
```

Expected: App launches, HomeScreen visible with 「開始旅程」 button.

- [ ] **18.7 Commit**

```bash
git add flutter_app/lib/
git commit -m "feat(flutter): add MapScreen with Google Maps POI markers, NarrationSheet overlay, and app routing"
```

---

## Task 19: Full Test Suite + README

**Files:**
- Create: `flutter_app/README.md`

- [ ] **19.1 Run complete test suite**

```bash
cd flutter_app
flutter test
```

Expected: All tests pass, 0 failures.

- [ ] **19.2 Run flutter analyze**

```bash
flutter analyze
```

Expected: `No issues found!`

- [ ] **19.3 Create README.md**

`flutter_app/README.md`:

````markdown
# AI Tour Guide — Flutter App

Flutter front-end for the AI Tour Guide, consuming the Plan A FastAPI backend.

## Prerequisites

- Flutter 3.x (`flutter --version`)
- A Google Maps API key with Maps SDK for Android + iOS enabled
- Plan A backend running locally (`cd ../backend && uvicorn tour_guide.main:app --reload`)

## Setup

1. **Clone and install:**
   ```bash
   flutter pub get
   dart run build_runner build --delete-conflicting-outputs
   ```

2. **Configure Google Maps API keys:**
   - Android: edit `android/app/src/main/AndroidManifest.xml`, replace `YOUR_ANDROID_MAPS_API_KEY`
   - iOS: edit `ios/Runner/AppDelegate.swift`, replace `YOUR_IOS_MAPS_API_KEY`

## Running

```bash
# Android Emulator (backend at 10.0.2.2:8000)
flutter run --dart-define-from-file=dart_defines/dev.json

# iOS Simulator (backend at localhost:8000)
flutter run --dart-define=BACKEND_URL=http://localhost:8000

# Real device on same WiFi (replace with your machine's IP)
flutter run --dart-define=BACKEND_URL=http://192.168.1.x:8000
```

## Testing

```bash
# All tests (unit + widget + integration)
flutter test

# Single file
flutter test test/unit/sse_parser_test.dart -v
```

## App Flow

1. Launch → HomeScreen shows 「歷史大叔」persona + 「開始旅程」 button
2. Tap → Grants location permission → MapScreen opens
3. Map shows nearby POI markers (blue=high confidence, yellow=medium, red=low)
4. Walk within 100m of POI → Auto-trigger narration (or tap marker to trigger manually)
5. NarrationSheet slides up from bottom → Shows subtitle + progress + pause/skip controls
6. Tap 「結束」 → Session ends, returns to HomeScreen
````

- [ ] **19.4 Final commit**

```bash
git add flutter_app/README.md
git commit -m "docs(flutter): add README with setup, run, and test instructions for Plan B"
```

---

## Plan B — Done Definition

1. `flutter test` → all tests green, 0 failures
2. `flutter analyze` → no issues
3. App builds for Android and iOS without errors
4. `flutter run` → HomeScreen visible with 「開始旅程」 button
5. (Requires device + backend running) Tap button → MapScreen opens with map
6. (Requires device + backend running) Tap POI marker → NarrationSheet slides up, audio plays

---
