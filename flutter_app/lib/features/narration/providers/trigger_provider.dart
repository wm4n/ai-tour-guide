import 'dart:async';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/haversine.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/log_events.dart';
import 'package:geolocator/geolocator.dart';

class TriggerState {
  final bool isCountingDown;
  final Duration countdownRemaining;
  final bool isWaitingForDisplacement;
  final double? skipLat;
  final double? skipLon;
  final double movedMeters;

  const TriggerState({
    this.isCountingDown = false,
    this.countdownRemaining = Duration.zero,
    this.isWaitingForDisplacement = false,
    this.skipLat,
    this.skipLon,
    this.movedMeters = 0,
  });

  TriggerState copyWith({
    bool? isCountingDown,
    Duration? countdownRemaining,
    bool? isWaitingForDisplacement,
    double? skipLat,
    double? skipLon,
    double? movedMeters,
  }) =>
      TriggerState(
        isCountingDown: isCountingDown ?? this.isCountingDown,
        countdownRemaining: countdownRemaining ?? this.countdownRemaining,
        isWaitingForDisplacement:
            isWaitingForDisplacement ?? this.isWaitingForDisplacement,
        skipLat: skipLat ?? this.skipLat,
        skipLon: skipLon ?? this.skipLon,
        movedMeters: movedMeters ?? this.movedMeters,
      );
}

class TriggerNotifier extends Notifier<TriggerState> {
  final Set<String> _sessionPlayedIds = {};
  List<POI> _latestPois = [];
  Timer? _cooldownTimer;
  DateTime? _cooldownUntil;
  String? _lastSelectedPoiId;
  String _lastSelectedPoiName = '';
  String _lastScript = '';
  bool _hasEverFired = false;
  StreamSubscription<Position>? _locationSub;
  Position? _currentPosition;
  Position? _lastTriggerPosition;
  Set<String> _lastCandidateIds = {};
  StreamSubscription<Position>? _positionTrackSub;

  @override
  TriggerState build() {
    ref.listen<AsyncValue<List<POI>>>(
      poiProvider,
      (_, next) => next.whenData((pois) {
        _latestPois = pois;
        AppLogger.info(
            LogEvents.triggerEval, {'layer': 'pois_updated', 'count': pois.length});
        // Fire immediately on first POI load if never played
        if (!_hasEverFired && pois.isNotEmpty && !state.isCountingDown) {
          final narState = ref.read(narrationProvider);
          if (narState.status == NarrationStatus.idle) {
            _doCandidatesRequest().catchError((Object e, StackTrace st) {
              AppLogger.error(
                  LogEvents.apiError, {'context': 'initial_trigger'}, e, st);
            });
          }
        }
      }),
    );

    ref.listen<NarrationState>(
      narrationProvider,
      (prev, next) {
        // Mark POI as played when it is first selected (MetaEvent received → playing)
        if (prev?.currentPoi == null && next.currentPoi != null) {
          _sessionPlayedIds.add(next.currentPoi!.id);
          _hasEverFired = true;
        }
        // Start countdown when narration completes normally
        if (prev?.status == NarrationStatus.playing &&
            next.status == NarrationStatus.idle) {
          _lastSelectedPoiId = next.currentPoi?.id;
          _lastSelectedPoiName = next.currentPoi?.name ?? '';
          _lastScript = next.scriptBuffer;
          _startCountdown();
        }
        // Also start countdown on error to avoid getting stuck
        if ((prev?.status == NarrationStatus.loading ||
                prev?.status == NarrationStatus.playing) &&
            next.status == NarrationStatus.error) {
          _startCountdown();
        }
        // Handle skip: switch to displacement-wait mode
        if (next.lastEventWasSkip && !(prev?.lastEventWasSkip ?? false)) {
          _handleSkip();
        }
      },
    );

    _positionTrackSub = ref.read(locationServiceProvider).positionStream.listen((pos) {
      _currentPosition = pos;
    });

    ref.onDispose(() {
      _cooldownTimer?.cancel();
      _locationSub?.cancel();
      _positionTrackSub?.cancel();
    });

    return const TriggerState();
  }

  void _startCountdown() {
    _locationSub?.cancel();
    _locationSub = null;
    _cooldownTimer?.cancel();
    final seconds = ref.read(appSettingsProvider).countdownSeconds;
    final duration = Duration(seconds: seconds);
    _cooldownUntil = DateTime.now().add(duration);
    state = TriggerState(isCountingDown: true, countdownRemaining: duration);

    _cooldownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      final remaining = _cooldownUntil!.difference(DateTime.now());
      if (remaining <= Duration.zero) {
        timer.cancel();
        _cooldownTimer = null;
        _cooldownUntil = null;
        state = const TriggerState();
        _doCandidatesRequest().catchError((Object e, StackTrace st) {
          AppLogger.error(
              LogEvents.apiError, {'context': 'countdown_expired'}, e, st);
        });
      } else {
        state = TriggerState(isCountingDown: true, countdownRemaining: remaining);
      }
    });
  }

  void skipCountdown() {
    _cooldownTimer?.cancel();
    _cooldownTimer = null;
    _cooldownUntil = null;
    state = const TriggerState();
    _doCandidatesRequest().catchError((Object e, StackTrace st) {
      AppLogger.error(LogEvents.apiError, {'context': 'countdown_skip'}, e, st);
    });
  }

  void _handleSkip() {
    _cooldownTimer?.cancel();
    _cooldownTimer = null;
    _cooldownUntil = null;
    AppLogger.info(
        LogEvents.triggerSkip, {'reason': 'poi_trivial_waiting_displacement'});
    state = const TriggerState(isWaitingForDisplacement: true);
    _startDisplacementWatch();
  }

  void _startDisplacementWatch() {
    _locationSub?.cancel();
    double? originLat;
    double? originLon;

    _locationSub =
        ref.read(locationServiceProvider).positionStream.listen((pos) {
      if (!state.isWaitingForDisplacement) {
        _locationSub?.cancel();
        _locationSub = null;
        return;
      }
      if (originLat == null) {
        originLat = pos.latitude;
        originLon = pos.longitude;
        state = state.copyWith(
            skipLat: originLat, skipLon: originLon, movedMeters: 0);
        return;
      }
      final dist =
          haversine(originLat!, originLon!, pos.latitude, pos.longitude);
      final threshold = ref.read(appSettingsProvider).skipDisplacementM;
      state = state.copyWith(movedMeters: dist);
      if (dist >= threshold) {
        _clearDisplacementWatch();
        _doCandidatesRequest().catchError((Object e, StackTrace st) {
          AppLogger.error(
              LogEvents.apiError, {'context': 'displacement_trigger'}, e, st);
        });
      }
    });
  }

  void _clearDisplacementWatch() {
    _locationSub?.cancel();
    _locationSub = null;
    state = const TriggerState();
  }

  Future<void> _doCandidatesRequest() async {
    if (_latestPois.isEmpty) return;

    final narState = ref.read(narrationProvider);
    if (narState.status == NarrationStatus.playing ||
        narState.status == NarrationStatus.loading) {
      return;
    }

    final lifecycleState = ref.read(appLifecycleStateProvider);
    if (lifecycleState != AppLifecycleState.resumed) return;

    final db = ref.read(localDbProvider);
    final cooldownIds = <String>{};
    for (final poi in _latestPois) {
      if (await db.isCooldown(poi.id, const Duration(hours: 24))) {
        cooldownIds.add(poi.id);
      }
    }

    final available = _latestPois
        .where((p) =>
            !_sessionPlayedIds.contains(p.id) && !cooldownIds.contains(p.id))
        .toList();

    if (available.isEmpty) {
      AppLogger.info(LogEvents.triggerSkip, {'reason': 'no_candidates_available'});
      return;
    }

    // Dedup guard: skip if user hasn't moved AND POI list is nearly identical
    if (_lastTriggerPosition != null &&
        _currentPosition != null &&
        _lastCandidateIds.isNotEmpty) {
      final moved = haversine(
        _lastTriggerPosition!.latitude,
        _lastTriggerPosition!.longitude,
        _currentPosition!.latitude,
        _currentPosition!.longitude,
      );
      final currentIds = available.map((p) => p.id).toSet();
      final intersectionSize = currentIds.intersection(_lastCandidateIds).length;
      final unionSize = currentIds.union(_lastCandidateIds).length;
      final jaccard = unionSize > 0 ? intersectionSize / unionSize : 0.0;

      if (moved < 30 && jaccard >= 0.8) {
        AppLogger.info(LogEvents.triggerSkip, {
          'reason': 'poi_unchanged',
          'moved_m': moved,
          'jaccard': jaccard,
        });
        return;
      }
    }

    // Update tracking before calling narrate
    _lastTriggerPosition = _currentPosition;
    _lastCandidateIds = available.map((p) => p.id).toSet();

    final session = ref.read(sessionProvider);
    final previous = _lastSelectedPoiId != null
        ? PreviousSelection(
            poiId: _lastSelectedPoiId!,
            poiName: _lastSelectedPoiName,
            script: _lastScript,
          )
        : null;

    AppLogger.info(LogEvents.narrationTrigger, {
      'candidate_count': available.length,
      'has_previous': previous != null,
    });

    ref.read(narrationProvider.notifier).narrate(
          candidates: available,
          persona: session.persona,
          lang: session.lang,
          previousSelection: previous,
        );
  }
}

final triggerProvider = NotifierProvider<TriggerNotifier, TriggerState>(
  TriggerNotifier.new,
);
