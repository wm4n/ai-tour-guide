import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../host/host_connection.dart';
import '../host/host_settings.dart';
import '../qa/qa_controller.dart';
import '../voice/voice_api.dart';
import '../voice/voice_controller.dart';

/// 旅程畫面右上角的齒輪打開的設定頁：聲音與家裡的主機。
///
/// 旅程 controller 是全域的，這頁開著時旅程照常進行。
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final TextEditingController _url;
  late final TextEditingController _token;

  @override
  void initState() {
    super.initState();
    final current = ref.read(settingsProvider);
    _url = TextEditingController(text: current.url);
    _token = TextEditingController(text: current.token);
    // build 期間不能改 provider：等這一輪建完再讀清單
    Future.microtask(ref.read(voiceProvider.notifier).refresh);
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
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('已儲存')));
    await ref.read(voiceProvider.notifier).refresh(); // 換了主機，聲音也跟著換
  }

  @override
  Widget build(BuildContext context) {
    final heading = Theme.of(context).textTheme.titleMedium;
    return Scaffold(
      appBar: AppBar(title: const Text('設定')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(vertical: 16),
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text('聲音', style: heading),
            ),
            const VoiceSection(),
            const Divider(height: 32),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('家裡的主機', style: heading),
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
                  const SizedBox(height: 16),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton(
                      key: const Key('setting-save'),
                      onPressed: _save,
                      child: const Text('儲存'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 主機上的聲音：頭像、名稱、描述、試聽、使用中打勾。連不上主機時只顯示目前的聲音。
class VoiceSection extends ConsumerWidget {
  const VoiceSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final voices = ref.watch(voiceProvider);
    final catalog = voices.catalog;
    final error = Theme.of(context).colorScheme.error;
    // 發問中再試聽，兩段聲音會疊在一起
    final canPreview = ref.watch(qaProvider).phase == QaPhase.idle;

    final children = <Widget>[];
    if (voices.loading && catalog == null) {
      children.add(const LinearProgressIndicator());
    } else if (catalog == null) {
      final current = voices.current;
      children.add(
        _Note(
          current == null ? '連不上主機，還不知道目前用的是哪個聲音' : '連不上主機，只顯示目前的聲音',
          key: const Key('voices-offline'),
        ),
      );
      if (current != null) {
        children.add(
          _VoiceTile(
            name: current.name,
            displayName: current.displayName,
            current: true,
          ),
        );
      }
    } else {
      if (catalog.currentVoice?.phrasesReady == false) {
        children.add(
          _Note(
            '目前的聲音還沒有準備好固定短句：連不上主機時可能聽不到提示，請在主機上產生',
            key: const Key('voice-current-not-ready'),
            color: error,
          ),
        );
      }
      for (final voice in catalog.voices) {
        children.add(
          _VoiceTile(
            name: voice.name,
            displayName: voice.displayName,
            description: voice.phrasesReady
                ? voice.description
                : _notReady(voice),
            current: voice.name == catalog.current,
            enabled: voice.phrasesReady,
            previewable: true,
            previewing: voices.previewing == voice.name,
            onPreview: voice.phrasesReady && canPreview
                ? () => ref.read(voiceProvider.notifier).preview(voice.name)
                : null,
          ),
        );
      }
    }
    if (voices.error != null) {
      children.add(
        _Note(voices.error!, key: const Key('voice-error'), color: error),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
    );
  }

  static String _notReady(VoiceInfo voice) =>
      voice.description.isEmpty ? '短句尚未準備' : '${voice.description}・短句尚未準備';
}

class _VoiceTile extends StatelessWidget {
  const _VoiceTile({
    required this.name,
    required this.displayName,
    required this.current,
    this.description = '',
    this.enabled = true,
    this.previewable = false,
    this.previewing = false,
    this.onPreview,
  });

  final String name;
  final String displayName;
  final String description;
  final bool current;
  final bool enabled;

  /// 離線時沒有試聽按鈕；有按鈕但 [onPreview] 是 null 時顯示為不能按。
  final bool previewable;
  final bool previewing;
  final VoidCallback? onPreview;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      key: Key('voice-$name'),
      enabled: enabled,
      leading: CircleAvatar(child: Text(displayName.characters.first)),
      title: Text(displayName),
      subtitle: description.isEmpty ? null : Text(description),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (previewable)
            IconButton(
              key: Key('voice-preview-$name'),
              tooltip: '試聽',
              icon: Icon(previewing ? Icons.volume_up : Icons.play_arrow),
              onPressed: onPreview,
            ),
          if (current)
            Icon(
              Icons.check_circle,
              color: Theme.of(context).colorScheme.primary,
            ),
        ],
      ),
    );
  }
}

class _Note extends StatelessWidget {
  const _Note(this.text, {super.key, this.color});

  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
    child: Text(text, style: TextStyle(color: color)),
  );
}
