# -*- coding: utf-8 -*-
from odoo import api, fields, models


class IrAttachment(models.Model):
	_inherit = 'ir.attachment'

	ajax_uploaded_file = fields.Boolean('Ajax Uploaded File', default=False)