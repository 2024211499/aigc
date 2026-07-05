import 'package:flutter_test/flutter_test.dart';
import 'package:aigc_app/main.dart';

void main() {
  testWidgets('App should build without errors', (WidgetTester tester) async {
    await tester.pumpWidget(const AigcApp());
    expect(find.text('AIGC 教学助手'), findsOneWidget);
  });
}
