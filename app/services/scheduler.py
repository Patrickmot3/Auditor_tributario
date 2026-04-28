"""
Scheduler APScheduler para atualização automática das tabelas SPED.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)
_scheduler = None


def start_scheduler(app):
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    tz = pytz.timezone(app.config.get('SCHEDULER_TIMEZONE', 'America/Sao_Paulo'))
    _scheduler = BackgroundScheduler(timezone=tz)

    def verificar_versao():
        with app.app_context():
            from app.services.rfb_scraper import verificar_atualizacao
            for tabela in ['4.3.10', '4.3.11', '4.3.13', '4.3.15']:
                verificar_atualizacao(tabela)

    def atualizar_tabelas():
        with app.app_context():
            from app.services.rfb_scraper import verificar_atualizacao, atualizar_tabela
            for tabela in ['4.3.10', '4.3.11', '4.3.13', '4.3.15']:
                if verificar_atualizacao(tabela):
                    atualizar_tabela(tabela)

    # Verificar versão diariamente às 08h
    _scheduler.add_job(
        verificar_versao,
        CronTrigger(hour=8, minute=0),
        id='verificar_versao_diaria',
        replace_existing=True,
    )

    # Baixar atualizações toda segunda às 06h
    _scheduler.add_job(
        atualizar_tabelas,
        CronTrigger(day_of_week='mon', hour=6, minute=0),
        id='atualizar_tabelas_semanal',
        replace_existing=True,
    )

    _scheduler.start()
    logger.info('Scheduler iniciado.')


def get_scheduler():
    return _scheduler


def get_proximas_execucoes():
    if not _scheduler:
        return []
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'nome': job.name or job.id,
            'proxima': job.next_run_time.strftime('%d/%m/%Y %H:%M') if job.next_run_time else 'N/A',
        })
    return jobs
