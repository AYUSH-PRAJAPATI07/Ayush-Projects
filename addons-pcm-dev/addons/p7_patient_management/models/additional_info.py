from odoo import api, fields, models, _


class AdditionaInformation(models.Model):
    _name = "additional.information"
    _description = "Additional Information"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char()
    explanation = fields.Html()
    created_by = fields.Selection([("admin", _("Admin")), ("doctor", _("Doctor"))], string="Created By")
    user_id = fields.Many2one("res.users", string="Created User", copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        user_type = self.env.user.partner_id.user_type
        user_id = self.env.user.id

        for vals in vals_list:
            vals['created_by'] = user_type
            vals['user_id'] = user_id

        return super().create(vals_list)
