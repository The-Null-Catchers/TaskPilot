import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/api.dart';
import 'task_models.dart';

class PersonItem {
  const PersonItem({required this.id, required this.name, required this.email});
  final String id;
  final String name;
  final String email;
  factory PersonItem.fromJson(Map<String, dynamic> json) => PersonItem(id: (json['id'] ?? json['user_id']) as String, name: json['name'] as String, email: json['email'] as String);
}

class SubtaskItem {
  const SubtaskItem({required this.id, required this.title, required this.status, required this.version});
  final String id;
  final String title;
  final String status;
  final int version;
  factory SubtaskItem.fromJson(Map<String, dynamic> json) => SubtaskItem(id: json['id'] as String, title: json['title'] as String, status: json['status'] as String, version: json['version'] as int);
}

class ChecklistItemModel {
  const ChecklistItemModel({required this.id, required this.title, required this.completed, required this.version});
  final String id;
  final String title;
  final bool completed;
  final int version;
  factory ChecklistItemModel.fromJson(Map<String, dynamic> json) => ChecklistItemModel(id: json['id'] as String, title: json['title'] as String, completed: json['completed'] as bool, version: json['version'] as int);
}

class ChecklistGroup {
  const ChecklistGroup({required this.id, required this.title, required this.items});
  final String id;
  final String title;
  final List<ChecklistItemModel> items;
}

class TaskDetailState {
  const TaskDetailState({this.loading = true, this.offline = false, this.task, this.comments = const [], this.assignees = const [], this.members = const [], this.subtasks = const [], this.checklists = const [], this.error});
  final bool loading;
  final bool offline;
  final TaskItem? task;
  final List<CommentItem> comments;
  final List<PersonItem> assignees;
  final List<PersonItem> members;
  final List<SubtaskItem> subtasks;
  final List<ChecklistGroup> checklists;
  final String? error;
}

final taskDetailProvider = StateNotifierProvider.family<TaskDetailController, TaskDetailState, String>((ref, taskId) => TaskDetailController(ref.watch(apiProvider), taskId)..load());

class TaskDetailController extends StateNotifier<TaskDetailState> {
  TaskDetailController(this.api, this.taskId) : super(const TaskDetailState());
  final ApiClient api;
  final String taskId;

  Future<void> load({bool quiet = false}) async {
    final prefs = await SharedPreferences.getInstance();
    final cacheKey = 'cached_task_$taskId';
    if (!quiet) state = TaskDetailState(loading: true, task: state.task);
    try {
      final taskResponse = await api.dio.get('/api/v1/tasks/$taskId');
      final task = TaskItem.fromJson((taskResponse.data as Map).cast<String, dynamic>());
      await prefs.setString(cacheKey, jsonEncode(task.toJson()));
      final responses = await Future.wait([
        api.dio.get('/api/v1/tasks/$taskId/comments'),
        api.dio.get('/api/v1/tasks/$taskId/assignees'),
        api.dio.get('/api/v1/workspaces/${task.workspaceId}/members'),
        api.dio.get('/api/v1/tasks/$taskId/subtasks'),
        api.dio.get('/api/v1/tasks/$taskId/checklists'),
      ]);
      final comments = (responses[0].data as List).map((item) => CommentItem.fromJson((item as Map).cast<String, dynamic>())).toList();
      final assignees = (responses[1].data as List).map((item) => PersonItem.fromJson((item as Map).cast<String, dynamic>())).toList();
      final members = (responses[2].data as List).map((item) => PersonItem.fromJson((item as Map).cast<String, dynamic>())).toList();
      final subtasks = (responses[3].data as List).map((item) => SubtaskItem.fromJson((item as Map).cast<String, dynamic>())).toList();
      final rawChecklists = (responses[4].data as List).map((item) => (item as Map).cast<String, dynamic>()).toList();
      final checklists = <ChecklistGroup>[];
      for (final checklist in rawChecklists) {
        final id = checklist['id'] as String;
        final itemResponse = await api.dio.get('/api/v1/tasks/$taskId/checklists/$id/items');
        checklists.add(ChecklistGroup(id: id, title: checklist['title'] as String, items: (itemResponse.data as List).map((item) => ChecklistItemModel.fromJson((item as Map).cast<String, dynamic>())).toList()));
      }
      state = TaskDetailState(loading: false, task: task, comments: comments, assignees: assignees, members: members, subtasks: subtasks, checklists: checklists);
    } catch (_) {
      final cached = prefs.getString(cacheKey);
      if (cached != null) {
        state = TaskDetailState(loading: false, offline: true, task: TaskItem.fromJson((jsonDecode(cached) as Map).cast<String, dynamic>()));
      } else {
        state = const TaskDetailState(loading: false, offline: true, error: 'Connect to the internet to load this task.');
      }
    }
  }

  Future<void> updateTask({required String title, required String description, required String priority, required String status, String? dueDate}) async {
    final task = state.task;
    if (task == null) return;
    await api.dio.patch('/api/v1/tasks/$taskId', data: {'version': task.version, 'title': title, 'description': description, 'priority': priority, 'status': status, 'due_date': dueDate});
    await load(quiet: true);
  }

  Future<void> addComment(String body) async {
    await api.dio.post('/api/v1/tasks/$taskId/comments', data: {'body': body});
    await load(quiet: true);
  }

  Future<void> assign(String userId) async {
    await api.dio.post('/api/v1/tasks/$taskId/assignees', data: {'user_id': userId});
    await load(quiet: true);
  }

  Future<void> unassign(String userId) async {
    await api.dio.delete('/api/v1/tasks/$taskId/assignees/$userId');
    await load(quiet: true);
  }

  Future<void> addSubtask(String title) async {
    await api.dio.post('/api/v1/tasks/$taskId/subtasks', data: {'title': title});
    await load(quiet: true);
  }

  Future<void> toggleSubtask(SubtaskItem item) async {
    await api.dio.patch('/api/v1/tasks/$taskId/subtasks/${item.id}', data: {'version': item.version, 'status': item.status == 'done' ? 'open' : 'done'});
    await load(quiet: true);
  }

  Future<void> addChecklist(String title) async {
    await api.dio.post('/api/v1/tasks/$taskId/checklists', data: {'title': title});
    await load(quiet: true);
  }

  Future<void> addChecklistItem(String checklistId, String title) async {
    await api.dio.post('/api/v1/tasks/$taskId/checklists/$checklistId/items', data: {'title': title});
    await load(quiet: true);
  }

  Future<void> toggleChecklistItem(String checklistId, ChecklistItemModel item) async {
    await api.dio.patch('/api/v1/tasks/$taskId/checklists/$checklistId/items/${item.id}', data: {'version': item.version, 'completed': !item.completed});
    await load(quiet: true);
  }
}
