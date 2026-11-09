import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../theme/medora_theme.dart';
import 'admin_widgets.dart';

/// A client's usage in numbers only (the user's rule of 2026-11-09: the
/// company sees how much a hospital uses Medora, never its patients' data).
class ClientSummaryDialog extends StatefulWidget {
  const ClientSummaryDialog({
    super.key,
    required this.admin,
    required this.client,
  });

  final AdminApi admin;
  final Map<String, dynamic> client;

  @override
  State<ClientSummaryDialog> createState() => _ClientSummaryDialogState();
}

class _ClientSummaryDialogState extends State<ClientSummaryDialog> {
  Map<String, dynamic>? _summary;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final s = await widget.admin.get(
        '/api/admin/tenants/${widget.client['id']}/summary',
      );
      if (mounted) setState(() => _summary = s as Map<String, dynamic>);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _summary;
    final text = Theme.of(context).textTheme;
    Widget figure(String label, Object? value, IconData icon) => SizedBox(
      width: 170,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          border: Border.all(color: MedoraColors.border),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 20, color: MedoraColors.primary),
            const SizedBox(height: 8),
            Text(
              formatCount((value as num?) ?? 0),
              style: text.headlineSmall?.copyWith(
                fontFamily: MedoraFonts.serif,
                color: MedoraColors.primary,
              ),
            ),
            Text(label, style: text.bodySmall),
          ],
        ),
      ),
    );
    final mode = (s?['byMode'] as Map?) ?? const {};
    return AlertDialog(
      key: const Key('client-summary'),
      title: Text('${widget.client['name']}: usage'),
      content: SizedBox(
        width: 580,
        child: _error != null
            ? Text(_error!)
            : s == null
            ? const Padding(
                padding: EdgeInsets.all(30),
                child: Center(child: CircularProgressIndicator()),
              )
            : SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        figure(
                          'Patients',
                          s['patients'],
                          Icons.people_alt_outlined,
                        ),
                        figure('Visits', s['visits'], Icons.event_note),
                        figure(
                          'Visits, last 7 days',
                          s['visitsLast7Days'],
                          Icons.date_range,
                        ),
                        figure(
                          'Visits, last 30 days',
                          s['visitsLast30Days'],
                          Icons.calendar_month_outlined,
                        ),
                        figure(
                          'Reports made',
                          s['reports'],
                          Icons.description_outlined,
                        ),
                        figure(
                          'Signed by a doctor',
                          s['signedByDoctor'],
                          Icons.verified_outlined,
                        ),
                        figure(
                          'Doctors',
                          s['doctors'],
                          Icons.medical_services_outlined,
                        ),
                        figure(
                          'Departments',
                          s['departments'],
                          Icons.account_tree_outlined,
                        ),
                        figure(
                          'Hospital admins',
                          s['hospitalAdmins'],
                          Icons.admin_panel_settings_outlined,
                        ),
                        figure(
                          'API calls, 24 h',
                          s['apiCalls24h'],
                          Icons.swap_horiz_rounded,
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'How patients came in: voice ${mode['voice'] ?? 0} · '
                      'typed ${mode['manual'] ?? 0} · '
                      'own phone ${mode['phone'] ?? 0}',
                      style: text.bodyMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Last visit: ${s['lastVisitAt'] == null ? '–' : formatDate(s['lastVisitAt'])}'
                      '  ·  Client since: ${s['createdAt'] == null ? '–' : formatDate(s['createdAt'])}',
                      style: text.bodyMedium,
                    ),
                  ],
                ),
              ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
      ],
    );
  }
}
