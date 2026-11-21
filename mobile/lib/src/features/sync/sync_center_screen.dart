import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/offline_queue.dart';

class SyncCenterScreen extends ConsumerWidget {
  const SyncCenterScreen({super.key});

  Color _statusColor(BuildContext context, OfflineMutationStatus status) {
    return switch (status) {
      OfflineMutationStatus.pending => Theme.of(context).colorScheme.primary,
      OfflineMutationStatus.conflict => Theme.of(context).colorScheme.error,
      OfflineMutationStatus.authRequired => Theme.of(context).colorScheme.secondary,
      OfflineMutationStatus.failed => Theme.of(context).colorScheme.tertiary,
    };
  }

  String _statusLabel(OfflineMutationStatus status) => switch (status) {
        OfflineMutationStatus.pending => 'Pending sync',
        OfflineMutationStatus.conflict => 'Needs review',
        OfflineMutationStatus.authRequired => 'Sign in required',
        OfflineMutationStatus.failed => 'Failed',
      };

  String _displayValue(Object? value) {
    if (value == null) return 'Not set';
    if (value is Map || value is List) return value.toString();
    return value.toString();
  }

  Future<void> _reviewConflict(
    BuildContext context,
    WidgetRef ref,
    OfflineMutation mutation,
  ) async {
    final controller = ref.read(offlineQueueProvider.notifier);
    final preview = await controller.previewConflict(mutation.id);
    if (!context.mounted) return;
    if (preview == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('The saved conflict could not be loaded.')),
      );
      return;
    }

    final choice = await showDialog<int>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Review ${mutation.label}'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (preview.canApply)
                Text(
                  'The server is now at version ${preview.serverVersion}. Compare the current values with your saved draft before choosing.',
                )
              else
                Text(
                  preview.error ??
                      'The server version is not available. Your local draft is still saved.',
                ),
              if (preview.localValues.isNotEmpty) ...[
                const SizedBox(height: 16),
                ...preview.localValues.entries.map(
                  (entry) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          entry.key.replaceAll('_', ' ').toUpperCase(),
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 4),
                        Text('On server: ${_displayValue(preview.serverValues[entry.key])}'),
                        Text('Your draft: ${_displayValue(entry.value)}'),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, 0),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, 1),
            child: const Text('Keep server version'),
          ),
          if (preview.canApply)
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, 2),
              child: const Text('Apply my changes'),
            ),
        ],
      ),
    );

    if (!context.mounted || choice == null || choice == 0) return;
    if (choice == 1) {
      await controller.discard(mutation.id);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Kept the server version.')),
        );
      }
      return;
    }

    if (choice == 2 && preview.serverVersion != null) {
      final applied = await controller.applyLocalConflict(
        mutation.id,
        expectedServerVersion: preview.serverVersion!,
      );
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              applied
                  ? 'Your reviewed changes were applied.'
                  : 'The server changed or sync failed. Your draft remains in Sync Center.',
            ),
          ),
        );
      }
    }
  }

  Future<void> _discard(
    BuildContext context,
    OfflineQueueController controller,
    OfflineMutation mutation,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Discard local change?'),
        content: const Text(
          'This removes the saved change and keeps the server version.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
    if (confirmed == true) await controller.discard(mutation.id);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(offlineQueueProvider);
    final controller = ref.read(offlineQueueProvider.notifier);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sync Center'),
        actions: [
          IconButton(
            onPressed: state.syncing ? null : () => controller.sync(),
            icon: state.syncing
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.sync_rounded),
            tooltip: 'Sync now',
          ),
        ],
      ),
      body: SafeArea(
        child: state.loading
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: controller.sync,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 40),
                  children: [
                    Card(
                      elevation: 0,
                      child: Padding(
                        padding: const EdgeInsets.all(18),
                        child: Row(
                          children: [
                            Icon(
                              state.conflictCount > 0
                                  ? Icons.sync_problem_rounded
                                  : Icons.cloud_done_outlined,
                              color: state.conflictCount > 0
                                  ? Theme.of(context).colorScheme.error
                                  : Theme.of(context).colorScheme.primary,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    state.items.isEmpty
                                        ? 'Everything is synced'
                                        : '${state.items.length} local change${state.items.length == 1 ? '' : 's'}',
                                    style: const TextStyle(fontWeight: FontWeight.w700),
                                  ),
                                  const SizedBox(height: 3),
                                  Text(
                                    '${state.pendingCount} pending · '
                                    '${state.conflictCount} conflicts · '
                                    '${state.authRequiredCount} need sign-in · '
                                    '${state.failedCount} failed',
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    if (state.items.isEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 56),
                        child: Column(
                          children: [
                            Icon(
                              Icons.check_circle_outline_rounded,
                              size: 48,
                              color: Theme.of(context).colorScheme.primary,
                            ),
                            const SizedBox(height: 12),
                            const Text(
                              'No queued changes',
                              style: TextStyle(fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 4),
                            const Text(
                              'Offline edits will appear here until they reach TaskPilot.',
                              textAlign: TextAlign.center,
                            ),
                          ],
                        ),
                      )
                    else
                      ...state.items.map(
                        (item) => Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: Card(
                            elevation: 0,
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Expanded(
                                        child: Text(
                                          item.label,
                                          style: const TextStyle(fontWeight: FontWeight.w700),
                                        ),
                                      ),
                                      Container(
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 8,
                                          vertical: 4,
                                        ),
                                        decoration: BoxDecoration(
                                          color: _statusColor(context, item.status)
                                              .withValues(alpha: .12),
                                          borderRadius: BorderRadius.circular(999),
                                        ),
                                        child: Text(
                                          _statusLabel(item.status),
                                          style: TextStyle(
                                            fontSize: 11,
                                            fontWeight: FontWeight.w700,
                                            color: _statusColor(context, item.status),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    '${item.method} ${item.path}',
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                  if (item.error != null) ...[
                                    const SizedBox(height: 8),
                                    Text(
                                      item.error!,
                                      style: TextStyle(
                                        color: Theme.of(context).colorScheme.error,
                                        fontSize: 12,
                                      ),
                                    ),
                                  ],
                                  const SizedBox(height: 12),
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 8,
                                    children: [
                                      if (item.status == OfflineMutationStatus.conflict)
                                        FilledButton.tonal(
                                          onPressed: () => _reviewConflict(context, ref, item),
                                          child: const Text('Review conflict'),
                                        ),
                                      if (item.status == OfflineMutationStatus.failed ||
                                          item.status == OfflineMutationStatus.authRequired)
                                        OutlinedButton(
                                          onPressed: () => controller.retry(item.id),
                                          child: const Text('Retry'),
                                        ),
                                      if (item.status != OfflineMutationStatus.conflict)
                                        TextButton(
                                          onPressed: () => _discard(context, controller, item),
                                          child: const Text('Discard'),
                                        ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
      ),
    );
  }
}
