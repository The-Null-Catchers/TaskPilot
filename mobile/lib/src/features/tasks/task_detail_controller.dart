import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/api.dart';
import '../../core/offline_queue.dart';
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

class LabelItem {
  const LabelItem({required this.id, required this.name, required this.color});
  final String id;
  final String name;
  final String color;
  factory LabelItem.fromJson(Map<String, dynamic> json) => LabelItem(id: json['id'] as String, name: json['name'] as String, color: json['color'] as String);
}

class DependencyItem {
  const DependencyItem({required this.id, required this.blockerTaskId, required this.blockedTaskId});
  final String id;
  final String blockerTaskId;
  final String blockedTaskId;
  factory DependencyItem.fromJson(Map<String, dynamic> json) => DependencyItem(
        id: json['id'] as String,
        blockerTaskId: json['blocker_task_id'] as String,
        blockedTaskId: json['blocked_task_id'] as String,
      );
}

class TaskDetailState {
  const TaskDetailState({
    this.loading = true,
    this.offline = false,
    this.pendingSync = false,
    this.conflict = false,
    this.task,
    this.comments = const [],
    this.assignees = const [],
    this.members = const [],
    this.subtasks = const [],
    this.checklists = const [],
    this.workspaceLabels = const [],
    this.taskLabels = const [],
    this.blockedBy = const [],
    this.projectTasks = const [],
    this.watching = false,
    this.watcherCount = 0,
    this.blocked = false,
    this.error,
  });
  final bool loading;
  final bool offline;
  final bool pendingSync;
  final bool conflict;
  final TaskItem? task;
  final List<CommentItem> comments;
  final List<PersonItem> assignees;
  final List<PersonItem> members;
  final List<SubtaskItem> subtasks;
  final List<ChecklistGroup> checklists;
  final List<LabelItem> workspaceLabels;
  final List<LabelItem> taskLabels;
  final List<DependencyItem> blockedBy;
  final List<TaskItem> projectTasks;
  final bool watching;
  final int watcherCount;
  final bool blocked;
  final String? error;
}

final taskDetailProvider = StateNotifierProvider.family<TaskDetailController, TaskDetailState, String>((ref, taskId) => TaskDetailController(ref.watch(apiProvider), ref.read(offlineQueueProvider.notifier), taskId)..load());

class TaskDetailController extends StateNotifier<TaskDetailState> {
  TaskDetailController(this.api, this.queue, this.taskId) : super(const TaskDetailState());
  final ApiClient api;
  final OfflineQueueController queue;
  final String taskId;

  TaskDetailState _withStatus({TaskItem? task, bool? offline, bool? pendingSync, bool? conflict}) => TaskDetailState(
        loading: false,
        offline: offline ?? state.offline,
        pendingSync: pendingSync ?? state.pendingSync,
        conflict: conflict ?? state.conflict,
        task: task ?? state.task,
        comments: state.comments,
        assignees: state.assignees,
        members: state.members,
        subtasks: state.subtasks,
        checklists: state.checklists,
        workspaceLabels: state.workspaceLabels,
        taskLabels: state.taskLabels,
        blockedBy: state.blockedBy,
        projectTasks: state.projectTasks,
        watching: state.watching,
        watcherCount: state.watcherCount,
        blocked: state.blocked,
        error: state.error,
      );

  Future<void> load({bool quiet = false}) async {
    final prefs = await SharedPreferences.getInstance();
    final cacheKey = 'cached_task_$taskId';
    if (!quiet) state = TaskDetailState(loading: true, task: state.task, pendingSync: state.pendingSync, conflict: state.conflict);
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
      var workspaceLabels = <LabelItem>[];
      var taskLabels = <LabelItem>[];
      var blockedBy = <DependencyItem>[];
      var projectTasks = <TaskItem>[];
      var watching = false;
      var watcherCount = 0;
      var blocked = false;
      try {
        final labelResponses = await Future.wait([
          api.dio.get('/api/v1/workspaces/${task.workspaceId}/labels'),
          api.dio.get('/api/v1/tasks/$taskId/labels'),
          api.dio.get('/api/v1/tasks/$taskId/collaboration-state'),
          api.dio.get('/api/v1/tasks/$taskId/dependencies'),
          api.dio.get('/api/v1/projects/${task.projectId}/board'),
        ]);
        workspaceLabels = (labelResponses[0].data as List).map((item) => LabelItem.fromJson((item as Map).cast<String, dynamic>())).toList();
        taskLabels = (labelResponses[1].data as List).map((item) => LabelItem.fromJson((item as Map).cast<String, dynamic>())).toList();
        final collaboration = (labelResponses[2].data as Map).cast<String, dynamic>();
        watching = collaboration['watching'] == true;
        watcherCount = (collaboration['watcher_count'] as num?)?.toInt() ?? 0;
        blocked = collaboration['blocked'] == true;
        final dependencies = (labelResponses[3].data as Map).cast<String, dynamic>();
        blockedBy = ((dependencies['blocked_by'] as List?) ?? const []).map((item) => DependencyItem.fromJson((item as Map).cast<String, dynamic>())).toList();
        final board = (labelResponses[4].data as Map).cast<String, dynamic>();
        projectTasks = ((board['tasks'] as List?) ?? const []).map((item) => TaskItem.fromJson((item as Map).cast<String, dynamic>())).toList();
      } catch (_) {
        // Core task detail remains usable if optional collaboration metadata fails.
      }
      state = TaskDetailState(
        loading: false,
        task: task,
        comments: comments,
        assignees: assignees,
        members: members,
        subtasks: subtasks,
        checklists: checklists,
        workspaceLabels: workspaceLabels,
        taskLabels: taskLabels,
        blockedBy: blockedBy,
        projectTasks: projectTasks,
        watching: watching,
        watcherCount: watcherCount,
        blocked: blocked,
      );
    } catch (_) {
      final cached = prefs.getString(cacheKey);
      if (cached != null) {
        state = TaskDetailState(loading: false, offline: true, pendingSync: state.pendingSync, conflict: state.conflict, task: TaskItem.fromJson((jsonDecode(cached) as Map).cast<String, dynamic>()));
      } else {
        state = TaskDetailState(loading: false, offline: true, pendingSync: state.pendingSync, conflict: state.conflict, error: 'Connect to the internet to load this task.');
      }
    }
  }

  Future<MutationOutcome> updateTask({required String title, required String description, required String priority, required String status, String? dueDate}) async {
    final task = state.task;
    if (task == null) return MutationOutcome.conflict;
    final data = {'version': task.version, 'title': title, 'description': description, 'priority': priority, 'status': status, 'due_date': dueDate};
    final outcome = await queue.mutate(method: 'PATCH', path: '/api/v1/tasks/$taskId', data: data, label: 'Update ${task.identifier}');
    if (outcome == MutationOutcome.synced) {
      await load(quiet: true);
    } else {
      final optimistic = task.copyWith(title: title, description: description, priority: priority, status: status, dueDate: dueDate, clearDueDate: dueDate == null, version: task.version + 1, updatedAt: DateTime.now().toUtc().toIso8601String());
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('cached_task_$taskId', jsonEncode(optimistic.toJson()));
      state = _withStatus(task: optimistic, offline: true, pendingSync: outcome == MutationOutcome.queued, conflict: outcome == MutationOutcome.conflict);
    }
    return outcome;
  }

  Future<MutationOutcome> addComment(String body) async {
    final outcome = await queue.mutate(method: 'POST', path: '/api/v1/tasks/$taskId/comments', data: {'body': body}, label: 'Comment on ${state.task?.identifier ?? 'task'}');
    if (outcome == MutationOutcome.synced) await load(quiet: true);
    return outcome;
  }

  Future<MutationOutcome> assign(String userId) async {
    final outcome = await queue.mutate(method: 'POST', path: '/api/v1/tasks/$taskId/assignees', data: {'user_id': userId}, label: 'Assign ${state.task?.identifier ?? 'task'}');
    if (outcome == MutationOutcome.synced) await load(quiet: true);
    return outcome;
  }

  Future<MutationOutcome> unassign(String userId) async {
    final outcome = await queue.mutate(method: 'DELETE', path: '/api/v1/tasks/$taskId/assignees/$userId', data: const {}, label: 'Unassign ${state.task?.identifier ?? 'task'}');
    if (outcome == MutationOutcome.synced) await load(quiet: true);
    return outcome;
  }

  Future<MutationOutcome> addSubtask(String title) async {
    final outcome = await queue.mutate(method: 'POST', path: '/api/v1/tasks/$taskId/subtasks', data: {'title': title}, label: 'Add subtask to ${state.task?.identifier ?? 'task'}');
    if (outcome == MutationOutcome.synced) await load(quiet: true);
    return outcome;
  }

  Future<MutationOutcome> toggleSubtask(SubtaskItem item) async {
    final outcome = await queue.mutate(method: 'PATCH', path: '/api/v1/tasks/$taskId/subtasks/${item.id}', data: {'version': item.version, 'status': item.status == 'done' ? 'open' : 'done'}, label: 'Update subtask');
    if (outcome == MutationOutcome.synced) await load(quiet: true);
    return outcome;
  }

  Future<MutationOutcome> addChecklist(String title) async {
    final outcome = await queue.mutate(method: 'POST', path: '/api/v1/tasks/$taskId/checklists', data: {'title': title}, label: 'Add checklist to ${state.task?.identifier ?? 'task'}');
    if (outcome == MutationOutcome.synced) await load(quiet: true);
    return outcome;
  }

  Future<MutationOutcome> addChecklistItem(String checklistId, String title) async {
    final outcome = await queue.mutate(method: 'POST', path: '/api/v1/tasks/$taskId/checklists/$checklistId/items', data: {'title': title}, label: 'Add checklist item');
    if (outcome == MutationOutcome.synced) await load(quiet: true);
    return outcome;
  }

  Future<MutationOutcome> toggleChecklistItem(String checklistId, ChecklistItemModel item) async {
    final outcome = await queue.mutate(method: 'PATCH', path: '/api/v1/tasks/$taskId/checklists/$checklistId/items/${item.id}', data: {'version': item.version, 'completed': !item.completed}, label: 'Update checklist item');
    if (outcome == MutationOutcome.synced) await load(quiet: true);
    return outcome;
  }

  Future<void> toggleWatch() async {
    await api.dio.request('/api/v1/tasks/$taskId/watch', options: Options(method: state.watching ? 'DELETE' : 'POST'));
    await load(quiet: true);
  }

  Future<void> addLabel(String labelId) async {
    await api.dio.post('/api/v1/tasks/$taskId/labels', data: {'label_id': labelId});
    await load(quiet: true);
  }

  Future<void> removeLabel(String labelId) async {
    await api.dio.delete('/api/v1/tasks/$taskId/labels/$labelId');
    await load(quiet: true);
  }

  Future<void> addDependency(String blockerTaskId) async {
    await api.dio.post('/api/v1/tasks/$taskId/dependencies', data: {'blocker_task_id': blockerTaskId});
    await load(quiet: true);
  }

  Future<void> removeDependency(String dependencyId) async {
    await api.dio.delete('/api/v1/tasks/$taskId/dependencies/$dependencyId');
    await load(quiet: true);
  }
}
