from datetime import datetime, timedelta
from odoo import models, fields, api

class HelpdeskNotification(models.Model):
    _name = 'helpdesk.notification'
    _description = 'Helpdesk Notification Settings'

    manager_email = fields.Char(string='Manager Email', required=True)
    last_execution = fields.Datetime(string='Last Execution Time')

    @api.model
    def _send_daily_update(self):
        yesterday = fields.Datetime.now() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59)

        # Get all tickets updated yesterday
        tickets = self.env['helpdesk.ticket'].search([
            ('write_date', '>=', yesterday_start),
            ('write_date', '<=', yesterday_end)
        ])

        if not tickets:
            return

        # Get notification settings
        settings = self.search([], limit=1)
        if not settings or not settings.manager_email:
            return

        # Prepare ticket information
        ticket_info = []
        for ticket in tickets:
            ticket_info.append({
                'name': ticket.name,
                'number': ticket.number,
                'stage': ticket.stage_id.name,
                'last_update': fields.Datetime.to_string(ticket.write_date),
                'priority': ticket.priority,
            })

        # Send email using template
        template = self.env.ref('blue_notification.email_template_helpdesk_daily_update')
        template.with_context(
            ticket_info=ticket_info,
            date=fields.Date.to_string(yesterday)
        ).send_mail(
            settings.id,
            force_send=True,
            email_values={'email_to': settings.manager_email}
        )

        # Update last execution time
        settings.write({'last_execution': fields.Datetime.now()})