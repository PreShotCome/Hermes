import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config.dart';

/// Thin client over the Hermes server. Base URL is read from
/// SharedPreferences (set via Settings); falls back to [Config.apiBase].
class ApiService {
  static String _base = Config.apiBase;

  static Future<void> loadBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    _base = prefs.getString('api_base') ?? Config.apiBase;
  }

  static Future<void> setBaseUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('api_base', url.trim());
    _base = url.trim();
  }

  static String get baseUrl => _base;

  static Map<String, String> get _headers => {
    'x-api-key': Config.apiKey,
    'Content-Type': 'application/json',
  };

  // ── Bankroll & status ──────────────────────────────────────────────────────
  static Future<Map<String, dynamic>> getBankroll() async {
    final r = await http.get(Uri.parse('$_base/bankroll'), headers: _headers);
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> getStatus() async {
    final r = await http.get(Uri.parse('$_base/status'), headers: _headers);
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  static Future<List<dynamic>> getEquityCurve({int limit = 500}) async {
    final r = await http.get(
        Uri.parse('$_base/equity?limit=$limit'), headers: _headers);
    return (jsonDecode(r.body) as Map<String, dynamic>)['curve'] ?? [];
  }

  // ── Picks (model's current value bets) ────────────────────────────────────
  static Future<List<dynamic>> getPicks() async {
    final r = await http.get(Uri.parse('$_base/picks'), headers: _headers);
    return (jsonDecode(r.body) as Map<String, dynamic>)['picks'] ?? [];
  }

  static Future<Map<String, dynamic>> placePick(String pickId) async {
    final r = await http.post(
      Uri.parse('$_base/picks/$pickId/place'),
      headers: _headers,
    );
    if (r.statusCode >= 400) {
      final body = jsonDecode(r.body);
      throw Exception(body['detail'] ?? 'Place failed');
    }
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> skipPick(String pickId) async {
    final r = await http.post(
      Uri.parse('$_base/picks/$pickId/skip'),
      headers: _headers,
    );
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> runScan() async {
    final r = await http.post(Uri.parse('$_base/scan'), headers: _headers);
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  // ── Bet history ────────────────────────────────────────────────────────────
  static Future<List<dynamic>> getBets({int limit = 100, String? status}) async {
    final qs = <String, String>{'limit': '$limit'};
    if (status != null) qs['status'] = status;
    final uri = Uri.parse('$_base/bets').replace(queryParameters: qs);
    final r = await http.get(uri, headers: _headers);
    return (jsonDecode(r.body) as Map<String, dynamic>)['bets'] ?? [];
  }

  static Future<Map<String, dynamic>> settleBet(String betId, String result) async {
    final r = await http.post(
      Uri.parse('$_base/bets/$betId/settle'),
      headers: _headers,
      body: jsonEncode({'result': result}),
    );
    if (r.statusCode >= 400) {
      throw Exception(jsonDecode(r.body)['detail'] ?? 'Settle failed');
    }
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  // ── Settings (server-side) ─────────────────────────────────────────────────
  static Future<Map<String, dynamic>> getSettings() async {
    final r = await http.get(Uri.parse('$_base/settings'), headers: _headers);
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  static Future<void> updateSetting(String key, dynamic value) async {
    await http.post(
      Uri.parse('$_base/settings'),
      headers: _headers,
      body: jsonEncode({'key': key, 'value': value}),
    );
  }

  static Future<Map<String, dynamic>> togglePause() async {
    final r = await http.post(Uri.parse('$_base/pause'), headers: _headers);
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  // ── Oracle (AI assistant) ──────────────────────────────────────────────────
  static Future<String> chat(String message) async {
    final r = await http.post(
      Uri.parse('$_base/chat'),
      headers: _headers,
      body: jsonEncode({'message': message}),
    );
    if (r.statusCode == 200) {
      return jsonDecode(r.body)['reply'] ?? '';
    }
    return 'Oracle unavailable — add ANTHROPIC_API_KEY on the server to enable.';
  }
}
