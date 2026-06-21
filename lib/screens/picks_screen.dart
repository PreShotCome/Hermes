import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../main.dart';
import '../services/api_service.dart';

class PicksScreen extends StatefulWidget {
  const PicksScreen({super.key});
  @override
  State<PicksScreen> createState() => _PicksScreenState();
}

class _PicksScreenState extends State<PicksScreen> {
  List<dynamic> _picks = [];
  bool _loading = true;
  bool _scanning = false;
  String? _error;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _refresh();
    _poll = Timer.periodic(const Duration(seconds: 20), (_) => _refresh());
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final picks = await ApiService.getPicks();
      if (!mounted) return;
      setState(() { _picks = picks; _loading = false; _error = null; });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _scan() async {
    setState(() => _scanning = true);
    try {
      final result = await ApiService.runScan();
      if (!mounted) return;
      final found = result['found'] ?? 0;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Scan complete — $found value bets found.'),
      ));
      await _refresh();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Scan failed: $e'),
        backgroundColor: HermesColors.loss,
      ));
    } finally {
      if (mounted) setState(() => _scanning = false);
    }
  }

  Future<void> _place(Map<String, dynamic> pick) async {
    try {
      final r = await ApiService.placePick(pick['id'].toString());
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Bet recorded — ${r['stake_pretty'] ?? ''}'),
        backgroundColor: HermesColors.win,
      ));
      await _refresh();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('$e'),
        backgroundColor: HermesColors.loss,
      ));
    }
  }

  Future<void> _skip(Map<String, dynamic> pick) async {
    try {
      await ApiService.skipPick(pick['id'].toString());
      await _refresh();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final pending = _picks.where((p) => p['status'] == 'pending').toList();
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('PICKS', style: TextStyle(letterSpacing: 4)),
        actions: [
          IconButton(
            icon: _scanning
              ? const SizedBox(
                  height: 18, width: 18,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: HermesColors.laurel))
              : const Icon(Icons.radar),
            onPressed: _scanning ? null : _scan,
            tooltip: 'Scan markets',
          ),
        ],
      ),
      body: _loading
        ? const Center(child: CircularProgressIndicator(color: HermesColors.laurel))
        : _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(_error!,
                    style: const TextStyle(color: HermesColors.loss)),
              ),
            )
          : RefreshIndicator(
              color: HermesColors.laurel,
              onRefresh: _refresh,
              child: pending.isEmpty
                ? ListView(children: const [SizedBox(height: 120), _EmptyState()])
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: pending.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                    itemBuilder: (_, i) =>
                        _PickCard(pending[i], onPlace: _place, onSkip: _skip),
                  ),
            ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            const Icon(Icons.radar, color: HermesColors.skyBright, size: 56),
            const SizedBox(height: 16),
            const Text('No value on the board.',
                style: TextStyle(
                  color: HermesColors.textPrimary,
                  fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            const Text(
              'Hermes only surfaces bets above the edge floor.\n'
              'Tap radar to re-scan markets.',
              textAlign: TextAlign.center,
              style: TextStyle(color: HermesColors.textSecond, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}

class _PickCard extends StatelessWidget {
  final Map<String, dynamic> pick;
  final Future<void> Function(Map<String, dynamic>) onPlace;
  final Future<void> Function(Map<String, dynamic>) onSkip;
  const _PickCard(this.pick, {required this.onPlace, required this.onSkip});

  @override
  Widget build(BuildContext context) {
    final selection = (pick['selection'] ?? '').toString();
    final matchup   = (pick['matchup']   ?? '').toString();
    final sport     = (pick['sport']     ?? '').toString();
    final book      = (pick['book']      ?? '').toString();
    final odds      = (pick['american_odds'] ?? 0).toString();
    final edge      = ((pick['edge'] ?? 0.0) as num).toDouble();
    final modelProb = ((pick['model_prob'] ?? 0.0) as num).toDouble();
    final stake     = ((pick['stake'] ?? 0.0) as num).toDouble();
    final tip       = (pick['commences_at'] ?? '').toString();
    final fmt       = NumberFormat.currency(symbol: '\$', decimalDigits: 2);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: HermesColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: HermesColors.laurel.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _tag(sport, HermesColors.skyBright),
              const SizedBox(width: 6),
              _tag(book, HermesColors.textSecond),
              const Spacer(),
              if (tip.isNotEmpty)
                Text(_fmtTip(tip),
                    style: const TextStyle(
                      color: HermesColors.textSecond, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 10),
          Text(selection,
              style: const TextStyle(
                color: HermesColors.textPrimary,
                fontSize: 18, fontWeight: FontWeight.w700)),
          Text(matchup,
              style: const TextStyle(
                color: HermesColors.textSecond, fontSize: 12)),
          const SizedBox(height: 12),
          Row(children: [
            _metric('ODDS', odds.startsWith('-') ? odds : '+$odds'),
            _metric('MODEL %', '${(modelProb * 100).toStringAsFixed(1)}%'),
            _metric('EDGE', '${(edge * 100).toStringAsFixed(1)}%',
                color: HermesColors.laurel),
            _metric('STAKE', fmt.format(stake)),
          ]),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton(
                onPressed: () => onSkip(pick),
                child: const Text('SKIP',
                    style: TextStyle(color: HermesColors.textSecond)),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: HermesColors.laurel,
                  foregroundColor: Colors.black,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(4)),
                ),
                onPressed: () => onPlace(pick),
                child: const Text('PLACE',
                    style: TextStyle(
                        fontWeight: FontWeight.bold, letterSpacing: 1.5)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _fmtTip(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      return DateFormat('EEE MMM d · h:mma').format(dt);
    } catch (_) { return iso; }
  }

  Widget _tag(String s, Color c) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
    decoration: BoxDecoration(
      color: c.withOpacity(0.12),
      borderRadius: BorderRadius.circular(3),
    ),
    child: Text(s.toUpperCase(),
        style: TextStyle(
          color: c, fontSize: 10, letterSpacing: 1.2,
          fontWeight: FontWeight.w600)),
  );

  Widget _metric(String label, String value, {Color? color}) => Expanded(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(
          color: HermesColors.textSecond, fontSize: 10, letterSpacing: 1.2)),
        const SizedBox(height: 2),
        Text(value, style: TextStyle(
          color: color ?? HermesColors.textPrimary,
          fontSize: 14, fontWeight: FontWeight.w600)),
      ],
    ),
  );
}
