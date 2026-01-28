from odoo import models, fields, api, _
import logging
import os
import requests
import json
import zipfile
from psycopg2.extras import execute_values
from datetime import datetime
import ijson

_logger = logging.getLogger(__name__)
class MedicalDetails(models.Model):
    _name = 'res.medication'
    _description = 'Medication Details'
    _rec_names_search = ['name', 'brand_name']
    
    name = fields.Char("Name")
    brand_name = fields.Char("Brand Name")
    pharma_name = fields.Char("Pharmacological Class")
    ingredient_name = fields.Char("Active Ingredient")
    descrip = fields.Char("Description")
    medication_id = fields.Many2one(
        'res.medication.update', 'Medication Name',
        copy=False)
    user_id = fields.Many2one('res.users', 'User', copy=False)
    
    @api.model
    def update_medication_data(self):
        records = self.env['res.medication'].sudo().search([('user_id','=',False)])
        prev_count = 0
        if records:
            prev_count = len(records)
            records.unlink()
        param_obj = self.env['ir.config_parameter'].sudo()
        urls = param_obj.get_param('download_urls')
        download_dir = param_obj.get_param('medication_path',)
            
        download_urls = json.loads(urls) if urls else []
        
        for url in download_urls:
            file_name = url.split('/')[-1]
            file_path = os.path.join(download_dir, file_name)
            try:
                with requests.get(url, stream=True, timeout=60) as response:
                    if response.status_code == 200:
                        with open(file_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        print(f"Downloaded: {file_path}")
                    else:
                        print(f"Failed to download: {url}")
                        continue

                # Extract the zip file
                if file_name.endswith('.zip'):
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(download_dir)
                    os.remove(file_path)

            except requests.exceptions.Timeout:
                _logger.info("Timed Out")
            except requests.exceptions.RequestException as e:
                _logger.info(f"Error downloading {url}: {e}")
            except zipfile.BadZipFile:
                _logger.info(f"Corrupt zip file: {file_path}")
        # Process the extracted JSON files
        for filename in os.listdir(download_dir):
            if filename.endswith('.json'):
                json_path = os.path.join(download_dir, filename)
                self._import_medication_data(json_path)
                os.remove(json_path)
                _logger.info(f"Processed and deleted: {json_path}")
        
        new_records = self.env['res.medication'].sudo().search([('user_id','=',False)])
        count = len(new_records)
        self.env['res.medication.update'].sudo().create({
                'name': "New Update",
                'date_update': fields.Date.today(),
                'rec_total': count,
                'new_rec_total': count - prev_count,
            })
    
    def _import_medication_data(self, json_path):
        medication_data = []
        now = datetime.today()

        with open(json_path, 'rb') as json_file:
            records = ijson.items(json_file, 'results.item')
            for record in records:
                name = record.get('openfda', {}).get('generic_name', ['Unknown'])[0]
                brand_name = record.get('openfda', {}).get('brand_name', ['Unknown'])[0]
                descrip = record.get('description', [''])[0]
                ingredient_name = record.get('openfda', {}).get('substance_name', ['Unknown'])[0]
                pharma_name = record.get('openfda', {}).get('pharm_class_cs', ['Unknown'])[0]

                if not name or name == 'Unknown':
                    continue

                medication_data.append((name, brand_name, descrip, ingredient_name, pharma_name, now, now))

                if len(medication_data) >= 1000:
                    self._bulk_insert(medication_data)
                    medication_data.clear()

        if medication_data:
            self._bulk_insert(medication_data)
            
    def _bulk_insert(self, data):
        insert_query = """
            INSERT INTO res_medication (name, brand_name, descrip, ingredient_name, pharma_name, create_date, write_date) 
            VALUES %s
        """
        execute_values(self.env.cr._obj, insert_query, data)
    
class MedicalUpdateDetails(models.Model):
    _name = 'res.medication.update'
    _description = 'Medication Update History'
    
    name = fields.Char("Medication Dataset Update", default="Dataset")
    date_update = fields.Date("Updated On")
    rec_total = fields.Integer("Total Records")
    new_rec_total = fields.Integer("Total of New Records")
    medication_ids = fields.One2many('res.medication', 'medication_id',string="List of new Medications")
    
class VerificationFaq(models.Model):
    _name = 'res.faq'
    _description = 'Verification FAQs'
    
    name = fields.Char("Question")
    value = fields.Char("Answer")
    sequence = fields.Integer("Sequence")
    
class MailUpdate(models.Model):
    _inherit = 'mail.mail'
    
    is_custom_log = fields.Boolean("Mail log", default=False)
    
class SmsUpdate(models.Model):
    _inherit = 'sms.sms'
    
    is_custom_log = fields.Boolean("sms log", default=False)