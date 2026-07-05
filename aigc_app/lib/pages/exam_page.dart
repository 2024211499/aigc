import 'package:flutter/material.dart';

import '../services/api_service.dart';

class ExamPage extends StatefulWidget {
  const ExamPage({super.key});

  @override
  State<ExamPage> createState() => _ExamPageState();
}

class _ExamPageState extends State<ExamPage> {
  final _api = ApiService();
  bool _isGenerating = false;
  String _examType = '单元测试';
  int _questionCount = 20;
  int _duration = 90;
  String? _notice;
  Map<String, dynamic>? _result;

  static const _purple = Color(0xFF7C3AED);
  static const _amber = Color(0xFFD97706);
  static const _muted = Color(0xFF6B7280);

  @override
  void dispose() {
    _api.dispose();
    super.dispose();
  }

  Future<void> _generateExam() async {
    setState(() {
      _isGenerating = true;
      _result = null;
      _notice = null;
    });
    try {
      final courses = await _api.getCourses();
      if (courses.isEmpty) {
        throw Exception('还没有课程资料，请先上传教材或课件。');
      }
      final data = await _api.generateExam(
        courseId: courses.first.id,
        examType: _examType,
        totalQuestions: _questionCount,
        durationMinutes: _duration,
      );
      setState(() => _result = data);
    } catch (_) {
      setState(() {
        _notice = '组卷接口暂不可用，当前展示示例试卷结构。';
        _result = _demoExam();
      });
    } finally {
      if (mounted) setState(() => _isGenerating = false);
    }
  }

  Map<String, dynamic> _demoExam() {
    return {
      'paper': {
        'title': '示例 $_examType',
        'duration_minutes': _duration,
        'total_score': 100,
        'sections': [
          {'name': '选择题', 'count': 10, 'score': 30},
          {'name': '填空题', 'count': 5, 'score': 20},
          {'name': '综合应用题', 'count': 5, 'score': 50},
        ],
      },
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('智能组卷')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          const _IntroCard(),
          const SizedBox(height: 12),
          _buildConfigCard(),
          if (_notice != null) ...[
            const SizedBox(height: 12),
            _InfoBox(text: _notice!, color: _amber),
          ],
          if (_isGenerating) ...[
            const SizedBox(height: 12),
            const LinearProgressIndicator(minHeight: 3),
          ],
          if (_result != null) ...[
            const SizedBox(height: 12),
            _buildResultCard(),
          ],
        ],
      ),
    );
  }

  Widget _buildConfigCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('组卷参数', style: TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _examType,
              decoration: const InputDecoration(labelText: '试卷类型'),
              items: const ['单元测试', '期中模拟', '期末复习', '错题强化']
                  .map((item) => DropdownMenuItem(value: item, child: Text(item)))
                  .toList(),
              onChanged: (value) => setState(() => _examType = value ?? _examType),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _SliderField(
                    label: '题目数',
                    value: _questionCount,
                    min: 5,
                    max: 40,
                    divisions: 7,
                    onChanged: (value) => setState(() => _questionCount = value),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _SliderField(
                    label: '时长',
                    value: _duration,
                    min: 30,
                    max: 150,
                    divisions: 8,
                    suffix: '分钟',
                    onChanged: (value) => setState(() => _duration = value),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: _isGenerating ? null : _generateExam,
              icon: const Icon(Icons.auto_awesome),
              label: Text(_isGenerating ? '正在组卷...' : '生成试卷'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultCard() {
    final paper = (_result!['paper'] as Map?)?.cast<String, dynamic>() ??
        (_result!['exam'] as Map?)?.cast<String, dynamic>() ??
        _result!;
    final sections = (paper['sections'] as List?) ?? const [];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              paper['title']?.toString() ?? '试卷已生成',
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Text(
              '时长 ${paper['duration_minutes'] ?? _duration} 分钟 · 总分 ${paper['total_score'] ?? 100}',
              style: const TextStyle(color: _muted),
            ),
            const SizedBox(height: 12),
            ...sections.map((item) {
              final section = (item as Map).cast<String, dynamic>();
              return ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.check_circle_outline, color: _purple),
                title: Text(section['name']?.toString() ?? '题型'),
                subtitle: Text('${section['count'] ?? '-'} 题 · ${section['score'] ?? '-'} 分'),
              );
            }),
          ],
        ),
      ),
    );
  }
}

class _IntroCard extends StatelessWidget {
  const _IntroCard();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: _ExamPageState._purple.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.quiz_outlined, color: _ExamPageState._purple),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('按课程目标生成试卷', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800)),
                  SizedBox(height: 5),
                  Text(
                    '适合考试复习、阶段测评和教师备课。后续可继续接入难度比例、知识点覆盖率和答案解析。',
                    style: TextStyle(color: _ExamPageState._muted, height: 1.45),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SliderField extends StatelessWidget {
  final String label;
  final int value;
  final int min;
  final int max;
  final int divisions;
  final String suffix;
  final ValueChanged<int> onChanged;

  const _SliderField({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.divisions,
    required this.onChanged,
    this.suffix = '',
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF9FAFB),
        border: Border.all(color: const Color(0xFFE5E7EB)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12.5, color: _ExamPageState._muted)),
          Text(
            suffix.isEmpty ? '$value' : '$value $suffix',
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
          ),
          Slider(
            value: value.toDouble(),
            min: min.toDouble(),
            max: max.toDouble(),
            divisions: divisions,
            onChanged: (value) => onChanged(value.round()),
          ),
        ],
      ),
    );
  }
}

class _InfoBox extends StatelessWidget {
  final String text;
  final Color color;

  const _InfoBox({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        border: Border.all(color: color.withValues(alpha: 0.25)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(text, style: TextStyle(color: color)),
    );
  }
}
