import 'package:flutter/material.dart';
import '../main.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../config.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _baseCtrl = TextEditingController();
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    await ApiService.loadBaseUrl();
    _baseCtrl.text = ApiService.baseUrl;
    if (mounted) setState(() => _loaded = true);
  }

  Future<void> _save() async {
    final url = _baseCtrl.text.trim();
    if (url.isEmpty) return;
    await ApiService.setBaseUrl(url);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
      content: Text('Backend URL saved.'),
    ));
  }

  Future<void> _signOut() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: HermesColors.surface,
        title: const Text('Sign out?',
            style: TextStyle(color: HermesColors.textPrimary)),
        content: const Text(
          'You will need to sign in again to use Hermes.',
          style: TextStyle(color: HermesColors.textSecond)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
              child: const Text('CANCEL',
                style: TextStyle(color: HermesColors.textSecond))),
          TextButton(onPressed: () => Navigator.pop(context, true),
              child: const Text('SIGN OUT',
                style: TextStyle(color: HermesColors.loss))),
        ],
      ),
    );
    if (confirmed == true) await AuthService.signOut();
  }

  @override
  void dispose() { _baseCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final user = AuthService.currentUser;
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('SETTINGS', style: TextStyle(letterSpacing: 4)),
      ),
      body: !_loaded
        ? const Center(child: CircularProgressIndicator(color: HermesColors.laurel))
        : ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _section('ACCOUNT', [
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.account_circle_outlined,
                      color: HermesColors.skyBright),
                  title: Text(user?.email ?? '—',
                      style: const TextStyle(color: HermesColors.textPrimary)),
                  subtitle: Text('uid: ${user?.uid ?? ''}',
                      style: const TextStyle(
                        color: HermesColors.textSecond, fontSize: 11)),
                ),
                TextButton.icon(
                  onPressed: _signOut,
                  icon: const Icon(Icons.logout, color: HermesColors.loss),
                  label: const Text('SIGN OUT',
                      style: TextStyle(color: HermesColors.loss)),
                ),
              ]),
              _section('BACKEND', [
                TextField(
                  controller: _baseCtrl,
                  style: const TextStyle(
                      color: HermesColors.textPrimary, fontSize: 13),
                  decoration: const InputDecoration(
                    labelText: 'Server URL',
                    labelStyle: TextStyle(color: HermesColors.textSecond),
                    hintText: 'http://192.168.1.10:8000',
                    hintStyle: TextStyle(color: HermesColors.textSecond),
                    enabledBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: HermesColors.slate)),
                    focusedBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: HermesColors.laurel)),
                  ),
                ),
                const SizedBox(height: 12),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: HermesColors.laurel,
                    foregroundColor: Colors.black,
                  ),
                  onPressed: _save,
                  child: const Text('SAVE',
                      style: TextStyle(fontWeight: FontWeight.bold,
                          letterSpacing: 2)),
                ),
                const SizedBox(height: 8),
                Text('Default: ${Config.apiBase}',
                    style: const TextStyle(
                      color: HermesColors.textSecond, fontSize: 11)),
              ]),
              _section('ABOUT', const [
                _AboutTile(
                  label: 'Version',
                  value: '1.0.0',
                ),
                _AboutTile(
                  label: 'Mode',
                  value: 'Paper (default)',
                  hint: 'Hermes records proposed wagers in a local ledger. '
                        'It does not place real bets.',
                ),
                _AboutTile(
                  label: 'Safety',
                  value: 'validate_bet — no override path',
                ),
              ]),
            ],
          ),
    );
  }

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
}

class _AboutTile extends StatelessWidget {
  final String label;
  final String value;
  final String? hint;
  const _AboutTile({required this.label, required this.value, this.hint});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(child: Text(label,
                style: const TextStyle(color: HermesColors.textSecond))),
            Text(value, style: const TextStyle(
                color: HermesColors.textPrimary,
                fontWeight: FontWeight.w600)),
          ]),
          if (hint != null) ...[
            const SizedBox(height: 2),
            Text(hint!, style: const TextStyle(
              color: HermesColors.textSecond, fontSize: 11)),
          ],
        ],
      ),
    );
  }
}
