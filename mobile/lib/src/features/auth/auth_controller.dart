import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api.dart';
import '../../core/push_registration.dart';

class AuthState {
  const AuthState({this.loading = false, this.authenticated = false, this.needsOnboarding = false, this.error});
  final bool loading;
  final bool authenticated;
  final bool needsOnboarding;
  final String? error;
  AuthState copyWith({bool? loading, bool? authenticated, bool? needsOnboarding, String? error}) => AuthState(
    loading: loading ?? this.loading,
    authenticated: authenticated ?? this.authenticated,
    needsOnboarding: needsOnboarding ?? this.needsOnboarding,
    error: error,
  );
}

final authProvider = StateNotifierProvider<AuthController, AuthState>((ref) => AuthController(ref.watch(apiProvider), ref.watch(pushRegistrationProvider))..restore());

class AuthController extends StateNotifier<AuthState> {
  AuthController(this.api, this.pushRegistration) : super(const AuthState(loading: true));
  final ApiClient api;
  final PushRegistrationService pushRegistration;

  Future<void> restore() async {
    final refresh = await api.storage.read(key: 'refresh_token');
    if (refresh == null) { state = const AuthState(); return; }
    try {
      final response = await api.dio.post('/api/v1/auth/refresh', data: {'refresh_token': refresh, 'client': 'mobile'});
      await api.saveTokens(response.data as Map<String, dynamic>);
      final userId = await api.currentUserId();
      final onboardingUserId = await api.storage.read(key: 'onboarding_required_user_id');
      state = AuthState(authenticated: true, needsOnboarding: userId != null && onboardingUserId == userId);
    } catch (_) {
      await pushRegistration.unregister();
      await api.clearTokens();
      state = const AuthState();
    }
  }

  Future<bool> login(String email, String password, {bool requireOnboarding = false}) async {
    state = const AuthState(loading: true);
    try {
      final response = await api.dio.post('/api/v1/auth/login', data: {'email': email.trim(), 'password': password, 'client': 'mobile', 'device_name': 'Flutter'});
      await api.saveTokens(response.data as Map<String, dynamic>);
      final userId = await api.currentUserId();
      if (requireOnboarding && userId != null) {
        await api.storage.write(key: 'onboarding_required_user_id', value: userId);
      }
      final onboardingUserId = await api.storage.read(key: 'onboarding_required_user_id');
      state = AuthState(authenticated: true, needsOnboarding: userId != null && onboardingUserId == userId);
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
      if (response.statusCode == 201) return await login(email, password, requireOnboarding: true);
      return false;
    } on DioException catch (e) {
      state = AuthState(error: (e.response?.data is Map ? e.response?.data['detail'] : null)?.toString() ?? 'Unable to register');
      return false;
    }
  }

  Future<void> completeOnboarding({String? useCase}) async {
    if (useCase != null && useCase.isNotEmpty) {
      await api.storage.write(key: 'onboarding_use_case', value: useCase);
    }
    await api.storage.delete(key: 'onboarding_required_user_id');
    state = state.copyWith(needsOnboarding: false, error: null);
  }

  Future<void> logout() async {
    await pushRegistration.unregister();
    await api.clearTokens();
    state = const AuthState();
  }
}
