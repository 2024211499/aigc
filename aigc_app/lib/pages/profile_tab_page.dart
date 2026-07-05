import 'package:flutter/material.dart';
import 'profile_page.dart';

class ProfileTabPage extends StatelessWidget {
  const ProfileTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('我的学习')),
      body: const ProfilePage(),
    );
  }
}
