import 'package:flutter/material.dart';

import '../models/course.dart';
import '../models/chapter.dart';
import '../services/api_service.dart';
import 'learning_page.dart';
import 'library_page.dart';

class CourseModePage extends StatefulWidget {
  final VoidCallback? onCourseChanged;

  const CourseModePage({super.key, this.onCourseChanged});

  @override
  State<CourseModePage> createState() => _CourseModePageState();
}

class _CourseModePageState extends State<CourseModePage> {
  final _api = ApiService();

  List<Course> _courses = [];
  String? _selectedCourseId;
  bool _isLoadingCourses = true;
  bool _isGenerating = false;
  bool _showPlan = false;
  String? _notice;
  String? _planId;
  List<_PlanTask> _plan = [];

  String _foundation = '了解基本概念，但不熟练';
  String _goal = '系统掌握，能做题也能讲清楚';
  String _pace = '每天 45 分钟';

  static const _bg = Color(0xFFFAF7F1);
  static const _card = Color(0xFFFFFCF7);
  static const _ink = Color(0xFF34324A);
  static const _muted = Color(0xFF7C7A8A);
  static const _blue = Color(0xFF536878);
  static const _teal = Color(0xFF7A9E9F);
  static const _purple = Color(0xFF7566A0);
  static const _amber = Color(0xFFD97706);
  static const _border = Color(0xFFE5DED2);

  Course? get _selectedCourse {
    if (_courses.isEmpty) return null;
    return _courses.firstWhere(
      (course) => course.id == _selectedCourseId,
      orElse: () => _courses.first,
    );
  }

  @override
  void initState() {
    super.initState();
    _loadCourses();
  }

  @override
  void dispose() {
    _api.dispose();
    super.dispose();
  }

  Future<void> _loadCourses() async {
    setState(() {
      _isLoadingCourses = true;
      _notice = null;
    });
    try {
      final courses = await _api.getCourses();
      final preferred =
          courses.where((course) => (course.chapterCount ?? 0) > 0).toList();
      setState(() {
        _courses = courses;
        _selectedCourseId =
            courses.isEmpty
                ? null
                : (preferred.isNotEmpty
                    ? preferred.first.id
                    : courses.first.id);
      });
    } catch (_) {
      setState(() => _notice = '课程资料暂时读取失败，可以先用示例流程体验。');
    } finally {
      if (mounted) setState(() => _isLoadingCourses = false);
    }
  }

  Future<void> _openMaterialLibrary() async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => LibraryPage(onChanged: widget.onCourseChanged),
      ),
    );
    await _loadCourses();
    widget.onCourseChanged?.call();
    if (!mounted) return;
    _openProfileSheet();
  }

  Future<void> _generatePlan() async {
    final course = _selectedCourse;
    if (course == null || _selectedCourseId == null) {
      setState(() => _notice = '请先上传并解析一份资料，再生成学习路径。');
      return;
    }

    setState(() {
      _isGenerating = true;
      _showPlan = false;
      _notice = null;
      _planId = null;
    });
    try {
      final chapters = await _api.getChapters(_selectedCourseId!);
      if (chapters.isEmpty) {
        setState(() {
          _notice = '这份资料还没有解析出章节。请在资料库打开解析报告，点“重新解析”后再生成学习路径。';
          _plan = [];
          _showPlan = false;
        });
        return;
      }

      final response = await _api.generateLearningPackage(
        courseId: _selectedCourseId!,
        learningGoal: _goal,
        studentLevel: _foundation,
        studyDays: 5,
        dailyMinutes:
            _pace.contains('60') ? 60 : (_pace.contains('30') ? 30 : 45),
      );
      _planId = response['plan_id']?.toString();
      _plan = _buildPlanFromChapters(chapters);
      _notice = null;
    } catch (e) {
      try {
        final chapters = await _api.getChapters(_selectedCourseId!);
        _plan = _buildPlanFromChapters(chapters);
        _notice =
            _plan.isEmpty
                ? '学习路径生成失败：资料没有可用章节。'
                : 'AI 详细讲义/练习生成暂时失败，已先根据解析章节生成可进入的学习路径。';
      } catch (_) {
        _notice = '学习路径生成失败：请确认后端服务正常，且资料已完成解析。';
        _plan = [];
      }
    } finally {
      if (mounted) {
        setState(() {
          _isGenerating = false;
          _showPlan = _plan.isNotEmpty;
        });
        widget.onCourseChanged?.call();
      }
    }
  }

  List<_PlanTask> _buildPlanFromChapters(List<Chapter> chapters) {
    final source = chapters.take(5).toList();
    if (source.isEmpty) return [];
    return source.asMap().entries.map((entry) {
      final index = entry.key;
      final chapter = entry.value;
      final type = switch (index) {
        0 => '讲义',
        1 => '图解',
        2 => '练习',
        3 => '测验',
        _ => '复盘',
      };
      final subtitle =
          chapter.intro?.trim().isNotEmpty == true
              ? chapter.intro!.trim()
              : '围绕“${chapter.title}”提炼重点、公式、例题和易错点';
      return _PlanTask(index + 1, chapter.title, subtitle, type);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
        children: [
          _hero(),
          const SizedBox(height: 12),
          _workflow(),
          const SizedBox(height: 12),
          _materialPanel(),
          if (_isGenerating) ...[
            const SizedBox(height: 12),
            const LinearProgressIndicator(minHeight: 3),
          ],
          if (_notice != null) ...[
            const SizedBox(height: 12),
            _noticeBox(_notice!),
          ],
          if (_showPlan) ...[const SizedBox(height: 12), _planPanel()],
        ],
      ),
    );
  }

  Widget _hero() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _iconBox(Icons.auto_stories_outlined, _blue),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  '课程模式',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                    color: _ink,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Text(
            '上传资料后，先采集学习基础和目标，再生成讲义、答疑、练习、测验、复盘的一条完整学习线。',
            style: TextStyle(color: _muted, height: 1.5),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: _openMaterialLibrary,
                  icon: const Icon(Icons.upload_file),
                  label: const Text('上传资料'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _courses.isEmpty ? null : _openProfileSheet,
                  icon: const Icon(Icons.psychology_outlined),
                  label: const Text('开始规划'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _workflow() {
    final active = _showPlan ? 3 : (_selectedCourse == null ? 0 : 1);
    final steps = const [
      _FlowStep(Icons.folder_open_outlined, '资料', '上传教材/课件', _blue),
      _FlowStep(Icons.person_search_outlined, '画像', '基础/目标/节奏', _teal),
      _FlowStep(Icons.route_outlined, '路径', '讲义与每日任务', _purple),
      _FlowStep(Icons.replay_circle_filled_outlined, '闭环', '练习/测验/复盘', _amber),
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
            steps.asMap().entries.map((entry) {
              final index = entry.key;
              final step = entry.value;
              final done = index < active;
              final current = index == active;
              return Expanded(
                child: Column(
                  children: [
                    CircleAvatar(
                      radius: current ? 20 : 18,
                      backgroundColor:
                          done || current
                              ? step.color
                              : const Color(0xFFEDE8DF),
                      child: Icon(
                        done ? Icons.check : step.icon,
                        color: done || current ? Colors.white : _muted,
                        size: 18,
                      ),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      step.title,
                      style: TextStyle(
                        fontWeight: FontWeight.w900,
                        color: current ? _ink : _muted,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      step.subtitle,
                      textAlign: TextAlign.center,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: _muted, fontSize: 10.5),
                    ),
                  ],
                ),
              );
            }).toList(),
      ),
    );
  }

  Widget _materialPanel() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '学习资料',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w900,
                color: _ink,
              ),
            ),
            const SizedBox(height: 12),
            if (_isLoadingCourses)
              const LinearProgressIndicator(minHeight: 3)
            else if (_selectedCourse == null)
              _emptyMaterial()
            else ...[
              _selectedMaterial(),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _openCoursePicker,
                      icon: const Icon(Icons.swap_horiz),
                      label: const Text('切换'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: _openProfileSheet,
                      icon: const Icon(Icons.tune),
                      label: const Text('采集信息'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _emptyMaterial() {
    return InkWell(
      borderRadius: BorderRadius.circular(18),
      onTap: _openMaterialLibrary,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: const Color(0xFFFFFCF7),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: _border),
        ),
        child: const Column(
          children: [
            Icon(Icons.upload_file, color: _blue, size: 34),
            SizedBox(height: 8),
            Text(
              '上传教材 / 课件 / 论文',
              style: TextStyle(fontWeight: FontWeight.w900, color: _ink),
            ),
            SizedBox(height: 4),
            Text('上传后会弹出信息采集窗口', style: TextStyle(color: _muted)),
          ],
        ),
      ),
    );
  }

  Widget _selectedMaterial() {
    final course = _selectedCourse!;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFEAF1F1),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _teal.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          _iconBox(Icons.description_outlined, _teal, size: 42),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  course.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontWeight: FontWeight.w900,
                    color: _ink,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  '用于生成章节、讲义、练习、测验和复盘任务',
                  style: TextStyle(color: _muted, fontSize: 12.5),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _planPanel() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _iconBox(Icons.check_circle_outline, _teal, size: 40),
                const SizedBox(width: 10),
                const Expanded(
                  child: Text(
                    '学习路径已生成',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w900,
                      color: _ink,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ..._plan.map(_taskTile),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed:
                  _selectedCourseId == null
                      ? null
                      : () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder:
                              (_) => LearningPage(
                                courseId: _selectedCourseId!,
                                courseName: _selectedCourse?.name ?? '学习空间',
                                planId: _planId,
                                foundation: _foundation,
                                goal: _goal,
                                pace: _pace,
                              ),
                        ),
                      ),
              icon: const Icon(Icons.play_arrow_rounded),
              label: const Text('进入学习空间'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _taskTile(_PlanTask task) {
    final isReview = task.type == '复盘';
    final color = isReview ? _amber : (task.day == 2 ? _teal : _blue);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.22)),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 17,
            backgroundColor: color,
            child: Text(
              '${task.day}',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  task.title,
                  style: const TextStyle(
                    color: _ink,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  task.subtitle,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: _muted, fontSize: 12.5),
                ),
              ],
            ),
          ),
          _pill(task.type, color),
        ],
      ),
    );
  }

  void _openProfileSheet() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (_) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return SafeArea(
              child: Padding(
                padding: EdgeInsets.fromLTRB(
                  16,
                  4,
                  16,
                  16 + MediaQuery.of(context).viewInsets.bottom,
                ),
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        '课程信息获取',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w900,
                          color: _ink,
                        ),
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        '这些信息会影响讲义深度、例题难度、练习数量和每天任务量。',
                        style: TextStyle(color: _muted, height: 1.45),
                      ),
                      const SizedBox(height: 16),
                      _choiceGroup(
                        title: '你的基础如何？',
                        value: _foundation,
                        options: const ['已经熟练掌握', '了解基本概念，但不熟练', '完全没有接触过'],
                        onChanged: (value) {
                          setState(() => _foundation = value);
                          setSheetState(() {});
                        },
                      ),
                      const SizedBox(height: 12),
                      _choiceGroup(
                        title: '这次学习目标是什么？',
                        value: _goal,
                        options: const [
                          '考试提分，优先做题',
                          '系统掌握，能做题也能讲清楚',
                          '项目应用，优先理解原理',
                        ],
                        onChanged: (value) {
                          setState(() => _goal = value);
                          setSheetState(() {});
                        },
                      ),
                      const SizedBox(height: 12),
                      _choiceGroup(
                        title: '学习节奏',
                        value: _pace,
                        options: const ['每天 30 分钟', '每天 45 分钟', '每天 60 分钟'],
                        onChanged: (value) {
                          setState(() => _pace = value);
                          setSheetState(() {});
                        },
                      ),
                      const SizedBox(height: 18),
                      FilledButton.icon(
                        onPressed: () {
                          Navigator.pop(context);
                          _generatePlan();
                        },
                        icon: const Icon(Icons.auto_awesome),
                        label: const Text('生成学习路径'),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _choiceGroup({
    required String title,
    required String value,
    required List<String> options,
    required ValueChanged<String> onChanged,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(fontWeight: FontWeight.w900, color: _ink),
        ),
        const SizedBox(height: 8),
        ...options.map(
          (option) => RadioListTile<String>(
            dense: true,
            visualDensity: VisualDensity.compact,
            contentPadding: EdgeInsets.zero,
            title: Text(option),
            value: option,
            groupValue: value,
            onChanged: (next) => onChanged(next ?? option),
          ),
        ),
      ],
    );
  }

  void _openCoursePicker() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (_) {
        return SafeArea(
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
            children: [
              const Padding(
                padding: EdgeInsets.only(left: 4, bottom: 10),
                child: Text(
                  '选择学习资料',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                    color: _ink,
                  ),
                ),
              ),
              ..._courses.map(
                (course) => ListTile(
                  leading: const Icon(Icons.description_outlined, color: _blue),
                  title: Text(
                    course.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing:
                      course.id == _selectedCourseId
                          ? const Icon(Icons.check_circle, color: _teal)
                          : null,
                  onTap: () {
                    setState(() => _selectedCourseId = course.id);
                    Navigator.pop(context);
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _noticeBox(String text) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: _amber.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _amber.withValues(alpha: 0.25)),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline, color: _amber, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(color: _amber))),
        ],
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

  Widget _pill(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
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

class _FlowStep {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;

  const _FlowStep(this.icon, this.title, this.subtitle, this.color);
}

class _PlanTask {
  final int day;
  final String title;
  final String subtitle;
  final String type;

  const _PlanTask(this.day, this.title, this.subtitle, this.type);
}
