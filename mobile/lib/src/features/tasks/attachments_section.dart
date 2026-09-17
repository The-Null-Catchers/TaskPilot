import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api.dart';

class AttachmentsSection extends ConsumerStatefulWidget {
  const AttachmentsSection({super.key, required this.taskId});
  final String taskId;

  @override
  ConsumerState<AttachmentsSection> createState() => _AttachmentsSectionState();
}

class _AttachmentsSectionState extends ConsumerState<AttachmentsSection> {
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _items = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await ref.read(apiProvider).dio.get('/api/v1/attachments', queryParameters: {
        'entity_type': 'task',
        'entity_id': widget.taskId,
      });
      if (!mounted) return;
      setState(() {
        _items = (response.data as List).map((item) => (item as Map).cast<String, dynamic>()).toList();
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Could not load attachments.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _open(Map<String, dynamic> item) async {
    try {
      final response = await ref.read(apiProvider).dio.get('/api/v1/attachments/${item['id']}/download');
      final data = (response.data as Map).cast<String, dynamic>();
      final uri = Uri.tryParse(data['url'] as String? ?? '');
      if (uri == null || !await launchUrl(uri, mode: LaunchMode.externalApplication)) {
        throw StateError('Could not launch attachment');
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not open attachment.')));
      }
    }
  }

  String _size(dynamic value) {
    final bytes = (value as num?)?.toDouble() ?? 0;
    if (bytes >= 1024 * 1024) return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    if (bytes >= 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${bytes.toStringAsFixed(0)} B';
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          const Icon(Icons.attach_file_rounded, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text('Attachments', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
          IconButton(onPressed: _loading ? null : _load, icon: const Icon(Icons.refresh_rounded), tooltip: 'Refresh attachments'),
        ]),
        if (_loading) const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: LinearProgressIndicator(minHeight: 2)),
        if (_error != null) Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        if (!_loading && _error == null && _items.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 8), child: Text('No attachments yet.')),
        if (_items.isNotEmpty)
          Card(
            elevation: 0,
            clipBehavior: Clip.antiAlias,
            child: Column(
              children: _items.map((item) => ListTile(
                    leading: const Icon(Icons.insert_drive_file_outlined),
                    title: Text((item['original_name'] ?? item['safe_name'] ?? 'Attachment') as String),
                    subtitle: Text('${item['mime_type'] ?? 'file'} · ${_size(item['size_bytes'])}'),
                    trailing: const Icon(Icons.open_in_new_rounded),
                    onTap: () => _open(item),
                  )).toList(),
            ),
          ),
      ],
    );
  }
}
