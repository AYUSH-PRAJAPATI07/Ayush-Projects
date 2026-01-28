# (c) 2015 ACSONE SA/NV, Dhinesh D

# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
from os import utime
from os.path import getmtime
from time import time
from twilio.rest import Client
import pytz

from odoo import api, http, models, fields
from odoo.http import SessionExpiredException

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _auth_timeout_get_ignored_urls(self):
        """Pluggable method for calculating ignored urls
        Defaults to stored config param
        """
        params = self.env["ir.config_parameter"]
        return params._auth_timeout_get_parameter_ignored_urls()

    @api.model
    def _auth_timeout_deadline_calculate(self):
        """Pluggable method for calculating timeout deadline
        Defaults to current time minus delay using delay stored as config
        param.
        """
        params = self.env["ir.config_parameter"]
        delay = params._auth_timeout_get_parameter_delay()
        if delay <= 0:
            return False
        return time() - delay

    @api.model
    def _auth_timeout_session_terminate(self, session):
        """Pluggable method for terminating a timed-out session

        This is a late stage where a session timeout can be aborted.
        Useful if you want to do some heavy checking, as it won't be
        called unless the session inactivity deadline has been reached.

        Return:
            True: session terminated
            False: session timeout cancelled
        """
        if session.db and session.uid:
            if self.partner_id.user_type == 'patient':
                case_id = self.env['patient.case'].sudo().search([('patient_id', '=', self.partner_id.id)], limit=1)
                if case_id:
                    if case_id.medic_state == 'in_progress' and case_id.medic_survey_id and case_id.medic_answer_id:
                        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                        local_op_date = False
                        if case_id and case_id.op_date:
                            local_op_date = pytz.utc.localize(case_id.op_date).astimezone(user_tz)
                        patient_number = f"{self.env.user.sudo().partner_id.phone_code.name} {self.env.user.sudo().partner_id.mob}"
                        doctor_number = f"{case_id.medic_survey_id.user_id.partner_id.phone_code.name} {case_id.medic_survey_id.user_id.partner_id.mob}"
                        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                        url = f"{base_url}/survey/{case_id.medic_survey_id.access_token}/{case_id.medic_answer_id.access_token}"
                        patient_msg = (
                            f"Hi! A reminder to complete your questionnaire\n"
                            f"{url}\n"
                        )
                        doctor_msg = (
                            f"Hi {case_id.medic_survey_id.user_id.partner_id.name} {case_id.medic_survey_id.user_id.partner_id.last_name}, patient {self.env.user.sudo().partner_id.name} {self.env.user.sudo().partner_id.last_name} has partially completed the medical history questionnaire for surgery on {local_op_date.strftime('%d/%m/%y') if local_op_date else ''} with Dr {case_id.op_surgeon if case_id else ''}\n"
                        )
                        
                        param_obj = self.env['ir.config_parameter'].sudo()
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
                            self.env['sms.sms'].sudo().create({
                                    'partner_id': self.partner_id.id,
                                    'number': patient_number,
                                    'state': 'sent',
                                    'body': patient_msg,
                                    'is_custom_log': True,
                                })
                            _logger.info(f"SMS sent to patient: {patient_number}")
                        except Exception as e:
                            self.env['sms.sms'].sudo().create({
                                    'partner_id': self.partner_id.id,
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
                            self.env['sms.sms'].sudo().create({
                                    'partner_id': case_id.medic_survey_id.user_id.partner_id.id,
                                    'number': doctor_number,
                                    'state': 'sent',
                                    'body': doctor_msg,
                                    'is_custom_log': True,
                                })
                            _logger.info(f"SMS sent to doctor: {doctor_number}")
                        except Exception as e:
                            self.env['sms.sms'].sudo().create({
                                    'partner_id': case_id.medic_survey_id.user_id.partner_id.id,
                                    'number': doctor_number,
                                    'state': 'error',
                                    'body': doctor_msg,
                                    'is_custom_log': True,
                                })
                            _logger.error("Failed to send SMS to doctor: %s", e)
                        
                        # send email
                        #patient
                        if self.env.user.sudo().partner_id.email:
                            user = self.env.user
                            template_id = self.env.ref('p7_patient_management.partial_survey_notification_template').sudo()
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
                                    'email_to': self.env.user.sudo().partner_id.email,
                                }
                            # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
                            email_body = f"""
                                        <p style="margin: 0px; padding: 0px; font-size: 15px;"> Hi {user.partner_id.name} {user.partner_id.last_name}, <p>
                                        <br/>
                                        <p style="margin: 0px; padding: 0px; font-size: 15px;"> Please find the url to complete the medical form which you left incomplete: </p>
                                        <br/>
                                        <a style="background-color:#875A7B; padding:8px 16px 8px 16px; text-decoration:none; color:#fff; border-radius:5px" href="{url}">Survey URL</a>
                                        <br/>
                                        <p>Best regards,<br/><strong>VANAESA</strong></p> """
                            try:
                                self.env['mail.mail'].sudo().create({
                                    'auto_delete': True,
                                    'email_to': self.env.user.sudo().partner_id.email,
                                    'subject': "An Important Reminder",
                                    'state': 'sent',
                                    'author_id': user.partner_id.id,
                                    'date': fields.Datetime.now(),
                                    'is_custom_log':True,
                                    'body_html':email_body
                                })
                                template_id.sudo().with_context(ctx).send_mail(user.id, force_send=True)
                            except Exception as e:
                                self.env['mail.mail'].sudo().create({
                                    'auto_delete': True,
                                    'email_to': self.env.user.sudo().partner_id.email,
                                    'subject': "An Important Reminder",
                                    'state': 'exception',
                                    'author_id': user.partner_id.id,
                                    'date': fields.Datetime.now(),
                                    'is_custom_log':True,
                                    'body_html':email_body
                                })
                                _logger.error("Failed to send mail: %s", e)
                        #doctor
                        if case_id.medic_survey_id.user_id.partner_id.email:
                            user = case_id.medic_survey_id.user_id
                            template_id = self.env.ref('p7_patient_management.partial_survey_notification_template_doctor').sudo()
                            ctx = {
                                    'default_model': 'res.users',
                                    'default_res_id': user.id,
                                    'default_use_template': bool(template_id.id),
                                    'default_template_id': template_id.id,
                                    'default_composition_mode': 'comment',
                                    'force_send': True,
                                    'object': user,
                                    'case': case_id,
                                    'email_to': case_id.medic_survey_id.user_id.partner_id.email,
                                }
                            # body_html = template_id._render_template(template_id.body_html, 'res.users', [user.sudo().id])
                            email_body = f"""
                                <p style="margin: 0px; padding: 0px; font-size: 15px;"> Hi {user.partner_id.name} {user.partner_id.last_name}, <p>
                                <br/>
                                <p style="margin: 0px; padding: 0px; font-size: 15px;"> Patient {self.env.user.sudo().partner_id.name} {self.env.user.sudo().partner_id.last_name} has partially completed the medical history questionnaire. </p>
                                <br/>
                                <p>Best regards,<br/><strong>VANAESA</strong></p> """
                            try:
                                self.env['mail.mail'].sudo().create({
                                    'auto_delete': True,
                                    'email_to': case_id.medic_survey_id.user_id.partner_id.email,
                                    'subject': "Partial Form Completion",
                                    'state': 'sent',
                                    'author_id': user.partner_id.id,
                                    'date': fields.Datetime.now(),
                                    'is_custom_log':True,
                                    'body_html':email_body
                                })
                                template_id.sudo().with_context(ctx).send_mail(user.id, force_send=True)
                            except Exception as e:
                                self.env['mail.mail'].sudo().create({
                                    'auto_delete': True,
                                    'email_to': case_id.medic_survey_id.user_id.partner_id.email,
                                    'subject': "Partial Form Completion",
                                    'state': 'exception',
                                    'author_id': user.partner_id.id,
                                    'date': fields.Datetime.now(),
                                    'is_custom_log':True,
                                    'body_html':email_body
                                })
                                _logger.error("Failed to send mail: %s", e)
            session.logout(keep_db=True)
        return True

    @api.model
    def _auth_timeout_check(self):
        """Perform session timeout validation and expire if needed."""

        if not http.request:
            return

        session = http.request.session

        # Calculate deadline
        deadline = self._auth_timeout_deadline_calculate()

        # Check if past deadline
        expired = False
        if deadline is not False:
            path = http.root.session_store.get_session_filename(session.sid)
            try:
                expired = getmtime(path) < deadline
            except OSError:
                _logger.exception(
                    "Exception reading session file modified time.",
                )
                # Force expire the session. Will be resolved with new session.
                expired = True

        # Try to terminate the session
        terminated = False
        if expired:
            terminated = self._auth_timeout_session_terminate(session)

        # If session terminated, all done
        if terminated:
            return SessionExpiredException("Session expired")

        # Else, conditionally update session modified and access times
        ignored_urls = self._auth_timeout_get_ignored_urls()

        if http.request.httprequest.path not in ignored_urls:
            if "path" not in locals():
                path = http.root.session_store.get_session_filename(
                    session.sid,
                )
            try:
                utime(path, None)
            except OSError:
                _logger.exception(
                    "Exception updating session file access/modified times.",
                )
