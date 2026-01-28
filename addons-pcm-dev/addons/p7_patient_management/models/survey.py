# -*- coaction_case_guide_updateing: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, time as dt_time
import logging
_logger = logging.getLogger(__name__)

class survey_update(models.Model):
    _inherit = 'survey.survey'

    question_and_page_ids = fields.One2many('survey.question', 'survey_id', string='Sections and Questions', copy=False)
    type_of_survey = fields.Selection(
        [('medical_history', 'Medical History Questionnaire'), ('feedback', 'Feedback Survey')], string="Type")
    template_type = fields.Selection([('reference', 'Reference Template'), ('personal', 'Personal Template')],
                                     string="Template Type")
    users_can_go_back = fields.Boolean('Users can go back', help="If checked, users can go back to previous pages.",
                                       default=False)
    state = fields.Selection(selection=[('draft', 'Draft'), ('release', 'Released'), ], string='Status', required=True,
                             readonly=True, default='draft', )
    version = fields.Char(string='Version')
    note = fields.Text('Note')
    released_date = fields.Date("Release Date")
    is_super_admin = fields.Boolean(compute='_compute_is_super_admin', store=False)
    survey_type = fields.Selection([
        ('survey', 'Survey'),
        ('live_session', 'Live session'),
        ('assessment', 'Assessment'),
        ('custom', 'Custom'),
    ], string='Survey Type', required=True, default='custom')
    surgic_ques_and_page_ids = fields.One2many('survey.question', 'surgic_survey_id',
                                               string='Surgery History Questions', copy=True)
    medic_ques_and_page_ids = fields.One2many('survey.question', 'medic_survey_id', string='Medical History Questions',
                                              copy=True)
    patient_ques_and_page_ids = fields.One2many('survey.question', 'patient_survey_id', string='Detailed Questions',
                                                copy=True)
    bio_ques_and_page_ids = fields.One2many('survey.question', 'bio_survey_id', string='Bio Questions', copy=True)
    is_height_ques_enabled = fields.Boolean("Height Question", default=False)
    is_weight_ques_enabled = fields.Boolean("Weight Question", default=False)
    is_surgery_ques_enabled = fields.Boolean("Surgery History Questions", default=False,
                                             help="By enabling this, the questions below will be added at the end of the survey,\n"
                                                  "1.Have you ever had surgery?\n"
                                                  "2.Year of surgery (YYYY)?\n"
                                                  "3.Location (hospital/clinic)?\n"
                                                  "4.What surgery?\n")
    is_medic_ques_enabled = fields.Boolean("Medication History Questions", default=False,
                                           help="By enabling this, the questions below will be added at the end of the survey,\n"
                                                "1.Are you taking any chronic medications?\n"
                                                "2.Name of medication?\n"
                                                "3.What is the dosage and frequency?\n"
                                                "4.Using since which year? (YYYY)\n")
    surgery_ques = fields.Text(string='Surgery History Question',
                               readonly=True,
                               default="1.Have you ever had surgery?\n"
                                       "2.Year of surgery (YYYY)?\n"
                                       "3.Location (hospital/clinic)?\n"
                                       "4.What surgery?\n")
    medication_ques = fields.Text(string='Medication History Question',
                                  readonly=True,
                                  default="1.Are you taking any chronic medications?\n"
                                          "2.Name of medication?\n"
                                          "3.What is the dosage and frequency?\n"
                                          "4.Using since which year? (YYYY)\n")

    _SEQUENCE_PRIORITY = [
        "What is your height (cm)?",
        "height",
        "What is your weight (KG)?",
        "weight",
        "normal",
        False,
        "Have you ever had surgery?",
        "surgery",
        "Are you taking any chronic medications?",
        "medical",
    ]

    _SEQUENCE_PRIORITY_SURGERY = [
        "Year of surgery (YYYY)",
        "Location (hospital/clinic)",
        "What surgery?"
    ]

    _SEQUENCE_PRIORITY_MEDIC = [
        "Name of medication?",
        "What is the dosage and frequency?",
        "Using since which year? (YYYY)"
    ]

    def _update_survey_question_sequence(self):
        self.ensure_one()
        queries_for_seq_udpate = []
        seq = 1

        # need to invalidate cache due to sequence update is still not in record cache
        self.invalidate_recordset(['question_and_page_ids'], flush=False)
        questions = self.question_and_page_ids
        proceeded_questions = self.env["survey.question"]

        for seq_question in self._SEQUENCE_PRIORITY:
            filtered_questions = questions.filtered(lambda q: q.title == seq_question or q.question_tag == seq_question)

            for question in filtered_questions:
                if question.triggering_question_ids - proceeded_questions:
                    continue

                if question in proceeded_questions:
                    continue

                proceeded_questions |= question

                queries_for_seq_udpate.append(f"UPDATE survey_question SET sequence = {seq} WHERE id = {question['id']}")
                seq += 1

                linked_questions = questions.filtered(lambda q: question in q.triggering_question_ids)
                questions -= linked_questions
                proceeded_questions |= linked_questions

                if question.title == "Have you ever had surgery?":

                    for seq_question_s in self._SEQUENCE_PRIORITY_SURGERY:
                        dep_questions = linked_questions.filtered(lambda q: q.title == seq_question_s)
                        linked_questions -= dep_questions

                        for q in dep_questions:
                            queries_for_seq_udpate.append(f"UPDATE survey_question SET sequence = {seq} WHERE id = {q['id']}")
                            seq += 1

                elif question.title == "Are you taking any chronic medications?":

                    for seq_question_m in self._SEQUENCE_PRIORITY_MEDIC:
                        dep_questions = linked_questions.filtered(lambda q: q.title == seq_question_m)
                        linked_questions -= dep_questions

                        for q in dep_questions:
                            queries_for_seq_udpate.append(f"UPDATE survey_question SET sequence = {seq} WHERE id = {q['id']}")
                            seq += 1

                for rem_question in linked_questions:
                    queries_for_seq_udpate.append(f"UPDATE survey_question SET sequence = {seq} WHERE id = {rem_question['id']}")
                    seq += 1

            questions -= filtered_questions

        if queries_for_seq_udpate:
            self.env.cr.execute("; ".join(queries_for_seq_udpate))
        return True

    def _compute_is_super_admin(self):
        for rec in self:
            rec.is_super_admin = self.env.user.has_group('p7_patient_management.group_user_super_admin')

    def unlink(self):
        if self.env.user.has_group('p7_patient_management.group_user_doctor') or \
           self.env.user.has_group('p7_patient_management.group_user_doctor_premium'):
            for survey in self:
                if survey.user_input_ids:
                    raise UserError(_('You cannot delete a template that already has participants. Please archive it instead.'))
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        surveys = super(survey_update, self).create(vals_list)
        for survey in surveys:
            if survey.type_of_survey == 'medical_history':
                # Surgery Questions
                surques1 = self.env['survey.question'].create({
                    'surgic_survey_id': survey.id,
                    'title': 'Have you ever had surgery?',
                    'question_type': 'simple_choice',
                    'constr_mandatory': True,
                    'question_tag': 'surgery',
                })

                # Answers
                answer_yes = self.env['survey.question.answer'].create([
                    {'question_id': surques1.id, 'value': 'Yes'},
                ])

                answer_no = self.env['survey.question.answer'].create([
                    {'question_id': surques1.id, 'value': 'No'},
                ])

                # related questions
                surques2 = self.env['survey.question'].create({
                    'surgic_survey_id': survey.id,
                    'title': 'Year of surgery (YYYY)',
                    'question_type': 'char_box',
                    'constr_mandatory': True,
                    'validation_required': True,
                    'question_placeholder': '2021',
                    'validation_length_min': 4,
                    'validation_length_max': 4,
                    'question_tag': 'surgery',
                    'triggering_answer_ids': [(6, 0, [answer_yes.id])],
                })
                
                surques3 = self.env['survey.question'].create({
                    'surgic_survey_id': survey.id,
                    'title': 'Location (hospital/clinic)',
                    'question_type': 'char_box',
                    'constr_mandatory': True,
                    'question_tag': 'surgery',
                    'triggering_answer_ids': [(6, 0, [answer_yes.id])],
                })
                
                surques4 = self.env['survey.question'].create({
                    'surgic_survey_id': survey.id,
                    'title': 'What surgery?',
                    'question_type': 'char_box',
                    'constr_mandatory': True,
                    'is_repeat_question': True,
                    'suffix': 'Surgery',
                    'question_tag': 'surgery',
                    'triggering_answer_ids': [(6, 0, [answer_yes.id])],
                })
                
                # Medical Questions
                medques1 = self.env['survey.question'].create({
                    'medic_survey_id': survey.id,
                    'title': 'Are you taking any chronic medications?',
                    'question_type': 'simple_choice',
                    'constr_mandatory': True,
                    'question_tag': 'medical',
                })

                # Answers
                answer_yes_med = self.env['survey.question.answer'].create([
                    {'question_id': medques1.id, 'value': 'Yes'},
                ])

                answer_no_med = self.env['survey.question.answer'].create([
                    {'question_id': medques1.id, 'value': 'No'},
                ])

                # related questions
                medques2 = self.env['survey.question'].create({
                    'medic_survey_id': survey.id,
                    'title': 'Name of medication?',
                    'question_type': 'char_box',
                    'constr_mandatory': True,
                    'medic_details': True,
                    'question_tag': 'medical',
                    'triggering_answer_ids': [(6, 0, [answer_yes_med.id])],
                })
                
                medques3 = self.env['survey.question'].create({
                    'medic_survey_id': survey.id,
                    'title': 'What is the dosage and frequency?',
                    'question_type': 'char_box',
                    'constr_mandatory': True,
                    'question_tag': 'medical',
                    'question_placeholder': 'eg 1 tablet 3 times a day / 500mg every morning / one injection every Tuesday',
                    'triggering_answer_ids': [(6, 0, [answer_yes_med.id])],
                })
                
                medques4 = self.env['survey.question'].create({
                    'medic_survey_id': survey.id,
                    'title': 'Using since which year? (YYYY)',
                    'question_type': 'char_box',
                    'constr_mandatory': True,
                    'is_repeat_question': True,
                    'question_placeholder': '2021',
                    'suffix': 'Medication',
                    'question_tag': 'medical',
                    'triggering_answer_ids': [(6, 0, [answer_yes_med.id])],
                })

                # Bio Questions
                height = self.env['survey.question'].create({
                    'bio_survey_id': survey.id,
                    'title': 'What is your height (cm)?',
                    'question_type': 'numerical_box',
                    'constr_mandatory': True,
                    'validation_required': True,
                    'validation_min_float_value': 30.00,
                    'validation_max_float_value': 300.00,
                    'validation_error_msg': 'Enter between 30.00 and 300.00 cm.',
                    'question_placeholder': '152.0',
                    'question_tag': 'height'
                })

                weight = self.env['survey.question'].create({
                    'bio_survey_id': survey.id,
                    'title': 'What is your weight (KG)?',
                    'question_type': 'numerical_box',
                    'constr_mandatory': True,
                    'question_tag': 'weight'
                })

                if survey.is_surgery_ques_enabled:
                    survey._surgery_questions()
                if survey.is_medic_ques_enabled:
                    survey._medic_questions()
                if survey.is_weight_ques_enabled:
                    survey._weight_questions()
                if survey.is_height_ques_enabled:
                    survey._height_questions()

        return surveys

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        """Correctly copy the 'triggering_answer_ids' field from the original to the clone.

        This needs to be done in post-processing to make sure we get references to the newly
        created answers from the copy instead of references to the answers of the original.
        This implementation assumes that the order of created answers will be kept between
        the original and the clone, using 'zip()' to match the records between the two.

        Note that when `question_ids` is provided in the default parameter, it falls back to the
        standard copy, meaning that triggering logic will not be maintained.
        """
        survey_questions = SurveyQuestion = self.env["survey.question"]

        survey_data = self.read([
            "title", "template_type", "type_of_survey", "questions_layout", "users_login_required",
            "is_attempts_limited", "access_mode", "attempts_limit", "is_surgery_ques_enabled",
            "is_medic_ques_enabled", "is_height_ques_enabled", "is_weight_ques_enabled"
        ])[0]

        is_height = survey_data["is_height_ques_enabled"]
        is_weight = survey_data["is_weight_ques_enabled"]
        is_medic_survery = survey_data["type_of_survey"] == "medical_history"

        template_values = {
            "title": survey_data["title"] + " (copy)",
            "template_type": self.env.context.get("template_type") or survey_data["template_type"],
            "type_of_survey": survey_data["type_of_survey"],
            "state": "draft",
            "user_id": self.env.user.id,
            "questions_layout": survey_data["questions_layout"],
            "users_login_required": survey_data["users_login_required"],
            "is_attempts_limited": survey_data["is_attempts_limited"],
            "access_mode": survey_data["access_mode"],
            "attempts_limit": survey_data["attempts_limit"],
            "users_can_go_back": False,
            "is_surgery_ques_enabled": survey_data["is_surgery_ques_enabled"] if is_medic_survery else False,
            "is_medic_ques_enabled": survey_data["is_medic_ques_enabled"] if is_medic_survery else False,
            "is_height_ques_enabled": is_height if is_medic_survery else False,
            "is_weight_ques_enabled": is_weight if is_medic_survery else False,
            "progression_mode": "percent",
            "is_time_limited": False,
            "scoring_type": "no_scoring",
            "questions_selection": "all",
        }
        personal_template = self.create(template_values)
        pt_id = personal_template.id

        questions_vals = []
        for rec in self.patient_ques_and_page_ids:
            update_vals = {}
            for fname in ("survey_id", "surgic_survey_id", "medic_survey_id", "patient_survey_id", "bio_survey_id"):
                if getattr(rec, fname):
                    update_vals[fname] = pt_id

            questions_vals.append(rec.sudo().copy_data(update_vals)[0])


        survey_questions = SurveyQuestion.sudo().create(questions_vals)
        survey_questions |= (
            personal_template.bio_ques_and_page_ids
            | personal_template.surgic_ques_and_page_ids
            | personal_template.medic_ques_and_page_ids
        )

        question_map = {q.title: q for q in survey_questions}

        answers_map = {}
        ques = self.question_and_page_ids.filtered(lambda q: not q.is_duplicated)

        for src in ques:
            dst = question_map.get(src.title)
            if not dst:
                continue
            for src_answer, dst_answer in zip(
                src.suggested_answer_ids.sorted(key=lambda x: x.value),
                dst.suggested_answer_ids.sorted(key=lambda x: x.value)
            ):
                answers_map[src_answer.id] = dst_answer.id

        for src in ques:
            dst = question_map.get(src.title)
            if dst and src.triggering_answer_ids:
                dst.triggering_answer_ids = [
                    answers_map[src_answer_id.id]
                    for src_answer_id in src.triggering_answer_ids
                    if src_answer_id.id in answers_map
                ]

        personal_template.with_context(skip_sequence_update=True).write({
            "is_height_ques_enabled": is_height,
            "is_weight_ques_enabled": is_weight
        })
        personal_template._update_survey_question_sequence()
        return personal_template

    def finalise(self):
        if not self.version:
            raise ValidationError(_('Please enter valid version number!'))
        self.write({'state': 'release', 'released_date': fields.Date.context_today(self)})
        self._message_log(body=_(
            "Questionnaire Released.\n"
            "Version: %s", self._get_html_link(title=f" {self.version}")
        ))

    def create_personel_template(self):
        personal_template = self.with_context(template_type="personal").copy()
        action = self.env.ref('p7_patient_management.action_medic_history_template_custom').read()[0]
        if self.type_of_survey == 'feedback':
            action = self.env.ref('p7_patient_management.action_feedback_template_custom').read()[0]
        return action

    def reset_to_draft(self):
        self.state = 'draft'

    def _prepare_medic_questions_vals(self):
        return [
            {
                "title": "Are you taking any chronic medications?",
                "question_type": "simple_choice",
                "constr_mandatory": True,
                "question_tag": "medical",
                "triggering_answer_ids": [(5, 0, 0)],
                "survey_id": self.id,
                "medic_survey_id": self.id,
            },
            {
                "title": "Name of medication?",
                "question_type": "char_box",
                "constr_mandatory": True,
                "medic_details": True,
                "question_tag": "medical",
                "medic_survey_id": self.id,
                "survey_id": self.id,
            },
            {
                "title": "What is the dosage and frequency?",
                "question_type": "char_box",
                "constr_mandatory": True,
                "question_tag": "medical",
                "question_placeholder": "eg 1 tablet 3 times a day / 500mg every morning / one injection every Tuesday",
                "medic_survey_id": self.id,
                "survey_id": self.id,
            },
            {
                "title": "Using since which year? (YYYY)",
                "question_type": "char_box",
                "constr_mandatory": True,
                "question_placeholder": "2021",
                "suffix": "Medication",
                "question_tag": "medical",
                "medic_survey_id": self.id,
                "survey_id": self.id,
            }
        ]

    def _medic_questions(self):
        SurveyQuestion = self.env["survey.question"]
        SurveyQuestionAnswer = self.env["survey.question.answer"]

        for survey in self:
            if not survey._origin.id:
                raise ValidationError(_('Please save the record manually before changing the question options!'))

            questions = SurveyQuestion.search([
                ("medic_survey_id", "=", survey._origin.id),
                ("question_tag", "=", "medical")
            ])

            if survey.is_medic_ques_enabled:
                if not questions:
                    medical_questions_vals = survey._prepare_medic_questions_vals()
                    questions = SurveyQuestion.create(medical_questions_vals)

                main_question = questions.filtered(lambda q: q.title == "Are you taking any chronic medications?")
                yes_answer = SurveyQuestionAnswer

                if main_question:
                    answers = main_question.suggested_answer_ids.filtered(lambda a: a.value in ("Yes", "No"))
                    answers_values = answers.mapped("value")
                    if "Yes" not in answers_values:
                        answers |= SurveyQuestionAnswer.create({"question_id": main_question.id, "value": "Yes"})
                    if "No" not in answers_values:
                        answers |= SurveyQuestionAnswer.create({"question_id": main_question.id, "value": "No"})
                    yes_answer = answers.filtered(lambda a: a.value == "Yes")

                    main_question.write({"triggering_answer_ids": [(5, 0, 0)], "survey_id": survey.id})

                if yes_answer:
                    for question in (questions - main_question):
                        question.write({"triggering_answer_ids": [(6, 0, yes_answer.ids)], "survey_id": survey.id})
            else:
                questions.write({"survey_id": False})

    def _prepare_surgery_questions_vals(self):
        return [
            {
                "surgic_survey_id": self.id,
                "title": "Have you ever had surgery?",
                "question_type": "simple_choice",
                "constr_mandatory": True,
                "question_tag": "surgery",
                "triggering_answer_ids": [(5, 0, 0)],
                "survey_id": self.id,
            },
            {
                "surgic_survey_id": self.id,
                "title": "Year of surgery (YYYY)",
                "question_type": "char_box",
                "constr_mandatory": True,
                "validation_required": True,
                "validation_length_min": 4,
                "validation_length_max": 4,
                "question_tag": "surgery",
                "survey_id": self.id,
            },
            {
                "surgic_survey_id": self.id,
                "title": "Location (hospital/clinic)",
                "question_type": "char_box",
                "constr_mandatory": True,
                "question_tag": "surgery",
                "survey_id": self.id,
            },
            {
                "surgic_survey_id": self.id,
                "title": "What surgery?",
                "question_type": "char_box",
                "constr_mandatory": True,
                "is_repeat_question": True,
                "suffix": "Surgery",
                "question_tag": "surgery",
                "survey_id": self.id,
            }
        ]

    def _surgery_questions(self):
        SurveyQuestion = self.env["survey.question"]
        SurveyQuestionAnswer = self.env["survey.question.answer"]

        for survey in self:
            if not survey._origin.id:
                raise ValidationError(_("Please save the record manually before changing the question options!"))

            questions = SurveyQuestion.search([
                ("surgic_survey_id", "=", survey._origin.id),
                ("question_tag", "=", "surgery")
            ])

            if survey.is_surgery_ques_enabled:
                if not questions:
                    surgery_questions_vals = survey._prepare_surgery_questions_vals()
                    questions = SurveyQuestion.create(surgery_questions_vals)

                main_question = questions.filtered(lambda q: q.title == "Have you ever had surgery?")
                yes_answer = SurveyQuestionAnswer

                if main_question:
                    answers = main_question.suggested_answer_ids.filtered(lambda a: a.value in ("Yes", "No"))
                    answers_values = answers.mapped("value")
                    if "Yes" not in answers_values:
                        answers |= SurveyQuestionAnswer.create({"question_id": main_question.id, "value": "Yes"})
                    if "No" not in answers_values:
                        answers |= SurveyQuestionAnswer.create({"question_id": main_question.id, "value": "No"})
                    yes_answer = answers.filtered(lambda a: a.value == "Yes")

                    main_question.write({"triggering_answer_ids": [(5, 0, 0)], "survey_id": survey.id})

                if yes_answer:
                    for question in (questions - main_question):
                        question.write({"triggering_answer_ids": [(6, 0, yes_answer.ids)], "survey_id": survey.id})
            else:
                questions.write({"survey_id": False})

    def _find_height_weight_question(self, question_tag):
        return self.env["survey.question"].search(
            [("bio_survey_id", "=", self.id), ("question_tag", "=", question_tag)], limit=1)

    @api.model
    def _create_or_update_height_question(self, survey_id, height_question=False):
        height_question_vals = {
            "bio_survey_id": survey_id,
            "title": "What is your height (cm)?",
            "question_type": "numerical_box",
            "validation_required": True,
            "validation_min_float_value": 30.00,
            "validation_max_float_value": 300.00,
            "validation_error_msg": "Enter between 30.00 and 300.00 cm.",
            "question_placeholder": "152.0",
            "question_tag": "height",
            "survey_id": survey_id,
        }
        if height_question:
            height_question.write(height_question_vals)
        else:
            height_question_vals["constr_mandatory"] = True
            height_question = self.env["survey.question"].create(height_question_vals)
        return height_question

    def _height_questions(self):
        for rec in self:
            if not rec._origin.id:
                continue

            height_question = rec._origin._find_height_weight_question("height")

            if rec.is_height_ques_enabled:
                height_question = self._create_or_update_height_question(rec._origin.id, height_question)
            elif height_question:
                height_question.write({"survey_id": False})

    @api.model
    def _create_or_update_weight_question(self, survey_id, weight_question=False):
        if weight_question:
            weight_question.write({
                "title": "What is your weight (KG)?",
                "question_type": "numerical_box",
                "survey_id": survey_id,
            })
        else:
            weight_question = self.env["survey.question"].create({
                "bio_survey_id": survey_id,
                "title": "What is your weight (KG)?",
                "question_type": "numerical_box",
                "constr_mandatory": True,
                "question_tag": "weight",
                "survey_id": survey_id,
            })
        return weight_question

    def _weight_questions(self):
        for rec in self:
            if not rec._origin.id:
                continue

            weight_question = rec._origin._find_height_weight_question("weight")

            if rec.is_weight_ques_enabled:
                weight_question = self._create_or_update_weight_question(rec._origin.id, weight_question)
            else:
                weight_question.write({"survey_id": False})

    def write(self, vals):
        res = super().write(vals)
        skip_sequence_update = self.env.context.get("skip_sequence_update")
        for rec in self:
            to_update_sequence = "patient_ques_and_page_ids" in vals
            if 'is_surgery_ques_enabled' in vals:
                rec._surgery_questions()
                to_update_sequence = True
            if 'is_medic_ques_enabled' in vals:
                rec._medic_questions()
                to_update_sequence = True
            if 'is_height_ques_enabled' in vals:
                rec._height_questions()
                to_update_sequence = True
            if 'is_weight_ques_enabled' in vals:
                rec._weight_questions()
                to_update_sequence = True

            if not skip_sequence_update and to_update_sequence:
                rec._update_survey_question_sequence()
        return res


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    continue_later = fields.Boolean(string='Continue Later', default=False)
    is_duplicated = fields.Boolean("copy", default=False)
    note = fields.Char('Notes')
    version = fields.Char(string='Version', compute='_compute_version', store=True)
    op_datetime = fields.Datetime("Date and Time", readonly=True)
    op_duration_hrs = fields.Integer("Duration", default=1)
    op_duration_mins = fields.Integer("Duration Mins")
    location = fields.Char(string="Location", readonly=True)
    op_process = fields.Char('Procedure Name', readonly=True)
    op_surgeon = fields.Char('Surgeon', readonly=True)
    gender = fields.Selection([('male', 'Male'), ('female', 'Female')], string="Sex")
    age = fields.Char('Age', readonly=True)
    bmi = fields.Char('BMI', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Patient Name', readonly=True, index='btree_not_null')
    state = fields.Selection([
        ('new', 'Not started yet'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('review', 'Reviewed')], string='Status', default='new', readonly=True)
    inform_guide_id = fields.Many2one('information.guide', string='Anaesthetic Plan', tracking=True)
    case_id = fields.Many2one('patient.case', string='Patient Case', tracking=True)
    case_tier = fields.Selection(
        related='case_id.case_tier',
        string="Case Tier",
        store=True,
        readonly=True,
    )
    is_edit = fields.Boolean("Edit", default=False)
    case_guide_id = fields.Many2one("information.guide.case", string="Case Guide Plan", copy=False)
    case_guide_state = fields.Selection(selection=[('draft', 'Draft'), ('update', 'Updated'), ('sent', 'Sent')],
                                        string='Case Guide Status', default='draft')
    op_nric_number = fields.Char("NRIC/FIN/Passport")
    type_of_survey = fields.Selection(
        related='survey_id.type_of_survey',
        selection=[('medical_history', 'Medical History Questionnaire'), ('feedback', 'Feedback Survey')],
        store=True,
        readonly=True
    )
    localized_op_datetime = fields.Char(compute='_compute_localized_op_datetime')
    additional_info_ids = fields.Many2many("additional.information", string="Additional Information (Optional)", copy=False)
    location_id = fields.Many2one("res.dislocation", string="Disposition (Optional)", copy=False,
        compute="compute_location_id",
        inverse="inverse_location_id",
        store=True)
    associate_id = fields.Many2one(
        "res.users",
        string="Associate Assigned",
        tracking=True,
        domain=lambda self: [
            ('groups_id', 'in', [self.env.ref('p7_patient_management.group_user_associate').id])
        ],
    )
    video_call_assign_status = fields.Selection(
        [
            ("unassigned", "Unassigned"),
            ("to_assign", "To be assigned"),
            ("assigned", "Assigned"),
        ],
        string="Video Call Status",
        default="unassigned",
        tracking=True,
    )
    contact_channel = fields.Selection(
        [
            ("sms", "SMS"),
            ("whatsapp", "WhatsApp Message"),
            ("phone", "Phone Call"),
            ("video", "Video Call"),
        ],
        groups="p7_patient_management.group_user_associate",
        string="Contact Channel",
    )
    video_call_datetime = fields.Datetime("Video Call Date and Time")
    video_call_location = fields.Char(
        "Patient's Physical Location",
        groups="p7_patient_management.group_user_associate",
    )
    video_call_contents = fields.Text(
        "Contents",
        default="The patient was introduced to the purpose and functions of the Virtual Anaesthesia Assessment (VANAESA) platform.",
        groups="p7_patient_management.group_user_associate",
    )
    video_call_performed_by = fields.Selection(
        [('self', 'Self'), ('associate', 'Associate')],
        string="Performed By",
        default='self',
    )
    video_call_outcome = fields.Selection(
        [('failed', 'Failed'), ('successful', 'Successful')],
        string="Outcome of Call",
    )
    video_call_status = fields.Selection(
        [
            ('pending', 'Not Started'),
            ('assigned', 'Assigned'),
            ('in_progress', 'In Progress'),
            ('failed', 'Failed'),
            ('success', 'Success'),
            ('bypassed', 'Bypassed'),
        ],
        string="Status of Video Call",
        default='pending',
    )
    video_call_fail_count = fields.Integer("Video Call Fail Count", default=0)
    bypass_reason = fields.Text("Bypass Reason")

    attempt_count = fields.Integer("Attempt Count", store=True)

    def action_mark_video_success(self):
        """Mark the video call as successful."""
        for record in self:
            record.update({
                'video_call_status': 'success',
                'video_call_outcome': 'successful',
            })
            record._message_log(body=_('Video call marked as successful.'))
            record.case_id.update({
                'video_call_status': 'success',
                'video_call_outcome': 'successful',
            })
            record.case_id._message_log(body=_('Video call marked as successful.'))

    def action_mark_video_fail(self):
        """Mark the video call as failed without logging an attempt."""
        for record in self:
            record.update({
                'video_call_status': 'failed',
                'video_call_outcome': 'failed',
            })

    def action_mark_video_bypass(self, reason):
        """Bypass the contact attempt with a provided reason."""
        for record in self:
            record.update({
                'video_call_status': 'bypassed',
                'bypass_reason': reason,
            })

    # on the model where this method lives (likely survey.user_input or patient.case)
    def action_request_associate(self):
        """Request or assign an associate for the video call."""
        for record in self:
            record.video_call_performed_by = 'associate'
            admin_group = self.env.ref('p7_patient_management.group_user_admin', raise_if_not_found=False)

            def _create_attempt(assigned: bool):
                vals = {
                    'user_input_id': record.id,
                    'case_id': record.case_id.id,
                    'patient_first_name': record.case_id.patient_first_name,
                    'patient_last_name': record.case_id.patient_last_name,
                    'patient_phone_code': record.case_id.patient_phone_code.name,
                    'patient_mob': record.case_id.patient_mob,
                    'patient_nric_number': record.case_id.patient_nric_number,
                    'patient_gender': record.case_id.patient_gender,
                    'patient_dob': record.case_id.patient_dob,
                    'video_call_assign_status': 'assigned' if assigned else 'to_assign',
                }
                if assigned and record.associate_id:
                    vals['associate_id'] = record.associate_id.id
                self.env['contact.attempt'].sudo().create(vals)

            if record.associate_id:
                # Assigned path
                record.video_call_assign_status = 'assigned'
                record.video_call_status = 'assigned'  # or 'in_progress' if you prefer
                record.case_id.video_call_assign_status = 'assigned'
                record.case_id.video_call_status = 'assigned'  # or 'in_progress' if you prefer

                _create_attempt(assigned=True)

                if record.associate_id.email:
                    self.env['mail.mail'].sudo().create({
                        'auto_delete': False,
                        'email_to': record.associate_id.email,
                        'subject': _('Video call assigned'),
                        'body_html': f"<p>{_('You have been assigned to case')} {record.case_id.name}.</p>",
                    }).send()

                if admin_group:
                    for admin in admin_group.users.filtered(lambda u: u.email):
                        self.env['mail.mail'].sudo().create({
                            'auto_delete': False,
                            'email_to': admin.email,
                            'subject': _('Associate assigned'),
                            'body_html': f"<p>{_('Associate')} {record.associate_id.name} {_('has been assigned to case')} {record.case_id.name}.</p>",
                        }).send()

                record.message_post(body=_('Doctor assigned video call to associate %s') % record.associate_id.name)

            else:
                # Unassigned path -> visible in "Bookings for Calling"
                record.video_call_assign_status = 'to_assign'
                record.video_call_status = 'pending'
                record.case_id.video_call_assign_status = 'to_assign'
                record.case_id.video_call_status = 'pending'  # <-- important for the view filter

                _create_attempt(assigned=False)

                if admin_group:
                    for admin in admin_group.users.filtered(lambda u: u.email):
                        self.env['mail.mail'].sudo().create({
                            'auto_delete': False,
                            'email_to': admin.email,
                            'subject': _('Associate assistance requested'),
                            'body_html': f"<p>{_('Doctor has requested associate assistance for case')} {record.case_id.name}.</p>",
                        }).send()

                record.message_post(body=_('Doctor requested associate assistance'))

    def action_video_call_complete(self):
        """Finalize a contact attempt and sync the case."""
        for record in self:
            if not record.video_call_outcome:
                raise UserError(_('Please select the outcome of the video call before completing it.'))

            case = record.case_id
            date_val = False
            time_val = 0.0
            if record.video_call_datetime:
                date_val = record.video_call_datetime.date()
                time_val = record.video_call_datetime.hour + record.video_call_datetime.minute / 60.0

            case.write({
                'video_call_date': date_val,
                'video_call_time': time_val,
                'video_call_location': record.video_call_location,
                'contact_channel': record.contact_channel,
                'video_call_contents': record.video_call_contents,
                'associate_id': record.associate_id.id,
                'video_call_performed_by': record.video_call_performed_by,
                'video_call_outcome': record.video_call_outcome,
                'video_call_status': record.video_call_status,
                'video_call_assign_status': record.video_call_assign_status,
                'video_call_fail_count': record.video_call_fail_count,
            })

            case.action_video_call_complete()

            hours = int(case.video_call_time or 0)
            minutes = int(round(((case.video_call_time or 0) - hours) * 60))
            dt_val = datetime.combine(case.video_call_date,
                                      dt_time(hour=hours, minute=minutes)) if case.video_call_date else False

            record.write({
                'video_call_datetime': dt_val,
                'video_call_location': case.video_call_location,
                'contact_channel': case.contact_channel,
                'video_call_contents': case.video_call_contents,
                'associate_id': case.associate_id.id,
                'video_call_performed_by': case.video_call_performed_by,
                'video_call_outcome': case.video_call_outcome,
                'video_call_status': case.video_call_status,
                'video_call_assign_status': case.video_call_assign_status,
                'video_call_fail_count': case.video_call_fail_count,
            })

    @api.depends("case_id", "case_id.location_id")
    def compute_location_id(self):
        for record in self:
            record.location_id = record.case_id.location_id

    def inverse_location_id(self):
        for record in self:
            record.case_id.location_id = record.location_id

    @api.depends('op_datetime')
    def _compute_localized_op_datetime(self):
        for rec in self:
            if rec.op_datetime:
                localized_dt = fields.Datetime.context_timestamp(rec, rec.op_datetime)
                rec.localized_op_datetime = localized_dt.strftime("%Y-%m-%d %H:%M")
            else:
                rec.localized_op_datetime = ""

    @api.model_create_multi
    def create(self, vals_list):
        records = super(SurveyUserInput, self).create(vals_list)
        if not self.env.context.get("skip_addition_info_update"):
            for record in records.filtered(lambda r: r.case_id.additional_info_ids):
                record.with_context(skip_addition_info_update=True).write({"additional_info_ids": [(6, 0, record.case_id.additional_info_ids.ids)]})

        return records

    def write(self, vals):
        default_case_id = self.env.context.get('default_case_id')
        if default_case_id and 'case_id' not in vals and not self.case_id:
            vals['case_id'] = default_case_id
        res = super(SurveyUserInput, self).write(vals)
        if vals.get('inform_guide_id'):
            case_id = self.case_guide_id

            if case_id:
                case_id.write({
                    'name': self.inform_guide_id.name,
                    'version': self.inform_guide_id.version,
                    'anaesthesia_type_ids': [(6, 0, self.inform_guide_id.anaesthesia_type_ids.ids)],
                    'additional_info_ids': [(6, 0, self.additional_info_ids.ids)],
                    'welcome_msg': self.inform_guide_id.welcome_msg,
                    'anaesthesia_intro': self.inform_guide_id.anaesthesia_intro,
                    'close_msg': self.inform_guide_id.close_msg,
                    'check_close_msg': self.inform_guide_id.check_clos_msg,
                    'patient_case_id': self.case_id.id,
                    'guide_id': self.inform_guide_id.id
                })
            else:
                new_case_id = self.env['information.guide.case'].create({
                    'name': self.inform_guide_id.name,
                    'version': self.inform_guide_id.version,
                    'anaesthesia_type_ids': [(6, 0, self.inform_guide_id.anaesthesia_type_ids.ids)],
                    'additional_info_ids': [(6, 0, self.additional_info_ids.ids)],
                    'welcome_msg': self.inform_guide_id.welcome_msg,
                    'anaesthesia_intro': self.inform_guide_id.anaesthesia_intro,
                    'close_msg': self.inform_guide_id.close_msg,
                    'check_close_msg': self.inform_guide_id.check_clos_msg,
                    'patient_case_id': self.case_id.id,
                    'guide_id': self.inform_guide_id.id
                })
                self.case_guide_id = new_case_id.id
            self.case_id.write(
                {'inform_guide_id': int(vals.get('inform_guide_id')), 'case_guide_id': self.case_guide_id})

        if "additional_info_ids" in vals and not self.env.context.get("skip_addition_info_update"):
            for record in self:
                record.case_id.write({"additional_info_ids": [(6, 0, record.additional_info_ids.ids)]})
                record.case_guide_id.write({"additional_info_ids": [(6, 0, record.additional_info_ids.ids)]})
        return res

    @api.depends('survey_id')
    def _compute_version(self):
        for record in self:
            if record.survey_id:
                record.version = record.survey_id.version
            else:
                record.version = " "

    # def _get_skipped_questions(self):
    #     self.ensure_one()

    #     return self.user_input_line_ids.filtered(
    #         lambda answer: answer.skipped and not answer.is_hidden and answer.question_id.constr_mandatory).question_id

    def get_question(self):
        self.env.cr.commit()
        question_ids = self.user_input_line_ids.filtered(lambda line: line.skipped == False).mapped('question_id')
        return question_ids

    def open_survey(self):
        all_ques_ids = self.env['survey.question'].sudo().search(
            [('repeat_survey_id', '=', self.survey_id.id), ('repeat_answer_id', '=', self.id)])
        all_page_ids = self.env['survey.question'].sudo().search(
            [('survey_id', '=', self.survey_id.id), ('is_page', '=', True)])
        user_input_line_ids = self.user_input_line_ids.filtered(lambda line: line.user_input_id == self)
        patient_case_id = self.env['patient.case'].sudo().search([('medic_answer_id', '=', self.id)], limit=1)
        feedback_case_id = self.env['patient.case'].sudo().search([('feedback_answer_id', '=', self.id)], limit=1)
        for page in all_page_ids:
            page.more_ques_and_page_ids = [(5, 0, 0)]
        for ques in all_ques_ids:
            if ques.id in user_input_line_ids.mapped('question_id').ids:
                ques.sudo().write(
                    {'page_id': ques.repeat_question_id.page_id.id if ques.repeat_question_id else ques.page_id.id, })
                ques.page_id.sudo().write({'more_ques_and_page_ids': [(4, ques.id)]})
        self.sudo().write({'state': 'in_progress', 'last_displayed_page_id': 0})
        survey_url = "/survey/%s/%s" % (self.survey_id.access_token, self.access_token)
        if patient_case_id:
            patient_case_id.sudo().write({'medic_state': 'in_progress', 'medic_survey_submit_date': False})
        if feedback_case_id:
            feedback_case_id.sudo().write({'feedback_state': 'in_progress', 'feedback_survey_submit_date': False})
        return {
            'type': 'ir.actions.act_url',
            'url': survey_url,
            'target': 'new',
        }

    def action_download_answers(self):
        self.ensure_one()
        return self.env.ref('p7_patient_management.action_report_survey_answer_form').report_action(self)

    def action_update_guide(self):
        self.ensure_one()
        if not self.case_id:
            raise ValidationError(_('This answer not connected with any booking!'))
        wizard = self.env['survey.confirm.popup'].sudo().create({
            'user_input_id': self.id,
            'inform_guide_id': self.inform_guide_id.id,
            'case_guide_id': self.case_guide_id.id
        })
        return {
            'name': _("Confirmation"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'survey.confirm.popup',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_patient_guide(self):
        self.ensure_one()
        self.case_id.send_guide()
        self.write({'case_guide_state': 'sent'})
        self.case_guide_id.write({'state': 'sent'})

    def action_review_state_update(self):
        self.write({'state': 'review'})
        patient_case_id = self.env['patient.case'].search([('medic_answer_id', '=', self.id)])
        if patient_case_id:
            patient_case_id.write({'medic_state': 'review', 'additional_info_ids': self.additional_info_ids.ids, 'location_id': self.location_id})
        patient_case_id = self.env['patient.case'].search([('feedback_answer_id', '=', self.id)])
        if patient_case_id:
            patient_case_id.write({'feedback_state': 'review'})

    def action_assign_to_associate(self):
        """Assign the contact attempt to an associate."""
        self.ensure_one()
        self.action_request_associate()

    def action_video_call_success(self):
        """Mark the related case video call as successful."""
        self.ensure_one()
        self.action_mark_video_success()

    def action_video_call_fail(self):
        """Mark the related case video call as failed."""
        self.ensure_one()
        self.action_mark_video_fail()

    # wherever this lives (likely an extension on survey.user_input)
    def action_open_bypass_wizard(self):
        """Open a wizard requesting a bypass reason."""
        self.ensure_one()
        return {
            'name': _('Bypass Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'video.call.bypass.wizard',
            'view_mode': 'form',
            # OPTIONAL: use a specific view_id if you want (otherwise Odoo picks default)
            # 'view_id': self.env.ref('p7_patient_management.view_video_call_bypass_wizard').id,
            'target': 'new',
            'context': {
                'default_user_input_id': self.id,
            },
        }


    def _clear_inactive_conditional_answers(self):
        """
        Cleans up answers to conditional and repeat questions that should not be visible anymore.
        """
        inactive_questions = self._get_inactive_conditional_questions()

        # delete user.input.line on question that should not be answered.
        # answers_to_delete = self.user_input_line_ids.filtered(lambda answer: answer.question_id in inactive_questions)
        # # answers_to_delete.unlink()

        # 1. Clear direct inactive answers
        answers_to_delete = self.user_input_line_ids.filtered(lambda ans: ans.question_id in inactive_questions)
        # find repeated questions related to those inactive triggers
        repeat_questions = self.env['survey.question'].sudo().search([('repeat_question_id', 'in', inactive_questions.ids), ('answer_id', '=', self.id)])
        # keep repeat questions that still have answers
        repeat_questions_with_answers = self.user_input_line_ids.filtered(lambda line: line.question_id in repeat_questions and not line.skipped).mapped('question_id')
        repeat_questions_to_remove = repeat_questions - repeat_questions_with_answers
        answers_to_delete |= self.user_input_line_ids.filtered(lambda line: line.question_id in repeat_questions_to_remove)
        if answers_to_delete:
            answers_to_delete.unlink()
        if repeat_questions_to_remove:
            repeat_questions_to_remove.unlink()

    def _save_lines(self, question, answer, comment=None, overwrite_existing=True):
        """ Save answers to questions, depending on question type.

        :param bool overwrite_existing: if an answer already exists for question and user_input_id
        it will be overwritten (or deleted for 'choice' questions) in order to maintain data consistency.
        :raises UserError: if line exists and overwrite_existing is False
        """
        old_answers = self.env['survey.user_input.line'].search([
            ('user_input_id', '=', self.id),
            ('question_id', '=', question.id)
        ])
        # if old_answers and not overwrite_existing:
        #     raise UserError(_("This answer cannot be overwritten."))

        if question.question_type in ['char_box', 'text_box', 'numerical_box', 'date', 'datetime']:
            self._save_line_simple_answer(question, old_answers, answer)
            if question.save_as_email and answer:
                self.write({'email': answer})
            if question.save_as_nickname and answer:
                self.write({'nickname': answer})

        elif question.question_type in ['simple_choice', 'multiple_choice']:
            self._save_line_choice(question, old_answers, answer, comment)
        elif question.question_type == 'matrix':
            self._save_line_matrix(question, old_answers, answer, comment)
        else:
            raise AttributeError(question.question_type + ": This type of question has no saving function")

    def _save_line_simple_answer(self, question, old_answers, answer):
        vals = self._get_line_answer_values(question, answer, question.question_type)
        vals.update({'is_hidden': False})
        if old_answers:
            old_answers.write(vals)
            return old_answers
        else:
            return self.env['survey.user_input.line'].create(vals)

    def action_case_guide_update(self):
        self.ensure_one()
        if not self.case_guide_id:
            raise ValidationError(_('This answer not connected with any booking!'))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Anaesthetic Plan Form',
            'res_model': 'information.guide.case',
            'res_id': self.case_guide_id.sudo().id,
            'view_mode': 'form',
            'view_id': False,
            'target': 'current',
        }
    
class SurveyUserInputLine(models.Model):
    _inherit = 'survey.user_input.line'

    note = fields.Char('Notes')
    colour = fields.Char(string='Colour')
    is_hidden = fields.Boolean("Hidden Answer", default=False)

    def write(self, vals):
        for record in self:
            if 'note' in vals:
                if record.note:
                    record.user_input_id._message_log(
                        body=_("The notes changed for the question '%s' from '%s' to '%s'", record.question_id.title,
                               record.note, vals.get('note')))
                else:
                    record.user_input_id._message_log(
                        body=_("The notes added for the question '%s' as '%s'.", record.question_id.title,
                               vals.get('note')))

            if record.answer_type == 'numerical_box' and 'value_numerical_box' not in vals:
                vals['value_numerical_box'] = record.value_numerical_box

        return super(SurveyUserInputLine, self).write(vals)

    def action_download_file(self):
        if self.attachment_id:
            self.attachment_id.sudo().write({'public': True})
            return {
                'type': 'ir.actions.act_url',
                'url': f"/web/content/{self.attachment_id.id}?download=true",
                'close': True,
            }

    def get_answer_value(self):
        return self

    def _compute_display_name(self):
        super(SurveyUserInputLine, self)._compute_display_name()
        for line in self:
            if line.answer_type == 'text_box' and line.value_text_box:
                line.display_name = line.value_text_box


class SurveyQuestionUpdate(models.Model):
    _inherit = 'survey.question'

    is_repeat_question = fields.Boolean("Repeat Question", default=False)
    medic_details = fields.Boolean("Medication Question", default=False)
    is_header = fields.Boolean("Header", default=False)
    is_duplicated = fields.Boolean("Copy", default=False)
    repeat_ques_id = fields.Many2one('survey.question', string="Repeat Id")
    repeat_question_id = fields.Many2one('survey.question', string="Repeat Ids")
    repeat_survey_id = fields.Many2one('survey.survey', string="Repeat Survey Id")
    surgic_survey_id = fields.Many2one('survey.survey', string="Surgery Id")
    medic_survey_id = fields.Many2one('survey.survey', string="Medic Id")
    bio_survey_id = fields.Many2one('survey.survey', string="Bio Id")
    patient_survey_id = fields.Many2one('survey.survey', string="Patient Id")
    question_tag = fields.Selection(
        [('medical', 'Medical History'), ('surgery', 'Surgery History'), ('height', 'Height'), ('weight', 'Weight'),
         ('normal', 'Normal')], string="Question Tag", default="normal")
    parent_question_id = fields.Many2one('survey.question', string='Parent Question')
    more_ques_and_page_ids = fields.One2many('survey.question', 'parent_question_id', string='More Questions',
                                             copy=False)
    repeat_answer_id = fields.Many2one('survey.user_input', string="Answer Id")
    answer_id = fields.Many2one('survey.user_input', string="Answers Id")
    colour = fields.Char(string='Color')
    length = fields.Integer('', default=0)
    set_sequence = fields.Integer('set sequence', default=1)
    suffix = fields.Char(string='Suffix')
    question_type = fields.Selection([
        ('simple_choice', 'Multiple choice: only one answer'),
        ('multiple_choice', 'Multiple choice: multiple answers'),
        ('text_box', 'Multiple Lines Text Box'),
        ('char_box', 'Single Line Text Box'),
        ('numerical_box', 'Numerical Value'),
        ('date', 'Date'),
        ('datetime', 'Datetime'),
        ('matrix', 'Matrix')], string='Question Type',
        compute='_compute_question_type', readonly=False, store=True)
    is_active_in_survey = fields.Boolean(default=False)
    sequence = fields.Integer(default=False)

    @api.model_create_multi
    def create(self, vals_list):
        SQ = self.env['survey.question']
        questions = super().create(vals_list)
        surveys = questions.mapped("patient_survey_id")
        for survey in surveys:
            psurvey_questions = questions.filtered(lambda q: q.patient_survey_id.id == survey.id)
            psurvey_questions.write({"survey_id": survey.id})
            survey_questions = SQ.search([
                ("survey_id", "=", survey.id),
                ("surgic_survey_id", "=", survey.id),
                ("medic_survey_id", "=", survey.id)
            ])

            if survey_questions:
                sequence = max(survey_questions.mapped("sequence")) or 0
                for question in psurvey_questions:
                    sequence += 1
                    question.sequence = sequence
        return questions

    @api.model
    def cron_convert_height_to_cm(self):
        height_questions = self.search([
            ('question_tag', '=', 'height'),
            ('validation_min_float_value', '=', 1.0),
            ('validation_max_float_value', '=', 4.0)
        ])

        for question in height_questions:
            question.write({
                'validation_min_float_value': 30.0,
                'validation_max_float_value': 300.0,
                'question_placeholder': '152.0',
                'validation_error_msg': 'Enter between 30.00 and 300.00 cm.',
                'title': 'What is your height (cm)?'
            })

    @api.onchange('question_type')
    def _onchange_question_typ(self):
        for rec in self:
            if rec.question_type in ['simple_choice', 'multiple_choice']:
                rec.constr_mandatory = True

    @api.depends('survey_id', 'survey_id.question_ids', 'triggering_answer_ids')
    def _compute_allowed_triggering_question_ids(self):
        """Although the question (and possible trigger questions) sequence
        is used here, we do not add these fields to the dependency list to
        avoid cascading rpc calls when reordering questions via the webclient.
        """
        possible_trigger_questions = self.search([
            ('is_page', '=', False),
            ('question_type', 'in', ['simple_choice', 'multiple_choice']),
            ('suggested_answer_ids', '!=', False),
            '|', '|',
            ('survey_id', 'in', self.survey_id.ids),
            ('surgic_survey_id', 'in', self.surgic_survey_id.ids),
            ('medic_survey_id', 'in', self.medic_survey_id.ids)
        ])
        # Using the sequence stored in db is necessary for existing questions that are passed as
        # NewIds because the sequence provided by the JS client can be incorrect.
        (self | possible_trigger_questions).flush_recordset()
        self.env.cr.execute(
            "SELECT id, sequence FROM survey_question WHERE id =ANY(%s)",
            [self.ids]
        )
        conditional_questions_sequences = dict(self.env.cr.fetchall())  # id: sequence mapping

        for question in self:
            question_id = question._origin.id
            if not question_id:  # New question
                question.allowed_triggering_question_ids = possible_trigger_questions.filtered(
                    lambda q: q.survey_id.id == question.survey_id._origin.id)
                question.is_placed_before_trigger = False
                continue

            question_sequence = conditional_questions_sequences[question_id]

            question.allowed_triggering_question_ids = possible_trigger_questions.filtered(
                lambda q: q.survey_id.id == question.survey_id._origin.id
                          and (q.sequence < question_sequence or q.sequence == question_sequence and q.id < question_id)
            )
            question.is_placed_before_trigger = bool(
                set(question.triggering_answer_ids.question_id.ids)
                - set(question.allowed_triggering_question_ids.ids)  # .ids necessary to match ids with newIds
            )