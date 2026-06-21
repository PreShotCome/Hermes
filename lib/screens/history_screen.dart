import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../main.dart';
import '../services/api_service.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});
  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<dynamic> _bets = [];
  bool _loading = true;
  String _filter = 'all';
  String? _error;

  @override
  void initState() { super.initState(); _refresh(); }

  Future<void> _refresh() async {
    try {
      final status = _filter == 'all' ? null : _filter;
      final bets = await ApiService.getBets(limit: 200, status: status);
      if (!mounted) return;
      setState(() { _bets = bets; _loading = false; _error = null; });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _settle(Map<String, dynamic> bet, String result) async {
    try {
      await ApiService.settleBet(bet['id'].toString(), result);
      await _refresh();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('$e'), backgroundColor: HermesColors.loss,
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('HISTORY', style: TextStyle(letterSpacing: 4)),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _refresh),
        ],
      ),
      body: Column(children: [
        _filterBar(),
        Expanded(
          child: _loading
            ? const Center(child: CircularProgressIndicator(
                color: HermesColors.laurel))
            : _error != null
              ? Center(child: Text(_error!,
                  style: const TextStyle(color: HermesColors.loss)))
              : _bets.isEmpty
                ? const Center(child: Text('No bets yet.',
                    style: TextStyle(color: HermesColors.textSecond)))
                : RefreshIndicator(
                    color: HermesColors.laurel,
                    onRefresh: _refresh,
                    child: ListView.separated(
                      padding: const EdgeInsets.all(16),
                      itemCount: _bets.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (_, i) => _BetTile(_bets[i], onSettle: _settle),
                    ),
                  ),
        ),
      ]),
    );
  }

  Widget _filterBar() {
    Widget chip(String key, String label) {
      final selected = _filter == key;
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: ChoiceChip(
          label: Text(label),
          selected: selected,
          backgroundColor: HermesColors.surface,
          selectedColor: HermesColors.laurel,
          labelStyle: TextStyle(
            color: selected ? Colors.black : HermesColors.textSecond,
            fontSize: 11, letterSpacing: 1.2,
          ),
          onSelected: (_) {
            setState(() { _filter = key; _loading = true; });
            _refresh();
          },
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(children: [
        chip('all', 'ALL'),
        chip('open', 'OPEN'),
        chip('won', 'WON'),
        chip('lost', 'LOST'),
        chip('push', 'PUSH'),
      ]),
    );
  }
}

class _BetTile extends StatelessWidget {
  final Map<String, dynamic> bet;
  final Future<void> Function(Map<String, dynamic>, String) onSettle;
  const _BetTile(this.bet, {required this.onSettle});

  @override
  Widget build(BuildContext context) {
    final selection = (bet['selection'] ?? '').toString();
    final matchup   = (bet['matchup']   ?? '').toString();
    final status    = (bet['status']    ?? 'open').toString();
    final odds      = (bet['american_odds'] ?? 0).toString();
    final stake     = ((bet['stake']  ?? 0.0) as num).toDouble();
    final payout    = ((bet['payout'] ?? 0.0) as num).toDouble();
    final placed    = (bet['placed_at'] ?? '').toString();
    final fmt       = NumberFormat.currency(symbol: '\$', decimalDigits: 2);

    Color statusColor;
    switch (status) {
      case 'won':  statusColor = HermesColors.win;  break;
      case 'lost': statusColor = HermesColors.loss; break;
      case 'push': statusColor = HermesColors.textSecond; break;
      default:     statusColor = HermesColors.skyBright;
    }

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: HermesColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: HermesColors.slate),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(
              child: Text(selection,
                style: const TextStyle(
                  color: HermesColors.textPrimary,
                  fontWeight: FontWeight.w600))),
            Container(
              padding: const EdgeInsets.symmetric(
                  horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: statusColor.withOpacity(0.12),
                border: Border.all(color: statusColor),
                borderRadius: BorderRadius.circular(3),
              ),
              child: Text(status.toUpperCase(),
                style: TextStyle(
                  color: statusColor, fontSize: 10,
                  fontWeight: FontWeight.bold, letterSpacing: 1.2)),
            ),
          ]),
          Text(matchup,
            style: const TextStyle(
              color: HermesColors.textSecond, fontSize: 11)),
          const SizedBox(height: 8),
          Row(children: [
            Text('odds ${odds.startsWith('-') ? odds : '+$odds'}',
              style: const TextStyle(color: HermesColors.skyBright, fontSize: 12)),
            const SizedBox(width: 16),
            Text('stake ${fmt.format(stake)}',
              style: const TextStyle(color: HermesColors.textSecond, fontSize: 12)),
            const SizedBox(width: 16),
            if (status != 'open')
              Text('${payout >= 0 ? '+' : ''}${fmt.format(payout)}',
                style: TextStyle(
                  color: payout >= 0 ? HermesColors.win : HermesColors.loss,
                  fontSize: 12, fontWeight: FontWeight.w600)),
            const Spacer(),
            Text(_fmtDate(placed),
              style: const TextStyle(color: HermesColors.textSecond, fontSize: 10)),
          ]),
          if (status == 'open') ...[
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                _settleBtn('PUSH', HermesColors.textSecond,
                    () => onSettle(bet, 'push')),
                const SizedBox(width: 8),
                _settleBtn('LOST', HermesColors.loss,
                    () => onSettle(bet, 'lost')),
                const SizedBox(width: 8),
                _settleBtn('WON', HermesColors.win,
                    () => onSettle(bet, 'won')),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _settleBtn(String label, Color c, VoidCallback onTap) =>
    OutlinedButton(
      onPressed: onTap,
      style: OutlinedButton.styleFrom(
        side: BorderSide(color: c),
        foregroundColor: c,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        minimumSize: Size.zero,
      ),
      child: Text(label,
          style: const TextStyle(fontSize: 10, letterSpacing: 1.2)),
    );

  String _fmtDate(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      return DateFormat('MMM d · h:mma').format(dt);
    } catch (_) { return iso; }
  }
}
