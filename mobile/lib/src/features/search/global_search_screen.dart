import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';

class GlobalSearchScreen extends ConsumerStatefulWidget {
  const GlobalSearchScreen({super.key});

  @override
  ConsumerState<GlobalSearchScreen> createState() => _GlobalSearchScreenState();
}

class _GlobalSearchScreenState extends ConsumerState<GlobalSearchScreen> {
  final _controller = TextEditingController();
  Timer? _debounce;
  bool _loading = false;
  String? _error;
  Map<String, dynamic>? _results;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _changed(String value) {
    _debounce?.cancel();
    final query = value.trim();
    if (query.length < 2) {
      setState(() {
        _results = null;
        _error = null;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 320), () => _search(query));
  }

  Future<void> _search(String query) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await ref.read(apiProvider).dio.get('/api/v1/search', queryParameters: {'q': query});
      if (!mounted) return;
      setState(() => _results = (response.data as Map).cast<String, dynamic>());
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Search is unavailable. Check your connection and try again.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<Map<String, dynamic>> _items(String key) =>
      ((_results?[key] as List?) ?? const []).map((item) => (item as Map).cast<String, dynamic>()).toList();

  @override
  Widget build(BuildContext context) {
    final tasks = _items('tasks');
    final projects = _items('projects');
    final comments = _items('comments');
    final workspaces = _items('workspaces');
    final labels = _items('labels');
    final empty = _results != null && [tasks, projects, comments, workspaces, labels].every((items) => items.isEmpty);

    return Scaffold(
      appBar: AppBar(title: const Text('Search')),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: TextField(
                controller: _controller,
                autofocus: true,
                onChanged: _changed,
                textInputAction: TextInputAction.search,
                decoration: InputDecoration(
                  prefixIcon: const Icon(Icons.search_rounded),
                  hintText: 'Search tasks, projects, comments…',
                  suffixIcon: _controller.text.isEmpty
                      ? null
                      : IconButton(
                          onPressed: () {
                            _controller.clear();
                            _changed('');
                            setState(() {});
                          },
                          icon: const Icon(Icons.close_rounded),
                        ),
                ),
              ),
            ),
            if (_loading) const LinearProgressIndicator(minHeight: 2),
            Expanded(
              child: _controller.text.trim().length < 2
                  ? const _Message(icon: Icons.manage_search_rounded, title: 'Search TaskPilot', body: 'Type at least two characters to search everything you can access.')
                  : _error != null
                      ? _Message(icon: Icons.wifi_off_rounded, title: 'Could not search', body: _error!)
                      : empty
                          ? const _Message(icon: Icons.search_off_rounded, title: 'No matches', body: 'Try a broader task title, project key, label, or comment phrase.')
                          : ListView(
                              padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
                              children: [
                                if (tasks.isNotEmpty) _section(context, 'Tasks', tasks.map((item) => ListTile(
                                      leading: const Icon(Icons.task_alt_rounded),
                                      title: Text('${item['identifier']} · ${item['title']}'),
                                      subtitle: Text('${item['status']} · ${item['priority']}'),
                                      trailing: const Icon(Icons.chevron_right_rounded),
                                      onTap: () => context.push('/tasks/${item['id']}'),
                                    ))),
                                if (projects.isNotEmpty) _section(context, 'Projects', projects.map((item) => ListTile(
                                      leading: const Icon(Icons.folder_outlined),
                                      title: Text(item['name'] as String),
                                      subtitle: Text(item['key'] as String),
                                      trailing: const Icon(Icons.chevron_right_rounded),
                                      onTap: () => context.push('/projects/${item['id']}'),
                                    ))),
                                if (comments.isNotEmpty) _section(context, 'Comments', comments.map((item) => ListTile(
                                      leading: const Icon(Icons.chat_bubble_outline_rounded),
                                      title: Text(item['task_identifier'] as String),
                                      subtitle: Text(item['body'] as String, maxLines: 2, overflow: TextOverflow.ellipsis),
                                      trailing: const Icon(Icons.chevron_right_rounded),
                                      onTap: () => context.push('/tasks/${item['task_id']}'),
                                    ))),
                                if (workspaces.isNotEmpty) _section(context, 'Workspaces', workspaces.map((item) => ListTile(
                                      leading: const Icon(Icons.space_dashboard_outlined),
                                      title: Text(item['name'] as String),
                                      trailing: const Icon(Icons.chevron_right_rounded),
                                      onTap: () => context.push('/workspaces/${item['id']}/projects'),
                                    ))),
                                if (labels.isNotEmpty) _section(context, 'Labels', labels.map((item) => ListTile(
                                      leading: const Icon(Icons.label_outline_rounded),
                                      title: Text(item['name'] as String),
                                      subtitle: const Text('Workspace label'),
                                    ))),
                              ],
                            ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _section(BuildContext context, String title, Iterable<Widget> children) => Padding(
        padding: const EdgeInsets.only(top: 12, bottom: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
              child: Text(title, style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800)),
            ),
            Card(elevation: 0, clipBehavior: Clip.antiAlias, child: Column(children: children.toList())),
          ],
        ),
      );
}

class _Message extends StatelessWidget {
  const _Message({required this.icon, required this.title, required this.body});
  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 46, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 14),
            Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text(body, textAlign: TextAlign.center),
          ]),
        ),
      );
}
