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

  const POI({
    required this.id,
    required this.name,
    required this.lat,
    required this.lon,
    required this.tags,
    this.wiki,
    required this.distanceM,
    required this.confidence,
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
      );
}
