import 'package:flutter/material.dart';

import '../services/api_service.dart';

class MicroLessonPage extends StatefulWidget {
  const MicroLessonPage({super.key});

  @override
  State<MicroLessonPage> createState() => _MicroLessonPageState();
}

class _MicroLessonPageState extends State<MicroLessonPage> {
  final _api = ApiService();
  final _topicController = TextEditingController();

  String _style = '讲解式';
  int _duration = 300;
  bool _isGenerating = false;
  String? _notice;
  Map<String, dynamic>? _result;

  static const _teal = Color(0xFF0F766E);
  static const _blue = Color(0xFF2563EB);
  static const _amber = Color(0xFFD97706);
  static const _muted = Color(0xFF6B7280);

  final _styles = const ['讲解式', '对话式', '故事式', '问题驱动式'];

  @override
  void dispose() {
    _topicController.dispose();
    _api.dispose();
    super.dispose();
  }

  Future<void> _generate() async {
    final topic = _topicController.text.trim();
    if (topic.isEmpty) {
      _showSnack('请输入一个微课主题');
      return;
    }

    setState(() {
      _isGenerating = true;
      _notice = null;
      _result = null;
    });

    try {
      final data = await _api.generateMicroLessonScript(
        courseId: '',
        topic: topic,
        style: _style,
        durationSeconds: _duration,
      );
      setState(() => _result = data);
    } catch (_) {
      setState(() {
        _notice = '微课接口暂不可用，当前展示示例脚本和课件大纲。';
        _result = _demoResult(topic);
      });
    } finally {
      if (mounted) setState(() => _isGenerating = false);
    }
  }

  void _showSnack(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: _amber,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  Map<String, dynamic> _demoResult(String topic) {
    return {
      'script': {
        'title': '$topic 微课',
        'teaching_objectives': [
          '理解 $topic 的核心概念',
          '掌握 $topic 的基本应用场景',
          '能够用一道例题说明解题过程',
        ],
        'outline': ['问题导入', '概念讲解', '例题演示', '课堂小结'],
        'sections': [
          {
            'section_name': '问题导入',
            'duration_seconds': 45,
            'script': '用一个生活化问题引出 $topic，让学生先产生疑问。',
          },
          {
            'section_name': '概念讲解',
            'duration_seconds': 120,
            'script': '解释 $topic 的定义、适用条件和常见误区。',
          },
          {
            'section_name': '例题演示',
            'duration_seconds': 90,
            'script': '通过一道典型题分步骤展示如何使用 $topic。',
          },
        ],
      },
      'ppt_content': {
        'slides': [
          {'slide_title': '学习目标', 'slide_content': '明确本节课要掌握什么'},
          {'slide_title': '问题导入', 'slide_content': '从真实问题进入主题'},
          {'slide_title': '核心概念', 'slide_content': '$topic 的定义与边界'},
          {'slide_title': '例题讲解', 'slide_content': '分步骤演示解题过程'},
          {'slide_title': '课堂小结', 'slide_content': '回顾重点和易错点'},
        ],
      },
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('微课课件')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          const _IntroCard(),
          const SizedBox(height: 12),
          _buildInputCard(),
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

  Widget _buildInputCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('生成设置', style: TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            TextField(
              controller: _topicController,
              decoration: const InputDecoration(
                labelText: '微课主题',
                hintText: '例如：二叉树遍历、牛顿第二定律、理想气体状态方程',
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _styles.map((style) {
                return ChoiceChip(
                  label: Text(style),
                  selected: _style == style,
                  onSelected: (_) => setState(() => _style = style),
                );
              }).toList(),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF9FAFB),
                border: Border.all(color: const Color(0xFFE5E7EB)),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('时长：${(_duration / 60).round()} 分钟',
                      style: const TextStyle(fontWeight: FontWeight.w800)),
                  Slider(
                    value: _duration.toDouble(),
                    min: 120,
                    max: 600,
                    divisions: 8,
                    onChanged: (value) => setState(() => _duration = value.round()),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: _isGenerating ? null : _generate,
              icon: const Icon(Icons.auto_awesome),
              label: Text(_isGenerating ? '正在生成...' : '生成微课'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultCard() {
    final script = (_result!['script'] as Map?)?.cast<String, dynamic>() ?? _result!;
    final objectives = (script['teaching_objectives'] as List?) ?? const [];
    final outline = (script['outline'] as List?) ?? const [];
    final sections = (script['sections'] as List?) ?? const [];
    final ppt = (_result!['ppt_content'] as Map?)?.cast<String, dynamic>() ?? {};
    final slides = (ppt['slides'] as List?) ?? const [];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              script['title']?.toString() ?? '微课已生成',
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 12),
            if (objectives.isNotEmpty)
              _SimpleList(title: '教学目标', items: objectives.map((item) => item.toString()).toList(), color: _teal),
            if (outline.isNotEmpty)
              _SimpleList(title: '课程大纲', items: outline.map((item) => item.toString()).toList(), color: _blue),
            if (sections.isNotEmpty) ...[
              const Text('脚本片段', style: TextStyle(fontWeight: FontWeight.w800)),
              const SizedBox(height: 8),
              ...sections.map((item) {
                final section = (item as Map).cast<String, dynamic>();
                return Container(
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF9FAFB),
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${section['section_name'] ?? '片段'} · ${section['duration_seconds'] ?? '-'} 秒',
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 6),
                      Text(section['script']?.toString() ?? '', style: const TextStyle(height: 1.45)),
                    ],
                  ),
                );
              }),
            ],
            if (slides.isNotEmpty)
              _SimpleList(
                title: '课件页',
                items: slides.map((item) {
                  final slide = (item as Map).cast<String, dynamic>();
                  return '${slide['slide_title'] ?? '幻灯片'}：${slide['slide_content'] ?? ''}';
                }).toList(),
                color: _amber,
              ),
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
                color: _MicroLessonPageState._teal.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.smart_display_outlined, color: _MicroLessonPageState._teal),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('把知识点变成短课', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800)),
                  SizedBox(height: 5),
                  Text(
                    '适合教师备课和学生快速复习。输出脚本、教学目标、课程大纲和课件页建议。',
                    style: TextStyle(color: _MicroLessonPageState._muted, height: 1.45),
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

class _SimpleList extends StatelessWidget {
  final String title;
  final List<String> items;
  final Color color;

  const _SimpleList({required this.title, required this.items, required this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          ...items.asMap().entries.map(
                (entry) => Padding(
                  padding: const EdgeInsets.only(bottom: 7),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 22,
                        height: 22,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: color.withValues(alpha: 0.10),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          '${entry.key + 1}',
                          style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w800),
                        ),
                      ),
                      const SizedBox(width: 9),
                      Expanded(child: Text(entry.value, style: const TextStyle(height: 1.45))),
                    ],
                  ),
                ),
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
