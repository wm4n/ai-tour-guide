import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/features/session/screens/home_screen.dart';
import 'package:flutter_app/features/map/screens/map_screen.dart';

final _router = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (_, __) => const HomeScreen(),
    ),
    GoRoute(
      path: '/map',
      builder: (_, __) => const MapScreen(),
    ),
  ],
);

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'AI Tour Guide',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF4A9EFF),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      routerConfig: _router,
    );
  }
}
