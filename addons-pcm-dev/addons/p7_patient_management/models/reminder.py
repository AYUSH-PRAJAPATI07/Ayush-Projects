from odoo import models, fields, api, _
from datetime import datetime,timedelta
import pytz
import re
import logging

_logger = logging.getLogger(__name__)
class ReminderSetup(models.Model):
    _name = 'res.reminder'
    _description = 'Reminder Setup'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char("Name of Reminder",required=True)
    anaesthesia_type_ids = fields.Many2many("anaesthesia.type", string="Associated with Anaesthesia Types",copy=False)
    medication_id = fields.Many2one("res.medication", string="Associated with Medication")
    medication_class_id = fields.Many2one("res.medication", string="Associated with Medication Class")
    reminder_hour = fields.Integer("Number of Days before Procedure")
    preparation_steps = fields.Html("Preparation Steps")
    created_by = fields.Selection([('admin', 'Admin'), ('doctor', 'Doctor')], string="Created By")
    # anaesthesia_type_id = fields.Many2one("anaesthesia.type", string="Associated Anaesthesia Type",copy=False)
    # patient_case_id = fields.Many2one("patient.case", string="Associated Patient Case",copy=False)
    user_id = fields.Many2one("res.users", string="Created User",copy=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['created_by'] = self.env.user.partner_id.user_type
            vals['user_id'] = self.env.user.id
        records = super().create(vals_list)
        for record in records:
            if record.anaesthesia_type_ids:
                for anaesthesia in record.anaesthesia_type_ids:
                    line_vals = {
                        'reminder_id': record.id,
                        'anaesthesia_id': anaesthesia.id,
                        'name': record.name,
                        'reminder_hour': record.reminder_hour,
                        'preparation_steps': record.preparation_steps,
                    }
                    self.env['res.reminder.line'].sudo().create(line_vals)
        return records
    
    def write(self, vals):
        res = super(ReminderSetup, self).write(vals)
        if 'anaesthesia_type_ids' in vals:
            for record in self:
                if record.anaesthesia_type_ids:
                    for anaesthesia in record.anaesthesia_type_ids:
                        existing_line = self.env['res.reminder.line'].sudo().search([
                            ('reminder_id', '=', record.id),
                            ('anaesthesia_id', '=', anaesthesia.id)
                        ], limit=1)
                        
                        if not existing_line:
                            line_vals = {
                                'reminder_id': record.id,
                                'anaesthesia_id': anaesthesia.id,
                                'name': record.name,
                                'reminder_hour': record.reminder_hour,
                                'preparation_steps': record.preparation_steps,
                            }
                            self.env['res.reminder.line'].sudo().create(line_vals)
    
        return res
    

class ReminderLineSetup(models.Model):
    _name = 'res.reminder.line'

    reminder_id = fields.Many2one("res.reminder", string="Associated Reminder")
    anaesthesia_id = fields.Many2one("anaesthesia.type", string="Associated Anaesthesia")
    name = fields.Char("Name")
    reminder_hour = fields.Integer("Number of Days before Procedure")
    operation_hour = fields.Integer("Number of Hours before Procedure")
    preparation_steps = fields.Html("Preparation Steps")
    patient_case_id = fields.Many2one("patient.case", string="Associated Patient Case",copy=False)
    
    @api.onchange('reminder_id')
    def _onchange_reminder_id(self):
        if self.reminder_id:
            self.name = self.reminder_id.name
            self.reminder_hour = self.reminder_id.reminder_hour
            self.preparation_steps = self.reminder_id.preparation_steps
        else:
            self.name = False
            self.reminder_hour = 0
            self.preparation_steps = False
            
    def action_formatted_datetime(self):
        if self.preparation_steps and self.patient_case_id:
            if self.operation_hour >= 0:
                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_op_date = pytz.utc.localize(self.patient_case_id.op_date).astimezone(user_tz)
                operation_time = local_op_date - timedelta(hours=self.operation_hour)
                formatted_time = operation_time.strftime('%d/%m/%Y %I:%M %p')
                self.preparation_steps = f"{self.preparation_steps} {formatted_time}."

    def get_prep_steps(self,case_id):
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        local_op_date = pytz.utc.localize(case_id.op_date).astimezone(user_tz)
        formatted_time = local_op_date.strftime('%d/%m/%Y %I:%M %p')
        match = str(self.preparation_steps).split('@')
        formatted_prep = str(self.preparation_steps)
        if '@' in str(self.preparation_steps):
            if 'operation_datetime' in match[1]:
                formatted_prep = f"{match[0]} {formatted_time}"
            fetch_number = re.findall("\d+", match[1])
            if 'hrs'in match[1] and fetch_number:
                hours_to_subtract = int(fetch_number[0])
                operation_time = local_op_date - timedelta(hours=hours_to_subtract)
                formatted_time = operation_time.strftime('%d/%m/%Y %I:%M %p')
                formatted_prep = f"{match[0]} {formatted_time}"
            if 'days'in match[1] and fetch_number:
                days_to_subtract = int(fetch_number[0])
                operation_time = local_op_date - timedelta(days=days_to_subtract)
                formatted_time = operation_time.strftime('%d/%m/%Y %I:%M %p')
                formatted_prep = f"{match[0]} {formatted_time}"
        formatted_prep = formatted_prep.replace("<p>","")
        return formatted_prep
    
class MailThreadInht(models.AbstractModel):
    _inherit = 'mail.thread'
    
    def _message_auto_subscribe_notify(self, partner_ids, template):
        """ Notify new followers, using a template to render the content of the
        notification message. Notifications pushed are done using the standard
        notification mechanism in mail.thread. It is either inbox either email
        depending on the partner state: no user (email, customer), share user
        (email, customer) or classic user (notification_type)

        :param partner_ids: IDs of partner to notify;
        :param template: XML ID of template used for the notification;
        """
        if not self or self.env.context.get('mail_auto_subscribe_no_notify'):
            return
        if not self.env.registry.ready:  # Don't send notification during install
            return

        for record in self:
            model_description = self.env['ir.model']._get(record._name).display_name
            company = record.company_id.sudo() if 'company_id' in record else self.env.company
            values = {
                'access_link': record._notify_get_action_link('view'),
                'company': company,
                'model_description': model_description,
                'object': record,
            }
            assignation_msg = self.env['ir.qweb']._render(template, values, minimal_qcontext=True)
            assignation_msg = self.env['mail.render.mixin']._replace_local_links(assignation_msg)
            
            # record.message_notify(
            #     subject=_('You have been assigned to %s', record.display_name),
            #     body=assignation_msg,
            #     partner_ids=partner_ids,
            #     record_name=record.display_name,
            #     email_layout_xmlid='mail.mail_notification_layout',
            #     model_description=model_description,
            # )