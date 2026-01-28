from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ContactAttempt(models.Model):
    """Track an associate's contact attempt."""

    _name = 'contact.attempt'
    _description = 'Contact Attempt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "name"

    name = fields.Char(
        string="Reference",
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    case_id = fields.Many2one('patient.case', string='Patient Case', tracking=True)
    case_backend_id = fields.Char(
        string="Master ID",
        compute="_compute_case_backend_value",
        store=True,
        readonly=True,
    )
    booking_id = fields.Char(
        related='case_id.name',
        string='Booking ID',
        store=True,
        readonly=True,
    )
    doctor_id = fields.Many2one(
        'res.users',
        related='case_id.create_uid',
        string='Doctor Full Name',
        store=True,
        readonly=True,
    )
    op_date = fields.Datetime(
        related='case_id.op_date',
        string='Operation Date/Time',
        store=True,
        readonly=True,
    )
    case_tier = fields.Selection(
        related='case_id.case_tier',
        string="Case Tier",
        store=True,
        readonly=True,
    )
    associate_id = fields.Many2one('res.users', string='Associate', tracking=True)
    video_call_datetime = fields.Datetime(string='Attempt DateTime', default=fields.Datetime.now,
                                    tracking=True, required=True)
    last_attempt_datetime = fields.Datetime(
        string='Last Contact Attempt',
        readonly=True,
        copy=False,
    )
    contact_channel = fields.Selection(
        [
            ("sms", "SMS"),
            ("whatsapp", "WhatsApp Message"),
            ("phone", "Phone Call"),
            ("video", "Video Call"),
        ],
        groups="p7_patient_management.group_user_associate",
        string="Contact Channel",
    )
    video_call_location = fields.Char(
        "Patient's Physical Location",
        groups="p7_patient_management.group_user_associate",
    )
    video_call_contents = fields.Text(
        "Contents",
        default="The patient was introduced to the purpose and functions of the Virtual Anaesthesia Assessment (VANAESA) platform.",
        groups="p7_patient_management.group_user_associate",
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
    video_call_fail_count = fields.Integer(string="Fail Count", default=0)
    attempt_count = fields.Integer("Attempt Count", compute='_compute_attempt_count', store=True)
    user_input_id = fields.Many2one('survey.user_input', string='Survey Entry')
    patient_id = fields.Many2one('res.partner', string='Patient')
    patient_first_name = fields.Char(string='First Name')
    patient_last_name = fields.Char(string='Last Name')
    patient_phone_code = fields.Char(string='Phone Code', size=8)
    patient_mob = fields.Char(string='Mobile')
    patient_nric_number = fields.Char(string='NRIC')
    patient_gender = fields.Selection(
        [('male', 'Male'), ('female', 'Female')],
        string='Gender'
    )
    patient_dob = fields.Date(string='Date of Birth')

    @api.depends('case_id.case_backend_id')
    def _compute_case_backend_value(self):
        for rec in self:
            rec.case_backend_id = rec.case_id.case_backend_id

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('contact.attempt.seq') or _('New')
        return super(ContactAttempt, self).create(vals)

    @api.depends('video_call_fail_count', 'video_call_status')
    def _compute_attempt_count(self):
        # Attempts = number of failed tries + 1 if there is a success
        for r in self:
            r.attempt_count = (r.video_call_fail_count or 0) + (1 if r.video_call_status == 'success' else 0)

    # ——— Actions ———

    def _whats_app_number(self):
        self.ensure_one()
        code = (self.patient_phone_code or '').lstrip('+').strip()
        mob = (self.patient_mob or '').strip()
        if not code or not mob:
            raise UserError(_("Missing phone code or mobile."))
        return f"{code}{mob}"

    def action_whatsapp_call(self):
        url = f"https://wa.me/{self._whats_app_number()}?video=true"
        return {'type': 'ir.actions.act_url', 'target': 'new', 'url': url}

    def action_whatsapp_message(self):
        url = f"https://wa.me/{self._whats_app_number()}"
        return {'type': 'ir.actions.act_url', 'target': 'new', 'url': url}

    def _dt_strings_for_user(self, dt_utc):
        """
        Return (date_str, time_str) converted to the current user's timezone.
        """
        # context_timestamp returns an aware datetime in the user's tz
        local_dt = fields.Datetime.context_timestamp(self, dt_utc)
        return local_dt.strftime('%d/%m/%Y'), local_dt.strftime('%H:%Mhrs')

    def _compose_log_body(self, record, default_contents):
        """Build the chatter message body with tz-correct times."""
        # ensure dt is set
        dt_utc = record.video_call_datetime or fields.Datetime.now()
        date_str, time_str = self._dt_strings_for_user(dt_utc)

        channel_label = dict(self._fields['contact_channel'].selection).get(
            record.contact_channel, 'contact'
        )
        associate = (
            record.associate_id.name
            if record.video_call_performed_by == 'associate' and record.associate_id
            else self.env.user.name
        )
        patient_name = f"{record.patient_first_name or ''} {record.patient_last_name or ''}".strip()

        if record.contact_channel in ('sms', 'whatsapp'):
            body = (
                f"On {date_str} at {time_str}, a {channel_label} was sent from {associate} to {patient_name}. "
                f"The patient's location was established to be {record.video_call_location or _('N/A')}. "
                f"{record.video_call_contents or default_contents}"
            )
        else:
            body = (
                f"On {date_str} at {time_str}, a {channel_label} was made between the patient and {associate}. "
                f"The {patient_name}'s location was established to be {record.video_call_location or _('N/A')}. "
                f"{record.video_call_contents or default_contents}"
            )
        return body

    def action_take_video_call(self):
        for attempt in self:
            user = self.env.user

            if attempt.user_input_id and getattr(attempt.user_input_id, 'case_id', False):
                attempt.case_id = attempt.user_input_id.case_id

            # claim the attempt
            attempt.sudo().write({
                'associate_id': user.id,
                'video_call_assign_status': 'assigned',
                'video_call_status': 'assigned',
                'video_call_performed_by': 'associate',
            })

            if attempt.user_input_id:
                attempt.user_input_id.sudo().write({
                    'associate_id': user.id,
                    'video_call_assign_status': 'assigned',
                    'video_call_status': 'assigned',
                    'video_call_performed_by': 'associate',
                })

            if attempt.case_id:
                attempt.case_id.sudo().write({
                    'video_call_assign_status': 'assigned',
                    'video_call_status': 'assigned',
                })
                # ← use sudo() here to bypass mail.message create ACLs
                attempt.case_id.sudo().message_post(
                    body=_('Associate %s took the booking') % user.name
                )

    def action_video_call_complete(self):
        """Finalize this attempt, increment fail count (up to 3), and log a message on the case.

        Behavior preserved from your previous case-level function:
        - Require outcome
        - Log a human-readable note
        - On success → mark success
        - On failure → increment fail count; after 3 fails → mark failed and notify admins;
                       otherwise reset key fields and keep the attempt In Progress
        """
        default_contents = (
            "The patient was introduced to the purpose and functions of the Virtual Anaesthesia "
            "Assessment (VANAESA) platform."
        )

        for record in self:
            if not record.video_call_outcome:
                raise UserError(_("Please select the outcome of the video call before completing it."))

            # set the attempt timestamp now (UTC) and preserve the previous one
            now_utc = fields.Datetime.now()
            vals = {'video_call_datetime': now_utc}
            if record.attempt_count:
                vals['last_attempt_datetime'] = record.video_call_datetime
            record.write(vals)

            body = self._compose_log_body(record, default_contents)

            # Post everywhere you need
            if record.case_id:
                record.case_id.sudo().message_post(body=body)
                if record.case_id.medic_answer_id:
                    record.case_id.medic_answer_id.sudo().message_post(body=body)
            record.sudo().message_post(body=body)

            if record.video_call_outcome == 'successful':
                # success path
                record.write({'video_call_status': 'success'})
                if record.case_id:
                    record.case_id.sudo().write({
                        'video_call_status': 'success',
                        'video_call_outcome': 'successful',
                        'attempt_count': (record.video_call_fail_count or 0) + 1,
                    })
                    if record.case_id.medic_answer_id:
                        record.case_id.medic_answer_id.sudo().write({
                            'video_call_status': 'success',
                            'video_call_outcome': 'successful',
                            'attempt_count': (record.video_call_fail_count or 0) + 1,
                        })
            else:
                # failure path
                new_fail_count = (record.video_call_fail_count or 0) + 1
                if record.case_id:
                    record.case_id.sudo().write({'attempt_count': new_fail_count})
                    if record.case_id.medic_answer_id:
                        record.case_id.medic_answer_id.sudo().write({'attempt_count': new_fail_count})

                if new_fail_count >= 3:
                    record.write({
                        'video_call_fail_count': new_fail_count,
                        'video_call_status': 'in_progress',
                        'video_call_outcome': 'failed',
                    })
                    if record.case_id:
                        record.case_id.sudo().write({
                            'video_call_status': 'in_progress',
                            'video_call_outcome': 'failed',
                        })
                        if record.case_id.medic_answer_id:
                            record.case_id.medic_answer_id.sudo().write({
                                'video_call_status': 'in_progress',
                                'video_call_outcome': 'failed',
                            })
                    admin_group = self.env.ref('p7_patient_management.group_user_admin', raise_if_not_found=False)
                    if admin_group:
                        case_label = record.case_id.display_name if record.case_id else (record.display_name or _("Attempt"))
                        for admin in admin_group.users.filtered(lambda u: u.email):
                            self.env['mail.mail'].sudo().create({
                                'auto_delete': False,
                                'email_to': admin.email,
                                'subject': _("Video call failed for %s") % case_label,
                                'body_html': _("<p>Video call failed 3 times for case %s.</p>") % case_label,
                            }).send()
                else:
                    record.write({
                        'video_call_fail_count': new_fail_count,
                        'video_call_status': 'in_progress',
                        'video_call_location': False,
                        'video_call_contents': default_contents,
                        'video_call_outcome': False,
                    })

    def action_video_call_success(self):
        for record in self:
            record.write({'video_call_status': 'success'})
            if record.case_id:
                record.case_id.sudo().write({'video_call_status': 'success', 'video_call_outcome': 'successful'})
                record.case_id.medic_answer_id.sudo().write({'video_call_status': 'success', 'video_call_outcome': 'successful'})

    def action_video_call_fail(self):
        for record in self:
            if not record.video_call_location:
                raise UserError(_("Please enter the patient's physical location before completing the video call."))

            now_utc = fields.Datetime.now()
            vals = {'video_call_datetime': now_utc}
            if record.attempt_count:
                vals['last_attempt_datetime'] = record.video_call_datetime
            record.write(vals)

            default_contents = (
                "The patient was introduced to the purpose and functions of the Virtual Anaesthesia "
                "Assessment (VANAESA) platform."
            )
            body = self._compose_log_body(record, default_contents)

            # Log the failed attempt
            if record.case_id:
                record.case_id.sudo().message_post(body=body)
                if record.case_id.medic_answer_id:
                    record.case_id.medic_answer_id.sudo().message_post(body=body)
            record.sudo().message_post(body=body)

            new_fail_count = (record.video_call_fail_count or 0) + 1
            if record.case_id:
                record.case_id.sudo().write({
                    'attempt_count': new_fail_count,
                    'video_call_status': 'failed',
                    'video_call_outcome': 'failed',
                })
                if record.case_id.medic_answer_id:
                    record.case_id.medic_answer_id.sudo().write({
                        'attempt_count': new_fail_count,
                        'video_call_status': 'failed',
                        'video_call_outcome': 'failed',
                    })

            if new_fail_count >= 3:
                record.write({
                    'video_call_fail_count': new_fail_count,
                    'video_call_status': 'failed',
                    'video_call_outcome': 'failed',
                })
                if record.case_id:
                    record.case_id.sudo().write({
                        'video_call_status': 'failed',
                        'video_call_outcome': 'failed',
                    })
                    if record.case_id.medic_answer_id:
                        record.case_id.medic_answer_id.sudo().write({
                            'video_call_status': 'failed',
                            'video_call_outcome': 'failed',
                        })
                admin_group = self.env.ref('p7_patient_management.group_user_admin', raise_if_not_found=False)
                if admin_group:
                    case_label = record.case_id.display_name if record.case_id else (record.display_name or _("Attempt"))
                    for admin in admin_group.users.filtered(lambda u: u.email):
                        self.env['mail.mail'].sudo().create({
                            'auto_delete': False,
                            'email_to': admin.email,
                            'subject': _("Video call failed for %s") % case_label,
                            'body_html': _("<p>Video call failed 3 times for case %s.</p>") % case_label,
                        }).send()
            else:
                record.write({
                    'video_call_fail_count': new_fail_count,
                    'video_call_status': 'failed',
                    'video_call_location': False,
                    'video_call_contents': default_contents,
                    'video_call_outcome': 'failed',
                })

    def action_release_video_call(self):
        for attempt in self:
            if attempt.associate_id != self.env.user:
                continue
            values = {
                'associate_id': False,
                'video_call_assign_status': 'to_assign',
                'video_call_status': 'pending',
            }
            attempt.sudo().write(values)
            if attempt.user_input_id:
                attempt.user_input_id.sudo().write(values)
            if attempt.case_id:
                attempt.case_id.sudo().write({
                    'video_call_assign_status': 'to_assign',
                    'video_call_status': 'pending',
                })
                attempt.case_id.sudo().message_post(
                    body=_('Associate %s released the booking') % self.env.user.name
                )



