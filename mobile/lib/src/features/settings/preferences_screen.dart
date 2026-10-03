import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'preferences_controller.dart';

class PreferencesScreen extends ConsumerStatefulWidget {
  const PreferencesScreen({super.key});

  @override
  ConsumerState<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends ConsumerState<PreferencesScreen> {
  String _theme = 'system';
  String _density = 'comfortable';
  int _weekStart = 1;
  String _defaultHome = 'home';
  bool _seeded = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(preferencesProvider.notifier).load());
  }

  void _seed(UserPreferences preferences) {
    if (_seeded || preferences.loading) return;
    _theme = preferences.theme;
    _density = preferences.density;
    _weekStart = preferences.weekStart;
    _defaultHome = preferences.defaultHome;
    _seeded = true;
  }

  @override
  Widget build(BuildContext context) {
    final preferences = ref.watch(preferencesProvider);
    _seed(preferences);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Preferences'),
        actions: [
          IconButton(
            onPressed: preferences.loading ? null : () async {
              setState(() => _seeded = false);
              await ref.read(preferencesProvider.notifier).load();
            },
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 40),
          children: [
            if (preferences.error != null)
              Container(
                margin: const EdgeInsets.only(bottom: 16),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.errorContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(preferences.error!),
              ),
            Text(
              'Personal experience',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Text(
              'These settings follow your TaskPilot account across web and mobile.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            Card(
              elevation: 0,
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.palette_outlined),
                    title: const Text('Theme'),
                    subtitle: const Text('Light, dark, or follow the device setting.'),
                    trailing: DropdownButton<String>(
                      value: _theme,
                      items: const [
                        DropdownMenuItem(value: 'system', child: Text('System')),
                        DropdownMenuItem(value: 'light', child: Text('Light')),
                        DropdownMenuItem(value: 'dark', child: Text('Dark')),
                      ],
                      onChanged: preferences.loading ? null : (value) => setState(() => _theme = value ?? _theme),
                    ),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.density_medium_outlined),
                    title: const Text('Interface density'),
                    subtitle: const Text('Use comfortable spacing or a more compact layout.'),
                    trailing: DropdownButton<String>(
                      value: _density,
                      items: const [
                        DropdownMenuItem(value: 'comfortable', child: Text('Comfortable')),
                        DropdownMenuItem(value: 'compact', child: Text('Compact')),
                      ],
                      onChanged: preferences.loading ? null : (value) => setState(() => _density = value ?? _density),
                    ),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.calendar_view_week_outlined),
                    title: const Text('Week starts on'),
                    subtitle: const Text('Used by calendar week views.'),
                    trailing: DropdownButton<int>(
                      value: _weekStart,
                      items: const [
                        DropdownMenuItem(value: 0, child: Text('Sunday')),
                        DropdownMenuItem(value: 1, child: Text('Monday')),
                        DropdownMenuItem(value: 6, child: Text('Saturday')),
                      ],
                      onChanged: preferences.loading ? null : (value) => setState(() => _weekStart = value ?? _weekStart),
                    ),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.home_outlined),
                    title: const Text('Default landing page'),
                    subtitle: const Text('Choose what opens after signing in.'),
                    trailing: DropdownButton<String>(
                      value: _defaultHome,
                      items: const [
                        DropdownMenuItem(value: 'home', child: Text('Projects')),
                        DropdownMenuItem(value: 'my_tasks', child: Text('My Tasks')),
                        DropdownMenuItem(value: 'calendar', child: Text('Calendar')),
                      ],
                      onChanged: preferences.loading ? null : (value) => setState(() => _defaultHome = value ?? _defaultHome),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: preferences.loading
                  ? null
                  : () async {
                      try {
                        await ref.read(preferencesProvider.notifier).update(
                              theme: _theme,
                              density: _density,
                              weekStart: _weekStart,
                              defaultHome: _defaultHome,
                            );
                        if (!mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Preferences saved.')),
                        );
                      } catch (_) {
                        if (!mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Could not save preferences.')),
                        );
                      }
                    },
              icon: preferences.loading
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.save_outlined),
              label: Text(preferences.loading ? 'Saving…' : 'Save preferences'),
            ),
          ],
        ),
      ),
    );
  }
}
