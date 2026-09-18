import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api.dart';
import '../auth/auth_controller.dart';

class AccountSettingsScreen extends ConsumerStatefulWidget {
  const AccountSettingsScreen({super.key});

  @override
  ConsumerState<AccountSettingsScreen> createState() => _AccountSettingsScreenState();
}

class _AccountSettingsScreenState extends ConsumerState<AccountSettingsScreen> {
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _account;
  List<Map<String, dynamic>> _sessions = const [];

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
        ref.read(apiProvider).dio.get('/api/v1/auth/account'),
        ref.read(apiProvider).dio.get('/api/v1/auth/sessions'),
      ]);
      if (!mounted) return;
      setState(() {
        _account = (responses[0].data as Map).cast<String, dynamic>();
        _sessions = (responses[1].data as List).map((item) => (item as Map).cast<String, dynamic>()).toList();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = _message(error, 'Could not load account settings.'));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _requestVerification() async {
    try {
      await ref.read(apiProvider).dio.post('/api/v1/auth/email-verification/request');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Verification email requested.')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_message(error, 'Could not request verification email.'))));
    }
  }

  Future<void> _changePassword() async {
    final current = TextEditingController();
    final next = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Change password'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: current, obscureText: true, decoration: const InputDecoration(labelText: 'Current password')),
            const SizedBox(height: 12),
            TextField(controller: next, obscureText: true, decoration: const InputDecoration(labelText: 'New password')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Change')),
        ],
      ),
    );
    if (confirmed != true || current.text.isEmpty || next.text.length < 10) return;
    try {
      await ref.read(apiProvider).dio.post('/api/v1/auth/change-password', data: {'current_password': current.text, 'new_password': next.text});
      await ref.read(authProvider.notifier).logout();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Password changed. Sign in again on this device.')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_message(error, 'Could not change password.'))));
    }
  }

  Future<void> _changeEmail() async {
    final email = TextEditingController(text: _account?['email'] as String? ?? '');
    final password = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Change email'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'New email')),
            const SizedBox(height: 12),
            TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Password')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Send confirmation')),
        ],
      ),
    );
    if (confirmed != true || email.text.trim().isEmpty || password.text.isEmpty) return;
    try {
      await ref.read(apiProvider).dio.post('/api/v1/auth/change-email', data: {'email': email.text.trim(), 'password': password.text});
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Confirmation sent to the new email address.')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_message(error, 'Could not request email change.'))));
    }
  }

  Future<void> _revokeSession(Map<String, dynamic> session) async {
    final id = session['id'] as String?;
    if (id == null) return;
    try {
      await ref.read(apiProvider).dio.delete('/api/v1/auth/sessions/$id');
      if (!mounted) return;
      setState(() {
        _sessions = _sessions.map((item) => item['id'] == id ? {...item, 'active': false, 'revoked_at': DateTime.now().toUtc().toIso8601String()} : item).toList();
      });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Session revoked.')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_message(error, 'Could not revoke session.'))));
    }
  }

  Future<void> _logoutAll() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign out everywhere?'),
        content: const Text('All active sessions will be revoked, including this device.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Sign out all')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(apiProvider).dio.post('/api/v1/auth/sessions/logout-all');
      await ref.read(authProvider.notifier).logout();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_message(error, 'Could not revoke all sessions.'))));
    }
  }

  Future<void> _deleteAccount() async {
    final password = TextEditingController();
    final confirmation = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete account'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('This deactivates your account permanently. Transfer or delete owned workspaces and projects first.'),
            const SizedBox(height: 16),
            TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Password')),
            const SizedBox(height: 12),
            TextField(controller: confirmation, decoration: const InputDecoration(labelText: 'Type DELETE')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete account')),
        ],
      ),
    );
    if (confirmed != true || confirmation.text != 'DELETE' || password.text.isEmpty) return;
    try {
      await ref.read(apiProvider).dio.post('/api/v1/auth/delete-account', data: {'password': password.text, 'confirmation': confirmation.text});
      await ref.read(authProvider.notifier).logout();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_message(error, 'Could not delete account.'))));
    }
  }

  String _when(dynamic value) {
    if (value is! String || value.isEmpty) return 'Unknown';
    final parsed = DateTime.tryParse(value);
    if (parsed == null) return value;
    return parsed.toLocal().toString().split('.').first;
  }

  @override
  Widget build(BuildContext context) {
    final account = _account;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile & settings'),
        actions: [IconButton(onPressed: _loading ? null : _load, icon: const Icon(Icons.refresh_rounded), tooltip: 'Refresh')],
      ),
      body: SafeArea(
        child: _loading && account == null
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 40),
                  children: [
                    if (_error != null)
                      Container(
                        margin: const EdgeInsets.only(bottom: 16),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(color: Theme.of(context).colorScheme.errorContainer, borderRadius: BorderRadius.circular(14)),
                        child: Text(_error!),
                      ),
                    if (account != null) ...[
                      Card(
                        elevation: 0,
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Row(
                            children: [
                              CircleAvatar(
                                radius: 28,
                                child: Text(((account['name'] as String?) ?? 'T').trim().isEmpty ? 'T' : (account['name'] as String).trim().substring(0, 1).toUpperCase()),
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(account['name'] as String? ?? 'TaskPilot user', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                                    const SizedBox(height: 4),
                                    Text(account['email'] as String? ?? '', style: Theme.of(context).textTheme.bodyMedium),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      Text('Account', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 10),
                      Card(
                        elevation: 0,
                        child: Column(
                          children: [
                            ListTile(
                              leading: Icon(account['email_verified'] == true ? Icons.verified_rounded : Icons.mark_email_unread_outlined, color: account['email_verified'] == true ? Theme.of(context).colorScheme.primary : null),
                              title: Text(account['email_verified'] == true ? 'Email verified' : 'Verify email'),
                              subtitle: Text(account['email_verified'] == true ? 'Verified ${_when(account['email_verified_at'])}' : 'Request a verification message for your account.'),
                              trailing: account['email_verified'] == true ? null : const Icon(Icons.chevron_right_rounded),
                              onTap: account['email_verified'] == true ? null : _requestVerification,
                            ),
                            const Divider(height: 1),
                            ListTile(leading: const Icon(Icons.alternate_email_rounded), title: const Text('Change email'), subtitle: const Text('Confirm the new address before it becomes active.'), trailing: const Icon(Icons.chevron_right_rounded), onTap: _changeEmail),
                            const Divider(height: 1),
                            ListTile(leading: const Icon(Icons.password_rounded), title: const Text('Change password'), subtitle: const Text('Revokes existing sessions after the password changes.'), trailing: const Icon(Icons.chevron_right_rounded), onTap: _changePassword),
                          ],
                        ),
                      ),
                      const SizedBox(height: 24),
                      Row(
                        children: [
                          Expanded(child: Text('Sessions', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800))),
                          TextButton(onPressed: _sessions.any((item) => item['active'] == true) ? _logoutAll : null, child: const Text('Sign out all')),
                        ],
                      ),
                      const SizedBox(height: 8),
                      if (_sessions.isEmpty)
                        const Card(elevation: 0, child: Padding(padding: EdgeInsets.all(20), child: Text('No session history is available.')))
                      else
                        ..._sessions.map((session) {
                          final active = session['active'] == true;
                          final device = (session['device_name'] as String?)?.trim();
                          final agent = (session['user_agent'] as String?)?.trim();
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: Card(
                              elevation: 0,
                              child: ListTile(
                                leading: Icon(active ? Icons.devices_rounded : Icons.devices_other_outlined),
                                title: Text(device?.isNotEmpty == true ? device! : 'Session'),
                                subtitle: Text([
                                  if (session['ip_address'] is String && (session['ip_address'] as String).isNotEmpty) session['ip_address'] as String,
                                  if (agent?.isNotEmpty == true) agent!,
                                  active ? 'Last used ${_when(session['last_used_at'])}' : 'Revoked',
                                ].join(' · ')),
                                isThreeLine: true,
                                trailing: active ? IconButton(onPressed: () => _revokeSession(session), icon: const Icon(Icons.logout_rounded), tooltip: 'Revoke session') : const Icon(Icons.block_rounded),
                              ),
                            ),
                          );
                        }),
                      const SizedBox(height: 20),
                      Text('Danger zone', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 10),
                      Card(
                        elevation: 0,
                        child: ListTile(
                          leading: Icon(Icons.delete_forever_outlined, color: Theme.of(context).colorScheme.error),
                          title: Text('Delete account', style: TextStyle(color: Theme.of(context).colorScheme.error, fontWeight: FontWeight.w700)),
                          subtitle: const Text('Requires your password and DELETE confirmation.'),
                          trailing: const Icon(Icons.chevron_right_rounded),
                          onTap: _deleteAccount,
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
