"""
Sistema de visualização de planilha Google Sheets + Banco de alunos cadastrados
Planilha: https://docs.google.com/spreadsheets/d/1-TyWurlvjDaiGwRmNFlq3OyK8ia4UP3fPpiSxyL2d3Y
"""

import sys
import subprocess

def instalar_dependencias():
    pacotes = ["gspread", "google-auth", "pandas", "tabulate", "colorama"]
    for pacote in pacotes:
        try:
            __import__(pacote.replace("-", "_").split(".")[0])
        except ImportError:
            print(f"Instalando {pacote}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pacote, "-q"])

instalar_dependencias()

import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
import pandas as pd
from tabulate import tabulate
from colorama import Fore, Style, init
import os
import unicodedata
import urllib.request
import io
import sqlite3
from datetime import datetime

init(autoreset=True)

SPREADSHEET_ID = "1-TyWurlvjDaiGwRmNFlq3OyK8ia4UP3fPpiSxyL2d3Y"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
PASTA_CACHE = os.path.join(BASE_DIR, "cache")
DB_PATH     = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "alunos.db"))
HOJE        = datetime.now().strftime("%Y-%m-%d")
DIA_SEMANA  = datetime.now().strftime("%A").upper()  # MONDAY, TUESDAY...
CSV_HOJE    = os.path.join(PASTA_CACHE, f"mapa_salas_{HOJE}.csv")

DIAS_PT = {
    "MONDAY": "SEGUNDA", "TUESDAY": "TERCA", "WEDNESDAY": "QUARTA",
    "THURSDAY": "QUINTA", "FRIDAY": "SEXTA", "SATURDAY": "SABADO", "SUNDAY": "DOMINGO",
}
DIA_PT = DIAS_PT.get(DIA_SEMANA, DIA_SEMANA)


# ── Banco de dados ────────────────────────────────────────────────────────────

def init_db():
    con = sqlite3.connect(DB_PATH)
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
            con.commit()
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
    con.commit()
    con.close()


def buscar_aluno(username):
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT id, username, criado FROM alunos WHERE username = ?",
                      (username,)).fetchone()
    con.close()
    return row  # (id, username, criado) ou None


def buscar_aluno_por_email(email):
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT id FROM alunos WHERE email = ?", (email,)).fetchone()
    con.close()
    return row


def aluno_bloqueado(aluno_id):
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT bloqueado FROM alunos WHERE id=?", (aluno_id,)).fetchone()
    con.close()
    return bool(row and row[0])


def set_bloqueio_aluno(aluno_id, bloqueado):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE alunos SET bloqueado=? WHERE id=?", (int(bloqueado), aluno_id))
    con.commit()
    con.close()


def criar_aluno(username, email=""):
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT INTO alunos (username, email, criado) VALUES (?, ?, ?)",
                (username, email, HOJE))
    con.commit()
    aluno_id = con.execute("SELECT id FROM alunos WHERE username = ?", (username,)).fetchone()[0]
    con.close()
    return aluno_id


def listar_todos_alunos():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT id, username, email, criado, bloqueado FROM alunos ORDER BY username").fetchall()
    con.close()
    return rows  # [(id, username, email, criado, bloqueado), ...]


def listar_alunos_com_email():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT id, username, email FROM alunos WHERE email != '' ORDER BY username").fetchall()
    con.close()
    return rows


def editar_aluno(aluno_id, username, email):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE alunos SET username=?, email=? WHERE id=?", (username, email, aluno_id))
    con.commit()
    con.close()


def excluir_aluno(aluno_id):
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM materias WHERE aluno_id=?", (aluno_id,))
    con.execute("DELETE FROM alunos WHERE id=?", (aluno_id,))
    con.commit()
    con.close()


def listar_disciplinas_historico():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT id, turma, disciplina, professor FROM disciplinas_historico ORDER BY turma, disciplina").fetchall()
    con.close()
    return rows


def adicionar_disciplina_historico(turma, disciplina, professor):
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT OR IGNORE INTO disciplinas_historico (turma, disciplina, professor) VALUES (?, ?, ?)",
                (turma, disciplina, professor))
    con.commit()
    con.close()


def editar_disciplina_historico(disc_id, turma, disciplina, professor):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE disciplinas_historico SET turma=?, disciplina=?, professor=? WHERE id=?",
                (turma, disciplina, professor, disc_id))
    con.commit()
    con.close()


def excluir_disciplina_historico(disc_id):
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM disciplinas_historico WHERE id=?", (disc_id,))
    con.commit()
    con.close()


def salvar_materia(aluno_id, dia, turma, disciplina, professor):
    con = sqlite3.connect(DB_PATH)
    # Evita duplicata exata
    existe = con.execute("""
        SELECT id FROM materias
        WHERE aluno_id=? AND dia=? AND disciplina=? AND turma=?
    """, (aluno_id, dia, disciplina, turma)).fetchone()
    if not existe:
        con.execute("""
            INSERT INTO materias (aluno_id, dia, turma, disciplina, professor)
            VALUES (?, ?, ?, ?, ?)
        """, (aluno_id, dia, turma, disciplina, professor))
        con.commit()
    con.close()


def remover_materia(aluno_id, materia_id):
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM materias WHERE id=? AND aluno_id=?", (materia_id, aluno_id))
    con.commit()
    con.close()


def buscar_disciplinas_historico(termo):
    palavras = termo.lower().split()
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT turma, disciplina, professor FROM disciplinas_historico ORDER BY turma, disciplina"
    ).fetchall()
    con.close()
    resultado = []
    for turma, disciplina, professor in rows:
        linha = f"{turma} {disciplina} {professor}".lower()
        if all(p in linha for p in palavras):
            resultado.append({"Turma": turma, "Disciplina": disciplina, "Professor": professor})
    return resultado


def listar_materias_aluno(aluno_id, dia=None):
    con = sqlite3.connect(DB_PATH)
    if dia:
        rows = con.execute("""
            SELECT id, dia, turma, disciplina, professor
            FROM materias WHERE aluno_id=? AND dia=?
            ORDER BY dia, disciplina
        """, (aluno_id, dia)).fetchall()
    else:
        rows = con.execute("""
            SELECT id, dia, turma, disciplina, professor
            FROM materias WHERE aluno_id=?
            ORDER BY dia, disciplina
        """, (aluno_id,)).fetchall()
    con.close()
    return rows  # lista de (id, dia, turma, disciplina, professor)


# ── Gmail API ─────────────────────────────────────────────────────────────────

GMAIL_SCOPES     = ["https://www.googleapis.com/auth/gmail.send"]
GMAIL_TOKEN_FILE = os.path.join(BASE_DIR, "gmail_token.json")
GMAIL_CREDS_FILE = os.path.join(BASE_DIR, "gmail_credentials.json")


def _gmail_service():
    """Retorna um serviço autenticado do Gmail. Abre browser na primeira vez."""
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
    """Envia um email via Gmail API."""
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


def _montar_email_aulas(username, dia, aulas):
    """Monta o HTML do email de notificação diária."""
    if not aulas:
        return None, None

    linhas = ""
    for a in aulas:
        if not a["salas"]:
            sala_txt = "<tr><td colspan='3' style='color:#888;font-size:12px'>sala nao encontrada</td></tr>"
        else:
            sala_txt = ""
            for s in a["salas"]:
                sala  = s.get("Salas") or s.get("Sala") or "-"
                hora  = s.get("Horario") or "-"
                data  = s.get("DATA") or s.get("Data") or ""
                sala_txt += f"<tr><td style='color:#ffc107'>{sala}</td><td style='color:#00d4ff'>{hora}</td><td style='color:#aaa'>{data}</td></tr>"

        linhas += f"""
        <div style='margin-bottom:20px;border:1px solid #1a2a3a;padding:14px;background:#0d1117'>
          <div style='color:#00d4ff;font-size:14px;margin-bottom:4px'>{a['disciplina']}</div>
          <div style='color:#4a5a6a;font-size:12px;margin-bottom:10px'>{a['turma']} &middot; {a['professor']}</div>
          <table style='width:100%;border-collapse:collapse;font-size:12px'>
            <thead><tr>
              <th style='text-align:left;color:#1e90ff;padding:4px 8px;border-bottom:1px solid #1a2a3a'>Sala</th>
              <th style='text-align:left;color:#1e90ff;padding:4px 8px;border-bottom:1px solid #1a2a3a'>Horario</th>
              <th style='text-align:left;color:#1e90ff;padding:4px 8px;border-bottom:1px solid #1a2a3a'>Data</th>
            </tr></thead>
            <tbody>{sala_txt}</tbody>
          </table>
        </div>"""

    assunto = f"[IBtech] Suas aulas de {dia} — {HOJE}"
    corpo   = f"""
    <div style='background:#080c10;color:#c9d1d9;font-family:Courier New,monospace;padding:24px;max-width:600px'>
      <div style='border-bottom:1px solid #1a2a3a;padding-bottom:12px;margin-bottom:20px'>
        <span style='color:#1e90ff;font-size:16px;letter-spacing:2px'>MAPA DE SALAS</span>
        <span style='color:#4a5a6a'> // </span>
        <span style='color:#6e7a8a;font-size:12px'>IBtech</span>
        <div style='color:#4a5a6a;font-size:12px;margin-top:4px'>{dia} &middot; {HOJE}</div>
      </div>
      <div style='color:#4a5a6a;font-size:12px;margin-bottom:16px'>// aulas de hoje para <span style='color:#1e90ff'>@{username}</span></div>
      {linhas}
      <div style='color:#4a5a6a;font-size:11px;margin-top:20px;border-top:1px solid #1a2a3a;padding-top:12px'>
        Este email foi gerado automaticamente pelo sistema de salas IBtech.
      </div>
    </div>"""
    return assunto, corpo


def _horario_na_janela(horario_str, janela_fim):
    """Verifica se o horário de início da aula está antes ou igual ao janela_fim (ex: '08:30')."""
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
    """Envia email de aulas do dia para alunos com aula dentro da janela horária."""
    alunos = listar_alunos_com_email()
    if not alunos:
        print(Fore.YELLOW + "Nenhum aluno com email cadastrado.")
        return

    enviados = 0
    erros    = 0
    for aluno_id, username, email in alunos:
        materias = listar_materias_aluno(aluno_id, dia=dia)
        if not materias:
            continue

        aulas = []
        for _, mat_dia, turma, disciplina, professor in materias:
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
            print(Fore.YELLOW + f"Sem aulas na janela para {username}, pulando.")
            continue

        assunto, corpo = _montar_email_aulas(username, dia, aulas)
        if not assunto:
            continue
        try:
            enviar_email(email, assunto, corpo)
            print(Fore.GREEN + f"Email enviado: {username} <{email}>")
            enviados += 1
        except Exception as e:
            print(Fore.RED + f"Erro ao enviar para {email}: {e}")
            erros += 1

    print(Fore.CYAN + f"Notificacoes: {enviados} enviadas, {erros} erros.")


# ── Conexão Google Sheets ─────────────────────────────────────────────────────

def conectar_via_service_account():
    cred_file = "credentials.json"
    if not os.path.exists(cred_file):
        return None
    creds = Credentials.from_service_account_file(cred_file, scopes=SCOPES)
    return gspread.authorize(creds)


def conectar_via_oauth():
    from google_auth_oauthlib.flow import InstalledAppFlow
    token_file = "token.json"
    creds = None
    if os.path.exists(token_file):
        creds = OAuthCredentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("oauth_credentials.json"):
                return None
            flow = InstalledAppFlow.from_client_secrets_file("oauth_credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return gspread.authorize(creds)


# ── Cache CSV ─────────────────────────────────────────────────────────────────

def csv_hoje_existe():
    return os.path.exists(CSV_HOJE)


def carregar_do_cache():
    print(Fore.GREEN + f"Cache do dia encontrado. Carregando...")
    return pd.read_csv(CSV_HOJE, encoding="utf-8-sig", dtype=str)


def buscar_planilha_remota():
    df = None
    client = conectar_via_service_account()
    if not client:
        try:
            client = conectar_via_oauth()
        except Exception:
            pass

    if client:
        try:
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            ws = spreadsheet.get_worksheet(0)
            dados_raw = ws.get_all_values()
            df = pd.DataFrame(dados_raw[1:], columns=dados_raw[0])
            print(Fore.GREEN + f"Conectado via API: {spreadsheet.title}")
        except Exception as e:
            print(Fore.YELLOW + f"Falha na API autenticada: {e}")

    if df is None:
        print(Fore.CYAN + "Carregando planilha (acesso publico)...")
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read().decode("utf-8")
        df = pd.read_csv(io.StringIO(data))

    return df


def excluir_csvs_anteriores():
    os.makedirs(PASTA_CACHE, exist_ok=True)
    for fname in os.listdir(PASTA_CACHE):
        if fname.startswith("mapa_salas_") and fname.endswith(".csv") and fname != os.path.basename(CSV_HOJE):
            path = os.path.join(PASTA_CACHE, fname)
            os.remove(path)
            print(Fore.YELLOW + f"CSV anterior removido: {fname}")


def atualizar_historico_disciplinas(df):
    graduacao = df[~df["Categoria"].str.startswith("OUTRAS RESERVAS", na=False)].copy()
    con = sqlite3.connect(DB_PATH)
    inseridos = 0
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
            if con.total_changes > 0:
                inseridos += 1
        except Exception:
            pass
    con.commit()
    con.close()
    if inseridos:
        print(Fore.GREEN + f"{inseridos} disciplina(s) inedita(s) adicionadas ao historico.")


def salvar_csv(df_organizado):
    os.makedirs(PASTA_CACHE, exist_ok=True)
    excluir_csvs_anteriores()
    df_organizado.to_csv(CSV_HOJE, index=False, encoding="utf-8-sig")
    print(Fore.YELLOW + Style.BRIGHT + f"CSV do dia salvo em: {CSV_HOJE}")
    atualizar_historico_disciplinas(df_organizado)


# ── Parse ─────────────────────────────────────────────────────────────────────

def normalizar_col(texto):
    nfd = unicodedata.normalize("NFD", texto.encode("utf-8", errors="ignore").decode("utf-8"))
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").strip()


def limpar_valor(val):
    if not isinstance(val, str):
        return val
    return val.encode("utf-8", errors="ignore").decode("utf-8").strip()


TITULOS_CATEGORIA = [
    "GRADUAÇÃO - MANHÃ",
    "GRADUAÇÃO - TARDE",
    "GRADUAÇÃO - NOITE",
    "OUTRAS RESERVAS - NOITE",
]


def parsear_e_organizar(df_bruto):
    categoria_atual = None
    colunas_atuais  = None
    todos_registros = []

    for _, row in df_bruto.iterrows():
        valores = row.tolist()
        col0 = str(valores[0]).strip() if pd.notna(valores[0]) else ""
        restante_vazio = all(pd.isna(v) or str(v).strip() == "" for v in valores[1:])

        if col0 in TITULOS_CATEGORIA and restante_vazio:
            categoria_atual = col0
            colunas_atuais  = None
            continue

        if col0 == "Turma" and categoria_atual:
            colunas_atuais = [normalizar_col(str(v)) if pd.notna(v) else f"col{i}"
                              for i, v in enumerate(valores)]
            continue

        if categoria_atual and colunas_atuais and col0 and col0 != "nan":
            if len(valores) < len(colunas_atuais):
                valores += [""] * (len(colunas_atuais) - len(valores))
            registro = {"Categoria": categoria_atual}
            for i, col in enumerate(colunas_atuais):
                val = valores[i]
                registro[col] = limpar_valor(str(val)) if pd.notna(val) else ""
            if any(v for k, v in registro.items() if k != "Categoria"):
                todos_registros.append(registro)

    return pd.DataFrame(todos_registros)


# ── Busca genérica ────────────────────────────────────────────────────────────

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


def exibir_resultado(resultado, titulo="Resultados"):
    print("\n" + "=" * 85)
    if resultado.empty:
        print(Fore.RED + f"  Nenhum resultado encontrado.")
        print("=" * 85)
        return
    print(Fore.GREEN + Style.BRIGHT + f"  {titulo}  ({len(resultado)} registro(s))")
    print("=" * 85)
    for cat in resultado["Categoria"].unique():
        subset = resultado[resultado["Categoria"] == cat].drop(columns=["Categoria"]).reset_index(drop=True)
        print(Fore.YELLOW + f"\n  [{cat}]")
        print(tabulate(subset.fillna(""), headers="keys", tablefmt="rounded_outline", showindex=False))


def exibir_categoria(nome, df):
    subset = df[df["Categoria"] == nome].drop(columns=["Categoria"]).reset_index(drop=True)
    print("\n" + "=" * 85)
    print(Fore.GREEN + Style.BRIGHT + f"  {nome}  ({len(subset)} registros)")
    print("=" * 85)
    if subset.empty:
        print(Fore.RED + "  (sem registros)")
        return
    print(tabulate(subset.fillna(""), headers="keys", tablefmt="rounded_outline", showindex=False))


# ── Fluxo: Consulta imediata ──────────────────────────────────────────────────

def menu_consulta_imediata(df):
    while True:
        print("\n" + Fore.CYAN + Style.BRIGHT + "=== CONSULTA IMEDIATA ===")
        for i, nome in enumerate(TITULOS_CATEGORIA):
            total = len(df[df["Categoria"] == nome])
            print(f"  [{i+1}] {nome}  ({total} registros)")
        print("  [B] Buscar por qualquer termo")
        print("  [T] Ver todas as categorias")
        print("  [0] Voltar")

        escolha = input(Fore.WHITE + "\nEscolha: ").strip().upper()

        if escolha == "0":
            break
        elif escolha == "B":
            print(Fore.CYAN + "\nDigite palavras para buscar (turma, disciplina, professor, sala, horario...)")
            print(Fore.WHITE + Style.DIM + "Vazio para cancelar.")
            termo = input(Fore.WHITE + "Busca: ").strip()
            if termo:
                exibir_resultado(filtrar_df(df, termo), f'"{termo}"')
        elif escolha == "T":
            for nome in TITULOS_CATEGORIA:
                exibir_categoria(nome, df)
        elif escolha.isdigit() and 1 <= int(escolha) <= len(TITULOS_CATEGORIA):
            exibir_categoria(TITULOS_CATEGORIA[int(escolha) - 1], df)
        else:
            print(Fore.RED + "Opcao invalida.")


# ── Fluxo: Aluno cadastrado ───────────────────────────────────────────────────

DIAS_SEMANA = ["SEGUNDA", "TERCA", "QUARTA", "QUINTA", "SEXTA", "SABADO"]


def selecionar_disciplina(df):
    """Busca interativa; retorna dict com a disciplina ou None se o usuário cancelar."""
    while True:
        print(Fore.CYAN + "\nBusque a disciplina:")
        print(Fore.WHITE + Style.DIM + "  (vazio = cancelar e voltar)")
        termo = input(Fore.WHITE + "Busca: ").strip()
        if not termo:
            return None

        resultado = filtrar_df(df, termo)
        if resultado.empty:
            print(Fore.RED + "Nenhum resultado. Tente outro termo.")
            continue

        print()
        opcoes = resultado[["Categoria", "Turma", "Disciplina", "Professor", "Salas", "Horario"]].reset_index(drop=True)
        for i, row in opcoes.iterrows():
            print(Fore.YELLOW + f"  [{i+1}] {row['Turma']}  |  {row['Disciplina']}  |  {row['Professor']}  |  Sala {row['Salas']}  {row['Horario']}")
        print(Fore.WHITE + Style.DIM + "  [0] Buscar de novo  |  vazio = cancelar")

        escolha = input(Fore.WHITE + "\nEscolha o numero: ").strip()
        if not escolha:
            return None
        if escolha == "0":
            continue
        if escolha.isdigit() and 1 <= int(escolha) <= len(opcoes):
            row = resultado.iloc[int(escolha) - 1]
            return {
                "turma":      row.get("Turma", ""),
                "disciplina": row.get("Disciplina", ""),
                "professor":  row.get("Professor", ""),
            }
        print(Fore.RED + "Opcao invalida.")


def _escolher_dia():
    """Retorna o dia escolhido ou None se o usuário cancelar."""
    print(Fore.CYAN + "\nQual dia da semana?")
    for i, d in enumerate(DIAS_SEMANA):
        print(f"  [{i+1}] {d}")
    print(Fore.WHITE + Style.DIM + "  (vazio = cancelar)")
    d_escolha = input(Fore.WHITE + "Dia: ").strip()
    if not d_escolha:
        return None
    if d_escolha.isdigit() and 1 <= int(d_escolha) <= len(DIAS_SEMANA):
        return DIAS_SEMANA[int(d_escolha) - 1]
    print(Fore.RED + "Invalido.")
    return None


def cadastrar_aluno(df):
    """Cadastro completo em memória — só grava no banco ao confirmar com [S]."""
    print("\n" + Fore.CYAN + Style.BRIGHT + "=== CADASTRO DE ALUNO ===")
    print(Fore.WHITE + Style.DIM + "  (vazio em qualquer etapa cancela o cadastro inteiro)")

    username = input(Fore.WHITE + "\nEscolha um username: ").strip()
    if not username:
        print(Fore.YELLOW + "Cadastro cancelado.")
        return

    if buscar_aluno(username):
        print(Fore.RED + f"Username '{username}' ja existe. Tente outro.")
        return

    # Coleta disciplinas em memória — nada salvo ainda
    materias_temp = []  # lista de (dia, turma, disciplina, professor)

    print(Fore.GREEN + f"\nUsername '{username}' disponivel!")
    print(Fore.CYAN + "Adicione suas disciplinas. Quando terminar, escolha [S] para salvar ou [0] para cancelar tudo.\n")

    while True:
        print(Fore.CYAN + Style.BRIGHT + "=== DISCIPLINAS ADICIONADAS ===")
        if not materias_temp:
            print(Fore.WHITE + Style.DIM + "  Nenhuma ainda.")
        else:
            rows = [{"#": i+1, "Dia": m[0], "Turma": m[1], "Disciplina": m[2], "Professor": m[3]}
                    for i, m in enumerate(materias_temp)]
            print(tabulate(rows, headers="keys", tablefmt="rounded_outline", showindex=False))

        print("\n  [A] Adicionar disciplina")
        if materias_temp:
            print("  [R] Remover disciplina da lista")
        print("  [S] Salvar cadastro e finalizar")
        print("  [0] Cancelar cadastro (nada sera salvo)")

        escolha = input(Fore.WHITE + "\nEscolha: ").strip().upper()

        if escolha == "0":
            print(Fore.YELLOW + "Cadastro cancelado. Nenhum dado foi salvo.")
            return

        elif escolha == "S":
            aluno_id = criar_aluno(username)
            for dia, turma, disciplina, professor in materias_temp:
                salvar_materia(aluno_id, dia, turma, disciplina, professor)
            print(Fore.GREEN + Style.BRIGHT + f"\nCadastro de '{username}' salvo com {len(materias_temp)} disciplina(s)!")
            return

        elif escolha == "A":
            dia = _escolher_dia()
            if dia is None:
                continue
            disc = selecionar_disciplina(df)
            if disc is None:
                continue
            entrada = (dia, disc["turma"], disc["disciplina"], disc["professor"])
            if entrada in materias_temp:
                print(Fore.YELLOW + "Essa disciplina ja foi adicionada.")
            else:
                materias_temp.append(entrada)
                print(Fore.GREEN + f"Adicionada: {disc['disciplina']} ({dia})")

        elif escolha == "R" and materias_temp:
            num = input(Fore.WHITE + "Digite o # para remover: ").strip()
            if num.isdigit() and 1 <= int(num) <= len(materias_temp):
                removida = materias_temp.pop(int(num) - 1)
                print(Fore.GREEN + f"Removida: {removida[2]}")
            else:
                print(Fore.RED + "Invalido.")

        else:
            print(Fore.RED + "Opcao invalida.")


def gerenciar_materias(aluno_id, username, df):
    """Gerencia disciplinas de um aluno já existente (salva imediatamente)."""
    while True:
        materias = listar_materias_aluno(aluno_id)

        print("\n" + Fore.CYAN + Style.BRIGHT + f"=== MATÉRIAS DE '{username}' ===")
        if not materias:
            print(Fore.WHITE + Style.DIM + "  Nenhuma matéria cadastrada ainda.")
        else:
            rows = [{"#": m[0], "Dia": m[1], "Turma": m[2], "Disciplina": m[3], "Professor": m[4]}
                    for m in materias]
            print(tabulate(rows, headers="keys", tablefmt="rounded_outline", showindex=False))

        print("\n  [A] Adicionar disciplina")
        print("  [R] Remover disciplina")
        print("  [0] Voltar")

        escolha = input(Fore.WHITE + "\nEscolha: ").strip().upper()

        if escolha == "0":
            break

        elif escolha == "A":
            dia = _escolher_dia()
            if dia is None:
                continue
            disc = selecionar_disciplina(df)
            if disc:
                salvar_materia(aluno_id, dia, disc["turma"], disc["disciplina"], disc["professor"])
                print(Fore.GREEN + f"Disciplina adicionada para {dia}!")

        elif escolha == "R":
            if not materias:
                print(Fore.RED + "Nenhuma matéria para remover.")
                continue
            materia_id = input(Fore.WHITE + "Digite o # da matéria para remover: ").strip()
            if materia_id.isdigit():
                remover_materia(aluno_id, int(materia_id))
                print(Fore.GREEN + "Matéria removida.")
            else:
                print(Fore.RED + "Invalido.")
        else:
            print(Fore.RED + "Opcao invalida.")


def login_aluno(df):
    print("\n" + Fore.CYAN + Style.BRIGHT + "=== ALUNO CADASTRADO ===")
    username = input(Fore.WHITE + "Username: ").strip()
    if not username:
        return

    aluno = buscar_aluno(username)
    if not aluno:
        print(Fore.RED + f"Username '{username}' nao encontrado.")
        novo = input(Fore.YELLOW + "Deseja criar este cadastro? (s/n): ").strip().lower()
        if novo == "s":
            cadastrar_aluno_com_nome(username, df)
        return

    aluno_id, username, criado = aluno
    print(Fore.GREEN + f"\nBem-vindo, {username}! (cadastrado em {criado})")

    while True:
        print("\n" + Fore.CYAN + Style.BRIGHT + f"=== MENU DE '{username}' ===")
        print(f"  [1] Ver minhas aulas de hoje ({DIA_PT})")
        print(f"  [2] Ver todas as minhas matérias cadastradas")
        print(f"  [3] Gerenciar minhas matérias (adicionar/remover)")
        print(f"  [0] Voltar")

        escolha = input(Fore.WHITE + "\nEscolha: ").strip()

        if escolha == "0":
            break

        elif escolha == "1":
            materias_hoje = listar_materias_aluno(aluno_id, dia=DIA_PT)
            print("\n" + "=" * 85)
            print(Fore.GREEN + Style.BRIGHT + f"  Suas aulas de hoje ({DIA_PT} - {HOJE})")
            print("=" * 85)
            if not materias_hoje:
                print(Fore.YELLOW + f"  Nenhuma matéria cadastrada para {DIA_PT}.")
            else:
                for _, dia, turma, disciplina, professor in materias_hoje:
                    # Busca a sala no CSV do dia
                    resultado = filtrar_df(df, f"{turma} {disciplina}")
                    if resultado.empty:
                        # Fallback: busca só pela disciplina
                        resultado = filtrar_df(df, disciplina[:20])

                    print(Fore.YELLOW + f"\n  {disciplina}  |  {turma}  |  {professor}")
                    if resultado.empty:
                        print(Fore.RED + "    Sala não encontrada para hoje.")
                    else:
                        subset = resultado.drop(columns=["Categoria"]).reset_index(drop=True)
                        print(tabulate(subset.fillna(""), headers="keys",
                                       tablefmt="rounded_outline", showindex=False))

        elif escolha == "2":
            todas = listar_materias_aluno(aluno_id)
            print("\n" + "=" * 85)
            print(Fore.GREEN + Style.BRIGHT + f"  Todas as matérias de '{username}'")
            print("=" * 85)
            if not todas:
                print(Fore.YELLOW + "  Nenhuma matéria cadastrada.")
            else:
                rows = [{"Dia": m[1], "Turma": m[2], "Disciplina": m[3], "Professor": m[4]}
                        for m in todas]
                print(tabulate(rows, headers="keys", tablefmt="rounded_outline", showindex=False))

        elif escolha == "3":
            gerenciar_materias(aluno_id, username, df)

        else:
            print(Fore.RED + "Opcao invalida.")


def cadastrar_aluno_com_nome(username, df):
    aluno_id = criar_aluno(username)
    print(Fore.GREEN + f"Aluno '{username}' criado!")
    gerenciar_materias(aluno_id, username, df)


# ── Menu principal ────────────────────────────────────────────────────────────

def menu_principal(df):
    while True:
        print("\n" + Fore.CYAN + Style.BRIGHT + "╔══════════════════════════════════════╗")
        print(Fore.CYAN + Style.BRIGHT +         "║         MAPA DE SALAS IBMEC          ║")
        print(Fore.CYAN + Style.BRIGHT +         "╚══════════════════════════════════════╝")
        print(Fore.WHITE + f"  {DIA_PT}, {HOJE}\n")
        print(f"  [1] Consulta imediata")
        print(f"  [2] Estou cadastrado")
        print(f"  [3] Criar cadastro")
        print(f"  [0] Sair")

        escolha = input(Fore.WHITE + "\nEscolha: ").strip()

        if escolha == "0":
            print(Fore.GREEN + "Encerrando...")
            break
        elif escolha == "1":
            menu_consulta_imediata(df)
        elif escolha == "2":
            login_aluno(df)
        elif escolha == "3":
            cadastrar_aluno(df)
        else:
            print(Fore.RED + "Opcao invalida.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    init_db()

    print(Fore.CYAN + Style.BRIGHT + """
╔══════════════════════════════════════════════════╗
║     VISUALIZADOR DE PLANILHA GOOGLE SHEETS       ║
╚══════════════════════════════════════════════════╝
""")

    if csv_hoje_existe():
        df = carregar_do_cache()
    else:
        print(Fore.YELLOW + "Nenhum cache para hoje. Buscando planilha...")
        try:
            df_bruto = buscar_planilha_remota()
        except Exception as e:
            print(Fore.RED + f"Erro ao buscar planilha: {e}")
            return
        print(Fore.CYAN + "Organizando dados...")
        df = parsear_e_organizar(df_bruto)
        salvar_csv(df)

    print()
    for nome in TITULOS_CATEGORIA:
        print(Fore.GREEN + f"  {nome}: {len(df[df['Categoria'] == nome])} registros")

    menu_principal(df)


if __name__ == "__main__":
    main()
