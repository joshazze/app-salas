"""
Processo separado para o agendador de tarefas.
Roda independente do servidor web.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import visualizar_planilha as vp
from apscheduler.schedulers.blocking import BlockingScheduler

def rotina_atualizacao(janela_fim=None):
    print(f"\n[scheduler] Iniciando atualizacao (janela ate {janela_fim})...")
    try:
        from datetime import datetime
        dia = vp.DIA_PT
        df_bruto = vp.buscar_planilha_remota()
        df = vp.parsear_e_organizar(df_bruto)
        vp.salvar_csv(df)
        vp.notificar_todos(df, dia, janela_fim=janela_fim)
        print(f"[scheduler] Concluido em {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"[scheduler] Erro: {e}")

if __name__ == "__main__":
    vp.init_db()
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(rotina_atualizacao, "cron", hour=7,  minute=10, kwargs={"janela_fim": "07:30"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=9,  minute=30, kwargs={"janela_fim": "09:50"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=13, minute=10, kwargs={"janela_fim": "13:30"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=15, minute=30, kwargs={"janela_fim": "15:50"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=17, minute=20, kwargs={"janela_fim": "19:10"})
    print("Scheduler iniciado. Aguardando horarios agendados...")
    scheduler.start()
