class Course {
  final String id;
  final String name;
  final String? description;
  final int? chapterCount;

  Course({
    required this.id,
    required this.name,
    this.description,
    this.chapterCount,
  });

  factory Course.fromJson(Map<String, dynamic> json) {
    return Course(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? json['title']?.toString() ?? '',
      description: json['description'] as String?,
      chapterCount: json['chapter_count'] as int?,
    );
  }
}
