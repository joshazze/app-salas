"""
Servidor Flask — API para o Mapa de Salas IBMEC
"""

import os
import threading
import json

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

import visualizar_planilha as vp

app = Flask(__name__)
CORS(app)

# ── Admin ─────────────────────────────────────────────────────────────────────

ADM_USERNAME = "adm"
ADM_PASSWORD = os.environ.get("ADM_PASSWORD", "osmargostoso")
LOCK_FILE    = os.path.join(os.path.dirname(__file__), "site_lock.json")


def site_travado():
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE) as f:
            return json.load(f).get("travado", False)
    except Exception:
        return False


def set_trava(estado):
    with open(LOCK_FILE, "w") as f:
        json.dump({"travado": estado}, f)


def check_adm(data):
    return (data.get("adm_user","").lower() == ADM_USERNAME.lower() and
            data.get("adm_pass","").lower() == ADM_PASSWORD.lower())


@app.before_request
def verificar_trava():
    if not site_travado():
        return
    if request.path.startswith("/api/adm") or request.path == "/":
        return
    if request.path.startswith("/api/"):
        return jsonify({"erro": "Site temporariamente indisponivel."}), 503


# ── Cache global do DataFrame ─────────────────────────────────────────────────

_df = None


def get_df():
    global _df
    if _df is None:
        if vp.csv_hoje_existe():
            _df = vp.carregar_do_cache()
        else:
            df_bruto = vp.buscar_planilha_remota()
            _df = vp.parsear_e_organizar(df_bruto)
            vp.salvar_csv(_df)
    return _df


def df_para_lista(df):
    return df.fillna("").to_dict(orient="records")


# ── Rotas públicas ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    df = get_df()
    resumo = {cat: int(len(df[df["Categoria"] == cat])) for cat in vp.TITULOS_CATEGORIA}
    return jsonify({
        "hoje":       vp.HOJE,
        "dia":        vp.DIA_PT,
        "csv":        vp.CSV_HOJE,
        "total":      int(len(df)),
        "categorias": resumo,
        "travado":    site_travado(),
    })


@app.route("/api/buscar", methods=["POST"])
def buscar():
    termo = (request.json or {}).get("termo", "").strip()
    if not termo:
        return jsonify({"erro": "Termo vazio"}), 400
    df = get_df()
    resultado = vp.filtrar_df(df, termo)
    registros = df_para_lista(resultado)
    return jsonify({"termo": termo, "total": len(registros), "registros": registros})


@app.route("/api/categoria/<path:nome>")
def categoria(nome):
    df = get_df()
    subset = df[df["Categoria"] == nome]
    return jsonify({"categoria": nome, "registros": df_para_lista(subset)})


@app.route("/api/login", methods=["POST"])
def login():
    username = (request.json or {}).get("username", "").strip()
    if not username:
        return jsonify({"erro": "Username vazio"}), 400
    aluno = vp.buscar_aluno(username)
    if not aluno:
        return jsonify({"encontrado": False})
    aluno_id, username, criado = aluno
    if vp.aluno_bloqueado(aluno_id):
        return jsonify({"encontrado": False, "bloqueado": True})
    return jsonify({"encontrado": True, "aluno_id": aluno_id,
                    "username": username, "criado": criado})


@app.route("/api/aulas-hoje", methods=["POST"])
def aulas_hoje():
    aluno_id = (request.json or {}).get("aluno_id")
    if not aluno_id:
        return jsonify({"erro": "aluno_id ausente"}), 400

    df = get_df()
    materias = vp.listar_materias_aluno(aluno_id, dia=vp.DIA_PT)
    resultado = []

    for _, dia, turma, disciplina, professor in materias:
        linhas = vp.filtrar_df(df, f"{turma} {disciplina}")
        if linhas.empty:
            linhas = vp.filtrar_df(df, " ".join(disciplina.split()[:3]))
        resultado.append({
            "disciplina": disciplina,
            "turma":      turma,
            "professor":  professor,
            "salas":      df_para_lista(linhas),
        })

    return jsonify({"dia": vp.DIA_PT, "hoje": vp.HOJE, "aulas": resultado})


@app.route("/api/minhas-materias", methods=["POST"])
def minhas_materias():
    aluno_id = (request.json or {}).get("aluno_id")
    if not aluno_id:
        return jsonify({"erro": "aluno_id ausente"}), 400
    rows = vp.listar_materias_aluno(aluno_id)
    materias = [{"id": r[0], "dia": r[1], "turma": r[2],
                 "disciplina": r[3], "professor": r[4]} for r in rows]
    return jsonify({"materias": materias})


@app.route("/api/cadastrar", methods=["POST"])
def cadastrar():
    data     = request.json or {}
    username = data.get("username", "").strip()
    email    = data.get("email", "").strip()
    materias = data.get("materias", [])

    if not username:
        return jsonify({"erro": "Username vazio"}), 400
    if not email:
        return jsonify({"erro": "Email obrigatorio"}), 400
    if vp.buscar_aluno(username):
        return jsonify({"erro": f"Username '{username}' ja existe"}), 409
    if vp.buscar_aluno_por_email(email):
        return jsonify({"erro": f"Email '{email}' ja esta cadastrado"}), 409

    aluno_id = vp.criar_aluno(username, email)
    for m in materias:
        vp.salvar_materia(aluno_id, m["dia"], m["turma"], m["disciplina"], m["professor"])

    threading.Thread(target=vp.email_boas_vindas, args=(username, email, materias), daemon=True).start()

    return jsonify({"ok": True, "aluno_id": aluno_id, "username": username,
                    "salvas": len(materias)})


@app.route("/api/adicionar-materia", methods=["POST"])
def adicionar_materia():
    data = request.json or {}
    vp.salvar_materia(data["aluno_id"], data["dia"], data["turma"],
                      data["disciplina"], data["professor"])
    return jsonify({"ok": True})


@app.route("/api/remover-materia", methods=["POST"])
def remover_materia():
    data = request.json or {}
    vp.remover_materia(data["aluno_id"], data["materia_id"])
    return jsonify({"ok": True})


@app.route("/api/buscar-disciplinas", methods=["POST"])
def buscar_disciplinas():
    termo = (request.json or {}).get("termo", "").strip()
    if not termo:
        return jsonify({"erro": "Termo vazio"}), 400
    registros = vp.buscar_disciplinas_historico(termo)
    return jsonify({"total": len(registros), "registros": registros})


@app.route("/api/verificar-username", methods=["POST"])
def verificar_username():
    username = (request.json or {}).get("username", "").strip()
    existe = vp.buscar_aluno(username) is not None
    return jsonify({"disponivel": not existe})


# ── Rotas Admin ───────────────────────────────────────────────────────────────

@app.route("/api/adm/login", methods=["POST"])
def adm_login():
    data = request.json or {}
    if check_adm(data):
        return jsonify({"ok": True, "travado": site_travado()})
    return jsonify({"ok": False}), 401


@app.route("/api/adm/trava", methods=["POST"])
def adm_trava():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    estado = data.get("travado", False)
    set_trava(estado)
    return jsonify({"ok": True, "travado": estado})


@app.route("/api/adm/disciplinas", methods=["POST"])
def adm_disciplinas():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    rows = vp.listar_disciplinas_historico()
    return jsonify({"registros": [
        {"id": r[0], "turma": r[1], "disciplina": r[2], "professor": r[3]} for r in rows
    ]})


@app.route("/api/adm/disciplinas/adicionar", methods=["POST"])
def adm_disc_adicionar():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    vp.adicionar_disciplina_historico(data["turma"], data["disciplina"], data["professor"])
    return jsonify({"ok": True})


@app.route("/api/adm/disciplinas/editar", methods=["POST"])
def adm_disc_editar():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    vp.editar_disciplina_historico(data["id"], data["turma"], data["disciplina"], data["professor"])
    return jsonify({"ok": True})


@app.route("/api/adm/disciplinas/excluir", methods=["POST"])
def adm_disc_excluir():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    vp.excluir_disciplina_historico(data["id"])
    return jsonify({"ok": True})


@app.route("/api/adm/alunos", methods=["POST"])
def adm_alunos():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    rows = vp.listar_todos_alunos()
    return jsonify({"registros": [
        {"id": r[0], "username": r[1], "email": r[2], "criado": r[3], "bloqueado": bool(r[4])}
        for r in rows
    ]})


@app.route("/api/adm/alunos/adicionar", methods=["POST"])
def adm_aluno_adicionar():
    data     = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    username = data.get("username", "").strip()
    email    = data.get("email", "").strip()
    if not username or not email:
        return jsonify({"erro": "Username e email obrigatorios"}), 400
    if vp.buscar_aluno(username):
        return jsonify({"erro": f"Username '{username}' ja existe"}), 409
    aluno_id = vp.criar_aluno(username, email)
    return jsonify({"ok": True, "aluno_id": aluno_id})


@app.route("/api/adm/alunos/editar", methods=["POST"])
def adm_aluno_editar():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    vp.editar_aluno(data["id"], data["username"], data["email"])
    return jsonify({"ok": True})


@app.route("/api/adm/alunos/bloquear", methods=["POST"])
def adm_aluno_bloquear():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    vp.set_bloqueio_aluno(data["id"], data.get("bloqueado", True))
    return jsonify({"ok": True})


@app.route("/api/adm/alunos/excluir", methods=["POST"])
def adm_aluno_excluir():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    vp.excluir_aluno(data["id"])
    return jsonify({"ok": True})


@app.route("/api/adm/email/todos", methods=["POST"])
def adm_email_todos():
    import threading
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    df = get_df()
    threading.Thread(target=vp.notificar_todos, args=(df, vp.DIA_PT), daemon=True).start()
    return jsonify({"ok": True, "msg": "Envio iniciado em background."})


@app.route("/api/adm/email/custom", methods=["POST"])
def adm_email_custom():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    destinatarios = data.get("destinatarios", [])
    assunto       = data.get("assunto", "").strip()
    mensagem      = data.get("mensagem", "").strip()
    if not assunto or not mensagem or not destinatarios:
        return jsonify({"erro": "Campos incompletos"}), 400

    corpo = f"""
    <div style='background:#080c10;color:#c9d1d9;font-family:Courier New,monospace;padding:24px;max-width:600px'>
      <div style='border-bottom:1px solid #1a2a3a;padding-bottom:12px;margin-bottom:20px'>
        <span style='color:#1e90ff;font-size:16px;letter-spacing:2px'>IBSALA</span>
        <span style='color:#4a5a6a'> // </span>
        <span style='color:#6e7a8a;font-size:12px'>IBtech</span>
      </div>
      <div style='white-space:pre-wrap;font-size:14px'>{mensagem}</div>
      <div style='color:#4a5a6a;font-size:11px;margin-top:20px;border-top:1px solid #1a2a3a;padding-top:12px'>
        Este email foi enviado pelo administrador do sistema IBtech.
      </div>
    </div>"""

    enviados = 0
    erros    = 0
    for d in destinatarios:
        try:
            vp.enviar_email(d["email"], assunto, corpo)
            enviados += 1
        except Exception:
            erros += 1
    return jsonify({"ok": True, "enviados": enviados, "erros": erros})


@app.route("/api/adm/email/aluno", methods=["POST"])
def adm_email_aluno():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    aluno_id = data.get("aluno_id")
    if not aluno_id:
        return jsonify({"erro": "aluno_id ausente"}), 400

    row = vp.buscar_aluno_por_id(aluno_id)
    if not row:
        return jsonify({"erro": "Aluno nao encontrado"}), 404
    username, email = row
    if not email:
        return jsonify({"erro": "Aluno sem email"}), 400

    df = get_df()
    materias = vp.listar_materias_aluno(aluno_id, dia=vp.DIA_PT)
    aulas = []
    for _, dia, turma, disciplina, professor in materias:
        linhas = vp.filtrar_df(df, f"{turma} {disciplina}")
        if linhas.empty:
            linhas = vp.filtrar_df(df, " ".join(disciplina.split()[:3]))
        aulas.append({
            "disciplina": disciplina,
            "turma":      turma,
            "professor":  professor,
            "salas":      linhas.fillna("").to_dict(orient="records"),
        })

    assunto, corpo = vp._montar_email_aulas(username, vp.DIA_PT, aulas)
    if not assunto:
        return jsonify({"erro": "Nenhuma aula hoje"}), 400
    vp.enviar_email(email, assunto, corpo)
    return jsonify({"ok": True})


@app.route("/api/adm/recapturar", methods=["POST"])
def adm_recapturar():
    global _df
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    try:
        df_bruto = vp.buscar_planilha_remota()
        _df = vp.parsear_e_organizar(df_bruto)
        vp.salvar_csv(_df)
        return jsonify({"ok": True, "total": int(len(_df))})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/adm/status-trava", methods=["POST"])
def adm_status_trava():
    data = request.json or {}
    if not check_adm(data):
        return jsonify({"erro": "Nao autorizado"}), 401
    return jsonify({"travado": site_travado()})


# ── Init ──────────────────────────────────────────────────────────────────────

vp.init_db()

if __name__ == "__main__":
    print(f"\n  Servidor rodando em: http://localhost:5000\n")
    app.run(debug=False, host="0.0.0.0", port=5000)
