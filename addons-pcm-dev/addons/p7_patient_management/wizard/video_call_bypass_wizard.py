from odoo import models, fields, _
from odoo.exceptions import UserError

class VideoCallBypassWizard(models.TransientModel):
    _name = 'video.call.bypass.wizard'
    _description = 'Video Call Bypass Wizard'

    user_input_id = fields.Many2one('survey.user_input', required=True, readonly=True)
    reason = fields.Text('Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        # extra safety (UI should enforce required anyway)
        if not (self.reason or '').strip():
            raise UserError(_("Please provide a reason."))
        # guard in case case_id is missing
        case = self.user_input_id.case_id
        if not case:
            raise UserError(_("No related patient case found for this survey entry."))
        case.medic_answer_id.bypass_reason = self.reason
        case.medic_answer_id.video_call_status = 'bypassed'
        case.medic_answer_id._message_log(body=_("Video call bypassed Successfully."))
        case.video_call_status = 'bypassed'
        case._message_log(body=_("Video call bypassed Successfully."))
        admin_group = self.env.ref('p7_patient_management.group_user_admin', raise_if_not_found=False)
        if admin_group:
            for admin in admin_group.users.filtered(lambda u: u.email):
                self.env['mail.mail'].sudo().create({
                    'auto_delete': False,
                    'email_to': admin.email,
                    'subject': _('ATTENTION!! - VIDEO CALL BYPASSED'),
                    'body_html': (
                        f"<p>Doctor {self.env.user.name} bypassed the video call for case {case.name}.</p>"
                        f"<p>Bypass Reason: {self.reason}</p>"
                    ),
                }).send()
        return {'type': 'ir.actions.act_window_close'}