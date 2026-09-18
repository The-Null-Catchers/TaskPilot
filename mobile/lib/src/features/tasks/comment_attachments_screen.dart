import 'package:flutter/material.dart';

import 'attachments_section.dart';

class CommentAttachmentsScreen extends StatelessWidget {
  const CommentAttachmentsScreen({super.key, required this.commentId});
  final String commentId;

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Comment attachments')),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [
              AttachmentsSection(
                entityType: 'comment',
                entityId: commentId,
                title: 'Comment attachments',
                emptyText: 'No files attached to this comment yet.',
              ),
            ],
          ),
        ),
      );
}
