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
  int calls = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
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

    await controller.sync();

    expect(controller.state.items, isEmpty);
    expect(controller.state.syncing, isFalse);
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
    expect(controller.state.items.single.error, contains('Server data changed'));
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
}
