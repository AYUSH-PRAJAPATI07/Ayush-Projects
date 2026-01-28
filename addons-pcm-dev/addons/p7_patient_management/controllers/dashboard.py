from odoo import http,_,fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
import pytz
import logging

_logger = logging.getLogger(__name__)

class PatientDashboard(http.Controller):
    
    @http.route('/patient-dashboard', type='http', auth='user', website=True, csrf=True)
    def get_dashboard(self, **kw):
        user = request.env.user
        if user.sudo().partner_id.user_type != 'patient':
            raise AccessError("You do not have permission to access this page.Only patients allowed for this page.")
        
        values = request.params.copy()
        patient_cases = request.env['patient.case'].sudo().search([('patient_id','=',request.env.user.partner_id.id)],limit=1)
        main_case = request.env['patient.case'].sudo().search([('patient_id','=',request.env.user.partner_id.id)],limit=1)
        doc_support = 'normal'
        if patient_cases:
            if patient_cases[0].case_tier == 'premium':
                doc_support = 'premium'
        if request.httprequest.method == 'POST':
            if values.get('case-button',False):
                main_case = request.env['patient.case'].sudo().search([('id','=',int(values.get('case-button')))])
                if main_case:
                    return request.render('p7_patient_management.patient_dashboard_template', {'patient_cases':patient_cases, 'main':True, 'main_case':main_case, 'doc_support':doc_support,})
                
            if values.get('medical_history_edit',False):
                main_case = request.env['patient.case'].sudo().search([('id','=',int(values.get('medical_history_edit')))])
                if main_case:
                    if main_case.medic_answer_id and main_case.medic_state != 'draft':
                        main_case.medic_answer_id.sudo().write({'is_edit':True})
                        all_ques_ids = request.env['survey.question'].sudo().search([('repeat_survey_id', '=', main_case.medic_answer_id.survey_id.id),('repeat_answer_id', '=', main_case.medic_answer_id.id)])
                        all_page_ids = request.env['survey.question'].sudo().search([('survey_id', '=', main_case.medic_answer_id.survey_id.id),('is_page', '=', True)])
                        user_input_line_ids = main_case.medic_answer_id.user_input_line_ids.filtered(lambda line: line.user_input_id == main_case.medic_answer_id)
                        patient_case_id = request.env['patient.case'].sudo().search([('medic_answer_id', '=', main_case.medic_answer_id.id)],limit=1)
                        for page in all_page_ids:
                            page.more_ques_and_page_ids = [(5, 0, 0)]
                        for ques in all_ques_ids:
                            if ques.id in user_input_line_ids.mapped('question_id').ids:
                                ques.sudo().write({'page_id': ques.repeat_question_id.page_id.id if ques.repeat_question_id else ques.page_id.id,})
                                ques.page_id.sudo().write({'more_ques_and_page_ids': [(4, ques.id)]})
                        main_case.medic_answer_id.sudo().write({'state':'in_progress','last_displayed_page_id':0})
                        survey_url = "/survey/%s/%s" % (main_case.medic_answer_id.survey_id.access_token, main_case.medic_answer_id.access_token)
                        if patient_case_id:
                            patient_case_id.sudo().write({'medic_state':'in_progress', 'medic_survey_submit_date': False})
                        return request.redirect(survey_url)
                    elif main_case.medic_answer_id and main_case.medic_state == 'confirm':
                        survey_url = "/survey/%s/%s" % (main_case.medic_answer_id.survey_id.access_token, main_case.medic_answer_id.access_token)
                        return request.redirect(survey_url)
                    elif not main_case.medic_answer_id and main_case.medic_state == 'confirm':
                        survey_url = "/survey/start/%s" % (main_case.medic_survey_id.access_token)
                        return request.redirect(survey_url)
                    else:
                        return request.render('p7_patient_management.patient_dashboard_template', {'patient_cases':patient_cases, 'main':True, 'main_case':main_case, 'doc_support':doc_support,})
                    
            if values.get('medical_history',False):
                main_case = request.env['patient.case'].sudo().search([('id','=',int(values.get('medical_history')))])
                if main_case:
                    if main_case.medic_answer_id and main_case.medic_answer_id.state in ('done','review'):
                        review_url = "/survey/print/%s?answer_token=%s" % (main_case.medic_answer_id.survey_id.access_token, main_case.medic_answer_id.access_token)
                        return request.redirect(review_url)
            
            if values.get('inform_guide',False):
                main_case = request.env['patient.case'].sudo().search([('id','=',int(values.get('inform_guide')))])
                if main_case and main_case.guide_state != 'draft':
                    user_tz = pytz.timezone(user.tz or 'UTC')
                    local_op_date = pytz.utc.localize(main_case.op_date).astimezone(user_tz)
                    local_op_end_date = False
                    if main_case.op_end_date:
                        local_op_end_date = pytz.utc.localize(main_case.op_end_date).astimezone(user_tz)
                    formatted_op_date = f"{local_op_date.strftime('%d/%m/%Y %I:%M %p') if local_op_date else ''} - {local_op_end_date.strftime('%d/%m/%Y %I:%M %p') if local_op_end_date else ''}" 
                    values = {
                        'doctor': main_case.create_uid.partner_id,
                        'case': main_case,
                        'guide': main_case.case_guide_id if main_case.case_guide_id else False,
                        'formatted_op_date': formatted_op_date,
                        'doc_support': doc_support,
                    }
                    return request.render('p7_patient_management.patient_guide_template', values)
                else:
                    if main_case:
                        return request.render('p7_patient_management.patient_dashboard_template', {'patient_cases':patient_cases, 'main':True, 'main_case':main_case, 'doc_support':doc_support,})
            
            if values.get('feedback_edit',False):
                main_case = request.env['patient.case'].sudo().search([('id','=',int(values.get('feedback_edit')))])
                if main_case:
                    if main_case.feedback_answer_id and main_case.feedback_state != 'draft':
                        main_case.feedback_answer_id.sudo().write({'is_edit':True})
                        all_ques_ids = request.env['survey.question'].sudo().search([('repeat_survey_id', '=', main_case.feedback_answer_id.survey_id.id),('repeat_answer_id', '=', main_case.feedback_answer_id.id)])
                        all_page_ids = request.env['survey.question'].sudo().search([('survey_id', '=', main_case.feedback_answer_id.survey_id.id),('is_page', '=', True)])
                        user_input_line_ids = main_case.feedback_answer_id.user_input_line_ids.filtered(lambda line: line.user_input_id == main_case.feedback_answer_id)
                        patient_case_id = request.env['patient.case'].sudo().search([('feedback_answer_id', '=', main_case.feedback_answer_id.id)],limit=1)
                        for page in all_page_ids:
                            page.more_ques_and_page_ids = [(5, 0, 0)]
                        for ques in all_ques_ids:
                            if ques.id in user_input_line_ids.mapped('question_id').ids:
                                ques.sudo().write({'page_id': ques.repeat_question_id.page_id.id if ques.repeat_question_id else ques.page_id.id,})
                                ques.page_id.sudo().write({'more_ques_and_page_ids': [(4, ques.id)]})
                        main_case.feedback_answer_id.sudo().write({'state':'in_progress','last_displayed_page_id':0})
                        survey_url = "/survey/%s/%s" % (main_case.feedback_answer_id.survey_id.access_token, main_case.feedback_answer_id.access_token)
                        if patient_case_id:
                            patient_case_id.sudo().write({'feedback_state':'in_progress','feedback_survey_submit_date': False})
                        return request.redirect(survey_url)
                    elif main_case.feedback_answer_id and main_case.feedback_state == 'confirm':
                        survey_url = "/survey/%s/%s" % (main_case.feedback_answer_id.survey_id.access_token, main_case.feedback_answer_id.access_token)
                        return request.redirect(survey_url)
                    elif not main_case.feedback_answer_id and main_case.feedback_state == 'confirm':
                        survey_url = "/survey/start/%s" % (main_case.feedback_survey_id.access_token)
                        return request.redirect(survey_url)
                    else:
                        return request.render('p7_patient_management.patient_dashboard_template', {'patient_cases':patient_cases, 'main':True, 'main_case':main_case, 'doc_support':doc_support,})
            
            if values.get('feedback_form',False):
                main_case = request.env['patient.case'].sudo().search([('id','=',int(values.get('feedback_form')))])
                if main_case:
                    if main_case.feedback_answer_id and main_case.feedback_answer_id.state == 'done':
                        review_url = "/survey/print/%s?answer_token=%s" % (main_case.feedback_answer_id.survey_id.access_token, main_case.feedback_answer_id.access_token)
                        return request.redirect(review_url)
            
        return request.render('p7_patient_management.patient_dashboard_template', {'patient_cases':patient_cases, 'doc_support':doc_support,'main':True, 'main_case':main_case,})

    @http.route('/chat', type='http', auth='user', website=True, csrf=False)
    def chat(self, **kw):
        user = request.env.user
        partner = user.partner_id

        values = request.params.copy()
        target_type = values.get('target', 'doctor')  # Default to 'doctor' if not given
        doc_support = 'basic'  # Initialize doc_support
        
        # Check patient case tier
        patient_cases = request.env['patient.case'].sudo().search([
            ('patient_id', '=', partner.id)
        ], limit=1)
        
        if patient_cases and patient_cases.case_tier == 'premium':
            doc_support = 'premium'

        # Check user permissions
        if partner.user_type != 'patient':
            raise AccessError("You do not have permission to access this page. Only patients allowed for this page.")

        support_label = 'doctor'  # Default support label
        channel = False
        target_partner = False

        if target_type == 'tech':
            support_label = 'tech'
            
            # Find tech support user
            tech_user = request.env['res.users'].sudo().search([
                ('is_tech_support', '=', True)
            ], limit=1)
            
            if not tech_user:
                raise ValidationError("No tech support user found.")
                
            target_partner = tech_user.partner_id

        else:  # target_type == 'doctor'
            support_label = 'doctor'
            
            # Get the doctor who created the patient user
            if hasattr(user, 'create_uid') and user.create_uid:
                doctor_user = user.create_uid
                target_partner = doctor_user.partner_id
            else:
                # Fallback: find any doctor user
                doctor_user = request.env['res.users'].sudo().search([
                    ('groups_id', 'ilike', 'doctor')  # Adjust this condition based on your doctor group
                ], limit=1)
                
                if not doctor_user:
                    raise ValidationError("No doctor user found.")
                    
                target_partner = doctor_user.partner_id

        # Use the built-in channel_get method which handles chat channel creation properly
        if target_partner:
            try:
                # This method automatically finds or creates a chat channel between two partners
                channel = request.env['discuss.channel'].sudo().channel_get([partner.id, target_partner.id])
            except Exception as e:
                # Fallback method if channel_get fails
                # Search for existing channel manually
                existing_channels = request.env['discuss.channel'].sudo().search([
                    ('channel_type', '=', 'chat')
                ])
                
                for ch in existing_channels:
                    member_partner_ids = ch.channel_member_ids.mapped('partner_id.id')
                    if set([partner.id, target_partner.id]) == set(member_partner_ids) and len(member_partner_ids) == 2:
                        channel = ch
                        break
                
                # If still no channel found, create one with a different approach
                if not channel:
                    # Create channel first without members
                    channel = request.env['discuss.channel'].sudo().create({
                        'name': f"{partner.name}, {target_partner.name}",
                        'channel_type': 'chat',
                        'create_uid': user.id,
                    })
                    
                    # Then add members one by one to avoid the restriction
                    try:
                        # Method 1: Try with channel join
                        channel.sudo().add_members([partner.id, target_partner.id])
                    except:
                        try:
                            # Method 2: Create members directly with proper context
                            member_vals = [
                                {'channel_id': channel.id, 'partner_id': partner.id},
                                {'channel_id': channel.id, 'partner_id': target_partner.id},
                            ]
                            request.env['discuss.channel.member'].sudo().with_context(mail_create_nosubscribe=True).create(member_vals)
                        except:
                            # Method 3: Use the channel's internal method
                            channel.sudo().write({
                                'channel_member_ids': [
                                    (0, 0, {'partner_id': partner.id}),
                                    (0, 0, {'partner_id': target_partner.id}),
                                ]
                            })

        # Handle POST request (sending message)
        if request.httprequest.method == 'POST':
            message_body = values.get('message')
            if message_body and channel:
                try:
                    # Use the channel's message_post method for proper message creation
                    channel.sudo().message_post(
                        body=message_body,
                        author_id=partner.id,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment'
                    )
                except Exception as e:
                    # Fallback to direct message creation
                    request.env['mail.message'].sudo().create({
                        'res_id': channel.id,
                        'model': 'discuss.channel',
                        'message_type': 'comment',
                        'author_id': partner.id,
                        'body': message_body,
                    })

        # Get messages from the channel
        messages = False
        if channel:
            messages = request.env['mail.message'].sudo().search([
                ('res_id', '=', channel.id),
                ('model', '=', 'discuss.channel'),
                ('message_type', '=', 'comment')
            ], order="create_date asc")

        return request.render('p7_patient_management.patient_chat_template', {
            'patient': partner.id,
            'messages': messages,
            'support': support_label,
            'doc_support': doc_support,
            'channel': channel,
        })


    @http.route('/direct-chat', type='http', auth='user', website=True, csrf=False)
    def direct_chat(self, **kw):
        user = request.env.user.sudo()
        if user.sudo().partner_id.user_type != 'patient':
            raise AccessError("You do not have permission to access this page.Only patients allowed for this page.")
        
        values = request.params.copy()
        # partner_channel = request.env['discuss.channel'].sudo().search([('write_uid','=',user.id),('channel_type','=','chat'),('name','not ilike','OdooBot')],limit=1)
        # messages = request.env['mail.message'].sudo().search([('res_id', 'in', partner_channel.ids),('model','=','discuss.channel'),('message_type','=','comment')], order="id asc")
        # if request.httprequest.method == 'POST':
        #     request.env['mail.message'].sudo().create({
        #                 'res_id': partner_channel.sudo().id,
        #                 'model': 'discuss.channel',
        #                 'message_type': 'comment',
        #                 'author_id': user.sudo().partner_id.id,
        #                 'body': str(values.get('message'))
        #             })
        #     messages = request.env['mail.message'].sudo().search([('res_id','=',partner_channel.id),('model','=','discuss.channel'),('message_type','=','comment')], order="id asc")
        #     return request.render('p7_patient_management.patient_chat_template', {'patient': user.sudo().partner_id.id, 'messages': messages})
        return request.render('p7_patient_management.patient_message_template')