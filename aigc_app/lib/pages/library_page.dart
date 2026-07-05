import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../models/document.dart';
import '../services/api_service.dart';

class LibraryPage extends StatefulWidget {
  final VoidCallback? onChanged;

  const LibraryPage({super.key, this.onChanged});

  @override
  State<LibraryPage> createState() => _LibraryPageState();
}

class _LibraryPageState extends State<LibraryPage> {
  final _api = ApiService();
  final List<Document> _documents = [];
  bool _isLoading = true;
  bool _isUploading = false;
  String? _error;
  Timer? _pollTimer;

  static const _bg = Color(0xFFFAF7F1);
  static const _card = Color(0xFFFFFCF7);
  static const _ink = Color(0xFF34324A);
  static const _muted = Color(0xFF7C7A8A);
  static const _blue = Color(0xFF536878);
  static const _teal = Color(0xFF7A9E9F);
  static const _purple = Color(0xFF7566A0);
  static const _amber = Color(0xFFD97706);
  static const _red = Color(0xFFDC2626);
  static const _border = Color(0xFFE5DED2);

  static const _allowedExtensions = [
    'pdf',
    'doc',
    'docx',
    'ppt',
    'pptx',
    'txt',
  ];

  @override
  void initState() {
    super.initState();
    _fetchDocuments();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _api.dispose();
    super.dispose();
  }

  Future<void> _fetchDocuments() async {
    try {
      final docs = await _api.getDocuments();
      if (!mounted) return;
      setState(() {
        _documents
          ..clear()
          ..addAll(docs);
        _isLoading = false;
        _error = null;
      });
      if (docs.any((doc) => doc.isProcessing)) {
        _startPolling();
      } else {
        _pollTimer?.cancel();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _error = e.toString();
      });
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(
      const Duration(seconds: 3),
      (_) => _fetchDocuments(),
    );
  }

  Future<void> _uploadFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: _allowedExtensions,
    );
    if (result == null || result.files.isEmpty) return;

    final file = result.files.first;
    final ext = file.extension?.toLowerCase() ?? '';
    if (!_allowedExtensions.contains(ext)) {
      _showSnack('暂不支持 .$ext 文件，请上传 PDF、Word、PPT 或 TXT。', _red);
      return;
    }

    setState(() => _isUploading = true);
    try {
      await _api.uploadDocument(file);
      await _fetchDocuments();
      widget.onChanged?.call();
      _showSnack('资料已上传，正在后台解析。', _teal);
    } catch (e) {
      _showSnack('上传失败：$e', _red);
    } finally {
      if (mounted) setState(() => _isUploading = false);
    }
  }

  Future<void> _deleteDoc(String docId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder:
          (ctx) => AlertDialog(
            title: const Text('删除资料'),
            content: const Text('删除后不可恢复，确定删除这份资料吗？'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('取消'),
              ),
              TextButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('删除', style: TextStyle(color: _red)),
              ),
            ],
          ),
    );
    if (confirm != true) return;

    try {
      await _api.deleteDocument(docId);
      await _fetchDocuments();
      widget.onChanged?.call();
      _showSnack('资料已删除。', _teal);
    } catch (e) {
      _showSnack('删除失败：$e', _red);
    }
  }

  Future<void> _reparseDoc(String docId) async {
    try {
      await _api.reparseDocument(docId);
      await _fetchDocuments();
      widget.onChanged?.call();
      _showSnack('已重新触发解析。', _teal);
    } catch (e) {
      _showSnack('重新解析失败：$e', _red);
    }
  }

  Future<void> _openReport(Document doc) async {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) {
        return FutureBuilder<Map<String, dynamic>>(
          future: _api.getDocumentReport(doc.id),
          builder: (context, snapshot) {
            if (!snapshot.hasData) {
              return const SafeArea(
                child: SizedBox(
                  height: 220,
                  child: Center(child: CircularProgressIndicator()),
                ),
              );
            }
            final data = snapshot.data!;
            final report =
                (data['report'] as Map?)?.cast<String, dynamic>() ??
                <String, dynamic>{};
            final chapters = (data['chapters'] as List?) ?? const [];
            final kps = (data['knowledge_points'] as List?) ?? const [];
            final fragments = (data['fragments'] as List?) ?? const [];
            return SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 18),
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    maxHeight: MediaQuery.sizeOf(context).height * 0.78,
                  ),
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          doc.fileName,
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w900,
                            color: _ink,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            _smallPill(
                              _statusLabel(
                                report['parse_status']?.toString() ??
                                    doc.parseStatus,
                              ),
                              _statusColor(doc.parseStatus),
                            ),
                            _smallPill(
                              '${report['total_chars'] ?? 0} 字',
                              _muted,
                            ),
                            _smallPill(
                              '${report['total_pages'] ?? 0} 页',
                              _blue,
                            ),
                            _smallPill(
                              '${report['parsed_pages'] ?? 0} 已解析',
                              _teal,
                            ),
                            if ((report['ocr_pages'] ?? 0) != 0)
                              _smallPill('${report['ocr_pages']} OCR', _amber),
                            if ((report['failed_pages'] ?? 0) != 0)
                              _smallPill('${report['failed_pages']} 失败页', _red),
                            _smallPill('${chapters.length} 章', _purple),
                            _smallPill('${kps.length} 知识点', _teal),
                            _smallPill(
                              '${report['formula_count'] ?? 0} 公式',
                              _purple,
                            ),
                            _smallPill(
                              '${report['example_count'] ?? 0} 例题',
                              _amber,
                            ),
                            _smallPill(
                              '${report['exercise_count'] ?? 0} 习题',
                              _blue,
                            ),
                            _smallPill(
                              '${report['chunk_count'] ?? fragments.length} 片段',
                              _blue,
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        _reportSection('章节', chapters, (item) {
                          final map = (item as Map).cast<String, dynamic>();
                          return '${map['chapter_number'] ?? ''}. ${map['chapter_name'] ?? ''}';
                        }),
                        _reportSection('知识点', kps, (item) {
                          final map = (item as Map).cast<String, dynamic>();
                          final page = map['page_reference']?.toString() ?? '';
                          final type = map['kp_type']?.toString() ?? '';
                          final suffix = [
                            if (type.isNotEmpty) type,
                            if (page.isNotEmpty) 'p.$page',
                          ].join(' · ');
                          return suffix.isEmpty
                              ? '${map['name'] ?? ''}'
                              : '${map['name'] ?? ''}  [$suffix]';
                        }),
                        _reportSection('检索片段预览', fragments, (item) {
                          final map = (item as Map).cast<String, dynamic>();
                          final start = map['page_start'] ?? 0;
                          final end = map['page_end'] ?? start;
                          final pageLabel =
                              start == 0
                                  ? ''
                                  : 'p.$start${end != start ? '-$end' : ''}  ';
                          return '$pageLabel${map['text'] ?? ''}';
                        }),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                onPressed: () {
                                  Navigator.pop(ctx);
                                  _reparseDoc(doc.id);
                                },
                                icon: const Icon(Icons.refresh),
                                label: const Text('重新解析'),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: FilledButton(
                                onPressed: () => Navigator.pop(ctx),
                                child: const Text('完成'),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _reportSection(
    String title,
    List items,
    String Function(dynamic item) labelOf,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.w900, color: _ink),
          ),
          const SizedBox(height: 8),
          if (items.isEmpty)
            const Text('暂无数据。可以点“重新解析”再试。', style: TextStyle(color: _muted))
          else
            ...items
                .take(8)
                .map(
                  (item) => Container(
                    width: double.infinity,
                    margin: const EdgeInsets.only(bottom: 7),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF4F1EA),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      labelOf(item),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: _ink, height: 1.35),
                    ),
                  ),
                ),
        ],
      ),
    );
  }

  void _showSnack(String message, Color color) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: color,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  String _statusLabel(String status) {
    return switch (status) {
      'completed' => '解析完成',
      'failed' => '解析失败',
      'parsing' => '正在解析',
      'chunking' => '正在分块',
      'embedding' => '生成索引',
      'uploaded' => '等待解析',
      _ => '处理中',
    };
  }

  Color _statusColor(String status) {
    return switch (status) {
      'completed' => _teal,
      'failed' => _red,
      _ => _amber,
    };
  }

  String _fileSize(int? bytes) {
    if (bytes == null || bytes <= 0) return '';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / 1024 / 1024).toStringAsFixed(1)} MB';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _isUploading ? null : _uploadFile,
        icon:
            _isUploading
                ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
                : const Icon(Icons.upload_file),
        label: Text(_isUploading ? '上传中' : '上传资料'),
      ),
      body: RefreshIndicator(onRefresh: _fetchDocuments, child: _buildBody()),
    );
  }

  Widget _buildBody() {
    if (_isLoading) return const Center(child: CircularProgressIndicator());

    if (_error != null) {
      return ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _emptyState(
            icon: Icons.cloud_off_outlined,
            title: '资料库连接失败',
            subtitle: _error!,
            actionLabel: '重试',
            onAction: _fetchDocuments,
          ),
        ],
      );
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
      children: [
        _header(),
        const SizedBox(height: 12),
        _workflowCard(),
        const SizedBox(height: 12),
        _formatCard(),
        const SizedBox(height: 12),
        if (_documents.isEmpty)
          _emptyState(
            icon: Icons.folder_open_outlined,
            title: '还没有学习资料',
            subtitle: '上传教材、课件、论文或笔记后，系统会解析成章节、知识点和检索片段，用于课程规划、答疑、练习和测评。',
            actionLabel: '上传第一份资料',
            onAction: _uploadFile,
          )
        else ...[
          const Text(
            '已上传资料',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w900,
              color: _ink,
            ),
          ),
          const SizedBox(height: 10),
          ..._documents.map(_documentTile),
        ],
      ],
    );
  }

  Widget _header() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: _border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _iconBox(Icons.library_books_outlined, _blue),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '资料库',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                    color: _ink,
                  ),
                ),
                SizedBox(height: 6),
                Text(
                  '这里是课程模式的数据源。上传完成后会进入解析、分块、索引，再生成学习路径。',
                  style: TextStyle(color: _muted, height: 1.45),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _workflowCard() {
    final steps = const [
      _UploadStep(Icons.upload_file, '上传', 'PDF/Word/PPT/TXT', _blue),
      _UploadStep(Icons.manage_search, '解析', '章节和知识点', _teal),
      _UploadStep(Icons.hub_outlined, '索引', 'RAG 检索片段', _purple),
      _UploadStep(Icons.route_outlined, '学习', '讲义/答疑/练习', _amber),
    ];
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: _border),
      ),
      child: Row(
        children:
            steps
                .map(
                  (step) => Expanded(
                    child: Column(
                      children: [
                        CircleAvatar(
                          radius: 18,
                          backgroundColor: step.color.withValues(alpha: 0.14),
                          child: Icon(step.icon, color: step.color, size: 18),
                        ),
                        const SizedBox(height: 7),
                        Text(
                          step.title,
                          style: const TextStyle(
                            fontWeight: FontWeight.w900,
                            color: _ink,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          step.subtitle,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: _muted, fontSize: 10.5),
                        ),
                      ],
                    ),
                  ),
                )
                .toList(),
      ),
    );
  }

  Widget _formatCard() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '支持格式',
            style: TextStyle(fontWeight: FontWeight.w900, color: _ink),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children:
                const [
                  'PDF',
                  'DOC',
                  'DOCX',
                  'PPT',
                  'PPTX',
                  'TXT',
                ].map((item) => _formatPill(item)).toList(),
          ),
          const SizedBox(height: 10),
          const Text(
            '说明：PPTX、DOCX、PDF、TXT 支持较稳定；旧版 PPT/DOC 会尽量解析，失败时建议另存为 PPTX/DOCX 后上传。',
            style: TextStyle(color: _muted, height: 1.45, fontSize: 12.5),
          ),
        ],
      ),
    );
  }

  Widget _documentTile(Document doc) {
    final statusColor = _statusColor(doc.parseStatus);
    final type = (doc.fileType ?? doc.fileName.split('.').last).toUpperCase();
    final size = _fileSize(doc.fileSize);
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        onTap: () => _openReport(doc),
        minVerticalPadding: 14,
        leading: _iconBox(Icons.description_outlined, _blue, size: 42),
        title: Text(
          doc.fileName,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w900, color: _ink),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Wrap(
            spacing: 8,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              _smallPill(_statusLabel(doc.parseStatus), statusColor),
              _smallPill(type, _blue),
              if (size.isNotEmpty) _smallPill(size, _muted),
              if (doc.chapterCount != null)
                _smallPill('${doc.chapterCount} 章', _purple),
              if (doc.kpCount != null) _smallPill('${doc.kpCount} 知识点', _teal),
              if (doc.isCompleted &&
                  ((doc.chapterCount ?? 0) == 0 || (doc.kpCount ?? 0) == 0))
                _smallPill('建议重解析', _amber),
              if (doc.isProcessing)
                const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
            ],
          ),
        ),
        trailing: PopupMenuButton<String>(
          onSelected: (value) {
            if (value == 'report') _openReport(doc);
            if (value == 'reparse') _reparseDoc(doc.id);
            if (value == 'delete') _deleteDoc(doc.id);
          },
          itemBuilder:
              (_) => const [
                PopupMenuItem(value: 'report', child: Text('查看解析报告')),
                PopupMenuItem(value: 'reparse', child: Text('重新解析')),
                PopupMenuItem(value: 'delete', child: Text('删除')),
              ],
        ),
      ),
    );
  }

  Widget _emptyState({
    required IconData icon,
    required String title,
    required String subtitle,
    required String actionLabel,
    required VoidCallback onAction,
  }) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          children: [
            Icon(icon, size: 54, color: const Color(0xFFB4AFA5)),
            const SizedBox(height: 12),
            Text(
              title,
              style: const TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w900,
                color: _ink,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: const TextStyle(color: _muted, height: 1.45),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onAction,
              icon: const Icon(Icons.upload_file),
              label: Text(actionLabel),
            ),
          ],
        ),
      ),
    );
  }

  Widget _iconBox(IconData icon, Color color, {double size = 44}) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Icon(icon, color: color, size: size * 0.52),
    );
  }

  static Widget _formatPill(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Color(0xFFEAF1F1),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: _blue,
          fontWeight: FontWeight.w900,
          fontSize: 12,
        ),
      ),
    );
  }

  Widget _smallPill(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _UploadStep {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;

  const _UploadStep(this.icon, this.title, this.subtitle, this.color);
}
