"""
Sistema de visualização de planilha Google Sheets + Banco de alunos cadastrados
Planilha: https://docs.google.com/spreadsheets/d/1-TyWurlvjDaiGwRmNFlq3OyK8ia4UP3fPpiSxyL2d3Y
"""

import os
import io
import time
import sqlite3
import unicodedata
import urllib.request
from contextlib import contextmanager
from datetime import datetime

import gspread
import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1-TyWurlvjDaiGwRmNFlq3OyK8ia4UP3fPpiSxyL2d3Y"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
PASTA_CACHE = os.path.join(BASE_DIR, "cache")
DB_PATH     = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "alunos.db"))
DIAS_PT = {
    "MONDAY": "SEGUNDA", "TUESDAY": "TERCA", "WEDNESDAY": "QUARTA",
    "THURSDAY": "QUINTA", "FRIDAY": "SEXTA", "SATURDAY": "SABADO", "SUNDAY": "DOMINGO",
}

def _hoje():
    return datetime.now().strftime("%Y-%m-%d")

def _dia_pt():
    dia = datetime.now().strftime("%A").upper()
    return DIAS_PT.get(dia, dia)

def _csv_hoje():
    return os.path.join(PASTA_CACHE, f"mapa_salas_{_hoje()}.csv")

# Compatibilidade com código existente (scheduler atualiza diretamente)
HOJE        = _hoje()
DIA_SEMANA  = datetime.now().strftime("%A").upper()
CSV_HOJE    = _csv_hoje()
DIA_PT      = _dia_pt()

TITULOS_CATEGORIA = [
    "GRADUAÇÃO - MANHÃ",
    "GRADUAÇÃO - TARDE",
    "GRADUAÇÃO - NOITE",
    "OUTRAS RESERVAS - NOITE",
]

# Faixas de horario para notificacao por slot (limites em minutos a partir de 00:00)
SLOTS = {
    "manha1": {"label": "Manha 1",  "inicio": (6,  0), "fim": (9, 29)},
    "manha2": {"label": "Manha 2",  "inicio": (9, 30), "fim": (12, 59)},
    "tarde1": {"label": "Tarde 1",  "inicio": (13, 0), "fim": (13, 59)},
    "tarde2": {"label": "Tarde 2",  "inicio": (14, 0), "fim": (17, 59)},
    "noite1": {"label": "Noite 1",  "inicio": (18, 0), "fim": (18, 59)},
    "noite2": {"label": "Noite 2",  "inicio": (19, 0), "fim": (23, 59)},
}


# ── Banco de dados ────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def horario_para_slot(horario_str):
    """Dado '07:30/09:20', retorna a chave do slot correspondente ao horario de inicio."""
    if not horario_str or not isinstance(horario_str, str):
        return None
    try:
        inicio = horario_str.split("/")[0].strip()
        h, m = map(int, inicio.split(":"))
        total = h * 60 + m
        for slot_key, slot in SLOTS.items():
            ini_min = slot["inicio"][0] * 60 + slot["inicio"][1]
            fim_min = slot["fim"][0] * 60 + slot["fim"][1]
            if ini_min <= total <= fim_min:
                return slot_key
    except (ValueError, IndexError):
        pass
    return None


def init_db():
    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS alunos (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT    UNIQUE NOT NULL,
                email    TEXT    NOT NULL DEFAULT '',
                criado   TEXT    NOT NULL
            )
        """)
        # migrações para bancos legados
        for migration in [
            "ALTER TABLE alunos ADD COLUMN email TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE alunos ADD COLUMN bloqueado INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE alunos ADD COLUMN receber_email INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE materias ADD COLUMN slot TEXT",
        ]:
            try:
                con.execute(migration)
            except Exception:
                pass
        con.execute("""
            CREATE TABLE IF NOT EXISTS materias (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                aluno_id   INTEGER NOT NULL REFERENCES alunos(id),
                dia        TEXT    NOT NULL,
                turma      TEXT    NOT NULL,
                disciplina TEXT    NOT NULL,
                professor  TEXT    NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS salas_historico (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                sala TEXT    UNIQUE NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS disciplinas_historico (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                turma      TEXT    NOT NULL,
                disciplina TEXT    NOT NULL,
                professor  TEXT    NOT NULL,
                UNIQUE(turma, disciplina, professor)
            )
        """)


def buscar_aluno(username):
    with get_db() as con:
        return con.execute(
            "SELECT id, username, criado FROM alunos WHERE LOWER(username) = LOWER(?)", (username,)
        ).fetchone()


def buscar_aluno_por_email(email):
    with get_db() as con:
        return con.execute(
            "SELECT id FROM alunos WHERE LOWER(email) = LOWER(?)", (email,)
        ).fetchone()


def aluno_bloqueado(aluno_id):
    with get_db() as con:
        row = con.execute("SELECT bloqueado FROM alunos WHERE id=?", (aluno_id,)).fetchone()
    return bool(row and row[0])


def set_bloqueio_aluno(aluno_id, bloqueado):
    with get_db() as con:
        con.execute("UPDATE alunos SET bloqueado=? WHERE id=?", (int(bloqueado), aluno_id))


def criar_aluno(username, email="", receber_email=1):
    with get_db() as con:
        cur = con.execute(
            "INSERT INTO alunos (username, email, criado, receber_email) VALUES (?, ?, ?, ?)",
            (username, email, _hoje(), int(receber_email))
        )
        return cur.lastrowid

def get_receber_email(aluno_id):
    with get_db() as con:
        row = con.execute("SELECT receber_email FROM alunos WHERE id=?", (aluno_id,)).fetchone()
    return bool(row and row[0])

def set_receber_email(aluno_id, valor):
    with get_db() as con:
        con.execute("UPDATE alunos SET receber_email=? WHERE id=?", (int(valor), aluno_id))


def listar_todos_alunos():
    with get_db() as con:
        return con.execute(
            "SELECT id, username, email, criado, bloqueado FROM alunos ORDER BY username"
        ).fetchall()


def listar_alunos_com_email():
    with get_db() as con:
        return con.execute(
            "SELECT id, username, email FROM alunos WHERE email != '' AND receber_email=1 ORDER BY username"
        ).fetchall()

def contar_alunos():
    with get_db() as con:
        row = con.execute("SELECT COUNT(*) FROM alunos WHERE bloqueado=0").fetchone()
    return row[0] if row else 0

def contar_disciplinas():
    with get_db() as con:
        row = con.execute("SELECT COUNT(*) FROM disciplinas_historico").fetchone()
    return row[0] if row else 0


def editar_aluno(aluno_id, username, email):
    with get_db() as con:
        con.execute(
            "UPDATE alunos SET username=?, email=? WHERE id=?", (username, email, aluno_id)
        )


def excluir_aluno(aluno_id):
    with get_db() as con:
        con.execute("DELETE FROM materias WHERE aluno_id=?", (aluno_id,))
        con.execute("DELETE FROM alunos WHERE id=?", (aluno_id,))


def listar_disciplinas_historico():
    with get_db() as con:
        return con.execute(
            "SELECT id, turma, disciplina, professor FROM disciplinas_historico ORDER BY turma, disciplina"
        ).fetchall()


def adicionar_disciplina_historico(turma, disciplina, professor):
    with get_db() as con:
        con.execute(
            "INSERT OR IGNORE INTO disciplinas_historico (turma, disciplina, professor) VALUES (?, ?, ?)",
            (turma, disciplina, professor)
        )


def editar_disciplina_historico(disc_id, turma, disciplina, professor):
    with get_db() as con:
        con.execute(
            "UPDATE disciplinas_historico SET turma=?, disciplina=?, professor=? WHERE id=?",
            (turma, disciplina, professor, disc_id)
        )


def excluir_disciplina_historico(disc_id):
    with get_db() as con:
        con.execute("DELETE FROM disciplinas_historico WHERE id=?", (disc_id,))



_SALAS_IGNORADAS = {"ONLINE", "EAD", "REMOTO", "HIBRIDO", "HIBRIDA", "A DEFINIR", "NAO DEFINIDA", ""}

def atualizar_historico_salas(df):
    """Armazena permanentemente todas as salas ineditas encontradas na planilha."""
    col = next((c for c in ["Salas","Sala"] if c in df.columns), None)
    if not col:
        return
    salas = df[col].dropna().astype(str).str.strip()
    salas = salas[~salas.str.upper().isin(_SALAS_IGNORADAS) & (salas != "")].unique()
    inseridas = 0
    with get_db() as con:
        for sala in salas:
            cur = con.execute(
                "INSERT OR IGNORE INTO salas_historico (sala) VALUES (?)", (sala,)
            )
            inseridas += cur.rowcount
    if inseridas:
        print(f"[historico] {inseridas} sala(s) inedita(s) adicionadas.")


def listar_salas_livres(df_hoje, horario_atual=None):
    """Retorna salas do historico que nao estao ocupadas no horario atual."""
    from datetime import datetime as _dt
    if horario_atual is None:
        agora = _dt.now()
        horario_atual = agora.hour * 60 + agora.minute

    col = next((c for c in ["Salas","Sala"] if c in df_hoje.columns), None)
    ocupadas = set()
    if col and "Horario" in df_hoje.columns:
        for _, row in df_hoje[[col, "Horario"]].dropna().iterrows():
            sala = str(row[col]).strip()
            horario_str = str(row["Horario"]).strip()
            try:
                partes = horario_str.split("/")
                h_ini = partes[0].strip()[:5]
                h_fim = partes[1].strip()[:5]
                ini_h, ini_m = map(int, h_ini.split(":"))
                fim_h, fim_m = map(int, h_fim.split(":"))
                ini = ini_h * 60 + ini_m
                fim = fim_h * 60 + fim_m
                if ini <= horario_atual <= fim:
                    ocupadas.add(sala)
            except Exception:
                pass
    elif col:
        ocupadas = set(df_hoje[col].dropna().astype(str).str.strip().unique())

    with get_db() as con:
        todas = [r[0] for r in con.execute("SELECT sala FROM salas_historico ORDER BY sala").fetchall()]
    return [s for s in todas if s not in ocupadas and s != ""]


def listar_salas_livres_por_slot(df_hoje):
    """Retorna dict slot -> [salas livres] para cada um dos 6 slots do dia.
    Uma sala e considerada ocupada num slot se alguma aula da planilha
    tiver Horario cujo inicio pertence a esse slot.
    """
    col = next((c for c in ["Salas", "Sala"] if c in df_hoje.columns), None)

    # Mapear sala -> conjunto de slots em que ela esta ocupada
    ocupadas_por_slot = {k: set() for k in SLOTS}
    if col and "Horario" in df_hoje.columns:
        for _, row in df_hoje[[col, "Horario"]].dropna().iterrows():
            sala = str(row[col]).strip()
            if not sala:
                continue
            slot = horario_para_slot(str(row["Horario"]).strip())
            if slot:
                ocupadas_por_slot[slot].add(sala)

    with get_db() as con:
        todas = [r[0] for r in con.execute(
            "SELECT sala FROM salas_historico ORDER BY sala"
        ).fetchall()]
    todas = [s for s in todas if s]

    return {
        slot: [s for s in todas if s not in ocupadas_por_slot[slot]]
        for slot in SLOTS
    }


def contar_salas():
    with get_db() as con:
        row = con.execute("SELECT COUNT(*) FROM salas_historico").fetchone()
    return row[0] if row else 0


def salvar_materia(aluno_id, dia, turma, disciplina, professor, slot=None):
    with get_db() as con:
        existe = con.execute("""
            SELECT id FROM materias
            WHERE aluno_id=? AND dia=? AND disciplina=? AND turma=?
        """, (aluno_id, dia, disciplina, turma)).fetchone()
        if existe:
            con.execute("UPDATE materias SET slot=? WHERE id=?", (slot, existe[0]))
        else:
            con.execute("""
                INSERT INTO materias (aluno_id, dia, turma, disciplina, professor, slot)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (aluno_id, dia, turma, disciplina, professor, slot))


def remover_materia(aluno_id, materia_id):
    with get_db() as con:
        con.execute("DELETE FROM materias WHERE id=? AND aluno_id=?", (materia_id, aluno_id))


def buscar_disciplinas_historico(termo):
    palavras = [_normalizar_texto(p) for p in termo.split()]
    if not palavras:
        return []
    # Busca SQL sem acento na primeira palavra
    primeira = f"%{palavras[0]}%"
    with get_db() as con:
        rows = con.execute(
            """SELECT turma, disciplina, professor FROM disciplinas_historico
               ORDER BY turma, disciplina LIMIT 500"""
        ).fetchall()
    resultado = []
    for turma, disciplina, professor in rows:
        texto = _normalizar_texto(turma + " " + disciplina + " " + professor)
        if all(p in texto for p in palavras):
            resultado.append({"Turma": turma, "Disciplina": disciplina, "Professor": professor})
    return resultado[:50]

def listar_materias_aluno(aluno_id, dia=None):
    with get_db() as con:
        if dia:
            return con.execute("""
                SELECT id, dia, turma, disciplina, professor, slot
                FROM materias WHERE aluno_id=? AND UPPER(dia)=UPPER(?)
                ORDER BY dia, disciplina
            """, (aluno_id, dia)).fetchall()
        return con.execute("""
            SELECT id, dia, turma, disciplina, professor, slot
            FROM materias WHERE aluno_id=?
            ORDER BY dia, disciplina
        """, (aluno_id,)).fetchall()


def buscar_aluno_por_id(aluno_id):
    with get_db() as con:
        return con.execute(
            "SELECT username, email FROM alunos WHERE id=?", (aluno_id,)
        ).fetchone()


# ── Gmail API ─────────────────────────────────────────────────────────────────

GMAIL_SCOPES     = ["https://www.googleapis.com/auth/gmail.send"]
GMAIL_TOKEN_FILE = os.path.join(BASE_DIR, "gmail_token.json")
GMAIL_CREDS_FILE = os.path.join(BASE_DIR, "gmail_credentials.json")


def _gmail_service():
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(GMAIL_TOKEN_FILE):
        creds = OAuthCredentials.from_authorized_user_file(GMAIL_TOKEN_FILE, GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[gmail] Falha ao refreshar token: {e}")
                creds = None
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDS_FILE, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(GMAIL_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


REMETENTE = "IBSALA <salas.ibtech@gmail.com>"

def enviar_email(para, assunto, corpo_html):
    if not para or not str(para).strip():
        print(f"[email] Destinatario vazio, abortando: {assunto}")
        return
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["From"]    = REMETENTE
    msg["To"]      = para
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service = _gmail_service()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()




def _email_wrapper(content: str, subtitle: str = "IBtech") -> str:
    """Gera HTML completo do email com fundo branco e letras pretas."""
    return (
        "<!DOCTYPE html><html lang='pt-BR'><head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "</head><body style='margin:0;padding:0;background:#f4f4f4'>"
        "<table width='100%' cellpadding='0' cellspacing='0' border='0' style='background:#f4f4f4'><tr><td>"
        "<table align='center' width='600' cellpadding='0' cellspacing='0' border='0' "
        "style='background:#ffffff;max-width:600px;margin:24px auto;"
        "font-family:Arial,Helvetica,sans-serif;border:1px solid #e0e0e0'>"
        "<tr><td style='background:#1a73e8;padding:20px 28px'>"
        "<span style='color:#ffffff;font-size:20px;font-weight:bold;letter-spacing:3px'>IBSALA</span>"
        f"<span style='color:#a8c7fa;font-size:13px;margin-left:10px'>// {subtitle}</span>"
        "</td></tr>"
        f"<tr><td style='padding:28px;color:#1a1a1a;font-size:14px;line-height:1.7'>{content}</td></tr>"
        "<tr><td style='background:#f4f4f4;padding:16px 28px;border-top:1px solid #e0e0e0'>"
        "<p style='margin:0;font-size:11px;color:#757575;font-family:Arial,Helvetica,sans-serif'>"
        "&copy; Joshua Azze &amp; IBtech &mdash; "
        "<a href='mailto:salas.ibtech@gmail.com' style='color:#1a73e8;text-decoration:none'>"
        "salas.ibtech@gmail.com</a></p></td></tr>"
        "</table></td></tr></table></body></html>"
    )


def email_boas_vindas(username, email, materias):
    """Envia email de boas-vindas após cadastro."""
    assunto = f"[IBSALA] Bem-vindo/a, {username}!"

    DIA_ORDER = ['SEGUNDA','TERCA','QUARTA','QUINTA','SEXTA','SABADO']

    if materias:
        dias = {}
        for m in materias:
            dias.setdefault(m["dia"], []).append(m)
        linhas_materias = ""
        for dia in sorted(dias.keys(), key=lambda d: DIA_ORDER.index(d) if d in DIA_ORDER else 99):
            mats = dias[dia]
            linhas_materias += (
                f"<p style='margin:16px 0 6px;font-size:12px;font-weight:bold;"
                f"color:#1a73e8;text-transform:uppercase;letter-spacing:1px'>{dia}</p>"
            )
            for m in mats:
                slot_label = ''
                if m.get("slot"):
                    slot_labels = {"manha1":"Manha 1 (07:30)","manha2":"Manha 2 (09:50)",
                                   "tarde1":"Tarde 1 (13:00)","tarde2":"Tarde 2 (14:00)",
                                   "noite1":"Noite 1 (18:00)","noite2":"Noite 2 (19:00)"}
                    slot_label = f" &middot; <span style='color:#1a73e8'>{slot_labels.get(m['slot'], m['slot'])}</span>"
                else:
                    slot_label = " &middot; <span style='color:#e53935'>sem slot &mdash; configure em Configuracoes</span>"
                linhas_materias += (
                    f"<div style='border:1px solid #e0e0e0;border-left:3px solid #1a73e8;"
                    f"padding:10px 14px;margin-bottom:6px;background:#f8f9ff'>"
                    f"<div style='font-weight:bold;color:#1a1a1a;font-size:13px'>{m['disciplina']}</div>"
                    f"<div style='color:#666;font-size:11px;margin-top:3px'>{m['turma']} &middot; {m['professor']}{slot_label}</div>"
                    f"</div>"
                )
        materias_bloco = (
            "<p style='font-weight:bold;margin:0 0 4px'>Suas matérias cadastradas:</p>"
            + linhas_materias
        )
    else:
        materias_bloco = (
            "<div style='border:1px solid #f5c518;background:#fffbea;padding:14px;color:#856404;font-size:13px'>"
            "&#9888; Você ainda não adicionou nenhuma matéria.<br/>"
            "<span style='font-size:12px'>Acesse o site e adicione suas disciplinas para receber notificações de sala.</span>"
            "</div>"
        )

    acesso_bloco = (
        "<div style='background:#f8f9ff;border:1px solid #e0e0e0;border-left:3px solid #1a73e8;"
        "padding:14px;margin-bottom:20px'>"
        "<p style='margin:0 0 6px;font-size:12px;color:#666;font-weight:bold'>SEU ACESSO</p>"
        f"<p style='margin:0 0 4px;font-size:14px'>Username: <strong style='color:#1a73e8'>@{username}</strong></p>"
        "<p style='margin:0;font-size:12px;color:#666'>Use esse username para entrar no site. Não é necessária senha.</p>"
        "</div>"
    )

    como_usar = (
        "<div style='background:#f8f9ff;border:1px solid #e0e0e0;padding:14px;margin-bottom:20px'>"
        "<p style='margin:0 0 10px;font-size:12px;color:#666;font-weight:bold'>COMO USAR O IBSALA</p>"
        "<div style='margin-bottom:8px'><span style='color:#1a73e8;font-weight:bold'>1.</span> "
        "Acesse <a href='https://ibsala.com.br' style='color:#1a73e8'>ibsala.com.br</a>"
        " e clique em <em>Estou cadastrado</em></div>"
        f"<div style='margin-bottom:8px'><span style='color:#1a73e8;font-weight:bold'>2.</span> "
        f"Digite seu username <strong>@{username}</strong> para entrar</div>"
        "<div style='margin-bottom:8px'><span style='color:#1a73e8;font-weight:bold'>3.</span> "
        "Veja suas aulas do dia com sala, horario e professor em tempo real</div>"
        "<div style='margin-bottom:8px'><span style='color:#1a73e8;font-weight:bold'>4.</span> "
        "Em <em>Configuracoes</em>, adicione suas disciplinas e selecione o "
        "<strong>slot de horario</strong> de cada uma para ativar as notificacoes por email</div>"
        "<div style='margin-top:10px;padding:10px 12px;background:#fff3cd;border:1px solid #ffc107;"
        "font-size:12px;color:#856404'>"
        "&#9432; Voce so recebera emails de aviso se cada disciplina tiver um slot definido. "
        "Acesse Configuracoes e atribua o turno correto a cada materia.</div>"
        "</div>"
    )

    content = (
        f"<p style='margin:0 0 20px'>Olá, <strong>{username}</strong>! Bem-vindo/a ao <strong>IBSALA</strong>.</p>"
        + acesso_bloco
        + como_usar
        + materias_bloco
    )

    corpo = _email_wrapper(content, "Bem-vindo/a!")
    enviar_email(email, assunto, corpo)

def email_recuperar_username(username, email):
    """Envia email com o username do aluno."""
    assunto = "[IBSALA] Recuperação de username"
    content = (
        "<p style='margin:0 0 16px'>Você solicitou a recuperação do seu username. Aqui está:</p>"
        "<div style='text-align:center;border:2px solid #1a73e8;padding:20px;margin-bottom:20px;background:#f8f9ff'>"
        f"<span style='font-size:24px;font-weight:bold;color:#1a73e8;letter-spacing:2px'>@{username}</span>"
        "</div>"
        "<p style='margin:0 0 8px;font-size:13px;color:#444'>Acesse o site com esse username:</p>"
        "<p style='margin:0'><a href='https://ibsala.com.br' style='color:#1a73e8;font-size:14px;font-weight:bold'>ibsala.com.br</a></p>"
        "<p style='margin:20px 0 0;font-size:12px;color:#888'>Se não foi você que solicitou, ignore este email.</p>"
    )
    corpo = _email_wrapper(content, "Recuperação de username")
    enviar_email(email, assunto, corpo)
def _montar_email_aulas(username, dia, aulas):
    if not aulas:
        return None, None

    blocos = ""
    for a in aulas:
        if not a["salas"]:
            sala_rows = (
                "<tr><td colspan='3' style='padding:10px 8px;color:#888;font-size:12px'>"
                "Sala não encontrada para hoje.</td></tr>"
            )
        else:
            sala_rows = ""
            for s in a["salas"]:
                sala = s.get("Salas") or s.get("Sala") or "-"
                hora = s.get("Horario") or "-"
                data = s.get("DATA") or s.get("Data") or ""
                sala_rows += (
                    f"<tr>"
                    f"<td style='padding:8px;border-bottom:1px solid #e0e0e0;font-weight:bold;color:#1a1a1a'>{sala}</td>"
                    f"<td style='padding:8px;border-bottom:1px solid #e0e0e0;color:#1a73e8'>{hora}</td>"
                    f"<td style='padding:8px;border-bottom:1px solid #e0e0e0;color:#444'>{data}</td>"
                    f"</tr>"
                )

        blocos += (
            "<div style='border:1px solid #e0e0e0;border-left:3px solid #1a73e8;"
            "margin-bottom:16px;background:#ffffff'>"
            f"<div style='padding:12px 14px;background:#f8f9ff;border-bottom:1px solid #e0e0e0'>"
            f"<div style='font-weight:bold;font-size:14px;color:#1a1a1a'>{a['disciplina']}</div>"
            f"<div style='font-size:12px;color:#666;margin-top:3px'>{a['turma']} &middot; {a['professor']}</div>"
            f"</div>"
            "<table width='100%' cellpadding='0' cellspacing='0' border='0' style='border-collapse:collapse'>"
            "<thead><tr>"
            "<th style='text-align:left;padding:8px;font-size:11px;color:#666;font-weight:bold;"
            "border-bottom:2px solid #e0e0e0;background:#fafafa'>SALA</th>"
            "<th style='text-align:left;padding:8px;font-size:11px;color:#666;font-weight:bold;"
            "border-bottom:2px solid #e0e0e0;background:#fafafa'>HORÁRIO</th>"
            "<th style='text-align:left;padding:8px;font-size:11px;color:#666;font-weight:bold;"
            "border-bottom:2px solid #e0e0e0;background:#fafafa'>DATA</th>"
            "</tr></thead>"
            f"<tbody>{sala_rows}</tbody>"
            "</table></div>"
        )

    assunto = f"[IBtech] Suas aulas de {dia} — {_hoje()}"
    content = (
        f"<p style='margin:0 0 4px;font-size:12px;color:#666'>"
        f"<strong style='color:#1a73e8'>{dia}</strong> &middot; {_hoje()}</p>"
        f"<p style='margin:0 0 20px;font-size:13px;color:#444'>"
        f"Aulas de hoje para <strong>@{username}</strong>:</p>"
        + blocos
        + "<p style='margin:16px 0 0;font-size:11px;color:#888'>"
        "Este email foi gerado automaticamente pelo sistema IBSALA.</p>"
    )
    corpo = _email_wrapper(content, f"Aulas de {dia}")
    return assunto, corpo

def _horario_na_janela(horario_str, janela_fim, janela_inicio=None):
    if not horario_str or not janela_fim:
        return True
    try:
        inicio_str = str(horario_str).split("/")[0].strip()[:5]
        h1, m1 = map(int, inicio_str.split(":"))
        minutos_aula = h1 * 60 + m1
        h2, m2 = map(int, janela_fim.split(":"))
        if minutos_aula > h2 * 60 + m2:
            return False
        if janela_inicio:
            h0, m0 = map(int, janela_inicio.split(":"))
            if minutos_aula < h0 * 60 + m0:
                return False
        return True
    except Exception:
        return True


def notificar_todos(df, dia, slot=None):
    """Envia email apenas com as disciplinas do slot especificado.
    Se slot=None (admin), envia todas as materias do dia sem filtro.
    A dupla confirmacao garante que:
      1. o slot do aluno bate com o slot do disparo;
      2. a disciplina aparece na planilha do dia com horario correspondente.
    Duplicatas da mesma disciplina no mesmo slot sao ignoradas.
    """
    alunos = listar_alunos_com_email()
    if not alunos:
        print("[notificar] Nenhum aluno com email cadastrado.")
        return 0, 0

    enviados = 0
    erros    = 0
    for aluno_id, username, email in alunos:
        materias = listar_materias_aluno(aluno_id, dia=dia)
        if not materias:
            continue

        aulas = []
        seen  = set()  # evita duplicatas quando disciplina aparece >1x no slot
        for _, _dia, turma, disciplina, professor, mat_slot in materias:
            # Confirmacao 1: slot do aluno bate com o slot do disparo
            if slot and mat_slot != slot:
                continue

            # Confirmacao 2: disciplina aparece na planilha do dia
            linhas = filtrar_df(df, f"{turma} {disciplina}")
            if linhas.empty:
                linhas = filtrar_df(df, " ".join(disciplina.split()[:3]))
            if linhas.empty:
                continue

            # Filtra linhas cujo horario na planilha pertence ao slot
            if slot and "Horario" in linhas.columns:
                linhas = linhas[linhas["Horario"].apply(
                    lambda h: horario_para_slot(h) == slot
                )]
            if linhas.empty:
                continue

            # Deduplicacao: mesma disciplina so entra uma vez por email
            if disciplina in seen:
                continue
            seen.add(disciplina)

            aulas.append({
                "disciplina": disciplina,
                "turma":      turma,
                "professor":  professor,
                "salas":      linhas.fillna("").to_dict(orient="records"),
            })

        if not aulas:
            print(f"[notificar] Sem aulas na janela para {username}, pulando.")
            continue

        assunto, corpo = _montar_email_aulas(username, dia, aulas)
        if not assunto:
            continue
        try:
            enviar_email(email, assunto, corpo)
            print(f"[notificar] Email enviado: {username} <{email}>")
            enviados += 1
            time.sleep(3)  # pausa para não sobrecarregar a VM
        except Exception as e:
            print(f"[notificar] Erro ao enviar para {email}: {e}")
            erros += 1

    print(f"[notificar] Concluido: {enviados} enviados, {erros} erros.")
    return enviados, erros


# ── Conexão Google Sheets ─────────────────────────────────────────────────────

def _conectar_via_service_account():
    cred_file = os.path.join(BASE_DIR, "credentials.json")
    if not os.path.exists(cred_file):
        return None
    creds = Credentials.from_service_account_file(cred_file, scopes=SCOPES)
    return gspread.authorize(creds)


def _conectar_via_oauth():
    from google_auth_oauthlib.flow import InstalledAppFlow
    token_file = os.path.join(BASE_DIR, "token.json")
    creds = None
    if os.path.exists(token_file):
        creds = OAuthCredentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            oauth_file = os.path.join(BASE_DIR, "oauth_credentials.json")
            if not os.path.exists(oauth_file):
                return None
            flow = InstalledAppFlow.from_client_secrets_file(oauth_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return gspread.authorize(creds)


def buscar_planilha_remota():
    df = None
    client = _conectar_via_service_account()
    if not client:
        try:
            client = _conectar_via_oauth()
        except Exception:
            pass

    if client:
        try:
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            ws = spreadsheet.get_worksheet(0)
            dados_raw = ws.get_all_values()
            df = pd.DataFrame(dados_raw[1:], columns=dados_raw[0])
            print(f"[planilha] Conectado via API: {spreadsheet.title}")
        except Exception as e:
            print(f"[planilha] Falha na API autenticada: {e}")

    if df is None:
        print("[planilha] Carregando via acesso publico...")
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(data))

    return df


# ── Cache CSV ─────────────────────────────────────────────────────────────────

def csv_hoje_existe():
    return os.path.exists(_csv_hoje())


def _normalizar_colunas(df):
    """Garante que a coluna de horário (pode vir como \"\", Unnamed: N, etc.) seja nomeada Horario."""
    for col in list(df.columns):
        if col == "" or col.startswith("Unnamed:"):
            if "Horario" not in df.columns:
                df = df.rename(columns={col: "Horario"})
            else:
                df["Horario"] = df[col].where(
                    df[col].notna() & (df[col] != ""), df["Horario"]
                )
                df = df.drop(columns=[col])
            break
    return df


def carregar_do_cache():
    csv = _csv_hoje()
    print(f"[cache] Carregando CSV do dia: {csv}")
    df = pd.read_csv(csv, encoding="utf-8-sig", dtype=str)
    return _normalizar_colunas(df)


def _excluir_csvs_anteriores():
    os.makedirs(PASTA_CACHE, exist_ok=True)
    basename_hoje = os.path.basename(_csv_hoje())
    for fname in os.listdir(PASTA_CACHE):
        if fname.startswith("mapa_salas_") and fname.endswith(".csv") and fname != basename_hoje:
            os.remove(os.path.join(PASTA_CACHE, fname))
            print(f"[cache] CSV anterior removido: {fname}")


def atualizar_historico_disciplinas(df):
    graduacao = df[~df["Categoria"].str.startswith("OUTRAS RESERVAS", na=False)]
    inseridos = 0
    with get_db() as con:
        for _, row in graduacao.iterrows():
            turma      = str(row.get("Turma", "") or "").strip()
            disciplina = str(row.get("Disciplina", "") or "").strip()
            professor  = str(row.get("Professor", "") or "").strip()
            if not turma or not disciplina:
                continue
            try:
                cur = con.execute(
                    "INSERT OR IGNORE INTO disciplinas_historico (turma, disciplina, professor) VALUES (?, ?, ?)",
                    (turma, disciplina, professor)
                )
                inseridos += cur.rowcount
            except Exception:
                pass
    if inseridos:
        print(f"[historico] {inseridos} disciplina(s) inedita(s) adicionadas.")


def salvar_csv(df_organizado):
    os.makedirs(PASTA_CACHE, exist_ok=True)
    _excluir_csvs_anteriores()
    path = _csv_hoje()
    df_organizado.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"[cache] CSV salvo: {path}")
    atualizar_historico_disciplinas(df_organizado)
    atualizar_historico_salas(df_organizado)


# ── Parse ─────────────────────────────────────────────────────────────────────

def _normalizar_col(texto):
    nfd = unicodedata.normalize("NFD", texto.encode("utf-8", errors="ignore").decode("utf-8"))
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").strip()


def _limpar_valor(val):
    if not isinstance(val, str):
        return val
    return val.encode("utf-8", errors="ignore").decode("utf-8").strip()


def parsear_e_organizar(df_bruto):
    categoria_atual = None
    colunas_atuais  = None
    todos_registros = []

    for _, row in df_bruto.iterrows():
        valores  = row.tolist()
        col0     = str(valores[0]).strip() if pd.notna(valores[0]) else ""
        resto_vazio = all(pd.isna(v) or str(v).strip() == "" for v in valores[1:])

        if col0 in TITULOS_CATEGORIA and resto_vazio:
            categoria_atual = col0
            colunas_atuais  = None
            continue

        if col0 == "Turma" and categoria_atual:
            colunas_atuais = [
                _normalizar_col(str(v)) if pd.notna(v) else f"col{i}"
                for i, v in enumerate(valores)
            ]
            continue

        if categoria_atual and colunas_atuais and col0 and col0 != "nan":
            if len(valores) < len(colunas_atuais):
                valores += [""] * (len(colunas_atuais) - len(valores))
            registro = {"Categoria": categoria_atual}
            for i, col in enumerate(colunas_atuais):
                val = valores[i]
                registro[col] = _limpar_valor(str(val)) if pd.notna(val) else ""
            if any(v for k, v in registro.items() if k != "Categoria"):
                todos_registros.append(registro)

    if not todos_registros:
        print("[parse] Nenhum registro valido encontrado na planilha.")
        return pd.DataFrame()
    df = pd.DataFrame(todos_registros)
    return _normalizar_colunas(df)


# ── Busca ─────────────────────────────────────────────────────────────────────

def _normalizar_texto(texto):
    """Remove acentos e converte para minúsculas para comparação semântica."""
    nfd = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def filtrar_df(df, termo):
    """Retorna linhas onde todas as palavras do termo aparecem em qualquer coluna.
    Insensível a acentos: financa == finanças, osmar == Osmar, etc.
    """
    if df.empty:
        return df.reset_index(drop=True)
    colunas = [c for c in df.columns if c != "Categoria"]
    texto_linha = df[colunas].fillna("").astype(str).apply(
        lambda row: _normalizar_texto(" ".join(row.values)), axis=1
    )
    palavras = [_normalizar_texto(p) for p in termo.split()]
    mascara = pd.Series([True] * len(df), index=df.index)
    for palavra in palavras:
        mascara &= texto_linha.str.contains(palavra, na=False, regex=False)
    return df[mascara].reset_index(drop=True)
