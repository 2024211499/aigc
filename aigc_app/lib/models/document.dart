class Document {
  final String id;
  final String fileName;
  final String parseStatus;
  final String? courseId;
  final String? fileUrl;
  final String? fileType;
  final int? fileSize;
  final int? chapterCount;
  final int? kpCount;

  Document({
    required this.id,
    required this.fileName,
    required this.parseStatus,
    this.courseId,
    this.fileUrl,
    this.fileType,
    this.fileSize,
    this.chapterCount,
    this.kpCount,
  });

  factory Document.fromJson(Map<String, dynamic> json) {
    return Document(
      id: json['id']?.toString() ?? json['document_id']?.toString() ?? '',
      fileName: json['file_name']?.toString() ?? '',
      parseStatus: json['parse_status']?.toString() ?? 'uploaded',
      courseId: json['course_id']?.toString(),
      fileUrl: json['file_url']?.toString(),
      fileType: json['file_type']?.toString(),
      fileSize: json['file_size'] as int?,
      chapterCount: json['chapter_count'] as int?,
      kpCount: json['kp_count'] as int?,
    );
  }

  bool get isCompleted => parseStatus == 'completed';
  bool get isFailed => parseStatus == 'failed';
  bool get isProcessing => !isCompleted && !isFailed;
}
