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
        import os
        # Recomputa data/hora atuais (o módulo vp tem constantes do momento do import)
        hoje       = datetime.now().strftime("%Y-%m-%d")
        dia_semana = datetime.now().strftime("%A").upper()
        dia_pt     = vp.DIAS_PT.get(dia_semana, dia_semana)
        csv_hoje   = os.path.join(vp.PASTA_CACHE, f"mapa_salas_{hoje}.csv")
        # Atualiza as constantes do módulo para refletir o dia atual
        vp.HOJE     = hoje
        vp.DIA_PT   = dia_pt
        vp.CSV_HOJE = csv_hoje

        df_bruto = vp.buscar_planilha_remota()
        df = vp.parsear_e_organizar(df_bruto)
        vp.salvar_csv(df)
        vp.notificar_todos(df, dia_pt, janela_fim=janela_fim)
        print(f"[scheduler] Concluido em {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"[scheduler] Erro: {e}")

if __name__ == "__main__":
    vp.init_db()
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(rotina_atualizacao, "cron", hour=7,  minute=10, kwargs={"janela_fim": "07:50"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=9,  minute=30, kwargs={"janela_fim": "10:10"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=13, minute=10, kwargs={"janela_fim": "13:50"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=15, minute=30, kwargs={"janela_fim": "16:10"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=17, minute=20, kwargs={"janela_fim": "23:00"})
    print("Scheduler iniciado. Aguardando horarios agendados...")
    scheduler.start()
