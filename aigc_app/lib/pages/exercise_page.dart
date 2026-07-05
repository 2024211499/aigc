import 'package:flutter/material.dart';

import '../models/exercise.dart';
import '../services/api_service.dart';

class ExercisePage extends StatefulWidget {
  final String? courseId;
  final String? chapterId;
  final String? knowledgePoint;
  final String? title;
  final String? difficulty;

  const ExercisePage({
    super.key,
    this.courseId,
    this.chapterId,
    this.knowledgePoint,
    this.title,
    this.difficulty,
  });

  @override
  State<ExercisePage> createState() => _ExercisePageState();
}

class _ExercisePageState extends State<ExercisePage>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  final _api = ApiService();
  final Map<String, _SubmitResult> _results = {};
  final Set<String> _submittingIds = {};

  List<Exercise> _exercises = [];
  List<Mistake> _mistakes = [];
  bool _isLoading = true;
  String? _notice;

  static const _bg = Color(0xFFFAF7F1);
  static const _card = Color(0xFFFFFCF7);
  static const _ink = Color(0xFF34324A);
  static const _muted = Color(0xFF78758A);
  static const _blue = Color(0xFF4F6D7A);
  static const _teal = Color(0xFF7AA7A3);
  static const _amber = Color(0xFFD97706);
  static const _red = Color(0xFFDC2626);

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
      String? courseId = widget.courseId;
      if (courseId == null || courseId.isEmpty) {
        final courses = await _api.getCourses();
        final parsed =
            courses.where((course) => (course.chapterCount ?? 0) > 0).toList();
        courseId =
            courses.isEmpty
                ? null
                : (parsed.isNotEmpty ? parsed.first.id : courses.first.id);
      }

      if (courseId != null && courseId.isNotEmpty) {
        final data = await _api.generateExercises(
          courseId: courseId,
          chapterId: widget.chapterId ?? '',
          knowledgePoint: widget.knowledgePoint ?? '',
          difficulty: widget.difficulty ?? 'medium',
          count: 3,
          fastMode: true,
        );
        _exercises = _parseExercises(data);
      }

      _mistakes = await _api.getMistakes();
      if (_exercises.isEmpty) {
        _notice = '暂时没有拿到可用题目，先给出当前小节的本地练习框架。';
        _exercises = _localExercises();
      }
    } catch (_) {
      _notice = '题目生成暂时不可用，已先给出当前小节的本地练习框架。';
      _exercises = _localExercises();
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  List<Exercise> _parseExercises(Map<String, dynamic> data) {
    final payload = data['exercises'] ?? data['questions'] ?? data['result'];
    final questions =
        payload is Map
            ? (payload['questions'] ?? payload['exercises'] ?? payload['items'])
            : payload;
    if (questions is! List) return [];
    return questions
        .whereType<Map>()
        .map((item) => Exercise.fromJson(item.cast<String, dynamic>()))
        .where((exercise) => exercise.question.trim().isNotEmpty)
        .toList();
  }

  List<Exercise> _localExercises() {
    final point =
        (widget.knowledgePoint?.trim().isNotEmpty ?? false)
            ? widget.knowledgePoint!.trim()
            : (widget.title ?? '当前小节');
    final difficulty = widget.difficulty ?? 'medium';
    return [
      Exercise(
        id: 'local-1',
        type: '概念题',
        question: '用自己的话解释“$point”，并写出它适用的条件。',
        date: '当前小节',
        difficulty: difficulty,
        answer: '围绕定义、适用条件、关键公式或典型场景回答即可。',
        explanation: '这道题用于确认你不是只记住名称，而是真的理解它在本节中的作用。',
        mistakeTip: '不要只背关键词，要写出条件和用途。',
      ),
      Exercise(
        id: 'local-2',
        type: '应用题',
        question: '结合本节资料，举一个需要用到“$point”的典型题型或场景。',
        date: '当前小节',
        difficulty: difficulty,
        answer: '答案应来自当前资料片段，并能说明为什么要用这个知识点。',
        explanation: '应用题主要训练知识迁移，避免练习和章节脱节。',
        mistakeTip: '不要跳到其他学科或无关知识点。',
      ),
      Exercise(
        id: 'local-3',
        type: '易错题',
        question: '学习“$point”时最容易忽略哪个条件？请写出原因。',
        date: '当前小节',
        difficulty: difficulty,
        answer: '写出一个限制条件、适用范围或常见误区，并解释原因。',
        explanation: '这会进入后续复盘逻辑，用来帮助错题本积累高价值错误。',
        mistakeTip: '不要只写“不会”，要具体到条件、公式或步骤。',
      ),
    ];
  }

  Future<void> _submitExercise(Exercise exercise, String answer) async {
    final trimmed = answer.trim();
    if (trimmed.isEmpty) {
      _showSnack('先写下你的答案。');
      return;
    }

    if (exercise.id.startsWith('local-')) {
      setState(() {
        _results[exercise.id] = _SubmitResult(
          isCorrect: false,
          answer: exercise.answer ?? '',
          explanation: exercise.explanation ?? '',
          mistakeTip: exercise.mistakeTip ?? '',
          addedToMistakes: false,
        );
      });
      return;
    }

    setState(() => _submittingIds.add(exercise.id));
    try {
      final data = await _api.submitAnswer(
        exerciseId: exercise.id,
        studentAnswer: trimmed,
      );
      final result = _SubmitResult.fromJson(data);
      setState(() => _results[exercise.id] = result);
      if (result.addedToMistakes) {
        _mistakes = await _api.getMistakes();
        _showSnack('已加入错题本，复盘时会再次练。');
      }
    } catch (e) {
      _showSnack('提交失败：$e');
    } finally {
      if (mounted) setState(() => _submittingIds.remove(exercise.id));
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        title: Text(widget.title ?? '练习与错题'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [Tab(text: '每日练习'), Tab(text: '错题本')],
        ),
      ),
      body:
          _isLoading
              ? const Center(child: CircularProgressIndicator())
              : TabBarView(
                controller: _tabController,
                children: [_buildExerciseList(), _buildMistakeList()],
              ),
    );
  }

  Widget _buildExerciseList() {
    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 28),
        children: [
          const _PageIntro(
            icon: Icons.edit_note_outlined,
            title: '练习用来巩固当前小节',
            subtitle: '题目优先根据当前章节、知识点和学习画像生成；提交后会返回答案、解析和错因。',
            color: _blue,
          ),
          if (_notice != null) ...[
            const SizedBox(height: 12),
            _InfoBox(text: _notice!, color: _amber),
          ],
          const SizedBox(height: 12),
          ..._exercises.map(
            (exercise) => _ExerciseTile(
              exercise: exercise,
              result: _results[exercise.id],
              isSubmitting: _submittingIds.contains(exercise.id),
              onSubmit: (answer) => _submitExercise(exercise, answer),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMistakeList() {
    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 28),
        children: [
          const _PageIntro(
            icon: Icons.error_outline,
            title: '错题本负责复盘',
            subtitle: '真实题目提交后，如果答案错误，会记录题干、错因和复习次数，供后续画像和复盘使用。',
            color: _red,
          ),
          const SizedBox(height: 12),
          if (_mistakes.isEmpty)
            const _EmptyState(text: '还没有错题。完成练习并提交后，错误记录会出现在这里。')
          else
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
      color: _ExercisePageState._card,
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
                  Text(
                    title,
                    style: const TextStyle(
                      color: _ExercisePageState._ink,
                      fontSize: 17,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      color: _ExercisePageState._muted,
                      height: 1.45,
                    ),
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

class _ExerciseTile extends StatefulWidget {
  final Exercise exercise;
  final _SubmitResult? result;
  final bool isSubmitting;
  final ValueChanged<String> onSubmit;

  const _ExerciseTile({
    required this.exercise,
    required this.result,
    required this.isSubmitting,
    required this.onSubmit,
  });

  @override
  State<_ExerciseTile> createState() => _ExerciseTileState();
}

class _ExerciseTileState extends State<_ExerciseTile> {
  late final TextEditingController _controller;
  String? _selectedOption;

  Exercise get exercise => widget.exercise;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final result = widget.result;
    return Card(
      color: _ExercisePageState._card,
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _Badge(
                  text: exercise.type.isEmpty ? '练习题' : exercise.type,
                  color: _ExercisePageState._blue,
                ),
                if (exercise.difficulty != null)
                  _Badge(
                    text: _difficultyLabel(exercise.difficulty!),
                    color: _ExercisePageState._teal,
                  ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              exercise.question,
              style: const TextStyle(
                color: _ExercisePageState._ink,
                fontWeight: FontWeight.w900,
                height: 1.5,
              ),
            ),
            if (exercise.options != null && exercise.options!.isNotEmpty) ...[
              const SizedBox(height: 10),
              ...exercise.options!.map(
                (option) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: ChoiceChip(
                    label: Align(
                      alignment: Alignment.centerLeft,
                      child: Text(option),
                    ),
                    selected: _selectedOption == option,
                    onSelected:
                        result == null
                            ? (_) {
                              setState(() {
                                _selectedOption = option;
                                _controller.text = option;
                              });
                            }
                            : null,
                  ),
                ),
              ),
            ],
            const SizedBox(height: 12),
            TextField(
              controller: _controller,
              enabled: result == null && !widget.isSubmitting,
              minLines: 1,
              maxLines: 3,
              decoration: const InputDecoration(
                hintText: '写下你的答案...',
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed:
                    result != null || widget.isSubmitting
                        ? null
                        : () => widget.onSubmit(_controller.text),
                icon:
                    widget.isSubmitting
                        ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                        : const Icon(Icons.check),
                label: Text(widget.isSubmitting ? '提交中' : '提交答案'),
              ),
            ),
            if (result != null) ...[
              const SizedBox(height: 12),
              _ResultBox(result: result),
            ],
          ],
        ),
      ),
    );
  }

  String _difficultyLabel(String difficulty) {
    return switch (difficulty) {
      'easy' => '基础',
      'hard' => '挑战',
      _ => '适中',
    };
  }
}

class _ResultBox extends StatelessWidget {
  final _SubmitResult result;

  const _ResultBox({required this.result});

  @override
  Widget build(BuildContext context) {
    final color =
        result.isCorrect ? _ExercisePageState._teal : _ExercisePageState._red;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.20)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                result.isCorrect
                    ? Icons.check_circle_outline
                    : Icons.error_outline,
                color: color,
                size: 18,
              ),
              const SizedBox(width: 6),
              Text(
                result.isCorrect ? '答对了' : '需要复盘',
                style: TextStyle(color: color, fontWeight: FontWeight.w900),
              ),
              if (result.addedToMistakes) ...[
                const SizedBox(width: 8),
                const _Badge(text: '已进错题本', color: _ExercisePageState._amber),
              ],
            ],
          ),
          const SizedBox(height: 8),
          Text('参考答案：${result.answer}', style: const TextStyle(height: 1.45)),
          if (result.explanation.trim().isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(result.explanation, style: const TextStyle(height: 1.45)),
          ],
          if (result.mistakeTip.trim().isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              '易错提醒：${result.mistakeTip}',
              style: const TextStyle(
                color: _ExercisePageState._muted,
                height: 1.45,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _SubmitResult {
  final bool isCorrect;
  final String answer;
  final String explanation;
  final String mistakeTip;
  final bool addedToMistakes;

  const _SubmitResult({
    required this.isCorrect,
    required this.answer,
    required this.explanation,
    required this.addedToMistakes,
    this.mistakeTip = '',
  });

  factory _SubmitResult.fromJson(Map<String, dynamic> json) {
    return _SubmitResult(
      isCorrect: json['is_correct'] == true,
      answer: json['answer']?.toString() ?? '',
      explanation: json['explanation']?.toString() ?? '',
      mistakeTip: json['mistake_tip']?.toString() ?? '',
      addedToMistakes: json['added_to_mistakes'] == true,
    );
  }
}

class _MistakeTile extends StatelessWidget {
  final Mistake mistake;

  const _MistakeTile({required this.mistake});

  @override
  Widget build(BuildContext context) {
    return Card(
      color: _ExercisePageState._card,
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
          child: const Icon(
            Icons.error_outline,
            color: _ExercisePageState._red,
          ),
        ),
        title: Text(
          mistake.stem,
          style: const TextStyle(
            color: _ExercisePageState._ink,
            fontWeight: FontWeight.w800,
          ),
        ),
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
        style: TextStyle(
          color: color,
          fontSize: 11.5,
          fontWeight: FontWeight.w800,
        ),
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

class _EmptyState extends StatelessWidget {
  final String text;

  const _EmptyState({required this.text});

  @override
  Widget build(BuildContext context) {
    return Card(
      color: _ExercisePageState._card,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Text(
          text,
          style: const TextStyle(color: _ExercisePageState._muted, height: 1.5),
        ),
      ),
    );
  }
}
