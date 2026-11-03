import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../theme/medora_theme.dart';
import '../widgets/medora_scaffold.dart';
import 'admin_widgets.dart';

const _base = '/api/admin/knowledge';

/// How often the numbers are counted again while the tab is open, and how
/// often while a file is being worked on.
const _refreshEvery = Duration(seconds: 15);
const _refreshWhileWorking = Duration(seconds: 4);

const _busyStates = {'waiting', 'reading', 'loading'};

/// The medical knowledge database (MEDORA_KNOWLEDGE_DATABASE_URL): what it
/// holds, counted live; the files uploaded into it; and browsing it. The app
/// database holds no medical knowledge.
class KnowledgeTab extends StatefulWidget {
  const KnowledgeTab({super.key, required this.admin});

  final AdminApi admin;

  @override
  State<KnowledgeTab> createState() => _KnowledgeTabState();
}

class _KnowledgeTabState extends State<KnowledgeTab> with Loader {
  Map<String, dynamic>? _summary;
  List<dynamic> _uploads = [];
  String? _uploadsProblem;

  String? _uploading;

  Timer? _refresh;
  bool _refreshing = false;

  bool get _reachable => _summary?['reachable'] == true;

  bool get _working =>
      _uploads.any((u) => _busyStates.contains((u as Map)['status']));

  @override
  void dispose() {
    _refresh?.cancel();
    super.dispose();
  }

  @override
  Future<void> load() async {
    _summary = await widget.admin.get('$_base/summary') as Map<String, dynamic>;
    if (!_reachable) {
      // The lists come from the database too; keep what was shown.
      _uploadsProblem = _summary!['configured'] == true
          ? 'The knowledge database cannot be reached right now.'
          : 'The knowledge database is not set up on this server.';
      _schedule();
      return;
    }
    try {
      _uploads = await widget.admin.get('$_base/uploads') as List;
      _uploadsProblem = null;
    } on ApiException catch (e) {
      _uploadsProblem = e.message;
    }
    _schedule();
  }

  /// Counts again by itself: often while a file is being worked on.
  void _schedule() {
    _refresh?.cancel();
    if (!mounted) return;
    _refresh = Timer(
      _working ? _refreshWhileWorking : _refreshEvery,
      _quietRefresh,
    );
  }

  Future<void> _quietRefresh() async {
    if (!mounted || busy || _refreshing) {
      _schedule();
      return;
    }
    _refreshing = true;
    try {
      await load();
    } on ApiException {
      _schedule();
    } finally {
      _refreshing = false;
    }
    if (mounted) setState(() {});
  }

  // --- uploads ---------------------------------------------------------------

  Future<void> _upload() async {
    final picked = await FilePicker.pickFiles();
    if (picked.isEmpty || !mounted) return;
    final choices =
        (_summary?['choices'] as Map?)?.cast<String, dynamic>() ?? const {};
    final problems = <String>[];
    await run(() async {
      for (final (i, file) in picked.indexed) {
        if (!mounted) return;
        final details = await showDialog<Map<String, String>>(
          context: context,
          builder: (context) =>
              _UploadDetailsDialog(filename: file.name, choices: choices),
        );
        if (details == null) continue;
        setState(
          () => _uploading =
              'Uploading ${i + 1} of ${picked.length}: ${file.name}',
        );
        try {
          final bytes = await file.readAsBytes();
          await widget.admin.upload(
            '$_base/uploads',
            filename: file.name,
            bytes: Stream.value(bytes),
            length: bytes.length,
            query: details,
          );
        } on ApiException catch (e) {
          problems.add('${file.name}: ${e.message}');
        }
      }
    });
    if (!mounted) return;
    setState(() {
      _uploading = null;
      if (problems.isNotEmpty) error = problems.join('\n');
    });
  }

  Future<void> _act(int id, String action, {String? text}) => run(
    () => widget.admin.send(
      'POST',
      '$_base/uploads/$id/$action',
      body: text == null ? null : {'text': text},
      // Re-planning with the AI, or saving the offline copy, takes a while.
      timeout: const Duration(minutes: 10),
    ),
  );

  Future<void> _openUpload(Map<String, dynamic> upload) async {
    final Map<String, dynamic> detail;
    try {
      detail =
          await widget.admin.get('$_base/uploads/${upload['id']}')
              as Map<String, dynamic>;
    } on ApiException catch (e) {
      setState(() => error = e.message);
      return;
    }
    if (!mounted) return;
    final action = await showDialog<String>(
      context: context,
      builder: (context) => _UploadDialog(upload: detail, switches: _switches),
    );
    if (action == null || !mounted) return;
    String? text;
    if (action == 'reject' || action == 'revise') {
      text = await askText(
        context,
        title: action == 'reject' ? 'Reject this file' : 'Revise the plan',
        label: action == 'reject'
            ? 'Why should it not be loaded?'
            : 'What should the AI change?',
        hint: action == 'reject'
            ? null
            : 'For example: only add other names to existing drugs, '
                  'do not create new ones',
        confirm: action == 'reject' ? 'Reject' : 'Revise',
      );
      if (text == null) return;
    }
    if (action == 'remove' && mounted) {
      final sure = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Remove from the knowledge database?'),
          content: Text(
            'Everything read from ${detail['filename']} is taken out of the '
            'knowledge database, and reports stop using it.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: MedoraColors.danger,
              ),
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Remove'),
            ),
          ],
        ),
      );
      if (sure != true) return;
    }
    await _act(upload['id'] as int, action, text: text);
  }

  Map<String, dynamic> get _switches =>
      (_summary?['switches'] as Map?)?.cast<String, dynamic>() ?? const {};

  // --- page ------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final s = _summary;
    if (s == null) return Column(children: statusWidgets());
    final totals = (s['totals'] as Map?)?.cast<String, dynamic>();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ...statusWidgets(),
        if (!_reachable) ...[
          _Connection(summary: s),
          const SizedBox(height: 16),
        ],
        if (totals != null) ...[
          _Numbers(totals: totals),
          const SizedBox(height: 24),
        ],
        _uploadSection(),
      ],
    );
  }

  Widget _uploadSection() {
    return Section(
      title: 'Uploaded files',
      actions: [
        FilledButton.icon(
          key: const Key('knowledge-upload'),
          onPressed: busy || !_reachable ? null : _upload,
          icon: const Icon(Icons.upload_file),
          label: const Text('Upload files'),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_uploading != null) ...[
            MedoraNotice(
              icon: Icons.cloud_upload_outlined,
              message: _uploading!,
              color: MedoraColors.primary,
            ),
            const SizedBox(height: 12),
          ],
          if (_uploadsProblem != null) ...[
            MedoraNotice(
              icon: Icons.cloud_off_outlined,
              message: _uploadsProblem!,
            ),
            const SizedBox(height: 12),
          ],
          _uploads.isEmpty
              ? const EmptyNote('No files uploaded yet.')
              : ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 420),
                  child: SingleChildScrollView(
                    child: AdminTable(
                      onTap: (i) =>
                          _openUpload(_uploads[i] as Map<String, dynamic>),
                      columns: const [
                        'File',
                        'Status',
                        'What it is',
                        'Result',
                        'Reports',
                      ],
                      rows: [
                        for (final u in _uploads.cast<Map<String, dynamic>>())
                          [
                            Clipped(u['filename'] as String, width: 220),
                            UploadStatusPill(u),
                            Clipped(_about(u), width: 320),
                            Text(uploadResult(u)),
                            Text(_inReports(u, _switches)),
                          ],
                      ],
                    ),
                  ),
                ),
        ],
      ),
    );
  }

  static String _about(Map<String, dynamic> u) {
    if (_busyStates.contains(u['status']) &&
        (u['stage'] as String).isNotEmpty) {
      return u['stage'] as String;
    }
    for (final key in const ['summary', 'title', 'note']) {
      final value = u[key] as String? ?? '';
      if (value.isNotEmpty) return value;
    }
    return '';
  }
}

/// Shown only when the knowledge database cannot be reached.
class _Connection extends StatelessWidget {
  const _Connection({required this.summary});

  final Map<String, dynamic> summary;

  @override
  Widget build(BuildContext context) {
    final counted = summary['countedAt'] as String? ?? '';
    return MedoraNotice(
      key: const Key('knowledge-connection'),
      icon: Icons.cloud_off_outlined,
      color: MedoraColors.warning,
      message: summary['configured'] != true
          ? 'The knowledge database is not set up on this server.'
          : 'The knowledge database cannot be reached right now'
                '${counted.isEmpty ? '.' : '. Numbers as of ${formatDate(counted)}.'}',
    );
  }
}

class _Numbers extends StatelessWidget {
  const _Numbers({required this.totals});

  final Map<String, dynamic> totals;

  // A number the server did not send shows as a dash, never a false 0.
  String n(String key) =>
      totals[key] is num ? formatCount(totals[key] as num) : '–';

  @override
  Widget build(BuildContext context) {
    return TileGrid(
      minTileWidth: 220,
      children: [
        KpiCard(
          key: const Key('knowledge-symptoms'),
          icon: Icons.sick_outlined,
          color: MedoraColors.accent,
          label: 'Symptoms',
          value: n('symptoms'),
        ),
        KpiCard(
          key: const Key('knowledge-diseases'),
          icon: Icons.coronavirus_outlined,
          color: MedoraColors.primary,
          label: 'Diseases',
          value: n('diseases'),
        ),
        KpiCard(
          key: const Key('knowledge-medications'),
          icon: Icons.medication_outlined,
          color: MedoraColors.teal,
          label: 'Medications',
          value: n('medications'),
        ),
        KpiCard(
          key: const Key('knowledge-precautions'),
          icon: Icons.health_and_safety_outlined,
          color: MedoraColors.warning,
          label: 'Precautions',
          value: n('precautions'),
        ),
      ],
    );
  }
}

String _tierName(int tier) => switch (tier) {
  1 => 'Indian government',
  2 => 'WHO / international',
  3 => 'Other reference',
  4 => 'Vocabulary',
  _ => 'Community',
};

String _inReports(Map<String, dynamic> u, Map<String, dynamic> switches) {
  if (u['status'] != 'loaded') return '–';
  if (u['reports'] == true) return 'Yes';
  final tier = u['tier'] as int? ?? 5;
  if (tier <= 4 && switches['testing'] == true) return 'Testing only';
  if (tier == 5 && switches['community'] == true) return 'Testing only';
  return 'No';
}

/// What came of an upload, in a few words.
String uploadResult(Map<String, dynamic> u) {
  final loaded = (u['loaded'] as Map?)?.cast<String, dynamic>();
  if (loaded == null || u['status'] != 'loaded') return '';
  int count(String key) => (loaded[key] as num?)?.toInt() ?? 0;
  if (u['kind'] == 'pdf') {
    final quarantined = count('quarantined');
    return '${formatCount(count('kb_chunks'))} passages'
        '${quarantined > 0 ? ', ${formatCount(quarantined)} quarantined' : ''}';
  }
  final parts = [
    for (final (key, label) in const [
      ('diseases', 'diseases'),
      ('symptoms', 'symptoms'),
      ('drugs', 'medicines'),
      ('symptom links', 'symptom links'),
      ('drug links', 'medicine links'),
      ('precautions', 'precautions'),
      ('enriched names', 'enriched names'),
    ])
      if (count(key) > 0) '${formatCount(count(key))} $label',
  ];
  return parts.isEmpty ? 'Nothing new' : parts.join(', ');
}

class UploadStatusPill extends StatelessWidget {
  const UploadStatusPill(this.upload, {super.key});

  final Map<String, dynamic> upload;

  @override
  Widget build(BuildContext context) {
    final review = (upload['needsReview'] as List? ?? const []).isNotEmpty;
    final (label, color) = switch (upload['status']) {
      'waiting' => ('Waiting', MedoraColors.primary),
      'reading' => ('Reading', MedoraColors.primary),
      'loading' => ('Loading', MedoraColors.primary),
      'planned' when review => ('Needs review', MedoraColors.warning),
      'planned' => ('Waiting for approval', MedoraColors.primary),
      'loaded' => ('Loaded', MedoraColors.teal),
      'failed' => ('Failed', MedoraColors.danger),
      'removed' => ('Removed', MedoraColors.muted),
      _ => (
        upload['verdict'] == 'not_data' ? 'Not data' : 'Skipped',
        MedoraColors.muted,
      ),
    };
    return Pill(label, color);
  }
}

/// What the person uploading says about a file: who publishes it, its
/// licence, and whether reports may use it.
class _UploadDetailsDialog extends StatefulWidget {
  const _UploadDetailsDialog({required this.filename, required this.choices});

  final String filename;
  final Map<String, dynamic> choices;

  @override
  State<_UploadDetailsDialog> createState() => _UploadDetailsDialogState();
}

class _UploadDetailsDialogState extends State<_UploadDetailsDialog> {
  late final bool _pdf = widget.filename.toLowerCase().endsWith('.pdf');
  late final _title = TextEditingController(
    text: widget.filename
        .replaceAll(RegExp(r'\.[A-Za-z0-9]+$'), '')
        .replaceAll(RegExp(r'[_-]+'), ' '),
  );
  final _publisher = TextEditingController();
  final _licence = TextEditingController();
  late String _tier = _pdf ? '1' : '5';
  String _kind = 'guideline';
  // A data file or article is approved by a person before it loads; a PDF
  // loads at once, so its use in reports is a deliberate choice.
  late bool _reports = !_pdf;

  @override
  void dispose() {
    _title.dispose();
    _publisher.dispose();
    _licence.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tiers =
        (widget.choices['tiers'] as Map?)?.cast<String, dynamic>() ??
        const {
          '1': 'Indian government',
          '2': 'WHO or international body',
          '3': 'Other reference',
          '5': 'Community dataset',
        };
    final kinds =
        (widget.choices['documentKinds'] as Map?)?.cast<String, dynamic>() ??
        const {
          'guideline': 'Clinical guideline',
          'formulary': 'Drug book (formulary)',
          'patient_info': 'Patient information',
        };
    return AlertDialog(
      title: Text(widget.filename),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                key: const Key('upload-title'),
                controller: _title,
                decoration: const InputDecoration(labelText: 'Title'),
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('upload-publisher'),
                controller: _publisher,
                decoration: const InputDecoration(
                  labelText: 'Publisher',
                  hintText: 'For example: ICMR, NCDC, WHO',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('upload-licence'),
                controller: _licence,
                decoration: const InputDecoration(
                  labelText: 'Licence or permission',
                  hintText: 'For example: Government of India publication',
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                key: const Key('upload-tier'),
                initialValue: tiers.containsKey(_tier)
                    ? _tier
                    : tiers.keys.first,
                decoration: const InputDecoration(
                  labelText: 'Who publishes it',
                ),
                items: [
                  for (final e in tiers.entries)
                    DropdownMenuItem(
                      value: e.key,
                      child: Text(e.value as String),
                    ),
                ],
                onChanged: (v) => setState(() => _tier = v ?? _tier),
              ),
              if (_pdf) ...[
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  key: const Key('upload-kind'),
                  initialValue: _kind,
                  decoration: const InputDecoration(
                    labelText: 'What kind of document',
                  ),
                  items: [
                    for (final e in kinds.entries)
                      DropdownMenuItem(
                        value: e.key,
                        child: Text(e.value as String),
                      ),
                  ],
                  onChanged: (v) => setState(() => _kind = v ?? _kind),
                ),
              ],
              const SizedBox(height: 8),
              SwitchListTile(
                key: const Key('upload-reports'),
                contentPadding: EdgeInsets.zero,
                value: _reports,
                onChanged: (v) => setState(() => _reports = v),
                title: const Text('Reports may use it'),
                subtitle: const Text(
                  'Only when the licence allows it. You can change this '
                  'later from the file.',
                ),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Skip this file'),
        ),
        FilledButton(
          key: const Key('upload-confirm'),
          onPressed: () => Navigator.pop(context, {
            'title': _title.text.trim(),
            'publisher': _publisher.text.trim(),
            'licence': _licence.text.trim(),
            'tier': _tier,
            if (_pdf) 'kind': _kind,
            'reports': '$_reports',
          }),
          child: const Text('Upload'),
        ),
      ],
    );
  }
}

/// One upload: what was found, what it would do, and what to do next.
class _UploadDialog extends StatelessWidget {
  const _UploadDialog({required this.upload, required this.switches});

  final Map<String, dynamic> upload;
  final Map<String, dynamic> switches;

  static String _col(Map? col) {
    if (col == null) return '';
    final split = col['split'] == null ? '' : ' (split on "${col['split']}")';
    return '${(col['sources'] as List).join(' or ')}$split';
  }

  static String _mapping(Map<String, dynamic> o) {
    switch (o['kind']) {
      case 'entity':
        final fields = (o['fields'] as Map).entries
            .map((e) => '${e.key} ← ${_col(e.value as Map)}')
            .join(', ');
        final mode = o['mode'] == 'enrich_only'
            ? 'Add other names to existing ${o['table']} only'
            : 'Add ${o['table']}';
        return '$mode: name ← ${_col(o['name'] as Map)}'
            '${o['aliases'] == null ? '' : ', other names ← ${_col(o['aliases'] as Map)}'}'
            '${fields.isEmpty ? '' : ', $fields'}';
      case 'link':
        final target = o['symptom'] != null ? 'symptom' : 'drug';
        return 'Link disease ← ${_col(o['disease'] as Map)}  to  '
            '$target ← ${_col(o[target] as Map)}';
      default:
        return 'Precaution ← ${_col(o['text'] as Map)} '
            'for ${o['disease'] != null ? 'disease ← ${_col(o['disease'] as Map)}' : 'symptom ← ${_col(o['symptom'] as Map)}'}';
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final status = upload['status'] as String;
    final kind = upload['kind'] as String;
    final preview = upload['preview'] as Map<String, dynamic>?;
    final review = (upload['needsReview'] as List).cast<String>();
    final outputs = (upload['outputs'] as List).cast<Map<String, dynamic>>();
    final dropped = (upload['droppedNotInArticle'] as List).cast<String>();
    final working = _busyStates.contains(status);
    final result = uploadResult(upload);

    Widget heading(String label) => Padding(
      padding: const EdgeInsets.only(top: 16, bottom: 6),
      child: Text(label, style: text.titleMedium),
    );

    return AlertDialog(
      title: Text(upload['filename'] as String),
      content: SizedBox(
        width: 640,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 10,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  UploadStatusPill(upload),
                  Text(
                    '${switch (kind) {
                      'pdf' => 'PDF',
                      'records' => 'Data file',
                      _ => 'Article',
                    }}  ·  ${formatBytes(upload['sizeBytes'] as int)}  ·  '
                    '${_tierName(upload['tier'] as int? ?? 5)}  ·  '
                    'In reports: ${_inReports(upload, switches)}',
                    style: text.bodyMedium,
                  ),
                ],
              ),
              if (working && (upload['stage'] as String).isNotEmpty) ...[
                const SizedBox(height: 12),
                MedoraNotice(
                  icon: Icons.hourglass_top,
                  message: upload['stage'] as String,
                  color: MedoraColors.primary,
                ),
              ],
              if ((upload['note'] as String).isNotEmpty) ...[
                const SizedBox(height: 12),
                MedoraNotice(
                  icon: Icons.info_outline,
                  message: upload['note'] as String,
                ),
              ],
              for (final r in review) ...[
                const SizedBox(height: 12),
                MedoraNotice(icon: Icons.flag_outlined, message: r),
              ],
              heading('About the file'),
              Text(upload['title'] as String),
              Text(
                'Publisher: ${upload['publisher']}  ·  '
                'Licence: ${(upload['licence'] as String?)?.isNotEmpty == true ? upload['licence'] : 'Not stated'}',
                style: text.bodyMedium,
              ),
              if ((upload['summary'] as String).isNotEmpty) ...[
                heading('What the AI found'),
                Text(upload['summary'] as String),
                if ((upload['reason'] as String? ?? '').isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(upload['reason'] as String, style: text.bodyMedium),
                ],
              ],
              if (upload['content'] == 'article') ...[
                heading('How it will be loaded'),
                const Text(
                  'An article about one disease: the AI extracted its '
                  'description, causes, symptoms, medicines and precautions; '
                  'every name was checked against the text.',
                ),
              ] else if (outputs.isNotEmpty) ...[
                heading('How it will be loaded'),
                for (final o in outputs)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text('•  ${_mapping(o)}'),
                  ),
              ],
              if (preview != null && status != 'loaded') ...[
                heading(
                  'Preview (first ${formatCount(preview['records'] as int)} records)',
                ),
                Text(
                  '${formatCount(preview['diseases'] as int)} diseases, '
                  '${formatCount(preview['symptoms'] as int)} symptoms, '
                  '${formatCount(preview['drugs'] as int)} medicines, '
                  '${formatCount(preview['links'] as int)} links, '
                  '${formatCount(preview['precautions'] as int)} precautions. '
                  '${((preview['reject_rate'] as num) * 100).toStringAsFixed(1)}% '
                  'of values refused by the checks.',
                ),
              ],
              if (dropped.isNotEmpty) ...[
                heading('Dropped: not found in the article'),
                Text(dropped.join('; '), style: text.bodyMedium),
              ],
              if (result.isNotEmpty) ...[
                heading('Loaded into the knowledge database'),
                Text(result),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        if (status == 'planned')
          TextButton(
            onPressed: () => Navigator.pop(context, 'reject'),
            child: const Text(
              'Reject',
              style: TextStyle(color: MedoraColors.danger),
            ),
          ),
        if (kind == 'records' &&
            const {'planned', 'skipped', 'failed'}.contains(status))
          TextButton(
            onPressed: () => Navigator.pop(context, 'revise'),
            child: const Text('Revise plan'),
          ),
        if (const {'failed', 'skipped'}.contains(status))
          TextButton(
            onPressed: () => Navigator.pop(context, 'retry'),
            child: const Text('Try again'),
          ),
        if (status == 'loaded')
          TextButton(
            onPressed: () => Navigator.pop(
              context,
              upload['reports'] == true ? 'block' : 'allow',
            ),
            child: Text(
              upload['reports'] == true
                  ? 'Stop using in reports'
                  : 'Allow in reports',
            ),
          ),
        if (const {'loaded', 'failed'}.contains(status))
          TextButton(
            onPressed: () => Navigator.pop(context, 'remove'),
            child: const Text(
              'Remove from database',
              style: TextStyle(color: MedoraColors.danger),
            ),
          ),
        if (status == 'planned')
          FilledButton(
            onPressed: () => Navigator.pop(context, 'approve'),
            child: const Text('Approve and load'),
          ),
      ],
    );
  }
}
