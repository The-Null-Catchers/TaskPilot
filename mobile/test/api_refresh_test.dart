import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:taskpilot_mobile/src/core/api.dart';

class _ConcurrentRefreshAdapter implements HttpClientAdapter {
  int refreshCalls = 0;
  int authorizedCalls = 0;

  ResponseBody _response(int status, String body) => ResponseBody.fromString(
        body,
        status,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (options.path.endsWith('/api/v1/auth/refresh')) {
      refreshCalls++;
      await Future<void>.delayed(const Duration(milliseconds: 30));
      return _response(
        200,
        '{"access_token":"new-token","refresh_token":"new-refresh","user":{"id":"user-1"}}',
      );
    }
    if (options.headers['Authorization'] == 'Bearer new-token') {
      authorizedCalls++;
      return _response(200, '{"ok":true}');
    }
    return _response(401, '{"detail":"expired"}');
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  test('simultaneous expired requests share one refresh rotation', () async {
    FlutterSecureStorage.setMockInitialValues({
      'current_user_id': 'user-1',
      'access_token': 'old-token',
      'refresh_token': 'old-refresh',
    });
    final api = ApiClient(const FlutterSecureStorage());
    final adapter = _ConcurrentRefreshAdapter();
    api.dio.httpClientAdapter = adapter;

    final responses = await Future.wait([
      api.dio.get('/protected-a'),
      api.dio.get('/protected-b'),
    ]);

    expect(responses, hasLength(2));
    expect(responses.every((response) => response.statusCode == 200), isTrue);
    expect(adapter.refreshCalls, 1);
    expect(adapter.authorizedCalls, 2);
    expect(await api.storage.read(key: 'access_token'), 'new-token');
    expect(await api.storage.read(key: 'refresh_token'), 'new-refresh');
  });
}
