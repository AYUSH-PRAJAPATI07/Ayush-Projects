import base64
import functools
import re
import os
import pyotp

from odoo import _, api, fields, models
from odoo.http import request
from odoo.exceptions import UserError
import logging

from odoo.addons.auth_totp.models.totp import TOTP, TOTP_SECRET_SIZE
compress = functools.partial(re.sub, r'\s', '')

_logger = logging.getLogger(__name__)

class Custom2FAWizard(models.TransientModel):
    _inherit = 'auth_totp.wizard'

    @api.model
    def create_2fa_wizard(self, user_id):
        """ Generates the 2FA secret and QR Code """
        user = self.env['res.users'].browse(user_id)
        secret_bytes_count = TOTP_SECRET_SIZE // 8
        secret = base64.b32encode(os.urandom(secret_bytes_count)).decode()
        # format secret in groups of 4 characters for readability
        secret = ' '.join(map(''.join, zip(*[iter(secret)]*4)))

        return self.create({
            'user_id': user.id,
            'secret': secret,
        })
        
    # def enable_2fa(self):
    #     """ Final step where the user enters the OTP """
    #     try:
    #         c = int(compress(self.code))
    #     except ValueError:
    #         raise UserError(_("The verification code should only contain numbers"))
        
    #     if self.user_id._totp_try_setting(self.secret, c):
    #         self.secret = ''
    #         return True
    #     return False
    
    def enable_2fa(self):
        """ Final step where the user enters the OTP """
        try:
            user = self.user_id
            otp = self.code.replace(' ', '').strip()
            totp = pyotp.TOTP(self.secret.replace(' ', '').strip())
            if totp.verify(otp):
                # Mark TOTP as enabled and store secret
                user.totp_enabled = True
                user.totp_secret = self.secret.replace(' ', '')
                return True
        except Exception as e:
            _logger.exception("2FA verification failed")
        return False