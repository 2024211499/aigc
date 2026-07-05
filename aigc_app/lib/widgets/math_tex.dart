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
    final textColor =
        color ?? Theme.of(context).textTheme.bodyLarge?.color ?? Colors.black87;
    final normalized = _normalizeFormula(formula);
    try {
      return Math.tex(
        normalized,
        textStyle: TextStyle(fontSize: fontSize, color: textColor),
      );
    } catch (_) {
      return Text(
        normalized,
        style: TextStyle(fontSize: fontSize, color: textColor, height: 1.5),
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
    } else if (text.startsWith(r'$') &&
        text.endsWith(r'$') &&
        text.length > 1) {
      text = text.substring(1, text.length - 1);
    }
    return _normalizeLooseFormula(text.replaceAll(r'$', '').trim());
  }

  String _normalizeLooseFormula(String value) {
    var text = value.trim();
    text = text.replaceAll('∫', r'\int ');
    text = text.replaceAll('√', r'\sqrt');
    text = text.replaceAll('≤', r'\leq ');
    text = text.replaceAll('≥', r'\geq ');
    text = text.replaceAll('·', r'\cdot ');
    text = text.replaceAll('*', r'\cdot ');
    text = text.replaceAllMapped(
      RegExp(r'\be\^\(([^)]+)\)'),
      (m) => 'e^{${m[1]}}',
    );
    text = text.replaceAllMapped(
      RegExp(r'\be\^([A-Za-z0-9]+)'),
      (m) => 'e^{${m[1]}}',
    );
    text = text.replaceAllMapped(
      RegExp(r'([A-Za-z0-9])\^\(([^)]+)\)'),
      (m) => '${m[1]}^{${m[2]}}',
    );
    text = text.replaceAllMapped(
      RegExp(r'([A-Za-z0-9])\^([A-Za-z0-9]+)'),
      (m) => '${m[1]}^{${m[2]}}',
    );
    text = text.replaceAllMapped(
      RegExp(r'([A-Za-z])_([A-Za-z0-9]+)'),
      (m) => '${m[1]}_{${m[2]}}',
    );
    text = text.replaceAllMapped(
      RegExp(r'_(\d+)\^(\d+)'),
      (m) => '_{${m[1]}}^{${m[2]}}',
    );
    return text;
  }
}

/// Detects if a string contains LaTeX math delimiters.
bool isLatex(String text) {
  return text.contains(r'\(') ||
      text.contains(r'\)') ||
      text.contains(r'\[') ||
      text.contains(r'\]') ||
      text.contains(r'$$') ||
      text.contains(r'$') ||
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
      return _scrollableMath(segments.first.text);
    }
    if (segments.any((segment) => segment.isMath)) {
      return LayoutBuilder(
        builder: (context, constraints) {
          return Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              for (final segment in segments)
                segment.isMath
                    ? ConstrainedBox(
                      constraints: BoxConstraints(
                        maxWidth:
                            constraints.maxWidth.isFinite
                                ? constraints.maxWidth
                                : 320,
                      ),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 2),
                        child: _scrollableMath(segment.text),
                      ),
                    )
                    : Text(
                      segment.text,
                      style: TextStyle(
                        fontSize: fontSize,
                        color: color,
                        height: 1.5,
                      ),
                    ),
            ],
          );
        },
      );
    }
    if (isLatex(text)) {
      return _scrollableMath(text);
    }
    return Text(
      text,
      style: TextStyle(fontSize: fontSize, color: color, height: 1.5),
    );
  }

  Widget _scrollableMath(String formula) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      physics: const BouncingScrollPhysics(),
      child: MathTex(formula, fontSize: fontSize, color: color, inline: true),
    );
  }

  List<_MathSegment> _splitInlineMath(String value) {
    final matches =
        RegExp(
          r'\$\$(.+?)\$\$|\\\((.+?)\\\)|\\\[(.+?)\\\]|\$([^$]+)\$',
          dotAll: true,
        ).allMatches(value).toList();
    if (matches.isEmpty) return _splitLooseMath(value);

    final segments = <_MathSegment>[];
    var start = 0;
    for (final match in matches) {
      if (match.start > start) {
        segments.add(_MathSegment(value.substring(start, match.start), false));
      }
      segments.add(
        _MathSegment(
          match.group(1) ??
              match.group(2) ??
              match.group(3) ??
              match.group(4) ??
              '',
          true,
        ),
      );
      start = match.end;
    }
    if (start < value.length) {
      segments.add(_MathSegment(value.substring(start), false));
    }
    return segments.where((segment) => segment.text.isNotEmpty).toList();
  }

  List<_MathSegment> _splitLooseMath(String value) {
    final segments = <_MathSegment>[];
    final buffer = StringBuffer();
    var inCandidate = false;

    void flushCandidate(String text) {
      if (text.isEmpty) return;
      final leading = RegExp(r'^\s*').firstMatch(text)?.group(0) ?? '';
      final trailing = RegExp(r'\s*$').firstMatch(text)?.group(0) ?? '';
      final core = text.trim();
      if (_looksLikeLooseMath(core)) {
        if (leading.isNotEmpty) segments.add(_MathSegment(leading, false));
        segments.add(_MathSegment(core, true));
        if (trailing.isNotEmpty) segments.add(_MathSegment(trailing, false));
      } else {
        segments.add(_MathSegment(text, false));
      }
    }

    void flush() {
      final text = buffer.toString();
      buffer.clear();
      if (inCandidate) {
        flushCandidate(text);
      } else if (text.isNotEmpty) {
        segments.add(_MathSegment(text, false));
      }
    }

    for (final rune in value.runes) {
      final char = String.fromCharCode(rune);
      final candidate = _isLooseMathChar(char);
      if (candidate != inCandidate && buffer.isNotEmpty) {
        flush();
      }
      inCandidate = candidate;
      buffer.write(char);
    }
    flush();
    return segments.where((segment) => segment.text.isNotEmpty).toList();
  }

  bool _isLooseMathChar(String char) {
    return RegExp(r'[A-Za-z0-9\s+\-*/=^_(){}\[\]<>.,]').hasMatch(char) ||
        '∫√π∞≤≥·'.contains(char);
  }

  bool _looksLikeLooseMath(String text) {
    if (text.length < 2) return false;
    final hasMathMarker = RegExp(
      r'[=^_+\-*/∫√≤≥]|[A-Za-z]\([^)]*\)',
    ).hasMatch(text);
    final hasMathLetterOrDigit = RegExp(r'[A-Za-z0-9]').hasMatch(text);
    return hasMathMarker && hasMathLetterOrDigit;
  }
}

class _MathSegment {
  final String text;
  final bool isMath;

  const _MathSegment(this.text, this.isMath);
}
