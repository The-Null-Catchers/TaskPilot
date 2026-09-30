import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth_controller.dart';

const onboardingUseCases = <String, String>{
  'Personal': 'Personal Productivity',
  'Software development': 'Software Development',
  'Business': 'Product Launch',
  'School': 'University Project',
  'Other': 'Blank Project',
};

String suggestedTemplateForUseCase(String useCase) =>
    onboardingUseCases[useCase] ?? 'Blank Project';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  String _selected = 'Software development';
  bool _saving = false;

  Future<void> _continue() async {
    if (_saving) return;
    setState(() => _saving = true);
    await ref.read(authProvider.notifier).completeOnboarding(useCase: _selected);
    if (!mounted) return;
    context.go('/home');
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final suggestion = suggestedTemplateForUseCase(_selected);
    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: false,
        title: const Text('Welcome to TaskPilot'),
      ),
      body: SafeArea(
        child: Center(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
            shrinkWrap: true,
            children: [
              Container(
                constraints: const BoxConstraints(maxWidth: 720),
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: scheme.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: scheme.outlineVariant),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.rocket_launch_outlined, size: 34, color: scheme.primary),
                    const SizedBox(height: 16),
                    Text(
                      'What will you use TaskPilot for?',
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Your personal workspace is ready. Pick a use case and TaskPilot will suggest a good starting project template.',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
                    ),
                    const SizedBox(height: 22),
                    ...onboardingUseCases.keys.map(
                      (item) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(16),
                          onTap: () => setState(() => _selected = item),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 160),
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                            decoration: BoxDecoration(
                              color: _selected == item ? scheme.primaryContainer : scheme.surface,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(
                                color: _selected == item ? scheme.primary : scheme.outlineVariant,
                              ),
                            ),
                            child: Row(
                              children: [
                                Icon(
                                  _selected == item ? Icons.radio_button_checked : Icons.radio_button_off,
                                  color: _selected == item ? scheme.primary : scheme.onSurfaceVariant,
                                ),
                                const SizedBox(width: 12),
                                Expanded(child: Text(item, style: const TextStyle(fontWeight: FontWeight.w600))),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: scheme.secondaryContainer.withValues(alpha: 0.5),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.auto_awesome_outlined, color: scheme.secondary),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text('Suggested template', style: TextStyle(fontWeight: FontWeight.w700)),
                                const SizedBox(height: 3),
                                Text(suggestion),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 22),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: _saving ? null : _continue,
                        icon: _saving
                            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.arrow_forward_rounded),
                        label: Text(_saving ? 'Preparing workspace…' : 'Continue to TaskPilot'),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
