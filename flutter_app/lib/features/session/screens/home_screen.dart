import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/features/session/widgets/persona_chip.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    final isStarting = session.status == SessionStatus.starting;

    return Scaffold(
      backgroundColor: const Color(0xFF1A1A2E),
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text(
                'AI Tour Guide',
                style: TextStyle(
                  color: Color(0xFF4A9EFF),
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              const PersonaChip(),
              const SizedBox(height: 48),
              ElevatedButton(
                onPressed: isStarting
                    ? null
                    : () => _start(context, ref),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 40,
                    vertical: 16,
                  ),
                ),
                child: isStarting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('開始旅程', style: TextStyle(fontSize: 18)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _start(BuildContext context, WidgetRef ref) async {
    await ref.read(sessionProvider.notifier).start();
    final status = ref.read(sessionProvider).status;
    if (status == SessionStatus.active && context.mounted) {
      context.push('/map');
    } else if (status == SessionStatus.idle && context.mounted) {
      showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('需要定位權限'),
          content: const Text('請在設定中允許「使用 App 期間」的定位權限。'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('確定'),
            ),
          ],
        ),
      );
    }
  }
}
