import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/trigger_engine.dart';
import 'package:flutter_app/features/session/persona_data.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
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

    final session = ref.read(sessionProvider);
    final personaInfo = kPersonas.firstWhere(
      (p) => p.id == session.persona,
      orElse: () => kPersonas.first,
    );
    final triggerRadiusM = personaInfo.defaultTriggerRadiusM.toDouble();

    final triggers = TriggerEngine.evaluate(
      userLat: position.latitude,
      userLon: position.longitude,
      pois: pois.cast(),
      playedPoiIds: _sessionPlayedIds,
      cooldownPoiIds: cooldownIds,
      radiusM: triggerRadiusM,
    );

    if (triggers.isNotEmpty) {
      final poi = triggers.first;
      _sessionPlayedIds.add(poi.id);
      final lifecycleState = ref.read(appLifecycleStateProvider);
      if (lifecycleState == AppLifecycleState.resumed) {
        ref.read(narrationProvider.notifier).narrate(
          poi,
          persona: session.persona,
          lang: session.lang,
        );
      } else {
        await ref.read(notificationServiceProvider).showPoiTrigger(poi);
      }
    }
  }
}

final triggerProvider = NotifierProvider<TriggerNotifier, void>(
  TriggerNotifier.new,
);
