# Default Fallback Location Design

**Date:** 2026-05-16
**Status:** Approved

## Problem

When the app runs on a simulator or a device without GPS signal, `positionStreamProvider` never emits a value. This means:
- The map camera stays at a meaningless hardcoded coordinate
- `PoiNotifier` never triggers a POI fetch
- The full tour experience is unavailable

## Goal

If no real GPS position arrives within 5 seconds of the location stream starting, automatically inject a language-appropriate fallback position so the user gets the full map + POI experience.

| Language | Fallback Location | Coordinates |
|----------|-------------------|-------------|
| zh-TW | 台北故宮博物院門口 | 25.1023°N, 121.5484°E |
| en | Smithsonian's National Air and Space Museum | 38.8882°N, 77.0197°W |

## Architecture

### Existing providers (unchanged)

- `positionStreamProvider` — pure GPS stream from `LocationService`. Remains unchanged.

### New: `effectivePositionStreamProvider`

A new `StreamProvider<Position>` that wraps the GPS stream and adds fallback logic:

1. Subscribe to `locationServiceProvider.positionStream`
2. Start a 5-second `Timer`
3. If GPS emits before the timer fires → cancel the timer, forward GPS values normally
4. If the timer fires before any GPS value → emit `fallbackPosition(lang)` once, then continue forwarding any GPS values that arrive later

The provider reads `sessionProvider` to determine the current language.

### New: `fallback_locations.dart`

A small constants file at `lib/shared/location/fallback_locations.dart`:

```dart
const _kFallbackZhTW = (lat: 25.1023, lon: 121.5484);
const _kFallbackEn   = (lat: 38.8882, lon: -77.0197);

Position fallbackPosition(String lang) {
  final coords = lang == 'zh-TW' ? _kFallbackZhTW : _kFallbackEn;
  return fakePosition(coords.lat, coords.lon);
}
```

Reuses the existing `fakePosition()` helper from `location_service.dart`.

## Consumer Changes

| File | Change |
|------|--------|
| `map/providers/poi_provider.dart` | `PoiNotifier.build()` listens to `effectivePositionStreamProvider` instead of `positionStreamProvider` |
| `features/map/screens/map_screen.dart` | Both `ref.watch` and `ref.listen` switch to `effectivePositionStreamProvider`; hardcoded `LatLng(25.1023, 121.5482)` in `initialCameraPosition` replaced with `LatLng(0, 0)` (the effective provider will move the camera within 5s) |
| `features/narration/providers/trigger_provider.dart` | Switches to `effectivePositionStreamProvider` |

## Files Changed

- **New:** `lib/shared/location/fallback_locations.dart`
- **New or updated:** `lib/features/map/providers/poi_provider.dart` (add `effectivePositionStreamProvider`)
- **Updated:** `lib/features/map/screens/map_screen.dart`
- **Updated:** `lib/features/narration/providers/trigger_provider.dart`

## Behavior Summary

| Scenario | Outcome |
|----------|---------|
| Real device, GPS arrives within 5s | Normal GPS behavior, no change |
| Simulator / GPS never arrives | After 5s, camera moves to fallback + POIs load at fallback |
| GPS arrives after fallback was injected | Subsequent GPS positions are forwarded normally |

## Out of Scope

- Persisting fallback preference
- User-configurable fallback location
- Detecting simulator vs real device explicitly
