import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';
import 'task_detail_controller.dart';
import 'task_models.dart';

const _allowedReactions = ['👍', '👎', '❤️', '🎉', '😄', '🚀', '👀'];

class CommentCard extends ConsumerStatefulWidget {
  const CommentCard({
    super.key,
    required this.taskId,
    required this.comment,
    required this.members,
    required this.currentUserId,
    required this.onEdit,
    required this.onDelete,
  });

  final String taskId;
  final CommentItem comment;
  final List<PersonItem> members;
  final String? currentUserId;
  final Future<void> Function(String body) onEdit;
  final Future<void> Function() onDelete;

  @override
  ConsumerState<CommentCard> createState() => _CommentCardState();
}

class _CommentCardState extends ConsumerState<CommentCard> {
  bool _loadingReactions = true;
  List<Map<String, dynamic>> _reactions = const [];

  @override
  void initState() {
    super.initState();
    _loadReactions();
  }

  Future<void> _loadReactions() async {
    try {
      final response = await ref.read(apiProvider).dio.get(
        '/api/v1/tasks/${widget.taskId}/comments/${widget.comment.id}/reactions',
      );
      if (!mounted) return;
      setState(() {
        _reactions = (response.data as List)
            .map((item) => (item as Map).cast<String, dynamic>())
            .toList();
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _reactions = const []);
    } finally {
      if (mounted) setState(() => _loadingReactions = false);
    }
  }

  Future<void> _toggleReaction(String emoji) async {
    final currentUserId = widget.currentUserId;
    if (currentUserId == null) return;
    final mine = _reactions.where(
      (item) => item['user_id'] == currentUserId && item['emoji'] == emoji,
    );
    try {
      if (mine.isNotEmpty) {
        await ref.read(apiProvider).dio.delete(
          '/api/v1/tasks/${widget.taskId}/comments/${widget.comment.id}/reactions/${mine.first['id']}',
        );
      } else {
        await ref.read(apiProvider).dio.post(
          '/api/v1/tasks/${widget.taskId}/comments/${widget.comment.id}/reactions',
          data: {'emoji': emoji},
        );
      }
      await _loadReactions();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not update reaction.')),
        );
      }
    }
  }

  Future<void> _edit() async {
    final controller = TextEditingController(text: widget.comment.body);
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit comment'),
        content: TextField(
          controller: controller,
          autofocus: true,
          minLines: 3,
          maxLines: 8,
          maxLength: 20000,
          decoration: const InputDecoration(labelText: 'Comment'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (result == null || result.isEmpty || result == widget.comment.body) return;
    await widget.onEdit(result);
  }

  Future<void> _delete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete comment?'),
        content: const Text('This permanently removes the comment and its attachments.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed == true) await widget.onDelete();
  }

  List<InlineSpan> _bodySpans(BuildContext context) {
    final byId = {for (final member in widget.members) member.id: member.name};
    final pattern = RegExp(r'@\[([0-9a-fA-F-]{36})\]');
    final spans = <InlineSpan>[];
    var cursor = 0;
    for (final match in pattern.allMatches(widget.comment.body)) {
      if (match.start > cursor) {
        spans.add(TextSpan(text: widget.comment.body.substring(cursor, match.start)));
      }
      final id = match.group(1)!;
      spans.add(
        TextSpan(
          text: '@${byId[id] ?? 'member'}',
          style: TextStyle(
            color: Theme.of(context).colorScheme.primary,
            fontWeight: FontWeight.w700,
          ),
        ),
      );
      cursor = match.end;
    }
    if (cursor < widget.comment.body.length) {
      spans.add(TextSpan(text: widget.comment.body.substring(cursor)));
    }
    return spans;
  }

  @override
  Widget build(BuildContext context) {
    final mine = widget.currentUserId == widget.comment.authorId;
    final author = widget.members.where((item) => item.id == widget.comment.authorId);
    final authorName = author.isEmpty ? widget.comment.authorId.substring(0, 8) : author.first.name;
    final counts = <String, int>{};
    for (final reaction in _reactions) {
      final emoji = reaction['emoji'] as String? ?? '';
      if (emoji.isNotEmpty) counts[emoji] = (counts[emoji] ?? 0) + 1;
    }

    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(radius: 14, child: Text(authorName.substring(0, 1).toUpperCase())),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(authorName, style: const TextStyle(fontWeight: FontWeight.w700)),
                ),
                IconButton(
                  onPressed: () => context.push('/comments/${widget.comment.id}/attachments'),
                  icon: const Icon(Icons.attach_file_rounded, size: 18),
                  tooltip: 'Comment attachments',
                ),
                if (mine)
                  PopupMenuButton<String>(
                    onSelected: (value) {
                      if (value == 'edit') _edit();
                      if (value == 'delete') _delete();
                    },
                    itemBuilder: (context) => const [
                      PopupMenuItem(value: 'edit', child: Text('Edit')),
                      PopupMenuItem(value: 'delete', child: Text('Delete')),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: 10),
            RichText(
              text: TextSpan(
                style: DefaultTextStyle.of(context).style.copyWith(height: 1.45),
                children: _bodySpans(context),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '${DateTime.parse(widget.comment.createdAt).toLocal().toString().split('.').first}${widget.comment.editedAt != null ? ' · edited' : ''}',
              style: Theme.of(context).textTheme.labelSmall,
            ),
            const SizedBox(height: 10),
            if (_loadingReactions)
              const LinearProgressIndicator(minHeight: 1)
            else
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: _allowedReactions.map((emoji) {
                  final selected = _reactions.any(
                    (item) => item['user_id'] == widget.currentUserId && item['emoji'] == emoji,
                  );
                  final count = counts[emoji] ?? 0;
                  return ActionChip(
                    label: Text(count > 0 ? '$emoji $count' : emoji),
                    onPressed: widget.currentUserId == null ? null : () => _toggleReaction(emoji),
                    side: selected
                        ? BorderSide(color: Theme.of(context).colorScheme.primary)
                        : null,
                  );
                }).toList(),
              ),
          ],
        ),
      ),
    );
  }
}
