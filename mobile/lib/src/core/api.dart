import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

const apiBaseUrl = String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000');
final secureStorageProvider = Provider((ref) => const FlutterSecureStorage());

final apiProvider = Provider<ApiClient>((ref) {
  return ApiClient(ref.watch(secureStorageProvider));
});

class ApiClient {
  ApiClient(this.storage)
      : dio = Dio(BaseOptions(baseUrl: apiBaseUrl, connectTimeout: const Duration(seconds: 12), receiveTimeout: const Duration(seconds: 20))) {
    dio.interceptors.add(InterceptorsWrapper(onRequest: (options, handler) async {
      if (options.extra['skipAuth'] != true) {
        final token = await storage.read(key: 'access_token');
        if (token != null) options.headers['Authorization'] = 'Bearer $token';
      }
      handler.next(options);
    }, onError: (error, handler) async {
      if (error.response?.statusCode == 401 && error.requestOptions.extra['retried'] != true && error.requestOptions.extra['skipAuth'] != true) {
        try {
          final tokens = await _refreshTokens();
          final request = error.requestOptions..extra['retried'] = true;
          request.headers['Authorization'] = 'Bearer ${tokens['access_token']}';
          return handler.resolve(await dio.fetch(request));
        } catch (_) {
          // The original 401 remains visible to the offline queue. Never
          // silently discard a pending edit when refresh cannot succeed.
        }
      }
      handler.next(error);
    }));
  }

  final Dio dio;
  final FlutterSecureStorage storage;
  Future<Map<String, dynamic>>? _refreshing;

  Future<Map<String, dynamic>> _refreshTokens() {
    final active = _refreshing;
    if (active != null) return active;

    final operation = () async {
      final refresh = await storage.read(key: 'refresh_token');
      if (refresh == null) throw StateError('No refresh token');
      final account = await currentUserId();
      final response = await dio.post(
        '/api/v1/auth/refresh',
        data: {'refresh_token': refresh, 'client': 'mobile'},
        options: Options(extra: {'skipAuth': true}),
      );
      if (account != await currentUserId()) {
        throw StateError('Account changed during token refresh');
      }
      final tokens = (response.data as Map).cast<String, dynamic>();
      await saveTokens(tokens);
      return tokens;
    }();

    _refreshing = operation;
    return operation.whenComplete(() {
      _refreshing = null;
    });
  }

  Future<void> saveTokens(Map<String, dynamic> data) async {
    await storage.write(key: 'access_token', value: data['access_token'] as String?);
    final refresh = data['refresh_token'] as String?;
    if (refresh != null) await storage.write(key: 'refresh_token', value: refresh);
    final user = data['user'];
    if (user is Map && user['id'] is String) {
      await storage.write(key: 'current_user_id', value: user['id'] as String);
    }
  }

  Future<String?> currentUserId() => storage.read(key: 'current_user_id');

  Future<void> clearTokens() async {
    await storage.delete(key: 'access_token');
    await storage.delete(key: 'refresh_token');
    await storage.delete(key: 'current_user_id');
  }
}
