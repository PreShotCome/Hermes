import 'dart:async';
import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import '../main.dart';
import '../services/api_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic>? _bankroll;
  Map<String, dynamic>? _status;
  List<dynamic> _curve = [];
  List<dynamic> _picks = [];
  bool _loading = true;
  String? _error;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _refresh();
    _poll = Timer.periodic(const Duration(seconds: 15), (_) => _refresh());
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final results = await Future.wait([
        ApiService.getBankroll(),
        ApiService.getStatus(),
        ApiService.getEquityCurve(limit: 200),
        ApiService.getPicks(),
      ]);
      if (!mounted) return;
      setState(() {
        _bankroll = results[0] as Map<String, dynamic>;
        _status   = results[1] as Map<String, dynamic>;
        _curve    = results[2] as List<dynamic>;
        _picks    = results[3] as List<dynamic>;
        _loading  = false;
        _error    = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('BANKROLL', style: TextStyle(letterSpacing: 4)),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _refresh),
        ],
      ),
      body: _loading
        ? const Center(child: CircularProgressIndicator(color: HermesColors.laurel))
        : _error != null
          ? _errorView(_error!)
          : RefreshIndicator(
              color: HermesColors.laurel,
              onRefresh: _refresh,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _bankrollCard(),
                  const SizedBox(height: 16),
                  _curveCard(),
                  const SizedBox(height: 16),
                  _picksTeaser(),
                  const SizedBox(height: 24),
                ],
              ),
            ),
    );
  }

  Widget _errorView(String e) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.cloud_off, color: HermesColors.loss, size: 48),
          const SizedBox(height: 12),
          const Text('Cannot reach the Hermes server.',
              style: TextStyle(color: HermesColors.textPrimary)),
          const SizedBox(height: 4),
          Text(e, style: const TextStyle(
            color: HermesColors.textSecond, fontSize: 11)),
          const SizedBox(height: 16),
          TextButton(onPressed: _refresh, child: const Text('Retry')),
        ],
      ),
    ),
  );

  Widget _bankrollCard() {
    final br = _bankroll ?? {};
    final st = _status ?? {};
    final balance  = (br['balance']  ?? 0.0).toDouble();
    final starting = (br['starting'] ?? balance).toDouble();
    final dayPnl   = (br['day_pnl']  ?? 0.0).toDouble();
    final open     = (br['open_bets'] ?? 0) as int;
    final mode     = (st['mode'] ?? 'paper').toString();
    final paused   = st['paused'] == true;
    final ret      = starting == 0 ? 0 : ((balance - starting) / starting) * 100;
    final fmt      = NumberFormat.currency(symbol: '\$', decimalDigits: 2);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: HermesColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: HermesColors.laurel.withOpacity(0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('BANKROLL', style: _label),
              _modeChip(mode, paused),
            ],
          ),
          const SizedBox(height: 8),
          Text(fmt.format(balance),
              style: const TextStyle(
                color: HermesColors.textPrimary,
                fontSize: 36, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Row(children: [
            _pnlChip(dayPnl, label: 'today'),
            const SizedBox(width: 8),
            _pnlChip(balance - starting, label: 'all-time', percent: ret),
          ]),
          const Divider(height: 28, color: HermesColors.slate),
          Row(children: [
            Expanded(child: _stat('Open bets', '$open')),
            Expanded(child: _stat('Settled today',
                '${br['settled_today'] ?? 0}')),
            Expanded(child: _stat('Win rate',
                '${(((br['win_rate'] ?? 0.0) as num) * 100).toStringAsFixed(1)}%')),
          ]),
        ],
      ),
    );
  }

  Widget _modeChip(String mode, bool paused) {
    final live = mode == 'live';
    final color = paused
        ? HermesColors.textSecond
        : (live ? HermesColors.loss : HermesColors.skyBright);
    final label = paused ? 'PAUSED' : mode.toUpperCase();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        border: Border.all(color: color),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(label,
          style: TextStyle(
            color: color, fontSize: 11, letterSpacing: 2,
            fontWeight: FontWeight.bold)),
    );
  }

  Widget _pnlChip(double amount, {required String label, double? percent}) {
    final color = amount >= 0 ? HermesColors.win : HermesColors.loss;
    final sign  = amount >= 0 ? '+' : '';
    final fmt   = NumberFormat.currency(symbol: '\$', decimalDigits: 2);
    final pct   = percent == null ? '' : '  (${sign}${percent.toStringAsFixed(2)}%)';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text('$sign${fmt.format(amount)}$pct  $label',
          style: TextStyle(color: color, fontSize: 11)),
    );
  }

  Widget _stat(String label, String value) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label.toUpperCase(),
          style: const TextStyle(
            color: HermesColors.textSecond, fontSize: 10, letterSpacing: 1.2)),
      const SizedBox(height: 4),
      Text(value, style: const TextStyle(
        color: HermesColors.textPrimary, fontSize: 16,
        fontWeight: FontWeight.w600)),
    ],
  );

  Widget _curveCard() {
    if (_curve.isEmpty) {
      return _empty('No equity history yet — the curve appears once bets settle.');
    }
    final spots = <FlSpot>[];
    for (var i = 0; i < _curve.length; i++) {
      final v = (_curve[i]['balance'] ?? 0).toDouble();
      spots.add(FlSpot(i.toDouble(), v));
    }
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: HermesColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: HermesColors.slate),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('EQUITY', style: _label),
          const SizedBox(height: 12),
          SizedBox(
            height: 160,
            child: LineChart(LineChartData(
              gridData: const FlGridData(show: false),
              titlesData: const FlTitlesData(show: false),
              borderData: FlBorderData(show: false),
              lineBarsData: [
                LineChartBarData(
                  spots: spots,
                  isCurved: true,
                  color: HermesColors.laurel,
                  barWidth: 2,
                  dotData: const FlDotData(show: false),
                  belowBarData: BarAreaData(
                    show: true,
                    color: HermesColors.laurel.withOpacity(0.12),
                  ),
                ),
              ],
            )),
          ),
        ],
      ),
    );
  }

  Widget _picksTeaser() {
    final pending = _picks.where((p) => p['status'] == 'pending').take(3).toList();
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: HermesColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: HermesColors.slate),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('TODAY\'S PICKS', style: _label),
              TextButton(
                onPressed: () => navRequest.value = 1,
                child: const Text('SEE ALL',
                    style: TextStyle(color: HermesColors.skyBright, fontSize: 11)),
              ),
            ],
          ),
          if (pending.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('No value bets right now. The model is watching.',
                  style: TextStyle(color: HermesColors.textSecond, fontSize: 12)),
            )
          else
            ...pending.map((p) => _PickRow(p)),
        ],
      ),
    );
  }

  Widget _empty(String message) => Container(
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: HermesColors.surface,
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: HermesColors.slate),
    ),
    child: Text(message,
        style: const TextStyle(color: HermesColors.textSecond, fontSize: 12)),
  );

  TextStyle get _label => const TextStyle(
    color: HermesColors.textSecond,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: FontWeight.w600,
  );
}

class _PickRow extends StatelessWidget {
  final Map<String, dynamic> pick;
  const _PickRow(Map<String, dynamic> p) : pick = p;

  @override
  Widget build(BuildContext context) {
    final selection = (pick['selection'] ?? '').toString();
    final matchup   = (pick['matchup']   ?? '').toString();
    final edge      = ((pick['edge']     ?? 0.0) as num).toDouble();
    final odds      = (pick['american_odds'] ?? 0).toString();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(selection,
                    style: const TextStyle(
                      color: HermesColors.textPrimary,
                      fontWeight: FontWeight.w600)),
                Text(matchup,
                    style: const TextStyle(
                      color: HermesColors.textSecond, fontSize: 11)),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(odds.startsWith('-') ? odds : '+$odds',
                  style: const TextStyle(color: HermesColors.skyBright)),
              Text('${(edge * 100).toStringAsFixed(1)}% edge',
                  style: const TextStyle(
                    color: HermesColors.laurel, fontSize: 11)),
            ],
          ),
        ],
      ),
    );
  }
}
