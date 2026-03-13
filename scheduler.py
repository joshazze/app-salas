"""
Processo separado para o agendador de tarefas.
Roda independente do servidor web.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import time
import json
import socket
import threading
from datetime import datetime

import visualizar_planilha as vp
from apscheduler.schedulers.blocking import BlockingScheduler

STATUS_FILE = os.path.join(os.path.dirname(__file__), "logs", "scheduler_status.json")


def _sd_notify(msg: str):
    """Envia mensagem para o watchdog do systemd via UNIX socket."""
    sock_path = os.environ.get("NOTIFY_SOCKET", "")
    if not sock_path:
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(sock_path)
            s.send(msg.encode())
    except Exception:
        pass


def _watchdog_thread():
    """Pulsa o watchdog do systemd a cada 60s para detectar travamentos."""
    _sd_notify("READY=1")
    while True:
        _sd_notify("WATCHDOG=1")
        time.sleep(60)


def _salvar_status(slot, enviados, erros, erro_msg=None):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    status = {
        "timestamp": datetime.utcnow().isoformat(),
        "slot": slot,
        "enviados": enviados,
        "erros": erros,
        "erro_msg": erro_msg,
    }
    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(status, f)
    os.replace(tmp, STATUS_FILE)


def rotina_atualizacao(slot=None):
    label = vp.SLOTS[slot]["label"] if slot and slot in vp.SLOTS else slot
    print(f"\n[scheduler] Iniciando atualizacao (slot: {label})...")
    enviados, erros, erro_msg = 0, 0, None
    try:
        hoje   = vp._hoje()
        dia_pt = vp._dia_pt()
        df_bruto = vp.buscar_planilha_remota()
        df = vp.parsear_e_organizar(df_bruto)
        vp.salvar_csv_incremental(df)

        if "Dia" in df.columns:
            df_hoje = df[df["Dia"].astype(str).apply(vp._normalizar_texto) == vp._normalizar_texto(dia_pt)].reset_index(drop=True)
        else:
            df_hoje = df

        resultado = vp.notificar_todos(df_hoje, dia_pt, slot=slot)
        enviados, erros = resultado if resultado else (0, 0)
        print(f"[scheduler] Concluido em {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        erro_msg = str(e)
        print(f"[scheduler] Erro: {e}")
    finally:
        _salvar_status(slot, enviados, erros, erro_msg)


def rotina_captura():
    """Busca e salva o CSV sem enviar emails. Roda a cada 20min nos dias uteis."""
    from datetime import datetime as _dt
    agora = _dt.now()
    dia_semana = agora.strftime("%A").upper()
    # Pula fins de semana (SATURDAY / SUNDAY)
    if dia_semana in ("SATURDAY", "SUNDAY"):
        return
    print(f"[scheduler] Captura ({agora.strftime('%H:%M')})...")
    try:
        hoje   = agora.strftime("%Y-%m-%d")
        dia_pt = vp.DIAS_PT.get(dia_semana, dia_semana)
        df_bruto = vp.buscar_planilha_remota()
        df       = vp.parsear_e_organizar(df_bruto)
        vp.salvar_csv_incremental(df)
        print(f"[scheduler] Captura OK — {len(df)} linhas.")
    except Exception as e:
        print(f"[scheduler] Erro na captura: {e}")


def rotina_monitoramento(slot):
    """Verifica se o envio do slot foi satisfatorio e notifica o admin se nao foi."""
    label = vp.SLOTS[slot]["label"] if slot in vp.SLOTS else slot
    print(f"\n[monitor] Verificando slot {label}...")
    try:
        import subprocess
        from visualizar_planilha import enviar_email, _email_wrapper, listar_alunos_com_email

        problemas = []

        # 1. Verifica resultado do ultimo envio
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE) as f:
                    status = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                problemas.append(f"Arquivo de status corrompido: {e}")
                status = {}
            ts_str = status.get("timestamp")
            if not ts_str:
                problemas.append("Arquivo de status sem campo timestamp -- scheduler pode nao ter rodado")
                ts_str = datetime.utcnow().isoformat()
            ts = datetime.fromisoformat(ts_str)
            minutos = max(0, (datetime.utcnow() - ts).total_seconds() / 60)

            if status.get("erro_msg"):
                problemas.append(f"Erro no scheduler: {status['erro_msg']}")
            elif minutos > 60:
                problemas.append(f"Ultimo envio foi ha {int(minutos)} minutos (esperado no slot {label})")
            elif status.get("enviados", 0) == 0:
                dia_pt = vp._dia_pt()
                alunos_com_email = listar_alunos_com_email()
                alunos_com_aula = [
                    a for a in alunos_com_email
                    if any((r[5] if len(r) > 5 else None) == slot for r in vp.listar_materias_aluno(a[0], dia=dia_pt))
                ]
                if alunos_com_aula:
                    problemas.append(f"0 emails enviados no slot {label}, mas ha {len(alunos_com_aula)} aluno(s) com aulas neste slot hoje")
        else:
            problemas.append(f"Arquivo de status nao encontrado — scheduler pode ter travado no slot {label}")

        # 2. Verifica saude dos servicos
        for servico in ["app-salas", "app-salas-scheduler", "nginx"]:
            result = subprocess.run(["systemctl", "is-active", servico], capture_output=True, text=True, timeout=10)
            if result.stdout.strip() != "active":
                problemas.append(f"Servico {servico} esta {result.stdout.strip()}")

        # 3. Verifica uso de disco
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=10)
        for line in result.stdout.splitlines()[1:]:
            try:
                partes = line.split()
                pct = next((p for p in partes if p.endswith("%")), None)
                if pct:
                    uso = int(pct.replace("%", ""))
                    if uso >= 85:
                        problemas.append(f"Disco em {uso}% de uso")
            except (ValueError, IndexError):
                pass

        if not problemas:
            print(f"[monitor] Tudo OK no slot {label}.")
            return

        # 4. Envia email de alerta para o admin
        admin_email = os.environ.get("ADMIN_EMAIL", "jazzedistel@gmail.com")
        lista_html = "".join(
            f"<div style='padding:10px 14px;margin-bottom:8px;border-left:4px solid #dc3545;"
            f"background:#fdf2f2;font-size:13px'>{p}</div>"
            for p in problemas
        )
        content = (
            f"<p style='margin:0 0 16px'>Foram detectados <strong>{len(problemas)} problema(s)</strong> "
            f"no servidor IBSALA as <strong>{datetime.now().strftime('%H:%M')}</strong>:</p>"
            + lista_html
            + "<p style='margin:16px 0 0;font-size:12px;color:#888'>Verifique os logs com:<br/>"
            "<code>sudo journalctl -u app-salas-scheduler -n 50</code></p>"
        )
        corpo = _email_wrapper(content, "Alerta do Servidor")
        assunto = f"[IBSALA] Alerta — {len(problemas)} problema(s) detectado(s) [{label}]"
        enviar_email(admin_email, assunto, corpo)
        print(f"[monitor] Alerta enviado para {admin_email}: {len(problemas)} problema(s)")

    except Exception as e:
        print(f"[monitor] Erro no monitoramento: {e}")


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)
    vp.init_db()

    t = threading.Thread(target=_watchdog_thread, daemon=True)
    t.start()

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")

    # Jobs de envio — disparo 30min antes do inicio de cada slot
    # manha1 (07:30) -> dispara 07:00
    # manha2 (09:50) -> dispara 09:20
    # tarde1 (13:00) -> dispara 12:30
    # tarde2 (15:50) -> dispara 15:20
    # noite1 (18:00) -> dispara 17:30
    # noite2 (19:00) -> dispara 18:30
    scheduler.add_job(rotina_atualizacao, "cron", hour=7,  minute=0,  kwargs={"slot": "manha1"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=9,  minute=20, kwargs={"slot": "manha2"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=12, minute=30, kwargs={"slot": "tarde1"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=15, minute=20, kwargs={"slot": "tarde2"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=17, minute=30, kwargs={"slot": "noite1"})
    scheduler.add_job(rotina_atualizacao, "cron", hour=18, minute=30, kwargs={"slot": "noite2"})

    # Jobs de monitoramento (40min apos cada disparo)
    scheduler.add_job(rotina_monitoramento, "cron", hour=7,  minute=40, kwargs={"slot": "manha1"})
    scheduler.add_job(rotina_monitoramento, "cron", hour=10, minute=0,  kwargs={"slot": "manha2"})
    scheduler.add_job(rotina_monitoramento, "cron", hour=13, minute=10, kwargs={"slot": "tarde1"})
    scheduler.add_job(rotina_monitoramento, "cron", hour=16, minute=0,  kwargs={"slot": "tarde2"})
    scheduler.add_job(rotina_monitoramento, "cron", hour=18, minute=10, kwargs={"slot": "noite1"})
    scheduler.add_job(rotina_monitoramento, "cron", hour=19, minute=10, kwargs={"slot": "noite2"})

    # Captura do CSV a cada 20min — dias uteis, 07:00 a 22:00
    scheduler.add_job(rotina_captura, "cron", day_of_week="mon-fri", hour="7-21", minute="0,20,40")
    scheduler.add_job(rotina_captura, "cron", day_of_week="mon-fri", hour=22, minute=0)

    print("Scheduler iniciado. Aguardando horarios agendados...")
    scheduler.start()
