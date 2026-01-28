from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)
class SetupLocation(models.Model):
    _name = 'res.location'
    _description = 'Setup Operation Locations'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char("Name of Location",required=True)
    created_by = fields.Selection([('admin', 'Admin'), ('doctor', 'Doctor')], string="Created By")
    user_id = fields.Many2one("res.users", string="Created User",copy=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['created_by'] = self.env.user.partner_id.user_type
            vals['user_id'] = self.env.user.id
        return super().create(vals_list)