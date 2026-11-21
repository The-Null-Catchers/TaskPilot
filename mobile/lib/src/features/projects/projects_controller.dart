import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/api.dart';
import '../auth/auth_controller.dart';
import '../tasks/task_models.dart';

class ProjectsState {
  const ProjectsState({this.loading = true, this.offline = false, this.projects = const [], this.error});
  final bool loading;
  final bool offline;
  final List<Project> projects;
  final String? error;
}

final projectsProvider = StateNotifierProvider.family<ProjectsController, ProjectsState, String>((ref, workspaceId) {
  ref.watch(authProvider);
  return ProjectsController(ref.watch(apiProvider), workspaceId)..load();
});

class ProjectsController extends StateNotifier<ProjectsState> {
  ProjectsController(this.api, this.workspaceId) : super(const ProjectsState());
  final ApiClient api;
  final String workspaceId;

  Future<void> load() async {
    final userId = await api.currentUserId();
    if (userId == null) {
      state = const ProjectsState(loading: false);
      return;
    }
    final prefs = await SharedPreferences.getInstance();
    final cacheKey = 'cached_projects_${userId}_$workspaceId';
    try {
      final response = await api.dio.get('/api/v1/projects', queryParameters: {'workspace_id': workspaceId});
      final items = (response.data as List).map((item) => Project.fromJson((item as Map).cast<String, dynamic>())).toList();
      if (!mounted || await api.currentUserId() != userId) return;
      await prefs.setString(cacheKey, jsonEncode(items.map((item) => item.toJson()).toList()));
      if (!mounted || await api.currentUserId() != userId) return;
      state = ProjectsState(loading: false, projects: items);
    } catch (_) {
      if (await api.currentUserId() != userId) return;
      final cached = prefs.getString(cacheKey);
      if (cached != null) {
        final items = (jsonDecode(cached) as List).map((item) => Project.fromJson((item as Map).cast<String, dynamic>())).toList();
        state = ProjectsState(loading: false, offline: true, projects: items);
      } else {
        state = const ProjectsState(loading: false, offline: true, error: 'Connect to the internet to load projects.');
      }
    }
  }
}
