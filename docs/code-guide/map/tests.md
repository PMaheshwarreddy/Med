# `tests`

## `backend/tests/test_api.py` (985 lines)

Settings and constants:
- **L9** `ADMIN`
- **L11** `SESSION`
- **L92** `VITALS`

Functions and classes:
- **L21–35** `def _seed_admin`  
  Signs a back-office user in, so `ADMIN` works as a session token.
- **L38–51** `def client`
- **L54–55** `def test_health`
- **L58–65** `def test_default_client_config`
- **L68–75** `def test_session_create_is_public_but_listing_is_not`
- **L78–80** `def test_session_validation`
- **L83–87** `def test_back_office_needs_a_signed_in_user`
- **L95–111** `class FakeLlm`
  - **L98–106** `def __init__`
  - **L108–111** `async def json`
- **L114–115** `def _new_session`
- **L118–124** `def test_status_reports_unconfigured_services`
- **L127–133** `def test_vitals_are_what_the_band_measured`
- **L136–142** `def test_unmeasured_vitals_are_named_in_the_case`
- **L145–151** `def test_report_progress_is_readable_while_and_after_it_runs`
- **L154–176** `def test_report_vitals_can_only_raise_urgency`
- **L179–187** `def test_report_without_vitals_and_with_bad_model_output`
- **L190–197** `def test_send_requires_configuration`
- **L200–202** `def test_voice_unavailable_without_provider`
- **L205–229** `def test_voice_relays_between_browser_and_provider`
- **L232–238** `def test_voice_tool_arguments_are_cleaned`
- **L244–247** `def _new_client`
- **L250–275** `def test_each_client_has_its_own_key_settings_and_sessions`
- **L278–298** `def test_rotating_or_switching_off_a_client_locks_its_kiosks`
- **L301–328** `def test_activity_is_logged_per_client`
- **L331–356** `def test_offline_mode_is_reported_and_voice_needs_internet`
- **L359–375** `def test_voice_respects_the_clients_switches`
- **L378–408** `def test_rows_are_mirrored_to_the_cloud_once`
- **L411–426** `def test_older_databases_are_upgraded_in_place`
- **L438–468** `def test_api_keys_identify_the_client_and_every_call_is_logged`
- **L471–492** `def test_back_office_can_preview_a_clients_kiosk`
- **L495–508** `def test_system_settings_and_dashboard_figures`
- **L514–516** `def _fresh`
- **L519–553** `def test_first_account_claims_the_installation_and_approves_the_rest`
- **L556–560** `def test_with_open_registration_every_account_works_at_once`
- **L563–581** `def test_sign_in_sign_out_and_lockout`
- **L584–592** `def test_passwords_and_tokens_are_not_stored_readable`
- **L598–636** `def test_vitals_are_skipped_only_on_a_clear_no_from_the_hosted_model`
- **L639–657** `def test_an_unexpected_failure_still_gives_the_patient_a_report`
- **L660–734** `def test_voice_tools_decide_on_vitals_and_never_measure_twice`
- **L737–790** `def test_offline_visits_are_served_from_memory_and_copied_back`
- **L793–802** `def test_a_small_local_model_is_still_not_trusted_offline`
- **L805–864** `def test_every_patient_report_comes_in_simple_english_and_malayalam`
- **L867–908** `def test_an_english_visit_gets_an_english_only_report_with_the_doctors_medicines`
- **L910–916** `def test_the_voice_agent_speaks_the_chosen_language`
- **L919–951** `def test_allergies_and_the_pregnancy_answer_reach_the_report_rules`
- **L955–960** `def test_status_gives_the_servers_network_address_for_qr_codes`
- **L963–984** `def test_dashboard_counts_days_in_the_viewers_time_zone`  
  A visit at 20:00 UTC yesterday is today in India (01:30 IST).

## `backend/tests/test_doctor.py` (376 lines)

Patients, the doctor portal, the signed final report, and the phone
hand-off.

Functions and classes:
- **L8–16** `def _doctor`
- **L19–28** `class Writer`  
  Answers every model call the report pipeline makes, plainly.
  - **L24–28** `async def json`
- **L31–37** `def _visit`
- **L40–71** `def test_returning_patients_are_found_by_an_earlier_visit_number_with_their_full_name`
- **L74–89** `def test_the_doctor_report_shows_everything_but_the_patient_waits_for_the_doctor`
- **L92–173** `def test_a_doctor_picks_reviews_and_signs_and_the_patient_gets_the_final_report`
- **L176–192** `def test_the_doctor_chooses_the_language_of_the_signed_report`
- **L195–203** `def test_old_hospital_lines_are_hidden_from_the_company_log`
- **L206–229** `def test_the_queue_follows_the_doctors_department_and_a_release_frees_the_patient`
- **L232–259** `def test_doctor_only_medicines_and_ai_percentages`
- **L262–284** `def test_the_intake_can_be_filled_on_the_patients_phone`
- **L287–323** `def test_the_phone_hand_off_works_offline_and_the_visit_joins_its_record_later`
- **L326–348** `def test_the_patients_copy_shows_the_ai_percentage_and_no_none_lines`
- **L351–375** `def test_the_doctor_gets_type_ahead_for_medicines_diagnoses_and_tests`

## `backend/tests/test_hospital.py` (182 lines)

The hospital portal: its own accounts, scoped to one hospital.

Functions and classes:
- **L6–12** `def _hospital`  
  A client (tenant) with its kiosk key, made in the company back office.
- **L15–33** `def _admin_of`  
  The hospital's first admin, signed in with a changed password.
- **L36–54** `def test_the_company_opens_a_hospital_portal_and_accounts_stay_apart`
- **L57–112** `def test_the_hospital_admin_manages_departments_and_doctors`
- **L115–141** `def test_a_hospital_sees_only_its_own_visits_and_opening_one_is_audited`
- **L144–161** `def test_hospital_settings_and_a_switched_off_hospital`
- **L164–181** `def test_a_client_is_created_with_its_hospital_admin_and_password`

## `backend/tests/test_ingest.py` (375 lines)

Settings and constants:
- **L13** `LINK_PLAN`
- **L271** `OWL`
- **L293** `MESH`

Functions and classes:
- **L24–38** `class ScriptedLlm`  
  Answers from a list, in order, and records what it was asked.
  - **L29–31** `def __init__`
  - **L33–38** `async def json`
- **L41–42** `def run`
- **L48–61** `def test_csv_rows_are_repaired`
- **L64–84** `def test_json_records_are_found_and_streamed`
- **L87–97** `def test_obo_terms`
- **L100–107** `def test_format_comes_from_content_not_name`
- **L113–128** `def test_names_are_cleaned_and_matched`
- **L131–141** `def test_name_validation`
- **L144–150** `def test_text_is_capped_at_a_sentence_and_headings_dropped`
- **L153–166** `def test_apply_plan_stages_and_rejects`
- **L172–180** `def test_plan_validation`
- **L183–195** `def test_planner_retries_an_unexecutable_plan`
- **L198–219** `def test_article_extraction_drops_names_not_in_the_text`
- **L225–235** `def test_nested_json_records_are_located`
- **L238–245** `def test_obo_keeps_exact_synonyms_only`
- **L248–268** `def test_bracketed_names_and_reversed_rows`
- **L330–339** `def test_owl_classes_are_read_like_obo_terms`
- **L342–354** `def test_xml_records_are_streamed_as_json_like_data`
- **L357–374** `def test_a_plan_may_pick_the_first_of_a_listed_field`

## `backend/tests/test_kb.py` (377 lines)

Knowledge-base pipeline (app/kb): the checks and parsers that stand in for
a person reviewing each page. No database or network needed.

Settings and constants:
- **L14** `PAGE`

Functions and classes:
- **L18–19** `def test_numbers_are_written_one_way`
- **L22–24** `def test_a_number_the_page_lacks_is_caught`
- **L27–29** `def test_coverage_counts_the_pages_words`
- **L32–38** `def test_dose_rows_need_a_medicine_an_amount_and_the_pages_numbers`
- **L41–44** `def test_a_source_with_too_many_refusals_fails_whole`
- **L47–52** `def test_chunks_fit_and_tables_keep_their_header`
- **L55–61** `def test_spellings_from_different_sources_share_one_key`
- **L64–69** `def test_bundle_records_every_spelling_as_a_drug_term`
- **L72–78** `def test_nfi_labels_tolerate_the_books_spelling_slips`
- **L81–84** `def test_nfi_drug_names_drop_headings_and_cross_references`
- **L87–93** `def test_stw_boilerplate_and_transcript`
- **L96–105** `def test_every_source_states_its_licence_and_reader`
- **L108–111** `def test_salt_only_medicines_keep_their_whole_name_for_us_labels`
- **L114–123** `def test_brand_compositions_are_parsed_into_medicine_and_strength`
- **L126–141** `def test_reversed_symptom_rows_are_refused`
- **L144–151** `def test_appendix_cell_starts_come_from_repeated_cell_positions`
- **L160–161** `def _passage`
- **L164–188** `class FakeRetriever`
  - **L165–167** `def __init__`
  - **L169–175** `def search`
  - **L177–184** `def condition_doses`
  - **L186–188** `def doses`
- **L191–192** `class _Session`
- **L195–206** `def test_pass_one_asks_about_the_presentation_and_pass_two_about_the_conditions`
- **L209–212** `def test_without_a_database_the_passes_say_so_instead_of_failing`
- **L215–226** `def test_a_written_dose_is_checked_against_guidelines_and_printed_doses`
- **L229–233** `def test_dose_found_needs_the_medicine_named_and_every_number`
- **L236–244** `def test_brands_the_patient_took_are_spelled_out_for_the_models`
- **L248–257** `def test_printed_doses_for_the_concluded_conditions_suit_the_patients_age`
- **L260–265** `def test_stw_titles_lose_the_series_prefix`
- **L268–278** `def test_guideline_reader_headings_kinds_and_charts`
- **L281–287** `def test_dose_found_needs_the_dose_on_the_medicines_own_line`
- **L290–313** `def test_pass_two_adds_the_patients_box_from_the_same_page_and_drops_other_groups`
- **L316–324** `def test_dose_conflicts_quote_the_guideline_line_for_the_reviewer`
- **L328–331** `def test_dose_found_ignores_the_tablet_count`
- **L334–352** `def test_an_unreachable_knowledge_database_is_not_retried_for_every_look_up`
- **L355–358** `def test_pass_one_also_reads_the_pages_of_the_conditions_to_look_up`
- **L361–366** `def test_a_condition_name_becomes_the_words_a_guideline_heading_uses`
- **L369–376** `def test_the_offline_case_carries_fewer_shorter_passages`

## `backend/tests/test_kb_uploads.py` (183 lines)

Knowledge in the knowledge database only: data files and the old tables
become kb_* rows, the symptom index reads those rows (or its disk copy), and
the back office's Database tab works from the knowledge database.

Settings and constants:
- **L21** `LINK_PLAN`

Functions and classes:
- **L29–38** `def index_rows`  
  What KnowledgeIndex.read_rows returns for these bundles' rows.
- **L41–58** `def test_a_planned_data_file_becomes_knowledge_rows_that_the_index_searches`
- **L61–74** `def test_enrich_rows_only_add_to_what_another_source_has`
- **L77–92** `def test_the_old_knowledge_tables_become_the_same_rows`
- **L95–107** `def test_the_index_serves_its_disk_copy_when_the_database_is_unreachable`
- **L110–138** `def test_upload_kinds_and_what_the_uploader_must_say`
- **L141–146** `def test_which_sources_reports_use`
- **L149–156** `def test_the_numbers_stay_visible_while_the_database_is_down`
- **L159–167** `def client`
- **L170–182** `def test_the_database_tab_reads_only_the_knowledge_database`

## `backend/tests/test_report_writer.py` (31 lines)

Functions and classes:
- **L3–12** `def test_a_skin_cream_needs_its_strength_and_how_to_apply_it`
- **L15–30** `def test_the_condition_check_never_drops_the_most_likely_condition_for_a_less_likely_one`

## `backend/tests/test_triage.py` (708 lines)

The report pipeline: retrieval, the specialist panel, and the safety rules.

Settings and constants:
- **L14** `KNOWLEDGE`
- **L290** `UTI_PANEL`
- **L294** `UTI_SYMPTOMS`
- **L416** `UTI_DRAFT`
- **L430** `APPROVE_ALL_BUT_LAST`

Functions and classes:
- **L22–35** `class WordEmbedder`  
  Bag-of-words vectors: enough to stand in for meaning in a test.
  - **L28–35** `def embed`
- **L38–50** `def knowledge_rows`  
  Rows as the index reads them from the knowledge database.
- **L53–55** `def kb`
- **L58–63** `def session_for`
- **L66–105** `class Understander`  
  Stands in for the model: answers each step by its instructions.
  - **L71–82** `def __init__`
  - **L84–105** `async def json`
- **L108–127** `class FakePanel`
  - **L111–113** `def __init__`
  - **L115–127** `async def run`
- **L130–131** `def run`
- **L137–149** `def test_retrieval_ranks_the_disease_that_explains_the_symptoms`
- **L152–157** `def test_retrieval_matches_by_meaning_and_from_free_text`
- **L160–163** `def test_reversed_rows_never_become_candidates`
- **L166–172** `def test_lookup_finds_a_condition_by_contained_name`
- **L178–186** `def test_panel_membership`
- **L189–194** `def test_department_is_a_real_department`
- **L197–201** `def test_model_replies_are_parsed_leniently`
- **L204–245** `def test_report_grounds_conditions_and_medicines_in_the_knowledge_base`
- **L248–268** `def test_urgency_can_only_be_raised`
- **L271–285** `def test_without_the_panel_no_conditions_or_medicines_are_offered`
- **L297–299** `def precautions_for`
- **L302–321** `def test_knowledge_base_precautions_are_offered_first_and_only_selected`
- **L324–347** `def test_missing_precautions_are_written_then_filtered_and_reviewed`
- **L350–360** `def test_written_precautions_are_not_shown_without_a_review`
- **L363–379** `def test_emergency_precautions_start_with_calling_for_help`
- **L382–392** `def test_a_specialist_who_stepped_aside_is_credited_with_nothing`
- **L395–413** `def test_progress_follows_the_real_panel`
- **L437–442** `def written_report`
- **L445–465** `def test_medicines_are_written_reviewed_then_ruled_by_code`
- **L468–481** `def test_no_written_medicines_without_review_for_children_or_in_an_emergency`
- **L484–497** `def test_without_the_panel_online_the_writer_names_reviewed_conditions`
- **L500–509** `def test_vitals_are_judged_against_normal_ranges`
- **L512–530** `def test_the_review_drops_panel_conditions_the_patient_s_account_does_not_support`
- **L533–554** `def test_the_report_never_names_pregnancy_or_sexual_health_unless_the_patient_did`
- **L557–579** `def test_guideline_passages_reach_the_panel_and_writer_and_stay_with_the_doctor`
- **L583–595** `def test_the_report_model_writes_the_final_report_and_the_panel_model_does_not`  
  writer_llm takes the draft, the condition check and the review; the main model keeps symptom understanding and precautions.
- **L598–604** `def test_a_child_sent_to_general_opd_goes_to_pediatrics`
- **L607–614** `def test_a_condition_finds_its_knowledge_base_disease_by_another_name`
- **L617–630** `def test_offline_the_chair_concludes_alone_and_precautions_need_no_model`
- **L633–666** `def test_local_model_calls_take_turns`
- **L669–694** `def test_a_stuck_model_call_is_stopped_and_tried_once_more`
- **L697–707** `def test_finished_parts_are_shown_while_the_report_is_written`

## `backend/tests/test_voice.py` (70 lines)

Functions and classes:
- **L3–9** `def test_greeting_is_short_and_english_and_asks_the_language_only_after_a_bare_hello`
- **L12–23** `def test_age_and_gender_come_first_and_habits_are_for_every_adult`
- **L26–32** `def test_one_question_per_reply_and_an_answer_fills_only_its_own_question`
- **L35–44** `def test_vitals_are_always_taken_and_the_band_is_shown_by_the_tool_call`
- **L47–53** `def test_malayalam_starts_in_malayalam_with_the_right_greeting`
- **L56–63** `def test_a_restarted_conversation_carries_on_and_resume_says_no_welcome_back`
- **L66–69** `def test_patient_speech_is_transcribed_as_english_or_malayalam`
