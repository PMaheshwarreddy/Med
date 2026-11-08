import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../l10n/strings.dart';
import '../models/intake.dart';
import '../state/intake_controller.dart';
import '../theme/medora_theme.dart';
import 'medora_scaffold.dart';

/// "Have you visited before?" (the user's rule of 2026-11-07): Yes / No
/// first. Yes asks for the earlier visit number OR the phone number (many
/// patients do not keep the visit number), then an "Is this you?" pop-up
/// shows each match (name, age, masked phone, the last visit in short).
/// Confirming links the visit to that record and fills in what the
/// patient need not be asked again (age, gender, allergies, conditions,
/// daily medicines, operations, weight, habits); "not me" changes nothing.
class VisitedBefore extends ConsumerStatefulWidget {
  const VisitedBefore({super.key, required this.find});

  /// Looks a number up: the kiosk's or the phone page's endpoint.
  final Future<List<Map<String, dynamic>>> Function(String number) find;

  @override
  ConsumerState<VisitedBefore> createState() => _VisitedBeforeState();
}

class _VisitedBeforeState extends ConsumerState<VisitedBefore> {
  final _number = TextEditingController();
  // null: not answered yet.
  bool? _visited;
  bool _busy = false;
  bool _short = false;
  bool _notFound = false;
  String _confirmedName = '';

  @override
  void dispose() {
    _number.dispose();
    super.dispose();
  }

  Future<void> _find(S s) async {
    final raw = _number.text.trim();
    final digits = raw.replaceAll(RegExp(r'\D'), '');
    final code = raw.replaceAll(RegExp(r'[^0-9A-Za-z]'), '');
    final isPhone = digits.length >= 10 && digits.length == code.length;
    if (!isPhone && code.length != 6) {
      setState(() => _short = true);
      return;
    }
    setState(() {
      _busy = true;
      _short = false;
      _notFound = false;
    });
    final found = await widget.find(
      isPhone ? digits.substring(digits.length - 10) : code,
    );
    if (!mounted) return;
    setState(() {
      _busy = false;
      _notFound = found.isEmpty;
    });
    if (found.isEmpty) return;
    final picked = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => _IsThisYou(found: found),
    );
    if (picked != null) _confirm(picked);
  }

  void _confirm(Map<String, dynamic> match) {
    final known = Map<String, dynamic>.from(match['known'] as Map? ?? {});
    final patient = ref.read(intakeProvider).patient;
    String keep(String now, Object? before) =>
        now.trim().isNotEmpty ? now : '${before ?? ''}';
    ref
        .read(intakeProvider.notifier)
        .setPatient(
          patient.copyWith(
            patientId: match['id'] as String,
            name: keep(patient.name, known['name']),
            age: patient.age ?? known['age'] as int?,
            gender:
                patient.gender ?? Gender.values.asNameMap()[known['gender']],
            phone: keep(patient.phone, known['phone']),
            email: keep(patient.email, known['email']),
            allergies: keep(patient.allergies, known['allergies']),
            conditions: keep(patient.conditions, known['conditions']),
            regularMedicines: keep(
              patient.regularMedicines,
              known['regularMedicines'],
            ),
            surgeries: keep(patient.surgeries, known['surgeries']),
            habits: keep(patient.habits, known['habits']),
            weightKg:
                patient.weightKg ?? (known['weightKg'] as num?)?.toDouble(),
          ),
        );
    setState(() => _confirmedName = '${match['name'] ?? ''}');
  }

  void _notMe() {
    final intake = ref.read(intakeProvider.notifier);
    final patient = ref.read(intakeProvider).patient;
    intake.setPatient(patient.copyWith(clearPatient: true));
    setState(() {
      _visited = false;
      _confirmedName = '';
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final text = Theme.of(context).textTheme;
    final picked = ref.watch(intakeProvider.select((x) => x.patient.patientId));
    return MedoraCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(s.visitedTitle, style: text.titleLarge),
          const SizedBox(height: 4),
          Text(s.visitedSubtitle, style: text.bodyMedium),
          const SizedBox(height: 14),
          if (picked != null) ...[
            MedoraNotice(
              key: const Key('visited-confirmed'),
              icon: Icons.check_circle_outline,
              message: _confirmedName.isEmpty
                  ? s.welcomeBack
                  : s.filledFromRecord(_confirmedName),
              color: MedoraColors.teal,
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(onPressed: _notMe, child: Text(s.notMe)),
            ),
          ] else ...[
            Row(
              children: [
                for (final (i, (value, label, key)) in [
                  (true, s.yes, 'visited-yes'),
                  (false, s.no, 'visited-no'),
                ].indexed) ...[
                  if (i > 0) const SizedBox(width: 12),
                  Expanded(
                    child: _visited == value
                        ? FilledButton(
                            key: Key(key),
                            onPressed: () => setState(() => _visited = value),
                            child: Text(label),
                          )
                        : OutlinedButton(
                            key: Key(key),
                            onPressed: () => setState(() => _visited = value),
                            child: Text(label),
                          ),
                  ),
                ],
              ],
            ),
            if (_visited == true) ...[
              const SizedBox(height: 14),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: TextField(
                      key: const Key('visited-number'),
                      controller: _number,
                      textCapitalization: TextCapitalization.characters,
                      inputFormatters: [
                        FilteringTextInputFormatter.allow(
                          RegExp(r'[0-9A-Za-z +-]'),
                        ),
                        LengthLimitingTextInputFormatter(16),
                      ],
                      onSubmitted: (_) => _busy ? null : _find(s),
                      decoration: InputDecoration(
                        labelText: s.visitNumberLabel,
                        hintText: 'AB12CD / 98765 43210',
                        errorText: _short ? s.visitNumberShort : null,
                        errorMaxLines: 2,
                        prefixIcon: const Icon(Icons.search_rounded),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: FilledButton(
                      key: const Key('visited-find'),
                      onPressed: _busy ? null : () => _find(s),
                      child: Text(s.findMe),
                    ),
                  ),
                ],
              ),
              if (_notFound) ...[
                const SizedBox(height: 10),
                Text(s.noneFound, style: text.bodyMedium),
              ],
            ],
          ],
        ],
      ),
    );
  }
}

/// The pop-up: each record found, to confirm or not.
class _IsThisYou extends StatelessWidget {
  const _IsThisYou({required this.found});

  final List<Map<String, dynamic>> found;

  String _date(String? iso) {
    final at = DateTime.tryParse(iso ?? '')?.toLocal();
    if (at == null) return '';
    return '${at.day.toString().padLeft(2, '0')}-'
        '${at.month.toString().padLeft(2, '0')}-${at.year}';
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final text = Theme.of(context).textTheme;
    return AlertDialog(
      key: const Key('is-this-you'),
      title: Text(s.isThisYou),
      content: SizedBox(
        width: 460,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final m in found) ...[
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    border: Border.all(color: MedoraColors.border),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        [
                          '${m['name'] ?? ''}',
                          if (m['age'] != null) '${m['age']}',
                        ].join(', '),
                        style: text.titleMedium,
                      ),
                      if ('${m['phone'] ?? ''}'.isNotEmpty)
                        Text('${m['phone']}', style: text.bodyMedium),
                      if (m['lastVisit'] is Map) ...[
                        const SizedBox(height: 6),
                        Text(
                          s.lastVisit(
                            _date(m['lastVisit']['at'] as String?),
                            '${m['lastVisit']['complaint'] ?? ''}',
                          ),
                          style: text.bodyMedium,
                        ),
                        if ((m['lastVisit']['diagnosis'] as List?)
                                ?.isNotEmpty ==
                            true)
                          Text(
                            s.lastDiagnosis(
                              (m['lastVisit']['diagnosis'] as List).join(', '),
                            ),
                            style: text.bodyMedium,
                          ),
                      ],
                      const SizedBox(height: 10),
                      FilledButton.icon(
                        key: Key('visited-${m['id']}'),
                        onPressed: () => Navigator.of(context).pop(m),
                        icon: const Icon(Icons.check_rounded),
                        label: Text(s.thisIsMe),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          key: const Key('visited-not-me'),
          onPressed: () => Navigator.of(context).pop(),
          child: Text(s.notMe),
        ),
      ],
    );
  }
}
