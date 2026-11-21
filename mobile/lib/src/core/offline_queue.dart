import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../features/auth/auth_controller.dart';
import 'api.dart';

enum OfflineMutationStatus { pending, conflict, authRequired, failed }
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
  const OfflineQueueState({
    this.loading = true,
    this.syncing = false,
    this.items = const [],
  });

  final bool loading;
  final bool syncing;
  final List<OfflineMutation> items;

  int get pendingCount =>
      items.where((item) => item.status == OfflineMutationStatus.pending).length;
  int get conflictCount =>
      items.where((item) => item.status == OfflineMutationStatus.conflict).length;
  int get authRequiredCount =>
      items.where((item) => item.status == OfflineMutationStatus.authRequired).length;
  int get failedCount =>
      items.where((item) => item.status == OfflineMutationStatus.failed).length;
}

class OfflineConflictPreview {
  const OfflineConflictPreview({
    required this.supportsApply,
    required this.localValues,
    required this.serverValues,
    this.serverVersion,
    this.error,
  });

  final bool supportsApply;
  final int? serverVersion;
  final Map<String, dynamic> localValues;
  final Map<String, dynamic> serverValues;
  final String? error;

  bool get canApply => supportsApply && serverVersion != null;
}

final offlineQueueProvider =
    StateNotifierProvider<OfflineQueueController, OfflineQueueState>((ref) {
  final controller = OfflineQueueController(ref.watch(apiProvider));
  ref.listen(authProvider, (previous, next) {
    if (previous?.authenticated != next.authenticated) {
      unawaited(controller.initialize());
    }
  });
  unawaited(controller.initialize());
  return controller;
});

class OfflineQueueController extends StateNotifier<OfflineQueueState> {
  OfflineQueueController(this.api) : super(const OfflineQueueState());

  final ApiClient api;
  final Random _random = Random.secure();
  Future<void> _serial = Future<void>.value();
  String? _loadedUserId;

  String _storageKey(String userId) => 'taskpilot_offline_mutations_v1_$userId';

  Future<T> _serialized<T>(Future<T> Function() action) {
    final previous = _serial;
    final completer = Completer<void>();
    _serial = completer.future;
    return () async {
      await previous;
      try {
        return await action();
      } finally {
        completer.complete();
      }
    }();
  }

  Future<List<OfflineMutation>> _read(String userId) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_storageKey(userId));
    if (raw == null) return <OfflineMutation>[];
    return (jsonDecode(raw) as List)
        .map((item) => OfflineMutation.fromJson((item as Map).cast<String, dynamic>()))
        .toList();
  }

  Future<bool> _ensureCurrentUser() async {
    final userId = await api.currentUserId();
    if (userId == null) {
      _loadedUserId = null;
      if (mounted) state = const OfflineQueueState(loading: false);
      return false;
    }
    if (_loadedUserId == userId && !state.loading) return true;

    // Clear the previous account's visible queue before loading another account.
    _loadedUserId = userId;
    state = const OfflineQueueState(loading: true);
    final items = await _read(userId);
    if (await api.currentUserId() != userId) {
      _loadedUserId = null;
      if (mounted) state = const OfflineQueueState(loading: false);
      return false;
    }
    state = OfflineQueueState(loading: false, items: items);
    return true;
  }

  Future<void> initialize() => _serialized(() async {
        await _ensureCurrentUser();
      });

  Future<void> _persistForUser(String userId, List<OfflineMutation> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _storageKey(userId),
      jsonEncode(items.map((item) => item.toJson()).toList()),
    );

    // Always write to the captured account key. Never redirect an in-flight
    // mutation into whichever account happens to be active after a login switch.
    if (mounted &&
        _loadedUserId == userId &&
        await api.currentUserId() == userId) {
      state = OfflineQueueState(
        loading: false,
        syncing: state.syncing,
        items: items,
      );
    }
  }

  String _newMutationId() => List.generate(
        32,
        (_) => _random.nextInt(256).toRadixString(16).padLeft(2, '0'),
      ).join();

  bool _retryableFailure(DioException error) {
    final status = error.response?.statusCode;
    return error.response == null ||
        status == 408 ||
        status == 425 ||
        status == 429 ||
        (status != null && status >= 500);
  }

  OfflineMutationStatus? _statusForError(DioException error) {
    if (error.response?.statusCode == 409) return OfflineMutationStatus.conflict;
    if (error.response?.statusCode == 401) return OfflineMutationStatus.authRequired;
    if (_retryableFailure(error)) return OfflineMutationStatus.pending;
    return null;
  }

  String _errorFor(DioException error, OfflineMutationStatus status) {
    return switch (status) {
      OfflineMutationStatus.conflict =>
        'The server has a newer version. Review both versions before applying this draft.',
      OfflineMutationStatus.authRequired =>
        'Sign in again to sync this saved change. Your draft is being kept on this device.',
      OfflineMutationStatus.pending =>
        'TaskPilot is temporarily unavailable. This change is saved and will retry.',
      OfflineMutationStatus.failed =>
        'The request could not be completed (HTTP ${error.response?.statusCode ?? 'unknown'}).',
    };
  }

  Future<void> _send(OfflineMutation mutation) async {
    await api.dio.request(
      mutation.path,
      data: mutation.data,
      options: Options(
        method: mutation.method,
        headers: {'Idempotency-Key': mutation.id},
      ),
    );
  }

  Future<MutationOutcome> mutate({
    required String method,
    required String path,
    required Map<String, dynamic> data,
    required String label,
  }) =>
      _serialized(() async {
        if (!await _ensureCurrentUser()) {
          throw StateError('Offline changes require an authenticated account');
        }
        final userId = _loadedUserId!;
        final mutation = OfflineMutation(
          id: _newMutationId(),
          method: method.toUpperCase(),
          path: path,
          data: Map<String, dynamic>.from(data),
          label: label,
          createdAt: DateTime.now().toUtc(),
          status: OfflineMutationStatus.pending,
        );

        // Write-ahead persistence: a process crash while the first request is
        // in flight must not erase the draft. The same key is used on replay.
        final items = [...state.items, mutation];
        await _persistForUser(userId, items);

        // Once a queue exists, append instead of sending later operations ahead
        // of an unresolved earlier mutation.
        if (items.length > 1) return MutationOutcome.queued;

        try {
          if (await api.currentUserId() != userId) {
            return MutationOutcome.queued;
          }
          await _send(mutation);
          await _persistForUser(userId, const <OfflineMutation>[]);
          return MutationOutcome.synced;
        } on DioException catch (error) {
          final status = _statusForError(error);
          if (status == null) {
            await _persistForUser(
              userId,
              [mutation.copyWith(
                status: OfflineMutationStatus.failed,
                error: _errorFor(error, OfflineMutationStatus.failed),
              )],
            );
            return MutationOutcome.queued;
          }
          await _persistForUser(
            userId,
            [mutation.copyWith(status: status, error: _errorFor(error, status))],
          );
          return status == OfflineMutationStatus.conflict
              ? MutationOutcome.conflict
              : MutationOutcome.queued;
        }
      });

  Future<void> _syncLocked() async {
    if (!await _ensureCurrentUser()) return;
    if (state.syncing || state.items.isEmpty) return;

    final userId = _loadedUserId!;
    final remaining = List<OfflineMutation>.from(state.items);
    state = OfflineQueueState(loading: false, syncing: true, items: remaining);
    try {
      while (remaining.isNotEmpty) {
        if (await api.currentUserId() != userId) break;
        final mutation = remaining.first;
        // An unresolved conflict, failed request, or expired session blocks
        // all later mutations. Never reorder or silently skip it.
        if (mutation.status != OfflineMutationStatus.pending) break;

        try {
          await _send(mutation);
        } on DioException catch (error) {
          final status = _statusForError(error) ?? OfflineMutationStatus.failed;
          remaining[0] = mutation.copyWith(
            status: status,
            error: _errorFor(error, status),
          );
          await _persistForUser(userId, List<OfflineMutation>.from(remaining));
          break;
        } catch (_) {
          remaining[0] = mutation.copyWith(
            status: OfflineMutationStatus.failed,
            error: 'An unexpected sync error occurred. Your saved change is still here.',
          );
          await _persistForUser(userId, List<OfflineMutation>.from(remaining));
          break;
        }

        remaining.removeAt(0);
        // Checkpoint every acknowledged operation before sending the next.
        // After a process crash, replay can safely resume at the first
        // unacknowledged operation with its original idempotency key.
        await _persistForUser(userId, List<OfflineMutation>.from(remaining));
      }
    } finally {
      if (mounted) {
        state = OfflineQueueState(
          loading: false,
          items: List<OfflineMutation>.from(remaining),
        );
      }
    }
  }

  Future<void> sync() => _serialized(_syncLocked);

  Future<void> discard(String id) => _serialized(() async {
        if (!await _ensureCurrentUser()) return;
        final userId = _loadedUserId!;
        final index = state.items.indexWhere((item) => item.id == id);
        if (index < 0) return;
        final items = List<OfflineMutation>.from(state.items)..removeAt(index);
        await _persistForUser(userId, items);
        if (index == 0 && items.isNotEmpty) await _syncLocked();
      });

  Future<void> retry(String id) => _serialized(() async {
        if (!await _ensureCurrentUser()) return;
        final userId = _loadedUserId!;
        final index = state.items.indexWhere((item) => item.id == id);
        if (index < 0 || state.items[index].status == OfflineMutationStatus.conflict) {
          return;
        }
        final items = List<OfflineMutation>.from(state.items);
        items[index] = items[index].copyWith(
          status: OfflineMutationStatus.pending,
          clearError: true,
        );
        await _persistForUser(userId, items);
        await _syncLocked();
      });

  bool _isTaskPatch(OfflineMutation mutation) =>
      mutation.method.toUpperCase() == 'PATCH' &&
      RegExp(r'^/api/v1/tasks/[^/?]+$').hasMatch(mutation.path);

  Future<OfflineConflictPreview?> previewConflict(String id) =>
      _serialized(() async {
        if (!await _ensureCurrentUser()) return null;
        final mutation = state.items.where((item) => item.id == id).firstOrNull;
        if (mutation == null || mutation.status != OfflineMutationStatus.conflict) {
          return null;
        }

        final localValues = Map<String, dynamic>.from(mutation.data)
          ..remove('version');
        if (!_isTaskPatch(mutation)) {
          return OfflineConflictPreview(
            supportsApply: false,
            localValues: localValues,
            serverValues: const {},
            error: 'This operation needs to be reviewed in the task before it can be replayed.',
          );
        }

        try {
          final response = await api.dio.get(mutation.path);
          final server = (response.data as Map).cast<String, dynamic>();
          final version = server['version'];
          return OfflineConflictPreview(
            supportsApply: true,
            serverVersion: version is int ? version : null,
            localValues: localValues,
            serverValues: {
              for (final key in localValues.keys) key: server[key],
            },
          );
        } on DioException {
          return OfflineConflictPreview(
            supportsApply: false,
            localValues: localValues,
            serverValues: const {},
            error: 'The current server version could not be loaded. Your draft remains saved.',
          );
        }
      });

  Future<bool> applyLocalConflict(
    String id, {
    required int expectedServerVersion,
  }) =>
      _serialized(() async {
        if (!await _ensureCurrentUser()) return false;
        final userId = _loadedUserId!;
        final index = state.items.indexWhere((item) => item.id == id);
        if (index < 0) return false;
        final mutation = state.items[index];
        if (mutation.status != OfflineMutationStatus.conflict ||
            !_isTaskPatch(mutation)) {
          return false;
        }

        try {
          final latestResponse = await api.dio.get(mutation.path);
          final latest = (latestResponse.data as Map).cast<String, dynamic>();
          final currentVersion = latest['version'];
          if (currentVersion is! int) return false;
          if (currentVersion != expectedServerVersion) {
            final items = List<OfflineMutation>.from(state.items);
            items[index] = mutation.copyWith(
              error: 'The server changed again. Review the latest version before applying this draft.',
            );
            await _persistForUser(userId, items);
            return false;
          }

          final data = Map<String, dynamic>.from(mutation.data)
            ..['version'] = currentVersion;
          final response = await api.dio.request(
            mutation.path,
            data: data,
            options: Options(
              method: mutation.method,
              headers: {'Idempotency-Key': mutation.id},
            ),
          );
          final updated = (response.data as Map).cast<String, dynamic>();
          final newVersion = updated['version'] is int
              ? updated['version'] as int
              : currentVersion + 1;
          final originalVersion = mutation.data['version'] is int
              ? mutation.data['version'] as int
              : currentVersion;
          final versionShift = newVersion - originalVersion - 1;

          final items = List<OfflineMutation>.from(state.items)..removeAt(index);
          // Later edits to the same task were created against the optimistic
          // local sequence. Rebase their expected versions after this explicit
          // resolution so FIFO replay can continue safely.
          for (var nextIndex = index; nextIndex < items.length; nextIndex++) {
            final next = items[nextIndex];
            if (next.path != mutation.path ||
                next.method.toUpperCase() != 'PATCH') {
              continue;
            }
            final nextVersion = next.data['version'];
            if (nextVersion is int) {
              final nextData = Map<String, dynamic>.from(next.data)
                ..['version'] = nextVersion + versionShift;
              items[nextIndex] = next.copyWith(data: nextData);
            }
          }
          await _persistForUser(userId, items);
          if (items.isNotEmpty) await _syncLocked();
          return true;
        } on DioException catch (error) {
          final status = _statusForError(error) ?? OfflineMutationStatus.failed;
          final items = List<OfflineMutation>.from(state.items);
          items[index] = mutation.copyWith(
            status: status,
            error: _errorFor(error, status),
          );
          await _persistForUser(userId, items);
          return false;
        }
      });
}

extension _IterableFirstOrNull<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
