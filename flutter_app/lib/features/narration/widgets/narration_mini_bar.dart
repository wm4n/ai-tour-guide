import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';

class NarrationMiniBar extends ConsumerWidget {
  const NarrationMiniBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(narrationProvider);
    if (state.status == NarrationStatus.idle || state.currentPoi == null) {
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
            onPressed: () => ref.read(narrationProvider.notifier).skip(),
          ),
        ],
      ),
    );
  }
}
