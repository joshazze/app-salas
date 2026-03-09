"""
Processo separado para o agendador de tarefas.
Roda independente do servidor web.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import visualizar_planilha as vp
from apscheduler.schedulers.blocking import BlockingScheduler

def rotina_atualizacao(janela_fim=None, janela_inicio=None):
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
        # Filtra apenas registros do dia atual antes de notificar
        import pandas as pd
        if "Dia" in df.columns:
            df_hoje = df[df["Dia"].str.upper() == dia_pt.upper()].reset_index(drop=True)
        else:
            df_hoje = df
        vp.notificar_todos(df_hoje, dia_pt, janela_fim=janela_fim, janela_inicio=janela_inicio)
        print(f"[scheduler] Concluido em {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"[scheduler] Erro: {e}")

if __name__ == "__main__":
    vp.init_db()
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(rotina_atualizacao, "cron", hour=7,  minute=10, kwargs={"janela_inicio": "07:00", "janela_fim": "07:50"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=9,  minute=30, kwargs={"janela_inicio": "09:00", "janela_fim": "10:10"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=13, minute=10, kwargs={"janela_inicio": "13:00", "janela_fim": "13:50"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=15, minute=30, kwargs={"janela_inicio": "15:00", "janela_fim": "16:10"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=17, minute=20, kwargs={"janela_inicio": "17:00", "janela_fim": "23:00"})
    print("Scheduler iniciado. Aguardando horarios agendados...")
    scheduler.start()
