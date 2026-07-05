import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';

/// Renders LaTeX math expressions with proper typography.
/// Falls back to plain text if parsing fails.
class MathTex extends StatelessWidget {
  final String formula;
  final double fontSize;
  final Color? color;
  final bool inline;

  const MathTex(
    this.formula, {
    super.key,
    this.fontSize = 14,
    this.color,
    this.inline = false,
  });

  @override
  Widget build(BuildContext context) {
    final textColor = color ?? Theme.of(context).textTheme.bodyLarge?.color ?? Colors.black87;
    final normalized = _normalizeFormula(formula);
    try {
      return Math.tex(
        normalized,
        textStyle: TextStyle(fontSize: fontSize, color: textColor),
      );
    } catch (_) {
      return Text(
        normalized,
        style: TextStyle(
          fontSize: fontSize,
          color: textColor,
          height: 1.5,
        ),
      );
    }
  }

  String _normalizeFormula(String value) {
    var text = value.trim();
    if (text.startsWith(r'\(') && text.endsWith(r'\)')) {
      text = text.substring(2, text.length - 2);
    } else if (text.startsWith(r'\[') && text.endsWith(r'\]')) {
      text = text.substring(2, text.length - 2);
    } else if (text.startsWith(r'$$') && text.endsWith(r'$$')) {
      text = text.substring(2, text.length - 2);
    } else if (text.startsWith(r'$') && text.endsWith(r'$') && text.length > 1) {
      text = text.substring(1, text.length - 1);
    }
    return text.trim();
  }
}

/// Detects if a string contains LaTeX math delimiters.
bool isLatex(String text) {
  return text.contains(r'\(') ||
      text.contains(r'\)') ||
      text.contains(r'\[') ||
      text.contains(r'\]') ||
      text.contains(r'$$') ||
      text.contains(r'\frac') ||
      text.contains(r'\lim') ||
      text.contains(r'\int') ||
      text.contains(r'\sum') ||
      text.contains(r'\sqrt') ||
      text.startsWith(r'\frac') ||
      text.startsWith(r'\int') ||
      text.startsWith(r'\sum') ||
      text.contains(r'\sqrt');
}

/// Renders a text block that may contain inline LaTeX.
/// Falls back to plain Text if no LaTeX detected.
class SmartText extends StatelessWidget {
  final String text;
  final double fontSize;
  final Color? color;

  const SmartText(this.text, {super.key, this.fontSize = 14, this.color});

  @override
  Widget build(BuildContext context) {
    final segments = _splitInlineMath(text);
    if (segments.length == 1 && segments.first.isMath) {
      return MathTex(text, fontSize: fontSize, color: color);
    }
    if (segments.any((segment) => segment.isMath)) {
      return Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          for (final segment in segments)
            segment.isMath
                ? Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 2),
                    child: MathTex(segment.text, fontSize: fontSize, color: color, inline: true),
                  )
                : Text(segment.text, style: TextStyle(fontSize: fontSize, color: color, height: 1.5)),
        ],
      );
    }
    if (isLatex(text)) {
      return MathTex(text, fontSize: fontSize, color: color);
    }
    return Text(
      text,
      style: TextStyle(fontSize: fontSize, color: color, height: 1.5),
    );
  }

  List<_MathSegment> _splitInlineMath(String value) {
    final matches = RegExp(r'\\\((.+?)\\\)|\\\[(.+?)\\\]').allMatches(value).toList();
    if (matches.isEmpty) return [_MathSegment(value, false)];

    final segments = <_MathSegment>[];
    var start = 0;
    for (final match in matches) {
      if (match.start > start) {
        segments.add(_MathSegment(value.substring(start, match.start), false));
      }
      segments.add(_MathSegment(match.group(1) ?? match.group(2) ?? '', true));
      start = match.end;
    }
    if (start < value.length) {
      segments.add(_MathSegment(value.substring(start), false));
    }
    return segments.where((segment) => segment.text.isNotEmpty).toList();
  }
}

class _MathSegment {
  final String text;
  final bool isMath;

  const _MathSegment(this.text, this.isMath);
}
