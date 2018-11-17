# -*- coding: utf-8 -*-
{
    'active': False,
    'author': u'Blanco Martín & Asociados',
    'website': 'http://blancomartin.cl',
    'category': 'Localization/Chile',
    'demo_xml': [
       # 'data/partner_demo.xml',
      ],
    'depends': [   
        'account',
        'account_accountant',
        'l10n_cl_chart',
        'l10n_cl_base_rut',
        'l10n_cl_partner_activities',
        'decimal_precision'
        ],
    'description': u'''


Módulo de Facturación de la localización Chilena.


Incluye:
- Configuración de libros, diarios (journals) y otros detalles para facturación para Chile.
- Asistente para configurar los talonarios de facturas, boletas, guías de despacho, etc.
''',
    'init_xml': [],
    'installable': True,
    'license': 'AGPL-3',
    'name': u'Chile - Sistema de apoyo a la facturación',
    'data': [
        'data/document_type.xml',
        'security/l10n_cl_invoice_security.xml',
        'data/responsability.xml',
        'data/sii_document_letter_data.xml',
        'data/sii_document_class_data.xml',
        'data/partner.xml',
        'data/country.xml',
        'data/sii.concept_type.csv',
        'data/decimal_precision_data.xml',
        'wizard/journal_config_wizard_view.xml',
        'views/company_view.xml',
        'views/country_view.xml',
        'views/sii_document_letter_view.xml',
        'views/sii_concept_type_view.xml',
        'views/sii_optional_type_view.xml',
        'views/sii_document_type_view.xml',
        'views/sii_responsability_view.xml',
        'views/sii_document_class_view.xml',
        'views/sii_point_of_sale_view.xml',
        'views/account_journal_sii_document_class_view.xml',
        'views/partner_view.xml',
        'views/journal_view.xml',
        'views/invoice_view.xml',
        'views/product_view.xml',
        'views/account_move_view.xml',
        'views/account_move_line_view.xml',
        'views/config_view.xml',
        'views/currency_view.xml',
        # 'views/report_invoice.xml',
        'security/ir.model.access.csv',
        'security/l10n_cl_invoice_security.xml',
        'data/res.currency.csv',
        # 'views/sii_menuitem.xml',
    ],
    'version': '8.0.1.0.0',
}
