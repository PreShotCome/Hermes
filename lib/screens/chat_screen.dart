import 'package:flutter/material.dart';
import '../main.dart';
import '../services/api_service.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _Msg {
  final String role;  // 'user' or 'oracle'
  final String text;
  _Msg(this.role, this.text);
}

class _ChatScreenState extends State<ChatScreen> {
  final _ctrl   = TextEditingController();
  final _scroll = ScrollController();
  final _msgs   = <_Msg>[
    _Msg('oracle',
        'I am the Oracle of Hermes. Ask about your bankroll, current picks, '
        'recent results, or sports the model is watching.'),
  ];
  bool _sending = false;

  Future<void> _send() async {
    final text = _ctrl.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() {
      _msgs.add(_Msg('user', text));
      _sending = true;
      _ctrl.clear();
    });
    _scrollToBottom();
    try {
      final reply = await ApiService.chat(text);
      if (!mounted) return;
      setState(() {
        _msgs.add(_Msg('oracle', reply));
        _sending = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _msgs.add(_Msg('oracle',
            'I lost the wind — ${e.toString()}'));
        _sending = false;
      });
    }
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() { _ctrl.dispose(); _scroll.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('ORACLE', style: TextStyle(letterSpacing: 4)),
      ),
      body: SafeArea(
        child: Column(children: [
          Expanded(
            child: ListView.builder(
              controller: _scroll,
              padding: const EdgeInsets.all(16),
              itemCount: _msgs.length + (_sending ? 1 : 0),
              itemBuilder: (_, i) {
                if (i == _msgs.length) return const _TypingDots();
                return _Bubble(_msgs[i]);
              },
            ),
          ),
          Container(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            decoration: const BoxDecoration(
              color: HermesColors.surface,
              border: Border(
                top: BorderSide(color: HermesColors.slate),
              ),
            ),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _ctrl,
                  style: const TextStyle(color: HermesColors.textPrimary),
                  decoration: const InputDecoration(
                    hintText: 'Ask the Oracle…',
                    hintStyle: TextStyle(color: HermesColors.textSecond),
                    border: InputBorder.none,
                  ),
                  onSubmitted: (_) => _send(),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.send, color: HermesColors.laurel),
                onPressed: _sending ? null : _send,
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  final _Msg msg;
  const _Bubble(this.msg);
  @override
  Widget build(BuildContext context) {
    final user = msg.role == 'user';
    return Align(
      alignment: user ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.78),
        decoration: BoxDecoration(
          color: user
              ? HermesColors.laurel.withOpacity(0.18)
              : HermesColors.surface,
          border: Border.all(
            color: user ? HermesColors.laurel : HermesColors.slate,
          ),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(msg.text,
            style: const TextStyle(
              color: HermesColors.textPrimary, fontSize: 13)),
      ),
    );
  }
}

class _TypingDots extends StatelessWidget {
  const _TypingDots();
  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 8, horizontal: 4),
      child: Row(children: [
        SizedBox(
          height: 12, width: 12,
          child: CircularProgressIndicator(
            strokeWidth: 2, color: HermesColors.laurel),
        ),
        SizedBox(width: 8),
        Text('the Oracle considers…',
            style: TextStyle(color: HermesColors.textSecond, fontSize: 12)),
      ]),
    );
  }
}
