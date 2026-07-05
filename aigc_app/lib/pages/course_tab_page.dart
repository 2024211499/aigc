import 'package:flutter/material.dart';

import 'course_mode_page.dart';
import 'learning_page.dart';
import 'library_page.dart';

class CourseTabPage extends StatefulWidget {
  const CourseTabPage({super.key});

  @override
  State<CourseTabPage> createState() => _CourseTabPageState();
}

class _CourseTabPageState extends State<CourseTabPage> {
  int _index = 0;

  final _pages = const [
    CourseModePage(),
    LibraryPage(),
    LearningPage(),
  ];

  @override
  Widget build(BuildContext context) {
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
              onSelectionChanged: (value) => setState(() => _index = value.first),
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
      body: IndexedStack(index: _index, children: _pages),
    );
  }
}
