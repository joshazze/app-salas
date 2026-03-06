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
HOJE        = datetime.now().strftime("%Y-%m-%d")
DIA_SEMANA  = datetime.now().strftime("%A").upper()
CSV_HOJE    = os.path.join(PASTA_CACHE, f"mapa_salas_{HOJE}.csv")

DIAS_PT = {
    "MONDAY": "SEGUNDA", "TUESDAY": "TERCA", "WEDNESDAY": "QUARTA",
    "THURSDAY": "QUINTA", "FRIDAY": "SEXTA", "SATURDAY": "SABADO", "SUNDAY": "DOMINGO",
}
DIA_PT = DIAS_PT.get(DIA_SEMANA, DIA_SEMANA)

TITULOS_CATEGORIA = [
    "GRADUAÇÃO - MANHÃ",
    "GRADUAÇÃO - TARDE",
    "GRADUAÇÃO - NOITE",
    "OUTRAS RESERVAS - NOITE",
]


# ── Banco de dados ────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    con = sqlite3.connect(DB_PATH)
    try:
        yield con
        con.commit()
    finally:
        con.close()


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
            "SELECT id, username, criado FROM alunos WHERE username = ?", (username,)
        ).fetchone()


def buscar_aluno_por_email(email):
    with get_db() as con:
        return con.execute(
            "SELECT id FROM alunos WHERE email = ?", (email,)
        ).fetchone()


def aluno_bloqueado(aluno_id):
    with get_db() as con:
        row = con.execute("SELECT bloqueado FROM alunos WHERE id=?", (aluno_id,)).fetchone()
    return bool(row and row[0])


def set_bloqueio_aluno(aluno_id, bloqueado):
    with get_db() as con:
        con.execute("UPDATE alunos SET bloqueado=? WHERE id=?", (int(bloqueado), aluno_id))


def criar_aluno(username, email=""):
    with get_db() as con:
        con.execute(
            "INSERT INTO alunos (username, email, criado) VALUES (?, ?, ?)",
            (username, email, HOJE)
        )
        return con.execute(
            "SELECT id FROM alunos WHERE username = ?", (username,)
        ).fetchone()[0]


def listar_todos_alunos():
    with get_db() as con:
        return con.execute(
            "SELECT id, username, email, criado, bloqueado FROM alunos ORDER BY username"
        ).fetchall()


def listar_alunos_com_email():
    with get_db() as con:
        return con.execute(
            "SELECT id, username, email FROM alunos WHERE email != '' ORDER BY username"
        ).fetchall()


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


def salvar_materia(aluno_id, dia, turma, disciplina, professor):
    with get_db() as con:
        existe = con.execute("""
            SELECT id FROM materias
            WHERE aluno_id=? AND dia=? AND disciplina=? AND turma=?
        """, (aluno_id, dia, disciplina, turma)).fetchone()
        if not existe:
            con.execute("""
                INSERT INTO materias (aluno_id, dia, turma, disciplina, professor)
                VALUES (?, ?, ?, ?, ?)
            """, (aluno_id, dia, turma, disciplina, professor))


def remover_materia(aluno_id, materia_id):
    with get_db() as con:
        con.execute("DELETE FROM materias WHERE id=? AND aluno_id=?", (materia_id, aluno_id))


def buscar_disciplinas_historico(termo):
    palavras = termo.lower().split()
    with get_db() as con:
        rows = con.execute(
            "SELECT turma, disciplina, professor FROM disciplinas_historico ORDER BY turma, disciplina"
        ).fetchall()
    resultado = []
    for turma, disciplina, professor in rows:
        linha = f"{turma} {disciplina} {professor}".lower()
        if all(p in linha for p in palavras):
            resultado.append({"Turma": turma, "Disciplina": disciplina, "Professor": professor})
    return resultado


def listar_materias_aluno(aluno_id, dia=None):
    with get_db() as con:
        if dia:
            return con.execute("""
                SELECT id, dia, turma, disciplina, professor
                FROM materias WHERE aluno_id=? AND dia=?
                ORDER BY dia, disciplina
            """, (aluno_id, dia)).fetchall()
        return con.execute("""
            SELECT id, dia, turma, disciplina, professor
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
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDS_FILE, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(GMAIL_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def enviar_email(para, assunto, corpo_html):
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["To"]      = para
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service = _gmail_service()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()



def email_boas_vindas(username, email, materias):
    """Envia email de boas-vindas após cadastro."""
    assunto = f"[Mapa de Salas] Bem-vindo, {username}!"

    if materias:
        linhas_materias = ""
        dias = {}
        for m in materias:
            dias.setdefault(m["dia"], []).append(m)
        for dia, mats in dias.items():
            linhas_materias += f"<div style='color:#1e90ff;font-size:11px;letter-spacing:1px;margin:14px 0 6px;text-transform:uppercase'>{dia}</div>"
            for m in mats:
                linhas_materias += f"""
                <div style='border:1px solid #253d54;padding:10px 14px;background:#0d1117;margin-bottom:6px'>
                  <div style='color:#00d4ff;font-size:13px'>{m["disciplina"]}</div>
                  <div style='color:#7a9ab5;font-size:11px;margin-top:3px'>{m["turma"]} &middot; {m["professor"]}</div>
                </div>"""
        materias_html = f"""
        <p style='color:#dde6f0;font-size:13px;margin-bottom:12px'>Suas matérias cadastradas:</p>
        {linhas_materias}"""
    else:
        materias_html = """
        <div style='border:1px solid #253d54;padding:14px;background:#0d1117;color:#ffc107;font-size:13px'>
          &#9888; Você ainda não adicionou nenhuma matéria.<br/>
          <span style='color:#9ab0c4;font-size:12px'>Acesse o site e adicione suas disciplinas para receber notificações de sala.</span>
        </div>"""

    corpo = f"""
    <div style='background:#080c10;color:#dde6f0;font-family:Courier New,monospace;padding:24px;max-width:600px'>
      <div style='border-bottom:1px solid #253d54;padding-bottom:12px;margin-bottom:20px'>
        <span style='color:#1e90ff;font-size:16px;letter-spacing:2px'>MAPA DE SALAS</span>
        <span style='color:#7a9ab5'> // </span>
        <span style='color:#9ab0c4;font-size:12px'>IBtech</span>
      </div>
      <p style='color:#00e676;font-size:14px;margin-bottom:16px'>&#10003; Cadastro realizado com sucesso!</p>
      <p style='font-size:13px;margin-bottom:6px'>Olá, <span style='color:#1e90ff'>{username}</span>.</p>
      <p style='font-size:13px;color:#9ab0c4;margin-bottom:20px'>
        Seu acesso ao Mapa de Salas IBtech está ativo. Use seu username para entrar no sistema.
      </p>
      {materias_html}
      <div style='color:#7a9ab5;font-size:11px;margin-top:24px;border-top:1px solid #253d54;padding-top:12px'>
        &copy; Joshua Azze &amp; IBtech &mdash; Todos os direitos reservados.
      </div>
    </div>"""

    enviar_email(email, assunto, corpo)

def _montar_email_aulas(username, dia, aulas):
    if not aulas:
        return None, None

    linhas = ""
    for a in aulas:
        if not a["salas"]:
            sala_txt = "<tr><td colspan='3' style='color:#a0b4c4;font-size:12px'>sala nao encontrada</td></tr>"
        else:
            sala_txt = ""
            for s in a["salas"]:
                sala = s.get("Salas") or s.get("Sala") or "-"
                hora = s.get("Horario") or "-"
                data = s.get("DATA") or s.get("Data") or ""
                sala_txt += (
                    f"<tr>"
                    f"<td style='color:#ffc107'>{sala}</td>"
                    f"<td style='color:#00d4ff'>{hora}</td>"
                    f"<td style='color:#c8d4e0'>{data}</td>"
                    f"</tr>"
                )

        linhas += f"""
        <div style='margin-bottom:20px;border:1px solid #253d54;padding:14px;background:#0d1117'>
          <div style='color:#00d4ff;font-size:14px;margin-bottom:4px'>{a['disciplina']}</div>
          <div style='color:#7a9ab5;font-size:12px;margin-bottom:10px'>{a['turma']} &middot; {a['professor']}</div>
          <table style='width:100%;border-collapse:collapse;font-size:12px'>
            <thead><tr>
              <th style='text-align:left;color:#1e90ff;padding:4px 8px;border-bottom:1px solid #253d54'>Sala</th>
              <th style='text-align:left;color:#1e90ff;padding:4px 8px;border-bottom:1px solid #253d54'>Horario</th>
              <th style='text-align:left;color:#1e90ff;padding:4px 8px;border-bottom:1px solid #253d54'>Data</th>
            </tr></thead>
            <tbody>{sala_txt}</tbody>
          </table>
        </div>"""

    assunto = f"[IBtech] Suas aulas de {dia} — {HOJE}"
    corpo   = f"""
    <div style='background:#080c10;color:#dde6f0;font-family:Courier New,monospace;padding:24px;max-width:600px'>
      <div style='border-bottom:1px solid #253d54;padding-bottom:12px;margin-bottom:20px'>
        <span style='color:#1e90ff;font-size:16px;letter-spacing:2px'>MAPA DE SALAS</span>
        <span style='color:#7a9ab5'> // </span>
        <span style='color:#9ab0c4;font-size:12px'>IBtech</span>
        <div style='color:#7a9ab5;font-size:12px;margin-top:4px'>{dia} &middot; {HOJE}</div>
      </div>
      <div style='color:#7a9ab5;font-size:12px;margin-bottom:16px'>// aulas de hoje para <span style='color:#1e90ff'>@{username}</span></div>
      {linhas}
      <div style='color:#7a9ab5;font-size:11px;margin-top:20px;border-top:1px solid #253d54;padding-top:12px'>
        Este email foi gerado automaticamente pelo sistema de salas IBtech.
      </div>
    </div>"""
    return assunto, corpo


def _horario_na_janela(horario_str, janela_fim):
    if not horario_str or not janela_fim:
        return True
    try:
        inicio_str = str(horario_str).split("/")[0].strip()[:5]
        h1, m1 = map(int, inicio_str.split(":"))
        h2, m2 = map(int, janela_fim.split(":"))
        return (h1 * 60 + m1) <= (h2 * 60 + m2)
    except Exception:
        return True


def notificar_todos(df, dia, janela_fim=None):
    """Envia email de aulas do dia para cada aluno com aula dentro da janela horária."""
    alunos = listar_alunos_com_email()
    if not alunos:
        print("[notificar] Nenhum aluno com email cadastrado.")
        return

    enviados = 0
    erros    = 0
    for aluno_id, username, email in alunos:
        materias = listar_materias_aluno(aluno_id, dia=dia)
        if not materias:
            continue

        aulas = []
        for _, _dia, turma, disciplina, professor in materias:
            linhas = filtrar_df(df, f"{turma} {disciplina}")
            if linhas.empty:
                linhas = filtrar_df(df, " ".join(disciplina.split()[:3]))

            if janela_fim and not linhas.empty:
                linhas = linhas[linhas["Horario"].apply(
                    lambda h: _horario_na_janela(h, janela_fim)
                )]

            if linhas.empty:
                continue

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
            time.sleep(2)  # pausa para não sobrecarregar a VM
        except Exception as e:
            print(f"[notificar] Erro ao enviar para {email}: {e}")
            erros += 1

    print(f"[notificar] Concluido: {enviados} enviados, {erros} erros.")


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
    return os.path.exists(CSV_HOJE)


def carregar_do_cache():
    print(f"[cache] Carregando CSV do dia: {CSV_HOJE}")
    return pd.read_csv(CSV_HOJE, encoding="utf-8-sig", dtype=str)


def _excluir_csvs_anteriores():
    os.makedirs(PASTA_CACHE, exist_ok=True)
    basename_hoje = os.path.basename(CSV_HOJE)
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
                con.execute(
                    "INSERT OR IGNORE INTO disciplinas_historico (turma, disciplina, professor) VALUES (?, ?, ?)",
                    (turma, disciplina, professor)
                )
                if con.total_changes > inseridos:
                    inseridos = con.total_changes
            except Exception:
                pass
    if inseridos:
        print(f"[historico] {inseridos} disciplina(s) inedita(s) adicionadas.")


def salvar_csv(df_organizado):
    os.makedirs(PASTA_CACHE, exist_ok=True)
    _excluir_csvs_anteriores()
    df_organizado.to_csv(CSV_HOJE, index=False, encoding="utf-8-sig")
    print(f"[cache] CSV salvo: {CSV_HOJE}")
    atualizar_historico_disciplinas(df_organizado)


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

    return pd.DataFrame(todos_registros)


# ── Busca ─────────────────────────────────────────────────────────────────────

def filtrar_df(df, termo):
    """Retorna linhas onde todas as palavras do termo aparecem em qualquer coluna."""
    colunas = [c for c in df.columns if c != "Categoria"]
    texto_linha = df[colunas].fillna("").apply(
        lambda row: " ".join(row.values.astype(str)), axis=1
    ).str.lower()
    mascara = pd.Series([True] * len(df), index=df.index)
    for palavra in termo.lower().split():
        mascara &= texto_linha.str.contains(palavra, na=False, regex=False)
    return df[mascara].reset_index(drop=True)
