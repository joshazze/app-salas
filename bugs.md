# IBSALA — Registro de Bugs e Correções

> **Instrução para o agente:** Sempre leia este arquivo antes de corrigir qualquer bug.
> Não corrija o que já está documentado como corrigido. Após nova correção, adicione uma entrada aqui.

---

## Bugs Corrigidos

### [CRÍTICO] Variáveis globais estáticas congeladas na carga do módulo
- **Arquivo:** `visualizar_planilha.py`
- **Problema:** `HOJE`, `DIA_SEMANA`, `CSV_HOJE`, `DIA_PT` eram definidas uma vez na inicialização e nunca atualizadas. Após meia-noite o sistema operava com data do dia anterior.
- **Correção:** Variáveis removidas. Toda a base de código já usava `_hoje()`, `_dia_pt()` dinamicamente.
- **Data:** 2026-03-12

---

### [CRÍTICO] Race condition no cache do DataFrame
- **Arquivo:** `server.py` — `get_df()`
- **Problema:** A checagem `if _df is not None and _df_data == hoje` ocorria fora do `_df_lock`, permitindo que duas threads carregassem o CSV simultaneamente.
- **Correção:** Toda a lógica de checagem e carregamento movida para dentro do bloco `with _df_lock`.
- **Data:** 2026-03-12

---

### [CRÍTICO] Normalizadores inconsistentes entre server.py e visualizar_planilha.py
- **Arquivo:** `server.py` — `get_df_hoje()`
- **Problema:** `server.py` usava `_sem_acento()` (uppercase) e `visualizar_planilha.py` usava `_normalizar_texto()` (lowercase) para a mesma operação de filtragem por dia.
- **Correção:** Removida `_sem_acento()` de `server.py`. `get_df_hoje()` agora usa `vp._normalizar_texto()` em ambos os lados.
- **Data:** 2026-03-12

---

### [CRÍTICO] Slot não validado no backend
- **Arquivo:** `server.py` — `/api/atualizar-slot` e `/api/adicionar-materia`
- **Problema:** Qualquer string era aceita como valor de slot e salva no banco. O frontend exibia `undefined` para slots inválidos.
- **Correção:** Adicionada validação `if slot is not None and slot not in vp.SLOTS` em ambas as rotas.
- **Data:** 2026-03-12

---

### [CRÍTICO] Username "josh" hardcoded na rota de email de teste
- **Arquivo:** `server.py` — `/api/adm/email/teste`
- **Problema:** Se o usuário "josh" fosse renomeado ou excluído, a funcionalidade de email de teste quebrava.
- **Correção:** Substituído por query `SELECT id, username FROM alunos WHERE bloqueado=0 LIMIT 1` — usa o primeiro aluno disponível.
- **Data:** 2026-03-12

---

### [MÉDIO] Função morta `_horario_na_janela()`
- **Arquivo:** `visualizar_planilha.py`
- **Problema:** Função definida mas nunca chamada — resquício de implementação anterior de filtro por janela horária.
- **Correção:** Função removida.
- **Data:** 2026-03-12

---

### [MÉDIO] Função morta `contar_salas()`
- **Arquivo:** `visualizar_planilha.py`
- **Problema:** Função definida mas nunca chamada. Referenciava tabela `salas_historico` que não existe no schema atual.
- **Correção:** Função removida.
- **Data:** 2026-03-12

---

### [MÉDIO] Slot labels hardcoded em `email_boas_vindas()`
- **Arquivo:** `visualizar_planilha.py`
- **Problema:** Dict `slot_labels` com horários hardcoded dentro da função. Ao mudar horários no dict `SLOTS`, os emails ficavam desatualizados.
- **Correção:** Substituído por `{k: f"{v['label']} ({v['hora']})" for k, v in SLOTS.items()}` — derivado dinamicamente do dict `SLOTS`.
- **Data:** 2026-03-12

---

### [MÉDIO] Campo `hora` ausente no dict SLOTS
- **Arquivo:** `visualizar_planilha.py`
- **Problema:** Não havia fonte única de verdade para o horário de exibição de cada slot (o campo `inicio` é a janela de captura, não o horário da aula).
- **Correção:** Adicionado campo `"hora"` a cada slot em `SLOTS` (ex: `"hora": "07:30"`). Usado em emails e labels.
- **Data:** 2026-03-12

---

### [MÉDIO] Duplicação de constantes SLOT em app.js
- **Arquivo:** `static/app.js`
- **Problema:** `SLOT_INI`, `SLOT_FIM`, `SLOT_HORA`, `SLOT_ORDER` estavam definidas localmente dentro de `loadSalasLivres()`, `loadHoje()` e `loadTodas()` — 3 cópias com risco de divergência.
- **Correção:** Extraídas para constantes globais no topo do arquivo (linhas 26–29). Definições locais removidas.
- **Data:** 2026-03-12

---

### [MÉDIO] Scheduler recalculava data manualmente
- **Arquivo:** `scheduler.py` — `rotina_atualizacao()`
- **Problema:** Usava `datetime.now().strftime(...)` e `vp.DIAS_PT.get(...)` diretamente em vez das funções `vp._hoje()` / `vp._dia_pt()`, duplicando lógica e ignorando variável `csv_hoje` que era calculada mas nunca usada.
- **Correção:** Substituído por `hoje = vp._hoje()` e `dia_pt = vp._dia_pt()`. Variável `csv_hoje` removida.
- **Data:** 2026-03-12

---

### [MÉDIO] Status file do scheduler sem escrita atômica
- **Arquivo:** `scheduler.py` — `_salvar_status()`
- **Problema:** Arquivo JSON escrito diretamente — se o processo morresse durante a escrita, o arquivo ficava corrompido.
- **Correção:** Escrita feita em arquivo temporário `.tmp` seguida de `os.replace()` — operação atômica no Linux.
- **Data:** 2026-03-12

---

### [BAIXO] Email sem validação de formato no backend
- **Arquivo:** `server.py` — `/api/cadastrar`
- **Problema:** Qualquer string era aceita como email e salva no banco. Envios falhavam silenciosamente.
- **Correção:** Adicionada validação com `re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)`.
- **Data:** 2026-03-12

---

### [BAIXO] Username não forçado para lowercase no cadastro
- **Arquivo:** `server.py` — `/api/cadastrar`
- **Problema:** A busca usava `WHERE LOWER(username)` mas o cadastro não forçava lowercase, permitindo criar `@JOSH` e `@josh` como contas separadas via API direta.
- **Correção:** `username = data.get("username", "").strip().lower()` e `email = data.get("email", "").strip().lower()`.
- **Data:** 2026-03-12

---

### [BAIXO] Mensagens de erro revelavam username/email existentes
- **Arquivo:** `server.py` — `/api/cadastrar`
- **Problema:** Mensagens `"Username 'X' ja existe"` e `"Email 'X' ja esta cadastrado"` permitiam enumerar usuários e emails válidos.
- **Correção:** Mensagens genéricas: `"Username indisponivel"` e `"Email ja cadastrado"`.
- **Data:** 2026-03-12

---

### [BAIXO] Sem limite de tamanho na mensagem de email custom
- **Arquivo:** `server.py` — `/api/adm/email/custom`
- **Problema:** Mensagem sem limite de tamanho — potencial DoS de memória.
- **Correção:** Adicionado `if len(mensagem) > 5000: return 400`.
- **Data:** 2026-03-12

---

### [BAIXO] `api()` no frontend descartava corpo do erro HTTP
- **Arquivo:** `static/app.js` — `api()`
- **Problema:** `if(!r.ok) return {erro: "Erro HTTP 400"}` — descartava o JSON de erro do servidor, exibindo mensagem genérica.
- **Correção:** `if(!r.ok){ try{ return await r.json(); } catch(_){ return {erro: "Erro HTTP N"}; } }`
- **Data:** 2026-03-12

---

### [BAIXO] Crash silencioso em `loadHoje()` quando API retorna erro
- **Arquivo:** `static/app.js` — `loadHoje()`
- **Problema:** `d.aulas.length` crashava com TypeError se `d = {erro: "..."}` (d.aulas undefined).
- **Correção:** Guard `if(d.erro){ el.innerHTML = ...; return; }` adicionado antes de acessar `d.aulas`.
- **Data:** 2026-03-12

---

### [BAIXO] `loadHoje()` chamada sem aluno logado via histórico do browser
- **Arquivo:** `static/app.js` — `loadHoje()`
- **Problema:** Navegação pelo histórico do browser (`popstate`) podia chamar `loadHoje()` com `G.alunoId = null`, gerando HTTP 400.
- **Correção:** Guard `if(!G.alunoId){ goto('s-main'); return; }` adicionado no início de `loadHoje()`.
- **Data:** 2026-03-12

---

### [BAIXO] Crash silencioso em `loadTodas()`, `loadGer()`, `gerBuscar()`, `cadBuscar()`, `loadAdmDisc()`
- **Arquivo:** `static/app.js`
- **Problema:** Todas acessavam `.length` em propriedades de `d` sem verificar `d.erro` primeiro.
- **Correção:** Guards `if(d.erro){ el.innerHTML = ...; return; }` adicionados em cada função.
- **Data:** 2026-03-12

---

### [BAIXO] `admToggleLock()` podia travar o site acidentalmente
- **Arquivo:** `static/app.js` — `admToggleLock()`
- **Problema:** `const novo = !d.travado` onde `d.travado` seria `undefined` em erro → `!undefined = true` → site travava.
- **Correção:** Guard `if(d.erro){ alert(...); return; }` adicionado.
- **Data:** 2026-03-12

---

## Inconsistências Conhecidas (não corrigidas)

| # | Descrição | Decisão |
|---|-----------|---------|
| A | `Salas` vs `Sala` (singular/plural) na coluna do CSV — código faz fallback | Mantido — depende da planilha da instituição |
| B | Sem CSRF token — mitigado pelo CORS | Mantido — adicionar quebraria o fluxo SPA |
| C | Sem logging estruturado (usa `print()`) | Mantido — complexidade desnecessária no momento |
| D | Timezone `America/Sao_Paulo` hardcoded no scheduler | Mantido — servidor está em São Paulo |

---

## Mudanças de Configuração de Slots

### Tarde 1 e Tarde 2 — janelas redefinidas
- **Data:** 2026-03-12
- **Motivo:** Análise dos horários reais da planilha mostrou dois blocos distintos: 13:00–14:00 e 15:50+
- **Antes:** tarde1 (13:00–13:59), tarde2 (14:00–17:59), disparo tarde2 às 13:30
- **Depois:** tarde1 (13:00–15:29), tarde2 (15:30–17:59), disparo tarde2 às 15:20
- **Arquivos afetados:** `visualizar_planilha.py`, `scheduler.py`, `app.js`, `templates/index.html`
