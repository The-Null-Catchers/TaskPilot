import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/offline_queue.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/login_screen.dart';
import 'features/home/home_screen.dart';
import 'features/notifications/notifications_screen.dart';
import 'features/projects/board_screen.dart';
import 'features/projects/projects_screen.dart';
import 'features/sync/sync_center_screen.dart';
import 'features/tasks/my_tasks_screen.dart';
import 'features/tasks/task_detail_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/home',
    redirect: (context, state) {
      final auth = ref.read(authProvider);
      if (auth.loading) return null;
      final goingLogin = state.matchedLocation == '/login';
      if (!auth.authenticated && !goingLogin) return '/login';
      if (auth.authenticated && goingLogin) return '/home';
      return null;
    },
    refreshListenable: _RouterRefresh(ref),
    routes: [
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
      GoRoute(path: '/my-tasks', builder: (_, __) => const MyTasksScreen()),
      GoRoute(path: '/notifications', builder: (_, __) => const NotificationsScreen()),
      GoRoute(path: '/sync', builder: (_, __) => const SyncCenterScreen()),
      GoRoute(path: '/workspaces/:workspaceId/projects', builder: (_, state) => ProjectsScreen(workspaceId: state.pathParameters['workspaceId']!)),
      GoRoute(path: '/projects/:projectId', builder: (_, state) => BoardScreen(projectId: state.pathParameters['projectId']!)),
      GoRoute(path: '/tasks/:taskId', builder: (_, state) => TaskDetailScreen(taskId: state.pathParameters['taskId']!)),
    ],
  );
});

class _RouterRefresh extends ChangeNotifier {
  _RouterRefresh(Ref ref) {
    ref.listen(authProvider, (_, __) => notifyListeners());
  }
}

class TaskPilotApp extends ConsumerWidget {
  const TaskPilotApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(offlineQueueProvider);
    return MaterialApp.router(
      title: 'TaskPilot',
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.system,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF5B5CE2), brightness: Brightness.light),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF7F8FB),
        inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(14)))),
        cardTheme: const CardThemeData(margin: EdgeInsets.zero),
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF7C7CFF), brightness: Brightness.dark),
        useMaterial3: true,
        inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(14)))),
        cardTheme: const CardThemeData(margin: EdgeInsets.zero),
      ),
      routerConfig: ref.watch(routerProvider),
    );
  }
}
