import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api.dart';

final pushRegistrationProvider = Provider<PushRegistrationService>(
  (ref) => PushRegistrationService(ref.watch(apiProvider)),
);

class PushRegistrationService {
  PushRegistrationService(this.api);
  final ApiClient api;

  StreamSubscription<String>? _tokenRefresh;
  StreamSubscription<RemoteMessage>? _opened;
  bool _initializing = false;

  String get _platform {
    if (kIsWeb) return 'web';
    return switch (defaultTargetPlatform) {
      TargetPlatform.android => 'android',
      TargetPlatform.iOS => 'ios',
      TargetPlatform.macOS => 'macos',
      TargetPlatform.windows => 'windows',
      TargetPlatform.linux => 'linux',
      TargetPlatform.fuchsia => 'fuchsia',
    };
  }

  Future<void> initialize({
    required void Function(Map<String, dynamic> data) onOpen,
  }) async {
    if (_initializing || kIsWeb) return;
    _initializing = true;
    try {
      final providerResponse = await api.dio.get('/api/v1/notifications/provider-config');
      final providerConfig = (providerResponse.data as Map).cast<String, dynamic>();
      if (providerConfig['fcm_enabled'] != true) return;

      if (Firebase.apps.isEmpty) {
        try {
          await Firebase.initializeApp();
        } catch (_) {
          // Firebase client configuration is deployment-specific. The app
          // remains fully usable when no Firebase configuration is bundled.
          return;
        }
      }

      final messaging = FirebaseMessaging.instance;
      final permission = await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
      );
      if (permission.authorizationStatus == AuthorizationStatus.denied) return;

      await messaging.setAutoInitEnabled(true);
      final token = await messaging.getToken();
      if (token != null && token.isNotEmpty) {
        await _registerToken(token);
      }

      await _tokenRefresh?.cancel();
      _tokenRefresh = messaging.onTokenRefresh.listen((token) async {
        try {
          await _registerToken(token);
        } catch (_) {
          // A later app start or token refresh retries registration.
        }
      });

      await _opened?.cancel();
      _opened = FirebaseMessaging.onMessageOpenedApp.listen(
        (message) => onOpen(message.data),
      );

      final initial = await messaging.getInitialMessage();
      if (initial != null) onOpen(initial.data);
    } catch (_) {
      // Push is an optional delivery channel and must never block app startup.
    } finally {
      _initializing = false;
    }
  }

  Future<void> _registerToken(String token) async {
    final response = await api.dio.post(
      '/api/v1/notifications/subscriptions',
      data: {
        'channel': 'fcm',
        'target': token,
        'config': <String, dynamic>{},
        'device_name': 'TaskPilot Flutter',
        'platform': _platform,
      },
    );
    final data = (response.data as Map).cast<String, dynamic>();
    final subscriptionId = data['id'] as String?;
    if (subscriptionId != null) {
      await api.storage.write(key: 'push_subscription_id', value: subscriptionId);
    }
  }

  Future<void> unregister() async {
    final subscriptionId = await api.storage.read(key: 'push_subscription_id');
    if (subscriptionId != null) {
      try {
        await api.dio.delete('/api/v1/notifications/subscriptions/$subscriptionId');
      } catch (_) {
        // Token/session may already be revoked. Remove local ownership either way.
      }
    }
    await api.storage.delete(key: 'push_subscription_id');
    try {
      if (Firebase.apps.isNotEmpty) {
        await FirebaseMessaging.instance.deleteToken();
      }
    } catch (_) {}
    await _tokenRefresh?.cancel();
    _tokenRefresh = null;
    await _opened?.cancel();
    _opened = null;
  }
}
