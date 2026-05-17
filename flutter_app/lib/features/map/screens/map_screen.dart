import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/features/narration/widgets/countdown_badge.dart';
import 'package:flutter_app/features/narration/widgets/narration_sheet.dart';
import 'package:flutter_app/features/qa/widgets/push_to_talk_button.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/features/settings/settings_screen.dart';

class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  GoogleMapController? _mapController;
  bool _centeredOnUser = false;

  void _centerOnPosition(Position pos) {
    if (_centeredOnUser) return;
    if (_mapController == null) return;
    _centeredOnUser = true;
    _mapController!.animateCamera(
      CameraUpdate.newLatLngZoom(LatLng(pos.latitude, pos.longitude), 16),
    );
  }

  @override
  void initState() {
    super.initState();
    ref.read(triggerProvider);
  }

  @override
  Widget build(BuildContext context) {
    final position = ref.watch(
      effectivePositionStreamProvider.select((v) => v.valueOrNull),
    );

    ref.listen<AsyncValue<Position>>(
      effectivePositionStreamProvider,
      (_, next) => next.whenData(_centerOnPosition),
    );

    if (position != null) _centerOnPosition(position);

    final initialTarget = position != null
        ? LatLng(position.latitude, position.longitude)
        : const LatLng(0, 0);

    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F3460),
        title: const Row(
          children: [
            Icon(Icons.circle, color: Color(0xFF4A9EFF), size: 12),
            SizedBox(width: 8),
            Text('旅程進行中', style: TextStyle(color: Colors.white)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white),
            tooltip: '設定',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SettingsScreen()),
            ),
          ),
          TextButton(
            onPressed: () async {
              await ref.read(sessionProvider.notifier).stop();
              if (context.mounted) context.pop();
            },
            child: const Text('結束', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
      body: Stack(
        children: [
          GoogleMap(
            initialCameraPosition: CameraPosition(
              target: initialTarget,
              zoom: 16,
            ),
            myLocationEnabled: true,
            myLocationButtonEnabled: true,
            onMapCreated: (c) {
              _mapController = c;
              if (position != null) _centerOnPosition(position);
            },
          ),
          const Align(
            alignment: Alignment.bottomCenter,
            child: NarrationSheet(),
          ),
          const Positioned(
            bottom: 100,
            left: 0,
            right: 0,
            child: Center(child: PushToTalkButton()),
          ),
          const Positioned(
            bottom: 110,
            right: 16,
            child: CountdownBadge(),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _mapController?.dispose();
    super.dispose();
  }
}
