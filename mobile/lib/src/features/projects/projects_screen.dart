import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';
import 'projects_controller.dart';

class ProjectsScreen extends ConsumerWidget {
  const ProjectsScreen({super.key, required this.workspaceId});
  final String workspaceId;

  Future<void> _createProject(BuildContext context, WidgetRef ref) async {
    final nameController = TextEditingController();
    final keyController = TextEditingController();
    final created = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Create project'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Name'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: keyController,
              textCapitalization: TextCapitalization.characters,
              decoration: const InputDecoration(labelText: 'Key', hintText: 'DEV'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Create')),
        ],
      ),
    );
    final name = nameController.text.trim();
    final key = keyController.text.trim().toUpperCase();
    nameController.dispose();
    keyController.dispose();
    if (created != true || name.length < 2 || key.length < 2) return;
    try {
      await ref.read(apiProvider).dio.post(
        '/api/v1/projects',
        data: {'workspace_id': workspaceId, 'name': name, 'key': key},
      );
      await ref.read(projectsProvider(workspaceId).notifier).load();
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not create project. Check your connection and permissions.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(projectsProvider(workspaceId));
    return Scaffold(
      appBar: AppBar(
        title: const Text('Projects'),
        actions: [
          IconButton(
            onPressed: () => ref.read(projectsProvider(workspaceId).notifier).load(),
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
          ),
        ],
      ),
      floatingActionButton: state.offline
          ? null
          : FloatingActionButton.extended(
              onPressed: () => _createProject(context, ref),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Project'),
            ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => ref.read(projectsProvider(workspaceId).notifier).load(),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 96),
            children: [
              if (state.offline) const _OfflineBanner(label: 'Offline — showing cached projects.'),
              Text(
                'Workspace projects',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              Text(
                'Open a project to view its live board and task activity.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),
              if (state.loading)
                const Padding(
                  padding: EdgeInsets.all(36),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (state.error != null)
                Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text(state.error!, textAlign: TextAlign.center),
                )
              else if (state.projects.isEmpty)
                Card(
                  elevation: 0,
                  child: Padding(
                    padding: const EdgeInsets.all(28),
                    child: Column(
                      children: [
                        Icon(
                          Icons.folder_open_rounded,
                          size: 36,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        const SizedBox(height: 12),
                        const Text('No projects yet', style: TextStyle(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 4),
                        const Text('Create one to get a five-column board.', textAlign: TextAlign.center),
                      ],
                    ),
                  ),
                )
              else
                ...state.projects.map((project) {
                  final initials = project.key.substring(0, project.key.length >= 2 ? 2 : project.key.length);
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Card(
                      elevation: 0,
                      clipBehavior: Clip.antiAlias,
                      child: ListTile(
                        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                        leading: CircleAvatar(child: Text(initials)),
                        title: Text(project.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                        subtitle: Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            '${project.key} · ${project.status}${project.dueDate == null ? '' : ' · due ${project.dueDate}'}',
                          ),
                        ),
                        trailing: const Icon(Icons.chevron_right_rounded),
                        onTap: () => context.push('/projects/${project.id}'),
                      ),
                    ),
                  );
                }),
            ],
          ),
        ),
      ),
    );
  }
}

class _OfflineBanner extends StatelessWidget {
  const _OfflineBanner({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.secondaryContainer,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            const Icon(Icons.cloud_off_rounded, size: 18),
            const SizedBox(width: 8),
            Expanded(child: Text(label)),
          ],
        ),
      );
}
