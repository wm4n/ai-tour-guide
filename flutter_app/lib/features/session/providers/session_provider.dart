import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

enum SessionStatus { idle, starting, active, ending }

class SessionState {
  final SessionStatus status;
  final String persona;
  final String lang;
  final int? currentSessionId;

  const SessionState({
    required this.status,
    this.persona = 'history_uncle',
    this.lang = 'zh-TW',
    this.currentSessionId,
  });

  SessionState copyWith({
    SessionStatus? status,
    String? persona,
    String? lang,
    int? currentSessionId,
  }) =>
      SessionState(
        status: status ?? this.status,
        persona: persona ?? this.persona,
        lang: lang ?? this.lang,
        currentSessionId: currentSessionId ?? this.currentSessionId,
      );
}

class SessionNotifier extends StateNotifier<SessionState> {
  SessionNotifier(this._location, this._db)
      : super(const SessionState(status: SessionStatus.idle));

  final LocationService _location;
  final LocalDb _db;

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
    if (!granted) {
      state = state.copyWith(status: SessionStatus.idle);
      return;
    }
    final sessionId = await _db.startSession(state.persona, state.lang);
    _location.start();
    state = state.copyWith(
      status: SessionStatus.active,
      currentSessionId: sessionId,
    );
  }

  Future<void> stop() async {
    state = state.copyWith(status: SessionStatus.ending);
    _location.stop();
    if (state.currentSessionId != null) {
      await _db.endSession(state.currentSessionId!);
    }
    state = state.copyWith(status: SessionStatus.idle);
  }
}

final sessionProvider =
    StateNotifierProvider<SessionNotifier, SessionState>((ref) {
  return SessionNotifier(
    ref.watch(locationServiceProvider),
    ref.watch(localDbProvider),
  );
});
