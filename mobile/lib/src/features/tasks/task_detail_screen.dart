import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/offline_queue.dart';
import 'task_detail_controller.dart';

class TaskDetailScreen extends ConsumerWidget {
  const TaskDetailScreen({super.key, required this.taskId});
  final String taskId;

  Future<String?> _askText(BuildContext context, {required String title, required String label, int maxLength = 240}) async {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: TextField(controller: controller, autofocus: true, maxLength: maxLength, minLines: 1, maxLines: 5, decoration: InputDecoration(labelText: label)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Add')),
        ],
      ),
    );
  }

  void _showOutcome(BuildContext context, MutationOutcome outcome) {
    if (outcome == MutationOutcome.synced) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(outcome == MutationOutcome.queued ? 'Saved locally. TaskPilot will sync this change when you reconnect.' : 'This edit conflicts with a newer server version. Review it in Sync Center.'),
      action: SnackBarAction(label: 'Sync Center', onPressed: () => context.push('/sync')),
    ));
  }

  Future<void> _editTask(BuildContext context, WidgetRef ref, TaskDetailState state) async {
    final task = state.task;
    if (task == null) return;
    final title = TextEditingController(text: task.title);
    final description = TextEditingController(text: task.description);
    var priority = task.priority;
    var status = task.status;
    final save = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(builder: (context, setDialogState) => AlertDialog(
        title: Text(task.identifier),
        content: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: title, maxLength: 240, decoration: const InputDecoration(labelText: 'Title')),
          const SizedBox(height: 12),
          TextField(controller: description, minLines: 3, maxLines: 8, decoration: const InputDecoration(labelText: 'Description')),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(initialValue: priority, decoration: const InputDecoration(labelText: 'Priority'), items: const ['urgent', 'high', 'medium', 'low', 'none'].map((value) => DropdownMenuItem(value: value, child: Text(value))).toList(), onChanged: (value) { if (value != null) setDialogState(() => priority = value); }),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(initialValue: status, decoration: const InputDecoration(labelText: 'Status'), items: const ['open', 'in_progress', 'review', 'done'].map((value) => DropdownMenuItem(value: value, child: Text(value.replaceAll('_', ' ')))).toList(), onChanged: (value) { if (value != null) setDialogState(() => status = value); }),
        ])),
        actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Save'))],
      )),
    );
    if (save != true || title.text.trim().isEmpty) return;
    try {
      final outcome = await ref.read(taskDetailProvider(taskId).notifier).updateTask(title: title.text.trim(), description: description.text.trim(), priority: priority, status: status, dueDate: task.dueDate);
      if (context.mounted) _showOutcome(context, outcome);
    } catch (_) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Task could not be saved. Check your permissions and try again.')));
    }
  }

  Future<void> _assignMember(BuildContext context, WidgetRef ref, TaskDetailState state) async {
    final assigned = state.assignees.map((person) => person.id).toSet();
    final available = state.members.where((person) => !assigned.contains(person.id)).toList();
    if (available.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No cached member is available to assign.')));
      return;
    }
    final selected = await showModalBottomSheet<PersonItem>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(child: ListView(shrinkWrap: true, children: [const Padding(padding: EdgeInsets.fromLTRB(20, 4, 20, 10), child: Text('Assign member', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700))), ...available.map((person) => ListTile(leading: CircleAvatar(child: Text(person.name.substring(0, 1).toUpperCase())), title: Text(person.name), subtitle: Text(person.email), onTap: () => Navigator.pop(context, person)))])),
    );
    if (selected != null) {
      final outcome = await ref.read(taskDetailProvider(taskId).notifier).assign(selected.id);
      if (context.mounted) _showOutcome(context, outcome);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(taskDetailProvider(taskId));
    final task = state.task;
    return Scaffold(
      appBar: AppBar(
        title: Text(task?.identifier ?? 'Task'),
        actions: [if (task != null) IconButton(onPressed: () => _editTask(context, ref, state), icon: const Icon(Icons.edit_rounded), tooltip: 'Edit task'), IconButton(onPressed: () async { await ref.read(offlineQueueProvider.notifier).sync(); await ref.read(taskDetailProvider(taskId).notifier).load(); }, icon: const Icon(Icons.refresh_rounded))],
      ),
      body: SafeArea(
        child: state.loading && task == null
            ? const Center(child: CircularProgressIndicator())
            : task == null
                ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(state.error ?? 'Task unavailable.', textAlign: TextAlign.center)))
                : RefreshIndicator(
                    onRefresh: () async { await ref.read(offlineQueueProvider.notifier).sync(); await ref.read(taskDetailProvider(taskId).notifier).load(); },
                    child: ListView(padding: const EdgeInsets.fromLTRB(20, 12, 20, 40), children: [
                      if (state.offline || state.pendingSync || state.conflict)
                        InkWell(
                          onTap: () => context.push('/sync'),
                          borderRadius: BorderRadius.circular(14),
                          child: Container(
                            margin: const EdgeInsets.only(bottom: 16),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(color: state.conflict ? Theme.of(context).colorScheme.errorContainer : Theme.of(context).colorScheme.secondaryContainer, borderRadius: BorderRadius.circular(14)),
                            child: Row(children: [Icon(state.conflict ? Icons.sync_problem_rounded : state.pendingSync ? Icons.cloud_upload_outlined : Icons.cloud_off_rounded, size: 18), const SizedBox(width: 8), Expanded(child: Text(state.conflict ? 'A local edit conflicts with a newer server version. Tap to review.' : state.pendingSync ? 'Local changes are waiting to sync.' : 'Offline — edits to this existing task will be queued locally.')), const Icon(Icons.chevron_right_rounded)]),
                          ),
                        ),
                      Text(task.title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 10),
                      Wrap(spacing: 8, runSpacing: 8, children: [_Chip(label: task.priority, icon: Icons.flag_outlined), _Chip(label: task.status.replaceAll('_', ' '), icon: Icons.track_changes_rounded), if (task.dueDate != null) _Chip(label: 'Due ${task.dueDate!.split('T').first}', icon: Icons.calendar_today_rounded)]),
                      if (task.description.isNotEmpty) ...[const SizedBox(height: 22), Text(task.description, style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5))],
                      const SizedBox(height: 28),
                      _SectionHeader(title: 'Assignees', icon: Icons.group_outlined, action: state.members.isEmpty ? null : IconButton(onPressed: () => _assignMember(context, ref, state), icon: const Icon(Icons.person_add_alt_1_rounded))),
                      const SizedBox(height: 8),
                      if (state.assignees.isEmpty) const Text('No cached assignees.') else Wrap(spacing: 8, runSpacing: 8, children: state.assignees.map((person) => InputChip(avatar: CircleAvatar(child: Text(person.name.substring(0, 1).toUpperCase())), label: Text(person.name), onDeleted: () async { final outcome = await ref.read(taskDetailProvider(taskId).notifier).unassign(person.id); if (context.mounted) _showOutcome(context, outcome); })).toList()),
                      const SizedBox(height: 28),
                      _SectionHeader(title: 'Subtasks', icon: Icons.account_tree_outlined, action: IconButton(onPressed: () async { final title = await _askText(context, title: 'Add subtask', label: 'Title'); if (title != null && title.isNotEmpty) { final outcome = await ref.read(taskDetailProvider(taskId).notifier).addSubtask(title); if (context.mounted) _showOutcome(context, outcome); } }, icon: const Icon(Icons.add_rounded))),
                      const SizedBox(height: 6),
                      if (state.subtasks.isEmpty) const Text('No cached subtasks. New subtasks can still be queued offline.') else ...state.subtasks.map((item) => CheckboxListTile(contentPadding: EdgeInsets.zero, value: item.status == 'done', title: Text(item.title, style: TextStyle(decoration: item.status == 'done' ? TextDecoration.lineThrough : null)), onChanged: (_) async { final outcome = await ref.read(taskDetailProvider(taskId).notifier).toggleSubtask(item); if (context.mounted) _showOutcome(context, outcome); })),
                      const SizedBox(height: 24),
                      _SectionHeader(title: 'Checklists', icon: Icons.checklist_rounded, action: IconButton(onPressed: () async { final title = await _askText(context, title: 'New checklist', label: 'Checklist title', maxLength: 160); if (title != null && title.isNotEmpty) { final outcome = await ref.read(taskDetailProvider(taskId).notifier).addChecklist(title); if (context.mounted) _showOutcome(context, outcome); } }, icon: const Icon(Icons.add_rounded))),
                      ...state.checklists.map((checklist) => Card(elevation: 0, margin: const EdgeInsets.only(top: 10), child: Padding(padding: const EdgeInsets.all(12), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Row(children: [Expanded(child: Text(checklist.title, style: const TextStyle(fontWeight: FontWeight.w700))), IconButton(onPressed: () async { final title = await _askText(context, title: 'Checklist item', label: 'Item'); if (title != null && title.isNotEmpty) { final outcome = await ref.read(taskDetailProvider(taskId).notifier).addChecklistItem(checklist.id, title); if (context.mounted) _showOutcome(context, outcome); } }, icon: const Icon(Icons.add_rounded), tooltip: 'Add item')]), ...checklist.items.map((item) => CheckboxListTile(dense: true, contentPadding: EdgeInsets.zero, value: item.completed, title: Text(item.title, style: TextStyle(decoration: item.completed ? TextDecoration.lineThrough : null)), onChanged: (_) async { final outcome = await ref.read(taskDetailProvider(taskId).notifier).toggleChecklistItem(checklist.id, item); if (context.mounted) _showOutcome(context, outcome); }))])))),
                      const SizedBox(height: 28),
                      _SectionHeader(title: 'Discussion', icon: Icons.chat_bubble_outline_rounded, action: IconButton(onPressed: () async { final body = await _askText(context, title: 'Comment', label: 'Write a comment…', maxLength: 20000); if (body != null && body.isNotEmpty) { final outcome = await ref.read(taskDetailProvider(taskId).notifier).addComment(body); if (context.mounted) _showOutcome(context, outcome); } }, icon: const Icon(Icons.add_comment_rounded))),
                      const SizedBox(height: 8),
                      if (state.comments.isEmpty) const Text('No cached comments. New comments can still be queued offline.') else ...state.comments.map((comment) => Card(elevation: 0, margin: const EdgeInsets.only(bottom: 10), child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(comment.body), const SizedBox(height: 8), Text(DateTime.parse(comment.createdAt).toLocal().toString().split('.').first, style: Theme.of(context).textTheme.labelSmall)])))),
                    ]),
                  ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.icon, this.action});
  final String title;
  final IconData icon;
  final Widget? action;
  @override
  Widget build(BuildContext context) => Row(children: [Icon(icon, size: 20), const SizedBox(width: 8), Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))), if (action != null) action!]);
}

class _Chip extends StatelessWidget {
  const _Chip({required this.label, required this.icon});
  final String label;
  final IconData icon;
  @override
  Widget build(BuildContext context) => Chip(avatar: Icon(icon, size: 15), label: Text(label));
}
