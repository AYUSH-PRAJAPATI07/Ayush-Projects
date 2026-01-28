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
    "name": "Ajax Upload File Common",
    "version": '17.0.1.0.2',
    'author': 'Banas Tech Private Limited',
    'website':  "https://www.banastech.com",
    "category": "Tools",
    'summary': """Upload file using ajax on Website.""",
    'description': """
        This Module enabling upload file using ajax on Website.
    """,
    "depends": [
        'website'
    ],
    "data": [
        'views/assets.xml',
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
        'web.assets_frontend': [
            '/bt_ajax_upload_file_common/static/src/css/uploadfile.css',
            '/bt_ajax_upload_file_common/static/src/js/jquery.uploadfile.js',
            '/bt_ajax_upload_file_common/static/src/js/upload.js',
        ],
    },
    'auto_install': False,
    'installable': True,
    'application': True,
}
