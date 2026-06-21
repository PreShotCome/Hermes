import 'dart:math';
import 'package:flutter/material.dart';
import '../main.dart';

/// Subtle animated background: slow drifting feathers + a faint dawn glow.
/// Evokes Hermes's winged sandals without overwhelming foreground UI.
class WingField extends StatefulWidget {
  final Widget child;
  const WingField({super.key, required this.child});

  @override
  State<WingField> createState() => _WingFieldState();
}

class _WingFieldState extends State<WingField>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  final _rng = Random(7);
  late final List<_Feather> _feathers;

  @override
  void initState() {
    super.initState();
    _feathers = List.generate(18, (_) => _Feather.random(_rng));
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 60),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        const _DawnGlow(),
        AnimatedBuilder(
          animation: _ctrl,
          builder: (_, __) => CustomPaint(
            size: Size.infinite,
            painter: _FeatherPainter(_feathers, _ctrl.value),
          ),
        ),
        widget.child,
      ],
    );
  }
}

class _DawnGlow extends StatelessWidget {
  const _DawnGlow();
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(0.0, -0.9),
          radius: 1.4,
          colors: [
            Color(0x332B7CA4),
            Color(0x00000000),
          ],
        ),
      ),
    );
  }
}

class _Feather {
  final double x;       // 0..1
  final double yStart;  // 0..1
  final double speed;   // 0..1 lap per cycle
  final double size;    // px
  final double phase;
  _Feather(this.x, this.yStart, this.speed, this.size, this.phase);

  factory _Feather.random(Random r) => _Feather(
    r.nextDouble(),
    r.nextDouble(),
    0.2 + r.nextDouble() * 0.4,
    6 + r.nextDouble() * 10,
    r.nextDouble() * 2 * pi,
  );
}

class _FeatherPainter extends CustomPainter {
  final List<_Feather> feathers;
  final double t; // 0..1
  _FeatherPainter(this.feathers, this.t);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = HermesColors.laurel.withOpacity(0.08)
      ..style = PaintingStyle.fill;
    for (final f in feathers) {
      final y = ((f.yStart + t * f.speed) % 1.0) * size.height;
      final sway = sin(t * 2 * pi + f.phase) * 14;
      final x = f.x * size.width + sway;
      _drawFeather(canvas, paint, Offset(x, y), f.size);
    }
  }

  void _drawFeather(Canvas c, Paint p, Offset center, double s) {
    final path = Path()
      ..moveTo(center.dx, center.dy - s)
      ..quadraticBezierTo(center.dx + s * 0.6, center.dy,
          center.dx, center.dy + s)
      ..quadraticBezierTo(center.dx - s * 0.6, center.dy,
          center.dx, center.dy - s)
      ..close();
    c.drawPath(path, p);
  }

  @override
  bool shouldRepaint(covariant _FeatherPainter old) => old.t != t;
}
