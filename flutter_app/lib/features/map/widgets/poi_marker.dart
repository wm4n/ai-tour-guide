import 'package:google_maps_flutter/google_maps_flutter.dart';

BitmapDescriptor poiMarkerHue(String confidence) {
  return switch (confidence) {
    'high' => BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueAzure),
    'medium' =>
      BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueYellow),
    _ => BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueRed),
  };
}
