import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/qa/providers/qa_provider.dart';

class NarrationSheet extends ConsumerWidget {
  const NarrationSheet({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(narrationProvider);
    if (state.status == NarrationStatus.idle || state.currentPoi == null) {
      return const SizedBox.shrink();
    }

    return DraggableScrollableSheet(
      initialChildSize: 0.12,
      minChildSize: 0.12,
      maxChildSize: 0.6,
      snap: true,
      snapSizes: const [0.12, 0.6],
      builder: (_, scrollController) => Container(
        decoration: const BoxDecoration(
          color: Color(0xFF16213E),
          borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
        ),
        child: ListView(
          controller: scrollController,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          children: [
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
            // Q&A 字幕區塊（僅在 Q&A 進行中時顯示）
            Consumer(
              builder: (context, ref, _) {
                final qa = ref.watch(qaProvider);
                if (qa.status == QaStatus.idle && qa.transcript.isEmpty) {
                  return const SizedBox.shrink();
                }
                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0A2240),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (qa.transcript.isNotEmpty)
                        Text(
                          qa.transcript,
                          style: const TextStyle(
                            color: Color(0xFF4A9EFF),
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      if (qa.responseText.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            qa.responseText,
                            style: const TextStyle(
                              color: Colors.white70,
                              fontSize: 13,
                              height: 1.5,
                            ),
                          ),
                        ),
                    ],
                  ),
                );
              },
            ),
            Text(
              state.subtitle,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 14,
                height: 1.6,
              ),
            ),
            const SizedBox(height: 12),
            LinearProgressIndicator(
              value: state.progress,
              backgroundColor: const Color(0xFF0A0A2A),
              valueColor:
                  const AlwaysStoppedAnimation<Color>(Color(0xFF4A9EFF)),
            ),
            const SizedBox(height: 12),
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
