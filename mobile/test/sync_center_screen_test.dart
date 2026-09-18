import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:taskpilot_mobile/src/core/api.dart';
import 'package:taskpilot_mobile/src/core/offline_queue.dart';
import 'package:taskpilot_mobile/src/features/sync/sync_center_screen.dart';

class _TestOfflineQueueController extends OfflineQueueController {
  _TestOfflineQueueController(ApiClient api, OfflineQueueState initial) : super(api) {
    state = initial;
  }

  @override
  Future<void> initialize() async {}

  @override
  Future<void> sync() async {}
}

void main() {
  testWidgets('Sync Center distinguishes conflicts from sign-in-required edits', (tester) async {
    FlutterSecureStorage.setMockInitialValues({'current_user_id': 'user-1'});
    final api = ApiClient(const FlutterSecureStorage());
    final controller = _TestOfflineQueueController(
      api,
      OfflineQueueState(
        loading: false,
        items: [
          OfflineMutation(
            id: 'auth-1',
            method: 'POST',
            path: '/api/v1/tasks/task-1/comments',
            data: const {'body': 'queued'},
            label: 'Comment on DEV-1',
            createdAt: DateTime.utc(2026, 9, 18),
            status: OfflineMutationStatus.authRequired,
            error: 'Sign in again to sync this queued change.',
          ),
          OfflineMutation(
            id: 'conflict-1',
            method: 'PATCH',
            path: '/api/v1/tasks/task-2',
            data: const {'version': 2, 'title': 'local'},
            label: 'Update DEV-2',
            createdAt: DateTime.utc(2026, 9, 18),
            status: OfflineMutationStatus.conflict,
            error: 'Server data changed.',
          ),
        ],
      ),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          offlineQueueProvider.overrideWith((ref) => controller),
        ],
        child: const MaterialApp(home: SyncCenterScreen()),
      ),
    );

    expect(find.text('Sync Center'), findsOneWidget);
    expect(find.text('2 local changes'), findsOneWidget);
    expect(find.text('0 pending · 1 conflicts · 1 need sign-in'), findsOneWidget);
    expect(find.text('Sign in required'), findsOneWidget);
    expect(find.text('Needs review'), findsOneWidget);
    expect(find.text('Apply my changes'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });
}
