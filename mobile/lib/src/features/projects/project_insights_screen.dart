import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';

class ProjectInsightsScreen extends ConsumerStatefulWidget {
  const ProjectInsightsScreen({super.key, required this.projectId});
  final String projectId;

  @override
  ConsumerState<ProjectInsightsScreen> createState() => _ProjectInsightsScreenState();
}

class _ProjectInsightsScreenState extends ConsumerState<ProjectInsightsScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _overview;
  Map<String, dynamic>? _timeline;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _load();
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        ref.read(apiProvider).dio.get('/api/v1/projects/${widget.projectId}/overview'),
        ref.read(apiProvider).dio.get('/api/v1/projects/${widget.projectId}/timeline'),
      ]);
      if (!mounted) return;
      setState(() {
        _overview = (results[0].data as Map).cast<String, dynamic>();
        _timeline = (results[1].data as Map).cast<String, dynamic>();
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Could not load project insights. Check your connection and permissions.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<Map<String, dynamic>> _list(Map<String, dynamic>? source, String key) =>
      ((source?[key] as List?) ?? const []).map((item) => (item as Map).cast<String, dynamic>()).toList();

  @override
  Widget build(BuildContext context) {
    final project = (_overview?['project'] as Map?)?.cast<String, dynamic>();
    return Scaffold(
      appBar: AppBar(
        title: Text(project?['name'] as String? ?? 'Project insights'),
        actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh_rounded), tooltip: 'Refresh')],
        bottom: TabBar(controller: _tabs, tabs: const [Tab(text: 'Overview'), Tab(text: 'Timeline')]),
      ),
      body: SafeArea(
        child: _loading && _overview == null
            ? const Center(child: CircularProgressIndicator())
            : _error != null && _overview == null
                ? Center(child: Padding(padding: const EdgeInsets.all(28), child: Text(_error!, textAlign: TextAlign.center)))
                : TabBarView(
                    controller: _tabs,
                    children: [
                      RefreshIndicator(onRefresh: _load, child: _overviewView(context)),
                      RefreshIndicator(onRefresh: _load, child: _timelineView(context)),
                    ],
                  ),
      ),
    );
  }

  Widget _overviewView(BuildContext context) {
    final counts = ((_overview?['counts'] as Map?) ?? const {}).cast<String, dynamic>();
    final progress = (_overview?['progress'] as num?)?.toDouble() ?? 0;
    final members = _list(_overview, 'members');
    final upcoming = _list(_overview, 'upcoming_tasks');
    final overdue = _list(_overview, 'overdue_tasks');
    final completed = _list(_overview, 'recently_completed');
    final milestones = _list(_overview, 'milestones');
    final activity = _list(_overview, 'activity');

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        Card(
          elevation: 0,
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [Expanded(child: Text('Progress', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800))), Text('${progress.toStringAsFixed(0)}%')]),
              const SizedBox(height: 12),
              LinearProgressIndicator(value: (progress / 100).clamp(0, 1), minHeight: 8, borderRadius: BorderRadius.circular(20)),
              const SizedBox(height: 18),
              Wrap(spacing: 10, runSpacing: 10, children: [
                _Metric(label: 'Total', value: '${counts['total'] ?? 0}'),
                _Metric(label: 'Open', value: '${counts['open'] ?? 0}'),
                _Metric(label: 'Done', value: '${counts['completed'] ?? 0}'),
                _Metric(label: 'Overdue', value: '${counts['overdue'] ?? 0}'),
              ]),
            ]),
          ),
        ),
        _section(context, 'Upcoming', upcoming.map(_taskTile)),
        _section(context, 'Overdue', overdue.map(_taskTile)),
        _section(context, 'Recently completed', completed.map(_taskTile)),
        _section(context, 'Milestones', milestones.map((item) => ListTile(
              leading: Icon(item['status'] == 'completed' ? Icons.flag_circle_rounded : Icons.flag_outlined),
              title: Text(item['title'] as String),
              subtitle: Text('Due ${_date(item['due_date'])} · ${item['status']}'),
            ))),
        _section(context, 'Members', members.map((item) => ListTile(
              leading: CircleAvatar(child: Text(((item['name'] as String?) ?? '?').substring(0, 1).toUpperCase())),
              title: Text(item['name'] as String),
              subtitle: Text('${item['role']} · ${item['email']}'),
            ))),
        _section(context, 'Recent activity', activity.map((item) => ListTile(
              leading: const Icon(Icons.bolt_outlined),
              title: Text(item['summary'] as String),
              subtitle: Text('${item['action']} · ${_date(item['created_at'])}'),
            ))),
      ],
    );
  }

  Widget _timelineView(BuildContext context) {
    final tasks = _list(_timeline, 'tasks');
    final milestones = _list(_timeline, 'milestones');
    if (tasks.isEmpty && milestones.isEmpty) {
      return const ListView(children: [SizedBox(height: 120), Center(child: Text('No timeline data yet.'))]);
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        if (milestones.isNotEmpty) _section(context, 'Milestones', milestones.map((item) => ListTile(
              leading: const Icon(Icons.flag_circle_outlined),
              title: Text(item['title'] as String),
              subtitle: Text('${_date(item['due_at'])} · ${item['status']}'),
            ))),
        _section(context, 'Tasks', tasks.map((item) {
          final blockers = ((item['blocked_by'] as List?) ?? const []).length;
          return Card(
            elevation: 0,
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: Icon(blockers > 0 ? Icons.block_rounded : Icons.timeline_rounded),
              title: Text('${item['identifier']} · ${item['title']}'),
              subtitle: Text('${_date(item['start_at'])} → ${item['due_at'] == null ? 'No due date' : _date(item['due_at'])}\n${item['status']} · ${item['priority']}${blockers > 0 ? ' · blocked by $blockers' : ''}'),
              isThreeLine: true,
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () => context.push('/tasks/${item['id']}'),
            ),
          );
        })),
      ],
    );
  }

  Widget _taskTile(Map<String, dynamic> item) => ListTile(
        leading: const Icon(Icons.task_alt_rounded),
        title: Text('${item['identifier']} · ${item['title']}'),
        subtitle: Text(item['due_date'] != null ? 'Due ${_date(item['due_date'])}' : item['completed_at'] != null ? 'Completed ${_date(item['completed_at'])}' : ''),
        trailing: const Icon(Icons.chevron_right_rounded),
        onTap: () => context.push('/tasks/${item['id']}'),
      );

  Widget _section(BuildContext context, String title, Iterable<Widget> children) {
    final items = children.toList();
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 22),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(padding: const EdgeInsets.fromLTRB(4, 0, 4, 8), child: Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800))),
        Card(elevation: 0, clipBehavior: Clip.antiAlias, child: Column(children: items)),
      ]),
    );
  }

  String _date(dynamic value) {
    if (value == null) return '—';
    final parsed = DateTime.tryParse(value.toString());
    if (parsed == null) return value.toString();
    final local = parsed.toLocal();
    return '${local.day}/${local.month}/${local.year}';
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Container(
        width: 88,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: Theme.of(context).colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(14)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(value, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
          Text(label, style: Theme.of(context).textTheme.labelMedium),
        ]),
      );
}
