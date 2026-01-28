from odoo import http,_,fields
from odoo.http import request
from odoo.exceptions import AccessError
from datetime import datetime,timedelta
from twilio.rest import Client
import pytz
import logging
import re

_logger = logging.getLogger(__name__)

class PatientGuide(http.Controller):
    
    # def get_formated_date(self,record,case):
    #     user_tz = pytz.timezone(request.env.user.tz or 'UTC')
    #     local_op_date = pytz.utc.localize(case.op_date).astimezone(user_tz)
    #     formatted_time = local_op_date.strftime('%d/%m/%Y %I:%M %p')
    #     match = str(record.preparation_steps).split('@')
    #     formatted_prep = record.preparation_steps
    #     if '@' in str(record.preparation_steps):
    #         if 'operation_datetime' in match[1]:
    #             formatted_prep = f"{match[0]} {formatted_time}"
    #         fetch_number = re.findall("\d+", match[1])
    #         if 'hrs'in match[1] and fetch_number:
    #             hours_to_subtract = int(fetch_number[0])
    #             operation_time = local_op_date - timedelta(hours=hours_to_subtract)
    #             formatted_time = operation_time.strftime('%d/%m/%Y %I:%M %p')
    #             formatted_prep = f"{match[0]} {formatted_time}"
    #         if 'days'in match[1] and fetch_number:
    #             days_to_subtract = int(fetch_number[0])
    #             operation_time = local_op_date - timedelta(days=days_to_subtract)
    #             formatted_time = operation_time.strftime('%d/%m/%Y %I:%M %p')
    #             formatted_prep = f"{match[0]} {formatted_time}"
    #     return formatted_prep

    def get_formatted_date(self, record, case):
        user_tz = pytz.timezone(request.env.user.tz or 'UTC')
        local_op_date = pytz.utc.localize(case.op_date).astimezone(user_tz)
        prep_text = str(record.preparation_steps)
        pattern = r'@operation_datetime-(\d+)(hrs|days)'
        def replacer(match):
            number = int(match.group(1))
            unit = match.group(2)
            if unit == 'hrs':
                adjusted_time = local_op_date - timedelta(hours=number)
            elif unit == 'days':
                adjusted_time = local_op_date - timedelta(days=number)
            else:
                adjusted_time = local_op_date
            return adjusted_time.strftime('%d/%m/%Y %I:%M %p')
        formatted_prep = re.sub(pattern, replacer, prep_text)
        return formatted_prep
    
    @http.route('/patient-guide', type='http', auth='user', website=True, csrf=True)
    def get_guide(self, **kw):
        user = request.env.user
        if user.sudo().partner_id.user_type != 'patient':
            raise AccessError("You do not have permission to access this page.Only patients allowed for this page.")
        vals = request.params.copy()
        doctor = request.env['res.partner'].sudo().browse(int(vals.get('doctor_id')))
        case = request.env['patient.case'].sudo().browse(int(vals.get('pcid')))
        user_tz = pytz.timezone(user.tz or 'UTC')
        formatted_op_date = ''
        op_date = case.op_date
        if op_date:
            local_op_date = pytz.utc.localize(op_date).astimezone(user_tz)
            local_op_end_date = False
            if case.op_end_date:
                local_op_end_date = pytz.utc.localize(case.op_end_date).astimezone(user_tz)
            formatted_op_date = (
                f"{local_op_date.strftime('%d/%m/%Y %I:%M %p')} - "
                f"{local_op_end_date.strftime('%d/%m/%Y %I:%M %p') if local_op_end_date else ''}"
            )
        doc_support = 'normal'
        if case:
            if case.case_tier == 'premium':
                doc_support = 'premium'
        values = {
            'doctor': doctor,
            'case': case,
            'guide': case.case_guide_id if case.case_guide_id else False,
            'formatted_op_date': formatted_op_date,
            'doc_support': doc_support,
        }
        if request.httprequest.method == 'POST':
            if vals.get('submit',False) and case.guide_state == 'sent':
                anaesthesia_id = False
                if len(case.case_guide_id.anaesthesia_type_ids) > 1:
                    anaesthesia_id = request.env['anaesthesia.type'].sudo().browse(int(vals.get('anaesthesia_options')))
                if len(case.case_guide_id.anaesthesia_type_ids) == 1:
                    anaesthesia_id = request.env['anaesthesia.type'].sudo().browse(int(case.case_guide_id.anaesthesia_type_ids[0].id))
                if anaesthesia_id:
                    for record in anaesthesia_id.reminder_ids:
                        request.env['res.reminder.line'].sudo().create({
                                'name': record.name,
                                'reminder_hour': record.reminder_hour,
                                'preparation_steps': self.get_formatted_date(record,case) if "@operation_datetime" in record.preparation_steps else record.preparation_steps,
                                'patient_case_id': case.id,
                            })
                    request.env['anaesthesia.type.line'].sudo().create({
                            'name': anaesthesia_id.name,
                            'anaesthesia_id': anaesthesia_id.id,
                            'date_updated': fields.Datetime.now(),
                            'preparation_steps': anaesthesia_id.preparation_steps,
                            'explanation': anaesthesia_id.explanation,
                            'patient_case_id': case.id,
                        })
                patient_number = f"{request.env.user.sudo().partner_id.phone_code.name} {request.env.user.sudo().partner_id.mob}"
                base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
                url = f"{base_url}/patient-guide?doctor_id={doctor.id}&pcid={case.id}"
                patient_msg = (
                    f"Hi {request.env.user.sudo().partner_id.name} {request.env.user.sudo().partner_id.last_name},\n"
                    f"Thank you for completing the pre-operative information guide.\n"
                    f"Look forward to seeing you on {case.get_start_date()} for your {case.op_process}\n"
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
                        body=patient_msg,
                        from_=str(number),
                        to=patient_number
                    )
                    request.env['sms.sms'].sudo().create({
                            'partner_id': request.env.user.sudo().partner_id.id,
                            'number': patient_number,
                            'state': 'sent',
                            'body': patient_msg,
                            'is_custom_log': True,
                        })
                    _logger.info(f"SMS sent to doctor: {patient_number}")
                except Exception as e:
                    request.env['sms.sms'].sudo().create({
                            'partner_id': request.env.user.sudo().partner_id.id,
                            'number': patient_number,
                            'state': 'error',
                            'body': patient_msg,
                            'is_custom_log': True,
                        })
                    _logger.error("Failed to send SMS to doctor: %s", e)
                
                # send email
                #doctor
                if request.env.user.sudo().partner_id.email:
                    user = request.env.user
                    template_id = request.env.ref('p7_patient_management.guide_completion_template_patient').sudo()
                    ctx = {
                            'default_model': 'res.users',
                            'default_res_id': user.id,
                            'default_use_template': bool(template_id.id),
                            'default_template_id': template_id.id,
                            'default_composition_mode': 'comment',
                            'force_send': True,
                            'object': user,
                            'email_to': request.env.user.sudo().partner_id.email,
                        }
                    # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
                    email_body = f"""
                                <p style="margin: 0px; padding: 0px; font-size: 15px;"> Hi {user.partner_id.name}, <p>
                                <p style="margin: 0px; padding: 0px; font-size: 15px;"> Thank you for completing your  Pre-Anaesthetic Plan. </p>
                                <p>Best regards,<br/><strong>VANAESA</strong></p> """
                    try:
                        request.env['mail.mail'].sudo().create({
                            'auto_delete': True,
                            'email_to': request.env.user.sudo().partner_id.email,
                            'subject': "Anaesthetic Plan Completion",
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
                            'subject': "Anaesthetic Plan Completion",
                            'state': 'exception',
                            'author_id': user.partner_id.id,
                            'date': fields.Datetime.now(),
                            'is_custom_log':True,
                            'body_html':email_body
                        })
                        _logger.error("Failed to send mail: %s", e)
                case.sudo().write({'guide_state':'confirm'})
                return request.render('p7_patient_management.patient_guide_confirmation_page')
        return request.render('p7_patient_management.patient_guide_template', values)
    
    @http.route('/guide/preview/<int:record_id>', type='http', auth='user', website=True)
    def preview_guide(self, record_id, **kw):
        record = request.env['information.guide.case'].sudo().browse(record_id)
        if not record.exists():
            return request.not_found()
        
        user = request.env.user
        user_tz = pytz.timezone(user.tz or 'UTC')
        formatted_op_date = ''
        op_date = record.patient_case_id.op_date
        if op_date:
            local_op_date = pytz.utc.localize(op_date).astimezone(user_tz)
            local_op_end_date = False
            if record.patient_case_id.op_end_date:
                local_op_end_date = pytz.utc.localize(record.patient_case_id.op_end_date).astimezone(user_tz)
            formatted_op_date = (
                f"{local_op_date.strftime('%d/%m/%Y %I:%M %p')} - "
                f"{local_op_end_date.strftime('%d/%m/%Y %I:%M %p') if local_op_end_date else ''}"
            )
        values = {
            'doctor': record.guide_id.create_uid.partner_id,
            'case': record.patient_case_id,
            'guide': record,
            'formatted_op_date': formatted_op_date,
        }

        return request.render('p7_patient_management.template_guide_preview', values)
