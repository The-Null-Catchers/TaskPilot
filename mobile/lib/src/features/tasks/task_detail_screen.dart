import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/offline_queue.dart';
import 'comment_card.dart';
import 'task_detail_controller.dart';
import 'task_models.dart';

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

  Future<void> _addLabel(BuildContext context, WidgetRef ref, TaskDetailState state) async {
    final selectedIds = state.taskLabels.map((item) => item.id).toSet();
    final available = state.workspaceLabels.where((item) => !selectedIds.contains(item.id)).toList();
    if (available.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No additional workspace labels are available.')));
      return;
    }
    final selected = await showModalBottomSheet<LabelItem>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const Padding(padding: EdgeInsets.fromLTRB(20, 4, 20, 10), child: Text('Add label', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
            ...available.map((label) => ListTile(leading: const Icon(Icons.label_outline_rounded), title: Text(label.name), onTap: () => Navigator.pop(context, label))),
          ],
        ),
      ),
    );
    if (selected == null) return;
    try {
      await ref.read(taskDetailProvider(taskId).notifier).addLabel(selected.id);
    } catch (_) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not add label.')));
    }
  }

  Future<void> _addDependency(BuildContext context, WidgetRef ref, TaskDetailState state) async {
    final task = state.task;
    if (task == null) return;
    final existing = state.blockedBy.map((item) => item.blockerTaskId).toSet();
    final available = state.projectTasks.where((item) => item.id != task.id && item.status != 'done' && !existing.contains(item.id)).toList();
    if (available.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No eligible blocker tasks are available.')));
      return;
    }
    final selected = await showModalBottomSheet<TaskItem>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const Padding(padding: EdgeInsets.fromLTRB(20, 4, 20, 10), child: Text('Add blocking task', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
            ...available.map((item) => ListTile(title: Text(item.title), subtitle: Text(item.identifier), onTap: () => Navigator.pop(context, item))),
          ],
        ),
      ),
    );
    if (selected == null) return;
    try {
      await ref.read(taskDetailProvider(taskId).notifier).addDependency(selected.id);
    } catch (_) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not add dependency. It may create a circular relationship.')));
    }
  }

  Future<void> _assignChecklistItem(
    BuildContext context,
    WidgetRef ref,
    TaskDetailState state,
    String checklistId,
    ChecklistItemModel item,
  ) async {
    final selected = await showModalBottomSheet<String?>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 4, 20, 10),
              child: Text('Assign checklist item', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            ),
            ListTile(
              leading: const Icon(Icons.person_off_outlined),
              title: const Text('Unassigned'),
              onTap: () => Navigator.pop(context, ''),
            ),
            ...state.members.map(
              (member) => ListTile(
                leading: CircleAvatar(child: Text(member.name.substring(0, 1).toUpperCase())),
                title: Text(member.name),
                subtitle: Text(member.email),
                trailing: item.assigneeId == member.id ? const Icon(Icons.check_rounded) : null,
                onTap: () => Navigator.pop(context, member.id),
              ),
            ),
          ],
        ),
      ),
    );
    if (selected == null) return;
    try {
      await ref.read(taskDetailProvider(taskId).notifier).assignChecklistItem(
            checklistId,
            item,
            selected.isEmpty ? null : selected,
          );
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not update checklist assignee.')),
        );
      }
    }
  }

  Future<void> _moveChecklistItem(
    BuildContext context,
    WidgetRef ref,
    String checklistId,
    ChecklistItemModel item,
    ChecklistItemModel other,
  ) async {
    try {
      await ref.read(taskDetailProvider(taskId).notifier).moveChecklistItem(checklistId, item, other);
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not reorder checklist item. Refresh and try again.')),
        );
      }
    }
  }

  Future<void> _convertSubtask(
    BuildContext context,
    WidgetRef ref,
    SubtaskItem item,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Convert to task?'),
        content: Text('“${item.title}” will become a standalone task in this project.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Convert')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(taskDetailProvider(taskId).notifier).convertSubtask(item.id);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Subtask converted to a standalone task.')),
        );
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not convert subtask.')),
        );
      }
    }
  }

  TaskItem? _projectTask(TaskDetailState state, String id) {
    for (final item in state.projectTasks) {
      if (item.id == id) return item;
    }
    return null;
  }

  Future<void> _composeComment(BuildContext context, WidgetRef ref, TaskDetailState state) async {
    final controller = TextEditingController();
    var mentionId = '';
    final body = await showDialog<String>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Comment'),
          content: SizedBox(
            width: 480,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (state.members.isNotEmpty)
                  DropdownButtonFormField<String>(
                    initialValue: mentionId,
                    decoration: const InputDecoration(labelText: 'Mention teammate'),
                    items: [
                      const DropdownMenuItem(value: '', child: Text('No mention')),
                      ...state.members.map((member) => DropdownMenuItem(value: member.id, child: Text(member.name))),
                    ],
                    onChanged: (value) {
                      final id = value ?? '';
                      setDialogState(() => mentionId = id);
                      if (id.isNotEmpty) {
                        final marker = '@[$id]';
                        if (!controller.text.contains(marker)) {
                          final prefix = controller.text.isEmpty || controller.text.endsWith(' ') ? '' : ' ';
                          controller.text = '${controller.text}$prefix$marker ';
                          controller.selection = TextSelection.collapsed(offset: controller.text.length);
                        }
                      }
                    },
                  ),
                if (state.members.isNotEmpty) const SizedBox(height: 12),
                TextField(
                  controller: controller,
                  autofocus: true,
                  maxLength: 20000,
                  minLines: 3,
                  maxLines: 8,
                  decoration: const InputDecoration(labelText: 'Write a comment…'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Comment')),
          ],
        ),
      ),
    );
    if (body == null || body.isEmpty) return;
    final outcome = await ref.read(taskDetailProvider(taskId).notifier).addComment(body);
    if (context.mounted) _showOutcome(context, outcome);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(taskDetailProvider(taskId));
    final task = state.task;
    return Scaffold(
      appBar: AppBar(
        title: Text(task?.identifier ?? 'Task'),
        actions: [
          if (task != null)
            IconButton(
              onPressed: state.offline ? null : () async {
                try {
                  await ref.read(taskDetailProvider(taskId).notifier).toggleWatch();
                } catch (_) {
                  if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not update watcher state.')));
                }
              },
              icon: Icon(state.watching ? Icons.notifications_active_rounded : Icons.notifications_none_rounded),
              tooltip: state.watching ? 'Unwatch task' : 'Watch task',
            ),
          if (task != null) IconButton(onPressed: () => _editTask(context, ref, state), icon: const Icon(Icons.edit_rounded), tooltip: 'Edit task'),
          IconButton(onPressed: () async { await ref.read(offlineQueueProvider.notifier).sync(); await ref.read(taskDetailProvider(taskId).notifier).load(); }, icon: const Icon(Icons.refresh_rounded)),
        ],
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
                      if (state.blocked)
                        Container(
                          margin: const EdgeInsets.only(bottom: 16),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(color: Theme.of(context).colorScheme.errorContainer, borderRadius: BorderRadius.circular(14)),
                          child: const Row(children: [Icon(Icons.block_rounded, size: 18), SizedBox(width: 8), Expanded(child: Text('Blocked by another task. Resolve the dependency before completing this work.'))]),
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
                      _SectionHeader(title: 'Labels', icon: Icons.label_outline_rounded, action: state.offline ? null : IconButton(onPressed: () => _addLabel(context, ref, state), icon: const Icon(Icons.add_rounded), tooltip: 'Add label')),
                      const SizedBox(height: 8),
                      if (state.taskLabels.isEmpty)
                        const Text('No labels.')
                      else
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: state.taskLabels.map((label) => InputChip(
                            label: Text(label.name),
                            onDeleted: state.offline ? null : () async {
                              try {
                                await ref.read(taskDetailProvider(taskId).notifier).removeLabel(label.id);
                              } catch (_) {
                                if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not remove label.')));
                              }
                            },
                          )).toList(),
                        ),
                      const SizedBox(height: 28),
                      _SectionHeader(title: 'Dependencies', icon: Icons.link_rounded, action: state.offline ? null : IconButton(onPressed: () => _addDependency(context, ref, state), icon: const Icon(Icons.add_link_rounded), tooltip: 'Add blocker')),
                      const SizedBox(height: 8),
                      Row(children: [
                        Icon(state.watching ? Icons.notifications_active_outlined : Icons.notifications_none_rounded, size: 18),
                        const SizedBox(width: 8),
                        Text(state.watching
                            ? 'Following · ${state.watcherCount} watcher${state.watcherCount == 1 ? '' : 's'}'
                            : 'Not following · ${state.watcherCount} watcher${state.watcherCount == 1 ? '' : 's'}'),
                      ]),
                      const SizedBox(height: 8),
                      if (state.blockedBy.isEmpty)
                        const Text('No blocking dependencies.')
                      else
                        ...state.blockedBy.map((dependency) {
                          final blocker = _projectTask(state, dependency.blockerTaskId);
                          return ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.link_rounded),
                            title: Text(blocker?.title ?? 'Blocking task'),
                            subtitle: Text(blocker?.identifier ?? dependency.blockerTaskId),
                            trailing: state.offline ? null : IconButton(
                              onPressed: () async {
                                try {
                                  await ref.read(taskDetailProvider(taskId).notifier).removeDependency(dependency.id);
                                } catch (_) {
                                  if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not remove dependency.')));
                                }
                              },
                              icon: const Icon(Icons.link_off_rounded),
                              tooltip: 'Remove dependency',
                            ),
                          );
                        }),
                      const SizedBox(height: 28),
                      _SectionHeader(title: 'Subtasks', icon: Icons.account_tree_outlined, action: IconButton(onPressed: () async { final title = await _askText(context, title: 'Add subtask', label: 'Title'); if (title != null && title.isNotEmpty) { final outcome = await ref.read(taskDetailProvider(taskId).notifier).addSubtask(title); if (context.mounted) _showOutcome(context, outcome); } }, icon: const Icon(Icons.add_rounded))),
                      const SizedBox(height: 6),
                      if (state.subtasks.isEmpty)
                        const Text('No cached subtasks. New subtasks can still be queued offline.')
                      else
                        ...state.subtasks.map(
                          (item) => ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: Checkbox(
                              value: item.status == 'done',
                              onChanged: (_) async {
                                final outcome = await ref.read(taskDetailProvider(taskId).notifier).toggleSubtask(item);
                                if (context.mounted) _showOutcome(context, outcome);
                              },
                            ),
                            title: Text(
                              item.title,
                              style: TextStyle(decoration: item.status == 'done' ? TextDecoration.lineThrough : null),
                            ),
                            trailing: state.offline
                                ? null
                                : IconButton(
                                    onPressed: () => _convertSubtask(context, ref, item),
                                    icon: const Icon(Icons.open_in_new_rounded),
                                    tooltip: 'Convert to task',
                                  ),
                          ),
                        ),
                      const SizedBox(height: 24),
                      _SectionHeader(title: 'Checklists', icon: Icons.checklist_rounded, action: IconButton(onPressed: () async { final title = await _askText(context, title: 'New checklist', label: 'Checklist title', maxLength: 160); if (title != null && title.isNotEmpty) { final outcome = await ref.read(taskDetailProvider(taskId).notifier).addChecklist(title); if (context.mounted) _showOutcome(context, outcome); } }, icon: const Icon(Icons.add_rounded))),
                      ...state.checklists.map((checklist) {
                        final ordered = [...checklist.items]..sort((a, b) => a.position.compareTo(b.position));
                        return Card(
                          elevation: 0,
                          margin: const EdgeInsets.only(top: 10),
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(child: Text(checklist.title, style: const TextStyle(fontWeight: FontWeight.w700))),
                                    IconButton(
                                      onPressed: () async {
                                        final title = await _askText(context, title: 'Checklist item', label: 'Item');
                                        if (title != null && title.isNotEmpty) {
                                          final outcome = await ref.read(taskDetailProvider(taskId).notifier).addChecklistItem(checklist.id, title);
                                          if (context.mounted) _showOutcome(context, outcome);
                                        }
                                      },
                                      icon: const Icon(Icons.add_rounded),
                                      tooltip: 'Add item',
                                    ),
                                  ],
                                ),
                                ...ordered.asMap().entries.map((entry) {
                                  final index = entry.key;
                                  final item = entry.value;
                                  PersonItem? assignee;
                                  for (final member in state.members) {
                                    if (member.id == item.assigneeId) {
                                      assignee = member;
                                      break;
                                    }
                                  }
                                  return ListTile(
                                    dense: true,
                                    contentPadding: EdgeInsets.zero,
                                    leading: Checkbox(
                                      value: item.completed,
                                      onChanged: (_) async {
                                        final outcome = await ref.read(taskDetailProvider(taskId).notifier).toggleChecklistItem(checklist.id, item);
                                        if (context.mounted) _showOutcome(context, outcome);
                                      },
                                    ),
                                    title: Text(
                                      item.title,
                                      style: TextStyle(decoration: item.completed ? TextDecoration.lineThrough : null),
                                    ),
                                    subtitle: assignee == null ? null : Text('Assigned to ${assignee.name}'),
                                    trailing: state.offline
                                        ? null
                                        : PopupMenuButton<String>(
                                            tooltip: 'Checklist item actions',
                                            onSelected: (value) {
                                              if (value == 'assign') {
                                                _assignChecklistItem(context, ref, state, checklist.id, item);
                                              } else if (value == 'up' && index > 0) {
                                                _moveChecklistItem(context, ref, checklist.id, item, ordered[index - 1]);
                                              } else if (value == 'down' && index < ordered.length - 1) {
                                                _moveChecklistItem(context, ref, checklist.id, item, ordered[index + 1]);
                                              }
                                            },
                                            itemBuilder: (context) => [
                                              const PopupMenuItem(value: 'assign', child: Text('Assign member')),
                                              PopupMenuItem(value: 'up', enabled: index > 0, child: const Text('Move up')),
                                              PopupMenuItem(value: 'down', enabled: index < ordered.length - 1, child: const Text('Move down')),
                                            ],
                                          ),
                                  );
                                }),
                              ],
                            ),
                          ),
                        );
                      }),
                      const SizedBox(height: 28),
                      Card(
                        elevation: 0,
                        child: ListTile(
                          leading: const Icon(Icons.attach_file_rounded),
                          title: const Text('Attachments', style: TextStyle(fontWeight: FontWeight.w700)),
                          subtitle: const Text('Upload, download, and remove task files'),
                          trailing: const Icon(Icons.chevron_right_rounded),
                          onTap: () => context.push('/tasks/$taskId/attachments'),
                        ),
                      ),
                      const SizedBox(height: 28),
                      _SectionHeader(
                        title: 'Discussion',
                        icon: Icons.chat_bubble_outline_rounded,
                        action: IconButton(
                          onPressed: () => _composeComment(context, ref, state),
                          icon: const Icon(Icons.add_comment_rounded),
                          tooltip: 'Add comment',
                        ),
                      ),
                      const SizedBox(height: 8),
                      if (state.comments.isEmpty)
                        const Text('No cached comments. New comments can still be queued offline.')
                      else
                        ...state.comments.map((comment) => CommentCard(
                              taskId: taskId,
                              comment: comment,
                              members: state.members,
                              currentUserId: state.currentUserId,
                              onEdit: (body) async {
                                try {
                                  await ref.read(taskDetailProvider(taskId).notifier).editComment(comment.id, body);
                                } catch (_) {
                                  if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not edit comment.')));
                                }
                              },
                              onDelete: () async {
                                try {
                                  await ref.read(taskDetailProvider(taskId).notifier).deleteComment(comment.id);
                                } catch (_) {
                                  if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not delete comment.')));
                                }
                              },
                            )),
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
