// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'local_db.dart';

// ignore_for_file: type=lint
class $SessionsTable extends Sessions with TableInfo<$SessionsTable, Session> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $SessionsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
      'id', aliasedName, false,
      hasAutoIncrement: true,
      type: DriftSqlType.int,
      requiredDuringInsert: false,
      defaultConstraints:
          GeneratedColumn.constraintIsAlways('PRIMARY KEY AUTOINCREMENT'));
  static const VerificationMeta _startedAtMeta =
      const VerificationMeta('startedAt');
  @override
  late final GeneratedColumn<int> startedAt = GeneratedColumn<int>(
      'started_at', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  static const VerificationMeta _endedAtMeta =
      const VerificationMeta('endedAt');
  @override
  late final GeneratedColumn<int> endedAt = GeneratedColumn<int>(
      'ended_at', aliasedName, true,
      type: DriftSqlType.int, requiredDuringInsert: false);
  static const VerificationMeta _personaMeta =
      const VerificationMeta('persona');
  @override
  late final GeneratedColumn<String> persona = GeneratedColumn<String>(
      'persona', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _langMeta = const VerificationMeta('lang');
  @override
  late final GeneratedColumn<String> lang = GeneratedColumn<String>(
      'lang', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  @override
  List<GeneratedColumn> get $columns => [id, startedAt, endedAt, persona, lang];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'sessions';
  @override
  VerificationContext validateIntegrity(Insertable<Session> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('started_at')) {
      context.handle(_startedAtMeta,
          startedAt.isAcceptableOrUnknown(data['started_at']!, _startedAtMeta));
    } else if (isInserting) {
      context.missing(_startedAtMeta);
    }
    if (data.containsKey('ended_at')) {
      context.handle(_endedAtMeta,
          endedAt.isAcceptableOrUnknown(data['ended_at']!, _endedAtMeta));
    }
    if (data.containsKey('persona')) {
      context.handle(_personaMeta,
          persona.isAcceptableOrUnknown(data['persona']!, _personaMeta));
    } else if (isInserting) {
      context.missing(_personaMeta);
    }
    if (data.containsKey('lang')) {
      context.handle(
          _langMeta, lang.isAcceptableOrUnknown(data['lang']!, _langMeta));
    } else if (isInserting) {
      context.missing(_langMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  Session map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Session(
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}id'])!,
      startedAt: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}started_at'])!,
      endedAt: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}ended_at']),
      persona: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}persona'])!,
      lang: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}lang'])!,
    );
  }

  @override
  $SessionsTable createAlias(String alias) {
    return $SessionsTable(attachedDatabase, alias);
  }
}

class Session extends DataClass implements Insertable<Session> {
  final int id;
  final int startedAt;
  final int? endedAt;
  final String persona;
  final String lang;
  const Session(
      {required this.id,
      required this.startedAt,
      this.endedAt,
      required this.persona,
      required this.lang});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['started_at'] = Variable<int>(startedAt);
    if (!nullToAbsent || endedAt != null) {
      map['ended_at'] = Variable<int>(endedAt);
    }
    map['persona'] = Variable<String>(persona);
    map['lang'] = Variable<String>(lang);
    return map;
  }

  SessionsCompanion toCompanion(bool nullToAbsent) {
    return SessionsCompanion(
      id: Value(id),
      startedAt: Value(startedAt),
      endedAt: endedAt == null && nullToAbsent
          ? const Value.absent()
          : Value(endedAt),
      persona: Value(persona),
      lang: Value(lang),
    );
  }

  factory Session.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Session(
      id: serializer.fromJson<int>(json['id']),
      startedAt: serializer.fromJson<int>(json['startedAt']),
      endedAt: serializer.fromJson<int?>(json['endedAt']),
      persona: serializer.fromJson<String>(json['persona']),
      lang: serializer.fromJson<String>(json['lang']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'startedAt': serializer.toJson<int>(startedAt),
      'endedAt': serializer.toJson<int?>(endedAt),
      'persona': serializer.toJson<String>(persona),
      'lang': serializer.toJson<String>(lang),
    };
  }

  Session copyWith(
          {int? id,
          int? startedAt,
          Value<int?> endedAt = const Value.absent(),
          String? persona,
          String? lang}) =>
      Session(
        id: id ?? this.id,
        startedAt: startedAt ?? this.startedAt,
        endedAt: endedAt.present ? endedAt.value : this.endedAt,
        persona: persona ?? this.persona,
        lang: lang ?? this.lang,
      );
  Session copyWithCompanion(SessionsCompanion data) {
    return Session(
      id: data.id.present ? data.id.value : this.id,
      startedAt: data.startedAt.present ? data.startedAt.value : this.startedAt,
      endedAt: data.endedAt.present ? data.endedAt.value : this.endedAt,
      persona: data.persona.present ? data.persona.value : this.persona,
      lang: data.lang.present ? data.lang.value : this.lang,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Session(')
          ..write('id: $id, ')
          ..write('startedAt: $startedAt, ')
          ..write('endedAt: $endedAt, ')
          ..write('persona: $persona, ')
          ..write('lang: $lang')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(id, startedAt, endedAt, persona, lang);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Session &&
          other.id == this.id &&
          other.startedAt == this.startedAt &&
          other.endedAt == this.endedAt &&
          other.persona == this.persona &&
          other.lang == this.lang);
}

class SessionsCompanion extends UpdateCompanion<Session> {
  final Value<int> id;
  final Value<int> startedAt;
  final Value<int?> endedAt;
  final Value<String> persona;
  final Value<String> lang;
  const SessionsCompanion({
    this.id = const Value.absent(),
    this.startedAt = const Value.absent(),
    this.endedAt = const Value.absent(),
    this.persona = const Value.absent(),
    this.lang = const Value.absent(),
  });
  SessionsCompanion.insert({
    this.id = const Value.absent(),
    required int startedAt,
    this.endedAt = const Value.absent(),
    required String persona,
    required String lang,
  })  : startedAt = Value(startedAt),
        persona = Value(persona),
        lang = Value(lang);
  static Insertable<Session> custom({
    Expression<int>? id,
    Expression<int>? startedAt,
    Expression<int>? endedAt,
    Expression<String>? persona,
    Expression<String>? lang,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (startedAt != null) 'started_at': startedAt,
      if (endedAt != null) 'ended_at': endedAt,
      if (persona != null) 'persona': persona,
      if (lang != null) 'lang': lang,
    });
  }

  SessionsCompanion copyWith(
      {Value<int>? id,
      Value<int>? startedAt,
      Value<int?>? endedAt,
      Value<String>? persona,
      Value<String>? lang}) {
    return SessionsCompanion(
      id: id ?? this.id,
      startedAt: startedAt ?? this.startedAt,
      endedAt: endedAt ?? this.endedAt,
      persona: persona ?? this.persona,
      lang: lang ?? this.lang,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (startedAt.present) {
      map['started_at'] = Variable<int>(startedAt.value);
    }
    if (endedAt.present) {
      map['ended_at'] = Variable<int>(endedAt.value);
    }
    if (persona.present) {
      map['persona'] = Variable<String>(persona.value);
    }
    if (lang.present) {
      map['lang'] = Variable<String>(lang.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('SessionsCompanion(')
          ..write('id: $id, ')
          ..write('startedAt: $startedAt, ')
          ..write('endedAt: $endedAt, ')
          ..write('persona: $persona, ')
          ..write('lang: $lang')
          ..write(')'))
        .toString();
  }
}

class $NarrationHistoryTable extends NarrationHistory
    with TableInfo<$NarrationHistoryTable, NarrationHistoryData> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $NarrationHistoryTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<int> id = GeneratedColumn<int>(
      'id', aliasedName, false,
      hasAutoIncrement: true,
      type: DriftSqlType.int,
      requiredDuringInsert: false,
      defaultConstraints:
          GeneratedColumn.constraintIsAlways('PRIMARY KEY AUTOINCREMENT'));
  static const VerificationMeta _sessionIdMeta =
      const VerificationMeta('sessionId');
  @override
  late final GeneratedColumn<int> sessionId = GeneratedColumn<int>(
      'session_id', aliasedName, false,
      type: DriftSqlType.int,
      requiredDuringInsert: true,
      defaultConstraints:
          GeneratedColumn.constraintIsAlways('REFERENCES sessions (id)'));
  static const VerificationMeta _poiIdMeta = const VerificationMeta('poiId');
  @override
  late final GeneratedColumn<String> poiId = GeneratedColumn<String>(
      'poi_id', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _poiNameMeta =
      const VerificationMeta('poiName');
  @override
  late final GeneratedColumn<String> poiName = GeneratedColumn<String>(
      'poi_name', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _poiLatMeta = const VerificationMeta('poiLat');
  @override
  late final GeneratedColumn<double> poiLat = GeneratedColumn<double>(
      'poi_lat', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _poiLonMeta = const VerificationMeta('poiLon');
  @override
  late final GeneratedColumn<double> poiLon = GeneratedColumn<double>(
      'poi_lon', aliasedName, false,
      type: DriftSqlType.double, requiredDuringInsert: true);
  static const VerificationMeta _personaMeta =
      const VerificationMeta('persona');
  @override
  late final GeneratedColumn<String> persona = GeneratedColumn<String>(
      'persona', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _langMeta = const VerificationMeta('lang');
  @override
  late final GeneratedColumn<String> lang = GeneratedColumn<String>(
      'lang', aliasedName, false,
      type: DriftSqlType.string, requiredDuringInsert: true);
  static const VerificationMeta _playedAtMeta =
      const VerificationMeta('playedAt');
  @override
  late final GeneratedColumn<int> playedAt = GeneratedColumn<int>(
      'played_at', aliasedName, false,
      type: DriftSqlType.int, requiredDuringInsert: true);
  static const VerificationMeta _completedMeta =
      const VerificationMeta('completed');
  @override
  late final GeneratedColumn<int> completed = GeneratedColumn<int>(
      'completed', aliasedName, false,
      type: DriftSqlType.int,
      requiredDuringInsert: false,
      defaultValue: const Constant(0));
  @override
  List<GeneratedColumn> get $columns => [
        id,
        sessionId,
        poiId,
        poiName,
        poiLat,
        poiLon,
        persona,
        lang,
        playedAt,
        completed
      ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'narration_history';
  @override
  VerificationContext validateIntegrity(
      Insertable<NarrationHistoryData> instance,
      {bool isInserting = false}) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    }
    if (data.containsKey('session_id')) {
      context.handle(_sessionIdMeta,
          sessionId.isAcceptableOrUnknown(data['session_id']!, _sessionIdMeta));
    } else if (isInserting) {
      context.missing(_sessionIdMeta);
    }
    if (data.containsKey('poi_id')) {
      context.handle(
          _poiIdMeta, poiId.isAcceptableOrUnknown(data['poi_id']!, _poiIdMeta));
    } else if (isInserting) {
      context.missing(_poiIdMeta);
    }
    if (data.containsKey('poi_name')) {
      context.handle(_poiNameMeta,
          poiName.isAcceptableOrUnknown(data['poi_name']!, _poiNameMeta));
    } else if (isInserting) {
      context.missing(_poiNameMeta);
    }
    if (data.containsKey('poi_lat')) {
      context.handle(_poiLatMeta,
          poiLat.isAcceptableOrUnknown(data['poi_lat']!, _poiLatMeta));
    } else if (isInserting) {
      context.missing(_poiLatMeta);
    }
    if (data.containsKey('poi_lon')) {
      context.handle(_poiLonMeta,
          poiLon.isAcceptableOrUnknown(data['poi_lon']!, _poiLonMeta));
    } else if (isInserting) {
      context.missing(_poiLonMeta);
    }
    if (data.containsKey('persona')) {
      context.handle(_personaMeta,
          persona.isAcceptableOrUnknown(data['persona']!, _personaMeta));
    } else if (isInserting) {
      context.missing(_personaMeta);
    }
    if (data.containsKey('lang')) {
      context.handle(
          _langMeta, lang.isAcceptableOrUnknown(data['lang']!, _langMeta));
    } else if (isInserting) {
      context.missing(_langMeta);
    }
    if (data.containsKey('played_at')) {
      context.handle(_playedAtMeta,
          playedAt.isAcceptableOrUnknown(data['played_at']!, _playedAtMeta));
    } else if (isInserting) {
      context.missing(_playedAtMeta);
    }
    if (data.containsKey('completed')) {
      context.handle(_completedMeta,
          completed.isAcceptableOrUnknown(data['completed']!, _completedMeta));
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  NarrationHistoryData map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return NarrationHistoryData(
      id: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}id'])!,
      sessionId: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}session_id'])!,
      poiId: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}poi_id'])!,
      poiName: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}poi_name'])!,
      poiLat: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}poi_lat'])!,
      poiLon: attachedDatabase.typeMapping
          .read(DriftSqlType.double, data['${effectivePrefix}poi_lon'])!,
      persona: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}persona'])!,
      lang: attachedDatabase.typeMapping
          .read(DriftSqlType.string, data['${effectivePrefix}lang'])!,
      playedAt: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}played_at'])!,
      completed: attachedDatabase.typeMapping
          .read(DriftSqlType.int, data['${effectivePrefix}completed'])!,
    );
  }

  @override
  $NarrationHistoryTable createAlias(String alias) {
    return $NarrationHistoryTable(attachedDatabase, alias);
  }
}

class NarrationHistoryData extends DataClass
    implements Insertable<NarrationHistoryData> {
  final int id;
  final int sessionId;
  final String poiId;
  final String poiName;
  final double poiLat;
  final double poiLon;
  final String persona;
  final String lang;
  final int playedAt;
  final int completed;
  const NarrationHistoryData(
      {required this.id,
      required this.sessionId,
      required this.poiId,
      required this.poiName,
      required this.poiLat,
      required this.poiLon,
      required this.persona,
      required this.lang,
      required this.playedAt,
      required this.completed});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<int>(id);
    map['session_id'] = Variable<int>(sessionId);
    map['poi_id'] = Variable<String>(poiId);
    map['poi_name'] = Variable<String>(poiName);
    map['poi_lat'] = Variable<double>(poiLat);
    map['poi_lon'] = Variable<double>(poiLon);
    map['persona'] = Variable<String>(persona);
    map['lang'] = Variable<String>(lang);
    map['played_at'] = Variable<int>(playedAt);
    map['completed'] = Variable<int>(completed);
    return map;
  }

  NarrationHistoryCompanion toCompanion(bool nullToAbsent) {
    return NarrationHistoryCompanion(
      id: Value(id),
      sessionId: Value(sessionId),
      poiId: Value(poiId),
      poiName: Value(poiName),
      poiLat: Value(poiLat),
      poiLon: Value(poiLon),
      persona: Value(persona),
      lang: Value(lang),
      playedAt: Value(playedAt),
      completed: Value(completed),
    );
  }

  factory NarrationHistoryData.fromJson(Map<String, dynamic> json,
      {ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return NarrationHistoryData(
      id: serializer.fromJson<int>(json['id']),
      sessionId: serializer.fromJson<int>(json['sessionId']),
      poiId: serializer.fromJson<String>(json['poiId']),
      poiName: serializer.fromJson<String>(json['poiName']),
      poiLat: serializer.fromJson<double>(json['poiLat']),
      poiLon: serializer.fromJson<double>(json['poiLon']),
      persona: serializer.fromJson<String>(json['persona']),
      lang: serializer.fromJson<String>(json['lang']),
      playedAt: serializer.fromJson<int>(json['playedAt']),
      completed: serializer.fromJson<int>(json['completed']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<int>(id),
      'sessionId': serializer.toJson<int>(sessionId),
      'poiId': serializer.toJson<String>(poiId),
      'poiName': serializer.toJson<String>(poiName),
      'poiLat': serializer.toJson<double>(poiLat),
      'poiLon': serializer.toJson<double>(poiLon),
      'persona': serializer.toJson<String>(persona),
      'lang': serializer.toJson<String>(lang),
      'playedAt': serializer.toJson<int>(playedAt),
      'completed': serializer.toJson<int>(completed),
    };
  }

  NarrationHistoryData copyWith(
          {int? id,
          int? sessionId,
          String? poiId,
          String? poiName,
          double? poiLat,
          double? poiLon,
          String? persona,
          String? lang,
          int? playedAt,
          int? completed}) =>
      NarrationHistoryData(
        id: id ?? this.id,
        sessionId: sessionId ?? this.sessionId,
        poiId: poiId ?? this.poiId,
        poiName: poiName ?? this.poiName,
        poiLat: poiLat ?? this.poiLat,
        poiLon: poiLon ?? this.poiLon,
        persona: persona ?? this.persona,
        lang: lang ?? this.lang,
        playedAt: playedAt ?? this.playedAt,
        completed: completed ?? this.completed,
      );
  NarrationHistoryData copyWithCompanion(NarrationHistoryCompanion data) {
    return NarrationHistoryData(
      id: data.id.present ? data.id.value : this.id,
      sessionId: data.sessionId.present ? data.sessionId.value : this.sessionId,
      poiId: data.poiId.present ? data.poiId.value : this.poiId,
      poiName: data.poiName.present ? data.poiName.value : this.poiName,
      poiLat: data.poiLat.present ? data.poiLat.value : this.poiLat,
      poiLon: data.poiLon.present ? data.poiLon.value : this.poiLon,
      persona: data.persona.present ? data.persona.value : this.persona,
      lang: data.lang.present ? data.lang.value : this.lang,
      playedAt: data.playedAt.present ? data.playedAt.value : this.playedAt,
      completed: data.completed.present ? data.completed.value : this.completed,
    );
  }

  @override
  String toString() {
    return (StringBuffer('NarrationHistoryData(')
          ..write('id: $id, ')
          ..write('sessionId: $sessionId, ')
          ..write('poiId: $poiId, ')
          ..write('poiName: $poiName, ')
          ..write('poiLat: $poiLat, ')
          ..write('poiLon: $poiLon, ')
          ..write('persona: $persona, ')
          ..write('lang: $lang, ')
          ..write('playedAt: $playedAt, ')
          ..write('completed: $completed')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(id, sessionId, poiId, poiName, poiLat, poiLon,
      persona, lang, playedAt, completed);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is NarrationHistoryData &&
          other.id == this.id &&
          other.sessionId == this.sessionId &&
          other.poiId == this.poiId &&
          other.poiName == this.poiName &&
          other.poiLat == this.poiLat &&
          other.poiLon == this.poiLon &&
          other.persona == this.persona &&
          other.lang == this.lang &&
          other.playedAt == this.playedAt &&
          other.completed == this.completed);
}

class NarrationHistoryCompanion extends UpdateCompanion<NarrationHistoryData> {
  final Value<int> id;
  final Value<int> sessionId;
  final Value<String> poiId;
  final Value<String> poiName;
  final Value<double> poiLat;
  final Value<double> poiLon;
  final Value<String> persona;
  final Value<String> lang;
  final Value<int> playedAt;
  final Value<int> completed;
  const NarrationHistoryCompanion({
    this.id = const Value.absent(),
    this.sessionId = const Value.absent(),
    this.poiId = const Value.absent(),
    this.poiName = const Value.absent(),
    this.poiLat = const Value.absent(),
    this.poiLon = const Value.absent(),
    this.persona = const Value.absent(),
    this.lang = const Value.absent(),
    this.playedAt = const Value.absent(),
    this.completed = const Value.absent(),
  });
  NarrationHistoryCompanion.insert({
    this.id = const Value.absent(),
    required int sessionId,
    required String poiId,
    required String poiName,
    required double poiLat,
    required double poiLon,
    required String persona,
    required String lang,
    required int playedAt,
    this.completed = const Value.absent(),
  })  : sessionId = Value(sessionId),
        poiId = Value(poiId),
        poiName = Value(poiName),
        poiLat = Value(poiLat),
        poiLon = Value(poiLon),
        persona = Value(persona),
        lang = Value(lang),
        playedAt = Value(playedAt);
  static Insertable<NarrationHistoryData> custom({
    Expression<int>? id,
    Expression<int>? sessionId,
    Expression<String>? poiId,
    Expression<String>? poiName,
    Expression<double>? poiLat,
    Expression<double>? poiLon,
    Expression<String>? persona,
    Expression<String>? lang,
    Expression<int>? playedAt,
    Expression<int>? completed,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (sessionId != null) 'session_id': sessionId,
      if (poiId != null) 'poi_id': poiId,
      if (poiName != null) 'poi_name': poiName,
      if (poiLat != null) 'poi_lat': poiLat,
      if (poiLon != null) 'poi_lon': poiLon,
      if (persona != null) 'persona': persona,
      if (lang != null) 'lang': lang,
      if (playedAt != null) 'played_at': playedAt,
      if (completed != null) 'completed': completed,
    });
  }

  NarrationHistoryCompanion copyWith(
      {Value<int>? id,
      Value<int>? sessionId,
      Value<String>? poiId,
      Value<String>? poiName,
      Value<double>? poiLat,
      Value<double>? poiLon,
      Value<String>? persona,
      Value<String>? lang,
      Value<int>? playedAt,
      Value<int>? completed}) {
    return NarrationHistoryCompanion(
      id: id ?? this.id,
      sessionId: sessionId ?? this.sessionId,
      poiId: poiId ?? this.poiId,
      poiName: poiName ?? this.poiName,
      poiLat: poiLat ?? this.poiLat,
      poiLon: poiLon ?? this.poiLon,
      persona: persona ?? this.persona,
      lang: lang ?? this.lang,
      playedAt: playedAt ?? this.playedAt,
      completed: completed ?? this.completed,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<int>(id.value);
    }
    if (sessionId.present) {
      map['session_id'] = Variable<int>(sessionId.value);
    }
    if (poiId.present) {
      map['poi_id'] = Variable<String>(poiId.value);
    }
    if (poiName.present) {
      map['poi_name'] = Variable<String>(poiName.value);
    }
    if (poiLat.present) {
      map['poi_lat'] = Variable<double>(poiLat.value);
    }
    if (poiLon.present) {
      map['poi_lon'] = Variable<double>(poiLon.value);
    }
    if (persona.present) {
      map['persona'] = Variable<String>(persona.value);
    }
    if (lang.present) {
      map['lang'] = Variable<String>(lang.value);
    }
    if (playedAt.present) {
      map['played_at'] = Variable<int>(playedAt.value);
    }
    if (completed.present) {
      map['completed'] = Variable<int>(completed.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('NarrationHistoryCompanion(')
          ..write('id: $id, ')
          ..write('sessionId: $sessionId, ')
          ..write('poiId: $poiId, ')
          ..write('poiName: $poiName, ')
          ..write('poiLat: $poiLat, ')
          ..write('poiLon: $poiLon, ')
          ..write('persona: $persona, ')
          ..write('lang: $lang, ')
          ..write('playedAt: $playedAt, ')
          ..write('completed: $completed')
          ..write(')'))
        .toString();
  }
}

abstract class _$LocalDb extends GeneratedDatabase {
  _$LocalDb(QueryExecutor e) : super(e);
  $LocalDbManager get managers => $LocalDbManager(this);
  late final $SessionsTable sessions = $SessionsTable(this);
  late final $NarrationHistoryTable narrationHistory =
      $NarrationHistoryTable(this);
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities =>
      [sessions, narrationHistory];
}

typedef $$SessionsTableCreateCompanionBuilder = SessionsCompanion Function({
  Value<int> id,
  required int startedAt,
  Value<int?> endedAt,
  required String persona,
  required String lang,
});
typedef $$SessionsTableUpdateCompanionBuilder = SessionsCompanion Function({
  Value<int> id,
  Value<int> startedAt,
  Value<int?> endedAt,
  Value<String> persona,
  Value<String> lang,
});

final class $$SessionsTableReferences
    extends BaseReferences<_$LocalDb, $SessionsTable, Session> {
  $$SessionsTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static MultiTypedResultKey<$NarrationHistoryTable, List<NarrationHistoryData>>
      _narrationHistoryRefsTable(_$LocalDb db) =>
          MultiTypedResultKey.fromTable(db.narrationHistory,
              aliasName: $_aliasNameGenerator(
                  db.sessions.id, db.narrationHistory.sessionId));

  $$NarrationHistoryTableProcessedTableManager get narrationHistoryRefs {
    final manager =
        $$NarrationHistoryTableTableManager($_db, $_db.narrationHistory)
            .filter((f) => f.sessionId.id.sqlEquals($_itemColumn<int>('id')!));

    final cache =
        $_typedResult.readTableOrNull(_narrationHistoryRefsTable($_db));
    return ProcessedTableManager(
        manager.$state.copyWith(prefetchedData: cache));
  }
}

class $$SessionsTableFilterComposer
    extends Composer<_$LocalDb, $SessionsTable> {
  $$SessionsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get startedAt => $composableBuilder(
      column: $table.startedAt, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get endedAt => $composableBuilder(
      column: $table.endedAt, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get persona => $composableBuilder(
      column: $table.persona, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get lang => $composableBuilder(
      column: $table.lang, builder: (column) => ColumnFilters(column));

  Expression<bool> narrationHistoryRefs(
      Expression<bool> Function($$NarrationHistoryTableFilterComposer f) f) {
    final $$NarrationHistoryTableFilterComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.id,
        referencedTable: $db.narrationHistory,
        getReferencedColumn: (t) => t.sessionId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$NarrationHistoryTableFilterComposer(
              $db: $db,
              $table: $db.narrationHistory,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return f(composer);
  }
}

class $$SessionsTableOrderingComposer
    extends Composer<_$LocalDb, $SessionsTable> {
  $$SessionsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get startedAt => $composableBuilder(
      column: $table.startedAt, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get endedAt => $composableBuilder(
      column: $table.endedAt, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get persona => $composableBuilder(
      column: $table.persona, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get lang => $composableBuilder(
      column: $table.lang, builder: (column) => ColumnOrderings(column));
}

class $$SessionsTableAnnotationComposer
    extends Composer<_$LocalDb, $SessionsTable> {
  $$SessionsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<int> get startedAt =>
      $composableBuilder(column: $table.startedAt, builder: (column) => column);

  GeneratedColumn<int> get endedAt =>
      $composableBuilder(column: $table.endedAt, builder: (column) => column);

  GeneratedColumn<String> get persona =>
      $composableBuilder(column: $table.persona, builder: (column) => column);

  GeneratedColumn<String> get lang =>
      $composableBuilder(column: $table.lang, builder: (column) => column);

  Expression<T> narrationHistoryRefs<T extends Object>(
      Expression<T> Function($$NarrationHistoryTableAnnotationComposer a) f) {
    final $$NarrationHistoryTableAnnotationComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.id,
        referencedTable: $db.narrationHistory,
        getReferencedColumn: (t) => t.sessionId,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$NarrationHistoryTableAnnotationComposer(
              $db: $db,
              $table: $db.narrationHistory,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return f(composer);
  }
}

class $$SessionsTableTableManager extends RootTableManager<
    _$LocalDb,
    $SessionsTable,
    Session,
    $$SessionsTableFilterComposer,
    $$SessionsTableOrderingComposer,
    $$SessionsTableAnnotationComposer,
    $$SessionsTableCreateCompanionBuilder,
    $$SessionsTableUpdateCompanionBuilder,
    (Session, $$SessionsTableReferences),
    Session,
    PrefetchHooks Function({bool narrationHistoryRefs})> {
  $$SessionsTableTableManager(_$LocalDb db, $SessionsTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$SessionsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$SessionsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$SessionsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<int> id = const Value.absent(),
            Value<int> startedAt = const Value.absent(),
            Value<int?> endedAt = const Value.absent(),
            Value<String> persona = const Value.absent(),
            Value<String> lang = const Value.absent(),
          }) =>
              SessionsCompanion(
            id: id,
            startedAt: startedAt,
            endedAt: endedAt,
            persona: persona,
            lang: lang,
          ),
          createCompanionCallback: ({
            Value<int> id = const Value.absent(),
            required int startedAt,
            Value<int?> endedAt = const Value.absent(),
            required String persona,
            required String lang,
          }) =>
              SessionsCompanion.insert(
            id: id,
            startedAt: startedAt,
            endedAt: endedAt,
            persona: persona,
            lang: lang,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) =>
                  (e.readTable(table), $$SessionsTableReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: ({narrationHistoryRefs = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [
                if (narrationHistoryRefs) db.narrationHistory
              ],
              addJoins: null,
              getPrefetchedDataCallback: (items) async {
                return [
                  if (narrationHistoryRefs)
                    await $_getPrefetchedData<Session, $SessionsTable,
                            NarrationHistoryData>(
                        currentTable: table,
                        referencedTable: $$SessionsTableReferences
                            ._narrationHistoryRefsTable(db),
                        managerFromTypedResult: (p0) =>
                            $$SessionsTableReferences(db, table, p0)
                                .narrationHistoryRefs,
                        referencedItemsForCurrentItem:
                            (item, referencedItems) => referencedItems
                                .where((e) => e.sessionId == item.id),
                        typedResults: items)
                ];
              },
            );
          },
        ));
}

typedef $$SessionsTableProcessedTableManager = ProcessedTableManager<
    _$LocalDb,
    $SessionsTable,
    Session,
    $$SessionsTableFilterComposer,
    $$SessionsTableOrderingComposer,
    $$SessionsTableAnnotationComposer,
    $$SessionsTableCreateCompanionBuilder,
    $$SessionsTableUpdateCompanionBuilder,
    (Session, $$SessionsTableReferences),
    Session,
    PrefetchHooks Function({bool narrationHistoryRefs})>;
typedef $$NarrationHistoryTableCreateCompanionBuilder
    = NarrationHistoryCompanion Function({
  Value<int> id,
  required int sessionId,
  required String poiId,
  required String poiName,
  required double poiLat,
  required double poiLon,
  required String persona,
  required String lang,
  required int playedAt,
  Value<int> completed,
});
typedef $$NarrationHistoryTableUpdateCompanionBuilder
    = NarrationHistoryCompanion Function({
  Value<int> id,
  Value<int> sessionId,
  Value<String> poiId,
  Value<String> poiName,
  Value<double> poiLat,
  Value<double> poiLon,
  Value<String> persona,
  Value<String> lang,
  Value<int> playedAt,
  Value<int> completed,
});

final class $$NarrationHistoryTableReferences extends BaseReferences<_$LocalDb,
    $NarrationHistoryTable, NarrationHistoryData> {
  $$NarrationHistoryTableReferences(
      super.$_db, super.$_table, super.$_typedResult);

  static $SessionsTable _sessionIdTable(_$LocalDb db) =>
      db.sessions.createAlias(
          $_aliasNameGenerator(db.narrationHistory.sessionId, db.sessions.id));

  $$SessionsTableProcessedTableManager get sessionId {
    final $_column = $_itemColumn<int>('session_id')!;

    final manager = $$SessionsTableTableManager($_db, $_db.sessions)
        .filter((f) => f.id.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_sessionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
        manager.$state.copyWith(prefetchedData: [item]));
  }
}

class $$NarrationHistoryTableFilterComposer
    extends Composer<_$LocalDb, $NarrationHistoryTable> {
  $$NarrationHistoryTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<int> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get poiId => $composableBuilder(
      column: $table.poiId, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get poiName => $composableBuilder(
      column: $table.poiName, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get poiLat => $composableBuilder(
      column: $table.poiLat, builder: (column) => ColumnFilters(column));

  ColumnFilters<double> get poiLon => $composableBuilder(
      column: $table.poiLon, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get persona => $composableBuilder(
      column: $table.persona, builder: (column) => ColumnFilters(column));

  ColumnFilters<String> get lang => $composableBuilder(
      column: $table.lang, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get playedAt => $composableBuilder(
      column: $table.playedAt, builder: (column) => ColumnFilters(column));

  ColumnFilters<int> get completed => $composableBuilder(
      column: $table.completed, builder: (column) => ColumnFilters(column));

  $$SessionsTableFilterComposer get sessionId {
    final $$SessionsTableFilterComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.sessionId,
        referencedTable: $db.sessions,
        getReferencedColumn: (t) => t.id,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$SessionsTableFilterComposer(
              $db: $db,
              $table: $db.sessions,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }
}

class $$NarrationHistoryTableOrderingComposer
    extends Composer<_$LocalDb, $NarrationHistoryTable> {
  $$NarrationHistoryTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<int> get id => $composableBuilder(
      column: $table.id, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get poiId => $composableBuilder(
      column: $table.poiId, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get poiName => $composableBuilder(
      column: $table.poiName, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get poiLat => $composableBuilder(
      column: $table.poiLat, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<double> get poiLon => $composableBuilder(
      column: $table.poiLon, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get persona => $composableBuilder(
      column: $table.persona, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<String> get lang => $composableBuilder(
      column: $table.lang, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get playedAt => $composableBuilder(
      column: $table.playedAt, builder: (column) => ColumnOrderings(column));

  ColumnOrderings<int> get completed => $composableBuilder(
      column: $table.completed, builder: (column) => ColumnOrderings(column));

  $$SessionsTableOrderingComposer get sessionId {
    final $$SessionsTableOrderingComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.sessionId,
        referencedTable: $db.sessions,
        getReferencedColumn: (t) => t.id,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$SessionsTableOrderingComposer(
              $db: $db,
              $table: $db.sessions,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }
}

class $$NarrationHistoryTableAnnotationComposer
    extends Composer<_$LocalDb, $NarrationHistoryTable> {
  $$NarrationHistoryTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<int> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get poiId =>
      $composableBuilder(column: $table.poiId, builder: (column) => column);

  GeneratedColumn<String> get poiName =>
      $composableBuilder(column: $table.poiName, builder: (column) => column);

  GeneratedColumn<double> get poiLat =>
      $composableBuilder(column: $table.poiLat, builder: (column) => column);

  GeneratedColumn<double> get poiLon =>
      $composableBuilder(column: $table.poiLon, builder: (column) => column);

  GeneratedColumn<String> get persona =>
      $composableBuilder(column: $table.persona, builder: (column) => column);

  GeneratedColumn<String> get lang =>
      $composableBuilder(column: $table.lang, builder: (column) => column);

  GeneratedColumn<int> get playedAt =>
      $composableBuilder(column: $table.playedAt, builder: (column) => column);

  GeneratedColumn<int> get completed =>
      $composableBuilder(column: $table.completed, builder: (column) => column);

  $$SessionsTableAnnotationComposer get sessionId {
    final $$SessionsTableAnnotationComposer composer = $composerBuilder(
        composer: this,
        getCurrentColumn: (t) => t.sessionId,
        referencedTable: $db.sessions,
        getReferencedColumn: (t) => t.id,
        builder: (joinBuilder,
                {$addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer}) =>
            $$SessionsTableAnnotationComposer(
              $db: $db,
              $table: $db.sessions,
              $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
              joinBuilder: joinBuilder,
              $removeJoinBuilderFromRootComposer:
                  $removeJoinBuilderFromRootComposer,
            ));
    return composer;
  }
}

class $$NarrationHistoryTableTableManager extends RootTableManager<
    _$LocalDb,
    $NarrationHistoryTable,
    NarrationHistoryData,
    $$NarrationHistoryTableFilterComposer,
    $$NarrationHistoryTableOrderingComposer,
    $$NarrationHistoryTableAnnotationComposer,
    $$NarrationHistoryTableCreateCompanionBuilder,
    $$NarrationHistoryTableUpdateCompanionBuilder,
    (NarrationHistoryData, $$NarrationHistoryTableReferences),
    NarrationHistoryData,
    PrefetchHooks Function({bool sessionId})> {
  $$NarrationHistoryTableTableManager(
      _$LocalDb db, $NarrationHistoryTable table)
      : super(TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$NarrationHistoryTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$NarrationHistoryTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$NarrationHistoryTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback: ({
            Value<int> id = const Value.absent(),
            Value<int> sessionId = const Value.absent(),
            Value<String> poiId = const Value.absent(),
            Value<String> poiName = const Value.absent(),
            Value<double> poiLat = const Value.absent(),
            Value<double> poiLon = const Value.absent(),
            Value<String> persona = const Value.absent(),
            Value<String> lang = const Value.absent(),
            Value<int> playedAt = const Value.absent(),
            Value<int> completed = const Value.absent(),
          }) =>
              NarrationHistoryCompanion(
            id: id,
            sessionId: sessionId,
            poiId: poiId,
            poiName: poiName,
            poiLat: poiLat,
            poiLon: poiLon,
            persona: persona,
            lang: lang,
            playedAt: playedAt,
            completed: completed,
          ),
          createCompanionCallback: ({
            Value<int> id = const Value.absent(),
            required int sessionId,
            required String poiId,
            required String poiName,
            required double poiLat,
            required double poiLon,
            required String persona,
            required String lang,
            required int playedAt,
            Value<int> completed = const Value.absent(),
          }) =>
              NarrationHistoryCompanion.insert(
            id: id,
            sessionId: sessionId,
            poiId: poiId,
            poiName: poiName,
            poiLat: poiLat,
            poiLon: poiLon,
            persona: persona,
            lang: lang,
            playedAt: playedAt,
            completed: completed,
          ),
          withReferenceMapper: (p0) => p0
              .map((e) => (
                    e.readTable(table),
                    $$NarrationHistoryTableReferences(db, table, e)
                  ))
              .toList(),
          prefetchHooksCallback: ({sessionId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins: <
                  T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic>>(state) {
                if (sessionId) {
                  state = state.withJoin(
                    currentTable: table,
                    currentColumn: table.sessionId,
                    referencedTable:
                        $$NarrationHistoryTableReferences._sessionIdTable(db),
                    referencedColumn: $$NarrationHistoryTableReferences
                        ._sessionIdTable(db)
                        .id,
                  ) as T;
                }

                return state;
              },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ));
}

typedef $$NarrationHistoryTableProcessedTableManager = ProcessedTableManager<
    _$LocalDb,
    $NarrationHistoryTable,
    NarrationHistoryData,
    $$NarrationHistoryTableFilterComposer,
    $$NarrationHistoryTableOrderingComposer,
    $$NarrationHistoryTableAnnotationComposer,
    $$NarrationHistoryTableCreateCompanionBuilder,
    $$NarrationHistoryTableUpdateCompanionBuilder,
    (NarrationHistoryData, $$NarrationHistoryTableReferences),
    NarrationHistoryData,
    PrefetchHooks Function({bool sessionId})>;

class $LocalDbManager {
  final _$LocalDb _db;
  $LocalDbManager(this._db);
  $$SessionsTableTableManager get sessions =>
      $$SessionsTableTableManager(_db, _db.sessions);
  $$NarrationHistoryTableTableManager get narrationHistory =>
      $$NarrationHistoryTableTableManager(_db, _db.narrationHistory);
}
