import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api.dart';

class UserPreferences {
  const UserPreferences({
    required this.theme,
    required this.density,
    required this.weekStart,
    required this.defaultHome,
    this.loading = false,
    this.error,
  });

  final String theme;
  final String density;
  final int weekStart;
  final String defaultHome;
  final bool loading;
  final String? error;

  factory UserPreferences.defaults() => const UserPreferences(
        theme: 'system',
        density: 'comfortable',
        weekStart: 1,
        defaultHome: 'home',
      );

  factory UserPreferences.fromJson(Map<String, dynamic> json) => UserPreferences(
        theme: json['theme'] as String? ?? 'system',
        density: json['density'] as String? ?? 'comfortable',
        weekStart: json['week_start'] as int? ?? 1,
        defaultHome: json['default_home'] as String? ?? 'home',
      );

  UserPreferences copyWith({
    String? theme,
    String? density,
    int? weekStart,
    String? defaultHome,
    bool? loading,
    String? error,
    bool clearError = false,
  }) {
    return UserPreferences(
      theme: theme ?? this.theme,
      density: density ?? this.density,
      weekStart: weekStart ?? this.weekStart,
      defaultHome: defaultHome ?? this.defaultHome,
      loading: loading ?? this.loading,
      error: clearError ? null : error ?? this.error,
    );
  }

  ThemeMode get themeMode => switch (theme) {
        'light' => ThemeMode.light,
        'dark' => ThemeMode.dark,
        _ => ThemeMode.system,
      };

  VisualDensity get visualDensity => density == 'compact' ? VisualDensity.compact : VisualDensity.standard;

  String get landingRoute => switch (defaultHome) {
        'my_tasks' => '/my-tasks',
        'calendar' => '/calendar',
        _ => '/home',
      };
}

class PreferencesController extends StateNotifier<UserPreferences> {
  PreferencesController(this.ref) : super(UserPreferences.defaults());

  final Ref ref;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final response = await ref.read(apiProvider).dio.get('/api/v1/settings/user');
      state = UserPreferences.fromJson((response.data as Map).cast<String, dynamic>());
    } catch (_) {
      state = state.copyWith(loading: false, error: 'Could not load preferences.');
    }
  }

  Future<void> update({
    required String theme,
    required String density,
    required int weekStart,
    required String defaultHome,
  }) async {
    final previous = state;
    state = UserPreferences(
      theme: theme,
      density: density,
      weekStart: weekStart,
      defaultHome: defaultHome,
      loading: true,
    );
    try {
      final response = await ref.read(apiProvider).dio.patch(
        '/api/v1/settings/user',
        data: {
          'theme': theme,
          'density': density,
          'week_start': weekStart,
          'default_home': defaultHome,
        },
      );
      state = UserPreferences.fromJson((response.data as Map).cast<String, dynamic>());
    } catch (_) {
      state = previous.copyWith(error: 'Could not save preferences.');
      rethrow;
    }
  }

  void reset() => state = UserPreferences.defaults();
}

final preferencesProvider = StateNotifierProvider<PreferencesController, UserPreferences>(
  (ref) => PreferencesController(ref),
);
