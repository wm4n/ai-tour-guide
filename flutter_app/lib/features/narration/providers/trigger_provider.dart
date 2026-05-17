import 'dart:async';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/log_events.dart';

class TriggerState {
  final bool isCountingDown;
  final Duration countdownRemaining;

  const TriggerState({
    this.isCountingDown = false,
    this.countdownRemaining = Duration.zero,
  });

  TriggerState copyWith({bool? isCountingDown, Duration? countdownRemaining}) =>
      TriggerState(
        isCountingDown: isCountingDown ?? this.isCountingDown,
        countdownRemaining: countdownRemaining ?? this.countdownRemaining,
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

  static const _countdownDuration = Duration(seconds: 90);

  @override
  TriggerState build() {
    ref.listen<AsyncValue<List<POI>>>(
      poiProvider,
      (_, next) => next.whenData((pois) {
        _latestPois = pois;
        AppLogger.info(LogEvents.triggerEval, {'layer': 'pois_updated', 'count': pois.length});
        // Fire immediately on first POI load if never played
        if (!_hasEverFired && pois.isNotEmpty && !state.isCountingDown) {
          final narState = ref.read(narrationProvider);
          if (narState.status == NarrationStatus.idle) {
            _doCandidatesRequest().catchError((Object e, StackTrace st) {
              AppLogger.error(LogEvents.apiError, {'context': 'initial_trigger'}, e, st);
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
        // Start countdown when narration completes
        if (prev?.status == NarrationStatus.playing && next.status == NarrationStatus.idle) {
          _lastSelectedPoiId = next.currentPoi?.id;
          _lastSelectedPoiName = next.currentPoi?.name ?? '';
          _lastScript = next.scriptBuffer;
          _startCountdown();
        }
        // Also start countdown on error to avoid getting stuck
        if ((prev?.status == NarrationStatus.loading || prev?.status == NarrationStatus.playing) &&
            next.status == NarrationStatus.error) {
          _startCountdown();
        }
      },
    );

    ref.onDispose(() {
      _cooldownTimer?.cancel();
    });

    return const TriggerState();
  }

  void _startCountdown() {
    _cooldownTimer?.cancel();
    _cooldownUntil = DateTime.now().add(_countdownDuration);
    state = const TriggerState(isCountingDown: true, countdownRemaining: _countdownDuration);

    _cooldownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      final remaining = _cooldownUntil!.difference(DateTime.now());
      if (remaining <= Duration.zero) {
        timer.cancel();
        _cooldownTimer = null;
        _cooldownUntil = null;
        state = const TriggerState();
        _doCandidatesRequest().catchError((Object e, StackTrace st) {
          AppLogger.error(LogEvents.apiError, {'context': 'countdown_expired'}, e, st);
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
        .where((p) => !_sessionPlayedIds.contains(p.id) && !cooldownIds.contains(p.id))
        .toList();

    if (available.isEmpty) {
      AppLogger.info(LogEvents.triggerSkip, {'reason': 'no_candidates_available'});
      return;
    }

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
