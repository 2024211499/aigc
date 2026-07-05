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

  static const _blue = Color(0xFF2563EB);
  static const _teal = Color(0xFF0F766E);
  static const _purple = Color(0xFF7C3AED);
  static const _amber = Color(0xFFD97706);
  static const _red = Color(0xFFDC2626);
  static const _muted = Color(0xFF6B7280);

  final _radar = const {
    '概念理解': 78.0,
    '解题步骤': 66.0,
    '公式应用': 72.0,
    '错题复盘': 58.0,
    '材料阅读': 80.0,
  };

  final _weakPoints = const [
    _WeakPoint('数据结构：树的遍历', 35, _red),
    _WeakPoint('电磁学：安培力方向判断', 55, _amber),
    _WeakPoint('热学：理想气体方程应用', 60, _blue),
  ];

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
    try {
      await _api.getProfile('anonymous');
    } catch (_) {
      _notice = '画像接口暂未返回有效数据，当前展示示例学习画像。';
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
              child: const Icon(Icons.account_circle_outlined, color: _blue, size: 30),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('学习画像', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                  SizedBox(height: 4),
                  Text(
                    '汇总你的课程、练习、错题和答疑记录，给出下一步学习建议。',
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
    final stats = const [
      _StatItem('掌握度', '72%', Icons.trending_up, _teal),
      _StatItem('错题', '18', Icons.error_outline, _red),
      _StatItem('本周学习', '5 天', Icons.calendar_month_outlined, _blue),
    ];
    return Row(
      children: stats
          .map(
            (item) => Expanded(
              child: Card(
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
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
                      ),
                      const SizedBox(height: 2),
                      Text(item.label, style: const TextStyle(fontSize: 12, color: _muted)),
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
    final labels = _radar.keys.toList();
    final values = _radar.values.map((value) => value / 100).toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('能力分布', style: TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            SizedBox(
              height: 250,
              child: RadarChart(
                RadarChartData(
                  radarShape: RadarShape.polygon,
                  tickCount: 4,
                  ticksTextStyle: const TextStyle(color: Colors.transparent, fontSize: 0),
                  gridBorderData: const BorderSide(color: Color(0xFFE5E7EB)),
                  borderData: FlBorderData(show: false),
                  radarBorderData: const BorderSide(color: Color(0xFFE5E7EB)),
                  getTitle: (index, angle) {
                    return RadarChartTitle(
                      text: labels[index],
                      angle: angle,
                    );
                  },
                  titleTextStyle: const TextStyle(fontSize: 11, color: _muted),
                  dataSets: [
                    RadarDataSet(
                      dataEntries: values.map((value) => RadarEntry(value: value)).toList(),
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
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('优先补强', style: TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            ..._weakPoints.map((point) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(point.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                        ),
                        Text(
                          '${point.mastery}%',
                          style: TextStyle(color: point.color, fontWeight: FontWeight.w800),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    LinearProgressIndicator(
                      value: point.mastery / 100,
                      minHeight: 6,
                      color: point.color,
                      backgroundColor: const Color(0xFFF3F4F6),
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
    final tasks = const [
      '今天先复盘 3 道高频错题，写清楚错因。',
      '针对最弱知识点生成 5 道基础题。',
      '把不懂的步骤用快速答疑追问到能复述。',
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('今日建议', style: TextStyle(fontWeight: FontWeight.w800)),
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
                              fontWeight: FontWeight.w800,
                            ),
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
      ),
    );
  }

  Widget _buildToolGrid() {
    final tools = [
      _ToolItem(Icons.flash_on_outlined, '快速答疑', '临时问题马上问', _blue, const QuickAnswerPage()),
      _ToolItem(Icons.edit_note_outlined, '题库练习', '生成练习和错题', _teal, const ExercisePage()),
      _ToolItem(Icons.quiz_outlined, '智能组卷', '按目标生成试卷', _purple, const ExamPage()),
      _ToolItem(Icons.smart_display_outlined, '微课课件', '生成短讲稿大纲', _amber, const MicroLessonPage()),
    ];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('学习工具', style: TextStyle(fontWeight: FontWeight.w800)),
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
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => tool.page),
                  ),
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      border: Border.all(color: const Color(0xFFE5E7EB)),
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
                              Text(tool.title,
                                  style: const TextStyle(fontWeight: FontWeight.w800)),
                              const SizedBox(height: 2),
                              Text(
                                tool.subtitle,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 11.5, color: _muted),
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
