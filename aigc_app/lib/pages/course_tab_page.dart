import 'package:flutter/material.dart';

import '../models/course.dart';
import '../services/api_service.dart';
import 'course_mode_page.dart';
import 'learning_page.dart';
import 'library_page.dart';

class CourseTabPage extends StatefulWidget {
  const CourseTabPage({super.key});

  @override
  State<CourseTabPage> createState() => _CourseTabPageState();
}

class _CourseTabPageState extends State<CourseTabPage> {
  final _api = ApiService();
  int _index = 0;
  Course? _activeCourse;
  bool _isLoadingCourse = true;

  @override
  void initState() {
    super.initState();
    _loadActiveCourse();
  }

  @override
  void dispose() {
    _api.dispose();
    super.dispose();
  }

  Future<void> _loadActiveCourse() async {
    setState(() => _isLoadingCourse = true);
    try {
      final courses = await _api.getCourses();
      final parsed =
          courses.where((course) => (course.chapterCount ?? 0) > 0).toList();
      _activeCourse =
          courses.isEmpty
              ? null
              : (parsed.isNotEmpty ? parsed.first : courses.first);
    } catch (_) {
      _activeCourse = null;
    } finally {
      if (mounted) setState(() => _isLoadingCourse = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      CourseModePage(onCourseChanged: _loadActiveCourse),
      LibraryPage(onChanged: _loadActiveCourse),
      _LearningEntry(
        isLoading: _isLoadingCourse,
        course: _activeCourse,
        onRefresh: _loadActiveCourse,
      ),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('学习流程'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(56),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
            child: SegmentedButton<int>(
              selected: {_index},
              showSelectedIcon: false,
              onSelectionChanged:
                  (value) => setState(() {
                    _index = value.first;
                    if (_index == 2) _loadActiveCourse();
                  }),
              segments: const [
                ButtonSegment(
                  value: 0,
                  icon: Icon(Icons.route_outlined, size: 18),
                  label: Text('规划'),
                ),
                ButtonSegment(
                  value: 1,
                  icon: Icon(Icons.folder_open_outlined, size: 18),
                  label: Text('资料'),
                ),
                ButtonSegment(
                  value: 2,
                  icon: Icon(Icons.menu_book_outlined, size: 18),
                  label: Text('学习'),
                ),
              ],
            ),
          ),
        ),
      ),
      body: IndexedStack(index: _index, children: pages),
    );
  }
}

class _LearningEntry extends StatelessWidget {
  final bool isLoading;
  final Course? course;
  final Future<void> Function() onRefresh;

  const _LearningEntry({
    required this.isLoading,
    required this.course,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (course == null) {
      return RefreshIndicator(
        onRefresh: onRefresh,
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: const [
            SizedBox(height: 80),
            Icon(
              Icons.folder_open_outlined,
              size: 56,
              color: Color(0xFF7C7A8A),
            ),
            SizedBox(height: 16),
            Text(
              '还没有可学习的资料',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
            ),
            SizedBox(height: 8),
            Text(
              '先到“资料”上传并解析教材或课件，再进入学习空间。',
              textAlign: TextAlign.center,
              style: TextStyle(color: Color(0xFF7C7A8A), height: 1.5),
            ),
          ],
        ),
      );
    }
    return LearningPage(courseId: course!.id, courseName: course!.name);
  }
}
