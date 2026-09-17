import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/offline_queue.dart';
import '../auth/auth_controller.dart';
import 'home_controller.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  Future<void> _createWorkspace(BuildContext context, WidgetRef ref) async {
    final controller = TextEditingController();
    final create = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Create workspace'),
        content: TextField(controller: controller, autofocus: true, maxLength: 120, decoration: const InputDecoration(labelText: 'Workspace name')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Create')),
        ],
      ),
    );
    if (create != true || controller.text.trim().length < 2) return;
    try {
      await ref.read(homeProvider.notifier).createWorkspace(controller.text.trim());
    } catch (_) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not create workspace.')));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(homeProvider);
    final sync = ref.watch(offlineQueueProvider);
    final syncCount = sync.items.length;
    return Scaffold(
      appBar: AppBar(
        title: const Text('TaskPilot'),
        actions: [
          IconButton(onPressed: () => context.push('/search'), icon: const Icon(Icons.search_rounded), tooltip: 'Search'),
          Stack(
            clipBehavior: Clip.none,
            children: [
              IconButton(onPressed: () => context.push('/sync'), icon: Icon(sync.conflictCount > 0 ? Icons.sync_problem_rounded : Icons.cloud_sync_outlined), tooltip: 'Sync Center'),
              if (syncCount > 0)
                Positioned(
                  right: 3,
                  top: 3,
                  child: Container(
                    constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    decoration: BoxDecoration(
                      color: sync.conflictCount > 0 ? Theme.of(context).colorScheme.error : Theme.of(context).colorScheme.primary,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    alignment: Alignment.center,
                    child: Text(syncCount > 99 ? '99+' : '$syncCount', style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w700)),
                  ),
                ),
            ],
          ),
          IconButton(onPressed: () => context.push('/notifications'), icon: const Icon(Icons.notifications_none_rounded), tooltip: 'Notifications'),
          IconButton(onPressed: () async { await ref.read(offlineQueueProvider.notifier).sync(); await ref.read(homeProvider.notifier).load(); }, icon: const Icon(Icons.refresh_rounded), tooltip: 'Refresh & sync'),
          IconButton(onPressed: () => ref.read(authProvider.notifier).logout(), icon: const Icon(Icons.logout_rounded), tooltip: 'Sign out'),
        ],
      ),
      floatingActionButton: state.offline ? null : FloatingActionButton(onPressed: () => _createWorkspace(context, ref), tooltip: 'Create workspace', child: const Icon(Icons.add_rounded)),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async { await ref.read(offlineQueueProvider.notifier).sync(); await ref.read(homeProvider.notifier).load(); },
          child: ListView(padding: const EdgeInsets.fromLTRB(20, 12, 20, 96), children: [
            if (sync.items.isNotEmpty)
              InkWell(
                onTap: () => context.push('/sync'),
                borderRadius: BorderRadius.circular(14),
                child: Container(
                  margin: const EdgeInsets.only(bottom: 12),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: (sync.conflictCount > 0 ? Theme.of(context).colorScheme.errorContainer : Theme.of(context).colorScheme.primaryContainer), borderRadius: BorderRadius.circular(14)),
                  child: Row(children: [Icon(sync.conflictCount > 0 ? Icons.warning_amber_rounded : Icons.sync_rounded, size: 18), const SizedBox(width: 8), Expanded(child: Text(sync.conflictCount > 0 ? '${sync.conflictCount} offline conflict${sync.conflictCount == 1 ? '' : 's'} need review.' : '${sync.pendingCount} offline change${sync.pendingCount == 1 ? '' : 's'} waiting to sync.')), const Icon(Icons.chevron_right_rounded)]),
                ),
              ),
            if (state.offline) Container(margin: const EdgeInsets.only(bottom: 16), padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Theme.of(context).colorScheme.secondaryContainer, borderRadius: BorderRadius.circular(14)), child: const Row(children: [Icon(Icons.cloud_off_rounded, size: 18), SizedBox(width: 8), Expanded(child: Text('Offline — showing cached workspace data.'))])),
            Text('Good to see you', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text('Your projects, tasks, and team activity in one place.', style: Theme.of(context).textTheme.bodyLarge),
            const SizedBox(height: 24),
            Row(children: [
              Expanded(child: _QuickAction(icon: Icons.task_alt_rounded, label: 'My Tasks', onTap: () => context.push('/my-tasks'))),
              const SizedBox(width: 10),
              Expanded(child: _QuickAction(icon: Icons.calendar_month_rounded, label: 'Calendar', onTap: () => context.push('/calendar'))),
            ]),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(child: _QuickAction(icon: Icons.search_rounded, label: 'Search', onTap: () => context.push('/search'))),
              const SizedBox(width: 10),
              Expanded(child: _QuickAction(icon: Icons.notifications_active_outlined, label: 'Notifications', onTap: () => context.push('/notifications'))),
            ]),
            const SizedBox(height: 28),
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text('Workspaces', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)), if (!state.offline) IconButton(onPressed: () => _createWorkspace(context, ref), icon: const Icon(Icons.add_rounded), tooltip: 'Create workspace')]),
            if (state.loading)
              const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator()))
            else if (state.error != null)
              Padding(padding: const EdgeInsets.symmetric(vertical: 32), child: Text(state.error!, textAlign: TextAlign.center))
            else if (state.workspaces.isEmpty)
              Card(elevation: 0, child: Padding(padding: const EdgeInsets.all(28), child: Column(children: [Icon(Icons.space_dashboard_outlined, size: 36, color: Theme.of(context).colorScheme.primary), const SizedBox(height: 12), const Text('Create your first workspace', style: TextStyle(fontWeight: FontWeight.w700)), const SizedBox(height: 4), const Text('Separate personal, team, school, or client work cleanly.', textAlign: TextAlign.center)])))
            else
              ...state.workspaces.map((workspace) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Card(
                      elevation: 0,
                      clipBehavior: Clip.antiAlias,
                      child: ListTile(
                        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                        leading: CircleAvatar(child: Text(workspace.name.substring(0, 1).toUpperCase())),
                        title: Text(workspace.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                        subtitle: const Text('Projects, boards and team tasks'),
                        trailing: const Icon(Icons.chevron_right_rounded),
                        onTap: () => context.push('/workspaces/${workspace.id}/projects'),
                      ),
                    ),
                  )),
          ]),
        ),
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  const _QuickAction({required this.icon, required this.label, required this.onTap});
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Card(elevation: 0, clipBehavior: Clip.antiAlias, child: InkWell(onTap: onTap, child: Padding(padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 18), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(icon, color: Theme.of(context).colorScheme.primary), const SizedBox(height: 12), Text(label, style: const TextStyle(fontWeight: FontWeight.w700))]))));
}
