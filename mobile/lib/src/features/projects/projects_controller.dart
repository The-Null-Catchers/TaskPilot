import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/api.dart';
import '../tasks/task_models.dart';

class ProjectsState {
  const ProjectsState({this.loading = true, this.offline = false, this.projects = const [], this.error});
  final bool loading;
  final bool offline;
  final List<Project> projects;
  final String? error;
}

final projectsProvider = StateNotifierProvider.family<ProjectsController, ProjectsState, String>((ref, workspaceId) {
  return ProjectsController(ref.watch(apiProvider), workspaceId)..load();
});

class ProjectsController extends StateNotifier<ProjectsState> {
  ProjectsController(this.api, this.workspaceId) : super(const ProjectsState());
  final ApiClient api;
  final String workspaceId;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final cacheKey = 'cached_projects_$workspaceId';
    try {
      final response = await api.dio.get('/api/v1/projects', queryParameters: {'workspace_id': workspaceId});
      final items = (response.data as List).map((item) => Project.fromJson((item as Map).cast<String, dynamic>())).toList();
      await prefs.setString(cacheKey, jsonEncode(items.map((item) => item.toJson()).toList()));
      state = ProjectsState(loading: false, projects: items);
    } catch (_) {
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
