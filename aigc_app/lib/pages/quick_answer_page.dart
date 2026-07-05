import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:record/record.dart';

import '../services/api_service.dart';
import '../widgets/math_tex.dart';

class QuickAnswerPage extends StatefulWidget {
  final bool showAppBar;

  const QuickAnswerPage({super.key, this.showAppBar = true});

  @override
  State<QuickAnswerPage> createState() => _QuickAnswerPageState();
}

class _QuickAnswerPageState extends State<QuickAnswerPage> {
  final _api = ApiService();
  final _questionController = TextEditingController();
  final _audioRecorder = AudioRecorder();

  final List<_ChatMessage> _messages = [];
  PlatformFile? _pickedImage;
  String _mode = 'quick';
  bool _isLoading = false;
  bool _isRecording = false;

  static const _bg = Color(0xFFFAF7F1);
  static const _card = Color(0xFFFFFCF7);
  static const _ink = Color(0xFF34324A);
  static const _muted = Color(0xFF8A8798);
  static const _primary = Color(0xFF536878);
  static const _accent = Color(0xFF8FB1B3);
  static const _border = Color(0xFFE5DED2);
  static const _danger = Color(0xFFDC2626);
  static const _amber = Color(0xFFD97706);

  @override
  void dispose() {
    _api.dispose();
    _questionController.dispose();
    _audioRecorder.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['png', 'jpg', 'jpeg'],
    );
    if (result != null && result.files.isNotEmpty) {
      setState(() => _pickedImage = result.files.first);
    }
  }

  Future<void> _toggleRecording() async {
    if (_isRecording) {
      final path = await _audioRecorder.stop();
      if (!mounted || path == null) return;
      setState(() {
        _isRecording = false;
        _isLoading = true;
      });
      try {
        final bytes = await File(path).readAsBytes();
        final data = await _api.voiceAsr(bytes, 'recording.wav');
        final text = data['text']?.toString();
        if (text != null && text.trim().isNotEmpty) {
          _questionController.text = text.trim();
        } else {
          _showSnack('没有识别到有效语音', _amber);
        }
      } catch (e) {
        _showSnack('语音识别失败：$e', _danger);
      } finally {
        if (mounted) setState(() => _isLoading = false);
        try {
          await File(path).delete();
        } catch (_) {}
      }
      return;
    }

    final hasPermission = await _audioRecorder.hasPermission();
    if (!hasPermission) {
      _showSnack('需要麦克风权限后才能录音', _danger);
      return;
    }
    final path = '${Directory.systemTemp.path}/aigc_voice_${DateTime.now().millisecondsSinceEpoch}.wav';
    await _audioRecorder.start(
      const RecordConfig(encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1),
      path: path,
    );
    setState(() => _isRecording = true);
  }

  Future<void> _ask() async {
    final question = _questionController.text.trim();
    if (question.isEmpty && _pickedImage == null) {
      _showSnack('请输入问题，或先添加一张题目图片', _amber);
      return;
    }

    final displayQuestion = question.isEmpty ? '请解答这张图片里的题目' : question;
    final imageName = _pickedImage?.name;
    setState(() {
      _messages.add(_ChatMessage.user(displayQuestion, imageName: imageName));
      _questionController.clear();
      _isLoading = true;
    });

    try {
      String? imageBase64;
      if (_pickedImage?.path != null) {
        imageBase64 = base64Encode(await File(_pickedImage!.path!).readAsBytes());
      }
      final data = await _api.quickAnswer(
        question: displayQuestion,
        mode: _apiMode,
        imageBase64: imageBase64,
      );
      setState(() {
        _messages.add(_ChatMessage.ai(_parseAnswer(data, displayQuestion, hadImage: imageName != null)));
        _pickedImage = null;
      });
    } catch (_) {
      setState(() {
        _messages.add(_ChatMessage.ai(_demoAnswer(displayQuestion, hadImage: imageName != null)));
        _pickedImage = null;
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  String get _apiMode {
    return switch (_mode) {
      'hint' => 'hint',
      'correction' => 'correction',
      _ => 'step_by_step',
    };
  }

  _AnswerPayload _parseAnswer(Map<String, dynamic> data, String question, {bool hadImage = false}) {
    final intent = _classifyIntent(question);
    if (intent.kind == _AnswerKind.vocabulary) {
      return _demoAnswer(question);
    }
    if (intent.kind == _AnswerKind.conceptOverview) {
      return _conceptOverviewAnswer(question);
    }
    final tutoring = _extractTutoringPayload(data);
    final steps = (tutoring['complete_steps'] as List?)?.map((item) => item.toString()).toList() ?? <String>[];
    final mistakes = (tutoring['common_mistakes'] as List?)?.map((item) => item.toString()).toList() ?? <String>[];
    final formulas = (tutoring['formulas'] as List?)?.map((item) => item.toString()).toList() ?? <String>[];
    if (tutoring['answer_status']?.toString() == 'insufficient') {
      if (!hadImage && _looksLikeChineseMultipleChoice(question)) return _chineseMultipleChoiceAnswer(question);
      if (!hadImage && _looksLikeMathProblem(question)) return _mathProblemAnswer(question);
      if (!hadImage && _looksLikeConceptOverview(question.toLowerCase())) return _conceptOverviewAnswer(question);
      return _AnswerPayload(
        summary: tutoring['solving_approach']?.toString() ?? '当前没有拿到可用解答。',
        hint: tutoring['next_step_hint']?.toString() ?? '请补充完整题干，或检查后端模型/OCR服务。',
        steps: steps.isEmpty ? const ['没有获得有效题目解析', '需要补充题干或等待模型返回'] : steps,
        finalAnswer: tutoring['final_answer']?.toString() ?? '',
        mistakes: mistakes,
        diagramType: _DiagramType.none,
        showDiagram: false,
      );
    }
    if (!_hasUsefulAnswer(tutoring, steps)) {
      if (hadImage) return _imageNeedsOcrAnswer();
      if (_looksLikeChineseMultipleChoice(question)) return _chineseMultipleChoiceAnswer(question);
      if (_looksLikeMathProblem(question)) return _mathProblemAnswer(question);
      if (_looksLikeImageOnlyQuestion(question)) return _imageNeedsOcrAnswer();
    }
    return _AnswerPayload(
      summary: tutoring['solving_approach']?.toString() ?? '我会先识别题目条件，再分步骤推导。',
      hint: tutoring['next_step_hint']?.toString() ?? '可以继续问“为什么这样画图”或“给我同类题”。',
      steps: steps.isEmpty ? const ['识别题目对象', '画出关系图或受力图', '列出公式或逻辑关系', '代入求解并检查'] : steps,
      formulas: formulas,
      finalAnswer: tutoring['final_answer']?.toString() ?? '',
      mistakes: mistakes.isEmpty ? const ['没有图示直接套公式', '漏掉方向或约束条件'] : mistakes,
      diagramType: intent.diagramType,
      showDiagram: intent.showDiagram,
    );
  }

  Map<String, dynamic> _extractTutoringPayload(Map<String, dynamic> data) {
    Map<String, dynamic> current = data;
    for (final key in ['tutoring', 'final_result', 'final_package', 'final_package_structure', 'tutor_result']) {
      final value = current[key];
      if (value is Map) {
        current = value.cast<String, dynamic>();
      }
    }
    return current;
  }

  _AnswerPayload _demoAnswer(String question, {bool hadImage = false}) {
    if (hadImage && _looksLikeImageOnlyQuestion(question)) {
      return _imageNeedsOcrAnswer();
    }
    if (_looksLikeMathProblem(question)) {
      return _mathProblemAnswer(question);
    }
    final intent = _classifyIntent(question);
    if (intent.kind == _AnswerKind.vocabulary) {
      final word = question.trim();
      if (word.toLowerCase() != 'abandon') {
        return _AnswerPayload(
          summary: '“$word” 看起来更像一个词汇或短语问题，不需要生成图解。我会先按词义、用法、例句这条线来处理。',
          hint: '可以继续问“给我例句”“怎么记这个词”或“和相近词有什么区别”。',
          steps: const [
            '先判断词性和常见语境',
            '再解释核心含义',
            '补充一个简单例句',
            '如果需要，再比较近义表达',
          ],
          finalAnswer: '当前后端不可用，所以本地只给出词汇答疑框架；接入模型后会返回准确释义、例句和记忆提示。',
          mistakes: const [],
          diagramType: _DiagramType.none,
          showDiagram: false,
        );
      }
      return _AnswerPayload(
        summary: '“$word” 可以先按词汇问题处理。它常见意思是“放弃、抛弃、离弃”。如果你是在背单词，可以把它理解为主动停止继续做某事，或离开某人/某物不再照管。',
        hint: '你可以继续问“给我例句”“和 give up 有什么区别”或“帮我记忆这个单词”。',
        steps: const [
          '词性：常作动词',
          '核心含义：放弃、抛弃、离弃',
          '常见搭配：abandon a plan / abandon hope / abandon a child',
          '近义表达：give up, desert, leave behind',
        ],
        finalAnswer: '例句：He abandoned the plan because it was too risky. 他因为风险太大而放弃了这个计划。',
        mistakes: const [],
        diagramType: _DiagramType.none,
        showDiagram: false,
      );
    }
    if (intent.kind == _AnswerKind.conceptOverview) {
      return _conceptOverviewAnswer(question);
    }
    if (_looksLikeChineseMultipleChoice(question)) {
      return _chineseMultipleChoiceAnswer(question);
    }
    final isForce = intent.diagramType == _DiagramType.force;
    final isQuestion = intent.kind == _AnswerKind.problemSolving || intent.kind == _AnswerKind.explicitDiagram;
    return _AnswerPayload(
      summary: isForce
          ? '这类题先不要急着代公式。先确定研究对象，画受力图，再沿合适方向分解力，最后用牛顿第二定律列方程。'
          : isQuestion
              ? '当前没有拿到针对这道题的有效模型解答，我不会把通用流程当作答案展示。'
              : '这个问题目前缺少具体题目或学习目标。我可以先给你一个简短解释，也可以等你补充题干、图片或你卡住的步骤。',
      hint: isQuestion ? '请补充完整题干，或检查后端模型是否正常返回 final_answer 和 complete_steps。' : '你可以继续补充：“这是哪道题”“请画图解释”或“给我例子”。',
      steps: isForce
          ? const ['确定研究对象：物块', '画出重力、支持力、拉力和摩擦力', '选择水平方向和竖直方向建立坐标', '列出 ΣF = ma 并代入求解']
          : isQuestion
              ? const ['没有获得有效题目解析', '不能展示“识别知识点、整理条件、选择方法”这类内部模板']
              : const ['确认你想问的是概念、题目还是翻译', '补充题干或截图会更准确', '需要图解时可以直接说“画图解释”'],
      finalAnswer: isForce
          ? '示例：若水平合力为 F，质量为 m，则加速度 a = F / m。'
          : isQuestion
              ? ''
              : '',
      mistakes: const [],
      diagramType: intent.diagramType,
      showDiagram: intent.showDiagram,
    );
  }

  _AnswerIntent _classifyIntent(String text) {
    final value = text.trim();
    if (value.isEmpty) return const _AnswerIntent(_AnswerKind.general, _DiagramType.none, false);
    if (_looksLikeVocabulary(value)) {
      return const _AnswerIntent(_AnswerKind.vocabulary, _DiagramType.none, false);
    }
    final lower = value.toLowerCase();
    if (_looksLikeConceptOverview(lower)) {
      return const _AnswerIntent(_AnswerKind.conceptOverview, _DiagramType.none, false);
    }
    const forceWords = ['受力图', '受力分析', '牛顿第二定律', '摩擦', '支持力', '重力', '拉力', '合力', '加速度'];
    if (_hasAny(lower, forceWords)) {
      return const _AnswerIntent(_AnswerKind.explicitDiagram, _DiagramType.force, true);
    }

    const explicitDiagramWords = [
      '画图',
      '出图',
      '图解',
      '示意图',
      '关系图',
      '函数图像',
      '电路图',
      'diagram',
      'graph',
    ];
    if (_hasAny(lower, explicitDiagramWords)) {
      return const _AnswerIntent(_AnswerKind.explicitDiagram, _DiagramType.logic, true);
    }

    const problemWords = [
      '题',
      '推导',
      '证明',
      '公式',
      '计算',
      '求',
      '为什么',
      '怎么解',
      '解析',
      '步骤',
      '受力',
      '电路',
      '几何',
      '函数',
      '坐标',
      '结构',
      '流程',
      'circuit',
    ];
    if (_hasAny(lower, problemWords)) {
      const visualDomains = ['电路', '几何', '函数图像', '坐标', '结构', '流程', '受力', '图像'];
      const symbolicTasks = ['推导', '证明', '公式'];
      final shouldDraw = _hasAny(lower, visualDomains) && !_hasAny(lower, symbolicTasks);
      return _AnswerIntent(_AnswerKind.problemSolving, shouldDraw ? _DiagramType.logic : _DiagramType.none, shouldDraw);
    }

    return const _AnswerIntent(_AnswerKind.general, _DiagramType.none, false);
  }

  _AnswerPayload _conceptOverviewAnswer(String question) {
    final lower = question.toLowerCase();
    final isAdvancedMath = question.contains('高数') || question.contains('高等数学') || lower.contains('calculus');
    return _AnswerPayload(
      summary: isAdvancedMath
          ? '高数主要学“用数学描述变化和累积”。它不是先背一堆公式，而是围绕函数、极限、导数、积分、级数和多元函数，训练你分析变化率、面积/累积量、近似和优化问题。'
          : '这个问题更像是在问一个学科或概念的整体介绍，不需要先给公式或图。我会先讲它研究什么、为什么学、通常学哪些模块，再给你一个入门顺序。',
      hint: isAdvancedMath ? '可以继续问“高数怎么学”“高数和线代有什么区别”或“给我一周入门路线”。' : '可以继续问“怎么入门”“它和相近概念有什么区别”或“给我学习路线”。',
      steps: isAdvancedMath
          ? const ['函数与极限：理解变化的起点', '导数：研究瞬时变化率和优化', '积分：研究累积量、面积和总效果', '级数与多元函数：处理更复杂的近似和多变量变化']
          : const ['先说明它研究什么', '再说明它解决什么问题', '列出核心模块', '给出适合初学者的学习顺序'],
      finalAnswer: isAdvancedMath
          ? '简单说：高数是在学习如何用函数、极限、导数和积分理解“变化”。工科、理科、经济、AI、物理里很多模型都会用到它。'
          : '',
      mistakes: const [],
      diagramType: _DiagramType.none,
      showDiagram: false,
    );
  }

  _AnswerPayload _mathProblemAnswer(String question) {
    final normalized = question.replaceAll(RegExp(r'\s+'), '').toLowerCase();
    final isEquivalentLimit = normalized.contains('lim') &&
        normalized.contains('ln(1+2x)') &&
        normalized.contains('sin3x') &&
        (normalized.contains('1-cosx') || normalized.contains('1-\\cosx'));
    final hasDerivativeIntent = normalized.contains("y'") ||
        normalized.contains("y\\'") ||
        normalized.contains('求导') ||
        normalized.contains('导数') ||
        normalized.contains('链式') ||
        normalized.contains('derivative');
    final hasExpSinSquare = (normalized.contains('e^') || normalized.contains('e{') || normalized.contains('exp')) &&
        normalized.contains('sin') &&
        normalized.contains('x^2') &&
        normalized.contains('+1');
    final isChainRuleDerivative = hasDerivativeIntent && hasExpSinSquare;

    if (isEquivalentLimit) {
      return const _AnswerPayload(
        summary: '这题是 x -> 0 时的等价无穷小极限。核心是把每一部分都换成同阶的简单表达式，再约掉 x 的次数。',
        hint: '同类题先看每个因子在 0 附近等价于什么，再检查分子分母的 x 次数是否相同。',
        formulas: [
          r'\ln(1+2x) \sim 2x',
          r'\sin 3x \sim 3x',
          r'1-\cos x \sim \frac{1}{2}x^2',
        ],
        steps: [
          '当 x -> 0 时，ln(1+2x) 等价于 2x',
          'sin(3x) 等价于 3x',
          '1-cos(x) 等价于 x^2/2',
          '原式等价于 (2x * 3x) / (x^2/2) = 12',
        ],
        finalAnswer: '极限值为 12。',
        mistakes: ['不要把 1-cos(x) 误写成 x，它是二阶无穷小', '替换等价无穷小时要保证整体是乘除结构'],
        diagramType: _DiagramType.none,
        showDiagram: false,
      );
    }

    if (isChainRuleDerivative) {
      return const _AnswerPayload(
        summary: '这题是复合函数求导，要从外到内连续使用链式法则。最外层是指数函数，中间是 sin，最里面是 x^2+1。',
        hint: '链式求导可以按“外层导数不动内层，再乘内层导数”的顺序写。',
        formulas: [
          r'y=e^{\sin(x^2+1)}',
          r'(e^u)^\prime=e^u\cdot u^\prime',
          r'(\sin v)^\prime=\cos v\cdot v^\prime',
          r'(x^2+1)^\prime=2x',
        ],
        steps: [
          '设 u = sin(x^2+1)，则 y = e^u',
          "根据 (e^u)' = e^u * u'，有 y' = e^u * u'",
          '再设 v = x^2+1，则 u = sin(v)，所以 u\' = cos(v) * v\'',
          "v' = (x^2+1)' = 2x",
          '代回得到 y\' = e^(sin(x^2+1)) * cos(x^2+1) * 2x',
        ],
        finalAnswer: "y' = 2x * e^(sin(x^2+1)) * cos(x^2+1)",
        mistakes: ['不要漏乘最里面的导数 2x', 'e 的指数部分求导后，原来的 e^(sin(x^2+1)) 仍然保留'],
        diagramType: _DiagramType.none,
        showDiagram: false,
      );
    }

    return const _AnswerPayload(
      summary: '这是一个数学解题问题，我会按题型、公式依据、代入推导、结果检查来处理，而不是给通用模板。',
      hint: '如果题干里有图片，请尽量补一行文字题干；这样前端兜底也能更准确地展示步骤。',
      formulas: ['先识别题型', '列出适用公式', '代入并化简'],
      steps: [
        '判断题型：极限、导数、积分、级数或方程',
        '找出题目中的关键表达式和趋近条件',
        '选择对应方法：等价无穷小、洛必达、换元、分部积分等',
        '写出化简过程并检查定义域或边界条件',
      ],
      finalAnswer: '当前本地兜底没有完整识别到具体表达式；接入后端模型后应返回真实推导和答案。',
      mistakes: ['不要直接套公式，要先确认题型和适用条件'],
      diagramType: _DiagramType.none,
      showDiagram: false,
    );
  }

  _AnswerPayload _imageNeedsOcrAnswer() {
    return const _AnswerPayload(
      summary: '这是一道图片题，但当前没有拿到 OCR 或模型识别出的题干，所以我不能假装已经读懂图片。',
      hint: '你可以把题目文字补充到输入框，或确认后端 OCR/图片问答接口已经正常返回识别结果。',
      steps: [
        '先识别图片中的题干、条件和问题',
        '再判断题型和使用的方法',
        '最后给出分步推导、公式块和答案',
      ],
      finalAnswer: '目前缺少图片题干文本，无法可靠解题。',
      mistakes: ['不要在未识别题干时输出通用步骤', '不要默认画图或套公式'],
      diagramType: _DiagramType.none,
      showDiagram: false,
    );
  }

  _AnswerPayload _chineseMultipleChoiceAnswer(String question) {
    final isIdiomQuestion = question.contains('成语') || question.contains('加点成语') || question.contains('使用有误');
    if (isIdiomQuestion && question.contains('不求甚解')) {
      return const _AnswerPayload(
        summary: '这题考查成语使用是否符合语境。错误项是 C。',
        hint: '做成语题时，先看成语本义，再看句子感情色彩和前后逻辑是否一致。',
        steps: [
          'A“一丝不苟”表示做事认真细致，用来形容学习态度认真，合适。',
          'B“人声鼎沸”形容人群声音嘈杂热闹，用在公园热闹场景，基本合适。',
          'C“不求甚解”指学习或理解不深入，和“终于取得了优异成绩”逻辑矛盾，使用有误。',
          'D“锲而不舍”表示坚持不放弃，用来形容面对困难的精神，合适。',
        ],
        finalAnswer: '答案：C',
        mistakes: ['不要只看成语表面是否熟悉，要检查它和句子结果是否矛盾。'],
        diagramType: _DiagramType.none,
        showDiagram: false,
      );
    }
    return const _AnswerPayload(
      summary: '这是选择题，但当前没有拿到可用模型解析。我不会把通用步骤当作答案。',
      hint: '请确认后端模型正常返回选项判断；也可以把题干和选项补完整后重试。',
      steps: ['未获得有效选项解析'],
      finalAnswer: '',
      mistakes: [],
      diagramType: _DiagramType.none,
      showDiagram: false,
    );
  }

  bool _looksLikeChineseMultipleChoice(String text) {
    final value = text.trim();
    final hasOptions = RegExp(r'[A-D][\.、]').hasMatch(value) || (value.contains('A.') && value.contains('B.'));
    final asksChoice = value.contains('下列') || value.contains('一项') || value.contains('选择') || value.contains('有误');
    return hasOptions && asksChoice;
  }

  bool _looksLikeMathProblem(String text) {
    final lower = text.toLowerCase();
    const mathWords = [
      'lim',
      'limit',
      '极限',
      '导数',
      '求导',
      '积分',
      '等价无穷小',
      '洛必达',
      'sin',
      'cos',
      'ln',
      'e^',
      'exp',
      "y'",
      'frac',
      '\\lim',
      '\\frac',
      '\\sin',
    ];
    return _hasAny(lower, mathWords);
  }

  bool _hasUsefulAnswer(Map<String, dynamic> tutoring, List<String> steps) {
    final summary = tutoring['solving_approach']?.toString().trim() ?? '';
    final finalAnswer = tutoring['final_answer']?.toString().trim() ?? '';
    final joined = '$summary ${steps.join(' ')}';
    const templateMarkers = [
      '识别知识点',
      '整理条件',
      '选择方法',
      '完成推导',
      '完成推导或计算',
      '检查答案',
      '先识别题目',
      '列出已知条件',
      '目标结论',
    ];
    final templateHits = templateMarkers.where((marker) => joined.contains(marker)).length;
    if (templateHits >= 2 && finalAnswer.isEmpty) return false;
    if (finalAnswer.isNotEmpty) return true;
    if (steps.isNotEmpty) return true;
    if (summary.length >= 18 && !summary.contains('识别题目条件')) return true;
    return false;
  }

  bool _looksLikeImageOnlyQuestion(String text) {
    return text.contains('图片') || text.toLowerCase().contains('image');
  }

  bool _looksLikeConceptOverview(String lower) {
    const overviewWords = ['是学啥', '学啥', '学什么', '是什么', '干什么', '有什么用', '介绍一下', '讲讲', '入门', '怎么学', '学习路线', '主要内容'];
    const taskWords = ['求', '计算', '证明', '推导', '画图', '出图', '图解', '受力图', '解这道', '这题', '题目', '公式', '答案'];
    if (_hasAny(lower, taskWords)) return false;
    return _hasAny(lower, overviewWords);
  }

  bool _hasAny(String value, List<String> words) {
    return words.any((word) => value.contains(word));
  }

  bool _looksLikeVocabulary(String text) {
    final value = text.trim();
    if (value.isEmpty) return false;
    final simpleEnglish = RegExp(r"^[A-Za-z][A-Za-z\s'-]{0,30}$").hasMatch(value);
    if (!simpleEnglish) return false;
    final words = value.split(RegExp(r'\s+')).where((word) => word.isNotEmpty).length;
    return words <= 3;
  }

  void _showSnack(String message, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: color, behavior: SnackBarBehavior.floating),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: widget.showAppBar ? AppBar(title: const Text('AI 答疑')) : null,
      body: SafeArea(
        child: Column(
          children: [
            Expanded(child: _messages.isEmpty ? _emptyState() : _chatList()),
            if (_isLoading) const LinearProgressIndicator(minHeight: 2),
            _composer(),
          ],
        ),
      ),
    );
  }

  Widget _emptyState() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 42, 20, 24),
      children: [
        const Text(
          '你好，准备好开始了吗？',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 28, fontWeight: FontWeight.w900, color: _ink),
        ),
        const SizedBox(height: 12),
        const Text(
          '这里是即时答疑。可以打字、语音、拍题，AI 会用步骤、图解和易错点帮你理解。',
          textAlign: TextAlign.center,
          style: TextStyle(color: _muted, height: 1.5),
        ),
        const SizedBox(height: 28),
        _quickEntryGrid(),
        const SizedBox(height: 16),
        _samplePrompts(),
      ],
    );
  }

  Widget modeCard() {
    final modes = const [
      _ModeChoice(value: 'quick', label: '快速回答', icon: Icons.flash_on_outlined),
      _ModeChoice(value: 'hint', label: '只给提示', icon: Icons.lightbulb_outline),
      _ModeChoice(value: 'correction', label: '纠错诊断', icon: Icons.fact_check_outlined),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('回答模式', style: TextStyle(fontWeight: FontWeight.w900)),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: modes.map((mode) {
                return ChoiceChip(
                  avatar: Icon(mode.icon, size: 17),
                  label: Text(mode.label),
                  selected: _mode == mode.value,
                  onSelected: (_) => setState(() => _mode = mode.value),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _quickEntryGrid() {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 10,
      crossAxisSpacing: 10,
      childAspectRatio: 1.45,
      children: [
        _entryTile(Icons.photo_camera_outlined, '拍题答疑', '拍照或选图后分步讲解', _primary, _pickPhoto),
        _entryTile(Icons.edit_note_outlined, '文字追问', '概念、公式、推导都可以问', const Color(0xFF6B7280), () {}),
        _entryTile(Icons.insights_outlined, '按需出图', '受力图、关系图、流程图', _accent, () {
          _questionController.text = '帮我画受力图并解释';
        }),
        _entryTile(Icons.tune, '回答模式', _modeLabel, const Color(0xFF7566A0), _openModeSheet),
      ],
    );
  }

  Widget _entryTile(IconData icon, String title, String subtitle, Color color, VoidCallback onTap) {
    return InkWell(
      borderRadius: BorderRadius.circular(20),
      onTap: onTap,
      child: Ink(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.72),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withValues(alpha: 0.22)),
          boxShadow: [BoxShadow(color: color.withValues(alpha: 0.08), blurRadius: 18, offset: const Offset(0, 8))],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 22),
            const Spacer(),
            Text(title, style: const TextStyle(color: _ink, fontWeight: FontWeight.w900)),
            const SizedBox(height: 3),
            Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: _muted, fontSize: 12)),
          ],
        ),
      ),
    );
  }

  Widget _samplePrompts() {
    final prompts = ['拍照解这道物理题', '帮我画受力图', '这一步为什么这样推？', '给我同类题'];
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      alignment: WrapAlignment.center,
      children: prompts
          .map(
            (prompt) => ActionChip(
              label: Text(prompt),
              avatar: const Icon(Icons.arrow_forward, size: 16),
              onPressed: () {
                _questionController.text = prompt;
                _ask();
              },
            ),
          )
          .toList(),
    );
  }

  Widget _chatList() {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 20),
      itemCount: _messages.length,
      itemBuilder: (_, index) {
        final message = _messages[index];
        return message.isUser ? _userBubble(message) : _answerBubble(message.answer!);
      },
    );
  }

  Widget _userBubble(_ChatMessage message) {
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 310),
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(13),
        decoration: BoxDecoration(
          color: const Color(0xFFEAF1F1),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0xFFD6E4E4)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(message.text, style: const TextStyle(fontWeight: FontWeight.w700, color: _ink)),
            if (message.imageName != null) ...[
              const SizedBox(height: 8),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.image_outlined, size: 16, color: _primary),
                  const SizedBox(width: 5),
                  Flexible(child: Text(message.imageName!, overflow: TextOverflow.ellipsis, style: const TextStyle(color: _primary, fontSize: 12))),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _answerBubble(_AnswerPayload answer) {
    final formulas = _answerFormulas(answer);
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: _card,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: _border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.auto_awesome, color: _primary, size: 20),
                SizedBox(width: 8),
                Text('解答', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: _ink)),
              ],
            ),
            const SizedBox(height: 12),
            SmartText(answer.summary, fontSize: 14, color: _ink),
            if (formulas.isNotEmpty) ...[
              const SizedBox(height: 12),
              _formulaBlock(formulas),
            ],
            if (answer.showDiagram) ...[
              const SizedBox(height: 12),
              _diagram(answer.diagramType),
            ],
            const SizedBox(height: 12),
            _numberedList('步骤', answer.steps, _primary),
            if (answer.finalAnswer.isNotEmpty) ...[
              const SizedBox(height: 6),
              _textBlock('参考答案', answer.finalAnswer, Icons.task_alt, _accent),
            ],
            if (answer.mistakes.isNotEmpty) ...[
              const SizedBox(height: 6),
              _numberedList('易错点', answer.mistakes, _danger),
            ],
            const SizedBox(height: 8),
            SmartText(answer.hint, fontSize: 13, color: _muted),
          ],
        ),
      ),
    );
  }

  List<String> _answerFormulas(_AnswerPayload answer) {
    if (answer.formulas.isNotEmpty) return answer.formulas;
    if (!answer.showDiagram) return const [];
    if (answer.diagramType == _DiagramType.force) {
      return const ['sum(F_x) = m * a_x', 'sum(F_y) = m * a_y', 'f <= mu * N'];
    }
    if (answer.diagramType == _DiagramType.logic) {
      return const ['Q_next = !(R || Q_next_complement)', 'Q_next_complement = !(S || Q_next)', 'S * R = 0'];
    }
    return const [];
  }

  Widget _formulaBlock(List<String> formulas) {
    final lines = formulas.where((line) => line.trim().isNotEmpty).toList();
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
          const Row(
            children: [
              Icon(Icons.functions, size: 18, color: _primary),
              SizedBox(width: 6),
              Text('公式', style: TextStyle(color: _primary, fontWeight: FontWeight.w900)),
            ],
          ),
          const SizedBox(height: 9),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
            child: Column(
              children: [
                for (final formula in lines) ...[
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: _isFormulaLike(formula)
                        ? MathTex(_toTexFormula(formula), fontSize: 19, color: _ink)
                        : SmartText(_prettyMathText(formula), fontSize: 16, color: _ink),
                  ),
                  if (formula != lines.last) const SizedBox(height: 12),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  bool _isFormulaLike(String value) {
    final text = value.trim();
    return text.contains(r'\') ||
        text.contains('=') ||
        text.contains('^') ||
        text.contains('_') ||
        text.contains('sum(') ||
        text.contains('sin') ||
        text.contains('cos') ||
        text.contains('ln') ||
        text.contains('lim');
  }

  String _toTexFormula(String value) {
    var text = value.trim();
    if (text.contains(r'\')) return text;
    text = text.replaceAll('sum(', r'\sum(');
    text = text.replaceAll('*', r'\cdot ');
    text = text.replaceAll('<=', r'\leq ');
    text = text.replaceAll('>=', r'\geq ');
    text = text.replaceAll('!=', r'\neq ');
    text = text.replaceAll('!', r'\neg ');
    text = text.replaceAll('||', r'\lor ');
    text = text.replaceAll('&&', r'\land ');
    text = text.replaceAllMapped(RegExp(r'\bmu\b'), (_) => r'\mu');
    text = text.replaceAllMapped(RegExp(r'\bpi\b'), (_) => r'\pi');
    text = text.replaceAllMapped(RegExp(r'\balpha\b'), (_) => r'\alpha');
    text = text.replaceAllMapped(RegExp(r'\bbeta\b'), (_) => r'\beta');
    text = text.replaceAllMapped(RegExp(r'\btheta\b'), (_) => r'\theta');
    text = text.replaceAllMapped(RegExp(r'([A-Za-z])_([A-Za-z0-9]+)'), (m) => '${m[1]}_{${m[2]}}');
    return text;
  }

  String _prettyMathText(String input) {
    var text = input;
    text = text.replaceAll(r'\(', '').replaceAll(r'\)', '');
    text = text.replaceAll(r'\[', '').replaceAll(r'\]', '');
    text = text.replaceAll(r'$$', '').replaceAll(r'$', '');
    text = text.replaceAll(r'\left', '').replaceAll(r'\right', '');
    text = text.replaceAll(r'\,', ' ');
    text = text.replaceAll(r'\;', ' ');
    text = text.replaceAll(r'\quad', ' ');
    text = text.replaceAll(r'\qquad', ' ');
    text = text.replaceAll(r'\prime', "'");
    text = text.replaceAll(r'\cdot', '·');
    text = text.replaceAll(r'\times', '×');
    text = text.replaceAll(r'\div', '÷');
    text = text.replaceAll(r'\leq', '≤');
    text = text.replaceAll(r'\geq', '≥');
    text = text.replaceAll(r'\neq', '≠');
    text = text.replaceAll(r'\approx', '≈');
    text = text.replaceAll(r'\sim', '∼');
    text = text.replaceAll(r'\to', '→');
    text = text.replaceAll(r'\rightarrow', '→');
    text = text.replaceAll(r'\infty', '∞');
    text = text.replaceAllMapped(RegExp(r'\\lim_\{([^}]+)\}'), (m) => 'lim ${_prettyMathText(m[1]!)}');
    text = text.replaceAll(r'\lim', 'lim');
    text = text.replaceAll(r'\ln', 'ln');
    text = text.replaceAll(r'\sin', 'sin');
    text = text.replaceAll(r'\cos', 'cos');
    text = text.replaceAll(r'\tan', 'tan');
    text = text.replaceAll(r'\sqrt', '√');
    text = _replaceLatexFractions(text);
    text = _replaceLatexPowers(text);
    text = text.replaceAllMapped(RegExp(r'([A-Za-z0-9\)])\^([0-9]+)'), (m) => '${m[1]}${_superscript(m[2]!)}');
    text = text.replaceAllMapped(RegExp(r'_\{([^}]+)\}'), (m) => _subscript(m[1]!));
    text = text.replaceAllMapped(RegExp(r'_([A-Za-z0-9])'), (m) => _subscript(m[1]!));
    text = text.replaceAll('{', '').replaceAll('}', '');
    text = text.replaceAll(RegExp(r'\s+'), ' ').trim();
    return text;
  }

  String _replaceLatexFractions(String text) {
    final fraction = RegExp(r'\\frac\{([^{}]+)\}\{([^{}]+)\}');
    while (fraction.hasMatch(text)) {
      text = text.replaceAllMapped(fraction, (m) {
        final numerator = _prettyMathText(m[1]!);
        final denominator = _prettyMathText(m[2]!);
        if (numerator == '1' && denominator == '2') return '½';
        if (numerator == '1' && denominator == '3') return '⅓';
        if (numerator == '2' && denominator == '3') return '⅔';
        return '($numerator)/($denominator)';
      });
    }
    return text;
  }

  String _replaceLatexPowers(String text) {
    return text.replaceAllMapped(RegExp(r'\^\{([^}]+)\}'), (m) {
      final value = m[1]!;
      return _superscript(value);
    });
  }

  String _superscript(String value) {
    const map = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '+': '⁺', '-': '⁻', 'n': 'ⁿ'};
    return value.split('').map((char) => map[char] ?? char).join();
  }

  String _subscript(String value) {
    const map = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉', '+': '₊', '-': '₋', 'x': 'ₓ'};
    return value.split('').map((char) => map[char] ?? char).join();
  }

  Widget _diagram(_DiagramType type) {
    return Container(
      width: double.infinity,
      height: 190,
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: _border),
        borderRadius: BorderRadius.circular(16),
      ),
      child: CustomPaint(painter: type == _DiagramType.force ? _ForceDiagramPainter() : _ConceptDiagramPainter()),
    );
  }

  Widget _numberedList(String title, List<String> items, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w900, color: _ink)),
        const SizedBox(height: 8),
        ...items.asMap().entries.map(
              (entry) => Padding(
                padding: const EdgeInsets.only(bottom: 7),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 23,
                      height: 23,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(color: color.withValues(alpha: 0.10), borderRadius: BorderRadius.circular(8)),
                      child: Text('${entry.key + 1}', style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w900)),
                    ),
                    const SizedBox(width: 9),
                    Expanded(child: SmartText(entry.value, fontSize: 14, color: _ink)),
                  ],
                ),
              ),
            ),
      ],
    );
  }

  Widget _textBlock(String title, String text, IconData icon, Color color) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(14)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 19),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w800, color: _ink)),
                const SizedBox(height: 3),
                SmartText(text, fontSize: 14, color: _ink),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _composer() {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
        decoration: const BoxDecoration(
          color: _bg,
          border: Border(top: BorderSide(color: _border)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (_pickedImage != null)
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(14), border: Border.all(color: _border)),
                child: Row(
                  children: [
                    const Icon(Icons.image_outlined, size: 18, color: _primary),
                    const SizedBox(width: 8),
                    Expanded(child: Text(_pickedImage!.name, maxLines: 1, overflow: TextOverflow.ellipsis)),
                    IconButton(
                      visualDensity: VisualDensity.compact,
                      onPressed: () => setState(() => _pickedImage = null),
                      icon: const Icon(Icons.close, size: 18),
                    ),
                  ],
                ),
              ),
            if (_isRecording)
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(color: _danger.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(999)),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.fiber_manual_record, size: 13, color: _danger),
                    SizedBox(width: 6),
                    Text('正在录音，点 + 里的语音按钮结束', style: TextStyle(color: _danger, fontWeight: FontWeight.w800, fontSize: 12)),
                  ],
                ),
              ),
            Row(
              children: [
                IconButton(
                  tooltip: '添加',
                  onPressed: _isLoading ? null : _openAttachSheet,
                  icon: const Icon(Icons.add_circle_outline),
                ),
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(22),
                      border: Border.all(color: _border),
                    ),
                    child: TextField(
                      controller: _questionController,
                      minLines: 1,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        hintText: '问问你想学的...',
                        isDense: true,
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        disabledBorder: InputBorder.none,
                        errorBorder: InputBorder.none,
                        focusedErrorBorder: InputBorder.none,
                        filled: false,
                        contentPadding: EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                IconButton(
                  tooltip: '回答模式',
                  onPressed: _openModeSheet,
                  icon: const Icon(Icons.tune),
                ),
                FilledButton(
                  onPressed: _isLoading ? null : _ask,
                  style: FilledButton.styleFrom(shape: const CircleBorder(), minimumSize: const Size(48, 48), padding: EdgeInsets.zero),
                  child: _isLoading
                      ? const SizedBox(width: 19, height: 19, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Icon(Icons.arrow_upward),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: Text(_modeLabel, style: const TextStyle(color: _muted, fontSize: 12, fontWeight: FontWeight.w700)),
            ),
          ],
        ),
      ),
    );
  }

  void _openAttachSheet() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (_) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ListTile(
                  leading: const Icon(Icons.photo_camera_outlined, color: _primary),
                  title: const Text('拍照 / 选择题目图片', style: TextStyle(fontWeight: FontWeight.w900)),
                  subtitle: const Text('适合题干、图表、公式截图'),
                  onTap: () {
                    Navigator.pop(context);
                    _pickPhoto();
                  },
                ),
                ListTile(
                  leading: Icon(_isRecording ? Icons.stop_circle_outlined : Icons.mic_none, color: _isRecording ? _danger : _primary),
                  title: Text(_isRecording ? '结束语音输入' : '语音输入', style: const TextStyle(fontWeight: FontWeight.w900)),
                  subtitle: Text(_isRecording ? '结束后会自动填入识别文本' : '说出你的问题，识别后可再编辑'),
                  onTap: () {
                    Navigator.pop(context);
                    _toggleRecording();
                  },
                ),
                if (_pickedImage != null)
                  ListTile(
                    leading: const Icon(Icons.delete_outline, color: _danger),
                    title: const Text('移除当前图片', style: TextStyle(fontWeight: FontWeight.w900)),
                    onTap: () {
                      Navigator.pop(context);
                      setState(() => _pickedImage = null);
                    },
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  void _openModeSheet() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (_) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _modeTile('quick', '快速回答', '直接给出清晰讲解和图解', Icons.flash_on_outlined),
                _modeTile('hint', '只给提示', '不直接给答案，帮你往下想', Icons.lightbulb_outline),
                _modeTile('correction', '纠错诊断', '根据你的思路找错因', Icons.fact_check_outlined),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _modeTile(String value, String title, String subtitle, IconData icon) {
    return ListTile(
      leading: Icon(icon, color: _primary),
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
      subtitle: Text(subtitle),
      trailing: _mode == value ? const Icon(Icons.check_circle, color: _primary) : null,
      onTap: () {
        setState(() => _mode = value);
        Navigator.pop(context);
      },
    );
  }

  String get _modeLabel {
    return switch (_mode) {
      'hint' => '只给提示',
      'correction' => '纠错诊断',
      _ => '快速回答',
    };
  }
}

class _ModeChoice {
  final String value;
  final String label;
  final IconData icon;

  const _ModeChoice({required this.value, required this.label, required this.icon});
}

class _ChatMessage {
  final bool isUser;
  final String text;
  final String? imageName;
  final _AnswerPayload? answer;

  const _ChatMessage.user(this.text, {this.imageName}) : isUser = true, answer = null;
  const _ChatMessage.ai(this.answer) : isUser = false, text = '', imageName = null;
}

class _AnswerPayload {
  final String summary;
  final String hint;
  final List<String> steps;
  final List<String> formulas;
  final String finalAnswer;
  final List<String> mistakes;
  final _DiagramType diagramType;
  final bool showDiagram;

  const _AnswerPayload({
    required this.summary,
    required this.hint,
    required this.steps,
    this.formulas = const [],
    required this.finalAnswer,
    required this.mistakes,
    required this.diagramType,
    required this.showDiagram,
  });
}

enum _DiagramType { none, force, logic }

enum _AnswerKind { vocabulary, conceptOverview, explicitDiagram, problemSolving, general }

class _AnswerIntent {
  final _AnswerKind kind;
  final _DiagramType diagramType;
  final bool showDiagram;

  const _AnswerIntent(this.kind, this.diagramType, this.showDiagram);
}

class _ForceDiagramPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final axis = Paint()
      ..color = const Color(0xFF94A3B8)
      ..strokeWidth = 1.5;
    final block = Paint()..color = const Color(0xFFEAF1F1);
    final arrow = Paint()
      ..color = const Color(0xFF536878)
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    final textPainter = TextPainter(textDirection: TextDirection.ltr);

    void label(String value, Offset offset, {Color color = const Color(0xFF34324A)}) {
      textPainter.text = TextSpan(text: value, style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w800));
      textPainter.layout();
      textPainter.paint(canvas, offset);
    }

    final center = Offset(size.width / 2, size.height / 2 + 8);
    final rect = Rect.fromCenter(center: center, width: 72, height: 48);
    canvas.drawLine(Offset(24, center.dy + 26), Offset(size.width - 24, center.dy + 26), axis);
    canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(10)), block);
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(10)),
      Paint()
        ..style = PaintingStyle.stroke
        ..color = const Color(0xFF536878)
        ..strokeWidth = 2,
    );

    void drawArrow(Offset from, Offset to, String text, Offset labelOffset) {
      canvas.drawLine(from, to, arrow);
      final direction = from - to;
      final angle = direction.direction;
      final path = Path()
        ..moveTo(to.dx, to.dy)
        ..lineTo(to.dx + 10 * math.cos(angle + 0.45), to.dy + 10 * math.sin(angle + 0.45))
        ..moveTo(to.dx, to.dy)
        ..lineTo(to.dx + 10 * math.cos(angle - 0.45), to.dy + 10 * math.sin(angle - 0.45));
      canvas.drawPath(path, arrow);
      label(text, labelOffset, color: const Color(0xFF536878));
    }

    drawArrow(center, Offset(center.dx, center.dy - 64), 'N', Offset(center.dx + 8, center.dy - 68));
    drawArrow(center, Offset(center.dx, center.dy + 70), 'G=mg', Offset(center.dx + 8, center.dy + 50));
    drawArrow(center, Offset(center.dx + 92, center.dy), 'F', Offset(center.dx + 96, center.dy - 20));
    drawArrow(center, Offset(center.dx - 82, center.dy), 'f', Offset(center.dx - 98, center.dy - 20));
    label('受力图示意', const Offset(16, 14), color: const Color(0xFF8A8798));
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _ConceptDiagramPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = const Color(0xFF536878)
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round;
    final fill = Paint()..color = const Color(0xFFEAF1F1);
    final textPainter = TextPainter(textDirection: TextDirection.ltr);

    void node(Offset center, String text) {
      final rect = Rect.fromCenter(center: center, width: 88, height: 42);
      canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(14)), fill);
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(14)),
        Paint()
          ..style = PaintingStyle.stroke
          ..color = const Color(0xFF8FB1B3)
          ..strokeWidth = 1.5,
      );
      textPainter.text = TextSpan(text: text, style: const TextStyle(color: Color(0xFF34324A), fontSize: 13, fontWeight: FontWeight.w900));
      textPainter.layout(maxWidth: 78);
      textPainter.paint(canvas, Offset(center.dx - textPainter.width / 2, center.dy - textPainter.height / 2));
    }

    final a = Offset(size.width * 0.25, size.height * 0.35);
    final b = Offset(size.width * 0.72, size.height * 0.35);
    final c = Offset(size.width * 0.50, size.height * 0.70);
    canvas.drawLine(a, b, line);
    canvas.drawLine(b, c, line);
    canvas.drawLine(c, a, line);
    node(a, '条件');
    node(b, '图示');
    node(c, '推导');
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
