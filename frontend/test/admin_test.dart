import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:medora/admin/admin_widgets.dart';
import 'package:medora/api/api_client.dart';
import 'package:medora/main.dart';
import 'package:medora/models/intake.dart';
import 'package:medora/state/service_status.dart';

/// In-memory stand-in for the Medora API.
class FakeServer {
  final requests = <String>[];
  final clients = <Map<String, dynamic>>[
    {
      'id': 'd1',
      'name': 'Default client',
      'isDefault': true,
      'active': true,
      'kioskKeyHint': '',
      'voiceIntake': true,
      'manualIntake': true,
      'smartBand': true,
      'sessions': 3,
      'lastSessionAt': '2026-10-12T08:00:00Z',
    },
  ]; // fmt: skip
  String runStatus = 'planned';
  bool knowledgeReachable = true;
  static const owner = {
    'id': 'u1',
    'email': 'owner@medora.io',
    'name': 'Priya Owner',
    'approved': true,
    'active': true,
    'createdAt': '2026-10-13T08:00:00Z',
    'lastLoginAt': '2026-10-13T09:00:00Z',
  }; // fmt: skip
  final users = <Map<String, dynamic>>[
    {...owner},
    {
      'id': 'u2',
      'email': 'sam@medora.io',
      'name': 'Sam New',
      'approved': false,
      'active': true,
      'createdAt': '2026-10-13T08:30:00Z',
      'lastLoginAt': null,
    },
  ]; // fmt: skip
  Map<String, dynamic>? registered;
  int panelSize = 5;
  final apiKeys = <Map<String, dynamic>>[];
  http.Request? lastRequest;

  Map<String, dynamic> get run => {
    'id': 7,
    'filename': 'mystery_file.csv',
    'sizeBytes': 2048,
    'kind': 'records',
    'status': runStatus,
    'stage': '',
    'note': '',
    'title': 'mystery file',
    'publisher': 'Not stated',
    'licence': 'Not stated',
    'tier': 5,
    'reports': true,
    'createdAt': '2026-10-12T08:00:00Z',
    'updatedAt': '2026-10-12T08:00:00Z',
    'summary': 'Diseases with their symptoms',
    'verdict': 'usable',
    'confidence': 0.9,
    'content': 'records',
    'needsReview': <String>[],
    'preview': {
      'records': 3,
      'diseases': 2,
      'symptoms': 3,
      'drugs': 0,
      'links': 4,
      'precautions': 0,
      'reject_rate': 0.0,
    },
    'loaded': runStatus == 'loaded'
        ? {'diseases': 2, 'symptoms': 3, 'symptom links': 4, 'quarantined': 0}
        : null,
    'reason': 'Clear disease and symptom columns.',
    'model': 'fake',
    'outputs': [
      {
        'kind': 'link',
        'disease': {
          'sources': ['disease'],
          'split': null,
        },
        'symptom': {
          'sources': ['symptoms'],
          'split': ',',
        },
        'drug': null,
      },
    ],
    'revised': <String>[],
    'droppedNotInArticle': <String>[],
  }; // fmt: skip

  Map<String, dynamic> get knowledgeSummary => {
    'configured': true,
    'reachable': knowledgeReachable,
    'error': knowledgeReachable ? '' : 'connection failed',
    'countedAt': '2026-10-30T09:00:00Z',
    'totals': {
      'sources': 31,
      'passages': 44400,
      'searchablePassages': 44400,
      'conditions': 11853,
      'names': 512000,
      'medicines': 2210,
      'brands': 251000,
      'doses': 3400,
      'safetyNotes': 9000,
      'redFlags': 700,
      'symptomLinks': 18015,
      'drugLinks': 6451,
      'precautions': 596,
      'listedEntries': 9597,
      'patientTopics': 1000,
      'quarantined': 120,
      'lastLoadedAt': '2026-10-29T10:00:00Z',
      'databaseSize': '2 GB',
      'symptoms': 73739,
      'diseases': 21790,
      'medications': 3384,
    },
    'sources': [
      {
        'key': 'msf-clinical-2024',
        'title': 'MSF Clinical guidelines',
        'publisher': 'Médecins Sans Frontières',
        'kind': 'guideline',
        'tier': 2,
        'status': 'loaded',
        'productionAllowed': false,
        'loadedAt': '2026-10-29T10:00:00Z',
        'passages': 5200,
        'quarantined': 3,
        'uploaded': false,
        'inReports': 'testing',
        'error': '',
      },
    ],
    'offline': {'passages': 18300, 'savedAt': '2026-10-29T11:00:00Z'},
    'evidenceIndex': {'available': true, 'from': 'database'},
    'switches': {'testing': true, 'community': false},
    'choices': {
      'tiers': {'1': 'Indian government', '5': 'Community dataset'},
      'documentKinds': {'guideline': 'Clinical guideline'},
    },
  }; // fmt: skip

  Future<http.Response> handle(http.Request request) async {
    final path = request.url.path;
    requests.add('${request.method} $path');
    lastRequest = request;
    http.Response json(Object body, [int status = 200]) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );
    if (path == '/api/status') {
      return json({
        'online': false,
        'voice': {'available': false, 'detail': 'offline'},
        'sms': {'available': false},
        'email': {'available': false},
      });
    }
    if (path == '/api/auth/login' || path == '/api/auth/register') {
      final body = jsonDecode(request.body) as Map;
      if (path.endsWith('register')) {
        registered = body.cast<String, dynamic>();
        return json({
          'user': {...owner, 'name': body['name'], 'email': body['email']},
          'token': 'secret',
        }, 201);
      }
      return body['password'] == 'correct horse'
          ? json({'user': owner, 'token': 'secret'})
          : json({'detail': 'Wrong email or password'}, 401);
    }
    if (request.headers['X-Admin-Key'] != 'secret') {
      return json({'detail': 'Sign in to the back office'}, 401);
    }
    if (path == '/api/auth/logout') return http.Response('', 204);
    if (path == '/api/admin/users' && request.method == 'GET') {
      return json(users);
    }
    if (path.startsWith('/api/admin/users/') && request.method == 'PATCH') {
      final user = users.firstWhere((u) => path.endsWith(u['id'] as String));
      user.addAll((jsonDecode(request.body) as Map).cast<String, dynamic>());
      return json(user);
    }
    if (path == '/api/admin/overview') {
      return json({
        'online': false,
        'clients': clients.length,
        'activeClients': clients.length,
        'sessions': 3,
        'sessionsLast24h': 1,
        'reports': 2,
        'errorsLast24h': 1,
        'voice': {
          'available': false,
          'detail': 'The voice agent needs an internet connection.',
        },
        'reportModel': 'ollama:qwen2.5:3b',
        'apiCallsLast24h': 12,
        'apiKeys': 1,
        'sessionsByDay': [
          for (var i = 0; i < 7; i++)
            {
              'date': '2026-10-${(7 + i).toString().padLeft(2, '0')}',
              'count': i == 6 ? 3 : i,
            },
        ],
        'sessionsByClient': [
          {'name': 'Default client', 'count': 3},
        ],
        'recentActivity': [
          {
            'at': '2026-10-13T08:06:00Z',
            'level': 'error',
            'event': 'report.error',
            'message': 'model is down',
            'client': 'Default client',
          },
        ],
        'sync': {
          'configured': true,
          'pending': 5,
          'lastSuccess': null,
          'lastError': '',
          'mirroredTotal': 0,
        },
      }); // fmt: skip
    }
    if (path == '/api/admin/system') {
      if (request.method == 'PUT') {
        panelSize = (jsonDecode(request.body) as Map)['panelSize'] as int;
      }
      return json({
        'panelSize': panelSize,
        'panelMax': 21,
        'specialists': ['Pulmonology', 'Cardiology'],
        'integrations': [
          {
            'name': 'Voice agent',
            'ok': true,
            'detail': 'gemini-live',
            'setting': 'MEDORA_GEMINI_API_KEY',
          },
          {
            'name': 'Report by SMS',
            'ok': false,
            'detail': 'Not set up',
            'setting': 'MEDORA_TWILIO_ACCOUNT_SID',
          },
        ],
      }); // fmt: skip
    }
    if (path == '/api/admin/api-keys' && request.method == 'GET') {
      return json(apiKeys);
    }
    if (path == '/api/admin/api-keys' && request.method == 'POST') {
      final body = jsonDecode(request.body) as Map;
      final created = {
        'id': 'k1',
        'name': body['name'],
        'tenantId': body['tenantId'],
        'tenantName': 'Default client',
        'keyHint': 'ma_abcd…',
        'createdAt': '2026-10-13T08:00:00Z',
        'lastUsedAt': null,
        'revoked': false,
        'callsLast24h': 0,
        'errorsLast24h': 0,
      }; // fmt: skip
      apiKeys.add(created);
      return json({...created, 'apiKey': 'ma_full_secret_api_key'}, 201);
    }
    if (path.startsWith('/api/admin/api-keys/') && request.method == 'DELETE') {
      apiKeys.first['revoked'] = true;
      return http.Response('', 204);
    }
    if (path == '/api/admin/api-logs') {
      return json([
        {
          'id': 'a1',
          'at': '2026-10-13T08:10:00Z',
          'tenantId': 'd1',
          'keyName': 'Hospital system',
          'method': 'POST',
          'path': '/api/sessions',
          'status': 201,
          'durationMs': 42,
        },
        {
          'id': 'a2',
          'at': '2026-10-13T08:09:00Z',
          'tenantId': 'd1',
          'keyName': 'Hospital system',
          'method': 'POST',
          'path': '/api/sessions',
          'status': 422,
          'durationMs': 8,
        },
      ]); // fmt: skip
    }
    if (path == '/api/config') {
      return json({
        'voiceIntake': true,
        'manualIntake': true,
        'smartBand': true,
      });
    }
    if (path == '/api/admin/knowledge/summary') return json(knowledgeSummary);
    if (path == '/api/admin/tenants' && request.method == 'GET') {
      return json(clients);
    }
    if (path == '/api/admin/tenants' && request.method == 'POST') {
      final created = {
        ...clients.first,
        'id': 'c2',
        'isDefault': false,
        'sessions': 0,
        'lastSessionAt': null,
        'kioskKeyHint': 'mk_abcd…',
        ...(jsonDecode(request.body) as Map).cast<String, dynamic>(),
      }; // fmt: skip
      clients.add(created);
      return json({...created, 'kioskKey': 'mk_abcd_full_secret_key'}, 201);
    }
    if (path.startsWith('/api/admin/tenants/') && request.method == 'PATCH') {
      final client = clients.firstWhere(
        (c) => path.endsWith(c['id'] as String),
      );
      client.addAll((jsonDecode(request.body) as Map).cast<String, dynamic>());
      return json(client);
    }
    if (path == '/api/sessions') {
      return json([
        {
          'id': 's1',
          'tenantId': 'd1',
          'name': 'Asha Rao',
          'age': 34,
          'gender': 'female',
          'phone': '9876543210',
          'mode': 'manual',
          'symptoms': 'Headache and fever',
          'vitals': null,
          'hasReport': true,
          'createdAt': '2026-10-12T08:05:00Z',
        },
      ]); // fmt: skip
    }
    if (path == '/api/admin/logs') {
      return json([
        {
          'id': 'l1',
          'at': '2026-10-12T08:06:00Z',
          'tenantId': 'd1',
          'level': 'error',
          'event': 'report.error',
          'message': 'model is down',
        },
        {
          'id': 'l2',
          'at': '2026-10-12T08:05:00Z',
          'tenantId': null,
          'level': 'info',
          'event': 'knowledge.load',
          'message': 'final.csv: loaded',
        },
      ]); // fmt: skip
    }
    if (path == '/api/admin/knowledge/uploads') return json([run]);
    if (path == '/api/admin/knowledge/uploads/7') return json(run);
    if (path == '/api/admin/knowledge/uploads/7/approve') {
      runStatus = 'loaded';
      return json(run);
    }
    if (path == '/api/admin/knowledge/browse/passages') {
      return json({
        'total': 44400,
        'items': [
          {
            'id': 11,
            'source': 'MSF Clinical guidelines',
            'tier': 2,
            'page': 120,
            'heading': 'MSF Clinical guidelines › Typhoid fever › Treatment',
            'excerpt': 'Azithromycin PO for 7 days...',
            'section': 'treatment',
          },
        ],
      }); // fmt: skip
    }
    return json({'detail': 'Not found: $path'}, 404);
  }
}

Future<FakeServer> pumpAdmin(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1500, 2600);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final server = FakeServer();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(
          ApiClient(client: MockClient(server.handle)),
        ),
        // The header and the kiosk poll the live status; fix it for tests.
        serviceStatusProvider.overrideWith(
          (ref) =>
              Stream.value(const ServiceStatus(online: false, voice: false)),
        ),
      ],
      // The whole app, because the back office is its home and opening the
      // kiosk from it is a navigation.
      child: const MedoraApp(),
    ),
  );
  await tester.pumpAndSettle();
  return server;
}

Future<void> signIn(
  WidgetTester tester, {
  String password = 'correct horse',
}) async {
  await tester.enterText(
    find.byKey(const ValueKey('email')),
    'owner@medora.io',
  );
  await tester.enterText(find.byKey(const ValueKey('password')), password);
  await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
  await tester.pumpAndSettle();
}

Future<void> openPage(WidgetTester tester, String name) async {
  await tester.tap(find.byKey(ValueKey('nav-$name')));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('the app opens on the sign-in screen', (tester) async {
    await pumpAdmin(tester);
    expect(find.text('Sign in to Medora'), findsOneWidget);

    // The form is checked before anything is sent.
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('Enter a valid email address'), findsOneWidget);
    expect(find.text('Enter a password'), findsOneWidget);

    await signIn(tester, password: 'wrong password');
    expect(find.text('Wrong email or password'), findsOneWidget);
    expect(find.byKey(const ValueKey('nav-clients')), findsNothing);

    await signIn(tester);
    expect(find.byKey(const ValueKey('nav-clients')), findsOneWidget);
    expect(find.text('Priya Owner'), findsOneWidget);
    expect(find.text('owner@medora.io'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('nav-signout')));
    await tester.pumpAndSettle();
    expect(find.text('Sign in to Medora'), findsOneWidget);
  });

  testWidgets('a new account is created and signed in', (tester) async {
    final server = await pumpAdmin(tester);
    await tester.tap(find.text('Create an account'));
    await tester.pumpAndSettle();
    expect(find.text('Create your account'), findsOneWidget);

    await tester.enterText(find.byKey(const ValueKey('name')), 'Sam New');
    await tester.enterText(
      find.byKey(const ValueKey('email')),
      'sam@medora.io',
    );
    await tester.enterText(find.byKey(const ValueKey('password')), 'short');
    await tester.enterText(find.byKey(const ValueKey('confirm')), 'different');
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();
    expect(find.text('Use at least 8 characters'), findsOneWidget);
    expect(find.text('The passwords do not match'), findsOneWidget);
    expect(server.registered, isNull);

    await tester.enterText(
      find.byKey(const ValueKey('password')),
      'battery staple',
    );
    await tester.enterText(
      find.byKey(const ValueKey('confirm')),
      'battery staple',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();
    expect(server.registered!['email'], 'sam@medora.io');
    expect(find.byKey(const ValueKey('nav-clients')), findsOneWidget);
    expect(find.text('Sam New'), findsOneWidget);
    // Pages that no longer exist.
    for (final gone in ['api', 'team', 'system']) {
      expect(find.byKey(ValueKey('nav-$gone')), findsNothing);
    }
  });

  testWidgets('dashboard: figures, the week, activity; keeps itself current', (
    tester,
  ) async {
    final server = await pumpAdmin(tester);
    await signIn(tester);

    expect(find.text('Offline mode'), findsOneWidget);
    expect(find.text('Patient sessions, last 7 days'), findsOneWidget);
    expect(find.text('Active clients'), findsOneWidget);
    expect(find.text('model is down'), findsOneWidget);
    expect(find.text('1 active keys'), findsOneWidget);
    // No health panel and no Refresh button.
    expect(find.text('System health'), findsNothing);
    expect(find.text('5 rows waiting to copy'), findsNothing);
    expect(find.text('Refresh'), findsNothing);
    final before = server.requests
        .where((r) => r == 'GET /api/admin/overview')
        .length;
    await tester.pump(const Duration(seconds: 31));
    await tester.pumpAndSettle();
    expect(
      server.requests.where((r) => r == 'GET /api/admin/overview').length,
      greaterThan(before),
    );
  });

  testWidgets('clients: add one, get its one key and link, change switches', (
    tester,
  ) async {
    final server = await pumpAdmin(tester);
    await signIn(tester);
    await openPage(tester, 'clients');
    expect(find.text('Default client'), findsWidgets);
    // The "Calls made with client keys" table was removed (2026-11-09).
    expect(find.text('Calls made with client keys'), findsNothing);

    await tester.tap(find.byKey(const Key('add-client')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('client-name')),
      'City Hospital',
    );
    // The hospital's portal sign-in is set while creating the client.
    await tester.enterText(
      find.byKey(const Key('client-admin-name')),
      'Asha Nair',
    );
    await tester.enterText(
      find.byKey(const Key('client-admin-email')),
      'asha@city.in',
    );
    await tester.enterText(
      find.byKey(const Key('client-admin-password')),
      'short',
    );
    await tester.tap(find.byKey(const Key('client-create')));
    await tester.pumpAndSettle();
    expect(find.textContaining('at least 8 characters.'), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('client-admin-password')),
      'city-pass-1',
    );
    // Chosen at creation: this client has no smart band.
    final band = find.widgetWithText(SwitchListTile, 'Smart band').last;
    await tester.ensureVisible(band);
    await tester.pumpAndSettle();
    await tester.tap(band);
    await tester.tap(find.byKey(const Key('client-create')));
    await tester.pumpAndSettle();
    expect(server.clients.last['adminEmail'], 'asha@city.in');
    expect(server.clients.last['adminPassword'], 'city-pass-1');
    expect(find.text('asha@city.in'), findsOneWidget);
    expect(find.text('city-pass-1'), findsOneWidget);
    expect(find.text('mk_abcd_full_secret_key'), findsOneWidget);
    expect(
      find.textContaining('/kiosk?key=mk_abcd_full_secret_key'),
      findsOneWidget,
    );
    expect(find.text('API address'), findsOneWidget);
    await tester.tap(find.text('I have copied them'));
    await tester.pumpAndSettle();
    expect(find.text('City Hospital'), findsWidgets);
    expect(find.text('mk_abcd_full_secret_key'), findsNothing);
    expect(server.clients.last['smartBand'], isFalse);

    await tester.tap(find.widgetWithText(SwitchListTile, 'Voice agent').last);
    await tester.pumpAndSettle();
    expect(server.clients.last['voiceIntake'], isFalse);
    expect(server.clients.first['voiceIntake'], isTrue);
    // The voice switch shows off at once, not greyed out.
    expect(
      tester
          .widget<SwitchListTile>(
            find.widgetWithText(SwitchListTile, 'Voice agent').last,
          )
          .value,
      isFalse,
    );
    // With voice off, manual input is the only way in: switching it off is
    // refused with a reason, and nothing is sent.
    final sent = server.requests.length;
    await tester.tap(find.widgetWithText(SwitchListTile, 'Manual input').last);
    await tester.pump();
    expect(find.textContaining('has to stay on'), findsOneWidget);
    expect(server.requests.length, sent);
    expect(server.clients.last['manualIntake'], isTrue);
    // The band can be switched off and on freely.
    await tester.tap(find.widgetWithText(SwitchListTile, 'Smart band').last);
    await tester.pumpAndSettle();
    expect(server.clients.last['smartBand'], isTrue);
  });

  testWidgets('the kiosk opens inside the back office as a client', (
    tester,
  ) async {
    final server = await pumpAdmin(tester);
    await signIn(tester);
    await openPage(tester, 'kiosk');
    expect(find.widgetWithText(Pill, 'Smart band'), findsOneWidget);

    await tester.tap(find.text('Open kiosk').first);
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(find.text("Hello, I'm Dr. Medora"), findsOneWidget);
    expect(
      find.text('Preview: Default client  ·  Back office'),
      findsOneWidget,
    );

    await tester.tap(find.text('Preview: Default client  ·  Back office'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    // Back in the back office, still unlocked.
    expect(find.byKey(const ValueKey('nav-clients')), findsOneWidget);
    expect(server.requests, isNot(contains('POST /api/sessions')));
  });

  testWidgets('no Sessions page; logs name the client', (tester) async {
    await pumpAdmin(tester);
    await signIn(tester);

    // Patient sessions are not the company's to browse (2026-11-09).
    expect(find.byKey(const Key('nav-sessions')), findsNothing);

    await openPage(tester, 'logs');
    expect(find.text('report.error'), findsOneWidget);
    expect(find.text('System'), findsWidgets);

    // Home goes back to the dashboard from any page.
    await tester.tap(find.byKey(const Key('admin-home')));
    await tester.pumpAndSettle();
    expect(find.text('report.error'), findsNothing);
    final home = tester.widget<IconButton>(find.byKey(const Key('admin-home')));
    expect(home.onPressed, isNull); // already home
  });

  testWidgets('database: live numbers, sources, and approving an upload', (
    tester,
  ) async {
    final server = await pumpAdmin(tester);
    await signIn(tester);
    await openPage(tester, 'database');

    // Four numbers, counted from the knowledge database.
    expect(find.text('73,739'), findsOneWidget);
    expect(find.text('21,790'), findsOneWidget);
    expect(find.text('3,384'), findsOneWidget);
    expect(find.text('596'), findsOneWidget);
    for (final gone in [
      'Guideline passages',
      'Sources',
      'Printed doses',
      'Quarantined',
    ]) {
      expect(find.text(gone), findsNothing);
    }
    expect(
      find.textContaining('Live from the knowledge database'),
      findsNothing,
    );
    expect(find.text('Uploaded files'), findsOneWidget);
    // Raw passages are not shown to operators.
    expect(find.text('Browse the knowledge'), findsNothing);
    expect(find.text('Waiting for approval'), findsOneWidget);
    expect(
      server.requests,
      isNot(contains('GET /api/admin/knowledge/diseases')),
    );

    await tester.tap(find.text('mystery_file.csv'));
    await tester.pumpAndSettle();
    expect(
      find.text(
        '•  Link disease ← disease  to  symptom ← symptoms (split on ",")',
      ),
      findsOneWidget,
    );
    await tester.tap(find.text('Approve and load'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(Pill, 'Loaded'), findsOneWidget);
    expect(
      find.text('2 diseases, 3 symptoms, 4 symptom links'),
      findsOneWidget,
    );
    expect(
      server.requests,
      contains('POST /api/admin/knowledge/uploads/7/approve'),
    );

    // The numbers count again by themselves.
    final before = server.requests
        .where((r) => r == 'GET /api/admin/knowledge/summary')
        .length;
    await tester.pump(const Duration(seconds: 16));
    await tester.pumpAndSettle();
    expect(
      server.requests
          .where((r) => r == 'GET /api/admin/knowledge/summary')
          .length,
      greaterThan(before),
    );
  });

  testWidgets('database: while the knowledge database is down', (tester) async {
    final server = await pumpAdmin(tester);
    server.knowledgeReachable = false;
    await signIn(tester);
    await openPage(tester, 'database');

    // The last numbers stay visible, saying when they were counted.
    expect(find.text('73,739'), findsOneWidget);
    expect(find.textContaining('cannot be reached right now'), findsWidgets);
    final upload = tester.widget<ButtonStyleButton>(
      find.byKey(const Key('knowledge-upload')),
    );
    expect(upload.onPressed, isNull);
    expect(
      server.requests,
      isNot(contains('GET /api/admin/knowledge/uploads')),
    );

    // Back on: the page notices by itself.
    server.knowledgeReachable = true;
    await tester.pump(const Duration(seconds: 16));
    await tester.pumpAndSettle();
    expect(find.textContaining('cannot be reached'), findsNothing);
    expect(find.text('mystery_file.csv'), findsOneWidget);
  });
}
