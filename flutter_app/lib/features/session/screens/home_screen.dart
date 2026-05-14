import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/features/session/widgets/persona_selector.dart';
import 'package:flutter_app/shared/providers.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    final isStarting = session.status == SessionStatus.starting;

    return Scaffold(
      backgroundColor: const Color(0xFF1A1A2E),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              const SizedBox(height: 32),
              const Text(
                'AI Tour Guide',
                style: TextStyle(
                  color: Color(0xFF4A9EFF),
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'zh-TW', label: Text('中文')),
                  ButtonSegment(value: 'en', label: Text('EN')),
                ],
                selected: {session.lang},
                onSelectionChanged: isStarting
                    ? null
                    : (s) =>
                        ref.read(sessionProvider.notifier).setLang(s.first),
                style: ButtonStyle(
                  foregroundColor: WidgetStateProperty.resolveWith(
                    (states) => states.contains(WidgetState.selected)
                        ? const Color(0xFF4A9EFF)
                        : Colors.white60,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const PersonaSelector(),
              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: isStarting ? null : () => _start(context, ref),
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
                        child:
                            CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('開始旅程', style: TextStyle(fontSize: 18)),
              ),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _start(BuildContext context, WidgetRef ref) async {
    await ref.read(sessionProvider.notifier).start();
    if (!context.mounted) return;
    final status = ref.read(sessionProvider).status;
    if (status == SessionStatus.active) {
      // Check if only whileInUse permission was granted (no background access)
      final permission =
          await ref.read(locationServiceProvider).checkPermission();
      if (!context.mounted) return;
      if (permission == LocationPermission.whileInUse) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('建議開啟「一律允許」背景定位，以便鎖屏時自動推播景點通知。'),
            duration: Duration(seconds: 4),
          ),
        );
      }
      context.push('/map');
    } else if (status == SessionStatus.idle) {
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
