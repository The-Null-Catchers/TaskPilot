import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/offline_queue.dart';
import 'core/push_registration.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/login_screen.dart';
import 'features/calendar/calendar_screen.dart';
import 'features/home/home_screen.dart';
import 'features/notifications/notifications_screen.dart';
import 'features/onboarding/onboarding_screen.dart';
import 'features/onboarding/splash_screen.dart';
import 'features/projects/board_screen.dart';
import 'features/projects/project_insights_screen.dart';
import 'features/projects/projects_screen.dart';
import 'features/search/global_search_screen.dart';
import 'features/settings/account_settings_screen.dart';
import 'features/settings/notification_preferences_screen.dart';
import 'features/settings/preferences_controller.dart';
import 'features/settings/preferences_screen.dart';
import 'features/sync/sync_center_screen.dart';
import 'features/tasks/archived_tasks_screen.dart';
import 'features/tasks/comment_attachments_screen.dart';
import 'features/tasks/my_tasks_screen.dart';
import 'features/tasks/task_attachments_screen.dart';
import 'features/tasks/task_detail_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/splash',
    redirect: (context, state) {
      final auth = ref.read(authProvider);
      final location = state.matchedLocation;
      if (auth.loading) return location == '/splash' ? null : '/splash';
      if (!auth.authenticated) return location == '/login' ? null : '/login';
      if (auth.needsOnboarding) return location == '/onboarding' ? null : '/onboarding';
      if (location == '/login' || location == '/splash' || location == '/onboarding') {
        return ref.read(preferencesProvider).landingRoute;
      }
      return null;
    },
    refreshListenable: _RouterRefresh(ref),
    routes: [
      GoRoute(path: '/splash', builder: (_, __) => const SplashScreen()),
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
      GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
      GoRoute(path: '/my-tasks', builder: (_, __) => const MyTasksScreen()),
      GoRoute(path: '/my-tasks/archived', builder: (_, __) => const ArchivedTasksScreen()),
      GoRoute(path: '/calendar', builder: (_, __) => const CalendarScreen()),
      GoRoute(path: '/search', builder: (_, __) => const GlobalSearchScreen()),
      GoRoute(path: '/notifications', builder: (_, __) => const NotificationsScreen()),
      GoRoute(path: '/sync', builder: (_, __) => const SyncCenterScreen()),
      GoRoute(path: '/settings/account', builder: (_, __) => const AccountSettingsScreen()),
      GoRoute(path: '/settings/preferences', builder: (_, __) => const PreferencesScreen()),
      GoRoute(path: '/settings/notifications', builder: (_, __) => const NotificationPreferencesScreen()),
      GoRoute(path: '/workspaces/:workspaceId/projects', builder: (_, state) => ProjectsScreen(workspaceId: state.pathParameters['workspaceId']!)),
      GoRoute(path: '/projects/:projectId', builder: (_, state) => BoardScreen(projectId: state.pathParameters['projectId']!)),
      GoRoute(path: '/projects/:projectId/insights', builder: (_, state) => ProjectInsightsScreen(projectId: state.pathParameters['projectId']!)),
      GoRoute(path: '/tasks/:taskId', builder: (_, state) => TaskDetailScreen(taskId: state.pathParameters['taskId']!)),
      GoRoute(path: '/tasks/:taskId/attachments', builder: (_, state) => TaskAttachmentsScreen(taskId: state.pathParameters['taskId']!)),
      GoRoute(path: '/comments/:commentId/attachments', builder: (_, state) => CommentAttachmentsScreen(commentId: state.pathParameters['commentId']!)),
    ],
  );
});

class _RouterRefresh extends ChangeNotifier {
  _RouterRefresh(Ref ref) {
    ref.listen(authProvider, (_, __) => notifyListeners());
    ref.listen(preferencesProvider, (_, __) => notifyListeners());
  }
}

class TaskPilotApp extends ConsumerWidget {
  const TaskPilotApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(offlineQueueProvider);
    final preferences = ref.watch(preferencesProvider);
    ref.listen<AuthState>(authProvider, (previous, next) async {
      if (previous?.authenticated != next.authenticated && !next.loading) {
        ref.read(offlineQueueProvider.notifier).initialize().then((_) {
          if (next.authenticated) ref.read(offlineQueueProvider.notifier).sync();
        });
        if (next.authenticated) {
          await ref.read(preferencesProvider.notifier).load();
          if (!next.needsOnboarding) {
            final router = ref.read(routerProvider);
            final location = router.routeInformationProvider.value.uri.path;
            if (location == '/login' || location == '/splash' || location == '/home') {
              router.go(ref.read(preferencesProvider).landingRoute);
            }
          }
          ref.read(pushRegistrationProvider).initialize(
            onOpen: (data) {
              final entityType = data['entity_type']?.toString();
              final entityId = data['entity_id']?.toString();
              final router = ref.read(routerProvider);
              if (entityType == 'task' && entityId != null && entityId.isNotEmpty) {
                router.push('/tasks/$entityId');
              } else {
                router.push('/notifications');
              }
            },
          );
        } else {
          ref.read(preferencesProvider.notifier).reset();
        }
      }
    });
    return MaterialApp.router(
      title: 'TaskPilot',
      debugShowCheckedModeBanner: false,
      themeMode: preferences.themeMode,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF5B5CE2), brightness: Brightness.light),
        useMaterial3: true,
        visualDensity: preferences.visualDensity,
        scaffoldBackgroundColor: const Color(0xFFF7F8FB),
        inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(14)))),
        cardTheme: const CardThemeData(margin: EdgeInsets.zero),
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF7C7CFF), brightness: Brightness.dark),
        useMaterial3: true,
        visualDensity: preferences.visualDensity,
        inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(14)))),
        cardTheme: const CardThemeData(margin: EdgeInsets.zero),
      ),
      routerConfig: ref.watch(routerProvider),
    );
  }
}
