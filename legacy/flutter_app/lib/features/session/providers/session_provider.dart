import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/tour_playback_queue_provider.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/log_events.dart';
import 'package:geolocator/geolocator.dart';

enum SessionStatus { idle, starting, active, ending }

enum SessionPermissionGuidance {
  backgroundLocationRecommended,
  notificationVisibilityLimited,
}

class SessionState {
  final SessionStatus status;
  final String persona;
  final String lang;
  final int? currentSessionId;
  final List<SessionPermissionGuidance> permissionGuidance;

  const SessionState({
    required this.status,
    this.persona = 'history_uncle',
    this.lang = 'zh-TW',
    this.currentSessionId,
    this.permissionGuidance = const [],
  });

  SessionState copyWith({
    SessionStatus? status,
    String? persona,
    String? lang,
    int? currentSessionId,
    List<SessionPermissionGuidance>? permissionGuidance,
  }) =>
      SessionState(
        status: status ?? this.status,
        persona: persona ?? this.persona,
        lang: lang ?? this.lang,
        currentSessionId: currentSessionId ?? this.currentSessionId,
        permissionGuidance: permissionGuidance ?? this.permissionGuidance,
      );
}

class SessionNotifier extends StateNotifier<SessionState> {
  SessionNotifier(
    this._location,
    this._db, {
    NotificationService? notificationService,
    Future<void> Function()? onStopCompleted,
  })  : _notificationService = notificationService,
        _onStopCompleted = onStopCompleted,
        super(const SessionState(status: SessionStatus.idle));

  final LocationService _location;
  final LocalDb _db;
  final NotificationService? _notificationService;
  final Future<void> Function()? _onStopCompleted;
  DateTime? _sessionStartedAt;

  void setPersona(String persona) {
    if (state.status != SessionStatus.idle) return;
    state = state.copyWith(persona: persona);
  }

  void setLang(String lang) {
    if (state.status != SessionStatus.idle) return;
    state = state.copyWith(lang: lang);
  }

  Future<void> start() async {
    state = state.copyWith(status: SessionStatus.starting);
    final granted = await _location.requestPermission();
    AppLogger.info(LogEvents.locationPermission, {'status': granted ? 'granted' : 'denied'});
    if (!granted) {
      state = state.copyWith(
        status: SessionStatus.idle,
        permissionGuidance: const [],
      );
      return;
    }
    final guidance = await _permissionGuidance();
    final sessionId = await _db.startSession(state.persona, state.lang);
    _location.start();
    _sessionStartedAt = DateTime.now();
    AppLogger.info(LogEvents.sessionStart, {'persona': state.persona, 'lang': state.lang});
    state = state.copyWith(
      status: SessionStatus.active,
      currentSessionId: sessionId,
      permissionGuidance: guidance,
    );
  }

  Future<List<SessionPermissionGuidance>> _permissionGuidance() async {
    final guidance = <SessionPermissionGuidance>[];
    final locationPermission = await _location.checkPermission();
    if (locationPermission == LocationPermission.whileInUse) {
      guidance.add(SessionPermissionGuidance.backgroundLocationRecommended);
    }

    final notificationService = _notificationService;
    if (notificationService != null &&
        !await notificationService.hasNotificationPermission()) {
      guidance.add(SessionPermissionGuidance.notificationVisibilityLimited);
    }
    return guidance;
  }

  Future<void> stop() async {
    state = state.copyWith(status: SessionStatus.ending);
    _location.stop();
    if (state.currentSessionId != null) {
      await _db.endSession(state.currentSessionId!);
    }
    final duration = _sessionStartedAt != null
        ? DateTime.now().difference(_sessionStartedAt!).inSeconds
        : 0;
    AppLogger.info(LogEvents.sessionEnd, {'duration_s': duration});
    _sessionStartedAt = null;
    await _onStopCompleted?.call();
    state = state.copyWith(status: SessionStatus.idle);
  }
}

final sessionProvider =
    StateNotifierProvider<SessionNotifier, SessionState>((ref) {
  return SessionNotifier(
    ref.watch(locationServiceProvider),
    ref.watch(localDbProvider),
    notificationService: ref.watch(notificationServiceProvider),
    onStopCompleted: () => ref.read(tourPlaybackQueueProvider.notifier).clear(),
  );
});
