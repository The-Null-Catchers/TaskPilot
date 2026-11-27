import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/api.dart';
import '../auth/auth_controller.dart';

class Workspace {
  const Workspace({required this.id, required this.name});
  final String id;
  final String name;
  factory Workspace.fromJson(Map<String, dynamic> json) => Workspace(id: json['id'] as String, name: json['name'] as String);
  Map<String, dynamic> toJson() => {'id': id, 'name': name};
}

class HomeState {
  const HomeState({this.loading = true, this.offline = false, this.workspaces = const [], this.error});
  final bool loading;
  final bool offline;
  final List<Workspace> workspaces;
  final String? error;
}

final homeProvider = StateNotifierProvider<HomeController, HomeState>((ref) {
  ref.watch(authProvider);
  return HomeController(ref.watch(apiProvider))..load();
});

class HomeController extends StateNotifier<HomeState> {
  HomeController(this.api) : super(const HomeState());
  final ApiClient api;

  Future<void> load() async {
    final userId = await api.currentUserId();
    if (userId == null) {
      state = const HomeState(loading: false);
      return;
    }
    final cacheKey = 'cached_workspaces_$userId';
    final prefs = await SharedPreferences.getInstance();
    try {
      final response = await api.dio.get('/api/v1/workspaces');
      final items = (response.data as List).map((item) => Workspace.fromJson((item as Map).cast<String, dynamic>())).toList();
      if (!mounted || await api.currentUserId() != userId) return;
      await prefs.setString(cacheKey, jsonEncode(items.map((item) => item.toJson()).toList()));
      if (!mounted || await api.currentUserId() != userId) return;
      state = HomeState(loading: false, workspaces: items);
    } catch (_) {
      if (await api.currentUserId() != userId) return;
      final cached = prefs.getString(cacheKey);
      if (cached != null) {
        final items = (jsonDecode(cached) as List).map((item) => Workspace.fromJson((item as Map).cast<String, dynamic>())).toList();
        state = HomeState(loading: false, offline: true, workspaces: items);
      } else {
        state = const HomeState(loading: false, offline: true, error: 'Connect to the internet to load your workspace.');
      }
    }
  }

  Future<void> createWorkspace(String name) async {
    await api.dio.post('/api/v1/workspaces', data: {'name': name});
    await load();
  }
}
