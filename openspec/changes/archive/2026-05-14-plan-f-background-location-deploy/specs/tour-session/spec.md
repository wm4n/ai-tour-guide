## MODIFIED Requirements

### Requirement: Location permission request on journey start
The app SHALL request foreground location permission before activating a session. After permission is granted, `HomeScreen._start()` SHALL call `LocationService.checkPermission()`. If the result is `LocationPermission.whileInUse` (i.e., background not granted), a SnackBar SHALL be shown guiding the user to upgrade to "Always Allow" for the best background experience.

#### Scenario: Permission not yet granted
- **WHEN** session starts for the first time
- **THEN** system permission dialog is shown to the user

#### Scenario: Permission permanently denied
- **WHEN** location permission is permanently denied
- **THEN** HomeScreen shows dialog with 「請在設定中允許定位權限」 message and a button to open system settings

#### Scenario: whileInUse permission shows background guidance SnackBar
- **WHEN** location permission is `whileInUse` after granting
- **THEN** HomeScreen shows a SnackBar with guidance text to enable "Always Allow" for background tracking
