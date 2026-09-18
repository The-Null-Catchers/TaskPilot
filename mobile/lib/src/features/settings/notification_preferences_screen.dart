import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api.dart';

class NotificationPreferencesScreen extends ConsumerStatefulWidget {
  const NotificationPreferencesScreen({super.key});

  @override
  ConsumerState<NotificationPreferencesScreen> createState() => _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState extends ConsumerState<NotificationPreferencesScreen> {
  bool _loading = true;
  bool _saving = false;
  String? _error;
  Map<String, dynamic>? _preferences;
  Map<String, dynamic>? _providers;

  @override
  void initState() {
    super.initState();
    _load();
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

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final responses = await Future.wait([
        ref.read(apiProvider).dio.get('/api/v1/notifications/preferences'),
        ref.read(apiProvider).dio.get('/api/v1/notifications/provider-config'),
      ]);
      if (!mounted) return;
      setState(() {
        _preferences = (responses[0].data as Map).cast<String, dynamic>();
        _providers = (responses[1].data as Map).cast<String, dynamic>();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = _message(error, 'Could not load notification preferences.'));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _patch(Map<String, dynamic> values) async {
    if (_saving || _preferences == null) return;
    final previous = Map<String, dynamic>.from(_preferences!);
    setState(() {
      _saving = true;
      _error = null;
      _preferences = {...previous, ...values};
    });
    try {
      final response = await ref.read(apiProvider).dio.patch('/api/v1/notifications/preferences', data: values);
      if (!mounted) return;
      setState(() => _preferences = (response.data as Map).cast<String, dynamic>());
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _preferences = previous;
        _error = _message(error, 'Could not update notification preferences.');
      });
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _toggle({
    required String field,
    required String title,
    required String subtitle,
    required IconData icon,
  }) {
    final enabled = _preferences?[field] == true;
    return SwitchListTile(
      secondary: Icon(icon),
      title: Text(title),
      subtitle: Text(subtitle),
      value: enabled,
      onChanged: _saving ? null : (value) => _patch({field: value}),
    );
  }

  @override
  Widget build(BuildContext context) {
    final preferences = _preferences;
    final providers = _providers;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notification settings'),
        actions: [
          IconButton(onPressed: _loading ? null : _load, icon: const Icon(Icons.refresh_rounded), tooltip: 'Refresh'),
        ],
      ),
      body: SafeArea(
        child: _loading && preferences == null
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 36),
                  children: [
                    if (_error != null)
                      Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.errorContainer,
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Text(_error!),
                      ),
                    if (preferences != null) ...[
                      Text('Delivery channels', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 10),
                      Card(
                        elevation: 0,
                        child: Column(
                          children: [
                            _toggle(
                              field: 'in_app_enabled',
                              title: 'In-app inbox',
                              subtitle: 'Keep notification records in the TaskPilot inbox.',
                              icon: Icons.inbox_outlined,
                            ),
                            const Divider(height: 1),
                            _toggle(
                              field: 'email_enabled',
                              title: 'Email',
                              subtitle: 'Receive enabled events by email or digest.',
                              icon: Icons.email_outlined,
                            ),
                            const Divider(height: 1),
                            _toggle(
                              field: 'mobile_enabled',
                              title: 'Mobile push',
                              subtitle: 'Allow registered Flutter devices to receive FCM/APNs notifications.',
                              icon: Icons.phone_android_rounded,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 22),
                      Text('Events', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 10),
                      Card(
                        elevation: 0,
                        child: Column(
                          children: [
                            _toggle(field: 'assignments_enabled', title: 'Assignments', subtitle: 'When tasks are assigned to you.', icon: Icons.assignment_ind_outlined),
                            const Divider(height: 1),
                            _toggle(field: 'mentions_enabled', title: 'Mentions', subtitle: 'When a collaborator mentions you.', icon: Icons.alternate_email_rounded),
                            const Divider(height: 1),
                            _toggle(field: 'comments_enabled', title: 'Comments', subtitle: 'Relevant comments and watched-task activity.', icon: Icons.chat_bubble_outline_rounded),
                            const Divider(height: 1),
                            _toggle(field: 'deadlines_enabled', title: 'Deadlines', subtitle: 'Upcoming and overdue task reminders.', icon: Icons.schedule_rounded),
                            const Divider(height: 1),
                            _toggle(field: 'dependencies_enabled', title: 'Dependencies', subtitle: 'Blockers and dependency resolution updates.', icon: Icons.account_tree_outlined),
                          ],
                        ),
                      ),
                      const SizedBox(height: 22),
                      Text('Email digest', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 10),
                      Card(
                        elevation: 0,
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: DropdownButtonFormField<String>(
                            initialValue: preferences['digest_frequency'] as String? ?? 'instant',
                            decoration: const InputDecoration(labelText: 'Frequency'),
                            items: const [
                              DropdownMenuItem(value: 'instant', child: Text('Instant')),
                              DropdownMenuItem(value: 'hourly', child: Text('Hourly digest')),
                              DropdownMenuItem(value: 'daily', child: Text('Daily digest')),
                              DropdownMenuItem(value: 'off', child: Text('Off')),
                            ],
                            onChanged: _saving ? null : (value) {
                              if (value != null) _patch({'digest_frequency': value});
                            },
                          ),
                        ),
                      ),
                      const SizedBox(height: 22),
                      Text('Push readiness', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 10),
                      Card(
                        elevation: 0,
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              _ProviderRow(label: 'Firebase Cloud Messaging', configured: providers?['fcm_enabled'] == true),
                              const SizedBox(height: 10),
                              _ProviderRow(label: 'Apple Push Notification service', configured: providers?['apns_enabled'] == true),
                              const SizedBox(height: 12),
                              Text(
                                'Push delivery is sent by the TaskPilot backend after a device token is registered. Native Firebase/APNs credentials remain app/deployment configuration and are never stored in the repository.',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
      ),
    );
  }
}

class _ProviderRow extends StatelessWidget {
  const _ProviderRow({required this.label, required this.configured});
  final String label;
  final bool configured;

  @override
  Widget build(BuildContext context) => Row(
        children: [
          Icon(configured ? Icons.check_circle_rounded : Icons.info_outline_rounded, size: 18, color: configured ? Theme.of(context).colorScheme.primary : null),
          const SizedBox(width: 8),
          Expanded(child: Text(label)),
          Text(configured ? 'Configured' : 'Not configured', style: Theme.of(context).textTheme.labelMedium),
        ],
      );
}
