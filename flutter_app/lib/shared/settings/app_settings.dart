class AppSettings {
  final double skipDisplacementM;
  final int countdownSeconds;

  const AppSettings({
    this.skipDisplacementM = 1500.0,
    this.countdownSeconds = 90,
  });

  AppSettings copyWith({double? skipDisplacementM, int? countdownSeconds}) =>
      AppSettings(
        skipDisplacementM: skipDisplacementM ?? this.skipDisplacementM,
        countdownSeconds: countdownSeconds ?? this.countdownSeconds,
      );
}
