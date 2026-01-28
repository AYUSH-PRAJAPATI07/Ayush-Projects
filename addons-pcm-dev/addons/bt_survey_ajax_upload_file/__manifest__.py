# -*- coding: utf-8 -*-
######################################################################################
#
#    BanasTech.com
#
#    Copyright (C) 2021-TODAY BanasTech.com(<https://www.banastech.com>).
#    Author: BanasTech.com (inquiry@banastech.com)
#
#    This program is under the terms of the Odoo Proprietary License v1.0 (OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the Software
#    or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
########################################################################################

{
    "name": "Survey File Upload - Ajax",
    "version": '17.0.1.0.2',
    'author': 'Banas Tech Private Limited',
    'website':  "https://www.banastech.com",
    "category": "Website",
    'summary': """Survey Multi File Upload Using Ajax""",
    'description': """""",
    "depends": [
        'survey',
        'bt_ajax_upload_file_common',
    ],
    "data": [
        'views/assets.xml',
        'views/survey_question_views.xml',
        'views/survey_question_templates.xml',
    ],
    'demo': [
    ],
    "license": "OPL-1",
    'price': 0.0,
    'currency': 'USD',
    'images': [
        'static/description/banner.png'
    ],
    'assets': {
        'survey.survey_assets': [
            '/bt_survey_ajax_upload_file/static/src/js/survey_form.js',
            '/bt_survey_ajax_upload_file/static/src/js/survey_print.js',
        ],
    },
    'auto_install': False,
    'installable': True,
    'application': True,
}
