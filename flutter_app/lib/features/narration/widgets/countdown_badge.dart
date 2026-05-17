import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';

class CountdownBadge extends ConsumerWidget {
  const CountdownBadge({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final triggerState = ref.watch(triggerProvider);

    if (!triggerState.isCountingDown) return const SizedBox.shrink();

    const totalSeconds = 90.0;
    final remaining = triggerState.countdownRemaining;
    final remainingSeconds = remaining.inSeconds;
    final progress = remaining.inMilliseconds / (totalSeconds * 1000);

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
            CircularProgressIndicator(
              value: progress.clamp(0.0, 1.0),
              strokeWidth: 3,
              color: Colors.white,
              backgroundColor: Colors.white24,
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
