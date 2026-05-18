import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

class CountdownBadge extends ConsumerWidget {
  const CountdownBadge({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final triggerState = ref.watch(triggerProvider);

    if (triggerState.isWaitingForDisplacement) {
      return _DisplacementBadge(state: triggerState);
    }

    if (!triggerState.isCountingDown) return const SizedBox.shrink();

    final settings = ref.watch(appSettingsProvider);
    final totalMs = settings.countdownSeconds * 1000.0;
    final remaining = triggerState.countdownRemaining;
    final remainingSeconds = remaining.inSeconds;
    final progress = remaining.inMilliseconds / totalMs;

    return GestureDetector(
      onTap: () => ref.read(triggerProvider.notifier).skipCountdown(),
      child: Container(
        width: 72,
        height: 72,
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.7),
          shape: BoxShape.circle,
        ),
        child: Stack(
          alignment: Alignment.center,
          children: [
            SizedBox.expand(
              child: CircularProgressIndicator(
                value: progress.clamp(0.0, 1.0),
                strokeWidth: 3,
                color: Colors.white,
                backgroundColor: Colors.white24,
              ),
            ),
            Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '$remainingSeconds',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const Text(
                  '下一個',
                  style: TextStyle(color: Colors.white70, fontSize: 9),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _DisplacementBadge extends ConsumerWidget {
  final TriggerState state;
  const _DisplacementBadge({required this.state});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(appSettingsProvider);
    final threshold = settings.skipDisplacementM;
    final moved = state.movedMeters;
    final progress = (moved / threshold).clamp(0.0, 1.0);
    final movedKm = (moved / 1000).toStringAsFixed(1);
    final thresholdKm = (threshold / 1000).toStringAsFixed(1);

    return Container(
      width: 72,
      height: 72,
      decoration: BoxDecoration(
        color: Colors.grey.shade800.withValues(alpha: 0.85),
        shape: BoxShape.circle,
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox.expand(
            child: CircularProgressIndicator(
              value: progress,
              strokeWidth: 3,
              color: Colors.white70,
              backgroundColor: Colors.white24,
            ),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.directions_walk, color: Colors.white70, size: 20),
              Text(
                '$movedKm/$thresholdKm',
                style: const TextStyle(
                    color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold),
              ),
              const Text(
                'km',
                style: TextStyle(color: Colors.white54, fontSize: 7),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
