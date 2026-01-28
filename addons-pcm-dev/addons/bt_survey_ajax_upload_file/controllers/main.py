from odoo import http
from odoo.addons.survey.controllers.main import Survey  # Import the class
from odoo.addons.bt_ajax_upload_file_common.controllers.main import AttachmentUpload  # Import the class
from odoo.http import request, content_disposition
from odoo.exceptions import UserError
from odoo.tools import ustr
import json, sys, base64, pytz


class SurveyAttachmentUpload(AttachmentUpload):

    def add_attachment(self, ufile, res_model, res_id, res_field=False):
        if res_model == 'survey.user_input.line':
            # res_id = False
            # res_model = False
            res_field = 'attachment_id'
        return super(SurveyAttachmentUpload, self).add_attachment(ufile, res_model, res_id, res_field=res_field)

    @http.route()        # Return non empty answers in a JSON compatible format
    def uploaded_files(self, **kw):
        if kw.get('res_model', '') == 'survey.user_input.line':
            res_id = kw.get('res_id', '')
            attachments = []
            if res_id:
                res_id = res_id.split('_')
                answer_sudo = request.env['survey.user_input.line'].sudo().search([
                    ('user_input_id', '=', int(res_id[1])),
                    ('survey_id', '=', int(res_id[0])),
                    ('question_id', '=', int(res_id[2]))
                ])
                for attach in answer_sudo:
                    attachments.append({'path': attach.attachment_id.id, 'name': attach.attachment_id.name, 'size': attach.attachment_id.file_size})
            return attachments
        else:
            return super(SurveyAttachmentUpload, self).uploaded_files(**kw)


class SurveyFile(Survey):
    
    @http.route('/survey/prefill/<string:survey_token>/<string:answer_token>', type='http', auth='public', website=True)
    def survey_get_answers(self, survey_token, answer_token, page_or_question_id=None, **post):
        """ TDE NOTE: original comment: # AJAX prefilling of a survey -> AJAX / http ?? """
        access_data = self._get_access_data(survey_token, answer_token, ensure_token=True)
        if access_data['validity_code'] is not True and access_data['validity_code'] != 'answer_done':
            return {}

        survey_sudo, answer_sudo = access_data['survey_sudo'], access_data['answer_sudo']
        try:
            page_or_question_id = int(page_or_question_id)
        except:
            page_or_question_id = None

        # Fetch previous answers
        if survey_sudo.questions_layout == 'one_page' or not page_or_question_id:
            previous_answers = answer_sudo.user_input_line_ids
        elif survey_sudo.questions_layout == 'page_per_section':
            previous_answers = answer_sudo.user_input_line_ids.filtered(lambda line: line.page_id.id == page_or_question_id)
        else:
            previous_answers = answer_sudo.user_input_line_ids.filtered(lambda line: line.question_id.id == page_or_question_id)
        ret = {}
        # Return non empty answers in a JSON compatible format
        for answer in previous_answers:
            if not answer.skipped:
                answer_tag = '%s_%s' % (answer.survey_id.id, answer.question_id.id)
                answer_value = None
                if answer.answer_type == 'free_text':
                    answer_value = answer.value_free_text
                elif answer.answer_type == 'text' and answer.question_id.question_type == 'textbox':
                    answer_value = answer.value_text
                elif answer.answer_type == 'file' and answer.question_id.question_type == 'file':
                    answer_value = ','.join([str(a) for a in answer.attachment_id.id])
                elif answer.answer_type == 'text' and answer.question_id.question_type != 'textbox':
                    # here come comment answers for matrices, simple choice and multiple choice
                    answer_tag = "%s_%s" % (answer_tag, 'comment')
                    answer_value = answer.value_text
                elif answer.answer_type == 'number':
                    answer_value = str(answer.value_number)
                elif answer.answer_type == 'date':
                    answer_value = fields.Datetime.to_string(answer.value_date)
                elif answer.answer_type == 'datetime':
                    answer_value = fields.Datetime.to_string(answer.value_datetime)
                elif answer.answer_type == 'suggestion' and not answer.value_suggested_row:
                    answer_value = answer.value_suggested.id
                elif answer.answer_type == 'suggestion' and answer.value_suggested_row:
                    answer_tag = "%s_%s" % (answer_tag, answer.value_suggested_row.id)
                    answer_value = answer.value_suggested.id
                if answer_value:
                    ret.setdefault(answer_tag, []).append(answer_value)
                else:
                    _logger.warning("[survey] No answer has been found for question %s marked as non skipped" % answer_tag)
        return json.dumps(ret, default=str)

        
           
    