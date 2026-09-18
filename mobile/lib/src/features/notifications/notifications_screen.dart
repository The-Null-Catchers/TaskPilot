import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'notifications_controller.dart';

class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(notificationsProvider);
    final unread = state.items.where((item) => item.readAt == null).length;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          IconButton(onPressed: () => context.push('/settings/notifications'), icon: const Icon(Icons.settings_outlined), tooltip: 'Notification settings'),
          if (unread > 0) TextButton.icon(onPressed: () => ref.read(notificationsProvider.notifier).markAllRead(), icon: const Icon(Icons.done_all_rounded), label: const Text('Read all')),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => ref.read(notificationsProvider.notifier).load(),
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 32), children: [
            Text('$unread unread', style: Theme.of(context).textTheme.labelLarge?.copyWith(color: Theme.of(context).colorScheme.primary)),
            const SizedBox(height: 12),
            if (state.loading)
              const Padding(padding: EdgeInsets.all(36), child: Center(child: CircularProgressIndicator()))
            else if (state.error != null)
              Padding(padding: const EdgeInsets.all(28), child: Text(state.error!, textAlign: TextAlign.center))
            else if (state.items.isEmpty)
              Card(elevation: 0, child: Padding(padding: const EdgeInsets.all(28), child: Column(children: [Icon(Icons.notifications_none_rounded, size: 36, color: Theme.of(context).colorScheme.primary), const SizedBox(height: 12), const Text('You’re all caught up', style: TextStyle(fontWeight: FontWeight.w700)), const SizedBox(height: 4), const Text('Assignments, mentions, deadlines and task activity will appear here.', textAlign: TextAlign.center)])))
            else
              ...state.items.map((item) => Card(
                    elevation: 0,
                    margin: const EdgeInsets.only(bottom: 10),
                    color: item.readAt == null ? Theme.of(context).colorScheme.primaryContainer.withValues(alpha: .28) : null,
                    child: ListTile(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      leading: Icon(item.readAt == null ? Icons.notifications_active_rounded : Icons.notifications_none_rounded, color: item.readAt == null ? Theme.of(context).colorScheme.primary : null),
                      title: Text(item.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                      subtitle: Padding(padding: const EdgeInsets.only(top: 5), child: Text(item.body.isEmpty ? item.kind : item.body)),
                      trailing: item.readAt == null ? const Icon(Icons.circle, size: 9) : null,
                      onTap: () async {
                        if (item.readAt == null) await ref.read(notificationsProvider.notifier).markRead(item.id);
                        if (context.mounted && item.entityType == 'task' && item.entityId != null) context.push('/tasks/${item.entityId}');
                      },
                    ),
                  )),
          ]),
        ),
      ),
    );
  }
}
