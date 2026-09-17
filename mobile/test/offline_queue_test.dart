import 'package:flutter_test/flutter_test.dart';
import 'package:taskpilot_mobile/src/core/offline_queue.dart';
import 'package:taskpilot_mobile/src/features/tasks/task_models.dart';

void main() {
  test('offline mutation survives JSON round trip', () {
    final mutation = OfflineMutation(
      id: 'local-1',
      method: 'PATCH',
      path: '/api/v1/tasks/task-1',
      data: const {'version': 3, 'title': 'Offline title'},
      label: 'Update DEV-1',
      createdAt: DateTime.utc(2026, 9, 18, 9),
      status: OfflineMutationStatus.conflict,
      error: 'Server changed',
    );

    final decoded = OfflineMutation.fromJson(mutation.toJson());
    expect(decoded.id, mutation.id);
    expect(decoded.method, 'PATCH');
    expect(decoded.data['version'], 3);
    expect(decoded.status, OfflineMutationStatus.conflict);
    expect(decoded.error, 'Server changed');
  });

  test('queued mutation can be reset to pending without stale error', () {
    final mutation = OfflineMutation(
      id: 'local-2',
      method: 'POST',
      path: '/api/v1/tasks/task-1/comments',
      data: const {'body': 'Queued comment'},
      label: 'Comment on DEV-1',
      createdAt: DateTime.utc(2026, 9, 18, 9),
      status: OfflineMutationStatus.failed,
      error: 'HTTP 500',
    );

    final retried = mutation.copyWith(status: OfflineMutationStatus.pending, clearError: true);
    expect(retried.status, OfflineMutationStatus.pending);
    expect(retried.error, isNull);
  });

  test('task copyWith preserves identity and advances optimistic fields', () {
    const task = TaskItem(
      id: 'task-1',
      workspaceId: 'workspace-1',
      projectId: 'project-1',
      columnId: 'todo',
      identifier: 'DEV-1',
      title: 'Before',
      description: '',
      priority: 'medium',
      status: 'open',
      position: 1000,
      version: 2,
      createdAt: '2026-09-18T08:00:00Z',
      updatedAt: '2026-09-18T08:00:00Z',
      dueDate: '2026-09-20T10:00:00Z',
    );

    final optimistic = task.copyWith(
      title: 'After',
      columnId: 'doing',
      version: 3,
      clearDueDate: true,
    );
    expect(optimistic.id, task.id);
    expect(optimistic.identifier, 'DEV-1');
    expect(optimistic.title, 'After');
    expect(optimistic.columnId, 'doing');
    expect(optimistic.version, 3);
    expect(optimistic.dueDate, isNull);
  });
}
