import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/qa/providers/qa_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';

class PushToTalkButton extends ConsumerWidget {
  const PushToTalkButton({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    if (session.status != SessionStatus.active) return const SizedBox.shrink();

    final qa = ref.watch(qaProvider);

    return GestureDetector(
      onLongPressStart: (_) {
        ref.read(qaProvider.notifier).startRecording();
      },
      onLongPressEnd: (_) {
        final narration = ref.read(narrationProvider);
        final sessionState = ref.read(sessionProvider);
        ref.read(qaProvider.notifier).stopAndSend(
          persona: sessionState.persona,
          lang: sessionState.lang,
          currentPoiId: narration.currentPoi?.id,
          narrationSoFar: narration.subtitle,
        );
      },
      onLongPressCancel: () {
        ref.read(qaProvider.notifier).cancelRecording();
      },
      child: _buildIcon(qa.status),
    );
  }

  Widget _buildIcon(QaStatus status) {
    return switch (status) {
      QaStatus.idle => _CircleButton(
          icon: Icons.mic,
          color: Colors.white,
          backgroundColor: const Color(0xFF4A9EFF),
        ),
      QaStatus.recording => _PulsingButton(),
      QaStatus.processing => const SizedBox(
          width: 56,
          height: 56,
          child: CircularProgressIndicator(
            color: Color(0xFF4A9EFF),
            strokeWidth: 3,
          ),
        ),
      QaStatus.answering => _CircleButton(
          icon: Icons.volume_up,
          color: Colors.white,
          backgroundColor: const Color(0xFF4A9EFF),
        ),
      QaStatus.error => _CircleButton(
          icon: Icons.warning_amber,
          color: Colors.white,
          backgroundColor: Colors.orange,
        ),
    };
  }
}

class _CircleButton extends StatelessWidget {
  const _CircleButton({
    required this.icon,
    required this.color,
    required this.backgroundColor,
  });

  final IconData icon;
  final Color color;
  final Color backgroundColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: backgroundColor,
        boxShadow: const [
          BoxShadow(
            color: Colors.black26,
            blurRadius: 8,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: Icon(icon, color: color, size: 28),
    );
  }
}

class _PulsingButton extends StatefulWidget {
  @override
  State<_PulsingButton> createState() => _PulsingButtonState();
}

class _PulsingButtonState extends State<_PulsingButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 600),
  )..repeat(reverse: true);
  late final Animation<double> _scale =
      Tween<double>(begin: 0.9, end: 1.1).animate(_controller);

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: _scale,
      child: Container(
        width: 56,
        height: 56,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          color: Colors.red,
        ),
        child: const Icon(Icons.mic, color: Colors.white, size: 28),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}
