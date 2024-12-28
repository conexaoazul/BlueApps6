{
    'name': 'Blue Notification',
    'version': '17.0.1.0.0',
    'category': 'Tools',
    'summary': 'Email notifications for Helpdesk updates',
    'sequence': 1,
    'author': 'OpenHands',
    'website': 'https://www.conexaoazuldigital.com.br',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'helpdesk',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/email_template.xml',
        'views/helpdesk_notification_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}