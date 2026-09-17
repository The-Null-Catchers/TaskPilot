import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/api.dart';
import 'task_models.dart';

class MyTasksState {
  const MyTasksState({this.loading = true, this.offline = false, this.tasks = const [], this.error});
  final bool loading;
  final bool offline;
  final List<TaskItem> tasks;
  final String? error;
}

final myTasksProvider = StateNotifierProvider.family<MyTasksController, MyTasksState, String>((ref, scope) => MyTasksController(ref.watch(apiProvider), scope)..load());

class MyTasksController extends StateNotifier<MyTasksState> {
  MyTasksController(this.api, this.scope) : super(const MyTasksState());
  final ApiClient api;
  final String scope;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final cacheKey = 'cached_my_tasks_$scope';
    try {
      final response = await api.dio.get('/api/v1/my-tasks', queryParameters: {'scope': scope, 'sort_by': 'due_date', 'sort_direction': 'asc', 'limit': 100});
      final data = (response.data as Map).cast<String, dynamic>();
      final tasks = (data['items'] as List).map((item) => TaskItem.fromJson((item as Map).cast<String, dynamic>())).toList();
      await prefs.setString(cacheKey, jsonEncode(tasks.map((item) => item.toJson()).toList()));
      state = MyTasksState(loading: false, tasks: tasks);
    } catch (_) {
      final cached = prefs.getString(cacheKey);
      if (cached != null) {
        final tasks = (jsonDecode(cached) as List).map((item) => TaskItem.fromJson((item as Map).cast<String, dynamic>())).toList();
        state = MyTasksState(loading: false, offline: true, tasks: tasks);
      } else {
        state = const MyTasksState(loading: false, offline: true, error: 'Connect to the internet to load My Tasks.');
      }
    }
  }
}
