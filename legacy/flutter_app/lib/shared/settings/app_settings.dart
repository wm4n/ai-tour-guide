enum TourPlaybackMode { autoPlay, notifyOnly }

enum TourUsageProfile { portable, car }

class AppSettings {
  final double skipDisplacementM;
  final int countdownSeconds;
  final TourPlaybackMode tourPlaybackMode;
  final TourUsageProfile tourUsageProfile;

  const AppSettings({
    this.skipDisplacementM = 1500.0,
    this.countdownSeconds = 90,
    this.tourPlaybackMode = TourPlaybackMode.autoPlay,
    this.tourUsageProfile = TourUsageProfile.portable,
  });

  AppSettings copyWith({
    double? skipDisplacementM,
    int? countdownSeconds,
    TourPlaybackMode? tourPlaybackMode,
    TourUsageProfile? tourUsageProfile,
  }) =>
      AppSettings(
        skipDisplacementM: skipDisplacementM ?? this.skipDisplacementM,
        countdownSeconds: countdownSeconds ?? this.countdownSeconds,
        tourPlaybackMode: tourPlaybackMode ?? this.tourPlaybackMode,
        tourUsageProfile: tourUsageProfile ?? this.tourUsageProfile,
      );
}
