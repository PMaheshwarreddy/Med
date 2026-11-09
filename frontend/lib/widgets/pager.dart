import 'package:flutter/material.dart';

import '../theme/medora_theme.dart';

/// Which page of a list is shown, and how many rows per page (the user's
/// request of 2026-11-09: 5 / 10 / 15 / 20 on every list in every portal). The
/// list itself stays in the page; [slice] picks the rows to draw.
class Paging {
  Paging({this.size = 10});

  static const sizes = [5, 10, 15, 20];

  int page = 0;
  int size;

  /// The rows of the current page. A page past the end (the list shrank)
  /// falls back to the last one.
  List<T> slice<T>(List<T> items) {
    final last = items.isEmpty ? 0 : (items.length - 1) ~/ size;
    if (page > last) page = last;
    final start = page * size;
    return items.sublist(start, (start + size).clamp(0, items.length));
  }
}

/// A slim footer under a list: "1–10 of 43" on the left; "Rows per page
/// [10 ▾]" and "‹ 1 / 5 ›" on the right (a dropdown since 2026-11-09: the
/// chips looked heavy). Hidden while the whole list fits on the smallest
/// page; [onChanged] should call setState.
class PagerBar extends StatelessWidget {
  const PagerBar({
    super.key,
    required this.paging,
    required this.total,
    required this.onChanged,
  });

  final Paging paging;
  final int total;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    if (total <= Paging.sizes.first) return const SizedBox.shrink();
    final style = Theme.of(
      context,
    ).textTheme.bodySmall?.copyWith(color: MedoraColors.muted, fontSize: 13);
    final pages = (total + paging.size - 1) ~/ paging.size;
    final page = paging.page.clamp(0, pages - 1);
    final from = page * paging.size + 1;
    final to = ((page + 1) * paging.size).clamp(0, total);
    void go(int p) {
      paging.page = p;
      onChanged();
    }

    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.only(top: 6),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: MedoraColors.border)),
      ),
      child: Row(
        children: [
          Text('$from–$to of $total', style: style),
          const Spacer(),
          Text('Rows per page', style: style),
          const SizedBox(width: 8),
          DropdownButtonHideUnderline(
            child: DropdownButton<int>(
              key: const Key('page-size'),
              value: paging.size,
              isDense: true,
              borderRadius: BorderRadius.circular(10),
              style: style?.copyWith(
                color: MedoraColors.text,
                fontFamily: MedoraFonts.sans,
              ),
              items: [
                for (final s in Paging.sizes)
                  DropdownMenuItem(
                    key: Key('page-size-$s'),
                    value: s,
                    child: Text('$s'),
                  ),
              ],
              onChanged: (s) {
                if (s == null) return;
                paging
                  ..size = s
                  ..page = 0;
                onChanged();
              },
            ),
          ),
          const SizedBox(width: 16),
          IconButton(
            key: const Key('page-prev'),
            tooltip: 'Previous page',
            visualDensity: VisualDensity.compact,
            iconSize: 20,
            onPressed: page > 0 ? () => go(page - 1) : null,
            icon: const Icon(Icons.chevron_left_rounded),
          ),
          Text('${page + 1} / $pages', style: style),
          IconButton(
            key: const Key('page-next'),
            tooltip: 'Next page',
            visualDensity: VisualDensity.compact,
            iconSize: 20,
            onPressed: page < pages - 1 ? () => go(page + 1) : null,
            icon: const Icon(Icons.chevron_right_rounded),
          ),
        ],
      ),
    );
  }
}

/// A list of already-built rows or cards, shown a page at a time with a
/// [PagerBar] under it. [layout] lays out the page's rows (a Column, a
/// Wrap, a table); by default they are stacked.
class Paged extends StatefulWidget {
  const Paged({super.key, required this.children, this.layout});

  final List<Widget> children;
  final Widget Function(List<Widget> shown)? layout;

  @override
  State<Paged> createState() => _PagedState();
}

class _PagedState extends State<Paged> {
  final _paging = Paging();

  @override
  Widget build(BuildContext context) {
    final shown = _paging.slice(widget.children);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        widget.layout?.call(shown) ??
            Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: shown,
            ),
        PagerBar(
          paging: _paging,
          total: widget.children.length,
          onChanged: () => setState(() {}),
        ),
      ],
    );
  }
}
