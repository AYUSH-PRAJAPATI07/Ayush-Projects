from odoo import http,fields,_
from odoo.http import request
from twilio.rest import Client
from datetime import datetime, timedelta, date
from collections import defaultdict
from odoo.exceptions import ValidationError,UserError
from dateutil.relativedelta import relativedelta
from odoo.addons.survey.controllers.main import Survey
from odoo.tools import format_datetime,format_date
import pytz
import random
import logging

_logger = logging.getLogger(__name__)

class SurveyController(http.Controller):
    
    def get_answer_sequence(self,lst):
        unique_list = list(dict.fromkeys(lst))
        removed_duplicates_count = len(lst) - len(unique_list)
        last_number = unique_list[-1]
        for i in range(1, removed_duplicates_count + 1):
            unique_list.append(last_number + i)
        
        return unique_list
    
    @http.route('/survey/confirmation', type='http', auth='user', website=True, csrf=True)
    def confirmation_page(self, **kw):
        return request.render('p7_patient_management.confirmation_page')
    
    @http.route('/survey/edit', type='http', auth='user', website=True, csrf=True)
    def edit_survey(self, **kw):
        values = request.params.copy()
        survey_id = values.get('survey')
        answer_id = values.get('answer')
        is_edit = values.get('edit')
        medic_patient_case_id = request.env['patient.case'].sudo().search([('medic_answer_id', '=', int(answer_id))],limit=1)
        feedback_patient_case_id = request.env['patient.case'].sudo().search([('feedback_answer_id', '=', int(answer_id))],limit=1)
        if is_edit == '1' and survey_id and answer_id:
            answer = request.env['survey.user_input'].sudo().browse(int(answer_id))
            survey = request.env['survey.survey'].sudo().browse(int(survey_id))
            if answer:
                answer.sudo().write({'is_edit':True})
                all_ques_ids = request.env['survey.question'].sudo().search([('repeat_survey_id', '=', survey.id),('repeat_answer_id', '=', answer.id)])
                all_page_ids = request.env['survey.question'].sudo().search([('survey_id', '=', survey.id),('is_page', '=', True)])
                user_input_line_ids = answer.user_input_line_ids
                medic_patient_case_id = request.env['patient.case'].sudo().search([('medic_answer_id', '=', answer.id)],limit=1)
                feedback_patient_case_id = request.env['patient.case'].sudo().search([('feedback_answer_id', '=', answer.id)],limit=1)
                for page in all_page_ids:
                    page.more_ques_and_page_ids = [(5, 0, 0)]
                for ques in all_ques_ids:
                    if ques.id in user_input_line_ids.mapped('question_id').ids:
                        ques.sudo().write({'page_id': ques.repeat_question_id.page_id.id if ques.repeat_question_id else ques.page_id.id,})
                        ques.page_id.sudo().write({'more_ques_and_page_ids': [(4, ques.id)]})
                # last_answered_line = answer.user_input_line_ids.sorted(key=lambda l: l.create_date or l.id)[-1:]
                # last_question = last_answered_line.question_id if last_answered_line else None
                answer.sudo().write({'state':'in_progress','last_displayed_page_id':0})
                survey_url = "/survey/%s/%s" % (survey.access_token, answer.access_token)
                if medic_patient_case_id:
                    medic_patient_case_id.sudo().write({'medic_state':'in_progress', 'medic_survey_submit_date': False})
                if feedback_patient_case_id:
                    feedback_patient_case_id.sudo().write({'feedback_state':'in_progress', 'feedback_survey_submit_date': False})
                return request.redirect(survey_url)

        survey = request.env['survey.survey'].sudo().browse(int(survey_id))
        answer = request.env['survey.user_input'].sudo().browse(int(answer_id))

        if medic_patient_case_id:
            medic_patient_case_id.sudo().write({'medic_state':'submit', 'medic_survey_submit_date': fields.Date.today()})

            today = date.today()
            dob = medic_patient_case_id.patient_dob
            age_str = ''
            if dob:
                years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                months = (today.month - dob.month - (today.day < dob.day)) % 12
                age_str = f"{years} Years {months} Months"
                
            # Get height and weight answers
            weight = height = 0.0
            for line in answer.user_input_line_ids:
                if line.question_id.question_tag == 'weight':
                    weight = float(line.value_numerical_box or 0.0)
                elif line.question_id.question_tag == 'height':
                    height = float(line.value_numerical_box or 0.0)

            # Compute BMI
            bmi = round(float(weight / ((height / 100) ** 2) if height else 0.0), 2)
            
            answer.write({
                        'age': age_str,
                        'bmi': str(bmi),
                        'case_id': medic_patient_case_id.id,
                    })
            
            doctor_number = f"{survey.user_id.partner_id.phone_code.name} {survey.user_id.partner_id.mob}"
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/web#id={answer.id}&model=survey.user_input&view_type=form"
            doctor_msg = (
                f"Hi! {survey.user_id.partner_id.name} {survey.user_id.partner_id.last_name},\n" 
                f"Patient {request.env.user.sudo().partner_id.name} {request.env.user.sudo().partner_id.last_name} has submitted the medical history questionnaire.\n"
                f"Please click on the following link to view the medical history submission\n"
                f"{url}\n"
            )
            param_obj = request.env['ir.config_parameter'].sudo()
            sid = param_obj.get_param('twilio_sid')
            token = param_obj.get_param('twilio_token')
            number = param_obj.get_param('twilio_number')

            client = Client(str(sid), str(token))

            # Send SMS to doctor
            try:
                client.messages.create(
                    body=doctor_msg,
                    from_=str(number),
                    to=doctor_number
                )
                request.env['sms.sms'].sudo().create({
                        'partner_id': survey.user_id.partner_id.id,
                        'number': doctor_number,
                        'state': 'sent',
                        'body': doctor_msg,
                        'is_custom_log': True,
                    })
                _logger.info(f"SMS sent to doctor: {doctor_number}")
            except Exception as e:
                request.env['sms.sms'].sudo().create({
                        'partner_id': survey.user_id.partner_id.id,
                        'number': doctor_number,
                        'state': 'error',
                        'body': doctor_msg,
                        'is_custom_log': True,
                    })
                _logger.error("Failed to send SMS to doctor: %s", e)
            
            # send email
            #doctor
            if survey.user_id.partner_id.email:
                user = survey.user_id
                template_id = request.env.ref('p7_patient_management.survey_completion_template_doctor').sudo()
                ctx = {
                        'default_model': 'res.users',
                        'default_res_id': user.id,
                        'default_use_template': bool(template_id.id),
                        'default_template_id': template_id.id,
                        'default_composition_mode': 'comment',
                        'force_send': True,
                        'object': user,
                        'url': url,
                        'case': medic_patient_case_id,
                        'email_to': survey.user_id.partner_id.email,
                    }
                # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
                email_body = f"""
                        <p style="margin: 0px; padding: 0px; font-size: 15px;">
                        Hello {user.partner_id.name} {user.partner_id.last_name},</p>
                        <br/>
                        <p style="margin: 0px; padding: 0px; font-size: 15px;">
                            Your patient has completed the medical history questionnaire.</p>
                        <br/>
                        <p>Best regards,<br/><strong>VANAESA</strong></p>
                    """
                try:
                    request.env['mail.mail'].sudo().create({
                        'auto_delete': True,
                        'email_to': survey.user_id.partner_id.email,
                        'subject': "Review your patient's Pre-Anaesthetic Questionnaire",
                        'state': 'sent',
                        'author_id': user.partner_id.id,
                        'date': fields.Datetime.now(),
                        'is_custom_log':True,
                        'body_html':email_body
                    })
                    template_id.sudo().with_context(ctx).send_mail(user.id, force_send=True)
                except Exception as e:
                    request.env['mail.mail'].sudo().create({
                        'auto_delete': True,
                        'email_to': survey.user_id.partner_id.email,
                        'subject': "Review your patient's Pre-Anaesthetic Questionnaire",
                        'state': 'exception',
                        'author_id': user.partner_id.id,
                        'date': fields.Datetime.now(),
                        'is_custom_log':True,
                        'body_html':email_body
                    })
                    _logger.error("Failed to send mail: %s", e)
        if feedback_patient_case_id:
            feedback_patient_case_id.sudo().write({'feedback_state':'submit', 'feedback_survey_submit_date': fields.Date.today()})
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/web#id={answer.id}&model=survey.user_input&view_type=form"

            # send email to doctor
            if survey.user_id.partner_id.email:
                user = survey.user_id
                template_id = request.env.ref("p7_patient_management.feedback_survey_completion_template_doctor").sudo()
                ctx = {
                    "default_model": "res.users",
                    "default_res_id": user.id,
                    "default_use_template": bool(template_id.id),
                    "default_template_id": template_id.id,
                    "default_composition_mode": "comment",
                    "force_send": True,
                    "object": user,
                    "url": url,
                    "case": feedback_patient_case_id,
                    "email_to": survey.user_id.partner_id.email,
                }
                try:
                    template_id.sudo().with_context(ctx).send_mail(user.id, force_send=True)
                except Exception as e:
                    _logger.error("Failed to send mail: %s", e)

        return request.redirect('/survey/confirmation')
    
    @http.route('/create_medicine', type='json', auth='public', website=True, csrf=False)
    def create_new_medicine(self, name):
        medicine = request.env['res.medication'].sudo().create({
                        'name':name,
                        'user_id':request.env.user.id,
                    })
        if medicine:
            return {"status": "success", "message": f"{medicine.name} added!",}
        else:
            return {"status": "error", "message": "Not Added in the list!"}
        
    @http.route('/get_medicines', type='json', auth='public', methods=['POST'], website=True, csrf=False)
    def get_medicines(self,query='',limit=10):
        domain = ['|', ('user_id', '=', request.env.user.id), ('user_id', '=', False)]
        if query:
            domain += ['|', ('name', 'ilike', query), ('brand_name', 'ilike', query)]
        medicine_ids = request.env['res.medication'].sudo().search(domain, limit=limit)
        medicines = [{'id': medicine.id, 'name': medicine.name, 'brand_name': medicine.brand_name} for medicine in medicine_ids]
        return medicines

    @http.route('/survey/repeat_question', type='json', auth='public', website=True, csrf=False)
    def repeat_survey_question(self, question_id, answer_token):
        main_question = request.env['survey.question'].sudo().browse(int(question_id))
        answer_id = request.env['survey.user_input'].sudo().search([('access_token','=',answer_token)], limit=1)
        if answer_id.test_entry:
            return {"status": "test"}
        question = (main_question.triggering_answer_ids[0].sudo().question_id
                if main_question.triggering_answer_ids else main_question.repeat_question_id)
        triggered_questions_by_answer = defaultdict(lambda: question.survey_id.env['survey.question'])
        colours = ['#b3e0ff','#ffcccc','#ffcce6','#ffffb3','#ffe6cc','#d9ffb3','#e6ffff','#cce0ff','#d9f2e6','#ffccff','#fff0b3','#ecc6c6']
        all_questions = question.survey_id.question_ids.sudo().with_prefetch()
        for ques in all_questions:
            for triggering_answer_id in ques.triggering_answer_ids:
                if triggering_answer_id.question_id == question:
                    triggered_questions_by_answer[triggering_answer_id] |= ques
        trigger_ques = list(triggered_questions_by_answer.values())
        if not main_question.exists():
            return {"status": "error", "message": "Original question not found"}
        
        # Fetch medications only once
        medicine_ids = request.env['res.medication'].sudo().search(['|', ('user_id', '=', request.env.user.id), ('user_id', '=', False)])
        medicines = [{'id': med.id, 'name': med.name} for med in medicine_ids]

        new_question_ids, questions = [], []
        sequence = main_question.sequence
        initial_sequence = sequence

        sequence_change_ids = request.env['survey.question'].sudo().search(
            [('sequence', '>', initial_sequence), '|', ('survey_id', '=', main_question.survey_id.id), ('repeat_survey_id', '=', main_question.survey_id.id)],
            order='sequence asc'
        )

        random_color = random.choice(colours)
        # trigger_ques = trigger_ques[0].filtered(lambda a: not a.answer_id)
        trigger_ques = [q for q in trigger_ques[0] if not q.answer_id]
        length, header_id = 0, False
        
        max_set_sequence = request.env['survey.question'].sudo().search([
            ('repeat_question_id', '=', question.id),('answer_id', '=', answer_id.id)], order='set_sequence desc', limit=1).set_sequence or 1
        new_set_sequence = max_set_sequence + 1
        for ids in trigger_ques:
            sequence += 1
            length += 1
            new_id = ids.sudo().copy()
            new_id.write({
                'sequence': sequence,
                'survey_id': False,
                'surgic_survey_id': False,
                'medic_survey_id': False,
                'answer_id': answer_id.id,
                'repeat_survey_id': main_question.survey_id.id,
                'is_duplicated': True,
                'suffix': main_question.suffix,
                'colour': random_color,
                'set_sequence': new_set_sequence,
            })
            new_question_ids.append(new_id.id)

        # Bulk update sequence
        last_sequence = sequence
        for rec in sequence_change_ids:
            last_sequence += 1
            rec.write({'sequence': last_sequence})

        # Re-fetch the updated list of questions
        new_change_ids = request.env['survey.question'].sudo().search(
            ['|', ('survey_id', '=', main_question.survey_id.id), '&', ('repeat_survey_id', '=', main_question.survey_id.id), ('answer_id', '=', answer_id.id)],
            order='sequence asc'
        )
        main_question.survey_id.question_and_page_ids = new_change_ids
        line_len = 0
        for line in request.env['survey.question'].sudo().browse(new_question_ids):
            line_len += 1
            if line_len == 1:
                header_id = line
                header_id.write({'is_header': True, 'length': length - 1})

            if header_id:
                line.write({'repeat_ques_id': header_id.id})

            line.write({'repeat_question_id': question.id})

            questions.append({
                'id': line.id,
                'title': line.title,
                'description': line.description,
                'is_medic': bool(line.medic_details),
                'type': line.question_type,
                'is_mandate': bool(line.constr_mandatory),
                'is_header': bool(line.is_header),
                'is_duplicated': bool(line.is_duplicated),
                'colour': line.colour,
            })

        return {
            "status": "success",
            "questions": questions,
            "previousquestionId": main_question.id,
            "length": length - 1,
            "medicines": medicines,
        }
        
    @http.route('/survey/delete_question', type='json', auth='public', website=True, csrf=False)
    def delete_survey_question(self, question_id, answer_token):
        question = request.env['survey.question'].sudo().browse(int(question_id))
        answer_id = request.env['survey.user_input'].sudo().search([('access_token','=',answer_token)])
        repeat_ques_ids = request.env['survey.question'].sudo().search([('repeat_ques_id', '=', question.id),('answer_id','=',answer_id.id)])
        all_related_question_ids = repeat_ques_ids.ids + [question.id]
        user_input_lines = request.env['survey.user_input.line'].sudo().search([
            ('user_input_id', '=', answer_id.id),
            ('question_id', 'in', all_related_question_ids)
        ])
        user_input_lines.unlink()
        seq_ids = request.env['survey.question'].sudo().search([('repeat_question_id', '=', question.repeat_question_id.id),('answer_id','=',answer_id.id),('id','not in', repeat_ques_ids.ids),('id','!=',question.id)],order="set_sequence asc")
        sequence = question.set_sequence
        for rec in repeat_ques_ids:
            rec.sudo().unlink()
        if question.exists():
            question.sudo().unlink()
        for rec in seq_ids.filtered(lambda a: a.set_sequence > sequence):
            rec.sudo().write({'set_sequence': rec.set_sequence - 1})
            
    
    @http.route('/survey/submit_question', type='json', auth='public', website=True, csrf=False)
    def submit_survey_questions(self, data):
        formdata = data.get('formdata', {})
        _logger.info('----------date---:%s',data)
        _logger.info('----------formdate---:%s',formdata)
        if formdata.get('token',False):
            active_lang = request.env.user.lang
            lang_rec = request.env['res.lang'].search([('code', '=', active_lang)], limit=1)
            submit_id = request.env['survey.user_input'].sudo().search([('access_token', '=', formdata.get('token'))])
            question_ids = [int(key) for key in formdata.keys() if key not in ['csrf_token', 'token'] and key.isdigit()]
            survey_questions = request.env['survey.question'].sudo().browse(question_ids if question_ids else [])
            if survey_questions:
                sequence_ids = survey_questions.mapped('sequence')
                sequences = self.get_answer_sequence(sequence_ids)
                if submit_id:
                    for line,sequence in zip(survey_questions, sequences):
                        line.sudo().write({'sequence': sequence})
                        date = False
                        datetime_local = False
                        if line.question_type == 'date':
                            date = formdata.get(f"{line.id}")
                            if '/' in formdata.get(f"{line.id}"):
                                date_obj = datetime.strptime(date, f'{lang_rec.date_format}')
                                date = date_obj.strftime('%Y-%m-%d')
                        if line.question_type == 'datetime':
                            datetime_local = formdata.get(f"{line.id}")
                            if 'T' in formdata.get(f"{line.id}"):
                                date_obj = datetime.strptime(datetime_local, '%Y-%m-%dT%H:%M')
                                datetime_local = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                            if '/' in formdata.get(f"{line.id}"):
                                date_obj = datetime.strptime(datetime_local, f'{lang_rec.date_format} {lang_rec.time_format}')
                                datetime_local = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                        if line.repeat_survey_id and line.repeat_question_id and formdata.get(f"{line.id}") != "":
                            line.sudo().write({'repeat_answer_id': submit_id.id})
                            vals = {
                                'user_input_id': submit_id.id,
                                'survey_id': submit_id.survey_id.id,
                                'question_id': line.id,
                                'question_sequence': sequence,
                                'colour':line.colour,
                                'answer_type': line.question_type,
                                'value_char_box': formdata.get(f"{line.id}") if line.question_type == 'char_box' else '',
                                'value_numerical_box': float(formdata.get(f"{line.id}")) if line.question_type == 'numerical_box' else False,
                                'value_text_box': formdata.get(f"{line.id}") if line.question_type == 'text_box' else '',
                                'value_date': date if line.question_type == 'date' else False,
                                'value_datetime': datetime_local if line.question_type == 'datetime' else False
                            }
                            existing_answer_ids = request.env['survey.user_input.line'].sudo().search([
                                            ('user_input_id', '=', submit_id.id),
                                            ('survey_id', '=', submit_id.survey_id.id),
                                            ('question_id', '=', line.id),
                                            ('question_sequence', '=', sequence),
                                        ],limit=1)
                            new_answer_id = request.env['survey.user_input.line'].sudo().create(vals)
                            for lines in existing_answer_ids:
                                if lines.question_sequence == new_answer_id.question_sequence:
                                    if lines.question_id.repeat_question_id:
                                        lines.unlink()
                        else:
                            if formdata.get(f"{line.id}") == '' and line.question_type != 'file':
                                if line.triggering_question_ids:
                                    if line.triggering_answer_ids and formdata.get(f"{line.triggering_question_ids[0].id}"):
                                        if line.triggering_answer_ids and line.triggering_answer_ids[0].id != formdata.get(f"{line.triggering_question_ids[0].id}") if formdata.get(f"{line.triggering_question_ids[0].id}").isdigit() else 0:
                                            line.sudo().write({
                                                                'repeat_answer_id': submit_id.id,
                                                                'repeat_survey_id': submit_id.survey_id.id,
                                                                # 'page_id':int(formdata.get('page_id'))
                                                            })
                                            vals = {
                                                'user_input_id': submit_id.id,
                                                'survey_id': submit_id.survey_id.id,
                                                'question_id': line.id,
                                                'question_sequence': sequence,
                                                'skipped':True,
                                                'is_hidden':True,
                                            }
                                            existing_skipped_ids = request.env['survey.user_input.line'].sudo().search([
                                                        ('user_input_id', '=', submit_id.id),
                                                        ('survey_id', '=', submit_id.survey_id.id),
                                                        ('question_id', '=', line.id),
                                                        ('question_sequence', '=', sequence),
                                                    ])
                                            new_skipped_id = request.env['survey.user_input.line'].sudo().create(vals)
                                            for lines in existing_skipped_ids:
                                                if lines.question_sequence == new_skipped_id.question_sequence:
                                                    lines.unlink()
                                elif line.repeat_survey_id and line.repeat_question_id:
                                    line.sudo().write({
                                                    'repeat_answer_id': submit_id.id,
                                                    'repeat_survey_id': submit_id.survey_id.id,
                                                    # 'page_id':int(formdata.get('page_id'))
                                                })
                                    vals = {
                                            'user_input_id': submit_id.id,
                                            'survey_id': submit_id.survey_id.id,
                                            'question_id': line.id,
                                            'question_sequence': sequence,
                                            'skipped':True,
                                            'is_hidden':True,
                                        }
                                    existing_skip_ids = request.env['survey.user_input.line'].sudo().search([
                                                    ('user_input_id', '=', submit_id.id),
                                                    ('survey_id', '=', submit_id.survey_id.id),
                                                    ('question_id', '=', line.id),
                                                    ('question_sequence', '=', sequence),
                                                ],limit=1)
                                    new_skip_id = request.env['survey.user_input.line'].sudo().create(vals)
                                    for lines in existing_skip_ids:
                                        if lines.question_sequence == new_skip_id.question_sequence:
                                            lines.unlink()
                            else:
                                if line.question_type != 'file':
                                    # delete_rec = request.env['survey.user_input.line']
                                    # delete_ques = request.env['survey.question']
                                    should_continue = True
                                    if line.question_type == "multiple_choice":
                                        answer = formdata.get(f"{line.id}")
                                        if type(answer) == list:
                                            should_continue = False
                                            answer_ids = [int(aid) for aid in formdata.get(f"{line.id}")]

                                            vals_list = []
                                            for answer_id in answer_ids:
                                                vals_list.append({
                                                    'user_input_id': submit_id.id,
                                                    'survey_id': submit_id.survey_id.id,
                                                    'question_id': line.id,
                                                    'question_sequence': sequence,
                                                    'suggested_answer_id': answer_id,
                                                    'colour': line.colour,
                                                    'answer_type': 'suggestion',
                                                    'value_char_box': '',
                                                    'value_numerical_box': False,
                                                    'value_text_box': '',
                                                    'value_date': False,
                                                    'value_datetime': False
                                                })
                                            existing_skip_ids = request.env['survey.user_input.line'].sudo().search([
                                                ('user_input_id', '=', submit_id.id),
                                                ('survey_id', '=', submit_id.survey_id.id),
                                                ('question_id', '=', line.id),
                                                ('question_sequence', '=', sequence),
                                            ]).unlink()
                                            existing_sk_ids = request.env['survey.user_input.line'].sudo().search([
                                                ('user_input_id', '=', submit_id.id),
                                                ('question_id', '=', line.id),
                                            ]).unlink()
                                            new_skip_ids = request.env['survey.user_input.line'].sudo().create(vals_list)

                                    if should_continue:
                                        vals = {
                                            'user_input_id': submit_id.id,
                                            'survey_id': submit_id.survey_id.id,
                                            'question_id': line.id,
                                            'question_sequence': sequence,
                                            'suggested_answer_id':int(formdata.get(f"{line.id}")) if line.question_type in ['simple_choice','multiple_choice'] else False,
                                            'colour': line.colour,
                                            'answer_type': line.question_type if line.question_type not in ['matrix','simple_choice','multiple_choice'] else 'suggestion',
                                            'value_char_box': formdata.get(f"{line.id}") if line.question_type == 'char_box' else '',
                                            'value_numerical_box': float(formdata.get(f"{line.id}")) if line.question_type == 'numerical_box' else False,
                                            'value_text_box': formdata.get(f"{line.id}") if line.question_type == 'text_box' else '',
                                            'value_date': date if line.question_type == 'date' else False,
                                            'value_datetime': datetime_local if line.question_type == 'datetime' else False
                                        }
                                        new_skip_id = request.env['survey.user_input.line'].sudo().create(vals)
                                        existing_skip_ids = request.env['survey.user_input.line'].sudo().search([
                                            ('user_input_id', '=', submit_id.id),
                                            ('survey_id', '=', submit_id.survey_id.id),
                                            ('question_id', '=', line.id),
                                            ('question_sequence', '=', sequence),
                                        ], limit=1)
                                        existing_sk_ids = request.env['survey.user_input.line'].sudo().search([
                                            ('user_input_id', '=', submit_id.id),
                                            ('question_id', '=', line.id),
                                        ])
                                        if existing_sk_ids and len(existing_sk_ids) > 1:
                                            existing_sk_ids[0].unlink()
                                        if existing_skip_ids and existing_skip_ids.id == new_skip_id.id and not submit_id.is_edit:
                                            # if lines.question_id.answer_id:
                                            existing_skip_ids[0].unlink()

                                        prev_answer_line = request.env['survey.user_input.line'].sudo().search([
                                            ('user_input_id', '=', submit_id.id),
                                            ('survey_id', '=', submit_id.survey_id.id),
                                            ('question_id', '=', line.id),
                                        ], limit=1)

                                        new_answer_value = int(formdata.get(f"{line.id}")) if formdata.get(
                                            f"{line.id}") and formdata.get(f"{line.id}").isdigit() else None

                                    if line.question_type == 'simple_choice' and prev_answer_line and prev_answer_line.suggested_answer_id:
                                        new_value = request.env['survey.question.answer'].sudo().browse(
                                            new_answer_value)
                                        prev_value = prev_answer_line.suggested_answer_id
                                        if new_value != prev_value:
                                            triggering_question_ids = request.env['survey.question'].sudo().search([
                                                ('survey_id', '=', submit_id.survey_id.id),
                                                ('triggering_answer_ids', 'in', new_value.id)])
                                            if not triggering_question_ids:
                                                triggering_question_ids = request.env['survey.question'].sudo().search([
                                                    ('survey_id', '=', submit_id.survey_id.id),
                                                    ('triggering_answer_ids', 'in', prev_value.id)])

                                                for rec in triggering_question_ids:
                                                    if rec.triggering_answer_ids and rec.triggering_answer_ids[
                                                        0] != new_value:
                                                        triggered_answers = request.env[
                                                            'survey.user_input.line'].sudo().search([
                                                            ('user_input_id', '=', submit_id.id),
                                                            ('survey_id', '=', submit_id.survey_id.id),
                                                            ('question_id', '=', rec.id),
                                                        ])

                                                        #             _logger.warning(f"Could not unlink survey.user_input.line after retries for {rec.title}: {e}")
                                                        if triggered_answers:
                                                            delete_rec += triggered_answers
                                                        if rec.answer_id == submit_id:
                                                            delete_ques += rec

                                    # print(delete_rec,'-------------------------------------66666666666666666----------------------------------')
                                    # delete_rec.sudo().unlink()
                                    # delete_ques.sudo().unlink()
                          
        return {'status': 'success'}

class CustomSurveyController(Survey):
    
    @http.route('/survey/partial-submit', type='json', auth='public', website=True, csrf=False)
    def submit_partial(self, survey_token,answer_token):
        patient_id = request.env.user.sudo().partner_id.id
        access_data = self._get_access_data(survey_token, answer_token, ensure_token=True)
        survey_sudo, answer_sudo = access_data['survey_sudo'], access_data['answer_sudo']
        user_tz = pytz.timezone(request.env.user.tz or 'UTC')
        local_op_date = False
        case_id = request.env['patient.case'].sudo().search(['|',('medic_answer_id', '=', answer_sudo.id),('feedback_answer_id', '=', answer_sudo.id)],limit=1)
        if case_id and case_id.op_date:
            local_op_date = pytz.utc.localize(case_id.op_date).astimezone(user_tz)
        patient_number = f"{request.env.user.sudo().partner_id.phone_code.name} {request.env.user.sudo().partner_id.mob}"
        doctor_number = f"{survey_sudo.user_id.partner_id.phone_code.name} {survey_sudo.user_id.partner_id.mob}"
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/survey/{survey_token}/{answer_token}"
        patient_msg = (
            f"Hi! A reminder to complete your questionnaire\n"
            f"{url}\n"
        )
        doctor_msg = (
            f"Hi {survey_sudo.user_id.partner_id.name} {survey_sudo.user_id.partner_id.last_name}, patient {request.env.user.sudo().partner_id.name} {request.env.user.sudo().partner_id.last_name} has partially completed the medical history questionnaire for surgery on {local_op_date.strftime('%d/%m/%y') if local_op_date else ''} with Dr {case_id.op_surgeon if case_id else ''}\n"
        )
        
        param_obj = request.env['ir.config_parameter'].sudo()
        sid = param_obj.get_param('twilio_sid')
        token = param_obj.get_param('twilio_token')
        number = param_obj.get_param('twilio_number')

        client = Client(str(sid), str(token))

        # Send SMS to patient
        try:
            client.messages.create(
                body=patient_msg,
                from_=str(number),
                to=patient_number
            )
            request.env['sms.sms'].sudo().create({
                    'partner_id': patient_id,
                    'number': patient_number,
                    'state': 'sent',
                    'body': patient_msg,
                    'is_custom_log': True,
                })
            _logger.info(f"SMS sent to patient: {patient_number}")
        except Exception as e:
            request.env['sms.sms'].sudo().create({
                    'partner_id': patient_id,
                    'number': patient_number,
                    'state': 'error',
                    'body': patient_msg,
                    'is_custom_log': True,
                })
            _logger.error("Failed to send SMS to patient: %s", e)

        # Send SMS to doctor
        try:
            client.messages.create(
                body=doctor_msg,
                from_=str(number),
                to=doctor_number
            )
            request.env['sms.sms'].sudo().create({
                    'partner_id': survey_sudo.user_id.partner_id.id,
                    'number': doctor_number,
                    'state': 'sent',
                    'body': doctor_msg,
                    'is_custom_log': True,
                })
            _logger.info(f"SMS sent to doctor: {doctor_number}")
        except Exception as e:
            request.env['sms.sms'].sudo().create({
                    'partner_id': survey_sudo.user_id.partner_id.id,
                    'number': doctor_number,
                    'state': 'error',
                    'body': doctor_msg,
                    'is_custom_log': True,
                })
            _logger.error("Failed to send SMS to doctor: %s", e)
        
        # send email
        #patient
        if request.env.user.sudo().partner_id.email:
            user = request.env.user
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/survey/{survey_token}/{answer_token}"
            template_id = request.env.ref('p7_patient_management.partial_survey_notification_template').sudo()
            ctx = {
                    'default_model': 'res.users',
                    'default_res_id': user.id,
                    'default_use_template': bool(template_id.id),
                    'default_template_id': template_id.id,
                    'default_composition_mode': 'comment',
                    'force_send': True,
                    'object': user,
                    'surgeon': case_id.op_surgeon,
                    'url':url,
                    'email_to': request.env.user.sudo().partner_id.email,
                }
            # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
            email_body = f"""
                        <p style="margin: 0px; padding: 0px; font-size: 15px;"> Hi {user.partner_id.name} {user.partner_id.last_name}, <p>
                        <br/>
                        <p style="margin: 0px; padding: 0px; font-size: 15px;"> Please find the url to complete the medical form which you left incomplete: </p>
                        <br/>
                        <a style="background-color: #54b1c9; padding:8px 16px 8px 16px; text-decoration:none; color:#fff; border-radius:5px" href="{url}">Survey URL</a>
                        <br/>
                        <p>Best regards,<br/><strong>VANAESA</strong></p> """
            try:
                request.env['mail.mail'].sudo().create({
                    'auto_delete': True,
                    'email_to': request.env.user.sudo().partner_id.email,
                    'subject': "An Important Reminder",
                    'state': 'sent',
                    'author_id': user.partner_id.id,
                    'date': fields.Datetime.now(),
                    'is_custom_log':True,
                    'body_html':email_body
                })
                template_id.sudo().with_context(ctx).send_mail(user.id, force_send=True)
            except Exception as e:
                request.env['mail.mail'].sudo().create({
                    'auto_delete': True,
                    'email_to': request.env.user.sudo().partner_id.email,
                    'subject': "An Important Reminder",
                    'state': 'exception',
                    'author_id': user.partner_id.id,
                    'date': fields.Datetime.now(),
                    'is_custom_log':True,
                    'body_html':email_body
                })
                _logger.error("Failed to send mail: %s", e)
        #doctor
        if survey_sudo.user_id.partner_id.email:
            user = survey_sudo.user_id
            template_id = request.env.ref('p7_patient_management.partial_survey_notification_template_doctor').sudo()
            ctx = {
                    'default_model': 'res.users',
                    'default_res_id': user.id,
                    'default_use_template': bool(template_id.id),
                    'default_template_id': template_id.id,
                    'default_composition_mode': 'comment',
                    'force_send': True,
                    'object': user,
                    'case': case_id,
                    'email_to': survey_sudo.user_id.partner_id.email,
                }
            # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
            email_body = f"""
                        <p style="margin: 0px; padding: 0px; font-size: 15px;"> Hi {user.partner_id.name} {user.partner_id.last_name}, <p>
                        <br/>
                        <p style="margin: 0px; padding: 0px; font-size: 15px;"> Patient {request.env.user.sudo().partner_id.name} {request.env.user.sudo().partner_id.last_name} has partially completed the medical history questionnaire. </p>
                        <br/>
                        <p>Best regards,<br/><strong>VANAESA</strong></p> """
            try:
                request.env['mail.mail'].sudo().create({
                    'auto_delete': True,
                    'email_to': survey_sudo.user_id.partner_id.email,
                    'subject': "Partial Form Completion",
                    'state': 'sent',
                    'author_id': user.partner_id.id,
                    'date': fields.Datetime.now(),
                    'is_custom_log':True,
                    'body_html':email_body
                })
                template_id.sudo().with_context(ctx).send_mail(user.id, force_send=True)
            except Exception as e:
                request.env['mail.mail'].sudo().create({
                    'auto_delete': True,
                    'email_to': survey_sudo.user_id.partner_id.email,
                    'subject': "Partial Form Completion",
                    'state': 'exception',
                    'author_id': user.partner_id.id,
                    'date': fields.Datetime.now(),
                    'is_custom_log':True,
                    'body_html':email_body
                })
                _logger.error("Failed to send mail: %s", e)
                
        answer_sudo.open_survey()
        if request.env.user.sudo().partner_id.user_type == 'patient':
            return {'redirect_url': '/patient-dashboard'}
        else:
            return {'redirect_url': '/web'}
    
    def _redirect_with_error(self, access_data, error_key):
        values = request.params.copy()
        survey_sudo = access_data['survey_sudo']
        answer_sudo = access_data['answer_sudo']
        uniq_id = False
        pcid = False
        if values.get('uniq_id',False):
            uniq_id = values.get('uniq_id')
        if values.get('pcid',False):
            pcid = values.get('pcid')
        if error_key == 'survey_void' and access_data['can_answer']:
            return request.render("survey.survey_void_content", {'survey': survey_sudo, 'answer': answer_sudo})
        elif error_key == 'survey_closed' and access_data['can_answer']:
            return request.render("survey.survey_closed_expired", {'survey': survey_sudo})
        elif error_key == 'survey_auth':
            if not answer_sudo:  # survey is not even started
                redirect_url = '/web/login?redirect=/survey/start/%s' % survey_sudo.access_token
            elif answer_sudo.access_token:  # survey is started but user is not logged in anymore.
                if answer_sudo.partner_id and (answer_sudo.partner_id.user_ids or survey_sudo.users_can_signup):
                    if answer_sudo.partner_id.user_ids:
                        answer_sudo.partner_id.signup_cancel()
                    else:
                        answer_sudo.partner_id.signup_prepare(expiration=fields.Datetime.now() + relativedelta(days=1))
                    redirect_url = answer_sudo.partner_id._get_signup_url_for_action(url='/survey/start/%s?answer_token=%s' % (survey_sudo.access_token, answer_sudo.access_token))[answer_sudo.partner_id.id]
                else:
                    redirect_url = '/web/login?redirect=%s' % ('/survey/start/%s?answer_token=%s' % (survey_sudo.access_token, answer_sudo.access_token))
            if uniq_id:
                redirect_url = f"{redirect_url}&uniq_id={uniq_id}&pcid={pcid}"
            return request.redirect(redirect_url) #request.render("survey.survey_auth_required", {'survey': survey_sudo, 'redirect_url': redirect_url})
        elif error_key == 'answer_deadline' and answer_sudo.access_token:
            return request.render("survey.survey_closed_expired", {'survey': survey_sudo})
        elif error_key in ['answer_wrong_user', 'token_wrong']:
            return request.render("survey.survey_access_error", {'survey': survey_sudo})

        return request.redirect("/")

    @http.route('/survey/submit/<string:survey_token>/<string:answer_token>', type='json', auth='public', website=True, csrf=False)
    def survey_submit(self, survey_token, answer_token, **post):
        """ Submit a page from the survey.
        This will take into account the validation errors and store the answers to the questions.
        If the time limit is reached, errors will be skipped, answers will be ignored and
        survey state will be forced to 'done'.
        Also returns the correct answers if the scoring type is 'scoring_with_answers_after_page'."""
        # Survey Validation
        access_data = self._get_access_data(survey_token, answer_token, ensure_token=True)
        if access_data['validity_code'] is not True:
            return {}, {'error': access_data['validity_code']}
        survey_sudo, answer_sudo = access_data['survey_sudo'], access_data['answer_sudo']
        if answer_sudo.state == 'done':
            return {}, {'error': 'unauthorized'}

        questions, page_or_question_id = survey_sudo._get_survey_questions(answer=answer_sudo,
                                                                           page_id=post.get('page_id'),
                                                                           question_id=post.get('question_id'))
        patient_number = f"{request.env.user.partner_id.phone_code.name} {request.env.user.partner_id.mob}"
        doctor_number = f"{survey_sudo.user_id.partner_id.phone_code.name} {survey_sudo.user_id.partner_id.mob}"
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/survey/{survey_token}/{answer_token}"
        
        if not answer_sudo.test_entry and not survey_sudo._has_attempts_left(answer_sudo.partner_id, answer_sudo.email, answer_sudo.invite_token):
            # prevent cheating with users creating multiple 'user_input' before their last attempt
            return {}, {'error': 'unauthorized'}

        if answer_sudo.survey_time_limit_reached or answer_sudo.question_time_limit_reached:
            if answer_sudo.question_time_limit_reached:
                time_limit = survey_sudo.session_question_start_time + relativedelta(
                    seconds=survey_sudo.session_question_id.time_limit
                )
                time_limit += timedelta(seconds=3)
            else:
                time_limit = answer_sudo.start_datetime + timedelta(minutes=survey_sudo.time_limit)
                time_limit += timedelta(seconds=10)
            if fields.Datetime.now() > time_limit:
                # prevent cheating with users blocking the JS timer and taking all their time to answer
                return {}, {'error': 'unauthorized'}

        errors = {}
        # Prepare answers / comment by question, validate and save answers
        for question in questions:
            inactive_questions = request.env['survey.question'] if answer_sudo.is_session_answer else answer_sudo._get_inactive_conditional_questions()
            if question in inactive_questions:  # if question is inactive, skip validation and save
                continue
            answer, comment = self._extract_comment_from_answers(question, post.get(str(question.id)))
            errors.update(question.validate_question(answer, comment))
            if not errors.get(question.id):
                answer_sudo._save_lines(question, answer, comment, overwrite_existing=survey_sudo.users_can_go_back or question.save_as_nickname or question.save_as_email)

        if errors and not (answer_sudo.survey_time_limit_reached or answer_sudo.question_time_limit_reached):
            return {}, {'error': 'validation', 'fields': errors}

        if not answer_sudo.is_session_answer:
            answer_sudo._clear_inactive_conditional_answers()

        # Get the page questions correct answers if scoring type is scoring after page
        correct_answers = {}
        if survey_sudo.scoring_type == 'scoring_with_answers_after_page':
            scorable_questions = (questions - answer_sudo._get_inactive_conditional_questions()).filtered('is_scored_question')
            correct_answers = scorable_questions._get_correct_answers()
        if answer_sudo.survey_time_limit_reached or survey_sudo.questions_layout == 'one_page':
            if answer_sudo.survey_time_limit_reached:
                patient_msg = (
                    f"Hi {request.env.user.partner_id.name} {request.env.user.partner_id.last_name}\n"
                    f"To continue goto {url}\n"
                )
                doctor_msg = (
                    f"{survey_sudo.user_id.name} {survey_sudo.user_id.last_name}\n"
                    f"Patient {request.env.user.partner_id.name} {request.env.user.partner_id.last_name} has exceeded time limit while filling medical history questionnaire.\n"
                )
                try:
                    param_obj = request.env['ir.config_parameter'].sudo()
                    sid = param_obj.get_param('twilio_sid')
                    token = param_obj.get_param('twilio_token')
                    number = param_obj.get_param('twilio_number')
                    client = Client(str(sid), str(token))
                    client.messages.create(
                        body=patient_msg,
                        from_=str(number),
                        to=patient_number
                    )
                    request.env['sms.sms'].sudo().create({
                        'partner_id': request.env.user.partner_id.id,
                        'number': patient_number,
                        'state': 'sent',
                        'body': patient_msg,
                        'is_custom_log': True,
                    })
                except Exception as e:
                    request.env['sms.sms'].sudo().create({
                        'partner_id': request.env.user.partner_id.id,
                        'number': patient_number,
                        'state': 'error',
                        'body': patient_msg,
                        'is_custom_log': True,
                    })
                    _logger.error("Failed to send sms: %s", e)
                    # raise ValidationError(_("Message not sent to the patient. Please contact Administrator!"))
                
                try:
                    param_obj = request.env['ir.config_parameter'].sudo()
                    sid = param_obj.get_param('twilio_sid')
                    token = param_obj.get_param('twilio_token')
                    number = param_obj.get_param('twilio_number')
                    client = Client(str(sid), str(token))
                    client.messages.create(
                        body=doctor_msg,
                        from_=str(number),
                        to=doctor_number
                    )
                    request.env['sms.sms'].sudo().create({
                        'partner_id': survey_sudo.user_id.id,
                        'number': doctor_number,
                        'state': 'sent',
                        'body': doctor_msg,
                        'is_custom_log': True,
                    })
                except Exception as e:
                    request.env['sms.sms'].sudo().create({
                        'partner_id': survey_sudo.user_id.id,
                        'number': doctor_number,
                        'state': 'error',
                        'body': doctor_msg,
                        'is_custom_log': True,
                    })
                    _logger.error("Failed to send sms: %s", e)
                    # raise ValidationError(_("Message not sent to the doctor. Please contact Administrator!"))
                
                answer_sudo.open_survey()
                return request.session.logout(keep_db=True)
            else:
                answer_sudo._mark_done()

        elif 'previous_page_id' in post:
            # when going back, save the last displayed to reload the survey where the user left it.
            answer_sudo.last_displayed_page_id = post['previous_page_id']
            # Go back to specific page using the breadcrumb. Lines are saved and survey continues
            return correct_answers, self._prepare_question_html(survey_sudo, answer_sudo, **post)
        elif 'next_skipped_page_or_question' in post:
            answer_sudo.last_displayed_page_id = page_or_question_id
            return correct_answers, self._prepare_question_html(survey_sudo, answer_sudo, next_skipped_page=True)
        else:
            if not answer_sudo.is_session_answer:
                page_or_question = request.env['survey.question'].sudo().browse(page_or_question_id)
                if answer_sudo.survey_first_submitted and answer_sudo._is_last_skipped_page_or_question(page_or_question):
                    next_page = request.env['survey.question']
                else:
                    next_page = survey_sudo._get_next_page_or_question(answer_sudo, page_or_question_id)
                if not next_page:
                    if survey_sudo.users_can_go_back and answer_sudo.user_input_line_ids.filtered(
                            lambda a: a.skipped and a.question_id.constr_mandatory):
                        answer_sudo.write({
                            'last_displayed_page_id': page_or_question_id,
                            'survey_first_submitted': True,
                        })
                        return correct_answers, self._prepare_question_html(survey_sudo, answer_sudo, next_skipped_page=True)
                    else:
                        answer_sudo._mark_done()

            answer_sudo.last_displayed_page_id = page_or_question_id
        patient_case_id = request.env['patient.case'].sudo().search([('medic_answer_id', '=', answer_sudo.id)],limit=1)
        feedback_case_id = request.env['patient.case'].sudo().search([('feedback_answer_id', '=', answer_sudo.id)],limit=1)
        if post.get('continue_later',False):
            if patient_case_id:
                patient_case_id.sudo().write({'medic_state':'in_progress','medic_survey_submit_date': False})
            if feedback_case_id:
                patient_case_id.sudo().write({'feedback_state':'in_progress', 'feedback_survey_submit_date': False})
            # return request.redirect("/patient-dashboard")
        if patient_case_id:
            if answer_sudo.state == 'in_progress':
                patient_case_id.sudo().write({'medic_state':'in_progress', 'medic_survey_submit_date': False})
            # else:
            #     patient_case_id.sudo().write({'medic_state':'submit', 'medic_survey_submit_date': fields.Date.today()})
        if feedback_case_id:
            if answer_sudo.state == 'in_progress':
                feedback_case_id.sudo().write({'feedback_state':'in_progress','feedback_survey_submit_date': False})
            # else:
            #     feedback_case_id.sudo().write({'feedback_state':'submit','feedback_survey_submit_date': fields.Date.today()})
        return correct_answers, self._prepare_question_html(survey_sudo, answer_sudo)

    @http.route('/survey/start/<string:survey_token>', type='http', auth='public', website=True, csrf=False)
    def survey_start(self, survey_token, answer_token=None, email=False, **post):
        """ Start a survey by providing
         * a token linked to a survey;
         * a token linked to an answer or generate a new token if access is allowed;
        """
        # Get the current answer token from cookie
        values = request.params.copy()
        answer_from_cookie = False
        if not answer_token:
            answer_token = request.httprequest.cookies.get('survey_%s' % survey_token)
            answer_from_cookie = bool(answer_token)

        access_data = self._get_access_data(survey_token, answer_token, ensure_token=False)

        if answer_from_cookie and access_data['validity_code'] in ('answer_wrong_user', 'token_wrong'):
            # If the cookie had been generated for another user or does not correspond to any existing answer object
            # (probably because it has been deleted), ignore it and redo the check.
            # The cookie will be replaced by a legit value when resolving the URL, so we don't clean it further here.
            access_data = self._get_access_data(survey_token, None, ensure_token=False)

        if access_data['validity_code'] is not True:
            return self._redirect_with_error(access_data, access_data['validity_code'])

        survey_sudo, answer_sudo = access_data['survey_sudo'], access_data['answer_sudo']
        if not answer_sudo:
            try:
                answer_sudo = survey_sudo._create_answer(user=request.env.user, email=email)
            except UserError:
                answer_sudo = False

        if not answer_sudo:
            try:
                survey_sudo.with_user(request.env.user).check_access_rights('read')
                survey_sudo.with_user(request.env.user).check_access_rule('read')
            except:
                return request.redirect("/")
            else:
                return request.render("survey.survey_403_page", {'survey': survey_sudo})
            
        def _get_age_str(patient_dob):
            # Calculate age from Patient DOB
            today = date.today()
            age_str = ''
            if patient_dob:
                years = today.year - patient_dob.year - ((today.month, today.day) < (patient_dob.month, patient_dob.day))
                months = (today.month - patient_dob.month - (today.day < patient_dob.day)) % 12
                age_str = f"{years} Years {months} Months"
            return age_str

        patient_case_id = request.env['patient.case'].sudo().search([('patient_id', '=', request.env.user.sudo().partner_id.id),('medic_survey_id', '=', survey_sudo.id),('medic_state', '=', 'confirm')],limit=1)
        if patient_case_id:
            age_str = _get_age_str(patient_case_id.patient_dob)

            # Get height and weight answers
            weight = height = 0.0
            for line in answer_sudo.user_input_line_ids:
                if line.question_id.question_tag == 'weight':
                    weight = float(line.value_numerical_box or 0.0)
                elif line.question_id.question_tag == 'height':
                    height = float(line.value_numerical_box or 0.0)

            # Compute BMI
            bmi = round(float(weight / ((height / 100) ** 2) if height else 0.0), 2)

            # Update the records
            patient_case_id.sudo().write({
                'medic_answer_id': answer_sudo.id,
                'medic_survey_start_date': fields.Date.today()
            })

            answer_sudo.write({
                "op_datetime": patient_case_id.op_date,
                "op_duration_hrs": patient_case_id.op_duration_hrs,
                "op_duration_mins": patient_case_id.op_duration_mins,
                "location": str(patient_case_id.op_location_id.name),
                "op_process": patient_case_id.op_process,
                "op_surgeon": patient_case_id.op_surgeon,
                "op_nric_number": patient_case_id.patient_nric_number,
                "gender": patient_case_id.patient_gender,
                "age": age_str,
                "bmi": str(bmi),
                "case_id": patient_case_id.id,
            })

        patient_case_id = request.env['patient.case'].sudo().search([('patient_id', '=', request.env.user.sudo().partner_id.id),('feedback_survey_id', '=', survey_sudo.id),('feedback_state', '=', 'confirm')],limit=1)
        if patient_case_id:
            age_str = _get_age_str(patient_case_id.patient_dob)

            patient_case_id.sudo().write({
                "feedback_answer_id": answer_sudo.id,
                "feedback_survey_start_date": fields.Date.today()
            })

            answer_sudo.write({
                "op_datetime": patient_case_id.op_date,
                "op_duration_hrs": patient_case_id.op_duration_hrs,
                "op_duration_mins": patient_case_id.op_duration_mins,
                "location": str(patient_case_id.op_location_id.name),
                "op_process": patient_case_id.op_process,
                "op_surgeon": patient_case_id.op_surgeon,
                "op_nric_number": patient_case_id.patient_nric_number,
                "gender": patient_case_id.patient_gender,
                "age": age_str,
                "bmi": patient_case_id.medic_answer_id.bmi,  # get bmi from pre-anaesthetic answer
                "case_id": patient_case_id.id,
            })

        return request.redirect('/survey/%s/%s' % (survey_sudo.access_token, answer_sudo.access_token))
    
    def _prepare_survey_data(self, survey_sudo, answer_sudo, **post):
        data = super(CustomSurveyController, self)._prepare_survey_data(survey_sudo, answer_sudo, **post)

        if survey_sudo.questions_layout == 'page_per_question':
            current_question = data.get('question')
            user_lines = answer_sudo.user_input_line_ids
            if current_question and current_question.answer_id and current_question.answer_id.id != answer_sudo.id:
                next_question = self._get_next_triggered_question(survey_sudo, answer_sudo, current_question)
                if next_question:
                    data.update({
                        'question': next_question,
                        'has_answered': user_lines.filtered(lambda line: line.question_id == next_question),
                        'can_go_back': survey_sudo._can_go_back(answer_sudo, next_question),
                        'previous_page_id': survey_sudo._get_next_page_or_question(answer_sudo, next_question.id, go_back=True).id
                    })
                else:
                    answer_sudo._mark_done()
                    return self._prepare_survey_finished_values(survey_sudo, answer_sudo)

        return data
    
    def _get_next_triggered_question(self, survey_sudo, answer_sudo, current_question):
        question = survey_sudo.question_and_page_ids.filtered(lambda a: a.sequence > current_question.sequence and not a.answer_id)[:1]
        if question:
            return question
        return None

    @http.route('/survey/<string:survey_token>/<string:answer_token>', type='http', auth='public', website=True)
    def survey_display_page(self, survey_token, answer_token, **post):
        access_data = self._get_access_data(survey_token, answer_token, ensure_token=True)
        if access_data['validity_code'] is not True:
            return self._redirect_with_error(access_data, access_data['validity_code'])
        answer_sudo = access_data['answer_sudo']
        # if answer_sudo.state != 'done' and answer_sudo.survey_time_limit_reached:
        #     answer_sudo._mark_done()
        return request.render('survey.survey_page_fill',
            self._prepare_survey_data(access_data['survey_sudo'], answer_sudo, **post))
