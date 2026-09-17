import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/offline_queue.dart';

class SyncCenterScreen extends ConsumerWidget {
  const SyncCenterScreen({super.key});

  Color _statusColor(BuildContext context, OfflineMutationStatus status) {
    return switch (status) {
      OfflineMutationStatus.pending => Theme.of(context).colorScheme.primary,
      OfflineMutationStatus.conflict => Theme.of(context).colorScheme.error,
      OfflineMutationStatus.failed => Theme.of(context).colorScheme.tertiary,
    };
  }

  String _statusLabel(OfflineMutationStatus status) => switch (status) {
        OfflineMutationStatus.pending => 'Pending sync',
        OfflineMutationStatus.conflict => 'Needs review',
        OfflineMutationStatus.failed => 'Failed',
      };

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
                ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2))
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
                              state.conflictCount > 0 ? Icons.sync_problem_rounded : Icons.cloud_done_outlined,
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
                                    state.items.isEmpty ? 'Everything is synced' : '${state.items.length} local change${state.items.length == 1 ? '' : 's'}',
                                    style: const TextStyle(fontWeight: FontWeight.w700),
                                  ),
                                  const SizedBox(height: 3),
                                  Text('${state.pendingCount} pending · ${state.conflictCount} conflicts'),
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
                            Icon(Icons.check_circle_outline_rounded, size: 48, color: Theme.of(context).colorScheme.primary),
                            const SizedBox(height: 12),
                            const Text('No queued changes', style: TextStyle(fontWeight: FontWeight.w700)),
                            const SizedBox(height: 4),
                            const Text('Offline edits will appear here until they reach TaskPilot.', textAlign: TextAlign.center),
                          ],
                        ),
                      )
                    else
                      ...state.items.map((item) => Padding(
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
                                        Expanded(child: Text(item.label, style: const TextStyle(fontWeight: FontWeight.w700))),
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                          decoration: BoxDecoration(
                                            color: _statusColor(context, item.status).withValues(alpha: .12),
                                            borderRadius: BorderRadius.circular(999),
                                          ),
                                          child: Text(
                                            _statusLabel(item.status),
                                            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: _statusColor(context, item.status)),
                                          ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 6),
                                    Text('${item.method.toUpperCase()} ${item.path}', style: Theme.of(context).textTheme.bodySmall),
                                    if (item.error != null) ...[
                                      const SizedBox(height: 8),
                                      Text(item.error!, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12)),
                                    ],
                                    const SizedBox(height: 12),
                                    Wrap(
                                      spacing: 8,
                                      runSpacing: 8,
                                      children: [
                                        if (item.status == OfflineMutationStatus.conflict)
                                          FilledButton.tonal(
                                            onPressed: () => controller.applyLocalConflict(item.id),
                                            child: const Text('Apply my changes'),
                                          ),
                                        if (item.status != OfflineMutationStatus.conflict)
                                          OutlinedButton(
                                            onPressed: () => controller.retry(item.id),
                                            child: const Text('Retry'),
                                          ),
                                        TextButton(
                                          onPressed: () async {
                                            final confirmed = await showDialog<bool>(
                                              context: context,
                                              builder: (context) => AlertDialog(
                                                title: const Text('Discard local change?'),
                                                content: const Text('This removes the queued edit and keeps the server version.'),
                                                actions: [
                                                  TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
                                                  FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Discard')),
                                                ],
                                              ),
                                            );
                                            if (confirmed == true) await controller.discard(item.id);
                                          },
                                          child: const Text('Use server / discard'),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          )),
                  ],
                ),
              ),
      ),
    );
  }
}
