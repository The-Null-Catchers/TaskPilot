import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api.dart';
import '../tasks/task_models.dart';

class NotificationsState {
  const NotificationsState({this.loading = true, this.items = const [], this.error});
  final bool loading;
  final List<NotificationItem> items;
  final String? error;
}

final notificationsProvider = StateNotifierProvider<NotificationsController, NotificationsState>((ref) => NotificationsController(ref.watch(apiProvider))..load());

class NotificationsController extends StateNotifier<NotificationsState> {
  NotificationsController(this.api) : super(const NotificationsState());
  final ApiClient api;

  Future<void> load() async {
    try {
      final response = await api.dio.get('/api/v1/notifications');
      final items = (response.data as List).map((item) => NotificationItem.fromJson((item as Map).cast<String, dynamic>())).toList();
      state = NotificationsState(loading: false, items: items);
    } catch (_) {
      state = const NotificationsState(loading: false, error: 'Could not load notifications.');
    }
  }

  Future<void> markRead(String id) async {
    await api.dio.post('/api/v1/notifications/$id/read');
    await load();
  }

  Future<void> markAllRead() async {
    await api.dio.post('/api/v1/notifications/read-all');
    await load();
  }
}
