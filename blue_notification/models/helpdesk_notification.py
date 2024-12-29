from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HelpdeskNotification(models.Model):
    _name = 'helpdesk.notification'
    _description = 'Configurações de Notificação do Helpdesk'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nome da Configuração', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    team_id = fields.Many2one('helpdesk.team', string='Equipe', required=True, tracking=True)
    manager_id = fields.Many2one('res.users', string='Gestor', required=True, tracking=True,
        domain="[('share', '=', False)]")
    manager_email = fields.Char(string='Email do Gestor', required=True, tracking=True)
    team_members = fields.Many2many('res.users', string='Membros da Equipe',
        related='team_id.member_ids', readonly=True)
    
    # Configurações de Notificação
    notification_frequency = fields.Selection([
        ('daily', 'Diário'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensal')
    ], string='Frequência', default='daily', required=True, tracking=True)
    
    include_metrics = fields.Boolean(string='Incluir Métricas', default=True, tracking=True)
    include_team_performance = fields.Boolean(string='Incluir Performance da Equipe', default=True, tracking=True)
    include_individual_stats = fields.Boolean(string='Incluir Estatísticas Individuais', default=True, tracking=True)
    
    # Métricas e Metas
    sla_target = fields.Float(string='Meta de SLA (%)', default=95.0, tracking=True)
    response_time_target = fields.Float(string='Meta de Tempo de Resposta (horas)', default=1.0, tracking=True)
    resolution_time_target = fields.Float(string='Meta de Tempo de Resolução (horas)', default=8.0, tracking=True)
    satisfaction_target = fields.Float(string='Meta de Satisfação (%)', default=90.0, tracking=True)
    
    # Gamificação
    enable_gamification = fields.Boolean(string='Ativar Gamificação', default=True, tracking=True)
    points_per_ticket = fields.Integer(string='Pontos por Ticket', default=10)
    points_sla_met = fields.Integer(string='Pontos por SLA Atingido', default=5)
    points_satisfaction = fields.Integer(string='Pontos por Avaliação Positiva', default=15)
    
    # Estatísticas
    last_execution = fields.Datetime(string='Última Execução', readonly=True)
    total_notifications = fields.Integer(string='Total de Notificações Enviadas', readonly=True)
    average_team_satisfaction = fields.Float(string='Média de Satisfação da Equipe', readonly=True)
    
    @api.constrains('sla_target', 'satisfaction_target')
    def _check_targets(self):
        for record in self:
            if not (0 <= record.sla_target <= 100):
                raise UserError(_('A meta de SLA deve estar entre 0 e 100%'))
            if not (0 <= record.satisfaction_target <= 100):
                raise UserError(_('A meta de satisfação deve estar entre 0 e 100%'))

    def _calculate_team_metrics(self, start_date, end_date):
        self.ensure_one()
        tickets = self.env['helpdesk.ticket'].search([
            ('team_id', '=', self.team_id.id),
            ('create_date', '>=', start_date),
            ('create_date', '<=', end_date)
        ])
        
        total_tickets = len(tickets)
        if not total_tickets:
            return {}
            
        sla_met = len(tickets.filtered(lambda t: t.sla_status == 'reached'))
        satisfaction_sum = sum(tickets.mapped('rating_avg'))
        rated_tickets = len(tickets.filtered(lambda t: t.rating_avg > 0))
        
        metrics = {
            'total_tickets': total_tickets,
            'sla_performance': (sla_met / total_tickets * 100) if total_tickets else 0,
            'avg_satisfaction': (satisfaction_sum / rated_tickets) if rated_tickets else 0,
            'tickets_by_priority': {
                'baixa': len(tickets.filtered(lambda t: t.priority == '0')),
                'media': len(tickets.filtered(lambda t: t.priority == '1')),
                'alta': len(tickets.filtered(lambda t: t.priority == '2')),
                'urgente': len(tickets.filtered(lambda t: t.priority == '3')),
            },
            'tickets_by_stage': {stage.name: len(tickets.filtered(lambda t: t.stage_id == stage))
                               for stage in self.team_id.stage_ids}
        }
        
        return metrics
    
    def _calculate_agent_performance(self, user_id, start_date, end_date):
        tickets = self.env['helpdesk.ticket'].search([
            ('team_id', '=', self.team_id.id),
            ('user_id', '=', user_id),
            ('create_date', '>=', start_date),
            ('create_date', '<=', end_date)
        ])
        
        total_tickets = len(tickets)
        if not total_tickets:
            return {}
            
        closed_tickets = len(tickets.filtered(lambda t: t.stage_id.is_close))
        sla_met = len(tickets.filtered(lambda t: t.sla_status == 'reached'))
        avg_response_time = sum(tickets.mapped('response_time')) / total_tickets if total_tickets else 0
        
        return {
            'total_tickets': total_tickets,
            'closed_tickets': closed_tickets,
            'sla_performance': (sla_met / total_tickets * 100) if total_tickets else 0,
            'avg_response_time': avg_response_time,
            'points_earned': self._calculate_agent_points(tickets)
        }
    
    def _calculate_agent_points(self, tickets):
        points = 0
        for ticket in tickets:
            # Pontos base por ticket
            points += self.points_per_ticket
            
            # Pontos por SLA atingido
            if ticket.sla_status == 'reached':
                points += self.points_sla_met
                
            # Pontos por satisfação do cliente
            if ticket.rating_avg >= 4:  # Considerando uma escala de 1-5
                points += self.points_satisfaction
        
        return points
    
    def _update_gamification_badges(self, user_id, points):
        if not self.enable_gamification:
            return
            
        Badge = self.env['gamification.badge']
        badges_to_grant = []
        
        # Verifica conquistas baseadas em pontos
        if points >= 1000:
            badges_to_grant.append('expert_badge')
        elif points >= 500:
            badges_to_grant.append('professional_badge')
        elif points >= 100:
            badges_to_grant.append('rising_star_badge')
            
        for badge_xml_id in badges_to_grant:
            badge = self.env.ref(f'blue_notification.{badge_xml_id}', False)
            if badge and not badge.has_user_won(user_id):
                badge.grant_to_user(user_id)
    
    @api.model
    def _send_daily_update(self):
        now = fields.Datetime.now()
        yesterday = now - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59)
        
        for config in self.search([('notification_frequency', '=', 'daily')]):
            # Cálculo de métricas da equipe
            team_metrics = config._calculate_team_metrics(yesterday_start, yesterday_end)
            if not team_metrics:
                continue
                
            # Cálculo de performance individual
            agent_performances = {}
            for member in config.team_members:
                performance = config._calculate_agent_performance(member.id, yesterday_start, yesterday_end)
                if performance:
                    agent_performances[member.name] = performance
                    config._update_gamification_badges(member.id, performance['points_earned'])
            
            # Preparação do contexto para o template
            template_ctx = {
                'team_metrics': team_metrics,
                'agent_performances': agent_performances,
                'date': fields.Date.to_string(yesterday),
                'config': config,
                'sla_status': 'Meta Atingida' if team_metrics['sla_performance'] >= config.sla_target else 'Abaixo da Meta',
                'satisfaction_status': 'Meta Atingida' if team_metrics['avg_satisfaction'] >= config.satisfaction_target else 'Abaixo da Meta'
            }
            
            # Envio do email
            template = self.env.ref('blue_notification.email_template_helpdesk_daily_update')
            template.with_context(**template_ctx).send_mail(
                config.id,
                force_send=True,
                email_values={'email_to': config.manager_email}
            )
            
            # Atualização das estatísticas
            config.write({
                'last_execution': now,
                'total_notifications': config.total_notifications + 1,
                'average_team_satisfaction': team_metrics['avg_satisfaction']
            })
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