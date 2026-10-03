import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';

enum _CalendarView { month, week }

class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});

  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen> {
  late DateTime _cursor;
  _CalendarView _view = _CalendarView.month;
  int _weekStart = DateTime.monday;
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _items = const [];

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _cursor = DateTime(now.year, now.month, now.day);
    _loadPreferencesAndCalendar();
  }

  Future<void> _loadPreferencesAndCalendar() async {
    try {
      final response = await ref.read(apiProvider).dio.get('/api/v1/settings/user');
      final value = response.data is Map ? (response.data as Map)['week_start'] : null;
      if (value is int && value >= 0 && value <= 6) {
        // API uses 0=Sunday ... 6=Saturday. Dart uses 1=Monday ... 7=Sunday.
        _weekStart = value == 0 ? DateTime.sunday : value;
      }
    } catch (_) {
      // Calendar still works with Monday as the safe local default.
    }
    await _load();
  }

  DateTime _startOfWeek(DateTime value) {
    final normalized = DateTime(value.year, value.month, value.day);
    final delta = (normalized.weekday - _weekStart + 7) % 7;
    return normalized.subtract(Duration(days: delta));
  }

  (DateTime, DateTime) _range() {
    if (_view == _CalendarView.month) {
      return (
        DateTime(_cursor.year, _cursor.month),
        DateTime(_cursor.year, _cursor.month + 1),
      );
    }
    final start = _startOfWeek(_cursor);
    return (start, start.add(const Duration(days: 7)));
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    final (start, end) = _range();
    try {
      final response = await ref.read(apiProvider).dio.get(
        '/api/v1/calendar',
        queryParameters: {
          'start': DateTime.utc(start.year, start.month, start.day).toIso8601String(),
          'end': DateTime.utc(end.year, end.month, end.day).toIso8601String(),
        },
      );
      if (!mounted) return;
      setState(() {
        _items = (response.data as List)
            .map((item) => (item as Map).cast<String, dynamic>())
            .toList();
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = _view == _CalendarView.month
            ? 'Could not load this month. Check your connection and try again.'
            : 'Could not load this week. Check your connection and try again.';
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _shift(int delta) {
    setState(() {
      if (_view == _CalendarView.month) {
        _cursor = DateTime(_cursor.year, _cursor.month + delta, 1);
      } else {
        _cursor = _cursor.add(Duration(days: 7 * delta));
      }
    });
    _load();
  }

  void _today() {
    final now = DateTime.now();
    setState(() => _cursor = DateTime(now.year, now.month, now.day));
    _load();
  }

  void _setView(_CalendarView value) {
    if (_view == value) return;
    setState(() => _view = value);
    _load();
  }

  String _monthName(DateTime value) {
    const names = [
      'January','February','March','April','May','June',
      'July','August','September','October','November','December',
    ];
    return '${names[value.month - 1]} ${value.year}';
  }

  String _rangeTitle() {
    if (_view == _CalendarView.month) return _monthName(_cursor);
    final start = _startOfWeek(_cursor);
    final end = start.add(const Duration(days: 6));
    if (start.month == end.month) {
      return '${_monthName(start).split(' ').first} ${start.day}–${end.day}, ${end.year}';
    }
    return '${start.day} ${_monthName(start).split(' ').first} – ${end.day} ${_monthName(end)}';
  }

  @override
  Widget build(BuildContext context) {
    final grouped = <DateTime, List<Map<String, dynamic>>>{};
    for (final item in _items) {
      final date = DateTime.parse(item['starts_at'] as String).toLocal();
      final key = DateTime(date.year, date.month, date.day);
      grouped.putIfAbsent(key, () => []).add(item);
    }

    final visibleDays = _view == _CalendarView.week
        ? List.generate(
            7,
            (index) => _startOfWeek(_cursor).add(Duration(days: index)),
          )
        : (grouped.keys.toList()..sort());

    return Scaffold(
      appBar: AppBar(
        title: const Text('Calendar'),
        actions: [
          IconButton(
            onPressed: _load,
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
              child: SegmentedButton<_CalendarView>(
                segments: const [
                  ButtonSegment(
                    value: _CalendarView.month,
                    icon: Icon(Icons.calendar_month_rounded),
                    label: Text('Month'),
                  ),
                  ButtonSegment(
                    value: _CalendarView.week,
                    icon: Icon(Icons.view_week_rounded),
                    label: Text('Week'),
                  ),
                ],
                selected: {_view},
                onSelectionChanged: (values) => _setView(values.first),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
              child: Row(
                children: [
                  IconButton(
                    onPressed: () => _shift(-1),
                    icon: const Icon(Icons.chevron_left_rounded),
                    tooltip: _view == _CalendarView.month ? 'Previous month' : 'Previous week',
                  ),
                  Expanded(
                    child: Column(
                      children: [
                        Text(
                          _rangeTitle(),
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                        const SizedBox(height: 2),
                        TextButton(
                          onPressed: _today,
                          child: const Text('Today'),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    onPressed: () => _shift(1),
                    icon: const Icon(Icons.chevron_right_rounded),
                    tooltip: _view == _CalendarView.month ? 'Next month' : 'Next week',
                  ),
                ],
              ),
            ),
            if (_loading) const LinearProgressIndicator(minHeight: 2),
            Expanded(
              child: _error != null
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(28),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(_error!, textAlign: TextAlign.center),
                            const SizedBox(height: 12),
                            FilledButton.tonal(
                              onPressed: _load,
                              child: const Text('Try again'),
                            ),
                          ],
                        ),
                      ),
                    )
                  : visibleDays.isEmpty && !_loading
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(28),
                            child: Text(
                              _view == _CalendarView.month
                                  ? 'No deadlines or milestones this month.'
                                  : 'No deadlines or milestones this week.',
                              textAlign: TextAlign.center,
                            ),
                          ),
                        )
                      : RefreshIndicator(
                          onRefresh: _load,
                          child: ListView.builder(
                            physics: const AlwaysScrollableScrollPhysics(),
                            padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
                            itemCount: visibleDays.length,
                            itemBuilder: (context, index) {
                              final day = visibleDays[index];
                              final items = grouped[day] ?? const <Map<String, dynamic>>[];
                              final today = DateTime.now();
                              final isToday = day.year == today.year &&
                                  day.month == today.month &&
                                  day.day == today.day;
                              return Padding(
                                padding: const EdgeInsets.only(bottom: 18),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Container(
                                          width: 38,
                                          height: 38,
                                          alignment: Alignment.center,
                                          decoration: BoxDecoration(
                                            color: isToday
                                                ? Theme.of(context).colorScheme.primary
                                                : Theme.of(context).colorScheme.surfaceContainerHighest,
                                            borderRadius: BorderRadius.circular(12),
                                          ),
                                          child: Text(
                                            '${day.day}',
                                            style: TextStyle(
                                              fontWeight: FontWeight.w800,
                                              color: isToday
                                                  ? Theme.of(context).colorScheme.onPrimary
                                                  : null,
                                            ),
                                          ),
                                        ),
                                        const SizedBox(width: 10),
                                        Text(
                                          _weekday(day.weekday),
                                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                                fontWeight: FontWeight.w800,
                                              ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    if (items.isEmpty)
                                      Padding(
                                        padding: const EdgeInsets.fromLTRB(48, 4, 0, 8),
                                        child: Text(
                                          'No scheduled items',
                                          style: Theme.of(context).textTheme.bodySmall,
                                        ),
                                      )
                                    else
                                      ...items.map(
                                        (item) => Card(
                                          elevation: 0,
                                          margin: const EdgeInsets.only(bottom: 8),
                                          clipBehavior: Clip.antiAlias,
                                          child: ListTile(
                                            leading: Icon(_icon(item['kind'] as String?)),
                                            title: Text(item['title'] as String),
                                            subtitle: Text(_subtitle(item)),
                                            trailing: item['task_id'] != null || item['project_id'] != null
                                                ? const Icon(Icons.chevron_right_rounded)
                                                : null,
                                            onTap: () {
                                              final taskId = item['task_id'] as String?;
                                              final projectId = item['project_id'] as String?;
                                              if (taskId != null) {
                                                context.push('/tasks/$taskId');
                                              } else if (projectId != null) {
                                                context.push('/projects/$projectId');
                                              }
                                            },
                                          ),
                                        ),
                                      ),
                                  ],
                                ),
                              );
                            },
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  String _weekday(int weekday) => switch (weekday) {
        DateTime.monday => 'Monday',
        DateTime.tuesday => 'Tuesday',
        DateTime.wednesday => 'Wednesday',
        DateTime.thursday => 'Thursday',
        DateTime.friday => 'Friday',
        DateTime.saturday => 'Saturday',
        DateTime.sunday => 'Sunday',
        _ => '',
      };

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
