import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../main.dart';
import '../services/auth_service.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email    = TextEditingController();
  final _password = TextEditingController();
  bool _signUp = false;
  bool _busy   = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() { _busy = true; _error = null; });
    try {
      if (_signUp) {
        await AuthService.createAccount(_email.text, _password.text);
      } else {
        await AuthService.signInWithEmail(_email.text, _password.text);
      }
    } on FirebaseAuthException catch (e) {
      setState(() => _error = AuthService.friendlyError(e));
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _google() async {
    setState(() { _busy = true; _error = null; });
    try {
      await AuthService.signInWithGoogle();
    } on FirebaseAuthException catch (e) {
      setState(() => _error = AuthService.friendlyError(e));
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resetPassword() async {
    if (_email.text.isEmpty) {
      setState(() => _error = 'Enter your email first.');
      return;
    }
    try {
      await AuthService.sendPasswordReset(_email.text);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Password reset email sent.'),
      ));
    } on FirebaseAuthException catch (e) {
      setState(() => _error = AuthService.friendlyError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: HermesColors.background,
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 380),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const _Wordmark(),
                const SizedBox(height: 8),
                const Center(
                  child: Text(
                    'swift counsel for every wager',
                    style: TextStyle(
                      color: HermesColors.textSecond,
                      fontSize: 12,
                      letterSpacing: 2,
                    ),
                  ),
                ),
                const SizedBox(height: 40),
                _field(_email, 'Email', keyboard: TextInputType.emailAddress),
                const SizedBox(height: 12),
                _field(_password, 'Password', obscure: true),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!,
                    style: const TextStyle(color: HermesColors.loss),
                    textAlign: TextAlign.center),
                ],
                const SizedBox(height: 20),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: HermesColors.laurel,
                    foregroundColor: Colors.black,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(6),
                    ),
                  ),
                  onPressed: _busy ? null : _submit,
                  child: _busy
                    ? const SizedBox(
                        height: 18, width: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.black))
                    : Text(_signUp ? 'CREATE ACCOUNT' : 'SIGN IN',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          letterSpacing: 2,
                        )),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _busy ? null : _google,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: HermesColors.textPrimary,
                    side: const BorderSide(color: HermesColors.slate),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  icon: const Icon(Icons.g_mobiledata, size: 28),
                  label: const Text('CONTINUE WITH GOOGLE',
                      style: TextStyle(letterSpacing: 1.5)),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    TextButton(
                      onPressed: () => setState(() => _signUp = !_signUp),
                      child: Text(
                        _signUp ? 'Have an account? Sign in' : 'Create account',
                        style: const TextStyle(color: HermesColors.skyBright),
                      ),
                    ),
                    if (!_signUp)
                      TextButton(
                        onPressed: _resetPassword,
                        child: const Text('Forgot password',
                          style: TextStyle(color: HermesColors.textSecond)),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _field(TextEditingController c, String label,
      {bool obscure = false, TextInputType? keyboard}) {
    return TextField(
      controller: c,
      obscureText: obscure,
      keyboardType: keyboard,
      style: const TextStyle(color: HermesColors.textPrimary),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: HermesColors.textSecond),
        enabledBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: HermesColors.slate),
        ),
        focusedBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: HermesColors.laurel),
        ),
      ),
    );
  }
}

class _Wordmark extends StatelessWidget {
  const _Wordmark();
  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text(
        'HERMES',
        style: TextStyle(
          color: HermesColors.laurel,
          fontSize: 42,
          fontWeight: FontWeight.w800,
          letterSpacing: 8,
        ),
      ),
    );
  }
}
