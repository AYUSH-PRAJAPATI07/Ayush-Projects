# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from twilio.rest import Client
from odoo.exceptions import ValidationError
import random
import string
import logging
import pytz
from odoo.exceptions import UserError
from odoo.addons.auth_signup.models.res_partner import now
from odoo.addons.base.models.ir_mail_server import MailDeliveryException

_logger = logging.getLogger(__name__)


_tzs = [(tz, tz) for tz in sorted(pytz.all_timezones, key=lambda tz: tz if not tz.startswith('Etc/') else '_')]
def _tz_get(self):
    return _tzs

class PatientManagement(models.Model):
    _name = 'patient.management'
    _description = 'Patient Management'
    
    name = fields.Char("Name")

class user_update(models.Model):
    _inherit = 'res.users'
    
    password = fields.Char(
        compute='_compute_password', inverse='_set_password', copy=False,
        help="Keep empty if you don't want the user to be able to connect on the system.")
    is_specific_login = fields.Boolean("Is Specific Login", default=False)
    is_tech_support = fields.Boolean("Is Technician", default=False)
            
    @api.model
    def update_phone_code(self):
        country_ids = self.env['res.country'].sudo().search([])
        for country_id in country_ids:
            if country_id.phone_code and country_id.name:
                self.env['res.phone_code'].sudo().create({
                    'name': f"+{country_id.phone_code}",
                    'country_name': country_id.name
                })
        
    def _compute_password(self):
        for user in self:
            user.password = 'fouri123'
            user.new_password = 'fouri123'
            
    def _set_password(self):
        ctx = self._crypt_context()
        for user in self:
            self._set_encrypted_password(user.id, ctx.hash(user.password))
            
    def _init_odoobot(self):
        return False

    def change_user_type(self):
        for rec in self:
            new_user_type = False
            action = False
            actions_model = self.env['ir.actions.actions'].sudo()
            if rec.has_group('p7_patient_management.group_user_admin'):
                new_user_type = 'admin'
                action = actions_model.search([('name', '=', 'Dashboard')], limit=1)
            elif rec.has_group('p7_patient_management.group_user_doctor'):
                new_user_type = 'doctor'
                action = actions_model.search([('name', '=', 'Bookings')], limit=1)
            elif rec.has_group('p7_patient_management.group_user_patient'):
                new_user_type = 'patient'
                action = actions_model.search([('name', '=', 'Patient Dashboard')], limit=1)
            elif rec.has_group('p7_patient_management.group_user_associate'):
                new_user_type = 'associate'
                action = actions_model.search([('name', '=', 'My Bookings')], limit=1)

            rec.partner_id.write({'user_type': new_user_type, 'password': 'fouri123'})
            if action and rec.action_id != action:
                rec.with_context(skip_change_user_type=True).sudo().write({'action_id': action.id})
                            
    @api.model_create_multi
    def create(self, vals_list):
        vals_list[0]['password'] = 'fouri123'
        res = super(user_update,self).create(vals_list)
        res.change_user_type()
        for user in res:
            if user.has_group('p7_patient_management.group_user_patient'):
                if user.partner_id.patient_backend_id == "New":
                    user.partner_id.patient_backend_id = f"PID-{user.partner_id.id}"
        return res
    
    def write(self, vals):
        res = super(user_update,self).write(vals)
        if not self.env.context.get('skip_change_user_type'):
            self.change_user_type()
        for user in self:
            if user.has_group('p7_patient_management.group_user_patient'):
                if user.partner_id.patient_backend_id == "New":
                    user.partner_id.patient_backend_id = f"PID-{user.partner_id.id}"
        return res
    
    def _notify_security_setting_update(self, subject, content, mail_values=None, **kwargs):
        """ This method is meant to be called whenever a sensitive update is done on the user's account.
        It will send an email to the concerned user warning him about this change and making some security suggestions.

        :param str subject: The subject of the sent email (e.g: 'Security Update: Password Changed')
        :param str content: The text to embed within the email template (e.g: 'Your password has been changed')
        :param kwargs: 'suggest_password_reset' key:
            Whether or not to suggest the end-user to reset
            his password in the email sent.
            Defaults to True. """

        _logger.info('security update!')
    
    def _alert_new_device(self):
        self.ensure_one()
        _logger.info("New device alert email sent for user <%s> to <%s>", self.login, self.email)

    def _action_reset_password(self):
        """ create signup token for each user, and send their signup url by email """
        if self.env.context.get('install_mode') or self.env.context.get('import_file'):
            return
        if self.filtered(lambda user: not user.active):
            raise UserError(_("You cannot perform this action on an archived user."))
        # prepare reset password signup
        create_mode = bool(self.env.context.get('create_user'))

        # no time limit for initial invitation, only for reset password
        expiration = False if create_mode else now(days=+1)

        self.mapped('partner_id').signup_prepare(signup_type="reset", expiration=expiration)
        _logger.info("Password reset email sending is stopped")
        
class partner_update(models.Model):
    _inherit = 'res.partner'
    
    last_name = fields.Char("Last Name",tracking=True)
    nric_number = fields.Char("NRIC/Passport", tracking=True)
    dob = fields.Date("Date of Birth",tracking=True)
    language = fields.Selection([('english', 'English'), ('chinese', 'Chinese')], default='english', string="Preferred Language",tracking=True)
    gender = fields.Selection([('male', 'Male'), ('female', 'Female')], string="Gender",tracking=True)
    mob = fields.Char("Mobile",tracking=True)
    mobile = fields.Char(unaccent=False, string="Note",)
    bio = fields.Text('Bio',tracking=True)
    email = fields.Char(default=" ",tracking=True)
    oms_number = fields.Char("OMS License Number", size=20, tracking=True)
    interest = fields.Char("Specialist Interest", size=150, tracking=True)
    skill = fields.Char("Skills", size=150, tracking=True)
    password = fields.Char("Password",default='fouri123')
    user_type = fields.Selection([('patient', 'Patient'), ('doctor', 'Doctor'), ('associate', 'Associate'), ('admin', 'Administrator')], string="Patient Case Management")
    doctor_id = fields.Many2one('res.partner', string='Doctors Assigned', domain=[('user_type', '=', 'doctor')], tracking=True)
    doctor_ids = fields.One2many('res.partner', 'partner_id', string='Doctors', domain=[('user_type', '=', 'doctor')])
    patient_ids = fields.One2many('res.partner', 'partner_id', string='Patients', domain=[('user_type', '=', 'patient')])
    state = fields.Selection([('new', 'Created'), ('verify_pass', 'Verified'), ('verify_fail', 'Verification Failed'), ('active', 'Connected')], default='new', string="Status")
    unique_id = fields.Char("uniq_id")
    patient_backend_id = fields.Char(
        "Patient ID",
        default="New",
        copy=False,
        readonly=True,
    )
    phone_code = fields.Many2one('res.phone_code',tracking=True, default=lambda self: self.env['res.phone_code'].search([('name', '=', '+65')], limit=1))
    operation_ids = fields.One2many('patient.case', 'partner_id', string='Operations')
    patient_operation_ids = fields.One2many('patient.case', 'patient_id', string='')
    partner_id = fields.Many2one('res.partner', compute='_compute_parent_id')
    is_created = fields.Boolean("Is Created", default=False)
    tz = fields.Selection(
        _tz_get,
        string='Timezone',
        default='Asia/Singapore',
        help="When printing documents and exporting/importing data, time values are computed according to this timezone.\n"
            "If the timezone is not set, UTC (Coordinated Universal Time) is used.\n"
            "Anywhere else, time values are computed according to the time offset of your web client."
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        res = super(partner_update,self).create(vals_list)
        for partner, vals in zip(res, vals_list):
            if partner.patient_backend_id == "New" and (
                    vals.get('user_type') == 'patient' or partner.user_type == 'patient'
            ):
                partner.patient_backend_id = f"PID-{partner.id}"
        self.is_created = True
        return res
    
    @api.model
    def write(self, vals):
        res = super().write(vals)
        for partner in self:
            if partner.patient_backend_id == "New" and partner.user_type == 'patient':
                partner.patient_backend_id = f"PID-{partner.id}"
        if 'email' in vals:
            for partner in self:
                user = self.env['res.users'].search([('partner_id', '=', partner.id)])
                if user:
                    user.login = vals['email']
        return res
    
    @api.model
    def get_doctor_profile_action(self):
        partners = self.env['res.partner'].search([('user_id', '=', self.env.user.id)])
 
        if len(partners) > 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'My Profiles',
                'res_model': 'res.partner',
                'view_mode': 'tree,form',
                'domain': [('user_id', '=', self.env.user.id)],
                'context': {'create': False, 'copy': False, 'delete': False},
            }
        elif len(partners) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'My Profile',
                'res_model': 'res.partner',
                'view_mode': 'form',
                'res_id': partners.id,
                'context': {'create': False, 'copy': False, 'delete': False},
            }
        else:
            return {
                'type': 'ir.actions.act_window_close',
            }
    
    def _compute_parent_id(self):
        for rec in self:
            if not rec.sudo().partner_id:
                rec.sudo().partner_id = rec.sudo().create_uid.partner_id.id
                
    def remove_duplicate_phone_codes(self):
        phone_codes = self.env['res.phone_code'].sudo().search([], order='create_date')

        seen = {}
        duplicates = []

        for record in phone_codes:
            key = record.name.strip()
            if key not in seen:
                seen[key] = record.id
            else:
                duplicates.append(record.id)

        if duplicates:
            self.env['res.phone_code'].sudo().browse(duplicates).unlink()
        
                
    @api.onchange('name')
    def _onchange_name(self):
        if self.name and self.user_type == 'patient':
            patient_case_ids = self.env['patient.case'].sudo().search([('patient_id', '=', self._origin.id)])
            for patient_case_id in patient_case_ids:
                patient_case_id.sudo().write({'patient_first_name' : self.name })
                
    @api.onchange('last_name')
    def _onchange_last_name(self):
        if self.last_name and self.user_type == 'patient':
            patient_case_ids = self.env['patient.case'].sudo().search([('patient_id', '=', self._origin.id)])
            for patient_case_id in patient_case_ids:
                patient_case_id.sudo().write({'patient_last_name' : self.last_name })
        
    @api.onchange('mob')
    def _onchange_mob(self):
        if self.mob:
            partner = self.env['res.partner'].sudo().search([('mob', '=', self.mob)], limit=1)
            if partner and partner != self:
                raise ValidationError(_('This mobile number already exists!'))
            if self.user_type == 'patient':
                patient_case_ids = self.env['patient.case'].sudo().search([('patient_id', '=', self._origin.id)])
                for patient_case_id in patient_case_ids:
                    patient_case_id.sudo().write({'patient_mob' : self.mob })
                
    @api.onchange('phone_code')
    def _onchange_phone_code(self):
        if self.phone_code and self.user_type == 'patient':
            patient_case_ids = self.env['patient.case'].sudo().search([('patient_id', '=', self._origin.id)])
            for patient_case_id in patient_case_ids:
                patient_case_id.sudo().write({'patient_phone_code' : self.phone_code })
                
    @api.onchange('gender')
    def _onchange_gender(self):
        if self.gender and self.user_type == 'patient':
            patient_case_ids = self.env['patient.case'].sudo().search([('patient_id', '=', self._origin.id)])
            for patient_case_id in patient_case_ids:
                patient_case_id.sudo().write({'patient_gender' : self.gender })
                
    @api.onchange('dob')
    def _onchange_dob(self):
        if self.dob and self.user_type == 'patient':
            patient_case_ids = self.env['patient.case'].sudo().search([('patient_id', '=', self._origin.id)])
            for patient_case_id in patient_case_ids:
                patient_case_id.sudo().write({'patient_dob' : self.dob })
                
    @api.onchange('nric_number')
    def _onchange_nric_number(self):
        if self.nric_number and self.user_type == 'patient':
            patient_case_ids = self.env['patient.case'].sudo().search([('patient_id', '=', self._origin.id)])
            for patient_case_id in patient_case_ids:
                patient_case_id.sudo().write({'patient_nric_number' : self.nric_number })
                
    def send_msg(self):
        # verification notification through sms and mail
        # sms notification
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/web/login?uniq_id={self.unique_id}"
        message_body = (
            f"Hi {self.name} {self.last_name}\n"
            f"Please complete your enrolment on VANAESA\n"
            f"{url}"
        )
        try:
            param_obj = self.env['ir.config_parameter'].sudo()
            sid = param_obj.get_param('twilio_sid')
            token = param_obj.get_param('twilio_token')
            number = param_obj.get_param('twilio_number')
            client = Client(str(sid), str(token))
            client.messages.create(
                body = message_body,
                from_ = str(number),
                to = f"{self.phone_code.name} {self.mob}"
            )
            self.env['sms.sms'].sudo().create({
                    'partner_id': self.id,
                    'number': f"{self.phone_code.name} {self.mob}",
                    'state': 'sent',
                    'body': message_body,
                    'is_custom_log': True,
                })
            return True
        except Exception as e:
            self.env['sms.sms'].sudo().create({
                    'partner_id': self.id,
                    'number': f"{self.phone_code.name} {self.mob}",
                    'state': 'error',
                    'body': message_body,
                    'is_custom_log': True,
                })
            _logger.error("Failed to send SMS: %s", e)
            return False
        
    def send_email(self,user):
        # mail notification
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/web/login?uniq_id={self.unique_id}"
        template_id = self.env.ref('p7_patient_management.verification_email_template')
        email_body = f"""
                    <p style="margin: 0px; padding: 0px; font-size: 15px;"> Hello {self.name} {self.last_name}, <p>
                    <br/>
                    <p style="margin: 0px; padding: 0px; font-size: 15px;">
                        Please find the url for the login verification below:
                    </p><br/>
                    <a href="{url}" style="background-color: #54b1c9; padding:8px 16px 8px 16px; text-decoration:none; color:#fff; border-radius:5px">Login Verification</a>
                    <br/>
                    <p>Best regards,<br/><strong>VANAESA</strong></p> """
        ctx = {
                'default_model': 'res.users',
                'default_res_id': user.id,
                'default_use_template': bool(template_id.id),
                'default_template_id': template_id.id,
                'default_composition_mode': 'comment',
                'force_send': True,
                'object': user,
                'url':url,
                'email_to': self.email,
            }
        # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
        try:
            self.env['mail.mail'].sudo().create({
                'auto_delete': True,
                'email_to': self.email,
                'subject': "Login Verification",
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
                'email_to': self.email,
                'subject': "Login Verification",
                'state': 'exception',
                'author_id': user.partner_id.id,
                'date': fields.Datetime.now(),
                'is_custom_log':True,
                'body_html':email_body
            })
            _logger.error("Failed to send mail: %s", e)
            return False
            
    def create_verified_user(self):
        user = self.env['res.users'].sudo().search([('id', '=', self.user_id.id if self.user_id else 0)], limit=1)
        # user creation
        if not user:
            group_id = False
            action = False
            action_id = self.env['ir.actions.actions'].sudo().search([('name', '=', 'Dashboard')], limit=1)
            if self.user_type == 'admin':
                group_id = [(4, self.env.ref('p7_patient_management.group_user_admin').id),(4, self.env.ref('base.group_user').id),(4, self.env.ref('base.group_partner_manager').id),(4, self.env.ref('survey.group_survey_manager').id),(4, self.env.ref('base.group_system').id)]
                action = action_id
            elif self.user_type == 'doctor':
                group_id = [(4, self.env.ref('p7_patient_management.group_user_doctor').id),(4, self.env.ref('base.group_user').id),(4, self.env.ref('base.group_partner_manager').id),(4, self.env.ref('survey.group_survey_manager').id),(4, self.env.ref('base.group_system').id)]
                action = self.env['ir.actions.actions'].sudo().search([('name', '=', 'Bookings')], limit=1)
            elif self.user_type == 'associate':
                group_id = [
                    (4, self.env.ref('p7_patient_management.group_user_associate').id),
                    (4, self.env.ref('base.group_user').id),
                    (4, self.env.ref('base.group_partner_manager').id),
                    (4, self.env.ref('survey.group_survey_manager').id),
                ]
                action = self.env['ir.actions.actions'].sudo().search([('name', '=', 'My Bookings')], limit=1)
            else:
                group_id = [(4, self.env.ref('p7_patient_management.group_user_patient').id),(4, self.env.ref('base.group_user').id),(4, self.env.ref('base.group_partner_manager').id),(4, self.env.ref('survey.group_survey_manager').id)]
                action = self.env['ir.actions.actions'].sudo().search([('name', '=', 'Patient Dashboard')], limit=1)
            user_values = {'company_id':self.env.user.company_id.id,
                        'partner_id':self.id,
                        'login':f"user{self.id}@gmail.com",
                        'password':'fouri123',
                        'groups_id': group_id,
                        'action_id': action.id,
                        'tz':'Asia/Singapore',
                        }
            user = self.env['res.users'].sudo().create(user_values)
            self.write({
                'user_id':user.id,
                'unique_id': ''.join(random.choices(string.ascii_letters,k=5))+''.join(random.choices(string.digits,k=5))
            })
            if self.user_type == 'doctor':
                reminder_ids = self.env['res.reminder'].sudo().search([('user_id', '=', self.env.user.id),('created_by', '=', 'admin')])
                for id in reminder_ids:
                    new_id = id.sudo().copy()
                    new_id.write({'user_id':user.id, 'created_by':'doctor',})
                anaesthesia_ids = self.env['anaesthesia.type'].sudo().search([('user_id', '=', self.env.user.id),('created_by', '=', 'admin')])
                for ids in anaesthesia_ids:
                    new_id = ids.sudo().copy()
                    new_id.write({'user_id':user.id, 'created_by':'doctor',})
                dislocation_ids = self.env['res.dislocation'].sudo().search([('user_id', '=', self.env.user.id),('created_by', '=', 'admin')])
                for ids in dislocation_ids:
                    new_id = ids.sudo().copy()
                    new_id.write({'user_id':user.id, 'created_by':'doctor',})
                location_ids = self.env['res.location'].sudo().search([('user_id', '=', self.env.user.id),('created_by', '=', 'admin')])
                for ids in location_ids:
                    new_id = ids.sudo().copy()
                    new_id.write({'user_id':user.id, 'created_by':'doctor',})
        
        success_msg = self.send_msg()
        success_email = False
        if self.email != " " or "":
            success_email = self.send_email(user)
        self._message_log(body=_("User verification Initiated."))
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
        
    
class ChangePasswordUserInherit(models.TransientModel):
    _inherit = 'change.password.user'
    
    def change_password_button(self):
        for line in self:
            if line.new_passwd:
                line.user_id._change_password(line.new_passwd)
                user_id = self.env['res.users'].sudo().search([('login', '=', line.user_login)], limit=1)
                user_id.partner_id.write({'password': line.new_passwd})
        # don't keep temporary passwords in the database longer than necessary
        self.write({'new_passwd': False})

class PhoneCode(models.Model):
    _name = 'res.phone_code'
    _description = "Phone code"
    _rec_names_search = ['name', 'country_name']
    
    name = fields.Char('')
    country_name = fields.Char('')
    
class ResUsersIdentityCheckInht(models.TransientModel):
    _inherit = 'res.users.identitycheck'

    password = fields.Char(default=lambda self: 'fouri123')
    
class MailMailInht(models.Model):
    _inherit = 'mail.mail'
    # restrict email while run send mail base level
    def send(self, auto_commit=False, raise_exception=False):
        """
        Override the base email send function to allow sending mail only if
         the template is 'Payment Advice Email'.
         """
        for rec in self:     
            if rec.model == 'discuss.channel':
                return False
            else:
                for mail_server_id, alias_domain_id, smtp_from, batch_ids in self._split_by_mail_configuration():
                    smtp_session = None
                    if self.model == 'discuss.channel':
                        return False
                    try:
                        smtp_session = self.env['ir.mail_server'].connect(mail_server_id=mail_server_id, smtp_from=smtp_from)
                    except Exception as exc:
                        if raise_exception:
                            # To be consistent and backward compatible with mail_mail.send() raised
                            # exceptions, it is encapsulated into an Odoo MailDeliveryException
                            raise MailDeliveryException(_('Unable to connect to SMTP Server'), exc)
                        else:
                            batch = self.browse(batch_ids)
                            batch.write({'state': 'exception', 'failure_reason': exc})
                            batch._postprocess_sent_message(success_pids=[], failure_type="mail_smtp")
                    else:
                        self.browse(batch_ids)._send(
                            auto_commit=auto_commit,
                            raise_exception=raise_exception,
                            smtp_session=smtp_session,
                            alias_domain_id=alias_domain_id,
                        )
                        _logger.info(
                            'Sent batch %s emails via mail server ID #%s',
                            len(batch_ids), mail_server_id)
                    finally:
                        if smtp_session:
                            smtp_session.quit()
 
