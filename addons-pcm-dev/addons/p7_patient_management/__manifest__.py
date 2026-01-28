# -*- coding: utf-8 -*-
{
    'name': "Patient Case Management",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','survey','web','spreadsheet','spreadsheet_dashboard','website','contacts','utm','mail','web_editor'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/user_type_views.xml',
        'views/views.xml',
        'views/survey_views.xml',
        'views/patient_case_views.xml',
        # 'views/survey_user_input_views.xml',
        'views/contact_attempt_views.xml',
        'views/medication_views.xml',
        'views/reminder_views.xml',
        'views/anaesthesia_views.xml',
        'views/dislocation_views.xml',
        'views/location_views.xml',
        'views/information_guide_views.xml',
        'views/template.xml',
        'views/dashboard_template.xml',
        'views/chat_template.xml',
        'views/factor_template.xml',
        'views/faq_template.xml',
        'views/guide_template.xml',
        'views/survey_print_template.xml',
        'views/survey_preview_template.xml',
        'views/survey_template.xml',
        'views/additional_info_views.xml',
        'views/menus.xml',
        'views/favicon.xml',
        'views/menu_items.xml',
        'views/terms_and_conditions_template.xml',
        'data/verification_mail_views.xml',
        'data/patient_case_cron.xml',
        'data/patient_case_sequence.xml',
        'data/patient_case_dashboard.xml',
        'report/download_survey_template.xml',
        'report/download_survey_view.xml',
        'wizard/guide_confirmation_template.xml',
        'wizard/video_call_bypass_wizard_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'survey.survey_assets': [
            'p7_patient_management/static/src/js/repeat_question_view.js',
        ],
        'web.assets_frontend': [
            'p7_patient_management/static/src/scss/patient_management.scss',
        ],
        'web.assets_backend': [
            "p7_patient_management/static/src/js/navbar.js",
            'p7_patient_management/static/src/views/message_custom.xml',
            'p7_patient_management/static/src/js/custom_message.js',
            'p7_patient_management/static/src/scss/patient_case.css',
            ('replace', 'mail/static/src/discuss/core/web/discuss_sidebar_categories.xml', 'p7_patient_management/static/src/discuss/core/web/custom_discuss.xml'),
        ],
        'web_editor.assets_wysiwyg': [
            'p7_patient_management/static/src/js/html_banner_view.js',
        ],
    },
    'license':'LGPL-3',
    'installable': True,
    'application': True,
}

