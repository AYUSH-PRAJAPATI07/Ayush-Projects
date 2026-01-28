# -*- coding: utf-8 -*-
# Part of Banastech. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class Survey(models.Model):
    _inherit = 'survey.survey'

    @api.model
    def prepare_result(self, question, current_filters=None):
        current_filters = current_filters if current_filters else []
        result_summary = {}
        input_lines = question.user_input_line_ids.filtered(lambda line: not line.user_input_id.test_entry)

        # Calculate and return statistics for attachment
        if question.question_type == 'file':
            result_summary = []
            for input_line in input_lines:
                if not(current_filters) or input_line.user_input_id.id in current_filters:
                    result_summary.append(input_line)
            return result_summary
        else:
            return super(Survey, self).prepare_result(question, current_filters=current_filters)


class SurveyQuestion(models.Model):
    _inherit = 'survey.question'

    # Answer
    question_type = fields.Selection(selection_add=[('file', 'Upload File')])
    max_file_size = fields.Integer("Maximum upload file size (MB)", default=5)
    allow_multi_file = fields.Boolean("Allow upload multiple file", default=True)
    rep = fields.Boolean("Allow upload multiple file", default=True)

    def validate_file(self, post, answer_tag):
        self.ensure_one()
        errors = {}
        answer = post[answer_tag].strip()
        # Empty answer to mandatory question
        if self.constr_mandatory and not answer:
            errors.update({answer_tag: self.constr_error_msg})
        return errors


class SurveyUserInput(models.Model):
    _inherit = "survey.user_input"

    def _save_lines(self, question, answer, comment=None, overwrite_existing=True):
        old_answers = self.env['survey.user_input.line'].sudo().search([
            ('user_input_id', '=', self.id),
            ('question_id', '=', question.id)
        ])
        if question.question_type == 'file':
            self.save_line_file(question, old_answers, answer, comment)
        else:
            super(SurveyUserInput, self)._save_lines(question, answer, comment=comment, overwrite_existing=overwrite_existing)

    @api.model
    def save_line_file(self, question, old_answers, answer, comment):
        vals = self._get_line_answer_values(question, answer, question.question_type)
        attachment_ids = answer.split(',') if answer else []

        # Collect IDs of existing attachments
        existing_attachment_ids = old_answers.mapped('attachment_id').ids if old_answers else []

        for attachment_id in attachment_ids:
            vals.update({'attachment_id': int(attachment_id), 'value_file': 'attachment_id'})
            # Check if the attachment is already present in old answers
            if int(attachment_id) in existing_attachment_ids:
                # Update the existing answer for this attachment
                existing_answer = old_answers.filtered(lambda a: a.attachment_id.id == int(attachment_id))
                if existing_answer:
                    existing_answer.write(vals)
            else:
                # Create a new answer line for this attachment
                self.env['survey.user_input.line'].sudo().create(vals)
        return True

class SurveyUserInputLine(models.Model):
    _inherit = 'survey.user_input.line'

    value_file = fields.Char("Value File")
    answer_type = fields.Selection(selection_add=[
        ('file', 'Upload file')])
    attachment_id = fields.Many2one('ir.attachment', 'Attachments')

    @api.depends('answer_type', 'attachment_id')
    def _compute_display_name(self):
        super(SurveyUserInputLine, self)._compute_display_name()
        for line in self:
            if line.answer_type == 'file':
                if len(line.attachment_id) == 1:
                    line.display_name = _("%s",line.attachment_id.name)
                else:
                    line.display_name = _("No Attachment")