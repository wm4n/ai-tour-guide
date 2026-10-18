import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/haversine.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

final tourPlaybackClockProvider = Provider<DateTime Function()>((ref) {
  return DateTime.now;
});

class QueuedPoi {
  final POI poi;
  final DateTime queuedAt;

  const QueuedPoi({
    required this.poi,
    required this.queuedAt,
  });
}

class TourPlaybackQueueState {
  final POI? currentPoi;
  final List<QueuedPoi> queue;

  const TourPlaybackQueueState({
    this.currentPoi,
    this.queue = const [],
  });

  POI? get nextPoi => queue.isEmpty ? null : queue.first.poi;
  int get queuedCount => queue.length;

  TourPlaybackQueueState copyWith({
    POI? currentPoi,
    bool clearCurrentPoi = false,
    List<QueuedPoi>? queue,
  }) {
    return TourPlaybackQueueState(
      currentPoi: clearCurrentPoi ? null : currentPoi ?? this.currentPoi,
      queue: queue ?? this.queue,
    );
  }
}

class TourPlaybackQueueNotifier extends Notifier<TourPlaybackQueueState> {
  static const itemTtl = Duration(minutes: 10);

  @override
  TourPlaybackQueueState build() {
    final audio = ref.read(audioPlayerServiceProvider);
    audio.setNextHandler(() => skipToNext());
    ref.onDispose(() {
      audio.setNextHandler(null);
    });
    ref.listen<NarrationState>(narrationProvider, (prev, next) {
      final becameIdle =
          (prev?.status == NarrationStatus.loading ||
                  prev?.status == NarrationStatus.playing ||
                  prev?.status == NarrationStatus.paused) &&
              next.status == NarrationStatus.idle;
      final errored = (prev?.status == NarrationStatus.loading ||
              prev?.status == NarrationStatus.playing) &&
          next.status == NarrationStatus.error;
      if (becameIdle || errored) {
        state = state.copyWith(clearCurrentPoi: true);
        unawaited(_playNextValid());
      }
    });
    return const TourPlaybackQueueState();
  }

  Future<void> enqueue({required List<POI> candidates}) async {
    final settings = ref.read(appSettingsProvider);
    if (settings.tourPlaybackMode == TourPlaybackMode.notifyOnly) return;

    final knownIds = <String>{
      if (state.currentPoi != null) state.currentPoi!.id,
      ...state.queue.map((item) => item.poi.id),
    };
    final now = ref.read(tourPlaybackClockProvider)();
    final additions = <QueuedPoi>[];
    for (final poi in candidates) {
      if (knownIds.add(poi.id)) {
        additions.add(QueuedPoi(poi: poi, queuedAt: now));
      }
    }
    if (additions.isNotEmpty) {
      state = state.copyWith(queue: [...state.queue, ...additions]);
    }
    await _playNextValid();
  }

  Future<void> skipToNext() async {
    state = state.copyWith(clearCurrentPoi: true);
    await ref.read(narrationProvider.notifier).stopCurrent();
    await _playNextValid();
  }

  Future<void> clear() async {
    state = const TourPlaybackQueueState();
    await ref.read(narrationProvider.notifier).stopCurrent();
  }

  Future<void> _playNextValid() async {
    final narration = ref.read(narrationProvider);
    if (narration.status == NarrationStatus.loading ||
        narration.status == NarrationStatus.playing ||
        narration.status == NarrationStatus.paused ||
        state.currentPoi != null) {
      return;
    }

    final next = _takeNextValid();
    if (next == null) return;

    state = state.copyWith(
      currentPoi: next.$1.poi,
      queue: next.$2,
    );

    final session = ref.read(sessionProvider);
    await ref.read(audioPlayerServiceProvider).setCurrentItem(
          id: next.$1.poi.id,
          title: next.$1.poi.name,
          subtitle: 'AI Tour Guide',
        );
    await ref.read(narrationProvider.notifier).narrate(
          candidates: [next.$1.poi],
          persona: session.persona,
          lang: session.lang,
          previousSelection: null,
        );
  }

  (QueuedPoi, List<QueuedPoi>)? _takeNextValid() {
    final queue = state.queue;
    final remaining = <QueuedPoi>[];

    for (var i = 0; i < queue.length; i++) {
      final item = queue[i];
      if (!_isEligible(item)) continue;
      remaining.addAll(queue.skip(i + 1));
      return (item, remaining);
    }

    if (queue.isNotEmpty) {
      state = state.copyWith(queue: const []);
    }
    return null;
  }

  bool _isEligible(QueuedPoi item) {
    final now = ref.read(tourPlaybackClockProvider)();
    if (now.difference(item.queuedAt) > itemTtl) return false;

    final position = ref.read(locationServiceProvider).latestPosition;
    if (position == null) return true;

    final settings = ref.read(appSettingsProvider);
    final maxDistance = settings.tourUsageProfile == TourUsageProfile.car
        ? 800.0
        : 250.0;
    final distance = haversine(
      position.latitude,
      position.longitude,
      item.poi.lat,
      item.poi.lon,
    );
    return distance <= maxDistance;
  }
}

final tourPlaybackQueueProvider =
    NotifierProvider<TourPlaybackQueueNotifier, TourPlaybackQueueState>(
  TourPlaybackQueueNotifier.new,
);
