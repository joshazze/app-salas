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
- **Consulta imediata** — navegue por categoria (manhã, tarde, noite) ou use a busca livre
- **Salas livres por turno** — toggle na busca livre mostra quais salas estão desocupadas em cada um dos 6 turnos; turno atual destacado com badge `AGORA`
- **Sobre o IBSALA** — documentação da plataforma acessível no menu

### Aluno cadastrado
- **Aulas de hoje** — painel principal pós-login com sala, horário e professor de cada disciplina do dia
- **Todas as matérias** — lista completa de matérias cadastradas, acessível a partir do painel de aulas
- **Configurações** — toggle de recebimento de emails e gerenciamento de matérias por dia da semana e turno
- **Recuperação de username** — envio do username por email
- **Email de boas-vindas** automático no momento do cadastro

### Administrador
- Banco permanente de disciplinas (adicionar, editar, excluir — código separado do nome)
- Banco de alunos (criar, editar, bloquear, excluir)
- Envio de email individual para qualquer aluno com a grade do dia
- Envio de email para todos os alunos com as aulas do dia
- Envio de email de teste para verificação de configuração
- Recapturar planilha manualmente a qualquer momento
- Travar/destrancar o site inteiro com um clique

---

## // STACK

| Camada | Tecnologia |
|---|---|
| Backend | Python 3 · Flask · SQLite |
| Frontend | HTML/CSS/JS puro (single-page, sem framework) |
| Email | Gmail API (OAuth2) |
| Planilha | Google Sheets API + fallback público (CSV) |
| Agendador | APScheduler |
| Servidor | Nginx (reverse proxy, HTTPS, rate limiting) |
| Infraestrutura | Google Cloud — Compute Engine (VM e2-standard-2) |
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
  [ Gunicorn + Flask :5000 ]
     ├── GET  /                        → index.html (SPA)
     ├── GET  /api/status              → dia, registros hoje, total alunos/disciplinas
     ├── POST /api/buscar              → busca livre filtrada por dia
     ├── GET  /api/categoria           → registros por categoria filtrados por dia
     ├── GET  /api/salas-livres        → salas desocupadas por turno
     ├── POST /api/login               → acesso do aluno por username
     ├── POST /api/cadastrar           → novo aluno
     ├── POST /api/minhas-aulas        → aulas do dia do aluno logado
     ├── POST /api/materias            → listar matérias do aluno
     ├── POST /api/adicionar-materia   → adicionar matéria
     ├── POST /api/remover-materia     → remover matéria
     ├── POST /api/configuracoes       → toggle receber email
     ├── POST /api/recuperar-username  → envia username por email
     └── POST /api/adm/*              → painel administrativo (autenticado)
          ├── /api/adm/status          → saúde do sistema
          ├── /api/adm/recapturar      → força nova captura da planilha
          ├── /api/adm/travar          → bloqueia/desbloqueia acesso público
          ├── /api/adm/alunos          → listar/criar/editar/bloquear alunos
          ├── /api/adm/email/aluno     → email do dia para aluno específico
          ├── /api/adm/email/todos     → email do dia para todos os alunos
          ├── /api/adm/email/teste     → email de teste
          └── /api/adm/disciplinas     → CRUD do banco de disciplinas

  [ SQLite — /home/salas_ibtech/data/alunos.db ]
     ├── alunos (id, username, email, criado, bloqueado, receber_email)
     ├── materias (aluno_id, dia, turma, disciplina, professor)
     └── disciplinas_historico (turma, codigo, disciplina, professor)

  [ Scheduler ] — serviço systemd separado (APScheduler)
     ├── 07:10 → captura planilha + notifica 1º Manhã (07:30)
     ├── 09:30 → notifica 2º Manhã (09:50)
     ├── 13:00 → notifica 1º Tarde (13:00) e 2º Tarde (14:00)
     ├── 17:50 → notifica 1º Noite (18:00)
     └── 18:50 → notifica 2º Noite (19:00)
```

---

## // SEPARAÇÃO DE CÓDIGO E NOME DE DISCIPLINA

A planilha da instituição fornece disciplinas no formato `IBM0022-8001/ JURISDICAO E PROCESSO`. O sistema separa automaticamente:

- **Código** (`IBM0022-8001`) — armazenado internamente, visível apenas no painel admin
- **Nome** (`JURISDICAO E PROCESSO`) — exibido em toda a interface do aluno, emails e buscas

Isso garante que o aluno veja apenas o nome limpo da disciplina, sem o código interno.

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

Variáveis de ambiente necessárias:

```bash
export ADM_PASSWORD="sua_senha_aqui"
export DB_PATH="/caminho/para/alunos.db"   # opcional, usa ./alunos.db por padrão
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
- Alunos identificados por username (sem armazenamento de senha)
- Bloqueio de alunos via painel admin
- Proteção contra encoding corrompido: limpeza de caracteres C1 (U+0080–U+009F) e normalização NFC em todos os dados da planilha

---

## // DEPLOY (produção)

O projeto roda em uma VM do **Google Cloud Compute Engine** com:

- Nginx como reverse proxy com SSL via Let's Encrypt
- Gunicorn (4 workers gevent) gerenciado por `systemd` (`app-salas`)
- Scheduler rodando como serviço separado via `systemd` (`app-salas-scheduler`)
- Banco SQLite em `/home/salas_ibtech/data/alunos.db`

---

## // CRÉDITOS

Desenvolvido por **Joshua Azze** para o **IBtech (IBMEC)**
Contato: [salas.ibtech@gmail.com](mailto:salas.ibtech@gmail.com)

```
© Joshua Azze & IBtech — Todos os direitos reservados.
```
