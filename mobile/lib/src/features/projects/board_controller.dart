import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../core/api.dart';
import '../tasks/task_models.dart';

class BoardState {
  const BoardState({this.loading = true, this.offline = false, this.board, this.error});
  final bool loading;
  final bool offline;
  final BoardData? board;
  final String? error;
}

final boardProvider = StateNotifierProvider.family<BoardController, BoardState, String>((ref, projectId) {
  return BoardController(ref.watch(apiProvider), projectId)..load();
});

class BoardController extends StateNotifier<BoardState> {
  BoardController(this.api, this.projectId) : super(const BoardState());
  final ApiClient api;
  final String projectId;
  WebSocketChannel? _channel;
  bool _connecting = false;

  Future<void> load({bool quiet = false}) async {
    final prefs = await SharedPreferences.getInstance();
    final cacheKey = 'cached_board_$projectId';
    if (!quiet) state = BoardState(loading: true, board: state.board);
    try {
      final response = await api.dio.get('/api/v1/projects/$projectId/board');
      final board = BoardData.fromJson((response.data as Map).cast<String, dynamic>());
      await prefs.setString(cacheKey, jsonEncode(board.toJson()));
      state = BoardState(loading: false, board: board);
      await _connectRealtime(board.project.workspaceId);
    } catch (_) {
      final cached = prefs.getString(cacheKey);
      if (cached != null) {
        state = BoardState(loading: false, offline: true, board: BoardData.fromJson((jsonDecode(cached) as Map).cast<String, dynamic>()));
      } else {
        state = const BoardState(loading: false, offline: true, error: 'Connect to the internet to load this board.');
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
      final uri = Uri.parse('$wsBase/api/v1/ws/workspaces/$workspaceId').replace(queryParameters: {'token': token});
      _channel = WebSocketChannel.connect(uri);
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

  Future<void> moveTask(TaskItem task, BoardColumn destination) async {
    final current = state.board;
    if (current == null || task.columnId == destination.id) return;
    final destinationTasks = current.tasks.where((item) => item.columnId == destination.id).toList()..sort((a, b) => a.position.compareTo(b.position));
    final position = destinationTasks.isEmpty ? 1000.0 : destinationTasks.last.position + 1000.0;
    try {
      await api.dio.post('/api/v1/tasks/${task.id}/move', data: {'column_id': destination.id, 'position': position, 'version': task.version});
      await load(quiet: true);
    } catch (_) {
      rethrow;
    }
  }

  @override
  void dispose() {
    _channel?.sink.close();
    super.dispose();
  }
}
