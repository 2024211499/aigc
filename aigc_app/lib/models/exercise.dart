class Exercise {
  final String id;
  final String type;
  final String question;
  final String? date;
  final String? difficulty;
  final List<String>? options;
  final String? answer;
  final String? explanation;
  final String? mistakeTip;

  const Exercise({
    required this.id,
    required this.type,
    required this.question,
    this.date,
    this.difficulty,
    this.options,
    this.answer,
    this.explanation,
    this.mistakeTip,
  });

  factory Exercise.fromJson(Map<String, dynamic> json) {
    return Exercise(
      id: json['id']?.toString() ?? '',
      type: json['question_type']?.toString() ?? json['type']?.toString() ?? '',
      question: json['stem']?.toString() ?? json['question']?.toString() ?? '',
      date: json['date']?.toString() ?? json['created_at']?.toString(),
      difficulty: json['difficulty']?.toString(),
      options:
          (json['options'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList(),
      answer: json['answer']?.toString(),
      explanation: json['explanation']?.toString(),
      mistakeTip: json['mistake_tip']?.toString(),
    );
  }
}

class Mistake {
  final String id;
  final String exerciseId;
  final String stem;
  final String questionType;
  final String errorType;
  final String errorReason;
  final bool mastered;
  final int reviewCount;
  final String? createdAt;

  const Mistake({
    required this.id,
    this.exerciseId = '',
    required this.stem,
    this.questionType = '',
    this.errorType = '',
    this.errorReason = '',
    this.mastered = false,
    this.reviewCount = 0,
    this.createdAt,
  });

  factory Mistake.fromJson(Map<String, dynamic> json) {
    return Mistake(
      id: json['id']?.toString() ?? '',
      exerciseId: json['exercise_id']?.toString() ?? '',
      stem: json['stem']?.toString() ?? json['question']?.toString() ?? '',
      questionType: json['question_type']?.toString() ?? '',
      errorType: json['error_type']?.toString() ?? '',
      errorReason: json['error_reason']?.toString() ?? '',
      mastered: (json['mastered'] is bool) ? json['mastered'] as bool : false,
      reviewCount:
          (json['review_count'] is int) ? json['review_count'] as int : 0,
      createdAt: json['created_at']?.toString(),
    );
  }
}
