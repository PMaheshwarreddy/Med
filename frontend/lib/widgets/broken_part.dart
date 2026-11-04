import 'package:flutter/material.dart';

import '../theme/medora_theme.dart';

/// What a part of a page shows when it fails to draw, instead of Flutter's
/// red error box (the user's request of 2026-11-04). The error itself is
/// still printed to the browser console for developers. Built without
/// relying on a theme or text direction above it, since it can appear
/// anywhere.
class BrokenPart extends StatelessWidget {
  const BrokenPart({super.key});

  static Widget fromError(FlutterErrorDetails details) => const BrokenPart();

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.ltr,
      child: Container(
        margin: const EdgeInsets.all(4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: MedoraColors.warning.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: MedoraColors.warning.withValues(alpha: 0.3),
          ),
        ),
        child: const Text(
          'This part could not be shown. Please reload the page.',
          style: TextStyle(
            fontFamily: MedoraFonts.sans,
            fontSize: 14,
            color: MedoraColors.warning,
            decoration: TextDecoration.none,
          ),
        ),
      ),
    );
  }
}
