from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)
class AnaesthesiaSetup(models.Model):
    _name = 'anaesthesia.type'
    _description = 'Anaesthesia Setup'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char("Name of Anaesthesia",required=True)
    explanation = fields.Html("Explanation")
    preparation_steps = fields.Html("Preparation Steps")
    date_updated = fields.Datetime("Date Updated")
    created_by = fields.Selection([('admin', 'Admin'), ('doctor', 'Doctor')], string="Created By")
    reminder_ids = fields.One2many('res.reminder.line', 'anaesthesia_id', string='Reminders',copy=False)
    user_id = fields.Many2one("res.users", string="Created User",copy=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['date_updated'] = fields.Datetime.now()
            vals['created_by'] = self.env.user.partner_id.user_type
            vals['user_id'] = self.env.user.id
        return super().create(vals_list)
    
    def write(self, vals):
        vals.update({'date_updated': fields.Datetime.now()})
        return super(AnaesthesiaSetup, self).write(vals)
    

class AnaesthesiaLineSetup(models.Model):
    _name = 'anaesthesia.type.line'

    anaesthesia_id = fields.Many2one("anaesthesia.type", string="Associated Anaesthesia")
    name = fields.Char("Name")
    date_updated = fields.Datetime("Date Updated")
    explanation = fields.Html("Explanation")
    preparation_steps = fields.Html("Preparation Steps")
    patient_case_id = fields.Many2one("patient.case", string="Associated Patient Case",copy=False)
    
    @api.onchange('anaesthesia_id')
    def _onchange_anaesthesia_id(self):
        if self.anaesthesia_id:
            self.name = self.anaesthesia_id.name
            self.date_updated = fields.Datetime.now()
            self.explanation = self.anaesthesia_id.explanation
            self.preparation_steps = self.anaesthesia_id.preparation_steps
        else:
            self.name = False
            self.date_updated = False
            self.explanation = False
            self.preparation_steps = False