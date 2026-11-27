import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:taskpilot_mobile/src/core/api.dart';
import 'package:taskpilot_mobile/src/core/offline_queue.dart';
import 'package:taskpilot_mobile/src/core/push_registration.dart';
import 'package:taskpilot_mobile/src/features/auth/auth_controller.dart';

class _SessionAdapter implements HttpClientAdapter {
  _SessionAdapter(this.status);

  final int? status;
  final List<RequestOptions> requests = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    final code = status;
    if (code == null) {
      throw DioException(
        requestOptions: options,
        type: DioExceptionType.connectionError,
      );
    }
    return ResponseBody.fromString(
      code == 200
          ? '{"access_token":"new-access","refresh_token":"new-refresh","user":{"id":"user-1"}}'
          : '{"detail":"unavailable"}',
      code,
      headers: {Headers.contentTypeHeader: [Headers.jsonContentType]},
    );
  }

  @override
  void close({bool force = false}) {}
}

class _PushStub extends PushRegistrationService {
  _PushStub(super.api);

  int unregisterCalls = 0;

  @override
  Future<void> unregister() async {
    unregisterCalls++;
  }
}

ApiClient _api(int? status) {
  final api = ApiClient(const FlutterSecureStorage());
  api.dio.httpClientAdapter = _SessionAdapter(status);
  return api;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({
      'current_user_id': 'user-1',
      'access_token': 'old-access',
      'refresh_token': 'old-refresh',
    });
    SharedPreferences.setMockInitialValues({});
  });

  test('offline cold start retains account and restores queued draft before reconnect', () async {
    final firstApi = _api(null);
    final firstQueue = OfflineQueueController(firstApi);
    await firstQueue.initialize();
    expect(
      await firstQueue.mutate(
        method: 'PATCH',
        path: '/api/v1/tasks/task-1',
        data: const {'version': 1, 'title': 'Saved before restart'},
        label: 'Update task',
      ),
      MutationOutcome.queued,
    );
    final mutationId = firstQueue.state.items.single.id;
    firstQueue.dispose();
    firstApi.dio.close();

    final restartedApi = _api(null);
    final push = _PushStub(restartedApi);
    final auth = AuthController(restartedApi, push);
    await auth.restore();

    expect(auth.state.authenticated, isTrue);
    expect(await restartedApi.currentUserId(), 'user-1');
    expect(await restartedApi.storage.read(key: 'refresh_token'), 'old-refresh');
    expect(push.unregisterCalls, 0);

    final restoredQueue = OfflineQueueController(restartedApi);
    await restoredQueue.initialize();
    expect(restoredQueue.state.items.single.id, mutationId);
    expect(restoredQueue.state.items.single.data['title'], 'Saved before restart');

    final onlineAdapter = _SessionAdapter(409);
    restartedApi.dio.httpClientAdapter = onlineAdapter;
    await restoredQueue.sync();
    expect(restoredQueue.state.conflictCount, 1);
    expect(restoredQueue.state.items.single.data['title'], 'Saved before restart');
    expect(onlineAdapter.requests.single.headers['Idempotency-Key'], mutationId);
  });

  test('temporary refresh server error keeps local account and credentials', () async {
    final api = _api(503);
    final push = _PushStub(api);
    final auth = AuthController(api, push);
    await auth.restore();

    expect(auth.state.authenticated, isTrue);
    expect(await api.storage.read(key: 'refresh_token'), 'old-refresh');
    expect(push.unregisterCalls, 0);
  });

  test('rejected refresh signs out without retrying or deleting stored drafts', () async {
    final offlineApi = _api(null);
    final queue = OfflineQueueController(offlineApi);
    await queue.initialize();
    await queue.mutate(
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 1, 'title': 'Private draft'},
      label: 'Update task',
    );

    final api = _api(401);
    final push = _PushStub(api);
    final auth = AuthController(api, push);
    await auth.restore();

    expect(auth.state.authenticated, isFalse);
    expect(await api.currentUserId(), isNull);
    expect(await api.storage.read(key: 'refresh_token'), isNull);
    expect(push.unregisterCalls, 1);
    final adapter = api.dio.httpClientAdapter as _SessionAdapter;
    expect(adapter.requests, hasLength(1));
    expect(adapter.requests.single.extra['skipAuth'], isTrue);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('taskpilot_offline_mutations_v1_user-1'), contains('Private draft'));
    final restoredQueue = OfflineQueueController(api);
    await restoredQueue.initialize();
    expect(restoredQueue.state.items, isEmpty);
  });

  test('offline startup without an identified account does not unlock local drafts', () async {
    FlutterSecureStorage.setMockInitialValues({'refresh_token': 'old-refresh'});
    final api = _api(null);
    final auth = AuthController(api, _PushStub(api));
    await auth.restore();

    expect(auth.state.authenticated, isFalse);
    expect(auth.state.error, contains('Connect to the internet'));
    expect(await api.storage.read(key: 'refresh_token'), 'old-refresh');
  });

  test('online startup still rotates tokens and restores session', () async {
    final api = _api(200);
    final auth = AuthController(api, _PushStub(api));
    await auth.restore();

    expect(auth.state.authenticated, isTrue);
    expect(await api.storage.read(key: 'access_token'), 'new-access');
    expect(await api.storage.read(key: 'refresh_token'), 'new-refresh');
  });
}
