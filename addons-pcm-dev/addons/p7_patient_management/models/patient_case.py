from odoo import models, fields, api, _
from odoo.exceptions import ValidationError,UserError
from twilio.rest import Client
from datetime import datetime,date,timedelta
from lxml.html import fromstring
import pytz
import random
import string
import logging
import base64
import re
from icalendar import Calendar, Event

_logger = logging.getLogger(__name__)
class PatientCase(models.Model):
    _name = 'patient.case'
    _description = 'Patient Case Details'
    _order = "op_date desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char("Booking ID",tracking=True, default=lambda self: _('New'),copy=False,)
    patient_id = fields.Many2one('res.partner', string='Patient', copy=False)
    patient_first_name = fields.Char('First Name')
    patient_last_name = fields.Char('Last Name')
    patient_mob = fields.Char("Mobile", copy=False)
    patient_nric_number = fields.Char("NRIC/FIN/Passport", tracking=True)
    patient_phone_code = fields.Many2one('res.phone_code', copy=False, default=lambda self: self.env['res.phone_code'].search([('name', '=', '+65')], limit=1))
    patient_gender = fields.Selection([('male', 'Male'), ('female', 'Female')], string="Sex")
    patient_dob = fields.Date("Date of Birth")
    state = fields.Selection(selection=[('pre-operation', 'Pre-operation'),('operation', 'Day of Operation'),('post-operation', 'Post-operation')],string='Status',required=True,readonly=True,default='pre-operation',tracking=True)
    medic_state = fields.Selection(selection=[('draft', 'Draft'),('confirm', 'Confirmed'),('in_progress', 'In Progress'),('submit', 'Submitted'),('review', 'Reviewed')],string='Medical History Collection Status',required=True,readonly=True,default='draft',tracking=True)
    feedback_state = fields.Selection(selection=[('draft', 'Draft'),('confirm', 'Confirmed'),('in_progress', 'In Progress'),('submit', 'Submitted'),('review', 'Reviewed')],string='Feedback Collection Status',required=True,readonly=True,default='draft',)
    op_process = fields.Char("Procedure (Abbreviated)")
    op_date = fields.Datetime("Date and Time")
    op_end_date = fields.Datetime("End Date & Time")
    op_duration_hrs = fields.Integer("Duration", default=1)
    op_duration_mins = fields.Integer("Duration Mins")
    medic_survey_start_date = fields.Date("Medical History Collection Start date")
    medic_survey_submit_date = fields.Date("Medical History Collection Submit date")
    survey_first_sms_date = fields.Date("Survey First SMS Date")
    survey_reminder_count = fields.Integer("Survey Reminder Count", default=0)
    guide_first_sms_date = fields.Date("Guide First SMS Date")
    guide_reminder_count = fields.Integer("Guide Reminder Count", default=0)
    feedback_survey_start_date = fields.Date("Feedback Collection Start date")
    feedback_survey_submit_date = fields.Date("Feedback Collection Submit date")
    comment = fields.Html("")
    op_location_id = fields.Many2one("res.location", string="Location", copy=False,)
    op_surgeon = fields.Char("Surgeon")
    medic_survey_id = fields.Many2one('survey.survey', string='Pre-Anaesthetic Questionnaire')
    feedback_survey_id = fields.Many2one('survey.survey', string='Post-Anaesthetic Feedback', domain=[('type_of_survey', '=', 'feedback')])
    inform_guide_id = fields.Many2one('information.guide', string='Anaesthetic Plan', tracking=True) 
    guide_state = fields.Selection(selection=[('draft', 'Draft'), ('sent', 'Sent'), ('confirm', 'Confirmed')],string='Information Guide Status',required=True,readonly=True,default='draft',tracking=True)
    medic_answer_id = fields.Many2one('survey.user_input', string='')
    feedback_answer_id = fields.Many2one('survey.user_input', string='')
    partner_id = fields.Many2one('res.partner', compute='_compute_partner_id')
    case_ids = fields.One2many('patient.case', 'id', string='Medical History Submissions')
    feedback_ids = fields.One2many('patient.case', 'id', string='Feedback Submissions')
    reminder_line_ids = fields.One2many('res.reminder.line', 'patient_case_id', string='Reminders')
    reminders_sent = fields.Boolean("Reminders Sent", default=False)
    anaesthesia_line_ids = fields.One2many('anaesthesia.type.line', 'patient_case_id', string='Anaesthesia Selected')
    location_id = fields.Many2one("res.dislocation", string="Disposition (Optional)", copy=False,
        compute="compute_location_id",
        inverse="inverse_location_id",
        store=True)
    case_tier = fields.Selection([('normal', 'Normal'),('premium', 'Premium')], string="Case Tier", default='normal')
    op_process_detail = fields.Text("Procedure Details")
    seq_number = fields.Integer("",default=0)
    case_backend_id = fields.Char(
        "Case ID",
        default="New",
        copy=False,
        required=True,
        readonly=True,
        groups="p7_patient_management.group_user_admin",
    )
    anaesthetist_id = fields.Many2one("res.users", string="Anaesthetist")
    case_guide_id = fields.Many2one("information.guide.case", string="Case Plan", copy=False)
    additional_info_ids = fields.Many2many("additional.information", string="Additional Information (Optional)", copy=False)
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
        string="Contact Channel",
    )
    video_call_date = fields.Date("Video Call Date")
    video_call_time = fields.Float("Video Call Time", widget="float_time")
    video_call_location = fields.Char("Patient's Physical Location")
    video_call_contents = fields.Text(
        "Contents",
        default="The patient was introduced to the purpose and functions of the Virtual Anaesthesia Assessment (VANAESA) platform.",
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
    attempt_count = fields.Integer(
        string="Attempt Count",
        related='medic_answer_id.attempt_count',
        store=True,
        readonly=True,
    )

    @api.depends("medic_answer_id", "medic_answer_id.location_id")
    def compute_location_id(self):
        for case in self:
            case.location_id = case.medic_answer_id.location_id

    def inverse_location_id(self):
        for case in self:
            case.medic_answer_id.location_id = case.location_id

    # def get_formatedd_date(self,record,case):
    #     user_tz = pytz.timezone(self.env.user.tz or 'UTC')
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

    def get_formated_date(self, record, case):
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
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

    @api.model
    def _assign_backend_ids_to_existing_cases(self):
        """Assign backend_case_id to existing patient cases without one."""
        cases = self.search([('case_backend_id', '=', 'New')])
        for case in cases:
            backend_seq = self.env['ir.sequence'].next_by_code('patient.case.backend')
            case.sudo().write({'case_backend_id': backend_seq})
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create patient cases.

        Populate ``case_backend_id`` using a dedicated sequence so the field
        remains admin only while still being filled automatically.
        """
        res = super().create(vals_list)
        for record in res:
            backend_seq = self.env['ir.sequence'].next_by_code('patient.case.backend')
            record.sudo().write({'case_backend_id': backend_seq})
            if record.name == _('New'):
                # record.name = self.env['ir.sequence'].next_by_code('patient.case')
                user = self.env.user
                year_suffix = str(date.today().year)[-2:]
                seq = self.env['patient.case'].sudo().search([('create_uid', '=', user.id),('id', '!=', record.id)], order='id desc', limit=1)
                seq_num = 1
                if seq:
                    seq_num = seq.seq_number + 1
                record.seq_number = seq_num
                record.name = f"PCID/{year_suffix}/{str(seq_num).zfill(4)}"
            if record.patient_mob:
                partner_id = self.env['res.partner'].sudo().search([('mob', '=', record.patient_mob)], limit=1)
                if partner_id:
                    partner_id.sudo().write({
                        'mob': record.patient_mob,
                        'phone_code': int(record.patient_phone_code),
                        'name': record.patient_first_name,
                        'last_name': record.patient_last_name,
                        'gender': record.patient_gender,
                        'dob': record.patient_dob,
                        'nric_number': record.patient_nric_number,
                    })
                    record.patient_id = partner_id

                    follower = self.env['mail.wizard.invite'].sudo().create({
                        'res_id': record.id,
                        'res_model': 'patient.case',
                        'notify': False,
                        'partner_ids': [(6, 0, [partner_id.id])],
                    })
                    follower.add_followers()
        return res
    
    def write(self, vals):
        if self.env.context.get('skip_update'):
            return super(PatientCase, self).write(vals)
        old_dates = {case.id: case.op_date for case in self}
        res = super(PatientCase, self).write(vals)
        partner_id = self.env['res.partner'].sudo().search([('mob', '=', self.patient_mob),], limit=1)
        if partner_id:
            # partner_id.sudo().write({
            #         'mob':self.patient_mob,
            #         'phone_code':self.patient_phone_code.id,
            #         'name':self.patient_first_name,
            #         'last_name':self.patient_last_name,
            #         'gender':self.patient_gender,
            #         'dob':self.patient_dob,
            #         'nric_number': self.patient_nric_number,
            #     })
            vals['patient_id'] = partner_id.id
        if vals.get('inform_guide_id'):
            self.reminder_line_ids.unlink()
            # default reminder creation
            user_tz = pytz.timezone(self.env.user.tz or 'UTC')
            if self.op_date:
                local_op_date = pytz.utc.localize(self.op_date).astimezone(user_tz)
                food_time = local_op_date - timedelta(hours=6)
                formatted_food_time = food_time.strftime('%d/%m/%Y %I:%M %p')
                water_time = local_op_date - timedelta(hours=2)
                formatted_water_time = water_time.strftime('%d/%m/%Y %I:%M %p')
                self.env['res.reminder.line'].sudo().create({
                        'name': 'Standard food water intake reminder',
                        'reminder_hour': 1,
                        'preparation_steps': (
                            f"Before {formatted_food_time}:\n"
                            f"- You may have a light meal. For example, plain bread or plain biscuits. Avoid meat, oily and fatty food.\n\n"
                            f"Between {formatted_food_time} and {formatted_water_time}:\n"
                            f"- You may have sips of plain water."
                        ),
                        'patient_case_id': self.id,
                    })
            self.env['res.reminder.line'].sudo().create({
                    'name': 'Standard URTI check reminder',
                    'reminder_hour': 3,
                    'preparation_steps': "Please inform your doctor if you are having any upper respiratory tract infection symptoms (runny nose, cough, sore throat, etc)",
                    'patient_case_id': self.id,
                })
            self.env['res.reminder.line'].sudo().create({
                'name': 'Fasting Reminder',
                'reminder_hour': 1,
                'preparation_steps': (
                    'This is a reminder to adhere to the fasting timings '
                    'ordered by your Anaesthetist. Undergoing surgery without '
                    'adequate fasting increases the risk of complications. '
                    'Your surgery may be delayed or even postponed.'
                ),
                'patient_case_id': self.id,
            })
            self.env['res.reminder.line'].sudo().create({
                'name': 'Medication Reminder',
                'reminder_hour': 1,
                'preparation_steps': (
                    'This is a reminder to adhere to the medication timings '
                    'ordered by your Anaesthetist.'
                ),
                'patient_case_id': self.id,
            })
            self.env['res.reminder.line'].sudo().create({
                'name': 'Wellness check-in',
                'reminder_hour': 5,
                'preparation_steps': (
                    'This is a wellness check-in from VANAESA. Having surgery '
                    'while unwell may increase your risk of complications. '
                    'Please inform your Surgeon and Anaesthetist if you are '
                    'unwell.'
                ),
                'patient_case_id': self.id,
            })
            if self.medic_state in ('submit','review'):
                medic_answers = self.medic_answer_id.user_input_line_ids.filtered(lambda line: line.question_id.medic_details).mapped('value_char_box')
                reminders = self.env['res.reminder'].sudo().search([('user_id','=',self.create_uid.id)])
                for reminder in reminders:
                    for answer in medic_answers:
                        if '[' in answer:
                            answer = answer.split('[')[1].strip(']')
                        # match = re.search(r'\[(.*?)\]', answer)
                        if reminder.medication_id or reminder.medication_class_id:
                            if reminder.medication_id:
                                if answer.upper() in reminder.medication_id.name.upper():
                                    self.env['res.reminder.line'].sudo().create({
                                            'name': reminder.name,
                                            'reminder_hour': reminder.reminder_hour,
                                            'preparation_steps': self.get_formated_date(reminder,self) if "@operation_datetime" in reminder.preparation_steps else reminder.preparation_steps,
                                            'patient_case_id': self.id,
                                            'reminder_id':reminder.id,
                                        })
                                else:
                                    med_id = self.env['res.medication'].sudo().search([('name','=',answer)],limit=1)
                                    if med_id and med_id.pharma_name and reminder.medication_id.pharma_name:
                                        if med_id.pharma_name.upper() in reminder.medication_id.pharma_name.upper():
                                            self.env['res.reminder.line'].sudo().create({
                                                'name': reminder.name,
                                                'reminder_hour': reminder.reminder_hour,
                                                'preparation_steps': self.get_formated_date(reminder,self) if "@operation_datetime" in reminder.preparation_steps else reminder.preparation_steps,
                                                'patient_case_id': self.id,
                                                'reminder_id':reminder.id,
                                            })
                            if reminder.medication_class_id:
                                reminder_ids = self.env['res.reminder.line'].sudo().search([('patient_case_id','=',self.id),('reminder_id','=',reminder.id)])
                                if not reminder_ids:
                                    if answer.upper() in reminder.medication_class_id.name.upper():
                                        self.env['res.reminder.line'].sudo().create({
                                                'name': reminder.name,
                                                'reminder_hour': reminder.reminder_hour,
                                                'preparation_steps': self.get_formated_date(reminder,self) if "@operation_datetime" in reminder.preparation_steps else reminder.preparation_steps,
                                                'patient_case_id': self.id,
                                                'reminder_id':reminder.id,
                                            })
                                    else:
                                        med_id = self.env['res.medication'].sudo().search([('name','=',answer)],limit=1)
                                        if med_id and med_id.pharma_name and reminder.medication_class_id.pharma_name:
                                            if med_id.pharma_name.upper() in reminder.medication_class_id.pharma_name.upper():
                                                self.env['res.reminder.line'].sudo().create({
                                                    'name': reminder.name,
                                                    'reminder_hour': reminder.reminder_hour,
                                                    'preparation_steps': self.get_formated_date(reminder,self) if "@operation_datetime" in reminder.preparation_steps else reminder.preparation_steps,
                                                    'patient_case_id': self.id,
                                                    'reminder_id':reminder.id,
                                                })
        if 'associate_id' in vals and vals['associate_id'] and self.env.user.has_group('p7_patient_management.group_user_admin'):
            for rec in self:
                rec.video_call_assign_status = 'assigned'
                associate = rec.associate_id
                if associate and associate.email:
                    self.env['mail.mail'].sudo().create({
                        'auto_delete': False,
                        'email_to': associate.email,
                        'subject': _('Video call assignment'),
                        'body_html': f"<p>You have been assigned to case {rec.name}.</p>",
                    }).send()
                rec.message_post(body=_('Associate %s assigned by admin') % associate.name)

        if 'op_date' in vals:
            now = fields.Datetime.now()
            for case in self:
                new_date = case.op_date
                old_date = old_dates.get(case.id)
                if new_date and new_date > now:
                    case.with_context(skip_update=True).write({'state': 'pre-operation'})
                if old_date and new_date and new_date > old_date and case.reminders_sent:
                    case.message_post(body=_('Please ignore all previous medication and fasting reminders.'))
                    case.reminder_line_ids.unlink()
                    case.with_context(skip_update=True).write({'reminders_sent': False})
        if "additional_info_ids" in vals and not self.env.context.get("skip_addition_info_update"):
            self.medic_answer_id.with_context(skip_addition_info_update=True).additional_info_ids = [(6, 0, self.additional_info_ids.ids)]
            self.case_guide_id.with_context(skip_addition_info_update=True).additional_info_ids = [(6, 0, self.additional_info_ids.ids)]
        return res

    def _compute_partner_id(self):
        for rec in self:
            if not rec.sudo().partner_id:
                rec.sudo().partner_id = rec.sudo().create_uid.partner_id.id
                
    def get_date(self):
        if self.op_date:
            user_tz = pytz.timezone(self.env.user.tz or 'UTC')
            local_op_date = pytz.utc.localize(self.op_date).astimezone(user_tz)
            return f"{local_op_date.strftime('%d %B %Y')}"
        return ''
    
    def get_start_date(self):
        if self.op_date:
            user_tz = pytz.timezone(self.env.user.tz or 'UTC')
            local_op_date = pytz.utc.localize(self.op_date).astimezone(user_tz)
            return f"{local_op_date.strftime('%d %B %Y %I:%M %p')}"
        return ''
    
    def get_end_date(self):
        if self.op_end_date:
            user_tz = pytz.timezone(self.env.user.tz or 'UTC')
            local_op_end_date = pytz.utc.localize(self.op_end_date).astimezone(user_tz)
            return f"{local_op_end_date.strftime('%d %B %Y %I:%M %p')}"
        return ''
    
    def action_whatsapp_call(self):
        url = f"https://wa.me/{self.patient_phone_code.name.lstrip('+')}{self.patient_mob}?video=true"
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': url
        }

    def action_whatsapp_message(self):
        url = f"https://wa.me/{self.patient_phone_code.name.lstrip('+')}{self.patient_mob}"
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': url
        }
    
    def action_calender(self):
        _logger.info('------------------------Calendar Job-----------------------')
        
    def initiate_premium(self):
        if self.case_tier == 'normal':
            self.write({'case_tier':'premium'})
        else:
            self.write({'case_tier':'normal'})

    def action_request_associate(self):
        """Request or assign an associate for the video call."""
        for record in self:
            record.video_call_performed_by = 'associate'
            admin_group = self.env.ref(
                'p7_patient_management.group_user_admin',
                raise_if_not_found=False,
            )

            if record.associate_id:
                record.video_call_assign_status = 'assigned'

                if record.associate_id.email:
                    self.env['mail.mail'].sudo().create({
                        'auto_delete': False,
                        'email_to': record.associate_id.email,
                        'subject': _('Video call assigned'),
                        'body_html': f"<p>You have been assigned to case {record.name}.</p>",
                    }).send()

                if admin_group:
                    for admin in admin_group.users.filtered(lambda u: u.email):
                        self.env['mail.mail'].sudo().create({
                            'auto_delete': False,
                            'email_to': admin.email,
                            'subject': _('Associate assigned'),
                            'body_html': f"<p>Associate {record.associate_id.name} has been assigned to case {record.name}.</p>",
                        }).send()
                record.message_post(
                    body=_('Doctor assigned video call to associate %s')
                         % record.associate_id.name
                )
            else:
                record.video_call_assign_status = 'to_assign'
                if admin_group:
                    for admin in admin_group.users.filtered(lambda u: u.email):
                        self.env['mail.mail'].sudo().create({
                            'auto_delete': False,
                            'email_to': admin.email,
                            'subject': _('Associate assistance requested'),
                            'body_html': f"<p>Doctor has requested associate assistance for case {record.name}.</p>",
                        }).send()
                record.message_post(body=_('Doctor requested associate assistance'))

    def action_take_video_call(self):
        for record in self:
            record.associate_id = self.env.user
            record.video_call_performed_by = 'associate'
            record.video_call_assign_status = 'assigned'
            record.video_call_status = 'in_progress'
            admin_group = self.env.ref('p7_patient_management.group_user_admin', raise_if_not_found=False)
            recipients = admin_group.users if admin_group else self.env['res.users']
            if record.anaesthetist_id:
                recipients |= record.anaesthetist_id
            else:
                recipients |= record.create_uid
            for user in recipients.filtered(lambda u: u.email):
                self.env['mail.mail'].sudo().create({
                    'auto_delete': False,
                    'email_to': user.email,
                    'subject': _('Associate took case'),
                    'body_html': f"<p>Associate {self.env.user.name} took case {record.name}.</p>",
                }).send()
            record.message_post(body=_('Associate %s took the case') % self.env.user.name)

    def action_video_call_complete(self):
        for record in self:
            if not record.video_call_outcome:
                raise UserError(_("Please select the outcome of the video call before completing it."))
            date_str = (
                record.video_call_date.strftime('%d/%m/%Y')
                if record.video_call_date
                else ''
            )
            hours = int(record.video_call_time or 0)
            minutes = int(round(((record.video_call_time or 0) - hours) * 60))
            time_str = f"{hours:02d}:{minutes:02d}hrs"
            channel_label = dict(self._fields['contact_channel'].selection).get(
                record.contact_channel, 'contact'
            )
            associate = (
                record.associate_id.name
                if record.video_call_performed_by == 'associate' and record.associate_id
                else self.env.user.name
            )
            body = (
                f"On {date_str} at {time_str}, a {channel_label} was made between the patient and {associate}. "
                f"The patient's location was established to be {record.video_call_location}. "
                f"{record.video_call_contents}"
            )
            record.message_post(body=body)
            if record.video_call_outcome == 'successful':
                record.video_call_status = 'success'
            else:
                record.video_call_fail_count += 1
                if record.video_call_fail_count >= 3:
                    record.video_call_status = 'failed'
                    record.video_call_outcome = 'failed'
                    admin_group = self.env.ref(
                        'p7_patient_management.group_user_admin', raise_if_not_found=False
                    )
                    if admin_group:
                        for admin in admin_group.users.filtered(lambda u: u.email):
                            self.env['mail.mail'].sudo().create({
                                'auto_delete': False,
                                'email_to': admin.email,
                                'subject': f"Video call failed for {record.name}",
                                'body_html': f"<p>Video call failed 3 times for case {record.name}.</p>",
                        }).send()
                else:
                    record.video_call_status = 'assigned'
                    record.update({
                        'video_call_date': False,
                        'video_call_time': 0,
                        'video_call_location': False,
                        'video_call_status': 'in_progress',
                        'video_call_contents': "The patient was introduced to the purpose and functions of the Virtual Anaesthesia Assessment (VANAESA) platform.",
                        'video_call_outcome': False,
                    })

    def action_mark_video_success(self):
        """Mark the video call as successful."""
        for record in self:
            record.update({
                'video_call_status': 'success',
                'video_call_outcome': 'successful',
            })

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

    def action_release_video_call(self):
        for record in self:
            if record.associate_id != self.env.user:
                continue
            record.associate_id = False
            record.video_call_assign_status = 'to_assign'
            record.video_call_status = 'pending'
            record.message_post(body=_('Associate %s released the case') % self.env.user.name)

    def get_google_calendar_url(self):
        user_tz = self.env.user.tz or 'UTC'
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        utc_time = self.op_date.replace(tzinfo=pytz.timezone('UTC'))
        local_time = utc_time.astimezone(pytz.timezone(user_tz))
        start_datetime = local_time.strftime('%Y%m%dT%H%M%S')
        end_datetime = (local_time + timedelta(hours=1)).strftime('%Y%m%dT%H%M%S')
        if self.op_end_date:
            utc_end_time = self.op_end_date.replace(tzinfo=pytz.timezone('UTC'))
            local_end_time = utc_end_time.astimezone(pytz.timezone(user_tz))
            end_datetime = local_end_time.strftime('%Y%m%dT%H%M%S')
        location = self.op_location_id.name
        record_id = self.id
        base_odoo_url = f"{base_url}"
        if self.env.user.partner_id.user_type != 'patient':
            base_odoo_url = f"{base_url}/web%23id%3D{record_id}%26model%3Dpatient.case%26view_type%3Dform"
        details = f"{base_odoo_url}%0AProcedure: {self.op_process if self.op_process else ''}%0ASurgeon: {self.op_surgeon if self.op_surgeon else ''}"
        google_calendar_url = (
            f"https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={self.op_process}%20-%20Dr%20{self.op_surgeon}"
            f"&dates={start_datetime}/{end_datetime}"
            f"&location={location}"
            f"&details={details}"
        )
        if self.env.user.partner_id.user_type == 'patient':
            return google_calendar_url
        return {
            'type': 'ir.actions.act_url',
            'url': google_calendar_url,
            'target': 'new'
        }
        
    def get_outlook_calendar_url(self):
        user_tz = self.env.user.tz or 'UTC'
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        utc_time = self.op_date.replace(tzinfo=pytz.timezone('UTC'))
        local_time = utc_time.astimezone(pytz.timezone(user_tz))
        start_datetime = local_time.strftime('%Y-%m-%dT%H:%M:%S')
        end_datetime = (local_time + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S')
        if self.op_end_date:
            utc_end_time = self.op_end_date.replace(tzinfo=pytz.timezone('UTC'))
            local_end_time = utc_end_time.astimezone(pytz.timezone(user_tz))
            end_datetime = local_end_time.strftime('%Y-%m-%dT%H:%M:%S')
        location = self.op_location_id.name
        record_id = self.id
        base_odoo_url = f"{base_url}"
        if self.env.user.partner_id.user_type != 'patient':
            base_odoo_url = f"{base_url}/web%23id%3D{record_id}%26model%3Dpatient.case%26view_type%3Dform"
        details = f"{base_odoo_url}%0AProcedure: {self.op_process if self.op_process else ''}%0ASurgeon: {self.op_surgeon if self.op_surgeon else ''}"
        outlook_calendar_url = (
            f"https://outlook.office365.com/calendar/0/deeplink/compose?"
            f"subject={self.op_process}%20-%20Dr%20{self.op_surgeon}"
            f"&startdt={start_datetime}"
            f"&enddt={end_datetime}"
            f"&location={location}"
            f"&body={details}"
            f"&allday=false"
        )
        if self.env.user.partner_id.user_type == 'patient':
            return outlook_calendar_url
        return {
            'type': 'ir.actions.act_url',
            'url': outlook_calendar_url,
            'target': 'new'
        }
        
    def get_ics_calendar_url(self):
        user_tz = self.env.user.tz or 'UTC'
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        local_tz = pytz.timezone(user_tz)
        start_dt_utc = self.op_date.replace(tzinfo=pytz.utc)
        end_dt_utc = (self.op_end_date or (self.op_date + timedelta(hours=1))).replace(tzinfo=pytz.utc)
        start_dt = start_dt_utc.astimezone(local_tz)
        end_dt = end_dt_utc.astimezone(local_tz)
        # start_dt = self.op_date
        # end_dt = start_dt + timedelta(hours=1)
        # if self.op_end_date:
        #     end_dt = self.op_end_date
        location = self.op_location_id.name or "No location specified"
        record_id = self.id
        description = f"{base_url}/web#id={record_id}&model=patient.case&view_type=form\nProcedure: {self.op_process if self.op_process else ''}\nSurgeon: {self.op_surgeon if self.op_surgeon else ''}"

        cal = Calendar()
        event = Event()
        event.add('summary', f"{self.op_process} - Dr {self.op_surgeon}")
        event.add('dtstart', start_dt)
        event.add('dtend', end_dt)
        event.add('location', location)
        event.add('description', description)
        event['uid'] = f"operation-{record_id}@yourcompany.com"

        cal.add_component(event)

        # Convert the calendar to iCal format and encode to base64
        ics_content = cal.to_ical()
        ics_encoded = base64.b64encode(ics_content).decode('utf-8')

        attachment = self.env['ir.attachment'].create({
            'name': f'Operation_{record_id}.ics',
            'datas': ics_encoded,  # Use Base64 encoding
            'mimetype': 'text/calendar',
            'res_model': self._name,
            'res_id': self.id,
        })

        ics_url = f'/web/content/{attachment.id}?download=true'
        if self.env.user.partner_id.user_type == 'patient':
            return ics_url
        return {
            'type': 'ir.actions.act_url',
            'url': ics_url,
            'target': 'self',
        }
        
    @api.model
    def _cron_patient_case_state_update(self):
        case_ids = self.env['patient.case'].sudo().search([('state', 'in' , ['pre-operation','operation'])])
        # now = fields.Datetime.now()
        # today = now.date()
        utc_now = fields.Datetime.now()
        sg_timezone = pytz.timezone('Asia/Singapore')
        sgt_now = utc_now.astimezone(sg_timezone)
        today_sgt = sgt_now.date()
        for case_id in case_ids:
            state = 'pre-operation'
            if case_id.op_date:
                # op_date = case_id.op_date.date()
                # if op_date < today:
                #     state = 'post-operation'
                # elif op_date == today:
                #     state = 'operation'
                op_date_sgt = case_id.op_date.astimezone(sg_timezone).date()
                if op_date_sgt < today_sgt:
                    state = 'post-operation'
                elif op_date_sgt == today_sgt:
                    state = 'operation'
            case_id.sudo().write({'state': state})
        # _logger.info("---------------Patient Case Update-------------------Last updated date:. And total records fetched: %s",len(case_ids))
        # #next call update
        # cron_id = self.env.ref('p7_patient_management.ir_cron_patient_case_update_state', raise_if_not_found=False)
        # if cron_id:
        #     utc_now = fields.Datetime.now()
        #     sg_timezone = pytz.timezone('Asia/Singapore')
        #     sgt_now = utc_now.astimezone(sg_timezone)
        #     _logger.info("UTC Now: %s -----|-------- SGT Now: %s", utc_now, sgt_now)
        #     if 3 <= sgt_now.hour < 21:
        #         next_call = utc_now + timedelta(hours=1)
        #     else:
        #         if sgt_now.hour >= 21:
        #             next_sgt_date = sgt_now.date() + timedelta(days=1)
        #         else:
        #             next_sgt_date = sgt_now.date()
        #         next_call_sgt = datetime.combine(next_sgt_date, datetime.strptime('03:00:00', '%H:%M:%S').time())
        #         next_call_utc = sg_timezone.localize(next_call_sgt).astimezone(pytz.utc)
        #         next_call = next_call_utc
        #     cron_id.sudo().write({'nextcall': next_call.strftime('%Y-%m-%d %H:%M:%S')})
        #     _logger.info('Cron nextcall updated to: %s (UTC)-------------------------------------------------------', next_call)
    
    @api.model
    def update_patient_reminder(self):
        case_ids = self.env['patient.case'].sudo().search([('state', 'in' , ['pre-operation','operation']),('guide_state', '=' , 'confirm')])
        param_obj = self.env['ir.config_parameter'].sudo()
        sid = param_obj.get_param('twilio_sid')
        token = param_obj.get_param('twilio_token')
        number = param_obj.get_param('twilio_number')
        client = Client(str(sid), str(token))
        today_date = datetime.today().date()
        for case_id in case_ids:
            patient_number = f"{case_id.patient_id.phone_code.name} {case_id.patient_id.mob}"
            for reminder in case_id.reminder_line_ids:
                reminder_date = case_id.op_date - timedelta(days=reminder.reminder_hour if reminder.reminder_hour else 0)
                if reminder_date.date() == today_date:
                    tree = fromstring(reminder.preparation_steps)
                    filtered_msg = tree.text_content().strip()
                    msg = (
                            f"{case_id.patient_id.name} {case_id.patient_id.last_name}\n"
                            f"{str(filtered_msg)}\n"
                        )
                    body_msg = (
                            f"{str(filtered_msg)}\n"
                        )
                    try:
                        client.messages.create(
                            body=f"{str(filtered_msg)}",
                            from_=str(number),
                            to=patient_number
                        )
                        self.env['sms.sms'].sudo().create({
                                'partner_id': case_id.patient_id.id,
                                'number': patient_number,
                                'state': 'sent',
                                'body': msg,
                                'is_custom_log': True,
                            })
                    except Exception as e:
                        self.env['sms.sms'].sudo().create({
                                'partner_id': case_id.patient_id.id,
                                'number': patient_number,
                                'state': 'error',
                                'body': msg,
                                'is_custom_log': True,
                            })
                        _logger.error("Failed to send sms: %s", e)
                    if case_id.patient_id.email:
                        user = self.env['res.users'].sudo().search([('partner_id', '=' , case_id.patient_id.id)])
                        template_id = self.env.ref('p7_patient_management.patient_reminder_template').sudo()
                        ctx = {
                                'default_model': 'res.users',
                                'default_res_id': user.id,
                                'default_use_template': bool(template_id.id),
                                'default_template_id': template_id.id,
                                'default_composition_mode': 'comment',
                                'force_send': True,
                                'object': user,
                                'msg': body_msg,
                                'email_to': case_id.patient_id.email,
                            }
                        # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
                        try:
                            self.env['mail.mail'].sudo().create({
                                'auto_delete': True,
                                'email_to': case_id.patient_id.email,
                                'subject': "An Important Reminder from VANAESA",
                                'state': 'sent',
                                'author_id': user.partner_id.id,
                                'date': fields.Datetime.now(),
                                'is_custom_log':True,
                                'body_html':f"<p>Hello {case_id.patient_id.name},</p><p>{body_msg}</p><p>Best regards,<br/><strong>VANAESA</strong></p>"
                            })
                            template_id.sudo().with_context(ctx).send_mail(user.id, force_send=True)
                        except Exception as e:
                            self.env['mail.mail'].sudo().create({
                                'auto_delete': True,
                                'email_to': case_id.patient_id.email,
                                'subject': "An Important Reminder from VANAESA",
                                'state': 'exception',
                                'author_id': user.partner_id.id,
                                'date': fields.Datetime.now(),
                                'is_custom_log':True,
                                'body_html':f"<p>Hello {case_id.patient_id.name},</p><p>{body_msg}</p><p>Best regards,<br/><strong>VANAESA</strong></p>"
                            })
                            _logger.error("Failed to send mail: %s", e)
                    case_id.with_context(skip_update=True).write({'reminders_sent': True})
        _logger.info('---------------------log------reminder-------------------------')

    @api.model
    def cron_send_survey_reminders(self):
        sg_tz = pytz.timezone('Asia/Singapore')
        now_utc = fields.Datetime.now()
        now_sg = now_utc.astimezone(sg_tz)
        if now_sg.hour != 12:
            return

        cases = self.env['patient.case'].sudo().search([
            ('medic_state', 'in', ['confirm', 'in_progress']),
            ('medic_survey_submit_date', '=', False),
            ('survey_first_sms_date', '!=', False),
            ('survey_reminder_count', '<', 5),
        ])

        for case in cases:
            op_date_sg = False
            if case.op_date:
                op_date_sg = case.op_date.astimezone(sg_tz).date()
            if op_date_sg and op_date_sg <= now_sg.date():
                continue

            days_since_first = (now_sg.date() - case.survey_first_sms_date).days
            if days_since_first <= case.survey_reminder_count:
                continue

            case.survey_collection_msg()
            case.send_survey_reminder_email()
            case.sudo().write({'survey_reminder_count': case.survey_reminder_count + 1})

    def cron_send_guide_reminders(self):
        """Send daily guide reminders at noon."""
        sg_tz = pytz.timezone('Asia/Singapore')
        now_utc = fields.Datetime.now()
        now_sg = now_utc.astimezone(sg_tz)
        if now_sg.hour != 12:
            return

        cases = self.env['patient.case'].sudo().search([
            ('guide_state', '=', 'sent'),
            ('guide_first_sms_date', '!=', False),
            ('guide_reminder_count', '<', 5),
        ])

        for case in cases:
            op_date_sg = False
            if case.op_date:
                op_date_sg = case.op_date.astimezone(sg_tz).date()
            if op_date_sg and op_date_sg <= now_sg.date():
                continue

            days_since_first = (now_sg.date() - case.guide_first_sms_date).days
            if days_since_first <= case.guide_reminder_count:
                continue

            case.send_msg()
            case.send_guide_reminder_email()
            case.sudo().write({'guide_reminder_count': case.guide_reminder_count + 1})

    def send_survey_reminder_email(self):
        if self.patient_id.email:
            user = self.env['res.users'].search([('partner_id', '=', self.patient_id.id)], limit=1)
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/survey/start/{self.medic_survey_id.access_token}?uniq_id={self.patient_id.unique_id}&pcid={self.id}"
            template_id = self.env.ref('p7_patient_management.survey_collection_reminder_email_template').sudo()
            ctx = {
                'default_model': 'res.users',
                'default_res_id': user.id,
                'default_use_template': bool(template_id.id),
                'default_template_id': template_id.id,
                'default_composition_mode': 'comment',
                'force_send': True,
                'object': user,
                'surgeon': self.op_surgeon,
                'url': url,
                'email_to': self.patient_id.email,
            }
            try:
                template_id.with_context(ctx).send_mail(user.id, force_send=True)
                return True
            except Exception as e:
                _logger.error("Failed to send reminder email: %s", e)
                return False

    def send_guide_reminder_email(self):
        """Send email reminder about the information guide."""
        if self.patient_id.email:
            user = self.env['res.users'].search([('partner_id', '=', self.patient_id.id)], limit=1)
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/patient-guide?doctor_id={self.env.user.partner_id.id}&pcid={self.id}"
            template_id = self.env.ref('p7_patient_management.guide_email_template').sudo()
            ctx = {
                'default_model': 'res.users',
                'default_res_id': user.id,
                'default_use_template': bool(template_id.id),
                'default_template_id': template_id.id,
                'default_composition_mode': 'comment',
                'force_send': True,
                'object': user,
                'url': url,
                'email_to': self.patient_id.email,
            }
            try:
                template_id.with_context(ctx).send_mail(user.id, force_send=True)
                return True
            except Exception as e:
                _logger.error("Failed to send guide reminder email: %s", e)
                return False

    @api.onchange('patient_first_name')
    def _onchange_patient_first_name(self):
        if self.patient_id and self.patient_first_name:
            self.patient_id.sudo().write({'name' : self.patient_first_name})
            
    @api.onchange('patient_last_name')
    def _onchange_patient_last_name(self):
        if self.patient_id and self.patient_last_name:
            self.patient_id.sudo().write({'last_name' : self.patient_last_name})
    
    @api.onchange('patient_phone_code')
    def _onchange_patient_phone_code(self):
        if self.patient_id and self.patient_phone_code:
            self.patient_id.sudo().write({'phone_code' : self.patient_phone_code })
            
    @api.onchange('patient_gender')
    def _onchange_patient_gender(self):
        if self.patient_id and self.patient_gender:
            self.patient_id.sudo().write({'gender' : self.patient_gender })
            
    @api.onchange('patient_nric_number')
    def _onchange_patient_nric_number(self):
        if self.patient_id and self.patient_nric_number:
            self.patient_id.sudo().write({'nric_number' : self.patient_nric_number })
    
    @api.onchange('patient_dob')
    def _onchange_patient_dob(self):
        if self.patient_id and self.patient_dob:
            self.patient_id.sudo().write({'dob' : self.patient_dob })
            
    @api.onchange('patient_mob')
    def _onchange_patinet_mob(self):
        if self.patient_id and self.patient_mob: 
            self.patient_id.sudo().write({'mob' : self.patient_mob })
        if self.patient_mob:
            partner = self.env['res.partner'].sudo().search([('mob', '=', self.patient_mob),], limit=1)
            if partner and partner.create_uid.id != self.env.uid:
                raise ValidationError("This number is already associated with a patient who is not under your care!")
            if partner:
                self.patient_first_name = partner.name
                self.patient_last_name = partner.last_name
                self.patient_phone_code = partner.phone_code
                self.patient_gender = partner.gender
                self.patient_dob = partner.dob
                self.patient_nric_number = partner.nric_number
                
    @api.onchange('op_date', 'op_duration_hrs', 'op_duration_mins')
    def _onchange_op_date(self):
        if self.op_date:
            self.op_end_date = self.op_date + timedelta(hours=1)
            if self.op_duration_hrs <= 0:
                raise ValidationError("Operation hours should be positive!")
            if self.op_duration_mins < 0:
                raise ValidationError("Operation minutes should be positive!")
            self.op_end_date = self.op_date + timedelta(hours=self.op_duration_hrs)
            if self.op_duration_mins > 0:
                self.op_end_date = self.op_end_date + timedelta(minutes=self.op_duration_mins)
            if self.reminders_sent:
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _(
                            'Warning: Some reminders have already been sent. Changing the op date/time will trigger a message to the patient to ignore all reminders, and will deactivate all future reminders. Please contact the patient through VANAESA Chat for updated fasting and medication reminders. Please confirm'
                        ),
                    }
                }
            if self.reminder_line_ids:
                return {
                        'warning': {
                        'title': _('Warning'),
                        'message': _(
                            'Warning: You are changing the op date and time. Existing reminders will need to be manually updated to reflect the changes. Please confirm'
                        ),
                    }
                }
                
    def survey_collection_msg(self):
        patient_number = f"{self.patient_id.phone_code.name} {self.patient_id.mob}"
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        local_op_date = pytz.utc.localize(self.op_date).astimezone(user_tz)
        url = f"{base_url}/survey/start/{self.medic_survey_id.access_token}?uniq_id={self.patient_id.unique_id}&pcid={self.id}"
        msg = (
            f"Hi {self.patient_id.name}, for your surgery on {local_op_date.strftime('%d/%m/%Y')} with Dr {self.op_surgeon}, please fill in your pre-anaesthetic questionnaire:\n"
            f"{url}\n"
            f"See vanaesa.com for more info.\n"
        )
        try:
            param_obj = self.env['ir.config_parameter'].sudo()
            sid = param_obj.get_param('twilio_sid')
            token = param_obj.get_param('twilio_token')
            number = param_obj.get_param('twilio_number')
            client = Client(str(sid), str(token))
            client.messages.create(
                body=msg,
                from_=str(number),
                to=patient_number
            )
            self.env['sms.sms'].sudo().create({
                    'partner_id': self.patient_id.id,
                    'number': patient_number,
                    'state': 'sent',
                    'body': msg,
                    'is_custom_log': True,
                })
            return True
        except Exception as e:
            self.env['sms.sms'].sudo().create({
                    'partner_id': self.patient_id.id,
                    'number': patient_number,
                    'state': 'error',
                    'body': msg,
                    'is_custom_log': True,
                })
            _logger.error("Failed to send sms: %s", e)
            return False
        
    def action_answer_form(self):
        self.ensure_one()
        if not self.medic_answer_id:
            raise UserError("No survey record linked to this operation.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Survey Answer Form',
            'res_model': 'survey.user_input',
            'res_id': self.medic_answer_id.id,
            'context': {
                'default_case_id': self.id,
            },
            'view_mode': 'form',
            'view_id': False,
            'target': 'current',
        }
        
    def action_case_guide(self):
        self.ensure_one()
        if not self.case_guide_id:
            raise UserError("No plan is sent to this patient till now!")
    
        if self.case_guide_id and self.case_guide_id.guide_id != self.inform_guide_id:
            self.case_guide_id.write({
                    'name': self.inform_guide_id.name,
                    'version': self.inform_guide_id.version,
                    'anaesthesia_type_ids': [(6, 0, self.inform_guide_id.anaesthesia_type_ids.ids)],
                    'additional_info_ids': [(6, 0, self.inform_guide_id.additional_info_ids.ids)],
                    'welcome_msg': self.inform_guide_id.welcome_msg,
                    'anaesthesia_intro': self.inform_guide_id.anaesthesia_intro,
                    'close_msg': self.inform_guide_id.close_msg,
                    'check_close_msg': self.inform_guide_id.check_clos_msg,
                    'patient_case_id': self.id,
                    'guide_id': self.inform_guide_id.id
                })
        elif not self.case_guide_id:
            case_guide_id = self.env['information.guide.case'].create({
                                    'name': self.inform_guide_id.name,
                                    'version': self.inform_guide_id.version,
                                    'anaesthesia_type_ids': [(6, 0, self.inform_guide_id.anaesthesia_type_ids.ids)],
                                    'welcome_msg': self.inform_guide_id.welcome_msg,
                                    'anaesthesia_intro': self.inform_guide_id.anaesthesia_intro,
                                    'close_msg': self.inform_guide_id.close_msg,
                                    'check_close_msg': self.inform_guide_id.check_clos_msg,
                                    'patient_case_id': self.id,
                                    'guide_id': self.inform_guide_id.id
                                })
            self.write({'case_guide_id':case_guide_id.id})
            
        return {
            'type': 'ir.actions.act_window',
            'name': 'Anaesthetic Plan Form',
            'res_model': 'information.guide.case',
            'res_id': self.case_guide_id.id,
            'view_mode': 'form',
            'view_id': False,
            'target': 'current',
        }
        
    def action_feedback_form(self):
        self.ensure_one()
        if not self.feedback_answer_id:
            raise UserError("No survey record linked to this operation.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Feedback Answer Form',
            'res_model': 'survey.user_input',
            'res_id': self.feedback_answer_id.id,
            'view_mode': 'form',
            'view_id': False,
            'target': 'current',
        }
        
    def survey_collection_email(self):
        if self.patient_id.email:
            user = self.env['res.users'].search([('partner_id', '=', self.patient_id.id)], limit=1)
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/survey/start/{self.medic_survey_id.access_token}?uniq_id={self.patient_id.unique_id}&pcid={self.id}"
            template_id = self.env.ref('p7_patient_management.survey_collection_email_template').sudo()
            ctx = {
                    'default_model': 'res.users',
                    'default_res_id': user.id,
                    'default_use_template': bool(template_id.id),
                    'default_template_id': template_id.id,
                    'default_composition_mode': 'comment',
                    'force_send': True,
                    'object': user,
                    'surgeon': self.op_surgeon,
                    'url':url,
                    'email_to': self.patient_id.email,
                }
            # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
            patient_name = self.patient_id.name or "Patient"
            email_body = f"""
                <p>Hello {patient_name},</p>
                <p>Please find the url for the medical history survey form below:</p>
                <br/>
                <a href="{url}" style="background-color: #54b1c9; padding:8px 16px 8px 16px; text-decoration:none; color: #fff; border-radius:5px;">Complete your Pre-Anaesthetic Questionnaire now</a>
                <br/>
                <p>Best regards,<br/><strong>VANAESA</strong></p>
                """
            try:
                self.env['mail.mail'].sudo().create({
                    'auto_delete': True,
                    'email_to': self.patient_id.email,
                    'subject': "Complete your Pre-Anaesthetic Questionnaire now",
                    'state': 'sent',
                    'author_id': user.partner_id.id,
                    'date': fields.Datetime.now(),
                    'is_custom_log':True,
                    'body_html':email_body
                })
                template_id.sudo().with_context(ctx).send_mail(user.id, force_send=True)
                return True
            except Exception as e:
                self.env['mail.mail'].sudo().create({
                    'auto_delete': True,
                    'email_to': self.patient_id.email,
                    'subject': "Complete your Pre-Anaesthetic Questionnaire now",
                    'state': 'exception',
                    'author_id': user.partner_id.id,
                    'date': fields.Datetime.now(),
                    'is_custom_log':True,
                    'body_html':email_body
                })
                _logger.error("Failed to send mail: %s", e)
                return False
            
    def create_user(self):
        user = self.env['res.users'].sudo().search([('id', '=', self.patient_id.user_id.id if self.patient_id.user_id else 0)], limit=1)
        # user creation
        if not user:
            group_id = False
            action = False
            action_id = self.env['ir.actions.actions'].sudo().search([('name', '=', 'Dashboard')], limit=1)
            if self.patient_id.user_type == 'admin':
                group_id = [(4, self.env.ref('p7_patient_management.group_user_admin').id),(4, self.env.ref('base.group_user').id),(4, self.env.ref('base.group_partner_manager').id),(4, self.env.ref('survey.group_survey_manager').id),(4, self.env.ref('base.group_system').id)]
                action = action_id
            elif self.patient_id.user_type == 'doctor':
                group_id = [(4, self.env.ref('p7_patient_management.group_user_doctor').id),(4, self.env.ref('base.group_user').id),(4, self.env.ref('base.group_partner_manager').id),(4, self.env.ref('survey.group_survey_manager').id),(4, self.env.ref('base.group_system').id)]
                action = self.env['ir.actions.actions'].sudo().search([('name', '=', 'Bookings')], limit=1)
            else:
                group_id = [(4, self.env.ref('p7_patient_management.group_user_patient').sudo().id),(4, self.env.ref('base.group_user').sudo().id),(4, self.env.ref('base.group_partner_manager').sudo().id),(4, self.env.ref('survey.group_survey_manager').sudo().id)]
                action = self.env['ir.actions.actions'].sudo().search([('name', '=', 'Patient Dashboard')], limit=1)
            user_values = {'company_id':self.env.user.company_id.id,
                        'partner_id':self.patient_id.id,
                        'login':f"user{self.patient_id.id}@gmail.com",
                        'password':'fouri123',
                        'groups_id': group_id,
                        'action_id': action.id,
                        }
            user = self.env['res.users'].sudo().create(user_values)
            self.patient_id.write({
                'user_id':user.id,
                'unique_id': ''.join(random.choices(string.ascii_letters,k=5))+''.join(random.choices(string.digits,k=5)),
            })
            # if self.patient_id.user_type == 'doctor':
            #     reminder_ids = self.env['res.reminder'].sudo().search([('user_id', '=', self.env.user.id),('created_by', '=', 'admin')])
            #     for id in reminder_ids:
            #         new_id = id.sudo().copy()
            #         new_id.write({'user_id':user.id, 'created_by':'doctor',})
            #     anaesthesia_ids = self.env['anaesthesia.type'].sudo().search([('user_id', '=', self.env.user.id),('created_by', '=', 'admin')])
            #     for ids in anaesthesia_ids:
            #         new_id = ids.sudo().copy()
            #         new_id.write({'user_id':user.id, 'created_by':'doctor',})
                
    def initiate_survey_collection(self):
        self.ensure_one()
        for record in self:
            if not record.medic_survey_id:
                raise ValidationError(_("Patient case %s is not having 'Pre-operation Medical History Collection Questionnaire' survey!",self.name))
        success_msg = False
        success_email = False
        for record in self:
            patient_id = self.env['res.partner'].sudo().search([('mob', '=', record.patient_mob),('phone_code', '=', record.patient_phone_code.id)], limit=1)
            if not patient_id:
                patient_id = self.env['res.partner'].sudo().create({
                                    'name': record.patient_first_name,
                                    'last_name': record.patient_last_name,
                                    'phone_code': record.patient_phone_code.id,
                                    'mob': record.patient_mob,
                                    'gender': record.patient_gender,
                                    'dob': record.patient_dob,
                                    'nric_number': record.patient_nric_number,
                                })
            record.sudo().write({'patient_id':patient_id})
            if record.patient_id.state != 'active':
                record.create_user()
            success_msg = record.survey_collection_msg()
            if record.patient_id.email != " " or "":
                success_email = record.survey_collection_email()
            record.write({
                'medic_state': 'confirm',
                'medic_survey_submit_date': False,
                'medic_survey_start_date': False,
                'survey_first_sms_date': fields.Date.context_today(record),
                'survey_reminder_count': 0,
            })
        if success_msg:
            message = _('SMS have been sent successfully. Failed to send email!')
            message_type = 'warning'
            if success_email:
                message = _('SMS and email have been sent successfully.')
                message_type = 'success'
        else:
            if success_email:
                message = _('Email have been sent successfully. Failed to send SMS!')
                message_type = 'warning'
            else:
                message = _('Failed to send SMS and Email!')
                message_type = 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': message_type,
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
        
    def send_msg(self):
        patient_number = f"{self.patient_id.phone_code.name} {self.patient_id.mob}"
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/patient-guide?doctor_id={self.env.user.partner_id.id}&pcid={self.id}"
        msg = (
            f"{self.patient_id.name} {self.patient_id.last_name}\n"
            f"Please click on the following link for more information regarding your upcoming {self.op_process} on {self.get_start_date()}\n"
            f"{url}\n"
        )
        try:
            param_obj = self.env['ir.config_parameter'].sudo()
            sid = param_obj.get_param('twilio_sid')
            token = param_obj.get_param('twilio_token')
            number = param_obj.get_param('twilio_number')
            client = Client(str(sid), str(token))
            client.messages.create(
                body=msg,
                from_=str(number),
                to=patient_number
            )
            self.env['sms.sms'].sudo().create({
                    'partner_id': self.patient_id.id,
                    'number': patient_number,
                    'state': 'sent',
                    'body': msg,
                    'is_custom_log': True,
                })
            return True
        except Exception as e:
            self.env['sms.sms'].sudo().create({
                    'partner_id': self.patient_id.id,
                    'number': patient_number,
                    'state': 'error',
                    'body': msg,
                    'is_custom_log': True,
                })
            _logger.error("Failed to send sms: %s", e)
            return False
        
    def send_email(self):
        if self.patient_id.email:
            user = self.env['res.users'].search([('partner_id', '=', self.patient_id.id)], limit=1)
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/patient-guide?doctor_id={self.env.user.partner_id.id}&pcid={self.id}"
            template_id = self.env.ref('p7_patient_management.guide_email_template').sudo()
            ctx = {
                    'default_model': 'res.users',
                    'default_res_id': user.id,
                    'default_use_template': bool(template_id.id),
                    'default_template_id': template_id.id,
                    'default_composition_mode': 'comment',
                    'force_send': True,
                    'object': user,
                    'url':url,
                    'email_to': self.patient_id.email,
                }
            # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
            patient_name = self.patient_id.name or "Patient"
            email_body = f"""
                            <p>Hello {patient_name},</p>
                            <p>Please find the url for the information of anaesthesia preparations:</p>
                            <a href="{url}" style="background-color: #54b1c9; padding:8px 16px 8px 16px; text-decoration:none; color: #fff; border-radius:5px;">Information Guide</a>
                            <br/>
                            <p>Best regards,<br/><strong>VANAESA</strong></p>
                        """
            try:
                self.env['mail.mail'].sudo().create({
                    'auto_delete': True,
                    'email_to': self.patient_id.email,
                    'subject': "Your Anaesthesia Information Guide is Ready",
                    'state': 'sent',
                    'author_id': user.partner_id.id,
                    'date': fields.Datetime.now(),
                    'is_custom_log':True,
                    'body_html':email_body
                })
                template_id.sudo().with_context(ctx).send_mail(user.id, force_send=True)
                return True
            except Exception as e:
                self.env['mail.mail'].sudo().create({
                    'auto_delete': True,
                    'email_to': self.patient_id.email,
                    'subject': "Your Anaesthesia Information Guide is Ready",
                    'state': 'exception',
                    'author_id': user.partner_id.id,
                    'date': fields.Datetime.now(),
                    'is_custom_log':True,
                    'body_html':email_body
                })
                _logger.error("Failed to send mail: %s", e)
                return False
        
    def send_guide(self):
        self.ensure_one()
        if self.video_call_status not in ('success', 'bypassed'):
            raise ValidationError(_('Video call must be successful or bypassed before sending guide.'))
        success_msg = False
        success_email = False
        for record in self:
            success_msg = record.send_msg()
            if record.patient_id.email != " " or "":
                success_email = record.send_email()
            vals = {'guide_state': 'sent'}
            if not record.guide_first_sms_date:
                vals.update({
                    'guide_first_sms_date': fields.Date.context_today(record),
                    'guide_reminder_count': 0,
                })
            record.write(vals)
        if success_msg:
            message = _('SMS have been sent successfully. Failed to send email!')
            message_type = 'warning'
            if success_email:
                message = _('SMS and email have been sent successfully.')
                message_type = 'success'
        else:
            if success_email:
                message = _('Email have been sent successfully. Failed to send SMS!')
                message_type = 'warning'
            else:
                message = _('Failed to send SMS and Email!')
                message_type = 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': message_type,
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
        
    def feedback_collection_msg(self):
        patient_number = f"{self.patient_id.phone_code.name} {self.patient_id.mob}"
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/survey/start/{self.feedback_survey_id.access_token}?uniq_id={self.patient_id.unique_id}&pcid={self.id}"
        msg = (
            f"Hi {self.patient_id.name} {self.patient_id.last_name}\n"
            f"Medical Feedback Survey Url: "
            f"{url}\n"
        )
        try:
            param_obj = self.env['ir.config_parameter'].sudo()
            sid = param_obj.get_param('twilio_sid')
            token = param_obj.get_param('twilio_token')
            number = param_obj.get_param('twilio_number')
            client = Client(str(sid), str(token))
            client.messages.create(
                body=msg,
                from_=str(number),
                to=patient_number
            )
            self.env['sms.sms'].sudo().create({
                    'partner_id': self.patient_id.id,
                    'number': patient_number,
                    'state': 'sent',
                    'body': msg,
                    'is_custom_log': True,
                })
            return True
        except Exception as e:
            self.env['sms.sms'].sudo().create({
                    'partner_id': self.patient_id.id,
                    'number': patient_number,
                    'state': 'error',
                    'body': msg,
                    'is_custom_log': True,
                })
            _logger.error("Failed to send sms: %s", e)
            return False
        
    def feedback_collection_email(self):
        if self.patient_id.email:
            user = self.env['res.users'].search([('partner_id', '=', self.patient_id.id)], limit=1)
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/survey/start/{self.feedback_survey_id.access_token}?uniq_id={self.patient_id.unique_id}&pcid={self.id}"
            template_id = self.env.ref('p7_patient_management.feedback_collection_email_template').sudo()
            ctx = {
                    'default_model': 'res.users',
                    'default_res_id': user.id,
                    'default_use_template': bool(template_id.id),
                    'default_template_id': template_id.id,
                    'default_composition_mode': 'comment',
                    'force_send': True,
                    'object': user,
                    'url':url,
                    'email_to': self.patient_id.email,
                }
            # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
            patient_name = self.patient_id.name or "Patient"
            email_body = f"""
                        <p>Hello {patient_name},</p>
                        <p>Please find the url for the medical feedback survey form below:</p>
                        <br/>
                        <a href="{url}" style="background-color: #54b1c9; padding:8px 16px 8px 16px; text-decoration:none; color: #fff; border-radius:5px;">Medical Feedback Survey</a>
                        <br/>
                        <p>Best regards,<br/><strong>VANAESA</strong></p>
                        """
            try:
                self.env['mail.mail'].sudo().create({
                    'auto_delete': True,
                    'email_to': self.patient_id.email,
                    'subject': "Medical Feedback Survey",
                    'state': 'sent',
                    'author_id': user.partner_id.id,
                    'date': fields.Datetime.now(),
                    'is_custom_log':True,
                    'body_html':email_body
                })
                template_id.sudo().with_context(ctx).send_mail(user.id, force_send=True)
                return True
            except Exception as e:
                self.env['mail.mail'].sudo().create({
                    'auto_delete': True,
                    'email_to': self.patient_id.email,
                    'subject': "Medical Feedback Survey",
                    'state': 'exception',
                    'author_id': user.partner_id.id,
                    'date': fields.Datetime.now(),
                    'is_custom_log':True,
                    'body_html':email_body
                })
                _logger.error("Failed to send mail: %s", e)
                return False
        
    def initiate_feedback_collection(self):
        self.ensure_one()
        for record in self:
            if not record.feedback_survey_id:
                raise ValidationError(_("Patient case %s is not having 'Post-operation Feedback Questionnaire'!",record.name))
            if record.state != 'post-operation':
                raise ValidationError(_("Patient case %s is not in Post-Operation state!",record.name))
        success_msg = False
        success_email = False
        for record in self:
            success_msg = record.feedback_collection_msg()
            if record.patient_id.email != " " or "":
                success_email = record.feedback_collection_email()
            record.write({'feedback_state':'confirm'})
        if success_msg:
            message = _('SMS have been sent successfully. Failed to send email!')
            message_type = 'warning'
            if success_email:
                message = _('SMS and email have been sent successfully.')
                message_type = 'success'
        else:
            if success_email:
                message = _('Email have been sent successfully. Failed to send SMS!')
                message_type = 'warning'
            else:
                message = _('Failed to send SMS and Email!')
                message_type = 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': message_type,
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
        
    def action_feedback_survey_collection(self):
        return self.initiate_feedback_collection()
        