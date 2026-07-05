import 'package:flutter/material.dart';

import 'course_tab_page.dart';
import 'exam_page.dart';
import 'exercise_page.dart';
import 'library_page.dart';
import 'microlesson_page.dart';
import 'quick_answer_page.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  static const _blue = Color(0xFF2563EB);
  static const _teal = Color(0xFF0F766E);
  static const _purple = Color(0xFF7C3AED);
  static const _amber = Color(0xFFD97706);
  static const _muted = Color(0xFF6B7280);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AIGC 教学助手'),
        actions: [
          IconButton(
            tooltip: '快速答疑',
            icon: const Icon(Icons.flash_on_outlined),
            onPressed: () => _open(context, const QuickAnswerPage()),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          _todayCard(context),
          const SizedBox(height: 12),
          _primaryActions(context),
          const SizedBox(height: 12),
          _flowCard(context),
          const SizedBox(height: 12),
          _toolList(context),
        ],
      ),
    );
  }

  Widget _todayCard(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(color: _blue.withValues(alpha: 0.10), borderRadius: BorderRadius.circular(16)),
                  child: const Icon(Icons.play_lesson_outlined, color: _blue, size: 28),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('今日学习', style: TextStyle(fontSize: 21, fontWeight: FontWeight.w900)),
                      SizedBox(height: 4),
                      Text('NOR 门 SR 锁存器 · 第 2 天', style: TextStyle(color: _muted)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: const LinearProgressIndicator(value: 0.42, minHeight: 8, backgroundColor: Color(0xFFE5E7EB), color: _teal),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () => _open(context, const CourseTabPage()),
                    icon: const Icon(Icons.play_arrow_rounded),
                    label: const Text('继续学习'),
                  ),
                ),
                const SizedBox(width: 10),
                IconButton.outlined(
                  tooltip: '提问',
                  onPressed: () => _open(context, const QuickAnswerPage()),
                  icon: const Icon(Icons.forum_outlined),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _primaryActions(BuildContext context) {
    return Row(
      children: [
        Expanded(child: _ActionCard(icon: Icons.upload_file, title: '上传资料', subtitle: '生成课程', color: _blue, onTap: () => _open(context, const LibraryPage()))),
        const SizedBox(width: 10),
        Expanded(child: _ActionCard(icon: Icons.flash_on_outlined, title: '题目答疑', subtitle: '拍照也能问', color: _teal, onTap: () => _open(context, const QuickAnswerPage()))),
      ],
    );
  }

  Widget _flowCard(BuildContext context) {
    final steps = const [
      _FlowStep(Icons.upload_file, '上传资料', '课件、教材、论文'),
      _FlowStep(Icons.route_outlined, '生成路径', '评估基础并排日程'),
      _FlowStep(Icons.menu_book_outlined, '学习讲义', '图解、公式、推导'),
      _FlowStep(Icons.edit_note_outlined, '练习测评', '错题进入复盘'),
    ];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('学习闭环', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
            const SizedBox(height: 12),
            ...steps.asMap().entries.map((entry) {
              final step = entry.value;
              final last = entry.key == steps.length - 1;
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Column(
                    children: [
                      CircleAvatar(radius: 17, backgroundColor: _blue.withValues(alpha: 0.10), child: Icon(step.icon, size: 18, color: _blue)),
                      if (!last) Container(width: 2, height: 24, margin: const EdgeInsets.symmetric(vertical: 4), color: const Color(0xFFE5E7EB)),
                    ],
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Padding(
                      padding: EdgeInsets.only(bottom: last ? 0 : 18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(step.title, style: const TextStyle(fontWeight: FontWeight.w900)),
                          Text(step.subtitle, style: const TextStyle(color: _muted, height: 1.35)),
                        ],
                      ),
                    ),
                  ),
                ],
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _toolList(BuildContext context) {
    final tools = [
      _Tool(Icons.edit_note_outlined, '习题生成与讲解', '按当前知识点生成练习，做完看解析。', _teal, const ExercisePage()),
      _Tool(Icons.quiz_outlined, '测评考试', '生成单元测试或模拟卷。', _purple, const ExamPage()),
      _Tool(Icons.smart_display_outlined, '微课讲解', '把知识点变成短讲稿和课件大纲。', _amber, const MicroLessonPage()),
    ];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('更多工具', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
            const SizedBox(height: 10),
            ...tools.map(
              (tool) => ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(color: tool.color.withValues(alpha: 0.10), borderRadius: BorderRadius.circular(12)),
                  child: Icon(tool.icon, color: tool.color),
                ),
                title: Text(tool.title, style: const TextStyle(fontWeight: FontWeight.w900)),
                subtitle: Text(tool.subtitle),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _open(context, tool.page),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _open(BuildContext context, Widget page) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => page));
  }
}

class _ActionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final VoidCallback onTap;

  const _ActionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: const Color(0xFFE5E7EB)),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(height: 16),
            Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
            const SizedBox(height: 2),
            Text(subtitle, style: const TextStyle(color: HomePage._muted, fontSize: 12)),
          ],
        ),
      ),
    );
  }
}

class _FlowStep {
  final IconData icon;
  final String title;
  final String subtitle;

  const _FlowStep(this.icon, this.title, this.subtitle);
}

class _Tool {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final Widget page;

  const _Tool(this.icon, this.title, this.subtitle, this.color, this.page);
}
