import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:medora/widgets/pager.dart';

void main() {
  testWidgets('a long list shows 10 rows a page, 5/10/15/20 from a dropdown', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: Paged(
              children: [for (var i = 1; i <= 23; i++) Text('row $i')],
            ),
          ),
        ),
      ),
    );
    expect(find.text('row 1'), findsOneWidget);
    expect(find.text('row 11'), findsNothing);
    expect(find.text('1–10 of 23'), findsOneWidget);

    await tester.tap(find.byKey(const Key('page-next')));
    await tester.pump();
    expect(find.text('row 11'), findsOneWidget);
    expect(find.text('row 1'), findsNothing);

    await tester.tap(find.byKey(const Key('page-size')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('page-size-5')).last);
    await tester.pumpAndSettle();
    expect(find.text('1–5 of 23'), findsOneWidget);
    expect(find.text('row 6'), findsNothing);

    await tester.tap(find.byKey(const Key('page-size')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('page-size-20')).last);
    await tester.pumpAndSettle();
    expect(find.text('row 20'), findsOneWidget);
    expect(find.text('2 / 2'), findsNothing);
  });

  testWidgets('no pager while the list fits the smallest page', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Paged(children: [for (var i = 1; i <= 4; i++) Text('row $i')]),
        ),
      ),
    );
    expect(find.byKey(const Key('page-size')), findsNothing);
  });

  test('a page past the end falls back to the last page', () {
    final p = Paging(size: 5)..page = 9;
    expect(p.slice([1, 2, 3, 4, 5, 6, 7]), [6, 7]);
    expect(p.page, 1);
  });
}
