import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(appSettingsProvider);
    final notifier = ref.read(appSettingsProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        title: const Text('設定'),
        backgroundColor: const Color(0xFF0F3460),
        foregroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        children: [
          const Text('旁白間隔',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 4),
          const Text('旁白結束後，多久觸發下一段旁白',
              style: TextStyle(color: Colors.grey, fontSize: 13)),
          Slider(
            value: settings.countdownSeconds.toDouble(),
            min: 30,
            max: 300,
            divisions: 27,
            label: '${settings.countdownSeconds} 秒',
            onChanged: (v) => notifier.setCountdownSeconds(v.round()),
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('30 秒', style: TextStyle(color: Colors.grey, fontSize: 12)),
              Text('${settings.countdownSeconds} 秒',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              const Text('300 秒', style: TextStyle(color: Colors.grey, fontSize: 12)),
            ],
          ),
          const SizedBox(height: 32),
          const Text('略過景點後的移動距離',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 4),
          const Text('景點不夠重要時，需要移動多遠才再次觸發',
              style: TextStyle(color: Colors.grey, fontSize: 13)),
          Slider(
            value: settings.skipDisplacementM,
            min: 500,
            max: 5000,
            divisions: 45,
            label: '${(settings.skipDisplacementM / 1000).toStringAsFixed(1)} km',
            onChanged: (v) => notifier.setSkipDisplacement(v),
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('500 m', style: TextStyle(color: Colors.grey, fontSize: 12)),
              Text('${(settings.skipDisplacementM / 1000).toStringAsFixed(1)} km',
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              const Text('5 km', style: TextStyle(color: Colors.grey, fontSize: 12)),
            ],
          ),
        ],
      ),
    );
  }
}
