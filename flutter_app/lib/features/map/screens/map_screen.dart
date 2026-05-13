import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/map/widgets/poi_marker.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/features/narration/widgets/narration_sheet.dart';
import 'package:flutter_app/features/qa/widgets/push_to_talk_button.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';

class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  GoogleMapController? _mapController;

  @override
  void initState() {
    super.initState();
    ref.read(triggerProvider);
  }

  @override
  Widget build(BuildContext context) {
    final poisAsync = ref.watch(poiProvider);
    final position = ref.watch(
      positionStreamProvider.select((v) => v.valueOrNull),
    );

    final markers = <Marker>{};
    poisAsync.whenData((pois) {
      for (final poi in pois) {
        markers.add(Marker(
          markerId: MarkerId(poi.id),
          position: LatLng(poi.lat, poi.lon),
          icon: poiMarkerHue(poi.confidence),
          infoWindow: InfoWindow(title: poi.name),
          onTap: () {
                final session = ref.read(sessionProvider);
                ref.read(narrationProvider.notifier).narrate(
                  poi,
                  persona: session.persona,
                  lang: session.lang,
                );
              },
        ));
      }
    });

    final initialTarget = position != null
        ? LatLng(position.latitude, position.longitude)
        : const LatLng(25.1023, 121.5482);

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
            markers: markers,
            onMapCreated: (c) => _mapController = c,
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
