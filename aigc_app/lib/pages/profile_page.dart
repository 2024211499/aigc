import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../services/api_service.dart';
import 'exam_page.dart';
import 'exercise_page.dart';
import 'microlesson_page.dart';
import 'quick_answer_page.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  final _api = ApiService();
  bool _isLoading = true;
  String? _notice;
  _ProfileViewData _data = _ProfileViewData.empty();

  static const _blue = Color(0xFF4F6D7A);
  static const _teal = Color(0xFF7AA7A3);
  static const _purple = Color(0xFF6D5A8D);
  static const _amber = Color(0xFFD97706);
  static const _red = Color(0xFFDC2626);
  static const _muted = Color(0xFF78758A);
  static const _card = Color(0xFFFFFCF7);
  static const _ink = Color(0xFF34324A);

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  @override
  void dispose() {
    _api.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _notice = null;
    });
    try {
      final response = await _api.getProfile('anonymous');
      _data = _ProfileViewData.fromApi(response);
      if (_data.totalAnswers == 0) {
        _notice = '还没有练习记录。完成并提交几道题后，画像会自动更新。';
      }
    } catch (_) {
      _notice = '画像接口暂时不可用，当前显示空画像。';
      _data = _ProfileViewData.empty();
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          _buildHeader(),
          if (_notice != null) ...[
            const SizedBox(height: 12),
            _InfoBox(text: _notice!, color: _amber),
          ],
          const SizedBox(height: 12),
          _buildStats(),
          const SizedBox(height: 12),
          _buildRadarCard(),
          const SizedBox(height: 12),
          _buildWeakPoints(),
          const SizedBox(height: 12),
          _buildReviewPlan(),
          const SizedBox(height: 12),
          _buildToolGrid(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Card(
      color: _card,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: _blue.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(
                Icons.account_circle_outlined,
                color: _blue,
                size: 30,
              ),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '学习画像',
                    style: TextStyle(
                      color: _ink,
                      fontSize: 18,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    '根据练习、错题和学习行为生成，不再展示固定样例。',
                    style: TextStyle(color: _muted, height: 1.45),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStats() {
    final stats = [
      _StatItem(
        '正确率',
        '${_data.accuracyRate.toStringAsFixed(1)}%',
        Icons.trending_up,
        _teal,
      ),
      _StatItem(
        '答题数',
        '${_data.totalAnswers}',
        Icons.edit_note_outlined,
        _blue,
      ),
      _StatItem('错题', '${_data.mistakeCount}', Icons.error_outline, _red),
    ];
    return Row(
      children:
          stats
              .map(
                (item) => Expanded(
                  child: Card(
                    color: _card,
                    margin: EdgeInsets.only(right: item == stats.last ? 0 : 8),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(item.icon, color: item.color, size: 22),
                          const SizedBox(height: 10),
                          Text(
                            item.value,
                            style: const TextStyle(
                              color: _ink,
                              fontSize: 20,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            item.label,
                            style: const TextStyle(fontSize: 12, color: _muted),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              )
              .toList(),
    );
  }

  Widget _buildRadarCard() {
    final labels = _data.radar.keys.toList();
    final values = _data.radar.values.map((value) => value / 100).toList();
    return Card(
      color: _card,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '能力分布',
              style: TextStyle(color: _ink, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 250,
              child: RadarChart(
                RadarChartData(
                  radarShape: RadarShape.polygon,
                  tickCount: 4,
                  ticksTextStyle: const TextStyle(
                    color: Colors.transparent,
                    fontSize: 0,
                  ),
                  gridBorderData: const BorderSide(color: Color(0xFFE5E1D8)),
                  borderData: FlBorderData(show: false),
                  radarBorderData: const BorderSide(color: Color(0xFFE5E1D8)),
                  getTitle:
                      (index, angle) =>
                          RadarChartTitle(text: labels[index], angle: angle),
                  titleTextStyle: const TextStyle(fontSize: 11, color: _muted),
                  dataSets: [
                    RadarDataSet(
                      dataEntries:
                          values
                              .map((value) => RadarEntry(value: value))
                              .toList(),
                      fillColor: _blue.withValues(alpha: 0.14),
                      borderColor: _blue,
                      borderWidth: 2,
                      entryRadius: 2,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWeakPoints() {
    return Card(
      color: _card,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '优先补强',
              style: TextStyle(color: _ink, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 12),
            if (_data.weakPoints.isEmpty)
              const Text(
                '暂无明确薄弱点。先完成几道当前课程练习，系统会根据错题自动生成。',
                style: TextStyle(color: _muted, height: 1.5),
              )
            else
              ..._data.weakPoints.map((point) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              point.name,
                              style: const TextStyle(
                                color: _ink,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          Text(
                            '${point.mastery}%',
                            style: TextStyle(
                              color: point.color,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      LinearProgressIndicator(
                        value: point.mastery / 100,
                        minHeight: 6,
                        color: point.color,
                        backgroundColor: const Color(0xFFF0EDE6),
                        borderRadius: BorderRadius.circular(999),
                      ),
                    ],
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }

  Widget _buildReviewPlan() {
    final tasks =
        _data.recommendations.isEmpty
            ? const [
              '先完成当前小节练习，提交后系统会沉淀错题。',
              '错题出现后，优先看错因，再做同知识点补强。',
              '用“问当前内容”追问不懂的概念或公式。',
            ]
            : _data.recommendations.take(4).toList();
    return Card(
      color: _card,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '今日建议',
              style: TextStyle(color: _ink, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 10),
            ...tasks.asMap().entries.map(
              (entry) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 22,
                      height: 22,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: _teal.withValues(alpha: 0.10),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        '${entry.key + 1}',
                        style: const TextStyle(
                          color: _teal,
                          fontSize: 12,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    const SizedBox(width: 9),
                    Expanded(
                      child: Text(
                        entry.value,
                        style: const TextStyle(color: _ink, height: 1.45),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildToolGrid() {
    final tools = [
      _ToolItem(
        Icons.flash_on_outlined,
        '快速答疑',
        '临时问题马上问',
        _blue,
        const QuickAnswerPage(),
      ),
      _ToolItem(
        Icons.edit_note_outlined,
        '题库练习',
        '生成练习和错题',
        _teal,
        const ExercisePage(),
      ),
      _ToolItem(
        Icons.quiz_outlined,
        '智能组卷',
        '按目标生成试卷',
        _purple,
        const ExamPage(),
      ),
      _ToolItem(
        Icons.smart_display_outlined,
        '微课课件',
        '生成短讲稿大纲',
        _amber,
        const MicroLessonPage(),
      ),
    ];

    return Card(
      color: _card,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '学习工具',
              style: TextStyle(color: _ink, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 12),
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: tools.length,
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                mainAxisExtent: 92,
                crossAxisSpacing: 8,
                mainAxisSpacing: 8,
              ),
              itemBuilder: (_, index) {
                final tool = tools[index];
                return InkWell(
                  borderRadius: BorderRadius.circular(8),
                  onTap:
                      () => Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => tool.page),
                      ),
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      border: Border.all(color: const Color(0xFFE5DED2)),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 36,
                          height: 36,
                          decoration: BoxDecoration(
                            color: tool.color.withValues(alpha: 0.10),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Icon(tool.icon, color: tool.color, size: 21),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                tool.title,
                                style: const TextStyle(
                                  color: _ink,
                                  fontWeight: FontWeight.w900,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                tool.subtitle,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 11.5,
                                  color: _muted,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _ProfileViewData {
  final int totalAnswers;
  final int mistakeCount;
  final double accuracyRate;
  final Map<String, double> radar;
  final List<_WeakPoint> weakPoints;
  final List<String> recommendations;

  const _ProfileViewData({
    required this.totalAnswers,
    required this.mistakeCount,
    required this.accuracyRate,
    required this.radar,
    required this.weakPoints,
    required this.recommendations,
  });

  factory _ProfileViewData.empty() {
    return const _ProfileViewData(
      totalAnswers: 0,
      mistakeCount: 0,
      accuracyRate: 0,
      radar: {'概念理解': 30, '解题步骤': 30, '公式应用': 30, '错题复盘': 30, '材料阅读': 30},
      weakPoints: [],
      recommendations: [],
    );
  }

  factory _ProfileViewData.fromApi(Map<String, dynamic> response) {
    final profile = _asMap(response['profile']);
    final stats = _asMap(response['stats']);
    final totalAnswers = _asInt(stats['total_answers']);
    final mistakeCount = _asInt(stats['mistake_count']);
    final accuracy = _asDouble(stats['accuracy_rate']);
    final weak = _weakPointsFrom(profile, stats);
    final recommendations = _stringList(profile['recommendations']);
    return _ProfileViewData(
      totalAnswers: totalAnswers,
      mistakeCount: mistakeCount,
      accuracyRate: accuracy,
      radar: {
        '概念理解': _clampScore(accuracy),
        '解题步骤': _clampScore(100 - mistakeCount * 8),
        '公式应用': _clampScore(accuracy - mistakeCount * 3 + 15),
        '错题复盘': _clampScore(_asInt(stats['mastered_count']) * 20.0),
        '材料阅读': _clampScore(totalAnswers > 0 ? 65 : 30),
      },
      weakPoints: weak,
      recommendations: recommendations,
    );
  }

  static Map<String, dynamic> _asMap(Object? value) {
    return value is Map ? value.cast<String, dynamic>() : <String, dynamic>{};
  }

  static int _asInt(Object? value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    return int.tryParse(value?.toString() ?? '') ?? 0;
  }

  static double _asDouble(Object? value) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '') ?? 0;
  }

  static double _clampScore(double value) => value.clamp(0, 100).toDouble();

  static List<String> _stringList(Object? value) {
    if (value is List) {
      return value
          .map((item) => item.toString())
          .where((s) => s.isNotEmpty)
          .toList();
    }
    return [];
  }

  static List<_WeakPoint> _weakPointsFrom(
    Map<String, dynamic> profile,
    Map<String, dynamic> stats,
  ) {
    final fromAgent = _stringList(profile['weak_points']);
    if (fromAgent.isNotEmpty) {
      return fromAgent
          .take(5)
          .map((name) => _WeakPoint(name, 45, _ProfilePageState._amber))
          .toList();
    }
    final dist = _asMap(stats['error_type_distribution']);
    return dist.entries.take(5).map((entry) {
      final count = _asInt(entry.value);
      final mastery = (70 - count * 12).clamp(15, 75);
      final color =
          mastery < 40 ? _ProfilePageState._red : _ProfilePageState._amber;
      return _WeakPoint(entry.key, mastery, color);
    }).toList();
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
      child: Row(
        children: [
          Icon(Icons.info_outline, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: TextStyle(color: color))),
        ],
      ),
    );
  }
}

class _WeakPoint {
  final String name;
  final int mastery;
  final Color color;

  const _WeakPoint(this.name, this.mastery, this.color);
}

class _StatItem {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _StatItem(this.label, this.value, this.icon, this.color);
}

class _ToolItem {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final Widget page;

  const _ToolItem(this.icon, this.title, this.subtitle, this.color, this.page);
}
