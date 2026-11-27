import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:taskpilot_mobile/src/core/api.dart';
import 'package:taskpilot_mobile/src/features/home/home_controller.dart';

class _CacheAdapter implements HttpClientAdapter {
  _CacheAdapter(this.responses);

  final List<ResponseBody?> responses;
  int calls = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final response = responses[calls++];
    if (response == null) {
      throw DioException(
        requestOptions: options,
        type: DioExceptionType.connectionError,
        error: 'offline',
      );
    }
    return response;
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody _jsonResponse(String body) => ResponseBody.fromString(
      body,
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({
      'current_user_id': 'user-1',
      'access_token': 'test-token',
    });
  });

  test('offline workspace cache never leaks into another account', () async {
    final api = ApiClient(const FlutterSecureStorage());
    api.dio.httpClientAdapter = _CacheAdapter([
      _jsonResponse('[{"id":"workspace-1","name":"Private workspace"}]'),
      null,
      null,
    ]);

    final first = HomeController(api);
    await first.load();
    expect(first.state.workspaces.single.name, 'Private workspace');

    await api.storage.write(key: 'current_user_id', value: 'user-2');
    final second = HomeController(api);
    await second.load();
    expect(second.state.offline, isTrue);
    expect(second.state.workspaces, isEmpty);

    await api.storage.write(key: 'current_user_id', value: 'user-1');
    final restored = HomeController(api);
    await restored.load();
    expect(restored.state.offline, isTrue);
    expect(restored.state.workspaces.single.name, 'Private workspace');
  });
}
