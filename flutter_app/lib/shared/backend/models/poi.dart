class WikiArticle {
  final String title;
  final String extract;
  final String url;

  const WikiArticle({
    required this.title,
    required this.extract,
    required this.url,
  });

  factory WikiArticle.fromJson(Map<String, dynamic> json) => WikiArticle(
        title: json['title'] as String,
        extract: json['extract'] as String,
        url: json['url'] as String,
      );

  Map<String, dynamic> toJson() => {
        'title': title,
        'extract': extract,
        'url': url,
      };
}

class POI {
  final String id;
  final String name;
  final double lat;
  final double lon;
  final Map<String, String> tags;
  final WikiArticle? wiki;
  final double distanceM;
  final String confidence;

  // foodie only — null for non-foodie POIs
  final double? rating;
  final int? userRatingsTotal;
  final int? priceLevel;
  final List<String>? placeTypes;
  final String? vicinity;

  const POI({
    required this.id,
    required this.name,
    required this.lat,
    required this.lon,
    required this.tags,
    this.wiki,
    required this.distanceM,
    required this.confidence,
    this.rating,
    this.userRatingsTotal,
    this.priceLevel,
    this.placeTypes,
    this.vicinity,
  });

  factory POI.fromJson(Map<String, dynamic> json) => POI(
        id: json['id'] as String,
        name: json['name'] as String,
        lat: (json['lat'] as num).toDouble(),
        lon: (json['lon'] as num).toDouble(),
        tags: (json['tags'] as Map<String, dynamic>? ?? {})
            .cast<String, String>(),
        wiki: json['wiki'] != null
            ? WikiArticle.fromJson(json['wiki'] as Map<String, dynamic>)
            : null,
        distanceM: (json['distance_m'] as num).toDouble(),
        confidence: json['confidence'] as String,
        rating: (json['rating'] as num?)?.toDouble(),
        userRatingsTotal: json['user_ratings_total'] as int?,
        priceLevel: json['price_level'] as int?,
        placeTypes: (json['place_types'] as List<dynamic>?)?.cast<String>(),
        vicinity: json['vicinity'] as String?,
      );
}
