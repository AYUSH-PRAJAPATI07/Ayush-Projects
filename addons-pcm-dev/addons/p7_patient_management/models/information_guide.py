from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from lxml.html import fromstring
import logging

_logger = logging.getLogger(__name__)
class PatientInformationGuide(models.Model):
    _name = 'information.guide'
    _description = 'Information Guide'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    reference_type = fields.Selection([('reference', 'Reference Guide'), ('personal', 'Doctor Guide')], string="Guide Type")
    name = fields.Char("Name",required=True)
    state = fields.Selection(selection=[('draft', 'Draft'),('release', 'Released'),],string='Status',required=True,readonly=True,default='draft',copy=False,tracking=True)
    version = fields.Char(string='Version',tracking=True)
    released_date = fields.Date("Release Date",tracking=True)
    created_by = fields.Selection([('admin', 'Admin'), ('doctor', 'Doctor')], string="Created By",tracking=True)
    anaesthesia_type_ids = fields.Many2many("anaesthesia.type", string="Anaesthesia Options")
    welcome_msg = fields.Html("Welcome Message")
    anaesthesia_intro = fields.Html("Introduction to Anaesthesia")
    close_msg = fields.Html("Closing Message")
    check_clos_msg = fields.Boolean("Check Closing Message", default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['created_by'] = self.env.user.partner_id.user_type
            vals['reference_type'] = 'reference' if self.env.user.partner_id.user_type == 'admin' else 'personal'
        return super().create(vals_list)
    
    @api.onchange('close_msg')
    def _onchange_closing_msg(self):
        if self.close_msg:
            tree = fromstring(self.close_msg)
            filtered_msg = tree.text_content().strip()
            if not filtered_msg:
                self.check_clos_msg = False
            else:
                self.check_clos_msg = True
    
    def create_personel_guide(self):
        self.ensure_one()
        for record in self:
            new_record = record.copy()
            new_record.write({
                'reference_type': 'personal',
                'state': 'draft',
                'version': "",
                'released_date': False,
                'created_by': 'doctor',
            })
        action = self.env.ref('p7_patient_management.action_information_guides_personel').read()[0]
        if self.env.user.partner_id.user_type == 'admin':
            action = self.env.ref('p7_patient_management.action_information_guides_all_doctor').read()[0]
        _logger.info('--------record duplicated-----')
        return action
        
    def finalise(self):
        if not self.version:
            raise ValidationError(_('Please enter valid version number!'))
        self.write({'state':'release','released_date': fields.Date.today()})
        self._message_log(body=_(
                            "Guide Released.\n"
                            "Version: %s",self._get_html_link(title=f" {self.version}")
                        ))
    
    def reset_to_draft(self):
        self.state = 'draft'
        
class PatientInformationCaseGuide(models.Model):
    _name = 'information.guide.case'
    _description = 'Patient Case Information Guide'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char("Name",required=True)
    version = fields.Char(string='Version',tracking=True)
    anaesthesia_type_ids = fields.Many2many("anaesthesia.type", string="Anaesthesia Options")
    welcome_msg = fields.Html("Welcome Message")
    anaesthesia_intro = fields.Html("Introduction to Anaesthesia")
    close_msg = fields.Html("Closing Message")
    check_close_msg = fields.Boolean("Check Close Message", default=False)
    patient_case_id = fields.Many2one('patient.case', string="Case Id", tracking=True)
    guide_id = fields.Many2one('information.guide', string="Guide Id", tracking=True)
    state = fields.Selection(selection=[('draft', 'Draft'),('sent', 'Sent')],string='Status', default='draft')
    additional_info_ids = fields.Many2many("additional.information", string="Additional Information (Optional)", copy=False)

    def action_open_guide_preview(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/guide/preview/%s' % self.id,
            'target': 'new',
        }

    def write(self, vals):
        res = super(PatientInformationCaseGuide, self).write(vals)
        if "additional_info_ids" in vals and not self.env.context.get("skip_addition_info_update"):
            self.patient_case_id.with_context(skip_addition_info_update=True).additional_info_ids = [(6, 0, self.additional_info_ids.ids)]
            self.patient_case_id.medic_answer_id.with_context(skip_addition_info_update=True).additional_info_ids = [(6, 0, self.additional_info_ids.ids)]
        return res
