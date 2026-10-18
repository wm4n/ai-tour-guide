import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../host/host_client.dart';
import '../host/host_connection.dart';
import '../host/host_settings.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  static String statusLabel(ConnectionStatus status) => switch (status) {
    ConnectionStatus.connected => '主機已連線',
    ConnectionStatus.unreachable => '主機未連線',
    ConnectionStatus.unauthorized => '主機未連線：token 不正確',
    ConnectionStatus.notConfigured => '尚未設定主機位址',
    ConnectionStatus.checking => '檢查主機中…',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = ref.watch(connectionProvider);
    final active = ref.watch(tourActiveProvider);
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
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _StatusChip(status: status),
            const SizedBox(height: 32),
            FilledButton(
              key: const Key('tour-toggle'),
              onPressed: connected
                  ? ref.read(tourActiveProvider.notifier).toggle
                  : null,
              child: Text(active ? '結束' : '出發'),
            ),
          ],
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
