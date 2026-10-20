import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../host/host_client.dart';
import '../host/host_connection.dart';
import '../host/host_settings.dart';
import '../tour/tour_api.dart';
import '../tour/tour_controller.dart';
import '../tour/traveler_state.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  static String statusLabel(ConnectionStatus status) => switch (status) {
    ConnectionStatus.connected => '主機已連線',
    ConnectionStatus.unreachable => '主機未連線',
    ConnectionStatus.unauthorized => '主機未連線：token 不正確',
    ConnectionStatus.notConfigured => '尚未設定主機位址',
    ConnectionStatus.checking => '檢查主機中…',
  };

  static String stoppedLabel(String reason) => switch (reason) {
    'quota' => 'Claude 額度用完了，先安靜陪你走',
    'llm_budget' => '主機的 Claude 呼叫上限用完了，先安靜陪你走',
    _ => '主機暫時停止準備介紹（$reason）',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(connectionProvider);
    final tour = ref.watch(tourProvider);
    final controller = ref.read(tourProvider.notifier);
    final connected = status == ConnectionStatus.connected;

    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Buddy Tour'),
        actions: [
          IconButton(
            key: const Key('open-settings'),
            icon: const Icon(Icons.settings),
            tooltip: '主機設定',
            onPressed: () => showDialog<void>(
              context: context,
              builder: (_) => const SettingsDialog(),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _StatusChip(status: status),
                if (tour.stoppedReason != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    stoppedLabel(tour.stoppedReason!),
                    key: const Key('stopped-reason'),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 24),
                if (!tour.active && tour.summary != null) ...[
                  TourSummaryCard(summary: tour.summary!),
                  const SizedBox(height: 24),
                ],
                if (!tour.active) const TravelerPicker(),
                const SizedBox(height: 24),
                FilledButton(
                  key: const Key('tour-toggle'),
                  onPressed: tour.active
                      ? controller.end
                      : (connected ? controller.start : null),
                  child: Text(tour.active ? '結束' : '出發'),
                ),
                if (tour.active) ...[
                  const SizedBox(height: 12),
                  OutlinedButton(
                    key: const Key('tour-pause'),
                    onPressed: tour.paused
                        ? controller.resume
                        : controller.pause,
                    child: Text(tour.paused ? '繼續介紹' : '暫停介紹'),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    tour.paused
                        ? '主動介紹已暫停'
                        : (tour.nowPlaying != null
                              ? '正在介紹：${tour.nowPlaying}'
                              : '陪你走，有好內容再開口'),
                    key: const Key('tour-status'),
                  ),
                ],
                if (tour.error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    tour.error!,
                    key: const Key('tour-error'),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final ConnectionStatus status;

  @override
  Widget build(BuildContext context) {
    final connected = status == ConnectionStatus.connected;
    return Chip(
      avatar: Icon(
        connected ? Icons.check_circle : Icons.cloud_off,
        color: connected ? Colors.green : Colors.grey,
      ),
      label: Text(HomeScreen.statusLabel(status)),
    );
  }
}

class SettingsDialog extends ConsumerStatefulWidget {
  const SettingsDialog({super.key});

  @override
  ConsumerState<SettingsDialog> createState() => _SettingsDialogState();
}

class _SettingsDialogState extends ConsumerState<SettingsDialog> {
  late final TextEditingController _url;
  late final TextEditingController _token;

  @override
  void initState() {
    super.initState();
    final current = ref.read(settingsProvider);
    _url = TextEditingController(text: current.url);
    _token = TextEditingController(text: current.token);
  }

  @override
  void dispose() {
    _url.dispose();
    _token.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await ref
        .read(settingsProvider.notifier)
        .save(HostSettings(url: _url.text.trim(), token: _token.text.trim()));
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('主機設定'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            key: const Key('setting-url'),
            controller: _url,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: '主機位址',
              hintText: 'http://100.x.y.z:8765',
            ),
          ),
          TextField(
            key: const Key('setting-token'),
            controller: _token,
            autocorrect: false,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'Token（可留空）'),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('取消'),
        ),
        FilledButton(onPressed: _save, child: const Text('儲存')),
      ],
    );
  }
}

class TravelerPicker extends ConsumerWidget {
  const TravelerPicker({super.key});

  static const _modes = {TravelMode.walking: '走路', TravelMode.driving: '開車'};
  static const _companions = {
    Companions.solo: '一個人',
    Companions.couple: '情侶',
    Companions.family: '家人',
    Companions.friends: '朋友',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final traveler = ref.watch(travelerProvider);
    final notifier = ref.read(travelerProvider.notifier);
    // 回呼裡要讀點選當下的最新狀態：連續快速點選時，build 時的 traveler 已經過期
    TravelerState current() => ref.read(travelerProvider);
    return Column(
      children: [
        SegmentedButton<TravelMode>(
          key: const Key('traveler-mode'),
          segments: [
            for (final entry in _modes.entries)
              ButtonSegment(value: entry.key, label: Text(entry.value)),
          ],
          selected: {traveler.mode},
          onSelectionChanged: (value) =>
              notifier.save(current().copyWith(mode: value.single)),
        ),
        const SizedBox(height: 12),
        Wrap(
          key: const Key('traveler-companions'),
          spacing: 8,
          children: [
            for (final entry in _companions.entries)
              ChoiceChip(
                label: Text(entry.value),
                selected: traveler.companions == entry.key,
                onSelected: (_) =>
                    notifier.save(current().copyWith(companions: entry.key)),
              ),
          ],
        ),
        SwitchListTile(
          key: const Key('traveler-children'),
          title: const Text('有小朋友同行'),
          value: traveler.withChildren,
          onChanged: (value) =>
              notifier.save(current().copyWith(withChildren: value)),
        ),
      ],
    );
  }
}

/// 一趟結束後顯示的用量摘要（設計文件第 11、13 節）。
class TourSummaryCard extends StatelessWidget {
  const TourSummaryCard({super.key, required this.summary});

  final TourSummary summary;

  static const _windowNames = {'five_hour': '5 小時', 'seven_day': '7 天'};

  static String _percent(double value) => '${(value * 100).round()}%';

  static String _change(double value) {
    final points = (value * 100).round();
    return points >= 0 ? '+$points%' : '$points%';
  }

  @override
  Widget build(BuildContext context) {
    final minutes = (summary.durationSeconds / 60).round();
    return Card(
      key: const Key('tour-summary'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('這一趟', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('${summary.narrations} 段介紹，走了約 $minutes 分鐘'),
            Text('呼叫 Claude ${summary.calls} 次'),
            for (final entry in summary.utilization.entries)
              Text(
                '${_windowNames[entry.key] ?? entry.key}額度 '
                '${_percent(entry.value.last)}'
                '（本趟 ${_change(entry.value.change)}）',
              ),
            if (summary.hitLimit)
              Text(
                '這趟撞到額度上限了',
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
    );
  }
}
