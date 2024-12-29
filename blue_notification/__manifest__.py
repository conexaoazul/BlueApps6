{
    'name': 'Blue Notification',
    'version': '17.0.1.1.0',
    'category': 'Tools',
    'summary': 'Sistema avançado de notificações e engajamento para Helpdesk',
    'sequence': 1,
    'author': 'OpenHands',
    'website': 'https://www.conexaoazuldigital.com.br',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'helpdesk',
        'gamification',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/email_template.xml',
        'data/gamification_data.xml',
        'views/helpdesk_notification_views.xml',
        'views/helpdesk_team_dashboard.xml',
        'views/helpdesk_agent_performance.xml',
        'reports/helpdesk_analysis.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'blue_notification/static/src/js/dashboard.js',
            'blue_notification/static/src/scss/dashboard.scss',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'description': """
Sistema Avançado de Notificações e Engajamento para Helpdesk
===========================================================

Principais funcionalidades:
--------------------------
* Dashboard em tempo real para equipes
* Sistema de gamificação e recompensas
* Relatórios detalhados de performance
* Notificações personalizadas por equipe
* Métricas de SLA e satisfação do cliente
* Integração com recursos humanos
* Sistema de metas e objetivos
    """
}