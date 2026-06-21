import 'package:flutter/material.dart';
import '../main.dart';
import '../services/api_service.dart';

class ControlsScreen extends StatefulWidget {
  const ControlsScreen({super.key});
  @override
  State<ControlsScreen> createState() => _ControlsScreenState();
}

class _ControlsScreenState extends State<ControlsScreen> {
  Map<String, dynamic>? _settings;
  bool _loading = true;
  String? _error;

  static const _sports = ['NFL', 'NBA', 'MLB', 'NHL', 'NCAAF', 'NCAAB', 'EPL'];

  @override
  void initState() { super.initState(); _refresh(); }

  Future<void> _refresh() async {
    try {
      final s = await ApiService.getSettings();
      if (!mounted) return;
      setState(() { _settings = s; _loading = false; _error = null; });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _update(String key, dynamic value) async {
    setState(() => _settings![key] = value);
    try {
      await ApiService.updateSetting(key, value);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Update failed: $e'),
        backgroundColor: HermesColors.loss,
      ));
      _refresh();
    }
  }

  Future<void> _togglePause() async {
    try {
      final r = await ApiService.togglePause();
      if (!mounted) return;
      setState(() => _settings!['paused'] = r['paused'] == true);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('CONTROL', style: TextStyle(letterSpacing: 4)),
      ),
      body: _loading
        ? const Center(child: CircularProgressIndicator(color: HermesColors.laurel))
        : _error != null
          ? Center(child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text(_error!,
                  style: const TextStyle(color: HermesColors.loss)),
            ))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _safetyBanner(),
                const SizedBox(height: 16),
                _section('ENGINE', [
                  _pauseRow(),
                  _slider('Kelly fraction', 'kelly_fraction',
                      min: 0.0, max: 1.0, divisions: 20,
                      formatter: (v) => '${(v * 100).toStringAsFixed(0)}%',
                      hint: 'Defaults to ¼-Kelly. Full Kelly is reckless.'),
                  _slider('Min edge to take', 'min_edge',
                      min: 0.0, max: 0.20, divisions: 20,
                      formatter: (v) => '${(v * 100).toStringAsFixed(1)}%',
                      hint: 'Skip bets below this projected edge.'),
                ]),
                _section('BANKROLL GUARD', [
                  _slider('Max bet (% bankroll)', 'max_bet_pct',
                      min: 0.005, max: 0.1, divisions: 19,
                      formatter: (v) => '${(v * 100).toStringAsFixed(1)}%',
                      hint: 'Hard cap per bet, regardless of Kelly.'),
                  _slider('Daily loss stop (% bankroll)', 'daily_loss_pct',
                      min: 0.01, max: 0.2, divisions: 19,
                      formatter: (v) => '${(v * 100).toStringAsFixed(1)}%',
                      hint: 'Halt new bets after this drawdown today.'),
                  _slider('Min remaining bankroll (\$)', 'min_bankroll',
                      min: 0.0, max: 1000.0, divisions: 20,
                      formatter: (v) => '\$${v.toStringAsFixed(0)}',
                      hint: 'Engine refuses to bet below this floor.'),
                ]),
                _section('SPORTS', _sports.map(_sportToggle).toList()),
              ],
            ),
    );
  }

  Widget _safetyBanner() => Container(
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: HermesColors.skyDawn.withOpacity(0.12),
      borderRadius: BorderRadius.circular(6),
      border: Border.all(color: HermesColors.skyBright.withOpacity(0.3)),
    ),
    child: Row(children: const [
      Icon(Icons.shield_outlined, color: HermesColors.skyBright, size: 18),
      SizedBox(width: 8),
      Expanded(
        child: Text(
          'Every bet runs through validate_bet on the server. Block = block.',
          style: TextStyle(color: HermesColors.textPrimary, fontSize: 12),
        ),
      ),
    ]),
  );

  Widget _section(String title, List<Widget> rows) => Container(
    margin: const EdgeInsets.only(bottom: 16),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: HermesColors.surface,
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: HermesColors.slate),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(title,
            style: const TextStyle(
              color: HermesColors.textSecond,
              fontSize: 11, letterSpacing: 2,
              fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        ...rows,
      ],
    ),
  );

  Widget _pauseRow() {
    final paused = _settings!['paused'] == true;
    return SwitchListTile.adaptive(
      contentPadding: EdgeInsets.zero,
      title: Text(paused ? 'Engine paused' : 'Engine running',
          style: const TextStyle(color: HermesColors.textPrimary)),
      subtitle: const Text(
        'Pause stops new picks. Existing open bets stay open.',
        style: TextStyle(color: HermesColors.textSecond, fontSize: 11)),
      value: !paused,
      activeColor: HermesColors.win,
      onChanged: (_) => _togglePause(),
    );
  }

  Widget _slider(String label, String key,
      {required double min, required double max,
       int? divisions, required String Function(double) formatter,
       String? hint}) {
    final v = ((_settings![key] ?? min) as num).toDouble().clamp(min, max);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(child: Text(label,
                style: const TextStyle(color: HermesColors.textPrimary))),
            Text(formatter(v),
                style: const TextStyle(
                  color: HermesColors.laurel,
                  fontWeight: FontWeight.w600)),
          ]),
          if (hint != null)
            Text(hint, style: const TextStyle(
              color: HermesColors.textSecond, fontSize: 11)),
          Slider(
            value: v,
            min: min, max: max, divisions: divisions,
            activeColor: HermesColors.laurel,
            inactiveColor: HermesColors.slate,
            onChanged: (nv) => setState(() => _settings![key] = nv),
            onChangeEnd: (nv) => _update(key, nv),
          ),
        ],
      ),
    );
  }

  Widget _sportToggle(String sport) {
    final active = (_settings!['sports'] as List?)?.contains(sport) ?? false;
    return SwitchListTile.adaptive(
      contentPadding: EdgeInsets.zero,
      title: Text(sport,
          style: const TextStyle(color: HermesColors.textPrimary)),
      value: active,
      activeColor: HermesColors.laurel,
      onChanged: (v) {
        final current = List<String>.from(
            (_settings!['sports'] as List?)?.cast<String>() ?? <String>[]);
        if (v) {
          if (!current.contains(sport)) current.add(sport);
        } else {
          current.remove(sport);
        }
        _update('sports', current);
      },
    );
  }
}
