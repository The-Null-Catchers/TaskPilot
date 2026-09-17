import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../tasks/task_models.dart';
import 'board_controller.dart';

class BoardScreen extends ConsumerWidget {
  const BoardScreen({super.key, required this.projectId});
  final String projectId;

  Future<void> _createTask(BuildContext context, WidgetRef ref, BoardColumn column) async {
    final controller = TextEditingController();
    final create = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('New task · ${column.name}'),
        content: TextField(controller: controller, autofocus: true, maxLength: 240, decoration: const InputDecoration(labelText: 'Task title')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Create')),
        ],
      ),
    );
    if (create != true || controller.text.trim().isEmpty) return;
    try {
      final task = await ref.read(boardProvider(projectId).notifier).createTask(column.id, controller.text.trim());
      if (context.mounted) context.push('/tasks/${task.id}');
    } catch (_) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not create task.')));
    }
  }

  Future<void> _moveTask(BuildContext context, WidgetRef ref, TaskItem task, BoardColumn destination) async {
    try {
      await ref.read(boardProvider(projectId).notifier).moveTask(task, destination);
    } catch (_) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Task changed elsewhere or could not be moved. Refresh and try again.')));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(boardProvider(projectId));
    final board = state.board;
    return Scaffold(
      appBar: AppBar(
        title: Text(board?.project.name ?? 'Board'),
        actions: [
          IconButton(onPressed: () => context.push('/projects/$projectId/insights'), icon: const Icon(Icons.insights_rounded), tooltip: 'Overview & timeline'),
          IconButton(onPressed: () => ref.read(boardProvider(projectId).notifier).load(), icon: const Icon(Icons.refresh_rounded), tooltip: 'Refresh'),
        ],
      ),
      body: SafeArea(
        child: Column(children: [
          if (state.offline) Container(width: double.infinity, margin: const EdgeInsets.fromLTRB(16, 8, 16, 0), padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Theme.of(context).colorScheme.secondaryContainer, borderRadius: BorderRadius.circular(14)), child: const Row(children: [Icon(Icons.cloud_off_rounded, size: 18), SizedBox(width: 8), Expanded(child: Text('Offline — showing the last cached board.'))])),
          if (state.loading && board == null)
            const Expanded(child: Center(child: CircularProgressIndicator()))
          else if (state.error != null && board == null)
            Expanded(child: Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(state.error!, textAlign: TextAlign.center))))
          else if (board != null)
            Expanded(
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.all(16),
                itemCount: board.columns.length,
                separatorBuilder: (_, __) => const SizedBox(width: 14),
                itemBuilder: (context, index) {
                  final column = board.columns[index];
                  final tasks = board.tasks.where((task) => task.columnId == column.id).toList()..sort((a, b) => a.position.compareTo(b.position));
                  return SizedBox(
                    width: MediaQuery.sizeOf(context).width.clamp(280, 360).toDouble(),
                    child: DecoratedBox(
                      decoration: BoxDecoration(color: Theme.of(context).colorScheme.surfaceContainerLow, borderRadius: BorderRadius.circular(20), border: Border.all(color: Theme.of(context).dividerColor.withValues(alpha: .5))),
                      child: Column(children: [
                        Padding(padding: const EdgeInsets.fromLTRB(16, 14, 10, 10), child: Row(children: [Expanded(child: Text(column.name, style: const TextStyle(fontWeight: FontWeight.w700))), Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), decoration: BoxDecoration(color: Theme.of(context).colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(20)), child: Text('${tasks.length}', style: Theme.of(context).textTheme.labelSmall)), IconButton(onPressed: state.offline ? null : () => _createTask(context, ref, column), icon: const Icon(Icons.add_rounded), tooltip: 'Add task')])),
                        Expanded(
                          child: tasks.isEmpty
                              ? const Center(child: Padding(padding: EdgeInsets.all(20), child: Text('No tasks', style: TextStyle(color: Colors.grey))))
                              : ListView.builder(
                                  padding: const EdgeInsets.fromLTRB(10, 0, 10, 12),
                                  itemCount: tasks.length,
                                  itemBuilder: (context, taskIndex) {
                                    final task = tasks[taskIndex];
                                    return Card(
                                      elevation: 0,
                                      margin: const EdgeInsets.only(bottom: 10),
                                      clipBehavior: Clip.antiAlias,
                                      child: InkWell(
                                        onTap: () => context.push('/tasks/${task.id}'),
                                        child: Padding(
                                          padding: const EdgeInsets.all(14),
                                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                              Expanded(child: Text(task.title, style: const TextStyle(fontWeight: FontWeight.w600))),
                                              IconButton(onPressed: () => context.push('/tasks/${task.id}/attachments'), icon: const Icon(Icons.attach_file_rounded, size: 19), tooltip: 'Attachments', visualDensity: VisualDensity.compact),
                                              if (!state.offline) PopupMenuButton<BoardColumn>(tooltip: 'Move task', icon: const Icon(Icons.more_horiz_rounded, size: 20), onSelected: (destination) => _moveTask(context, ref, task, destination), itemBuilder: (_) => board.columns.where((item) => item.id != task.columnId).map((item) => PopupMenuItem(value: item, child: Text('Move to ${item.name}'))).toList()),
                                            ]),
                                            const SizedBox(height: 10),
                                            Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [Text(task.identifier, style: Theme.of(context).textTheme.labelSmall?.copyWith(color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.w700)), _PriorityChip(priority: task.priority), if (task.dueDate != null) Row(mainAxisSize: MainAxisSize.min, children: [const Icon(Icons.schedule_rounded, size: 13), const SizedBox(width: 3), Text(task.dueDate!.split('T').first, style: Theme.of(context).textTheme.labelSmall)])]),
                                          ]),
                                        ),
                                      ),
                                    );
                                  },
                                ),
                        ),
                      ]),
                    ),
                  );
                },
              ),
            ),
        ]),
      ),
    );
  }
}

class _PriorityChip extends StatelessWidget {
  const _PriorityChip({required this.priority});
  final String priority;
  @override
  Widget build(BuildContext context) {
    if (priority == 'none') return const SizedBox.shrink();
    return Container(padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3), decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, borderRadius: BorderRadius.circular(20)), child: Text(priority, style: Theme.of(context).textTheme.labelSmall));
  }
}
