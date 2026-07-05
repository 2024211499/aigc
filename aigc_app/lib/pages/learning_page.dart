import 'package:flutter/material.dart';

import '../services/api_service.dart';
import 'exercise_page.dart';
import 'quick_answer_page.dart';

class LearningPage extends StatefulWidget {
  const LearningPage({super.key});

  @override
  State<LearningPage> createState() => _LearningPageState();
}

class _LearningPageState extends State<LearningPage> {
  final _api = ApiService();
  final _questionController = TextEditingController();

  int _activeIndex = 1;
  bool _isAsking = false;
  _InlineAnswer? _answer;

  static const _bg = Color(0xFFFAF7F1);
  static const _card = Color(0xFFFFFCF7);
  static const _ink = Color(0xFF34324A);
  static const _muted = Color(0xFF7C7A8A);
  static const _blue = Color(0xFF536878);
  static const _teal = Color(0xFF7A9E9F);
  static const _purple = Color(0xFF7566A0);
  static const _border = Color(0xFFE5DED2);

  final List<_LessonUnit> _units = const [
    _LessonUnit(day: 1, title: '先导补足：信号传输延迟与反馈回路', shortTitle: '信号延迟', type: '讲义', summary: '补齐学习锁存器前需要的基础直觉。'),
    _LessonUnit(day: 2, title: 'NOR 门 SR 锁存器', shortTitle: 'SR 锁存器', type: '讲义', summary: '从两个交叉耦合的 NOR 门理解保持、置位、复位和非法状态。'),
    _LessonUnit(day: 3, title: 'D 锁存器结构与工作过程', shortTitle: 'D 锁存器', type: '讲义', summary: '理解为什么 D 锁存器可以避免 SR 锁存器的禁态。'),
    _LessonUnit(day: 4, title: '双稳态元件与锁存器原理', shortTitle: '双稳态', type: '图解', summary: '用状态推导和真值表解释锁存器为什么能记忆。'),
    _LessonUnit(day: 5, title: '同步与异步系统差异分析', shortTitle: '同步异步', type: '测验', summary: '比较不同触发方式，并完成一次课程测验。'),
  ];

  _LessonUnit get _current => _units[_activeIndex];

  @override
  void dispose() {
    _api.dispose();
    _questionController.dispose();
    super.dispose();
  }

  Future<void> _askInline(String question) async {
    final text = question.trim();
    if (text.isEmpty) return;

    setState(() {
      _isAsking = true;
      _answer = null;
    });

    try {
      final data = await _api.quickAnswer(
        question: text,
        mode: 'step_by_step',
        fragments: [_current.title, _current.summary],
      );
      final tutoring = (data['tutoring'] as Map?)?.cast<String, dynamic>() ?? data;
      setState(() {
        _answer = _InlineAnswer(
          title: '结合当前讲义的解答',
          summary: tutoring['solving_approach']?.toString() ?? tutoring['final_answer']?.toString() ?? '已经结合当前讲义生成回答。',
          formulas: const [],
          steps: const ['先回到当前知识点定位概念', '再把题目条件映射到公式或状态表', '最后检查边界条件和易错点'],
        );
      });
    } catch (_) {
      setState(() {
        _answer = _InlineAnswer(
          title: '结合当前讲义的解答',
          summary: '这类问题先不要背结论，先看输入 S、R 对两个 NOR 门输出的影响，再用状态表验证 Q 的下一状态。',
          formulas: const ['Q_next = !(R || Q_next_complement)', 'Q_next_complement = !(S || Q_next)'],
          steps: const ['确认当前状态 Q 和 Q\'', '代入 S、R 的输入组合', '按 NOR 门规则逐行推导', '用互补关系检查结果是否合理'],
        );
      });
    } finally {
      if (mounted) setState(() => _isAsking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        title: const Text('学习空间'),
        actions: [
          IconButton(
            tooltip: '独立答疑',
            icon: const Icon(Icons.open_in_new),
            onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const QuickAnswerPage())),
          ),
        ],
      ),
      body: Column(
        children: [
          _unitStrip(),
          Expanded(child: _lecturePane()),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openAskSheet,
        icon: const Icon(Icons.forum_outlined),
        label: const Text('问当前内容'),
      ),
      bottomNavigationBar: _bottomActionBar(),
    );
  }

  Widget _unitStrip() {
    return Container(
      height: 82,
      decoration: const BoxDecoration(
        color: _card,
        border: Border(bottom: BorderSide(color: _border)),
      ),
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        scrollDirection: Axis.horizontal,
        itemCount: _units.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, index) {
          final unit = _units[index];
          final active = index == _activeIndex;
          final done = index < _activeIndex;
          final color = active ? _blue : (done ? _teal : const Color(0xFFB4AFA5));
          return InkWell(
            borderRadius: BorderRadius.circular(18),
            onTap: () => setState(() => _activeIndex = index),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              width: active ? 168 : 150,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: active ? const Color(0xFFEAF1F1) : Colors.white.withValues(alpha: 0.72),
                border: Border.all(color: active ? _teal : _border),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 17,
                    backgroundColor: color,
                    child: done ? const Icon(Icons.check, color: Colors.white, size: 16) : Text('${unit.day}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900)),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(unit.shortTitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 12.5, color: _ink)),
                        const SizedBox(height: 2),
                        Text('第 ${unit.day} 天 · ${unit.type}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11, color: _muted)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _lecturePane() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 112),
      children: [
        _unitHeader(),
        const SizedBox(height: 12),
        _sectionCard(
          title: '一、精准定义',
          icon: Icons.article_outlined,
          color: _blue,
          children: const [
            Text('SR 锁存器是一种最基本的异步时序电路。它有两个控制输入端 S（Set，置位）和 R（Reset，复位），以及两个互补输出端 Q 和 Q\'。', style: TextStyle(height: 1.55, color: _ink)),
            SizedBox(height: 8),
            Text('适用范围：用于暂存 1 位二进制数据，是构成触发器和寄存器的基础单元。', style: TextStyle(height: 1.55, color: _ink)),
          ],
        ),
        const SizedBox(height: 12),
        const _FormulaBlock(
          title: '输入约束',
          formulas: ['S * R = 0', 'S 和 R 不能同时为 1'],
          note: '如果 S=1 且 R=1，会破坏两个输出互补的关系，实际电路中通常视为非法状态。',
        ),
        const SizedBox(height: 12),
        _diagramCard(),
        const SizedBox(height: 12),
        _sectionCard(
          title: '三、状态推导',
          icon: Icons.functions,
          color: _purple,
          children: [
            const Text('NOR 门的规则很简单：只要任一输入为 1，输出就是 0；只有全部输入为 0，输出才是 1。把这个规则代入交叉反馈结构，就能得到下一状态。', style: TextStyle(height: 1.55, color: _ink)),
            const SizedBox(height: 12),
            const _FormulaBlock(
              title: '下一状态关系',
              formulas: ['Q_next = !(R || Q_next_complement)', 'Q_next_complement = !(S || Q_next)'],
              note: '公式单独成块显示，避免和正文混在一起看不清。',
            ),
            const SizedBox(height: 12),
            _stateTable(),
            const SizedBox(height: 12),
            const Text('小结：S=0 且 R=0 时保持；S=1 时置位；R=1 时复位；S=R=1 时进入非法状态。', style: TextStyle(height: 1.55, color: _ink)),
          ],
        ),
        const SizedBox(height: 12),
        _sectionCard(
          title: '四、下一步行动',
          icon: Icons.task_alt,
          color: _teal,
          children: [
            _actionRow(Icons.forum_outlined, '看不懂图或推导时，从底部拉起答疑抽屉。'),
            _actionRow(Icons.edit_note_outlined, '学完当前讲义后，生成同类练习并查看解析。'),
            _actionRow(Icons.fact_check_outlined, '完成当天测验，错题自动进入复盘。'),
          ],
        ),
      ],
    );
  }

  Widget _unitHeader() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _badge('第 ${_current.day} 天', _blue),
                const SizedBox(width: 8),
                _badge(_current.type, _teal),
              ],
            ),
            const SizedBox(height: 12),
            Text(_current.title, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w900, color: _ink, height: 1.25)),
            const SizedBox(height: 6),
            Text(_current.summary, style: const TextStyle(color: _muted, height: 1.5)),
            const SizedBox(height: 14),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: const LinearProgressIndicator(value: 0.42, minHeight: 8, backgroundColor: Color(0xFFE5DED2), color: _teal),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sectionCard({required String title, required IconData icon, required Color color, required List<Widget> children}) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(color: color.withValues(alpha: 0.10), borderRadius: BorderRadius.circular(10)),
                  child: Icon(icon, color: color, size: 19),
                ),
                const SizedBox(width: 10),
                Expanded(child: Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: _ink))),
              ],
            ),
            const SizedBox(height: 13),
            ...children,
          ],
        ),
      ),
    );
  }

  Widget _diagramCard() {
    return _sectionCard(
      title: '二、结构图解',
      icon: Icons.account_tree_outlined,
      color: _teal,
      children: [
        Container(
          height: 230,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: _border),
          ),
          child: CustomPaint(painter: _LatchDiagramPainter()),
        ),
        const SizedBox(height: 10),
        const Text('两个 NOR 门交叉反馈：上方输出 Q 会回到下方 NOR 门输入，下方输出 Q\' 也会回到上方 NOR 门输入。反馈让电路具备“保持状态”的能力。', style: TextStyle(color: _muted, height: 1.5)),
      ],
    );
  }

  Widget _stateTable() {
    const rows = [
      ['0', '0', '保持', '输出不变'],
      ['1', '0', '置位', 'Q 变为 1'],
      ['0', '1', '复位', 'Q 变为 0'],
      ['1', '1', '非法', '不建议出现'],
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        headingRowHeight: 38,
        dataRowMinHeight: 40,
        dataRowMaxHeight: 46,
        columns: const [
          DataColumn(label: Text('S')),
          DataColumn(label: Text('R')),
          DataColumn(label: Text('状态')),
          DataColumn(label: Text('说明')),
        ],
        rows: rows
            .map(
              (row) => DataRow(
                cells: row.map((cell) => DataCell(Text(cell, style: const TextStyle(fontWeight: FontWeight.w700)))).toList(),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _actionRow(IconData icon, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: _teal),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(color: _ink, height: 1.45))),
        ],
      ),
    );
  }

  Widget _badge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.10), borderRadius: BorderRadius.circular(999)),
      child: Text(text, style: TextStyle(color: color, fontWeight: FontWeight.w900, fontSize: 12)),
    );
  }

  Widget _bottomActionBar() {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
        decoration: const BoxDecoration(color: _card, border: Border(top: BorderSide(color: _border))),
        child: Row(
          children: [
            OutlinedButton.icon(
              onPressed: _activeIndex == 0 ? null : () => setState(() => _activeIndex--),
              icon: const Icon(Icons.chevron_left),
              label: const Text('上一节'),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: FilledButton.icon(
                onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ExercisePage())),
                icon: const Icon(Icons.edit_note_outlined),
                label: const Text('练习'),
              ),
            ),
            const SizedBox(width: 8),
            OutlinedButton.icon(
              onPressed: _activeIndex == _units.length - 1 ? null : () => setState(() => _activeIndex++),
              icon: const Icon(Icons.chevron_right),
              label: const Text('下一节'),
            ),
          ],
        ),
      ),
    );
  }

  void _openAskSheet() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return SafeArea(
              child: Padding(
                padding: EdgeInsets.fromLTRB(16, 4, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('问当前内容', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                    const SizedBox(height: 4),
                    Text(_current.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: _muted)),
                    const SizedBox(height: 12),
                    if (_isAsking) const LinearProgressIndicator(minHeight: 3),
                    if (_answer != null) ...[
                      _inlineAnswerCard(_answer!),
                      const SizedBox(height: 12),
                    ] else ...[
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: ['这张图怎么读？', '公式为什么这样写？', '给我出一道同类题']
                            .map(
                              (text) => ActionChip(
                                label: Text(text),
                                onPressed: () async {
                                  _questionController.text = text;
                                  await _askInline(text);
                                  setSheetState(() {});
                                },
                              ),
                            )
                            .toList(),
                      ),
                      const SizedBox(height: 12),
                    ],
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _questionController,
                            minLines: 1,
                            maxLines: 3,
                            decoration: const InputDecoration(hintText: '问这节课里没懂的地方...', border: OutlineInputBorder()),
                          ),
                        ),
                        const SizedBox(width: 8),
                        FilledButton(
                          onPressed: _isAsking
                              ? null
                              : () async {
                                  await _askInline(_questionController.text);
                                  setSheetState(() {});
                                },
                          style: FilledButton.styleFrom(shape: const CircleBorder(), minimumSize: const Size(48, 48), padding: EdgeInsets.zero),
                          child: const Icon(Icons.arrow_upward),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _inlineAnswerCard(_InlineAnswer answer) {
    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(color: _teal.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(10)),
                child: const Icon(Icons.auto_awesome, color: _teal, size: 18),
              ),
              const SizedBox(width: 8),
              Expanded(child: Text(answer.title, style: const TextStyle(fontWeight: FontWeight.w900, color: _ink))),
            ],
          ),
          const SizedBox(height: 10),
          Text(answer.summary, style: const TextStyle(height: 1.55, color: _ink)),
          if (answer.formulas.isNotEmpty) ...[
            const SizedBox(height: 10),
            _FormulaBlock(title: '公式', formulas: answer.formulas),
          ],
          const SizedBox(height: 10),
          ...answer.steps.asMap().entries.map((entry) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 7),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(radius: 11, backgroundColor: _blue.withValues(alpha: 0.12), child: Text('${entry.key + 1}', style: const TextStyle(fontSize: 11, color: _blue, fontWeight: FontWeight.w900))),
                  const SizedBox(width: 8),
                  Expanded(child: Text(entry.value, style: const TextStyle(height: 1.45, color: _ink))),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}

class _FormulaBlock extends StatelessWidget {
  final String title;
  final List<String> formulas;
  final String? note;

  const _FormulaBlock({required this.title, required this.formulas, this.note});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF3F7F7),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFD6E4E4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w900, color: _LearningPageState._blue)),
          const SizedBox(height: 8),
          ...formulas.map(
            (formula) => Container(
              width: double.infinity,
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
              child: SelectableText(
                formula,
                textAlign: TextAlign.center,
                style: const TextStyle(fontFamily: 'monospace', fontSize: 15, fontWeight: FontWeight.w800, color: _LearningPageState._ink),
              ),
            ),
          ),
          if (note != null) Text(note!, style: const TextStyle(color: _LearningPageState._muted, height: 1.45, fontSize: 12.5)),
        ],
      ),
    );
  }
}

class _LatchDiagramPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = const Color(0xFF3F3D4D)
      ..strokeWidth = 2.3
      ..style = PaintingStyle.stroke;
    final gatePaint = Paint()
      ..color = const Color(0xFFFFFCF7)
      ..style = PaintingStyle.fill;
    final gateBorder = Paint()
      ..color = const Color(0xFFD97706)
      ..strokeWidth = 2.2
      ..style = PaintingStyle.stroke;
    final feedback = Paint()
      ..color = const Color(0xFF2F7D73)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;

    final topGate = RRect.fromRectAndRadius(Rect.fromLTWH(size.width * .34, size.height * .24, size.width * .28, 44), const Radius.circular(22));
    final bottomGate = RRect.fromRectAndRadius(Rect.fromLTWH(size.width * .34, size.height * .56, size.width * .28, 44), const Radius.circular(22));
    canvas.drawRRect(topGate, gatePaint);
    canvas.drawRRect(topGate, gateBorder);
    canvas.drawRRect(bottomGate, gatePaint);
    canvas.drawRRect(bottomGate, gateBorder);

    final inputX = size.width * .12;
    final gateInX = size.width * .34;
    final gateOutX = size.width * .62;
    final outputX = size.width * .88;
    final topY = size.height * .34;
    final bottomY = size.height * .66;

    canvas.drawLine(Offset(inputX, topY), Offset(gateInX, topY), line);
    canvas.drawLine(Offset(inputX, bottomY), Offset(gateInX, bottomY), line);
    canvas.drawLine(Offset(gateOutX, topY), Offset(outputX, topY), line);
    canvas.drawLine(Offset(gateOutX, bottomY), Offset(outputX, bottomY), line);
    canvas.drawLine(Offset(gateOutX + 8, topY), Offset(gateInX - 8, bottomY), feedback);
    canvas.drawLine(Offset(gateOutX + 8, bottomY), Offset(gateInX - 8, topY), feedback);

    _drawLabel(canvas, 'R', Offset(inputX - 24, topY - 10), 18, FontWeight.w900);
    _drawLabel(canvas, 'S', Offset(inputX - 24, bottomY - 10), 18, FontWeight.w900);
    _drawLabel(canvas, 'NOR 1', Offset(size.width * .405, topY - 10), 12, FontWeight.w800, const Color(0xFFD97706));
    _drawLabel(canvas, 'NOR 2', Offset(size.width * .405, bottomY - 10), 12, FontWeight.w800, const Color(0xFFD97706));
    _drawLabel(canvas, 'Q', Offset(outputX + 8, topY - 11), 18, FontWeight.w900, const Color(0xFFC2410C));
    _drawLabel(canvas, "Q'", Offset(outputX + 8, bottomY - 11), 18, FontWeight.w900, const Color(0xFFC2410C));
  }

  void _drawLabel(Canvas canvas, String text, Offset offset, double size, FontWeight weight, [Color color = const Color(0xFF34324A)]) {
    final painter = TextPainter(
      text: TextSpan(text: text, style: TextStyle(color: color, fontSize: size, fontWeight: weight)),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(canvas, offset);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _LessonUnit {
  final int day;
  final String title;
  final String shortTitle;
  final String type;
  final String summary;

  const _LessonUnit({
    required this.day,
    required this.title,
    required this.shortTitle,
    required this.type,
    required this.summary,
  });
}

class _InlineAnswer {
  final String title;
  final String summary;
  final List<String> formulas;
  final List<String> steps;

  const _InlineAnswer({
    required this.title,
    required this.summary,
    required this.formulas,
    required this.steps,
  });
}
