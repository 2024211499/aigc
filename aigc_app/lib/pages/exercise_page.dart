import 'package:flutter/material.dart';

import '../models/exercise.dart';
import '../services/api_service.dart';

class ExercisePage extends StatefulWidget {
  const ExercisePage({super.key});

  @override
  State<ExercisePage> createState() => _ExercisePageState();
}

class _ExercisePageState extends State<ExercisePage> with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  final _api = ApiService();
  List<Exercise> _exercises = [];
  List<Mistake> _mistakes = [];
  bool _isLoading = true;
  String? _notice;

  static const _blue = Color(0xFF2563EB);
  static const _teal = Color(0xFF0F766E);
  static const _amber = Color(0xFFD97706);
  static const _red = Color(0xFFDC2626);
  static const _muted = Color(0xFF6B7280);

  final _demoExercises = const [
    Exercise(id: 'demo-1', type: '单选题', question: '下列哪一种遍历方式不属于二叉树的深度优先遍历？', date: '今日推荐'),
    Exercise(id: 'demo-2', type: '计算题', question: '质量为 2kg 的物体在 10N 水平拉力下运动，求 3s 后速度。', date: '今日推荐'),
    Exercise(id: 'demo-3', type: '填空题', question: '理想气体状态方程中，温度需要使用____作为单位。', date: '今日推荐'),
  ];

  final _demoMistakes = const [
    Mistake(id: 'm1', stem: '二叉树中序遍历输出顺序理解错误。', errorType: '概念混淆', createdAt: '2026-05-10'),
    Mistake(id: 'm2', stem: '受力分析漏掉斜面对物体的支持力分量。', errorType: '步骤遗漏', createdAt: '2026-05-09'),
    Mistake(id: 'm3', stem: '理想气体方程中温度没有换算为开尔文。', errorType: '单位换算', createdAt: '2026-05-08'),
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _api.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _notice = null;
    });
    try {
      final courses = await _api.getCourses();
      if (courses.isNotEmpty) {
        final data = await _api.generateExercises(courseId: courses.first.id, count: 5);
        final payload = data['exercises'] ?? data['questions'] ?? data['result'];
        final questions = payload is Map ? payload['questions'] : payload;
        if (questions is List) {
          _exercises = questions
              .whereType<Map>()
              .map((item) => Exercise.fromJson(item.cast<String, dynamic>()))
              .toList();
        }
      }
      _mistakes = await _api.getMistakes();
      if (_exercises.isEmpty) _exercises = _demoExercises;
      if (_mistakes.isEmpty) _mistakes = _demoMistakes;
    } catch (_) {
      _notice = '题库接口暂不可用，当前展示示例练习和错题。';
      _exercises = _demoExercises;
      _mistakes = _demoMistakes;
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('题库与错题'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: '每日练习'),
            Tab(text: '错题本'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildExerciseList(),
                _buildMistakeList(),
              ],
            ),
    );
  }

  Widget _buildExerciseList() {
    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          const _PageIntro(
            icon: Icons.edit_note_outlined,
            title: '练习用来巩固课程',
            subtitle: '系统会优先根据当前课程生成题目，后续可接入难度、题型和知识点筛选。',
            color: _blue,
          ),
          if (_notice != null) ...[
            const SizedBox(height: 12),
            _InfoBox(text: _notice!, color: _amber),
          ],
          const SizedBox(height: 12),
          ..._exercises.map((exercise) => _ExerciseTile(exercise: exercise)),
        ],
      ),
    );
  }

  Widget _buildMistakeList() {
    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          const _PageIntro(
            icon: Icons.error_outline,
            title: '错题本负责复盘',
            subtitle: '每道错题应该沉淀错因、涉及知识点和下一次复习动作。',
            color: _red,
          ),
          const SizedBox(height: 12),
          ..._mistakes.map((mistake) => _MistakeTile(mistake: mistake)),
        ],
      ),
    );
  }
}

class _PageIntro extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;

  const _PageIntro({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
  });

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
                color: color.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: color),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 5),
                  Text(subtitle, style: const TextStyle(color: _ExercisePageState._muted, height: 1.45)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ExerciseTile extends StatelessWidget {
  final Exercise exercise;

  const _ExerciseTile({required this.exercise});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _Badge(text: exercise.type.isEmpty ? '练习题' : exercise.type, color: _ExercisePageState._blue),
                if (exercise.difficulty != null) ...[
                  const SizedBox(width: 8),
                  _Badge(text: exercise.difficulty!, color: _ExercisePageState._teal),
                ],
              ],
            ),
            const SizedBox(height: 10),
            Text(exercise.question, style: const TextStyle(fontWeight: FontWeight.w800, height: 1.45)),
            if (exercise.options != null && exercise.options!.isNotEmpty) ...[
              const SizedBox(height: 10),
              ...exercise.options!.map(
                (option) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(option, style: const TextStyle(color: _ExercisePageState._muted)),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _MistakeTile extends StatelessWidget {
  final Mistake mistake;

  const _MistakeTile({required this.mistake});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        minVerticalPadding: 14,
        leading: Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            color: _ExercisePageState._red.withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(8),
          ),
          child: const Icon(Icons.error_outline, color: _ExercisePageState._red),
        ),
        title: Text(mistake.stem, style: const TextStyle(fontWeight: FontWeight.w800)),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text(
            mistake.errorType.isEmpty ? '待诊断错因' : mistake.errorType,
            style: const TextStyle(color: _ExercisePageState._muted),
          ),
        ),
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String text;
  final Color color;

  const _Badge({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontSize: 11.5, fontWeight: FontWeight.w800),
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
