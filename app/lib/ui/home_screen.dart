import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../host/host_client.dart';
import '../host/host_connection.dart';
import '../qa/qa_controller.dart';
import '../qa/speech_recognizer.dart';
import '../tour/tour_api.dart';
import '../tour/tour_controller.dart';
import '../tour/traveler_state.dart';
import '../voice/voice_controller.dart';
import 'settings_screen.dart';

class HomeScreen extends ConsumerStatefulWidget {
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
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // 使用者可能剛到「設定」把定位改成「永遠」：回到前景時重讀，畫面的提醒才跟得上
    if (state == AppLifecycleState.resumed) {
      unawaited(ref.read(tourProvider.notifier).refreshLocationAccess());
    }
  }

  @override
  Widget build(BuildContext context) {
    // 連上主機（含 App 啟動後第一次）就跟上主機的目前聲音，手機裡沒有它的短句就補下載
    ref.listen(connectionProvider, (previous, next) {
      if (next == ConnectionStatus.connected &&
          previous != ConnectionStatus.connected) {
        unawaited(ref.read(voiceProvider.notifier).refresh());
      }
    });
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
            tooltip: '設定',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SettingsScreen()),
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
                if (tour.active &&
                    !tour.locationAccess.keepsWorkingWhenLocked) ...[
                  const SizedBox(height: 12),
                  Text(
                    '定位目前只允許「使用 App 期間」：手機鎖定螢幕時可能收不到位置。'
                    '請到「設定 → Buddy Tour → 位置」改成「永遠」。',
                    key: const Key('location-hint'),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                if (tour.stoppedReason != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    HomeScreen.stoppedLabel(tour.stoppedReason!),
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
                  const SizedBox(height: 24),
                  const AskButton(),
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

/// 按住說話發問（設計文件第 8 節）：按下開始聽，放開就送出並等答案；答案以語音播出。
///
/// 用 [Listener] 而不是長按手勢：一按下就要開麥克風，不等長按的判定時間。
class AskButton extends ConsumerWidget {
  const AskButton({super.key});

  static String _label(QaPhase phase) => switch (phase) {
    QaPhase.idle => '按住說話',
    QaPhase.listening => '聽你說…',
    QaPhase.photographing => '拍照中…',
    QaPhase.asking => '想一想…',
    QaPhase.answering => '回答中…',
  };

  static String _modeLabel(RecognitionMode mode) => switch (mode) {
    RecognitionMode.onDevice => '本機辨識',
    RecognitionMode.online => '線上辨識（語音會送到 Apple）',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final qa = ref.watch(qaProvider);
    final controller = ref.read(qaProvider.notifier);
    final scheme = Theme.of(context).colorScheme;
    final listening = qa.phase == QaPhase.listening;
    final idle = qa.phase == QaPhase.idle;
    return Column(
      children: [
        Listener(
          key: const Key('ask-button'),
          behavior: HitTestBehavior.opaque,
          onPointerDown: (_) => controller.press(),
          onPointerUp: (_) => controller.release(),
          // 手指被系統奪走（例如被當成捲動）：不要把講到一半的話送出去
          onPointerCancel: (_) {
            // 只有「按住中」才丟掉錄音；答案播放中碰一下又被取消，不該停掉答案
            if (ref.read(qaProvider).phase == QaPhase.listening) {
              controller.cancel();
            }
          },
          child: Container(
            width: 160,
            height: 160,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: listening
                  ? scheme.error
                  : (idle ? scheme.primary : scheme.surfaceContainerHighest),
            ),
            child: Text(
              _label(qa.phase),
              style: TextStyle(
                fontSize: 18,
                color: listening
                    ? scheme.onError
                    : (idle ? scheme.onPrimary : scheme.onSurfaceVariant),
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          key: const Key('photo-button'),
          onPressed: idle ? controller.askWithPhoto : null,
          icon: const Icon(Icons.photo_camera),
          label: const Text('拍照問'),
        ),
        if (qa.mode != null && !idle) ...[
          const SizedBox(height: 8),
          Text(
            _modeLabel(qa.mode!),
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
        if (qa.searchingWeb && !idle) ...[
          const SizedBox(height: 8),
          const Text('正在上網查…', key: Key('qa-searching')),
        ],
        if (qa.quotaExhausted) ...[
          const SizedBox(height: 8),
          Text(
            'Claude 額度用完了，這題先不回答',
            key: const Key('qa-quota'),
            style: TextStyle(color: scheme.error),
          ),
        ],
        if (qa.error != null) ...[
          const SizedBox(height: 8),
          Text(
            qa.error!,
            key: const Key('qa-error'),
            style: TextStyle(color: scheme.error),
          ),
        ],
      ],
    );
  }
}
