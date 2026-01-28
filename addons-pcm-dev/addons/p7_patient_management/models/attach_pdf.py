from odoo import models, fields, api
import base64
from pdf2image import convert_from_bytes
from PIL import Image
import io
 
class IrAttachmentUpdate(models.Model):
    _inherit = 'ir.attachment'
 
    pdf_image_ids = fields.One2many('ir.attachment.pdf.image', 'attachment_id', string="PDF Images", compute="_compute_pdf_images", store=False)
 
    @api.depends('datas', 'mimetype')
    def _compute_pdf_images(self):
        for record in self:
            record.pdf_image_ids = [(5, 0, 0)]  # clear existing
            if record.ajax_uploaded_file and record.mimetype == "application/pdf":
                try:
                    pdf_binary_data = base64.b64decode(record.datas)
                    images = convert_from_bytes(pdf_binary_data, dpi=90)
 
                    image_records = []
                    for img in images:
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format="PNG")
                        image_data = base64.b64encode(img_byte_arr.getvalue())
 
                        image_records.append((0, 0, {
                            'image_data': image_data,
                        }))
                    record.pdf_image_ids = image_records
                except Exception:
                    record.pdf_image_ids = []
                    
class IrAttachmentPdfImage(models.Model):
    _name = 'ir.attachment.pdf.image'
    _description = 'PDF Page Image for Attachment'
 
    attachment_id = fields.Many2one('ir.attachment', ondelete='cascade')
    image_data = fields.Binary("Page Image", attachment=True)