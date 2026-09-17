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
        final refresh = await storage.read(key: 'refresh_token');
        if (refresh != null) {
          try {
            final response = await dio.post('/api/v1/auth/refresh', data: {'refresh_token': refresh, 'client': 'mobile'}, options: Options(extra: {'skipAuth': true}));
            await saveTokens(response.data as Map<String, dynamic>);
            final request = error.requestOptions..extra['retried'] = true;
            request.headers['Authorization'] = 'Bearer ${response.data['access_token']}';
            return handler.resolve(await dio.fetch(request));
          } catch (_) {}
        }
      }
      handler.next(error);
    }));
  }

  final Dio dio;
  final FlutterSecureStorage storage;

  Future<void> saveTokens(Map<String, dynamic> data) async {
    await storage.write(key: 'access_token', value: data['access_token'] as String?);
    final refresh = data['refresh_token'] as String?;
    if (refresh != null) await storage.write(key: 'refresh_token', value: refresh);
  }

  Future<void> clearTokens() async {
    await storage.delete(key: 'access_token');
    await storage.delete(key: 'refresh_token');
  }
}
