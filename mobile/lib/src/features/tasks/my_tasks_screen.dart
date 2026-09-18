import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'my_tasks_controller.dart';

class MyTasksScreen extends ConsumerStatefulWidget {
  const MyTasksScreen({super.key});
  @override
  ConsumerState<MyTasksScreen> createState() => _MyTasksScreenState();
}

class _MyTasksScreenState extends ConsumerState<MyTasksScreen> {
  String scope = 'assigned';

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(myTasksProvider(scope));
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Tasks'),
        actions: [
          IconButton(
            onPressed: () => context.push('/my-tasks/archived'),
            icon: const Icon(Icons.archive_outlined),
            tooltip: 'Archived tasks',
          ),
          IconButton(
            onPressed: () => ref.read(myTasksProvider(scope).notifier).load(),
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () => ref.read(myTasksProvider(scope).notifier).load(),
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 32), children: [
            if (state.offline) Container(margin: const EdgeInsets.only(bottom: 14), padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Theme.of(context).colorScheme.secondaryContainer, borderRadius: BorderRadius.circular(14)), child: const Row(children: [Icon(Icons.cloud_off_rounded, size: 18), SizedBox(width: 8), Expanded(child: Text('Offline — showing cached tasks.'))])),
            SingleChildScrollView(scrollDirection: Axis.horizontal, child: SegmentedButton<String>(segments: const [ButtonSegment(value: 'assigned', label: Text('Assigned')), ButtonSegment(value: 'created', label: Text('Created')), ButtonSegment(value: 'watching', label: Text('Watching')), ButtonSegment(value: 'all', label: Text('All'))], selected: {scope}, onSelectionChanged: (values) => setState(() => scope = values.first))),
            const SizedBox(height: 20),
            if (state.loading)
              const Padding(padding: EdgeInsets.all(36), child: Center(child: CircularProgressIndicator()))
            else if (state.error != null)
              Padding(padding: const EdgeInsets.all(24), child: Text(state.error!, textAlign: TextAlign.center))
            else if (state.tasks.isEmpty)
              Card(elevation: 0, child: Padding(padding: const EdgeInsets.all(28), child: Column(children: [Icon(Icons.task_alt_rounded, size: 36, color: Theme.of(context).colorScheme.primary), const SizedBox(height: 12), const Text('Nothing in this view', style: TextStyle(fontWeight: FontWeight.w700)), const SizedBox(height: 4), const Text('Try another scope or assign a task to yourself.')])) )
            else
              ...state.tasks.map((task) => Card(
                    elevation: 0,
                    margin: const EdgeInsets.only(bottom: 10),
                    clipBehavior: Clip.antiAlias,
                    child: ListTile(
                      onTap: () => context.push('/tasks/${task.id}'),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      title: Text(task.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                      subtitle: Padding(padding: const EdgeInsets.only(top: 5), child: Text('${task.identifier} · ${task.priority}${task.dueDate == null ? '' : ' · due ${task.dueDate!.split('T').first}'}')),
                      trailing: const Icon(Icons.chevron_right_rounded),
                    ),
                  )),
          ]),
        ),
      ),
    );
  }
}
