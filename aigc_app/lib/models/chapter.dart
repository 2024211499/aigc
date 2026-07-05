class Chapter {
  final String id;
  final String title;
  final String? chapterNumber;
  final String? intro;
  final List<KnowledgePoint> points;

  Chapter({
    required this.id,
    required this.title,
    this.chapterNumber,
    this.intro,
    this.points = const [],
  });

  factory Chapter.fromJson(Map<String, dynamic> json) {
    return Chapter(
      id: json['id']?.toString() ?? '',
      title: json['chapter_name']?.toString() ??
          json['title']?.toString() ??
          json['name']?.toString() ??
          '未命名章节',
      chapterNumber: json['chapter_number']?.toString(),
      intro: json['intro']?.toString() ?? json['chapter_intro']?.toString(),
      points: (json['points'] as List<dynamic>?)
              ?.map((item) => KnowledgePoint.fromJson(item as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

class KnowledgePoint {
  final String id;
  final String label;
  final String content;
  final String? formula;
  final String? type;
  final String? difficulty;

  KnowledgePoint({
    this.id = '',
    required this.label,
    required this.content,
    this.formula,
    this.type,
    this.difficulty,
  });

  factory KnowledgePoint.fromJson(Map<String, dynamic> json) {
    return KnowledgePoint(
      id: json['id']?.toString() ?? '',
      label: json['name']?.toString() ?? json['label']?.toString() ?? '',
      content: json['definition']?.toString() ??
          json['content']?.toString() ??
          json['description']?.toString() ??
          '',
      formula: json['formula']?.toString(),
      type: json['type']?.toString() ?? json['kp_type']?.toString(),
      difficulty: json['difficulty']?.toString(),
    );
  }
}
