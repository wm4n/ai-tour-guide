import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/haversine.dart';

class TriggerEngine {
  static const double defaultTriggerRadiusM = 100.0;

  static List<POI> evaluate({
    required double userLat,
    required double userLon,
    required List<POI> pois,
    required Set<String> playedPoiIds,
    required Set<String> cooldownPoiIds,
    double radiusM = defaultTriggerRadiusM,
  }) {
    return pois.where((poi) {
      if (playedPoiIds.contains(poi.id)) return false;
      if (cooldownPoiIds.contains(poi.id)) return false;
      final dist = haversine(userLat, userLon, poi.lat, poi.lon);
      return dist <= radiusM;
    }).toList();
  }
}
