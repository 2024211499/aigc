import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:file_picker/file_picker.dart';
import '../config/api_config.dart';
import '../models/course.dart';
import '../models/document.dart';
import '../models/chapter.dart';
import '../models/exercise.dart';

class ApiService {
  final http.Client _client = http.Client();

  String get _base => ApiConfig.baseUrl;
  Map<String, String> get _jsonHeader => {
        'Content-Type': 'application/json',
      };

  // ─── helpers ───

  Map<String, dynamic> _unwrap(Map<String, dynamic> body) {
    return body;
  }

  List<dynamic> _extractList(Map<String, dynamic> body) {
    // response: { success: true, <plural_key>: [...] }
    const possibleKeys = [
      'courses', 'documents', 'knowledge_points', 'chapters',
      'exercises', 'mistakes', 'study_plans', 'plans',
      'exam_papers', 'variants', 'learning_logs',
    ];
    for (final key in possibleKeys) {
      if (body.containsKey(key) && body[key] is List) {
        return body[key] as List<dynamic>;
      }
    }
    // fallback: look for any list value
    for (final v in body.values) {
      if (v is List) return v;
    }
    return [];
  }

  Future<Map<String, dynamic>> _get(String path) async {
    final uri = Uri.parse('$_base$path');
    final resp = await _client.get(uri).timeout(ApiConfig.timeout);
    if (resp.statusCode >= 400) {
      throw ApiException(resp.statusCode, _parseError(resp.body));
    }
    final body = jsonDecode(resp.body) as Map<String, dynamic>;
    return _unwrap(body);
  }

  Future<List<dynamic>> _getList(String path) async {
    final body = await _get(path);
    return _extractList(body);
  }

  Future<Map<String, dynamic>> _post(
      String path, Map<String, dynamic> body,
      {Duration? timeout}) async {
    final uri = Uri.parse('$_base$path');
    final resp = await _client
        .post(uri, headers: _jsonHeader, body: jsonEncode(body))
        .timeout(timeout ?? ApiConfig.timeout);
    if (resp.statusCode >= 400) {
      throw ApiException(resp.statusCode, _parseError(resp.body));
    }
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    return _unwrap(data);
  }

  Future<Map<String, dynamic>> _delete(String path) async {
    final uri = Uri.parse('$_base$path');
    final resp = await _client.delete(uri).timeout(ApiConfig.timeout);
    if (resp.statusCode >= 400) {
      throw ApiException(resp.statusCode, _parseError(resp.body));
    }
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    return _unwrap(data);
  }

  String _parseError(String body) {
    try {
      final j = jsonDecode(body);
      return j['detail']?.toString() ?? j['error']?.toString() ?? 'Unknown error';
    } catch (_) {
      return 'HTTP ${body.length > 100 ? body.substring(0, 100) : body}';
    }
  }

  // ─── Courses ───
  Future<List<Course>> getCourses() async {
    final data = await _getList('/api/courses');
    return data.map((e) => Course.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> createCourse(String name, {String? description}) async {
    return _post('/api/courses', {
      'name': name,
      if (description != null) 'description': description,
    });
  }

  Future<Map<String, dynamic>> getCourseDetail(String id) async {
    return _get('/api/courses/$id');
  }

  // ─── Documents ───
  Future<List<Document>> getDocuments() async {
    final data = await _getList('/api/documents');
    return data
        .map((e) => Document.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, dynamic>> uploadDocument(PlatformFile file) async {
    final uri = Uri.parse('$_base/api/upload');
    final request = http.MultipartRequest('POST', uri);
    if (file.path != null) {
      request.files.add(await http.MultipartFile.fromPath('file', file.path!));
    }
    final streamed = await request.send().timeout(const Duration(seconds: 300));
    final resp = await http.Response.fromStream(streamed);
    if (resp.statusCode >= 400) {
      throw ApiException(resp.statusCode, _parseError(resp.body));
    }
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    return _unwrap(data);
  }

  Future<Map<String, dynamic>> getDocumentStatus(String docId) async {
    return _get('/api/documents/$docId/status');
  }

  Future<Map<String, dynamic>> getDocumentReport(String docId) async {
    return _get('/api/documents/$docId/report');
  }

  Future<void> deleteDocument(String docId) async {
    await _delete('/api/documents/$docId');
  }

  // ─── Chapters & Knowledge Points ───
  Future<List<Chapter>> getChapters(String courseId) async {
    final data = await _getList('/api/courses/$courseId/chapters');
    return data
        .map((e) => Chapter.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, dynamic>> getChapterDetail(String chapterId) async {
    return _get('/api/chapters/$chapterId');
  }

  // ─── Learning Package ───
  Future<Map<String, dynamic>> generateLearningPackage({
    required String courseId,
    String learningGoal = '系统学习',
    int studyDays = 7,
    int dailyMinutes = 45,
    String studentLevel = '中等',
  }) async {
    return _post('/api/learning-package/generate', {
      'course_id': courseId,
      'learning_goal': learningGoal,
      'study_days': studyDays,
      'daily_minutes': dailyMinutes,
      'student_level': studentLevel,
    }, timeout: ApiConfig.generationTimeout);
  }

  // ─── Quick Answer / Homework Tutor ───
  Future<Map<String, dynamic>> quickAnswer({
    required String question,
    String studentAnswer = '',
    String mode = 'step_by_step',
    List<String> fragments = const [],
    String? imageBase64,
  }) async {
    return _post('/api/homework/tutor', {
      'question': question,
      'student_answer': studentAnswer,
      'mode': mode,
      'fragments': fragments,
      if (imageBase64 != null) 'image_base64': imageBase64,
    }, timeout: ApiConfig.generationTimeout);
  }

  // ─── Exercises ───
  Future<Map<String, dynamic>> generateExercises({
    required String courseId,
    String chapterId = '',
    String knowledgePoint = '',
    List<String> questionTypes = const ['choice', 'calc'],
    String difficulty = 'medium',
    int count = 5,
  }) async {
    return _post('/api/exercises/generate', {
      'course_id': courseId,
      'chapter_id': chapterId,
      'knowledge_point': knowledgePoint,
      'question_types': questionTypes,
      'difficulty': difficulty,
      'count': count,
    }, timeout: ApiConfig.generationTimeout);
  }

  Future<Map<String, dynamic>> getExercise(String exerciseId) async {
    return _get('/api/exercises/$exerciseId');
  }

  Future<Map<String, dynamic>> submitAnswer({
    required String exerciseId,
    required String studentAnswer,
    String userId = 'anonymous',
    int timeSpentSec = 0,
  }) async {
    return _post('/api/exercises/submit', {
      'exercise_id': exerciseId,
      'student_answer': studentAnswer,
      'user_id': userId,
      'time_spent_sec': timeSpentSec,
    }, timeout: ApiConfig.generationTimeout);
  }

  Future<Map<String, dynamic>> homeworkDiagnose({
    required String question,
    required String studentAnswer,
    String mode = 'correction',
  }) async {
    return _post('/api/homework/diagnose', {
      'question': question,
      'student_answer': studentAnswer,
      'mode': mode,
    }, timeout: ApiConfig.generationTimeout);
  }

  // ─── Mistakes ───
  Future<List<Mistake>> getMistakes({String userId = 'anonymous'}) async {
    final data = await _getList('/api/mistakes?user_id=$userId');
    return data
        .map((e) => Mistake.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, dynamic>> reviewMistake(String mistakeId) async {
    return _post('/api/mistakes/$mistakeId/review', {});
  }

  Future<Map<String, dynamic>> markMistakeMastered(String mistakeId) async {
    return _post('/api/mistakes/$mistakeId/mastered', {});
  }

  // ─── Exam ───
  Future<Map<String, dynamic>> generateExam({
    required String courseId,
    String examType = '单元测试',
    int totalQuestions = 20,
    int durationMinutes = 90,
  }) async {
    return _post('/api/exam/generate', {
      'course_id': courseId,
      'exam_type': examType,
      'total_questions': totalQuestions,
      'duration_minutes': durationMinutes,
    }, timeout: ApiConfig.generationTimeout);
  }

  Future<Map<String, dynamic>> getExam(String examId) async {
    return _get('/api/exam/$examId');
  }

  // ─── Explanation ───
  Future<Map<String, dynamic>> generateExplanation({
    required String courseId,
    required String knowledgePoint,
    String style = 'textbook',
    String userLevel = '中等',
  }) async {
    return _post('/api/explanation/generate', {
      'course_id': courseId,
      'knowledge_point': knowledgePoint,
      'explanation_style': style,
      'user_level': userLevel,
    }, timeout: ApiConfig.generationTimeout);
  }

  // ─── Micro-Lesson ───
  Future<Map<String, dynamic>> generateMicroLessonScript({
    required String courseId,
    required String topic,
    String style = '讲解式',
    int durationSeconds = 300,
  }) async {
    return _post('/api/micro-lesson/script', {
      'course_id': courseId,
      'topic': topic,
      'style': style,
      'duration_seconds': durationSeconds,
    }, timeout: ApiConfig.generationTimeout);
  }

  // ─── Profile ───
  Future<Map<String, dynamic>> getProfile(String userId) async {
    return _get('/api/profile/$userId');
  }

  Future<void> logLearningAction({
    required String userId,
    required String action,
    Map<String, dynamic> detail = const {},
    int durationSec = 0,
  }) async {
    await _post('/api/learning-log', {
      'user_id': userId,
      'action': action,
      'detail': detail,
      'duration_sec': durationSec,
    });
  }

  // ─── Dashboard ───
  Future<Map<String, dynamic>> getStudentDashboard(String userId) async {
    return _get('/api/dashboard/student/$userId');
  }

  // ─── Voice ASR ───
  Future<Map<String, dynamic>> voiceAsr(List<int> audioBytes, String filename) async {
    final uri = Uri.parse('$_base/api/voice/asr');
    final request = http.MultipartRequest('POST', uri);
    request.files.add(http.MultipartFile.fromBytes(
      'audio', audioBytes, filename: filename));
    final streamed = await request.send().timeout(const Duration(seconds: 60));
    final resp = await http.Response.fromStream(streamed);
    if (resp.statusCode >= 400) {
      throw ApiException(resp.statusCode, _parseError(resp.body));
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  // ─── Text Similarity ───
  Future<Map<String, dynamic>> textSimilarity(String textA, String textB) async {
    return _post('/api/text/similarity', {
      'text_a': textA,
      'text_b': textB,
    });
  }

  void dispose() {
    _client.close();
  }
}

class ApiException implements Exception {
  final int statusCode;
  final String message;

  ApiException(this.statusCode, this.message);

  @override
  String toString() => message;
}
