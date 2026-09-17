import 'package:flutter/material.dart';

import 'attachments_section.dart';

class TaskAttachmentsScreen extends StatelessWidget {
  const TaskAttachmentsScreen({super.key, required this.taskId});
  final String taskId;

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Attachments')),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [AttachmentsSection(taskId: taskId)],
          ),
        ),
      );
}
