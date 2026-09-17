import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';

enum OfflineMutationStatus { pending, conflict, failed }
enum MutationOutcome { synced, queued, conflict }

class OfflineMutation {
  const OfflineMutation({
    required this.id,
    required this.method,
    required this.path,
    required this.data,
    required this.label,
    required this.createdAt,
    required this.status,
    this.error,
  });

  final String id;
  final String method;
  final String path;
  final Map<String, dynamic> data;
  final String label;
  final DateTime createdAt;
  final OfflineMutationStatus status;
  final String? error;

  OfflineMutation copyWith({
    Map<String, dynamic>? data,
    OfflineMutationStatus? status,
    String? error,
    bool clearError = false,
  }) =>
      OfflineMutation(
        id: id,
        method: method,
        path: path,
        data: data ?? this.data,
        label: label,
        createdAt: createdAt,
        status: status ?? this.status,
        error: clearError ? null : error ?? this.error,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'method': method,
        'path': path,
        'data': data,
        'label': label,
        'created_at': createdAt.toIso8601String(),
        'status': status.name,
        'error': error,
      };

  factory OfflineMutation.fromJson(Map<String, dynamic> json) => OfflineMutation(
        id: json['id'] as String,
        method: json['method'] as String,
        path: json['path'] as String,
        data: (json['data'] as Map).cast<String, dynamic>(),
        label: json['label'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
        status: OfflineMutationStatus.values.firstWhere(
          (item) => item.name == json['status'],
          orElse: () => OfflineMutationStatus.pending,
        ),
        error: json['error'] as String?,
      );
}

class OfflineQueueState {
  const OfflineQueueState({this.loading = true, this.syncing = false, this.items = const []});
  final bool loading;
  final bool syncing;
  final List<OfflineMutation> items;

  int get pendingCount => items.where((item) => item.status == OfflineMutationStatus.pending).length;
  int get conflictCount => items.where((item) => item.status == OfflineMutationStatus.conflict).length;
}

final offlineQueueProvider = StateNotifierProvider<OfflineQueueController, OfflineQueueState>(
  (ref) => OfflineQueueController(ref.watch(apiProvider))..initialize(),
);

class OfflineQueueController extends StateNotifier<OfflineQueueState> {
  OfflineQueueController(this.api) : super(const OfflineQueueState());
  final ApiClient api;
  static const _storageKey = 'taskpilot_offline_mutations_v1';

  Future<void> initialize() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_storageKey);
    final items = raw == null
        ? <OfflineMutation>[]
        : (jsonDecode(raw) as List)
            .map((item) => OfflineMutation.fromJson((item as Map).cast<String, dynamic>()))
            .toList();
    state = OfflineQueueState(loading: false, items: items);
    await sync();
  }

  Future<void> _persist(List<OfflineMutation> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_storageKey, jsonEncode(items.map((item) => item.toJson()).toList()));
    state = OfflineQueueState(loading: false, syncing: state.syncing, items: items);
  }

  String _id() => '${DateTime.now().microsecondsSinceEpoch}-${state.items.length}';

  bool _networkFailure(DioException error) =>
      error.response == null ||
      error.type == DioExceptionType.connectionError ||
      error.type == DioExceptionType.connectionTimeout ||
      error.type == DioExceptionType.sendTimeout ||
      error.type == DioExceptionType.receiveTimeout;

  Future<MutationOutcome> mutate({
    required String method,
    required String path,
    required Map<String, dynamic> data,
    required String label,
  }) async {
    try {
      await api.dio.request(path, data: data, options: Options(method: method));
      return MutationOutcome.synced;
    } on DioException catch (error) {
      final conflict = error.response?.statusCode == 409;
      if (!conflict && !_networkFailure(error)) rethrow;
      final mutation = OfflineMutation(
        id: _id(),
        method: method,
        path: path,
        data: Map<String, dynamic>.from(data),
        label: label,
        createdAt: DateTime.now().toUtc(),
        status: conflict ? OfflineMutationStatus.conflict : OfflineMutationStatus.pending,
        error: conflict ? 'Server data changed while you were editing.' : null,
      );
      await _persist([...state.items, mutation]);
      return conflict ? MutationOutcome.conflict : MutationOutcome.queued;
    }
  }

  Future<void> sync() async {
    if (state.loading || state.syncing || state.items.isEmpty) return;
    state = OfflineQueueState(loading: false, syncing: true, items: state.items);
    final next = <OfflineMutation>[];
    var offline = false;
    for (final mutation in state.items) {
      if (mutation.status == OfflineMutationStatus.conflict) {
        next.add(mutation);
        continue;
      }
      if (offline) {
        next.add(mutation);
        continue;
      }
      try {
        await api.dio.request(
          mutation.path,
          data: mutation.data,
          options: Options(method: mutation.method),
        );
      } on DioException catch (error) {
        if (error.response?.statusCode == 409) {
          next.add(mutation.copyWith(
            status: OfflineMutationStatus.conflict,
            error: 'Server data changed while this offline edit was queued.',
          ));
        } else if (_networkFailure(error)) {
          offline = true;
          next.add(mutation.copyWith(status: OfflineMutationStatus.pending, clearError: true));
        } else {
          next.add(mutation.copyWith(
            status: OfflineMutationStatus.failed,
            error: 'Request failed with HTTP ${error.response?.statusCode ?? 'unknown'}.',
          ));
        }
      }
    }
    state = OfflineQueueState(loading: false, items: next);
    await _persist(next);
  }

  Future<void> discard(String id) async {
    await _persist(state.items.where((item) => item.id != id).toList());
  }

  Future<void> retry(String id) async {
    final items = state.items
        .map((item) => item.id == id
            ? item.copyWith(status: OfflineMutationStatus.pending, clearError: true)
            : item)
        .toList();
    await _persist(items);
    await sync();
  }

  Future<void> applyLocalConflict(String id) async {
    final mutation = state.items.where((item) => item.id == id).firstOrNull;
    if (mutation == null) return;
    var data = Map<String, dynamic>.from(mutation.data);
    if (mutation.method.toUpperCase() == 'PATCH' &&
        mutation.path.startsWith('/api/v1/tasks/') &&
        !mutation.path.substring('/api/v1/tasks/'.length).contains('/')) {
      try {
        final response = await api.dio.get(mutation.path);
        final server = (response.data as Map).cast<String, dynamic>();
        final version = server['version'];
        if (version is int) data['version'] = version;
      } on DioException {
        return;
      }
    }
    try {
      await api.dio.request(mutation.path, data: data, options: Options(method: mutation.method));
      await discard(id);
    } on DioException catch (error) {
      final updated = state.items
          .map((item) => item.id == id
              ? item.copyWith(
                  data: data,
                  status: error.response?.statusCode == 409
                      ? OfflineMutationStatus.conflict
                      : OfflineMutationStatus.failed,
                  error: error.response?.statusCode == 409
                      ? 'The server changed again. Reload before applying your edit.'
                      : 'Could not apply local changes.',
                )
              : item)
          .toList();
      await _persist(updated);
    }
  }
}

extension _IterableFirstOrNull<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
