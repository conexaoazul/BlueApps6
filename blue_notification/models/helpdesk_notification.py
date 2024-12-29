# -*- coding: utf-8 -*-
"""
Este módulo implementa o sistema de notificações e gamificação para o Helpdesk da Conexão Azul.
Autor: OpenHands
Versão: 17.0.1.1.0

Principais funcionalidades:
- Sistema de notificações por email
- Gamificação com pontos e conquistas
- Dashboard de performance
- Análise de métricas de atendimento
"""

from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HelpdeskNotification(models.Model):
    """
    Modelo principal para gerenciar as notificações e métricas do Helpdesk.
    Herda funcionalidades de email (mail.thread) e atividades (mail.activity.mixin).
    
    Fluxo principal:
    1. Configuração das métricas e metas
    2. Monitoramento automático dos tickets
    3. Cálculo de performance e pontos
    4. Envio de notificações
    """
    _name = 'helpdesk.notification'
    _description = 'Configurações de Notificação do Helpdesk'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Campos básicos de identificação e controle
    name = fields.Char(
        string='Nome da Configuração',
        required=True,
        tracking=True,
        help='Nome para identificar esta configuração de notificações'
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
        help='Se desmarcado, esta configuração ficará inativa'
    )
    
    # Campos de relacionamento com equipe e gestão
    team_id = fields.Many2one(
        'helpdesk.team',
        string='Equipe',
        required=True,
        tracking=True,
        help='Equipe do helpdesk que será monitorada'
    )
    manager_id = fields.Many2one(
        'res.users',
        string='Gestor',
        required=True,
        tracking=True,
        domain="[('share', '=', False)]",  # Apenas usuários internos
        help='Gestor responsável que receberá as notificações'
    )
    manager_email = fields.Char(
        string='Email do Gestor',
        required=True,
        tracking=True,
        help='Email para envio dos relatórios'
    )
    team_members = fields.Many2many(
        'res.users',
        string='Membros da Equipe',
        related='team_id.member_ids',
        readonly=True,
        help='Lista automática dos membros da equipe'
    )
    
    # Configurações de Notificação
    notification_frequency = fields.Selection([
        ('daily', 'Diário'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensal')
    ], string='Frequência',
       default='daily',
       required=True,
       tracking=True,
       help='Com qual frequência os relatórios serão enviados'
    )
    
    # Opções de conteúdo do relatório
    include_metrics = fields.Boolean(
        string='Incluir Métricas',
        default=True,
        tracking=True,
        help='Incluir métricas gerais como SLA e satisfação'
    )
    include_team_performance = fields.Boolean(
        string='Incluir Performance da Equipe',
        default=True,
        tracking=True,
        help='Incluir dados de performance da equipe como um todo'
    )
    include_individual_stats = fields.Boolean(
        string='Incluir Estatísticas Individuais',
        default=True,
        tracking=True,
        help='Incluir estatísticas individuais de cada membro'
    )
    
    # Métricas e Metas
    sla_target = fields.Float(
        string='Meta de SLA (%)',
        default=95.0,
        tracking=True,
        help='Porcentagem alvo de tickets que devem cumprir o SLA'
    )
    response_time_target = fields.Float(
        string='Meta de Tempo de Resposta (horas)',
        default=1.0,
        tracking=True,
        help='Tempo máximo para primeira resposta ao cliente'
    )
    resolution_time_target = fields.Float(
        string='Meta de Tempo de Resolução (horas)',
        default=8.0,
        tracking=True,
        help='Tempo máximo para resolver o ticket'
    )
    satisfaction_target = fields.Float(
        string='Meta de Satisfação (%)',
        default=90.0,
        tracking=True,
        help='Meta de satisfação do cliente (média das avaliações)'
    )
    
    # Sistema de Gamificação
    enable_gamification = fields.Boolean(
        string='Ativar Gamificação',
        default=True,
        tracking=True,
        help='Ativa o sistema de pontos e conquistas'
    )
    points_per_ticket = fields.Integer(
        string='Pontos por Ticket',
        default=10,
        help='Pontos base ganhos por resolver um ticket'
    )
    points_sla_met = fields.Integer(
        string='Pontos por SLA Atingido',
        default=5,
        help='Pontos extras por resolver dentro do SLA'
    )
    points_satisfaction = fields.Integer(
        string='Pontos por Avaliação Positiva',
        default=15,
        help='Pontos extras por avaliação positiva do cliente'
    )
    
    # Campos Estatísticos (somente leitura)
    last_execution = fields.Datetime(
        string='Última Execução',
        readonly=True,
        help='Data e hora da última execução do relatório'
    )
    total_notifications = fields.Integer(
        string='Total de Notificações Enviadas',
        readonly=True,
        help='Contador de notificações enviadas'
    )
    average_team_satisfaction = fields.Float(
        string='Média de Satisfação da Equipe',
        readonly=True,
        help='Média histórica de satisfação da equipe'
    )
    
    @api.constrains('sla_target', 'satisfaction_target')
    def _check_targets(self):
        """
        Validação das metas de SLA e satisfação.
        Garante que os valores estejam entre 0 e 100%.
        
        Raises:
            UserError: Se alguma meta estiver fora do intervalo permitido
        """
        for record in self:
            if not (0 <= record.sla_target <= 100):
                raise UserError(_('A meta de SLA deve estar entre 0 e 100%'))
            if not (0 <= record.satisfaction_target <= 100):
                raise UserError(_('A meta de satisfação deve estar entre 0 e 100%'))

    def _calculate_team_metrics(self, start_date, end_date):
        """
        Calcula as métricas de performance da equipe para um período específico.
        
        Args:
            start_date (datetime): Data inicial do período
            end_date (datetime): Data final do período
            
        Returns:
            dict: Dicionário com as métricas calculadas:
                - total_tickets: Total de tickets no período
                - sla_performance: % de tickets que atingiram o SLA
                - avg_satisfaction: Média de satisfação
                - tickets_by_priority: Distribuição por prioridade
                - tickets_by_stage: Distribuição por estágio
        """
        self.ensure_one()
        # Busca todos os tickets da equipe no período
        tickets = self.env['helpdesk.ticket'].search([
            ('team_id', '=', self.team_id.id),
            ('create_date', '>=', start_date),
            ('create_date', '<=', end_date)
        ])
        
        # Contagem total de tickets no período
        total_tickets = len(tickets)
        if not total_tickets:
            return {}
            
        # Cálculo de métricas de SLA
        sla_met = len(tickets.filtered(lambda t: t.sla_status == 'reached'))
        
        # Cálculo de métricas de satisfação
        satisfaction_sum = sum(tickets.mapped('rating_avg'))
        rated_tickets = len(tickets.filtered(lambda t: t.rating_avg > 0))
        
        # Preparação do dicionário de métricas
        metrics = {
            # Métricas básicas
            'total_tickets': total_tickets,
            'sla_performance': (sla_met / total_tickets * 100) if total_tickets else 0,
            'avg_satisfaction': (satisfaction_sum / rated_tickets) if rated_tickets else 0,
            
            # Distribuição por prioridade
            'tickets_by_priority': {
                'baixa': len(tickets.filtered(lambda t: t.priority == '0')),    # Prioridade 0
                'media': len(tickets.filtered(lambda t: t.priority == '1')),    # Prioridade 1
                'alta': len(tickets.filtered(lambda t: t.priority == '2')),     # Prioridade 2
                'urgente': len(tickets.filtered(lambda t: t.priority == '3')),  # Prioridade 3
            },
            
            # Distribuição por estágio do ticket
            'tickets_by_stage': {
                stage.name: len(tickets.filtered(lambda t: t.stage_id == stage))
                for stage in self.team_id.stage_ids
            }
        }
        
        return metrics
    
    def _calculate_agent_performance(self, user_id, start_date, end_date):
        """
        Calcula as métricas de performance individual de um agente.
        
        Args:
            user_id (int): ID do usuário (agente)
            start_date (datetime): Data inicial do período
            end_date (datetime): Data final do período
            
        Returns:
            dict: Dicionário com as métricas do agente:
                - total_tickets: Total de tickets atribuídos
                - closed_tickets: Tickets fechados
                - sla_performance: % de SLA atingido
                - avg_response_time: Tempo médio de resposta
                - points_earned: Pontos ganhos no período
        """
        # Busca tickets atribuídos ao agente no período
        tickets = self.env['helpdesk.ticket'].search([
            ('team_id', '=', self.team_id.id),
            ('user_id', '=', user_id),
            ('create_date', '>=', start_date),
            ('create_date', '<=', end_date)
        ])
        
        # Contagem básica de tickets
        total_tickets = len(tickets)
        if not total_tickets:
            return {}
            
        # Cálculos de performance
        closed_tickets = len(tickets.filtered(lambda t: t.stage_id.is_close))  # Tickets fechados
        sla_met = len(tickets.filtered(lambda t: t.sla_status == 'reached'))   # SLA atingido
        
        # Cálculo do tempo médio de resposta
        avg_response_time = sum(tickets.mapped('response_time')) / total_tickets if total_tickets else 0
        
        # Montagem do resultado
        return {
            'total_tickets': total_tickets,
            'closed_tickets': closed_tickets,
            'sla_performance': (sla_met / total_tickets * 100) if total_tickets else 0,
            'avg_response_time': avg_response_time,
            'points_earned': self._calculate_agent_points(tickets)  # Cálculo de pontos
        }
    
    def _calculate_agent_points(self, tickets):
        """
        Calcula os pontos ganhos por um agente com base nos tickets resolvidos.
        Sistema de pontuação:
        - Pontos base por cada ticket resolvido
        - Bônus por atingir o SLA
        - Bônus por avaliação positiva do cliente
        
        Args:
            tickets (recordset): Conjunto de tickets do agente
            
        Returns:
            int: Total de pontos ganhos
        """
        points = 0
        for ticket in tickets:
            # Pontos base por ticket resolvido
            # Incentiva a produtividade geral
            points += self.points_per_ticket
            
            # Bônus por cumprir o SLA
            # Incentiva a rapidez no atendimento
            if ticket.sla_status == 'reached':
                points += self.points_sla_met
                
            # Bônus por satisfação do cliente
            # Incentiva a qualidade no atendimento
            # Consideramos 4+ como uma avaliação positiva (escala 1-5)
            if ticket.rating_avg >= 4:
                points += self.points_satisfaction
        
        return points
    
    def _update_gamification_badges(self, user_id, points):
        """
        Atualiza as conquistas (badges) do agente com base nos pontos acumulados.
        Sistema de níveis:
        - Rising Star (100+ pontos): Iniciante promissor
        - Professional (500+ pontos): Profissional experiente
        - Expert (1000+ pontos): Especialista em atendimento
        
        Args:
            user_id (int): ID do usuário (agente)
            points (int): Total de pontos acumulados
            
        Note:
            As badges são concedidas de forma progressiva e permanente.
            Uma vez conquistada, a badge não é removida mesmo se os pontos diminuírem.
        """
        # Verifica se a gamificação está ativa
        if not self.enable_gamification:
            return
            
        Badge = self.env['gamification.badge']
        badges_to_grant = []
        
        # Define as badges a serem concedidas com base nos pontos
        # A ordem é importante: verifica primeiro o nível mais alto
        if points >= 1000:
            badges_to_grant.append('expert_badge')  # Nível Expert
        elif points >= 500:
            badges_to_grant.append('professional_badge')  # Nível Profissional
        elif points >= 100:
            badges_to_grant.append('rising_star_badge')  # Nível Iniciante
            
        # Concede as badges que o usuário ainda não possui
        for badge_xml_id in badges_to_grant:
            # Busca a badge pelo XML ID
            badge = self.env.ref(f'blue_notification.{badge_xml_id}', False)
            # Concede apenas se a badge existe e o usuário ainda não a possui
            if badge and not badge.has_user_won(user_id):
                badge.grant_to_user(user_id)
    
    @api.model
    def _send_daily_update(self):
        """
        Método principal para envio das notificações diárias.
        Este método é chamado automaticamente pelo agendador do Odoo (ir.cron).
        
        Processo:
        1. Identifica o período de análise (dia anterior)
        2. Busca configurações ativas para notificações diárias
        3. Calcula métricas da equipe e performance individual
        4. Atualiza gamificação
        5. Envia email com o relatório
        6. Atualiza estatísticas
        
        Note:
            - Executa apenas para configurações com frequência diária
            - Ignora equipes sem tickets no período
            - Atualiza badges de gamificação automaticamente
        """
        # Define o período de análise (dia anterior)
        now = fields.Datetime.now()
        yesterday = now - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59)
        
        # Processa cada configuração ativa de notificação diária
        for config in self.search([('notification_frequency', '=', 'daily')]):
            # Obtém métricas da equipe
            team_metrics = config._calculate_team_metrics(yesterday_start, yesterday_end)
            if not team_metrics:
                continue  # Pula se não houver dados no período
                
            # Processa performance individual de cada membro
            agent_performances = {}
            for member in config.team_members:
                # Calcula performance e atualiza gamificação
                performance = config._calculate_agent_performance(
                    member.id,
                    yesterday_start,
                    yesterday_end
                )
                if performance:
                    agent_performances[member.name] = performance
                    # Atualiza badges se houver pontos ganhos
                    config._update_gamification_badges(
                        member.id,
                        performance['points_earned']
                    )
            
            # Prepara o contexto para o template de email
            template_ctx = {
                'team_metrics': team_metrics,
                'agent_performances': agent_performances,
                'date': fields.Date.to_string(yesterday),
                'config': config,
                # Status de metas com texto amigável
                'sla_status': 'Meta Atingida' 
                    if team_metrics['sla_performance'] >= config.sla_target 
                    else 'Abaixo da Meta',
                'satisfaction_status': 'Meta Atingida'
                    if team_metrics['avg_satisfaction'] >= config.satisfaction_target
                    else 'Abaixo da Meta'
            }
            
            # Envia o email usando o template configurado
            template = self.env.ref('blue_notification.email_template_helpdesk_daily_update')
            template.with_context(**template_ctx).send_mail(
                config.id,
                force_send=True,  # Envia imediatamente
                email_values={'email_to': config.manager_email}
            )
            
            # Atualiza estatísticas da configuração
            config.write({
                'last_execution': now,  # Marca horário da execução
                'total_notifications': config.total_notifications + 1,  # Incrementa contador
                'average_team_satisfaction': team_metrics['avg_satisfaction']  # Atualiza média
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