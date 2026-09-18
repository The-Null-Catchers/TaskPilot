import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';
import 'task_models.dart';

class ArchivedTasksScreen extends ConsumerStatefulWidget {
  const ArchivedTasksScreen({super.key});

  @override
  ConsumerState<ArchivedTasksScreen> createState() => _ArchivedTasksScreenState();
}

class _ArchivedTasksScreenState extends ConsumerState<ArchivedTasksScreen> {
  bool _loading = true;
  String? _error;
  String _workspaceId = '';
  List<Map<String, dynamic>> _workspaces = const [];
  List<TaskItem> _tasks = const [];
  String? _restoringId;

  @override
  void initState() {
    super.initState();
    _loadWorkspaces();
  }

  String _message(Object error, String fallback) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['detail'] is String) return data['detail'] as String;
      if (data is Map && data['error'] is Map && data['error']['message'] is String) {
        return data['error']['message'] as String;
      }
    }
    return fallback;
  }

  Future<void> _loadWorkspaces() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await ref.read(apiProvider).dio.get('/api/v1/workspaces');
      final workspaces = (response.data as List)
          .map((item) => (item as Map).cast<String, dynamic>())
          .toList();
      final nextWorkspace = _workspaceId.isNotEmpty &&
              workspaces.any((item) => item['id'] == _workspaceId)
          ? _workspaceId
          : (workspaces.isEmpty ? '' : workspaces.first['id'] as String);
      if (!mounted) return;
      setState(() {
        _workspaces = workspaces;
        _workspaceId = nextWorkspace;
      });
      if (nextWorkspace.isNotEmpty) {
        await _loadTasks(quiet: true);
      } else {
        setState(() => _tasks = const []);
      }
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = _message(error, 'Could not load workspaces.'));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadTasks({bool quiet = false}) async {
    if (_workspaceId.isEmpty) return;
    if (!quiet) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final response = await ref.read(apiProvider).dio.get(
        '/api/v1/workspaces/$_workspaceId/archived-tasks',
      );
      if (!mounted) return;
      setState(() {
        _tasks = (response.data as List)
            .map((item) => TaskItem.fromJson((item as Map).cast<String, dynamic>()))
            .toList();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = _message(error, 'Could not load archived tasks.'));
    } finally {
      if (mounted && !quiet) setState(() => _loading = false);
    }
  }

  Future<void> _restore(TaskItem task) async {
    setState(() {
      _restoringId = task.id;
      _error = null;
    });
    try {
      await ref.read(apiProvider).dio.post('/api/v1/tasks/${task.id}/restore');
      if (!mounted) return;
      setState(() => _tasks = _tasks.where((item) => item.id != task.id).toList());
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${task.identifier} restored.'),
          action: SnackBarAction(
            label: 'Open',
            onPressed: () => context.push('/tasks/${task.id}'),
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = _message(error, 'Could not restore task.'));
    } finally {
      if (mounted) setState(() => _restoringId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Archived tasks'),
        actions: [
          IconButton(
            onPressed: _loading ? null : _loadTasks,
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadTasks,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
            children: [
              if (_workspaces.isNotEmpty)
                DropdownButtonFormField<String>(
                  initialValue: _workspaceId,
                  decoration: const InputDecoration(labelText: 'Workspace'),
                  items: _workspaces
                      .map(
                        (workspace) => DropdownMenuItem(
                          value: workspace['id'] as String,
                          child: Text(workspace['name'] as String),
                        ),
                      )
                      .toList(),
                  onChanged: _loading
                      ? null
                      : (value) async {
                          if (value == null || value == _workspaceId) return;
                          setState(() => _workspaceId = value);
                          await _loadTasks();
                        },
                ),
              if (_workspaces.isNotEmpty) const SizedBox(height: 18),
              if (_error != null)
                Container(
                  margin: const EdgeInsets.only(bottom: 14),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Text(_error!),
                ),
              if (_loading)
                const Padding(
                  padding: EdgeInsets.all(36),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_workspaces.isEmpty)
                const Card(
                  elevation: 0,
                  child: Padding(
                    padding: EdgeInsets.all(28),
                    child: Text(
                      'No active workspaces are available.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              else if (_tasks.isEmpty)
                Card(
                  elevation: 0,
                  child: Padding(
                    padding: const EdgeInsets.all(28),
                    child: Column(
                      children: [
                        Icon(
                          Icons.archive_outlined,
                          size: 38,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        const SizedBox(height: 12),
                        const Text(
                          'No archived tasks',
                          style: TextStyle(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Tasks archived in this workspace will appear here.',
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                )
              else
                ..._tasks.map(
                  (task) => Card(
                    elevation: 0,
                    margin: const EdgeInsets.only(bottom: 10),
                    child: ListTile(
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 10,
                      ),
                      leading: const Icon(Icons.inventory_2_outlined),
                      title: Text(
                        task.title,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                      subtitle: Text(
                        '${task.identifier} · ${task.priority} · ${task.status.replaceAll('_', ' ')}',
                      ),
                      trailing: _restoringId == task.id
                          ? const SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : IconButton(
                              onPressed: () => _restore(task),
                              icon: const Icon(Icons.restore_rounded),
                              tooltip: 'Restore task',
                            ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
