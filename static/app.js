const G={alunoId:null,username:null,statusData:null,cadUser:null,cadMats:[]};
function goto(id){
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  if(id==='s-hoje')loadHoje();
  if(id==='s-todas')loadTodas();
  if(id==='s-ger'){loadGer();loadEmailToggle();}
  if(id==='s-adm-disc')loadAdmDisc();
  if(id==='s-adm-alunos')loadAdmAlunos();
  if(id==='s-adm-email'){loadAdmAlunosPick();loadTesteAlunos();}
}
async function api(url,body){
  const o={headers:{'Content-Type':'application/json'}};
  if(body){o.method='POST';o.body=JSON.stringify(body);}
  return(await fetch(url,o)).json();
}
const COL_CLS={Sala:'c-sala',Horario:'c-hora',Turma:'c-turma',Categoria:'c-dim',Professor:'c-dim',Data:'c-hora',Dia:'c-dim'};
const SKIP_COLS=new Set(['Categoria','Salas','DATA','Sala','Data','Descricao','Responsavel']);
function normalizeRow(r){
  return Object.assign({},r,{
    Sala:r.Salas||r.Sala||'',
    Data:r.DATA||r.Data||''
  });
}
function mkTable(rows,cols){
  if(!rows.length)return'<div class="msg warn">Nenhum resultado.</div>';
  const norm=rows.map(normalizeRow);
  if(!cols){
    const base=['Turma','Disciplina','Professor','Horario','Sala','Data','Dia'];
    cols=base.filter(c=>norm.some(r=>r[c]&&r[c]!==''));
  }
  let h='<table class="tbl"><thead><tr>'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr></thead><tbody>';
  norm.forEach(r=>{h+='<tr>'+cols.map(c=>'<td class="'+(COL_CLS[c]||'')+'">'+( r[c]??'')+'</td>').join('')+'</tr>';});
  return h+'</tbody></table>';
}
function mkGroups(rows){
  if(!rows.length)return'<div class="msg warn">Nenhum resultado.</div>';
  const g={};
  rows.forEach(r=>{const k=r.Categoria||'---';(g[k]=g[k]||[]).push(r);});
  return Object.entries(g).map(([cat,rs])=>
    `<div class="cat-block"><div class="cat-label">${cat}</div>${mkTable(rs)}</div>`).join('');
}
function mkPickList(rows,onSelect){
  const ul=document.createElement('ul');ul.className='pick-list';
  rows.slice(0,15).forEach(row=>{
    const li=document.createElement('li');li.className='pick-item';
    const sala=row.Salas||row.Sala||'';
    const hora=row.Horario||'';
    li.innerHTML='<span class="pi-turma">'+(row.Turma||'')+'</span>'
      +'<span class="pi-disc">'+(row.Disciplina||'')+'</span>'
      +'<span class="pi-prof">'+(row.Professor||'')+'</span>'
      +(sala?'<span class="pi-sala">sala '+sala+'</span>':'')
      +(hora?'<span class="pi-hora">'+hora+'</span>':'');
    li.onclick=()=>onSelect(row);ul.appendChild(li);
  });
  return ul;
}
async function init(){
  const d=await api('/api/status');G.statusData=d;if(d.travado){document.body.classList.add('travado');}else{document.body.classList.remove('travado');}
  document.getElementById('hdr-meta').innerHTML=
    `<span class="hl">${d.dia}</span> &middot; <span class="hl">${d.hoje}</span> &middot; <span>${d.total} capturas de hoje</span> &middot; <span>${d.total_alunos} aluno(s)</span> &middot; <span>${d.total_disciplinas} disciplina(s)</span>`;
  const ul=document.getElementById('cat-menu');
  let idx=1;
  Object.entries(d.categorias).forEach(([cat,n])=>{
    if(n===0)return;
    const li=document.createElement('li');li.className='menu-item';
    li.innerHTML=`<span class="menu-key">${idx++}</span><span class="menu-label">${cat}</span><span class="menu-badge">${n} registros</span>`;
    li.onclick=()=>loadCat(cat);ul.appendChild(li);
  });
}
async function loadCat(nome){
  goto('s-cat');
  document.getElementById('s-cat-title').textContent=nome.toLowerCase();
  document.getElementById('s-cat-body').innerHTML='<div class="loading">carregando...</div>';
  const d=await api(`/api/categoria/${encodeURIComponent(nome)}`);
  const sorted=d.registros.slice().sort((a,b)=>(a.Horario||'').localeCompare(b.Horario||''));
  document.getElementById('s-cat-body').innerHTML=mkTable(sorted);
}
async function doBusca(){
  const termo=document.getElementById('busca-inp').value.trim();if(!termo)return;
  const out=document.getElementById('busca-out');
  out.innerHTML='<div class="loading">buscando...</div>';
  const d=await api('/api/buscar',{termo});
  out.innerHTML=`<div class="msg info" style="margin-bottom:14px">"${termo}" &mdash; ${d.total} resultado(s)</div>`+mkGroups(d.registros);
}
async function doLogin(){
  const un=document.getElementById("login-inp").value.trim().toLowerCase();
  const msg=document.getElementById('login-msg');if(!un)return;
  msg.innerHTML='<div class="loading">verificando...</div>';
  const d=await api('/api/login',{username:un});
  if(d.bloqueado){
    msg.innerHTML='<div class="msg error">acesso bloqueado. entre em contato com o administrador.</div>';
    return;
  }
  if(!d.encontrado){
    msg.innerHTML=`<div class="msg error">username "${un}" nao encontrado.</div>
      <div style="margin-top:8px;font-size:12px;color:var(--text-muted)">
        <button class="btn sm" onclick="irCadastro('${un}')">criar cadastro com este nome</button></div>`;
    return;
  }
  msg.innerHTML='';G.alunoId=d.aluno_id;G.username=d.username;
  document.getElementById('s-aluno-title').textContent=`ola, ${d.username}`;
  document.getElementById('badge-hoje').textContent=G.statusData?.dia||'';
  goto('s-aluno');
}
function doLogout(){
  G.alunoId=null;G.username=null;
  document.getElementById('login-inp').value='';
  document.getElementById('login-msg').innerHTML='';
  goto('s-main');
}
async function loadHoje(){
  const el=document.getElementById('s-hoje-body');
  document.getElementById('s-hoje-title').textContent=`aulas de hoje -- ${G.statusData?.dia||''}`;
  el.innerHTML='<div class="loading">carregando...</div>';
  const d=await api('/api/aulas-hoje',{aluno_id:G.alunoId});
  if(!d.aulas.length){el.innerHTML=`<div class="msg warn">Nenhuma materia para ${d.dia}.</div>`;return;}
  el.innerHTML=d.aulas.map(a=>{
    function aulaTable(rows){
      if(!rows.length)return '<div class="msg warn" style="font-size:12px">sala nao encontrada para hoje.</div>';
      const cols=[];
      if(rows.some(r=>r.Horario))cols.push('Horario');
      if(rows.some(r=>r.Salas||r.Sala))cols.push('Sala');
      if(rows.some(r=>r.DATA||r.Data))cols.push('Data');
      if(rows.some(r=>r.Dia))cols.push('Dia');
      if(!cols.length)return '<div class="msg warn" style="font-size:12px">sem detalhes disponiveis.</div>';
      let h='<table class="tbl"><thead><tr>'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr></thead><tbody>';
      rows.forEach(r=>{
        const sala=r.Salas||r.Sala||'';
        const data=r.DATA||r.Data||'';
        h+='<tr>'+cols.map(c=>{
          if(c==='Sala')return '<td class="c-sala">'+sala+'</td>';
          if(c==='Data')return '<td class="c-hora">'+data+'</td>';
          if(c==='Horario')return '<td class="c-hora">'+(r.Horario||'')+'</td>';
          if(c==='Dia')return '<td class="c-dim">'+(r.Dia||'')+'</td>';
          return '<td>'+(r[c]||'')+'</td>';
        }).join('')+'</tr>';
      });
      return h+'</tbody></table>';
    }
    return '<div class="aula-card">'
      +'<div class="aula-card-title">'+a.disciplina+'</div>'
      +'<div class="aula-card-meta">'+a.turma+' &nbsp;&middot;&nbsp; '+a.professor+'</div>'
      +aulaTable(a.salas)
      +'</div>';
  }).join('');
}
async function loadTodas(){
  const el=document.getElementById('s-todas-body');
  el.innerHTML='<div class="loading">carregando...</div>';
  const d=await api('/api/minhas-materias',{aluno_id:G.alunoId});
  if(!d.materias.length){el.innerHTML='<div class="msg warn">Nenhuma materia.</div>';return;}
  const g={};d.materias.forEach(m=>{(g[m.dia]=g[m.dia]||[]).push(m);});
  const DIA_ORDER=['SEGUNDA','TERCA','QUARTA','QUINTA','SEXTA','SABADO'];
  el.innerHTML=Object.entries(g).sort(([a],[b])=>DIA_ORDER.indexOf(a)-DIA_ORDER.indexOf(b)).map(([dia,mats])=>
    `<div class="cat-block"><div class="cat-label">${dia}</div>
    <table class="tbl"><thead><tr><th>Turma</th><th>Disciplina</th><th>Professor</th></tr></thead><tbody>
    ${mats.map(m=>`<tr><td class="c-turma">${m.turma}</td><td>${m.disciplina}</td><td class="c-dim">${m.professor}</td></tr>`).join('')}
    </tbody></table></div>`).join('');
}
async function loadGer(){
  const el=document.getElementById('s-ger-lista');
  el.innerHTML='<div class="loading">carregando...</div>';
  const d=await api('/api/minhas-materias',{aluno_id:G.alunoId});
  if(!d.materias.length){el.innerHTML='<div class="msg warn" style="margin-bottom:0">Nenhuma materia.</div>';return;}
  el.innerHTML=`<table class="tbl"><thead><tr><th>Dia</th><th>Turma</th><th>Disciplina</th><th>Professor</th><th></th></tr></thead><tbody>`+
  d.materias.map(m=>`<tr>
    <td class="c-hora">${m.dia}</td><td class="c-turma">${m.turma}</td>
    <td>${m.disciplina}</td><td class="c-dim">${m.professor}</td>
    <td><button class="btn danger sm" onclick="rmMateria(${m.id})">rm</button></td>
  </tr>`).join('')+'</tbody></table>';
}
async function rmMateria(id){
  await api('/api/remover-materia',{aluno_id:G.alunoId,materia_id:id});loadGer();
}
async function gerBuscar(){
  const termo=document.getElementById('ger-inp').value.trim();
  const el=document.getElementById('ger-pick');
  if(!termo){el.innerHTML='';return;}
  const d=await api('/api/buscar-disciplinas',{termo});
  if(!d.registros.length){el.innerHTML='<div class="msg warn">Sem resultados.</div>';return;}
  el.replaceChildren(mkPickList(d.registros,async row=>{
    const dia=document.getElementById('ger-dia').value;
    if(!dia){alert('Selecione o dia primeiro.');return;}
    await api('/api/adicionar-materia',{aluno_id:G.alunoId,dia,turma:row.Turma,disciplina:row.Disciplina,professor:row.Professor});
    el.innerHTML=`<div class="msg ok">Adicionada: ${row.Disciplina} (${dia})</div>`;
    document.getElementById('ger-inp').value='';loadGer();
  }));
}
function cancelCadastro(){
  G.cadUser=null;G.cadMats=[];
  document.getElementById('cad-un').value='';
  document.getElementById('cad-email').value='';
  document.getElementById('cad-un-msg').innerHTML='';
  document.getElementById('cad-p1').style.display='block';
  document.getElementById('cad-p2').style.display='none';
  document.getElementById('cad-dt-list').innerHTML='<li style="color:var(--text-dim);font-size:12px;padding:5px 0">nenhuma ainda.</li>';
  document.getElementById('cad-pick').innerHTML='';
  goto('s-main');
}
function irCadastro(un){goto('s-cadastro');document.getElementById('cad-un').value=un;cadCheckUser();}
async function cadCheckUser(){
  const un=document.getElementById("cad-un").value.trim().toLowerCase();
  const msg=document.getElementById('cad-un-msg');if(!un)return;
  msg.innerHTML='<div class="loading">verificando...</div>';
  const d=await api('/api/verificar-username',{username:un});
  if(!d.disponivel){msg.innerHTML=`<div class="msg error">username "${un}" ja existe.</div>`;return;}
  G.cadUser=un;G.cadMats=[];msg.innerHTML='';
  document.getElementById('cad-un-ok').textContent=`username "${un}" disponivel.`;
  document.getElementById('cad-p1').style.display='none';
  document.getElementById('cad-p2').style.display='block';
}
function renderDtList(){
  const ul=document.getElementById('cad-dt-list');
  if(!G.cadMats.length){ul.innerHTML='<li style="color:var(--text-dim);font-size:12px;padding:5px 0">nenhuma ainda.</li>';return;}
  ul.innerHTML=G.cadMats.map((m,i)=>`<li class="dt-item">
    <span class="dt-dia">${m.dia}</span><span class="dt-disc">${m.disciplina}</span>
    <button class="dt-rm" onclick="cadRm(${i})">&#10005;</button></li>`).join('');
}
function cadRm(i){G.cadMats.splice(i,1);renderDtList();}
async function cadBuscar(){
  const termo=document.getElementById('cad-inp').value.trim();
  const el=document.getElementById('cad-pick');
  if(!termo){el.innerHTML='';return;}
  const d=await api('/api/buscar-disciplinas',{termo});
  if(!d.registros.length){el.innerHTML='<div class="msg warn">Sem resultados.</div>';return;}
  el.replaceChildren(mkPickList(d.registros,row=>{
    const dia=document.getElementById('cad-dia').value;
    if(!dia){alert('Selecione o dia primeiro.');return;}
    const dup=G.cadMats.some(m=>m.dia===dia&&m.disciplina===row.Disciplina&&m.turma===row.Turma);
    if(dup){el.innerHTML='<div class="msg warn">Ja adicionada.</div>';return;}
    G.cadMats.push({dia,turma:row.Turma,disciplina:row.Disciplina,professor:row.Professor});
    renderDtList();
    el.innerHTML=`<div class="msg ok">Adicionada: ${row.Disciplina} (${dia})</div>`;
    document.getElementById('cad-inp').value='';
  }));
}
async function cadSalvar(){
  if(!G.cadUser)return;
  const email=document.getElementById('cad-email').value.trim();
  if(!email){document.getElementById('cad-pick').innerHTML='<div class="msg error">Email e obrigatorio.</div>';return;}
  const receber_email=document.getElementById('btn-cad-email-toggle')?.getAttribute('data-ativo')!=='0';
  const d=await api('/api/cadastrar',{username:G.cadUser,email,materias:G.cadMats,receber_email});
  if(d.erro){document.getElementById('cad-pick').innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  G.alunoId=d.aluno_id;G.username=d.username;
  document.getElementById('s-aluno-title').textContent=`ola, ${d.username}`;
  document.getElementById('badge-hoje').textContent=G.statusData?.dia||'';
  cancelCadastro();goto('s-aluno');
}

async function doRecuperar(){
  const email=document.getElementById('rec-email').value.trim();
  const msg=document.getElementById('rec-msg');
  if(!email){msg.innerHTML='<div class="msg error">Informe seu email.</div>';return;}
  msg.innerHTML='<div class="loading">enviando...</div>';
  const d=await api('/api/recuperar-username',{email});
  if(d.erro){msg.innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  msg.innerHTML='<div class="msg ok">Email enviado! Verifique sua caixa de entrada.</div>';
  document.getElementById('rec-email').value='';
}

// ── Admin ────────────────────────────────────────────────────────────────────
const ADM={user:null,pass:null};
function admCreds(){return{adm_user:ADM.user,adm_pass:ADM.pass};}
function admStep1(){
  const un=document.getElementById('adm-un').value.trim();
  if(!un){return;}
  ADM.user=un.toLowerCase();
  document.getElementById('adm-step1').style.display='none';
  document.getElementById('adm-step2').style.display='block';
  document.getElementById('adm-pw').focus();
}
async function admLogin(){
  const pw=document.getElementById('adm-pw').value;
  ADM.pass=pw.toLowerCase();
  const d=await api('/api/adm/login',{adm_user:ADM.user,adm_pass:ADM.pass});
  if(!d.ok){
    document.getElementById('adm-step2-msg').innerHTML='<div class="msg error">credenciais incorretas.</div>';
    ADM.pass=null;return;
  }
  admAtualizarBadge(d.travado);
  goto('s-adm-main');
}
function admLogout(){
  ADM.user=null;ADM.pass=null;
  document.getElementById('adm-un').value='';
  document.getElementById('adm-pw').value='';
  document.getElementById('adm-step1').style.display='block';
  document.getElementById('adm-step2').style.display='none';
  document.getElementById('adm-step1-msg').innerHTML='';
  document.getElementById('adm-step2-msg').innerHTML='';
  goto('s-main');
}
function admAtualizarBadge(travado){
  const b=document.getElementById('adm-lock-badge');
  if(travado){
    b.textContent='SITE TRAVADO';b.style.color='var(--red)';b.style.borderColor='var(--red)';
  } else {
    b.textContent='SITE ABERTO';b.style.color='var(--green)';b.style.borderColor='var(--green)';
  }
}
async function admToggleLock(){
  const d=await api('/api/adm/status-trava',admCreds());
  const novo=!d.travado;
  const conf=confirm(novo?'Trancar o site? Ninguem tera acesso.':'Destrancar o site?');
  if(!conf)return;
  await api('/api/adm/trava',{...admCreds(),travado:novo});
  admAtualizarBadge(novo);
}

// disciplinas
async function loadAdmDisc(){
  const el=document.getElementById('adm-disc-body');
  el.innerHTML='<div class="loading">carregando...</div>';
  const d=await api('/api/adm/disciplinas',admCreds());
  if(!d.registros.length){el.innerHTML='<div class="msg warn">Nenhuma disciplina.</div>';return;}
  let h='<table class="tbl"><thead><tr><th>Turma</th><th>Disciplina</th><th>Professor</th><th></th></tr></thead><tbody>';
  d.registros.forEach(r=>{
    h+=`<tr>
      <td><input class="tbl-inp" value="${r.turma}" id="dt-${r.id}-turma"/></td>
      <td><input class="tbl-inp" value="${r.disciplina}" id="dt-${r.id}-disc"/></td>
      <td><input class="tbl-inp" value="${r.professor}" id="dt-${r.id}-prof"/></td>
      <td style="white-space:nowrap">
        <button class="btn sm" onclick="discEditar(${r.id})">salvar</button>
        <button class="btn danger sm" onclick="discExcluir(${r.id})">rm</button>
      </td></tr>`;
  });
  el.innerHTML=h+'</tbody></table>';
}
async function discAdicionar(){
  const turma=document.getElementById('disc-turma').value.trim();
  const disc=document.getElementById('disc-nome').value.trim();
  const prof=document.getElementById('disc-prof').value.trim();
  const msg=document.getElementById('disc-add-msg');
  if(!turma||!disc){msg.innerHTML='<div class="msg error">Turma e disciplina obrigatorios.</div>';return;}
  await api('/api/adm/disciplinas/adicionar',{...admCreds(),turma,disciplina:disc,professor:prof});
  document.getElementById('disc-turma').value='';
  document.getElementById('disc-nome').value='';
  document.getElementById('disc-prof').value='';
  msg.innerHTML='<div class="msg ok">Adicionada.</div>';
  loadAdmDisc();
}
async function discEditar(id){
  const turma=document.getElementById(`dt-${id}-turma`).value;
  const disc=document.getElementById(`dt-${id}-disc`).value;
  const prof=document.getElementById(`dt-${id}-prof`).value;
  await api('/api/adm/disciplinas/editar',{...admCreds(),id,turma,disciplina:disc,professor:prof});
  loadAdmDisc();
}
async function discExcluir(id){
  if(!confirm('Excluir disciplina?'))return;
  await api('/api/adm/disciplinas/excluir',{...admCreds(),id});
  loadAdmDisc();
}

// alunos
async function loadAdmAlunos(){
  const el=document.getElementById('adm-alunos-body');
  // Inject search bar once
  if(!document.getElementById('adm-alunos-search')){
    el.insertAdjacentHTML('beforebegin',
      `<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
        <div class="igroup" style="flex:1;margin:0">
          <span class="iprefix">&#128269;</span>
          <input type="text" id="adm-alunos-search" placeholder="buscar por username ou email..."
            oninput="debounce(buscarAdmAlunos,350)()" autocomplete="off"/>
        </div>
        <button class="btn sm" onclick="buscarAdmAlunos()">buscar</button>
      </div>
      <div id="adm-alunos-total" style="font-size:11px;color:var(--text-muted);margin-bottom:6px"></div>`
    );
  }
  el.innerHTML='<div style="color:var(--text-dim);font-size:12px;padding:10px 0">digite para buscar alunos.</div>';
  document.getElementById('adm-alunos-total').textContent='';
}
async function buscarAdmAlunos(){
  const el=document.getElementById('adm-alunos-body');
  const termo=document.getElementById('adm-alunos-search')?.value.trim()||'';
  el.innerHTML='<div class="loading">buscando...</div>';
  const d=await api('/api/adm/alunos/buscar',{...admCreds(),termo,limite:50});
  const totalEl=document.getElementById('adm-alunos-total');
  if(!d.registros||!d.registros.length){
    el.innerHTML='<div class="msg warn">Nenhum aluno encontrado.</div>';
    if(totalEl)totalEl.textContent='';
    return;
  }
  if(totalEl)totalEl.textContent=`${d.registros.length} de ${d.total} resultado(s)`;
  let h='<table class="tbl"><thead><tr><th>Username</th><th>Email</th><th>Criado</th><th></th><th></th><th></th></tr></thead><tbody>';
  d.registros.forEach(r=>{
    const bloq=r.bloqueado;
    h+=`<tr style="${bloq?'opacity:0.6':''}">
      <td><input class="tbl-inp" value="${r.username}" id="al-${r.id}-un"/></td>
      <td><input class="tbl-inp" value="${r.email}" id="al-${r.id}-email"/></td>
      <td class="c-dim">${r.criado||''}</td>
      <td style="white-space:nowrap">
        <button class="btn sm" onclick="alunoEditar(${r.id})">salvar</button>
        <button class="btn danger sm" onclick="alunoExcluir(${r.id})">rm</button>
      </td>
      <td><button class="btn sm ${bloq?'danger':''}" onclick="alunoToggleBloqueio(${r.id},${bloq})" title="${bloq?'desbloquear':'bloquear'}">${bloq?'&#128274;':'&#128275;'}</button></td>
      <td><button class="btn sm" onclick="alunoEmailHoje(${r.id},'${r.email}','${r.username}')" title="enviar aulas de hoje">&#9993;</button></td>
    </tr>`;
  });
  el.innerHTML=h+'</tbody></table>';
}
async function alunoAdicionar(){
  const un=document.getElementById('al-un').value.trim();
  const email=document.getElementById('al-email').value.trim();
  const msg=document.getElementById('al-add-msg');
  if(!un||!email){msg.innerHTML='<div class="msg error">Username e email obrigatorios.</div>';return;}
  const d=await api('/api/adm/alunos/adicionar',{...admCreds(),username:un,email});
  if(d.erro){msg.innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  document.getElementById('al-un').value='';document.getElementById('al-email').value='';
  msg.innerHTML='<div class="msg ok">Aluno adicionado.</div>';buscarAdmAlunos();
}
async function alunoEditar(id){
  const un=document.getElementById(`al-${id}-un`).value;
  const email=document.getElementById(`al-${id}-email`).value;
  await api('/api/adm/alunos/editar',{...admCreds(),id,username:un,email});
  buscarAdmAlunos();
}
async function alunoToggleBloqueio(id, bloqueado){
  const acao=bloqueado?'desbloquear':'bloquear';
  if(!confirm(`Deseja ${acao} este aluno?`))return;
  await api('/api/adm/alunos/bloquear',{...admCreds(),id,bloqueado:!bloqueado});
  buscarAdmAlunos();
}
async function alunoEmailHoje(aluno_id, email, username){
  if(!email){alert('Este aluno nao tem email cadastrado.');return;}
  const d=await api('/api/adm/email/aluno',{...admCreds(),aluno_id});
  if(d.ok) alert('Email enviado para '+email);
  else alert('Erro: '+(d.erro||'falha ao enviar'));
}
async function alunoExcluir(id){
  if(!confirm('Excluir aluno e todas as suas materias?'))return;
  await api('/api/adm/alunos/excluir',{...admCreds(),id});
  buscarAdmAlunos();
}

// ── Admin email ───────────────────────────────────────────────────────────────
// Pick list com busca server-side
let admAlunosSel=new Map(); // email -> {email, username}
let _pickDebounce=null;

async function loadAdmAlunosPick(){
  admAlunosSel=new Map();
  document.getElementById('pick-search').value='';
  atualizarContador();
  document.getElementById('adm-alunos-pick').innerHTML=
    '<div style="color:var(--text-dim);font-size:12px;padding:8px">digite para buscar alunos.</div>';
}
async function filtrarPick(){
  clearTimeout(_pickDebounce);
  _pickDebounce=setTimeout(async()=>{
    const q=document.getElementById('pick-search').value.trim();
    if(q.length<1){
      document.getElementById('adm-alunos-pick').innerHTML=
        '<div style="color:var(--text-dim);font-size:12px;padding:8px">digite para buscar alunos.</div>';
      return;
    }
    const el=document.getElementById('adm-alunos-pick');
    el.innerHTML='<div class="loading" style="padding:6px">buscando...</div>';
    const d=await api('/api/adm/alunos/buscar',{...admCreds(),termo:q,limite:50});
    const lista=(d.registros||[]).filter(r=>r.email);
    if(!lista.length){el.innerHTML='<div class="msg warn" style="padding:8px">nenhum resultado.</div>';return;}
    el.innerHTML=lista.map(r=>`
      <label style="display:flex;align-items:center;gap:6px;font-size:12px;cursor:pointer;padding:5px 8px;border-bottom:1px solid var(--border);background:${admAlunosSel.has(r.email)?'var(--bg3)':'transparent'};transition:background .1s">
        <input type="checkbox" data-email="${r.email}" data-username="${encodeURIComponent(r.username)}" onchange="admToggleSel(this)" ${admAlunosSel.has(r.email)?'checked':''} style="accent-color:var(--blue)"/>
        <span style="color:var(--text);min-width:90px">${r.username}</span>
        <span style="color:var(--text-muted)">${r.email}</span>
      </label>`).join('');
    atualizarContador();
  },300);
}
function admToggleSel(cb){
  const email=cb.dataset.email;
  const username=decodeURIComponent(cb.dataset.username||'');
  if(cb.checked)admAlunosSel.set(email,{email,username});
  else admAlunosSel.delete(email);
  cb.closest('label').style.background=cb.checked?'var(--bg3)':'transparent';
  atualizarContador();
}
function selecionarVisiveis(){
  document.querySelectorAll('#adm-alunos-pick input[type=checkbox]').forEach(cb=>{
    const email=cb.dataset.email;
    const username=decodeURIComponent(cb.dataset.username||'');
    cb.checked=true;admAlunosSel.set(email,{email,username});
    cb.closest('label').style.background='var(--bg3)';
  });
  atualizarContador();
}
function limparSelecao(){
  admAlunosSel.clear();
  document.querySelectorAll('#adm-alunos-pick input[type=checkbox]').forEach(cb=>{
    cb.checked=false;cb.closest('label').style.background='transparent';
  });
  atualizarContador();
}
function atualizarContador(){
  const n=admAlunosSel.size;
  const el=document.getElementById('pick-counter');
  if(el)el.innerHTML=n?`<span style="color:var(--cyan)">${n} selecionado(s)</span> &mdash; <button class="btn sm danger" onclick="limparSelecao()" style="padding:1px 7px">limpar</button>`:'0 selecionado(s)';
}
async function emailTodos(){
  const msg=document.getElementById('email-todos-msg');
  msg.innerHTML='<div class="loading">enviando...</div>';
  await api('/api/adm/email/todos',admCreds());
  msg.innerHTML='<div class="msg ok">Emails enviados.</div>';
}
async function admRecapturar(){
  const msg=document.getElementById('recap-msg');
  msg.innerHTML='<div class="loading">buscando planilha...</div>';
  const d=await api('/api/adm/recapturar',admCreds());
  if(d.ok) msg.innerHTML=`<div class="msg ok">Planilha atualizada. ${d.total} registros.</div>`;
  else msg.innerHTML=`<div class="msg error">${d.erro}</div>`;
}
async function emailCustom(){
  const assunto=document.getElementById('email-assunto').value.trim();
  const mensagem=document.getElementById('email-msg').value.trim();
  const msg=document.getElementById('email-custom-msg');
  const destinatarios=[...admAlunosSel.values()];
  if(!assunto||!mensagem){msg.innerHTML='<div class="msg error">Assunto e mensagem obrigatorios.</div>';return;}
  if(!destinatarios.length){msg.innerHTML='<div class="msg error">Selecione ao menos um destinatario.</div>';return;}
  msg.innerHTML='<div class="loading">enviando...</div>';
  const d=await api('/api/adm/email/custom',{...admCreds(),assunto,mensagem,destinatarios});
  msg.innerHTML=`<div class="msg ok">Envio de ${d.total} iniciado em background.</div>`;
}

// ── Teste de email com busca ──────────────────────────────────────────────────
let _testeAlunos=[];
let _testeDebounce=null;
let _testeSel=null; // {id, username, email}

async function loadTesteAlunos(){
  _testeAlunos=[];_testeSel=null;
  const wrap=document.getElementById('teste-aluno-wrap');
  if(!wrap)return;
  wrap.innerHTML=`
    <div style="position:relative;flex:1;min-width:180px">
      <div class="igroup" style="margin:0">
        <span class="iprefix">@</span>
        <input type="text" id="teste-search" placeholder="buscar aluno..." autocomplete="off"
          oninput="debounce(buscaTeste,350)()" onfocus="buscaTeste()"
          style="flex:1"/>
      </div>
      <div id="teste-suggestions" style="display:none;position:absolute;top:100%;left:0;right:0;z-index:99;
        background:var(--bg2);border:1px solid var(--cyan);max-height:200px;overflow-y:auto"></div>
    </div>
    <div id="teste-sel-badge" style="font-size:11px;color:var(--text-dim);align-self:center"></div>`;
}
async function buscaTeste(){
  const inp=document.getElementById('teste-search');
  const sug=document.getElementById('teste-suggestions');
  if(!inp||!sug)return;
  const q=inp.value.trim();
  const d=await api('/api/adm/alunos/buscar',{...admCreds(),termo:q,limite:20});
  const lista=(d.registros||[]).filter(r=>r.email);
  if(!lista.length){sug.style.display='none';return;}
  sug.style.display='block';
  sug.innerHTML=lista.map(r=>`
    <div onclick="selecionarTestAluno(${r.id},'${r.username}','${r.email}')"
      style="padding:7px 12px;cursor:pointer;font-size:12px;border-bottom:1px solid var(--border);
      display:flex;gap:8px;align-items:center" onmouseover="this.style.background='var(--bg3)'" onmouseout="this.style.background=''">
      <span style="color:var(--text);min-width:80px">${r.username}</span>
      <span style="color:var(--text-muted)">${r.email}</span>
    </div>`).join('');
}
function selecionarTestAluno(id,username,email){
  _testeSel={id,username,email};
  const inp=document.getElementById('teste-search');
  const sug=document.getElementById('teste-suggestions');
  const badge=document.getElementById('teste-sel-badge');
  if(inp)inp.value=username;
  if(sug)sug.style.display='none';
  if(badge)badge.innerHTML=`&#10003; <span style="color:var(--cyan)">${username}</span> &lt;${email}&gt;`;
}
document.addEventListener('click',e=>{
  const sug=document.getElementById('teste-suggestions');
  if(sug&&!sug.contains(e.target)&&e.target.id!=='teste-search')sug.style.display='none';
});
async function emailTeste(){
  const msg=document.getElementById('email-teste-msg');
  if(!_testeSel){msg.innerHTML='<div class="msg error">Selecione um aluno.</div>';return;}
  msg.innerHTML='<div class="loading">enviando...</div>';
  const d=await api('/api/adm/email/teste',{...admCreds(),aluno_id:_testeSel.id});
  if(d.erro){msg.innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  msg.innerHTML=`<div class="msg ok">&#10003; Enviado para ${d.enviado_para}</div>`;
}

// Debounce helper
function debounce(fn,ms){
  let t;return function(...args){clearTimeout(t);t=setTimeout(()=>fn(...args),ms);}
}


// ── Configuracoes do aluno ───────────────────────────────────────────────────
function cadToggleEmail(){
  const btn=document.getElementById('btn-cad-email-toggle');
  const ativo=btn.getAttribute('data-ativo')==='1';
  btn.setAttribute('data-ativo', ativo?'0':'1');
  btn.textContent=ativo?'desativado':'ativado';
  btn.className='btn sm '+(ativo?'danger':'success');
}

async function loadEmailToggle(){
  if(!G.alunoId)return;
  const d=await api('/api/configuracoes',{aluno_id:G.alunoId});
  const btn=document.getElementById('btn-email-toggle');
  if(!btn)return;
  const ativo=d.receber_email;
  btn.setAttribute('data-ativo',ativo?'1':'0');
  btn.textContent=ativo?'ativado':'desativado';
  btn.className='btn sm '+(ativo?'success':'danger');
}

async function toggleEmail(){
  const btn=document.getElementById('btn-email-toggle');
  const ativo=btn.getAttribute('data-ativo')==='1';
  const novo=!ativo;
  await api('/api/configuracoes',{aluno_id:G.alunoId,receber_email:novo});
  btn.setAttribute('data-ativo',novo?'1':'0');
  btn.textContent=novo?'ativado':'desativado';
  btn.className='btn sm '+(novo?'success':'danger');
}

init();

document.getElementById("footer-year").textContent=new Date().getFullYear();
