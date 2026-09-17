import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';

class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});

  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen> {
  late DateTime _month;
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _items = const [];

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _month = DateTime(now.year, now.month);
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final start = DateTime.utc(_month.year, _month.month);
    final end = DateTime.utc(_month.year, _month.month + 1);
    try {
      final response = await ref.read(apiProvider).dio.get('/api/v1/calendar', queryParameters: {
        'start': start.toIso8601String(),
        'end': end.toIso8601String(),
      });
      if (!mounted) return;
      setState(() {
        _items = (response.data as List).map((item) => (item as Map).cast<String, dynamic>()).toList();
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Could not load this month. Check your connection and try again.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _shift(int delta) {
    setState(() => _month = DateTime(_month.year, _month.month + delta));
    _load();
  }

  String _monthName(DateTime value) {
    const names = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    return '${names[value.month - 1]} ${value.year}';
  }

  @override
  Widget build(BuildContext context) {
    final grouped = <DateTime, List<Map<String, dynamic>>>{};
    for (final item in _items) {
      final date = DateTime.parse(item['starts_at'] as String).toLocal();
      final key = DateTime(date.year, date.month, date.day);
      grouped.putIfAbsent(key, () => []).add(item);
    }
    final days = grouped.keys.toList()..sort();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Calendar'),
        actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh_rounded), tooltip: 'Refresh')],
      ),
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
            child: Row(children: [
              IconButton(onPressed: () => _shift(-1), icon: const Icon(Icons.chevron_left_rounded)),
              Expanded(child: Text(_monthName(_month), textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800))),
              IconButton(onPressed: () => _shift(1), icon: const Icon(Icons.chevron_right_rounded)),
            ]),
          ),
          if (_loading) const LinearProgressIndicator(minHeight: 2),
          Expanded(
            child: _error != null
                ? Center(child: Padding(padding: const EdgeInsets.all(28), child: Text(_error!, textAlign: TextAlign.center)))
                : days.isEmpty && !_loading
                    ? const Center(child: Padding(padding: EdgeInsets.all(28), child: Text('No deadlines or milestones this month.')))
                    : RefreshIndicator(
                        onRefresh: _load,
                        child: ListView.builder(
                          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
                          itemCount: days.length,
                          itemBuilder: (context, index) {
                            final day = days[index];
                            final items = grouped[day]!;
                            return Padding(
                              padding: const EdgeInsets.only(bottom: 18),
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Padding(
                                  padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
                                  child: Text('${day.day}/${day.month}/${day.year}', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800)),
                                ),
                                ...items.map((item) => Card(
                                      elevation: 0,
                                      margin: const EdgeInsets.only(bottom: 8),
                                      clipBehavior: Clip.antiAlias,
                                      child: ListTile(
                                        leading: Icon(_icon(item['kind'] as String?)),
                                        title: Text(item['title'] as String),
                                        subtitle: Text(_subtitle(item)),
                                        trailing: item['task_id'] != null || item['project_id'] != null ? const Icon(Icons.chevron_right_rounded) : null,
                                        onTap: () {
                                          final taskId = item['task_id'] as String?;
                                          final projectId = item['project_id'] as String?;
                                          if (taskId != null) context.push('/tasks/$taskId');
                                          else if (projectId != null) context.push('/projects/$projectId');
                                        },
                                      ),
                                    )),
                              ]),
                            );
                          },
                        ),
                      ),
          ),
        ]),
      ),
    );
  }

  IconData _icon(String? kind) => switch (kind) {
        'task' => Icons.task_alt_rounded,
        'milestone' => Icons.flag_circle_outlined,
        'project' => Icons.event_available_rounded,
        _ => Icons.event_note_rounded,
      };

  String _subtitle(Map<String, dynamic> item) {
    final kind = item['kind'] as String? ?? 'item';
    final identifier = item['identifier'] as String?;
    final status = item['status'] as String?;
    return [kind, if (identifier != null) identifier, if (status != null) status].join(' · ');
  }
}
