import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'screens/dashboard_screen.dart';
import 'screens/picks_screen.dart';
import 'screens/history_screen.dart';
import 'screens/controls_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/login_screen.dart';
import 'widgets/wing_field.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await Firebase.initializeApp();
  } catch (_) {
    // Allow the app to boot without firebase_options.dart in dev; sign-in
    // will fail loudly until the platform config files are in place.
  }
  runApp(const HermesApp());
}

// ── Hermes brand colours ─────────────────────────────────────────────────────
class HermesColors {
  // Backgrounds — slate dusk, the herald's evening sky
  static const background  = Color(0xFF0E1116);
  static const surface     = Color(0xFF1B2330);
  static const surfaceCard = Color(0xFF243044);
  static const slate       = Color(0xFF334155);

  // Sky — the herald's flight
  static const skyDawn     = Color(0xFF2B7CA4);
  static const skyBright   = Color(0xFF4FB3D9);

  // Laurel — victory gold
  static const laurel      = Color(0xFFC9A227);
  static const laurelBright= Color(0xFFF0C040);
  static const laurelDim   = Color(0xFF8A6A10);

  // Outcomes
  static const win         = Color(0xFF4FA862);
  static const loss        = Color(0xFFB33A3A);

  // Text
  static const textPrimary = Color(0xFFF1F5F9);
  static const textSecond  = Color(0xFF94A3B8);
}

class HermesApp extends StatelessWidget {
  const HermesApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Hermes',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: HermesColors.background,
        colorScheme: const ColorScheme.dark(
          primary:   HermesColors.laurel,
          secondary: HermesColors.skyBright,
          surface:   HermesColors.surface,
        ),
        fontFamily: 'monospace',
        appBarTheme: const AppBarTheme(
          backgroundColor: HermesColors.background,
          foregroundColor: HermesColors.laurel,
          elevation: 0,
        ),
        dividerColor: HermesColors.slate,
        cardColor: HermesColors.surfaceCard,
      ),
      home: const AuthGate(),
    );
  }
}

// ── Auth gate — routes to login or app based on Firebase auth state ─────────
class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.authStateChanges(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            backgroundColor: HermesColors.background,
            body: Center(
              child: CircularProgressIndicator(color: HermesColors.laurel),
            ),
          );
        }
        if (snapshot.hasData) return const MainShell();
        return const LoginScreen();
      },
    );
  }
}

// Cross-screen nav bus — set the index to switch tabs from anywhere.
final ValueNotifier<int> navRequest = ValueNotifier<int>(0);

class MainShell extends StatefulWidget {
  const MainShell({super.key});
  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;

  final _screens = const [
    DashboardScreen(),
    PicksScreen(),
    HistoryScreen(),
    ControlsScreen(),
    SettingsScreen(),
    ChatScreen(),
  ];

  @override
  void initState() {
    super.initState();
    navRequest.addListener(_onNavRequest);
  }

  @override
  void dispose() {
    navRequest.removeListener(_onNavRequest);
    super.dispose();
  }

  void _onNavRequest() {
    final i = navRequest.value;
    if (i >= 0 && i < _screens.length && i != _index) {
      setState(() => _index = i);
    }
  }

  @override
  Widget build(BuildContext context) {
    return WingField(
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: IndexedStack(index: _index, children: _screens),
        bottomNavigationBar: Container(
          decoration: BoxDecoration(
            color: HermesColors.surface,
            border: Border(
              top: BorderSide(color: HermesColors.laurel.withOpacity(0.2)),
            ),
          ),
          child: BottomNavigationBar(
            currentIndex: _index,
            onTap: (i) => setState(() => _index = i),
            backgroundColor: Colors.transparent,
            selectedItemColor: HermesColors.laurel,
            unselectedItemColor: HermesColors.textSecond.withOpacity(0.6),
            type: BottomNavigationBarType.fixed,
            showSelectedLabels: true,
            showUnselectedLabels: true,
            selectedLabelStyle: const TextStyle(fontSize: 10, letterSpacing: 1),
            unselectedLabelStyle: const TextStyle(fontSize: 10),
            items: const [
              BottomNavigationBarItem(
                  icon: Icon(Icons.dashboard_outlined),
                  activeIcon: Icon(Icons.dashboard),
                  label: 'BANKROLL'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.stars_outlined),
                  activeIcon: Icon(Icons.stars),
                  label: 'PICKS'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.history_outlined),
                  activeIcon: Icon(Icons.history),
                  label: 'HISTORY'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.tune_outlined),
                  activeIcon: Icon(Icons.tune),
                  label: 'CONTROL'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.settings_outlined),
                  activeIcon: Icon(Icons.settings),
                  label: 'SETTINGS'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.auto_awesome_outlined),
                  activeIcon: Icon(Icons.auto_awesome),
                  label: 'ORACLE'),
            ],
          ),
        ),
      ),
    );
  }
}
