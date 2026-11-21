import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:taskpilot_mobile/src/core/api.dart';
import 'package:taskpilot_mobile/src/core/offline_queue.dart';

class _Reply {
  const _Reply(this.statusCode, [this.body = '{}']);

  final int statusCode;
  final String body;
}

class _NetworkFailure {
  const _NetworkFailure();
}

class _ScriptedAdapter implements HttpClientAdapter {
  _ScriptedAdapter(this.script);

  final List<Object> script;
  final List<RequestOptions> requests = [];
  int calls = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    if (calls >= script.length) {
      throw StateError('No scripted response for ${options.method} ${options.path}');
    }
    final step = script[calls++];
    if (step is _NetworkFailure) {
      throw DioException(
        requestOptions: options,
        type: DioExceptionType.connectionError,
        error: 'offline',
      );
    }
    final reply = step as _Reply;
    return ResponseBody.fromString(
      reply.body,
      reply.statusCode,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Future<ApiClient> _apiWith(List<Object> script) async {
  FlutterSecureStorage.setMockInitialValues({
    'current_user_id': 'user-1',
    'access_token': 'access-token',
  });
  final api = ApiClient(const FlutterSecureStorage());
  api.dio.httpClientAdapter = _ScriptedAdapter(script);
  return api;
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('network failure queues edit and successful reconnect replays it', () async {
    final api = await _apiWith([
      const _NetworkFailure(),
      const _Reply(200),
    ]);
    final adapter = api.dio.httpClientAdapter as _ScriptedAdapter;
    final controller = OfflineQueueController(api);
    await controller.initialize();

    final outcome = await controller.mutate(
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 2, 'title': 'Offline title'},
      label: 'Update DEV-1',
    );

    expect(outcome, MutationOutcome.queued);
    expect(controller.state.pendingCount, 1);
    expect(controller.state.items.single.status, OfflineMutationStatus.pending);
    final mutationId = controller.state.items.single.id;

    await controller.sync();

    expect(controller.state.items, isEmpty);
    expect(controller.state.syncing, isFalse);
    expect(adapter.requests, hasLength(2));
    expect(
      adapter.requests.map((request) => request.headers['Idempotency-Key']),
      everyElement(mutationId),
    );
  });

  test('409 is preserved as a conflict for explicit resolution', () async {
    final api = await _apiWith([const _Reply(409, '{"detail":"conflict"}')]);
    final controller = OfflineQueueController(api);
    await controller.initialize();

    final outcome = await controller.mutate(
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 1, 'title': 'Stale edit'},
      label: 'Update DEV-1',
    );

    expect(outcome, MutationOutcome.conflict);
    expect(controller.state.conflictCount, 1);
    expect(controller.state.items.single.error, contains('newer version'));
  });

  test('401 preserves queued edit as sign-in required and can retry later', () async {
    final api = await _apiWith([
      const _Reply(401, '{"detail":"expired"}'),
      const _Reply(200),
    ]);
    final controller = OfflineQueueController(api);
    await controller.initialize();

    final outcome = await controller.mutate(
      method: 'POST',
      path: '/api/v1/tasks/task-1/comments',
      data: const {'body': 'Keep this comment'},
      label: 'Comment on DEV-1',
    );

    expect(outcome, MutationOutcome.queued);
    expect(controller.state.authRequiredCount, 1);
    final item = controller.state.items.single;
    expect(item.status, OfflineMutationStatus.authRequired);
    expect(item.error, contains('Sign in again'));

    await controller.retry(item.id);

    expect(controller.state.items, isEmpty);
  });

  test('a conflict survives controller restart with the original draft', () async {
    final api = await _apiWith([const _Reply(409, '{"detail":"conflict"}')]);
    final first = OfflineQueueController(api);
    await first.initialize();

    final outcome = await first.mutate(
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 1, 'title': 'Keep this offline draft'},
      label: 'Update DEV-1',
    );

    expect(outcome, MutationOutcome.conflict);
    final restored = OfflineQueueController(api);
    await restored.initialize();

    expect(restored.state.conflictCount, 1);
    expect(restored.state.items.single.status, OfflineMutationStatus.conflict);
    expect(restored.state.items.single.data['version'], 1);
    expect(restored.state.items.single.data['title'], 'Keep this offline draft');
  });

  test('queued edits are restored from account-scoped local storage', () async {
    final api = await _apiWith([const _NetworkFailure()]);
    final first = OfflineQueueController(api);
    await first.initialize();

    await first.mutate(
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 4, 'priority': 'high'},
      label: 'Prioritize DEV-1',
    );
    expect(first.state.items, hasLength(1));

    final restored = OfflineQueueController(api);
    await restored.initialize();

    expect(restored.state.items, hasLength(1));
    expect(restored.state.items.single.label, 'Prioritize DEV-1');
    expect(restored.state.items.single.data['version'], 4);
  });

  test('a conflict blocks later mutations until the user resolves it', () async {
    final api = await _apiWith([
      const _Reply(409, '{"detail":"conflict"}'),
    ]);
    final adapter = api.dio.httpClientAdapter as _ScriptedAdapter;
    final controller = OfflineQueueController(api);
    await controller.initialize();

    await controller.mutate(
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 1, 'title': 'First draft'},
      label: 'Update DEV-1',
    );
    final second = await controller.mutate(
      method: 'POST',
      path: '/api/v1/tasks/task-1/comments/rich',
      data: const {'body': 'Second queued action'},
      label: 'Comment on DEV-1',
    );

    expect(second, MutationOutcome.queued);
    expect(controller.state.items, hasLength(2));
    await controller.sync();

    expect(adapter.requests, hasLength(1));
    expect(controller.state.items.first.status, OfflineMutationStatus.conflict);
    expect(controller.state.items.last.status, OfflineMutationStatus.pending);
  });

  test('temporary server failures stay queued and reuse the same idempotency key', () async {
    final api = await _apiWith([
      const _NetworkFailure(),
      const _Reply(503, '{"detail":"unavailable"}'),
      const _Reply(200),
    ]);
    final adapter = api.dio.httpClientAdapter as _ScriptedAdapter;
    final controller = OfflineQueueController(api);
    await controller.initialize();

    await controller.mutate(
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 1, 'title': 'Retry safely'},
      label: 'Update DEV-1',
    );
    final mutationId = controller.state.items.single.id;

    await controller.sync();
    expect(controller.state.pendingCount, 1);
    await controller.sync();

    expect(controller.state.items, isEmpty);
    expect(adapter.requests, hasLength(3));
    expect(
      adapter.requests.map((request) => request.headers['Idempotency-Key']),
      everyElement(mutationId),
    );
  });

  test('account switching never exposes another account queued mutations', () async {
    final api = await _apiWith([const _NetworkFailure()]);
    final controller = OfflineQueueController(api);
    await controller.initialize();

    await controller.mutate(
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 1, 'title': 'Private user one draft'},
      label: 'Update DEV-1',
    );
    expect(controller.state.items, hasLength(1));

    await api.storage.write(key: 'current_user_id', value: 'user-2');
    await controller.initialize();
    expect(controller.state.items, isEmpty);

    await api.storage.write(key: 'current_user_id', value: 'user-1');
    await controller.initialize();
    expect(controller.state.items, hasLength(1));
    expect(controller.state.items.single.data['title'], 'Private user one draft');
  });

  test('conflict preview compares the current server values before applying', () async {
    const server = '{"id":"task-1","version":4,"title":"Web title","description":"Web body","priority":"high","status":"open"}';
    final api = await _apiWith([
      const _Reply(409, '{"detail":"conflict"}'),
      const _Reply(200, server),
      const _Reply(200, server),
      const _Reply(200, '{"id":"task-1","version":5,"title":"Mobile title"}'),
    ]);
    final adapter = api.dio.httpClientAdapter as _ScriptedAdapter;
    final controller = OfflineQueueController(api);
    await controller.initialize();

    await controller.mutate(
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 2, 'title': 'Mobile title', 'description': 'Mobile body'},
      label: 'Update DEV-1',
    );
    final mutationId = controller.state.items.single.id;
    final preview = await controller.previewConflict(mutationId);

    expect(preview?.canApply, isTrue);
    expect(preview?.serverVersion, 4);
    expect(preview?.serverValues['title'], 'Web title');
    expect(preview?.localValues['title'], 'Mobile title');

    final applied = await controller.applyLocalConflict(
      mutationId,
      expectedServerVersion: 4,
    );

    expect(applied, isTrue);
    expect(controller.state.items, isEmpty);
    expect(adapter.requests.last.headers['Idempotency-Key'], mutationId);
  });

  test('conflict resolution refuses to overwrite a server version changed after review', () async {
    final api = await _apiWith([
      const _Reply(409, '{"detail":"conflict"}'),
      const _Reply(200, '{"id":"task-1","version":4,"title":"Server v4"}'),
      const _Reply(200, '{"id":"task-1","version":5,"title":"Server v5"}'),
    ]);
    final adapter = api.dio.httpClientAdapter as _ScriptedAdapter;
    final controller = OfflineQueueController(api);
    await controller.initialize();

    await controller.mutate(
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 2, 'title': 'My draft'},
      label: 'Update DEV-1',
    );
    final mutationId = controller.state.items.single.id;
    await controller.previewConflict(mutationId);

    final applied = await controller.applyLocalConflict(
      mutationId,
      expectedServerVersion: 4,
    );

    expect(applied, isFalse);
    expect(adapter.requests, hasLength(3));
    expect(controller.state.conflictCount, 1);
    expect(controller.state.items.single.data['title'], 'My draft');
    expect(controller.state.items.single.error, contains('changed again'));
  });
}
