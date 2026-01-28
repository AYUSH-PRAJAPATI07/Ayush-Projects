from odoo import models, fields, api

class SurveyConfirmPopup(models.TransientModel):
    _name = 'survey.confirm.popup'
    _description = 'Confirm Info Guide Popup'

    user_input_id = fields.Many2one('survey.user_input', string='Survey Entry')
    inform_guide_id = fields.Many2one('information.guide', string='Selected Info Guide')
    case_guide_id = fields.Many2one('information.guide.case', string='Selected Info Guide Case')

    def confirm_action(self):
        self.user_input_id.case_id.write({
            'inform_guide_id': self.inform_guide_id.id,
            'case_tier': 'premium',
            'case_guide_id': self.case_guide_id.id,
        })
        self.user_input_id.write({'case_guide_state':'update'})
        # make normal doctor a premium doctor
        if self.env.user.has_group("p7_patient_management.group_user_doctor"):
            group_premium_doctor = self.env.ref("p7_patient_management.group_user_doctor_premium", raise_if_not_found=False)
            if group_premium_doctor:
                group_premium_doctor.sudo().write({"users": [(4, self.env.user.id)]})
                return {
                    "type": "ir.actions.client",
                    "tag": "reload"
                }
        return {'type': 'ir.actions.act_window_close'}

    def cancel_action(self):
        return {'type': 'ir.actions.act_window_close'}