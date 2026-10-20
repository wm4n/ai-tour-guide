import 'package:http/http.dart' as http;

import 'host_settings.dart';

enum ConnectionStatus {
  notConfigured,
  checking,
  connected,
  unreachable,
  unauthorized,
}

class HostClient {
  HostClient(this._http, {Duration timeout = const Duration(seconds: 5)})
    : _timeout = timeout;

  final http.Client _http;
  final Duration _timeout;

  Future<ConnectionStatus> check(HostSettings settings) async {
    final base = _baseUri(settings.url);
    if (base == null) return ConnectionStatus.notConfigured;

    try {
      final response = await _http
          .get(
            base.replace(path: '/v1/status'),
            headers: {
              if (settings.token.isNotEmpty) 'X-Buddy-Token': settings.token,
            },
          )
          .timeout(_timeout);
      if (response.statusCode == 200) return ConnectionStatus.connected;
      if (response.statusCode == 401) return ConnectionStatus.unauthorized;
      return ConnectionStatus.unreachable;
    } on Exception {
      return ConnectionStatus.unreachable;
    }
  }

  static Uri? _baseUri(String raw) {
    var text = raw.trim();
    if (text.isEmpty) return null;
    if (!text.contains('://')) text = 'http://$text';
    text = text.replaceFirst(RegExp(r'/+$'), '');
    final uri = Uri.tryParse(text);
    if (uri == null || uri.host.isEmpty) return null;
    return uri;
  }
}
