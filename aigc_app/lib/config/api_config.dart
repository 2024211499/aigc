import 'dart:io' show Platform;

class ApiConfig {
  ApiConfig._();

  static String get baseUrl {
    if (Platform.isAndroid) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://localhost:8000';
  }

  // CRUD 等轻量操作
  static const timeout = Duration(seconds: 60);
  // LLM 生成类操作（学习包、组卷、答疑）可能串行调用多个 Agent
  static const generationTimeout = Duration(seconds: 240);
}
