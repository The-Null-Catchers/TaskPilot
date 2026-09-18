import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../core/api.dart';
import '../../core/offline_queue.dart';
import '../tasks/task_models.dart';

class BoardState {
  const BoardState({this.loading = true, this.offline = false, this.pendingSync = false, this.conflict = false, this.board, this.error});
  final bool loading;
  final bool offline;
  final bool pendingSync;
  final bool conflict;
  final BoardData? board;
  final String? error;
}

final boardProvider = StateNotifierProvider.family<BoardController, BoardState, String>((ref, projectId) {
  return BoardController(ref.watch(apiProvider), ref.read(offlineQueueProvider.notifier), projectId)..load();
});

class BoardController extends StateNotifier<BoardState> {
  BoardController(this.api, this.queue, this.projectId) : super(const BoardState());
  final ApiClient api;
  final OfflineQueueController queue;
  final String projectId;
  WebSocketChannel? _channel;
  bool _connecting = false;

  Future<void> _cache(BoardData board) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('cached_board_$projectId', jsonEncode(board.toJson()));
  }

  Future<void> load({bool quiet = false}) async {
    final prefs = await SharedPreferences.getInstance();
    final cacheKey = 'cached_board_$projectId';
    if (!quiet) state = BoardState(loading: true, board: state.board, pendingSync: state.pendingSync, conflict: state.conflict);
    try {
      final response = await api.dio.get('/api/v1/projects/$projectId/board');
      final board = BoardData.fromJson((response.data as Map).cast<String, dynamic>());
      await prefs.setString(cacheKey, jsonEncode(board.toJson()));
      state = BoardState(loading: false, board: board);
      await _connectRealtime(board.project.workspaceId);
      await queue.sync();
    } catch (_) {
      final cached = prefs.getString(cacheKey);
      if (cached != null) {
        state = BoardState(loading: false, offline: true, pendingSync: state.pendingSync, conflict: state.conflict, board: BoardData.fromJson((jsonDecode(cached) as Map).cast<String, dynamic>()));
      } else {
        state = BoardState(loading: false, offline: true, pendingSync: state.pendingSync, conflict: state.conflict, error: 'Connect to the internet to load this board.');
      }
    }
  }

  Future<void> _connectRealtime(String workspaceId) async {
    if (_channel != null || _connecting) return;
    _connecting = true;
    final token = await api.storage.read(key: 'access_token');
    if (token == null) {
      _connecting = false;
      return;
    }
    try {
      final wsBase = apiBaseUrl.replaceFirst(RegExp(r'^http'), 'ws');
      final uri = Uri.parse('$wsBase/api/v1/ws/workspaces/$workspaceId');
      _channel = WebSocketChannel.connect(uri);
      _channel!.sink.add(jsonEncode({'type': 'auth', 'token': token}));
      _channel!.stream.listen((message) {
        try {
          final payload = jsonDecode(message as String) as Map<String, dynamic>;
          final event = payload['event'] as String?;
          if (event != null && (event.startsWith('task.') || event.startsWith('subtask.') || event.startsWith('checklist.'))) {
            load(quiet: true);
          }
        } catch (_) {}
      }, onDone: () {
        _channel = null;
      }, onError: (_) {
        _channel = null;
      });
    } catch (_) {
      _channel = null;
    } finally {
      _connecting = false;
    }
  }

  Future<TaskItem> createTask(String columnId, String title) async {
    final response = await api.dio.post('/api/v1/tasks', data: {'project_id': projectId, 'column_id': columnId, 'title': title});
    final task = TaskItem.fromJson((response.data as Map).cast<String, dynamic>());
    await load(quiet: true);
    return task;
  }

  Future<MutationOutcome> moveTask(TaskItem task, BoardColumn destination) async {
    final current = state.board;
    if (current == null || task.columnId == destination.id) return MutationOutcome.synced;
    final destinationTasks = current.tasks.where((item) => item.columnId == destination.id).toList()..sort((a, b) => a.position.compareTo(b.position));
    final position = destinationTasks.isEmpty ? 1000.0 : destinationTasks.last.position + 1000.0;
    final optimisticTask = task.copyWith(columnId: destination.id, position: position, version: task.version + 1, updatedAt: DateTime.now().toUtc().toIso8601String());
    final optimisticBoard = BoardData(project: current.project, columns: current.columns, tasks: current.tasks.map((item) => item.id == task.id ? optimisticTask : item).toList());
    state = BoardState(loading: false, board: optimisticBoard, offline: state.offline, pendingSync: state.pendingSync, conflict: state.conflict);
    await _cache(optimisticBoard);
    try {
      final outcome = await queue.mutate(
        method: 'POST',
        path: '/api/v1/tasks/${task.id}/move',
        data: {'column_id': destination.id, 'position': position, 'version': task.version},
        label: 'Move ${task.identifier} to ${destination.name}',
      );
      if (outcome == MutationOutcome.synced) {
        await load(quiet: true);
      } else {
        state = BoardState(loading: false, board: optimisticBoard, offline: true, pendingSync: outcome == MutationOutcome.queued, conflict: outcome == MutationOutcome.conflict);
      }
      return outcome;
    } catch (_) {
      state = BoardState(loading: false, board: current);
      await _cache(current);
      rethrow;
    }
  }

  @override
  void dispose() {
    _channel?.sink.close();
    super.dispose();
  }
}
