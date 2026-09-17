import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api.dart';

class AuthState {
  const AuthState({this.loading = false, this.authenticated = false, this.error});
  final bool loading;
  final bool authenticated;
  final String? error;
  AuthState copyWith({bool? loading, bool? authenticated, String? error}) => AuthState(loading: loading ?? this.loading, authenticated: authenticated ?? this.authenticated, error: error);
}

final authProvider = StateNotifierProvider<AuthController, AuthState>((ref) => AuthController(ref.watch(apiProvider))..restore());

class AuthController extends StateNotifier<AuthState> {
  AuthController(this.api) : super(const AuthState(loading: true));
  final ApiClient api;

  Future<void> restore() async {
    final refresh = await api.storage.read(key: 'refresh_token');
    if (refresh == null) { state = const AuthState(); return; }
    try {
      final response = await api.dio.post('/api/v1/auth/refresh', data: {'refresh_token': refresh, 'client': 'mobile'});
      await api.saveTokens(response.data as Map<String, dynamic>);
      state = const AuthState(authenticated: true);
    } catch (_) {
      await api.clearTokens();
      state = const AuthState();
    }
  }

  Future<bool> login(String email, String password) async {
    state = const AuthState(loading: true);
    try {
      final response = await api.dio.post('/api/v1/auth/login', data: {'email': email.trim(), 'password': password, 'client': 'mobile', 'device_name': 'Flutter'});
      await api.saveTokens(response.data as Map<String, dynamic>);
      state = const AuthState(authenticated: true);
      return true;
    } on DioException catch (e) {
      state = AuthState(error: (e.response?.data is Map ? e.response?.data['detail'] : null)?.toString() ?? 'Unable to sign in');
      return false;
    }
  }

  Future<bool> register(String name, String email, String password) async {
    state = const AuthState(loading: true);
    try {
      final response = await api.dio.post('/api/v1/auth/register', data: {'name': name.trim(), 'email': email.trim(), 'password': password});
      if (response.statusCode == 201) return await login(email, password);
      return false;
    } on DioException catch (e) {
      state = AuthState(error: (e.response?.data is Map ? e.response?.data['detail'] : null)?.toString() ?? 'Unable to register');
      return false;
    }
  }

  Future<void> logout() async {
    await api.clearTokens();
    state = const AuthState();
  }
}
