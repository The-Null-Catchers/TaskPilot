import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api.dart';

class AttachmentsSection extends ConsumerStatefulWidget {
  const AttachmentsSection({super.key, this.taskId, this.entityId, this.entityType = 'task', this.title = 'Attachments', this.emptyText = 'No attachments yet.'}) : assert(taskId != null || entityId != null);
  final String? taskId;
  final String? entityId;
  final String entityType;
  final String title;
  final String emptyText;

  String get resolvedEntityId => entityId ?? taskId!;

  @override
  ConsumerState<AttachmentsSection> createState() => _AttachmentsSectionState();
}

class _AttachmentsSectionState extends ConsumerState<AttachmentsSection> {
  bool _loading = true;
  bool _uploading = false;
  double? _uploadProgress;
  String? _error;
  List<Map<String, dynamic>> _items = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await ref.read(apiProvider).dio.get(
        '/api/v1/attachments',
        queryParameters: {'entity_type': widget.entityType, 'entity_id': widget.resolvedEntityId},
      );
      if (!mounted) return;
      setState(() {
        _items = (response.data as List)
            .map((item) => (item as Map).cast<String, dynamic>())
            .toList();
      });
    } on DioException catch (error) {
      if (!mounted) return;
      setState(() => _error = _messageFor(error, fallback: 'Could not load attachments.'));
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Could not load attachments.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _messageFor(DioException error, {required String fallback}) {
    final data = error.response?.data;
    if (data is Map) {
      final detail = data['detail'];
      if (detail is String && detail.isNotEmpty) return detail;
      final nested = data['error'];
      if (nested is Map && nested['message'] is String) return nested['message'] as String;
    }
    return fallback;
  }

  Future<void> _pickAndUpload() async {
    if (_uploading) return;
    final result = await FilePicker.pickFiles(
      allowMultiple: false,
      withData: true,
    );
    if (result == null || result.files.isEmpty || !mounted) return;

    final picked = result.files.single;
    final bytes = picked.bytes;
    if (bytes == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('TaskPilot could not read that file. Please choose it again.')),
      );
      return;
    }

    setState(() {
      _uploading = true;
      _uploadProgress = 0;
      _error = null;
    });

    try {
      final form = FormData.fromMap({
        'entity_type': widget.entityType,
        'entity_id': widget.resolvedEntityId,
        'file': MultipartFile.fromBytes(bytes, filename: picked.name),
      });
      await ref.read(apiProvider).dio.post(
        '/api/v1/attachments',
        data: form,
        options: Options(contentType: 'multipart/form-data'),
        onSendProgress: (sent, total) {
          if (!mounted || total <= 0) return;
          setState(() => _uploadProgress = sent / total);
        },
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${picked.name} uploaded.')),
      );
      await _load();
    } on DioException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_messageFor(error, fallback: 'Upload failed. Check the file and try again.'))),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Upload failed. Check your connection and try again.')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _uploading = false;
          _uploadProgress = null;
        });
      }
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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open attachment.')),
        );
      }
    }
  }

  Future<void> _delete(Map<String, dynamic> item) async {
    final name = (item['original_name'] ?? item['safe_name'] ?? 'this attachment') as String;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete attachment?'),
        content: Text('Delete "$name" permanently?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      await ref.read(apiProvider).dio.delete('/api/v1/attachments/${item['id']}');
      if (!mounted) return;
      setState(() => _items = _items.where((candidate) => candidate['id'] != item['id']).toList());
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$name deleted.')));
    } on DioException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_messageFor(error, fallback: 'Could not delete attachment.'))),
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not delete attachment.')),
        );
      }
    }
  }

  String _size(dynamic value) {
    final bytes = (value as num?)?.toDouble() ?? 0;
    if (bytes >= 1024 * 1024) return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    if (bytes >= 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${bytes.toStringAsFixed(0)} B';
  }

  IconData _iconFor(String mime) {
    if (mime.startsWith('image/')) return Icons.image_outlined;
    if (mime == 'application/pdf') return Icons.picture_as_pdf_outlined;
    if (mime.startsWith('text/')) return Icons.description_outlined;
    return Icons.insert_drive_file_outlined;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.attach_file_rounded, size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                widget.title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
              ),
            ),
            IconButton(
              onPressed: _loading || _uploading ? null : _pickAndUpload,
              icon: const Icon(Icons.upload_file_rounded),
              tooltip: 'Upload attachment',
            ),
            IconButton(
              onPressed: _loading || _uploading ? null : _load,
              icon: const Icon(Icons.refresh_rounded),
              tooltip: 'Refresh attachments',
            ),
          ],
        ),
        if (_uploading)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: LinearProgressIndicator(value: _uploadProgress),
          ),
        if (_loading)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: LinearProgressIndicator(minHeight: 2),
          ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ),
        if (!_loading && _error == null && _items.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(widget.emptyText),
          ),
        if (_items.isNotEmpty)
          Card(
            elevation: 0,
            clipBehavior: Clip.antiAlias,
            child: Column(
              children: _items.map((item) {
                final mime = item['mime_type'] as String? ?? 'file';
                return ListTile(
                  leading: Icon(_iconFor(mime)),
                  title: Text((item['original_name'] ?? item['safe_name'] ?? 'Attachment') as String),
                  subtitle: Text('$mime · ${_size(item['size_bytes'])}'),
                  onTap: () => _open(item),
                  trailing: PopupMenuButton<String>(
                    tooltip: 'Attachment actions',
                    onSelected: (value) {
                      if (value == 'open') {
                        _open(item);
                      } else if (value == 'delete') {
                        _delete(item);
                      }
                    },
                    itemBuilder: (context) => const [
                      PopupMenuItem(value: 'open', child: ListTile(leading: Icon(Icons.open_in_new_rounded), title: Text('Open'))),
                      PopupMenuItem(value: 'delete', child: ListTile(leading: Icon(Icons.delete_outline_rounded), title: Text('Delete'))),
                    ],
                  ),
                );
              }).toList(),
            ),
          ),
      ],
    );
  }
}
