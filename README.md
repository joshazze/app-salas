# IBSALA — Sistema de Mapa de Salas

```
██╗██████╗ ███████╗ █████╗ ██╗      █████╗
██║██╔══██╗██╔════╝██╔══██╗██║     ██╔══██╗
██║██████╔╝███████╗███████║██║     ███████║
██║██╔══██╗╚════██║██╔══██║██║     ██╔══██║
██║██████╔╝███████║██║  ██║███████╗██║  ██║
╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
// IBtech · Sistema de Consulta de Salas
```

> Plataforma web para consulta em tempo real de salas, horários e professores do **IBMEC BH**.
> Acesse em: **[ibsala.com.br](https://ibsala.com.br)**

---

## // O QUE É

O IBSALA captura diariamente a planilha oficial de salas da instituição e disponibiliza as informações de forma rápida e organizada para qualquer aluno — sem necessidade de login para consultas públicas.

Alunos cadastrados têm acesso ao painel pessoal com suas aulas do dia, gerenciamento de matérias e recebem notificações automáticas por email antes de cada turno.

---

## // FUNCIONALIDADES

### Público (sem login)
- `[1]` **Consulta imediata** — navegue por categoria (manhã, tarde, noite) ou use a busca livre
- `[4]` **Sobre o IBSALA** — documentação da plataforma

### Aluno cadastrado
- Painel pessoal com aulas do dia (sala, horário, professor)
- Visualização de todas as matérias cadastradas
- Gerenciamento de matérias por dia da semana
- Preferência de recebimento de emails
- Recuperação de username por email

### Administrador
- Banco permanente de disciplinas (adicionar, editar, excluir)
- Banco de alunos (criar, editar, bloquear, excluir)
- Recapturar planilha manualmente
- Envio de emails: teste, todos os alunos, mensagem personalizada
- Travar/destrancar o site inteiro com um clique

---

## // STACK

| Camada | Tecnologia |
|---|---|
| Backend | Python 3 · Flask · SQLite |
| Frontend | HTML/CSS/JS puro (single-page, sem framework) |
| Email | Gmail API (OAuth2) |
| Planilha | Google Sheets API + fallback público |
| Agendador | APScheduler |
| Servidor | Nginx (reverse proxy, HTTPS, rate limiting) |
| Infraestrutura | Google Cloud — Compute Engine (VM) |
| Certificado | Let's Encrypt (renovação automática) |

---

## // ARQUITETURA

```
ibsala.com.br
     │
     ▼
  [ Nginx ]  ← HTTPS, rate limiting, www → canonical redirect
     │
     ▼
  [ Flask :5000 ]
     ├── GET  /              → index.html (SPA)
     ├── GET  /api/status    → dia, registros hoje, total alunos/disciplinas
     ├── POST /api/buscar    → busca livre filtrada por dia
     ├── GET  /api/categoria → registros por categoria filtrados por dia
     ├── POST /api/login     → acesso do aluno por username
     ├── POST /api/cadastrar → novo aluno
     ├── POST /api/configuracoes    → toggle receber email
     ├── POST /api/recuperar-username → envia username por email
     └── POST /api/adm/*    → painel administrativo (autenticado)

  [ SQLite ]
     ├── alunos (id, username, email, criado, bloqueado, receber_email)
     ├── materias (aluno_id, dia, turma, disciplina, professor)
     └── disciplinas_historico (turma, disciplina, professor)

  [ Scheduler ] — processo separado (APScheduler)
     ├── 07:10 → captura planilha + notifica turno manhã
     ├── 09:30 → notifica turno manhã (segunda janela)
     ├── 13:10 → notifica turno tarde
     ├── 15:30 → notifica turno tarde (segunda janela)
     └── 17:20 → notifica turno noite
```

---

## // COMO RODAR LOCALMENTE

### Pré-requisitos
- Python 3.10+
- Conta Google com acesso à planilha
- Credenciais OAuth2 do Google (Gmail API + Sheets API)

### Instalação

```bash
git clone https://github.com/joshazze/app-salas.git
cd app-salas
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuração

Coloque na raiz do projeto:
- `gmail_credentials.json` — credenciais OAuth2 para envio de email
- `gmail_token.json` — token gerado após primeiro login (Gmail)

Defina a variável de ambiente para a senha do administrador:

```bash
export ADM_PASSWORD="sua_senha_aqui"
```

### Executar

```bash
# Servidor web
python3 server.py

# Agendador (em processo separado)
python3 scheduler.py
```

Acesse em `http://localhost:5000`

---

## // SEGURANÇA

- Rate limiting via Nginx: 20 req/min nas rotas de autenticação, 60 req/min geral
- Senha do administrador via variável de ambiente (não commitada)
- Credenciais Google fora do repositório (`.gitignore`)
- HSTS habilitado, redirecionamento forçado para HTTPS
- Alunos identificados apenas por username (sem senha exposta)
- Bloqueio de alunos via painel admin

---

## // DEPLOY (produção)

O projeto roda em uma VM do **Google Cloud Compute Engine** com:

- Nginx como reverse proxy com SSL via Let's Encrypt
- Aplicação Flask gerenciada por `systemd`
- Scheduler rodando como serviço separado via `systemd`
- Banco SQLite com backup manual periódico

---

## // CRÉDITOS

Desenvolvido por **Joshua Azze** para o **IBtech (IBMEC)**
Contato: [salas.ibtech@gmail.com](mailto:salas.ibtech@gmail.com)

```
© Joshua Azze & IBtech — Todos os direitos reservados.
```
