const G={alunoId:null,username:null,statusData:null,cadUser:null,cadMats:[]};
function goto(id,_fromPop){
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  if(id==='s-hoje')loadHoje();
  if(id==='s-todas')loadTodas();
  if(id==='s-ger'){loadGer();loadEmailToggle();}
  if(id==='s-adm-disc')loadAdmDisc();
  if(id==='s-adm-alunos')loadAdmAlunos();
  if(id==='s-adm-email'){loadAdmAlunosPick();loadTesteAlunos();}
  if(!_fromPop)history.pushState({screen:id},'','');
}
async function api(url,body){
  const o={headers:{'Content-Type':'application/json'}};
  if(body){o.method='POST';o.body=JSON.stringify(body);}
  try{
    const r=await fetch(url,o);
    if(!r.ok)return{erro:`Erro HTTP ${r.status}`};
    return await r.json();
  }catch(e){
    console.error('api error',url,e);
    return{erro:'Falha de conexao com o servidor.'};
  }
}
const SLOT_LABELS={manha1:"1º Manhã",manha2:"2º Manhã",tarde1:"1º Tarde",tarde2:"2º Tarde",noite1:"1º Noite",noite2:"2º Noite"};
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
    const base=['Turma','Sala','Disciplina','Professor','Horario','Data','Dia'];
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
  return Object.entries(g).map(([cat,rs])=>{
    const label=LABEL_MAP[cat]||cat;
    const body=cat.startsWith('OUTRAS RESERVAS')?mkOutrasReservas(rs):mkTable(rs);
    return `<div class="cat-block"><div class="cat-label">${label}</div>${body}</div>`;
  }).join('');
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
  const d=await api('/api/status');G.statusData=d;
  if(d.travado){document.body.classList.add('travado');}else{document.body.classList.remove('travado');}
  const _aviso=document.getElementById('main-trava-aviso');
  if(_aviso)_aviso.style.display=d.travado?'block':'none';
  // Desabilita cliques nos itens do menu principal quando travado
  document.querySelectorAll('#s-main .menu-item:not(.adm-item)').forEach(el=>{
    if(d.travado){el._onclick=el.onclick;el.onclick=null;el.style.pointerEvents='none';el.style.cursor='not-allowed';}
    else{if(el._onclick)el.onclick=el._onclick;el.style.pointerEvents='';el.style.cursor='';}
  });
  document.querySelectorAll('#s-main .btn:not(.adm-btn)').forEach(el=>{
    el.disabled=!!d.travado;
  });
  const meses=['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
  const [,mes,dia2]=(d.hoje||'2000-01-01').split('-');
  const dataFmt=`${parseInt(dia2)} de ${meses[parseInt(mes)-1]}`;
  const _min=d.ultima_captura_min;
  const _capStr=_min>=0?(_min===0?'agora mesmo':_min<60?(_min===1?'ha 1 min':`ha ${_min} min`):(_min<120?'ha 1 h':`ha ${Math.round(_min/60)} h`)):'--';
  const _discStr=d.total>0?` · ${d.total} disc.`:'';
  document.getElementById('hdr-meta').innerHTML=
    `<span class="hl">${d.dia}</span> · <span class="hl">${dataFmt}</span>`
    +` · <span>capturado ${_capStr}${_discStr}</span>`
    +` · <span>${d.total_alunos} alunos</span>`;
  const ul=document.getElementById('cat-menu');
  let idx=1;
  d.categorias.forEach(([cat,n])=>{
    if(n===0)return;
    const li=document.createElement('li');li.className='menu-item';
    const label=LABEL_MAP[cat]||cat;
    li.innerHTML=`<span class="menu-key">${idx++}</span><span class="menu-label">${label}</span><span class="menu-badge">${n} registros</span>`;
    li.onclick=()=>loadCat(cat);ul.appendChild(li);
  });
}
const LABEL_MAP={'OUTRAS RESERVAS - NOITE':'OUTRAS RESERVAS'};
async function loadCat(nome){
  goto('s-cat');
  const label=LABEL_MAP[nome]||nome;
  document.getElementById('s-cat-title').textContent=label.toLowerCase();
  document.getElementById('s-cat-body').innerHTML='<div class="loading">carregando...</div>';
  const d=await api(`/api/categoria/${encodeURIComponent(nome)}`);
  if(d.erro){document.getElementById('s-cat-body').innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  const sorted=d.registros.slice().sort((a,b)=>(a.Horario||'').localeCompare(b.Horario||''));
  const isOutras=nome.startsWith('OUTRAS RESERVAS');
  document.getElementById('s-cat-body').innerHTML=isOutras?mkOutrasReservas(sorted):mkTable(sorted);
}

function mkOutrasReservas(rows){
  if(!rows.length)return'<div class="msg warn">Nenhum resultado.</div>';
  let h='<table class="tbl"><thead><tr>'
    +'<th>Horario</th><th>Descricao</th><th>Responsavel</th><th>Sala</th><th>Data</th>'
    +'</tr></thead><tbody>';
  rows.forEach(r=>{
    const sala=r.Sala||r.Salas||'';
    const data=r.Data||r.DATA||'';
    const desc=r.Descricao||'';
    const resp=r.Responsavel||'';
    const hora=r.Horario||'';
    h+=`<tr>
      <td class="c-hora">${hora}</td>
      <td>${desc}</td>
      <td class="c-dim">${resp}</td>
      <td class="c-sala">${sala}</td>
      <td class="c-hora">${data}</td>
    </tr>`;
  });
  return h+'</tbody></table>';
}
async function doBusca(){
  const termo=document.getElementById('busca-inp').value.trim();
  if(!termo){document.getElementById('busca-out').innerHTML='<div class="msg warn">Digite um nome, disciplina, turma ou horario para buscar.</div>';return;}
  const out=document.getElementById('busca-out');
  out.innerHTML='<div class="loading">buscando...</div>';
  const d=await api('/api/buscar',{termo});
  if(d.erro){out.innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  out.innerHTML=`<div class="msg info" style="margin-bottom:14px">"${termo}" &mdash; ${d.total} resultado(s)</div>`+mkGroups(d.registros);
}

let _modoLivre=false;
function toggleModoLivre(){
  _modoLivre=!_modoLivre;
  document.getElementById('busca-mode-normal').style.display=_modoLivre?'none':'block';
  document.getElementById('busca-mode-livre').style.display=_modoLivre?'block':'none';
  document.getElementById('sw-track-livre').classList.toggle('on',_modoLivre);
  document.getElementById('busca-out').innerHTML='';
  document.getElementById('salas-livre-horario').textContent='';
  if(_modoLivre){
    document.getElementById('sala-livre-inp').value='';
    doSalasLivres();
  }
}

async function doSalasLivres(){
  if(!_modoLivre)return;
  const filtro=document.getElementById('sala-livre-inp').value.trim();
  const out=document.getElementById('busca-out');
  const horEl=document.getElementById('salas-livre-horario');
  out.innerHTML='<div class="loading">consultando...</div>';
  const url='/api/salas-livres-slots'+(filtro?`?sala=${encodeURIComponent(filtro)}`:'');
  const d=await api(url);
  if(d.erro){out.innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  const agora=new Date();
  const hm=agora.getHours().toString().padStart(2,'0')+':'+agora.getMinutes().toString().padStart(2,'0');
  horEl.textContent=`consulta em ${hm}`;
  const SLOT_HORA={manha1:'07:30',manha2:'09:50',tarde1:'13:00',tarde2:'14:00',noite1:'18:00',noite2:'19:00'};
  const agora_min=agora.getHours()*60+agora.getMinutes();
  const SLOT_INI={manha1:6*60,manha2:9*60+30,tarde1:13*60,tarde2:14*60,noite1:18*60,noite2:19*60};
  const SLOT_FIM={manha1:9*60+29,manha2:12*60+59,tarde1:13*60+59,tarde2:17*60+59,noite1:18*60+59,noite2:23*60+59};
  let html='';
  const ordem=['manha1','manha2','tarde1','tarde2','noite1','noite2'];
  for(const slot of ordem){
    const s=d[slot];
    if(!s)continue;
    const ativo=agora_min>=SLOT_INI[slot]&&agora_min<=SLOT_FIM[slot];
    const badge=ativo?`<span class="badge-agora" style="margin-left:8px;font-size:10px;padding:2px 7px;background:var(--cyan);color:var(--bg);font-weight:bold">AGORA</span>`:'';
    const chips=s.salas.length
      ?s.salas.map(r=>`<span style="padding:5px 12px;border:1px solid var(--cyan);color:var(--cyan);font-size:12px;font-weight:bold">${r}</span>`).join('')
      :`<span style="color:var(--text-dim);font-size:12px">Nenhuma sala livre${filtro?` com "${filtro}"`:''}.</span>`;
    html+=`<details style="margin-bottom:8px" ${ativo?'open':''}>
      <summary style="cursor:pointer;list-style:none;padding:10px 14px;background:var(--bg2);border:1px solid var(--border);display:flex;align-items:center;gap:6px;user-select:none">
        <span class="slot-arrow" style="color:var(--cyan);font-size:11px">&#9654;</span>
        <span style="font-weight:bold;font-size:13px;color:var(--text)">${s.label}</span>
        <span style="font-size:11px;color:var(--text-dim)">${SLOT_HORA[slot]}</span>
        ${badge}
        <span style="margin-left:auto;font-size:11px;color:var(--text-dim)">${s.total} livre(s)</span>
      </summary>
      <div style="padding:10px 14px;border:1px solid var(--border);border-top:none;display:flex;flex-wrap:wrap;gap:8px;background:var(--bg)">
        ${chips}
      </div>
    </details>`;
  }
  out.innerHTML=(filtro?`<div class="msg info" style="margin-bottom:10px">filtro: "${filtro}"</div>`:'') + html;
}
async function doLogin(){
  const un=document.getElementById("login-inp").value.trim().toLowerCase();
  const msg=document.getElementById('login-msg');
  if(!un){msg.innerHTML='<div class="msg error">Informe seu username para entrar.</div>';return;}
  msg.innerHTML='<div class="loading">verificando...</div>';
  const d=await api('/api/login',{username:un});
  if(d.bloqueado){
    msg.innerHTML='<div class="msg error">acesso bloqueado. entre em contato com o administrador.</div>';
    return;
  }
  if(!d.encontrado){
    msg.innerHTML=`<div class="msg error">Username "${un}" nao encontrado. Verifique a digitacao.</div>
      <div style="margin-top:8px;font-size:12px;color:var(--text-muted)">
        <button class="btn sm" onclick="irCadastro('${un}')">criar cadastro com este nome</button></div>`;
    return;
  }
  msg.innerHTML='';G.alunoId=d.aluno_id;G.username=d.username;
  document.getElementById('s-aluno-title').textContent=`ola, ${d.username}`;
  document.getElementById('badge-hoje').textContent=G.statusData?.dia||'';
  goto('s-hoje');
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
  if(!d.aulas.length){el.innerHTML=`<div class="msg warn">Nenhuma aula encontrada para ${d.dia}. Verifique se suas materias estao cadastradas e com turno definido em Configuracoes.</div>`;return;}

  const agora=new Date();
  const agora_min=agora.getHours()*60+agora.getMinutes();
  const SLOT_INI={manha1:6*60,manha2:9*60+30,tarde1:13*60,tarde2:14*60,noite1:18*60,noite2:19*60};
  const SLOT_FIM={manha1:9*60+29,manha2:12*60+59,tarde1:13*60+59,tarde2:17*60+59,noite1:18*60+59,noite2:23*60+59};
  const SLOT_HORA={manha1:'07:30',manha2:'09:50',tarde1:'13:00',tarde2:'14:00',noite1:'18:00',noite2:'19:00'};
  const SLOT_ORDER={manha1:0,manha2:1,tarde1:2,tarde2:3,noite1:4,noite2:5};

  function classify(slot){
    const ini=SLOT_INI[slot],fim=SLOT_FIM[slot];
    if(ini==null)return 'futuro';
    if(agora_min>=ini&&agora_min<=fim)return 'agora';
    if(agora_min>fim)return 'concluida';
    return 'futuro';
  }

  // Classificar e ordenar: agora primeiro, futuro por horario, concluida no final
  const aulas=d.aulas.map(a=>({...a,_status:classify(a.slot),_order:SLOT_ORDER[a.slot]??99}));
  const PRIO={agora:0,futuro:1,concluida:2};
  aulas.sort((a,b)=>PRIO[a._status]-PRIO[b._status]||a._order-b._order);

  function getSala(rows){
    if(!rows.length)return null;
    const r=rows[0];
    return r.Salas||r.Sala||null;
  }
  function getHorario(rows){
    if(!rows.length)return null;
    return rows[0].Horario||null;
  }

  el.innerHTML=aulas.map(a=>{
    const st=a._status;
    const sala=getSala(a.salas);
    const horario=getHorario(a.salas)||SLOT_HORA[a.slot]||'';
    const turnoLabel=SLOT_LABELS[a.slot]||'';

    const badge=st==='agora'
      ?`<span class="badge-agora" style="font-size:10px;padding:3px 8px;background:var(--cyan);color:var(--bg);font-weight:bold;letter-spacing:.5px">AGORA</span>`
      :st==='concluida'
      ?`<span style="font-size:10px;padding:3px 8px;border:1px solid var(--text-dim);color:var(--text-dim);letter-spacing:.5px">CONCLU\u00cdDA</span>`
      :'';

    const salaEl=sala
      ?`<span class="c-sala" style="font-size:18px;font-weight:900;letter-spacing:1px">${sala}</span>`
      :`<span style="color:var(--text-dim);font-size:13px">sala nao encontrada</span>`;

    const extraRows=a.salas.length>1
      ?`<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px">`
        +a.salas.slice(1).map(r=>{
          const s=r.Salas||r.Sala||'';
          const h=r.Horario||'';
          return s?`<span style="padding:3px 10px;border:1px solid var(--border);color:var(--text-dim);font-size:11px">${s}${h?' · '+h:''}</span>`:'';
        }).join('')+'</div>'
      :'';

    const cardStyle=st==='agora'
      ?'border-color:var(--cyan)'
      :st==='concluida'
      ?'opacity:0.55'
      :'';

    return `<div class="aula-card" style="${cardStyle}">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">
        ${badge}
        <span style="color:var(--text-dim);font-size:11px;letter-spacing:.5px">${turnoLabel} &mdash; ${horario}</span>
      </div>
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:6px;flex-wrap:wrap">
        <div style="min-width:90px">${salaEl}</div>
        <div>
          <div class="aula-card-title" style="margin-bottom:2px">${a.disciplina}</div>
          <div class="aula-card-meta">${a.turma} &nbsp;&middot;&nbsp; ${a.professor}</div>
        </div>
      </div>
      ${extraRows}
    </div>`;
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
    <table class="tbl"><thead><tr><th>Turma</th><th>Disciplina</th><th>Professor</th><th>Turno</th></tr></thead><tbody>
    ${mats.map(m=>`<tr><td class="c-turma">${m.turma}</td><td>${m.disciplina}</td><td class="c-dim">${m.professor}</td><td class="c-hora">${SLOT_LABELS[m.slot]||'—'}</td></tr>`).join('')}
    </tbody></table></div>`).join('');
}
async function loadGer(){
  const el=document.getElementById('s-ger-lista');
  el.innerHTML='<div class="loading">carregando...</div>';
  const d=await api('/api/minhas-materias',{aluno_id:G.alunoId});
  if(d.erro){el.innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  if(!d.materias.length){el.innerHTML='<div class="msg warn" style="margin-bottom:0">Nenhuma materia cadastrada. Adicione suas disciplinas abaixo.</div>';return;}
  const semSlot=d.materias.filter(m=>!m.slot);
  const aviso=semSlot.length
    ?`<div class="msg warn" style="margin-bottom:12px">&#9888; ${semSlot.length} disciplina(s) sem turno definido. Selecione o turno de horario de cada uma para receber notificacoes por email.</div>`
    :'';
  const slotOpts=`<option value="">-- turno --</option><option value="manha1">1º Manhã (07:30)</option><option value="manha2">2º Manhã (09:50+)</option><option value="tarde1">1º Tarde (13:00)</option><option value="tarde2">2º Tarde (14:00+)</option><option value="noite1">1º Noite (18:00)</option><option value="noite2">2º Noite (19:00+)</option>`;
  el.innerHTML=aviso+`<table class="tbl"><thead><tr><th>Dia</th><th>Turma</th><th>Disciplina</th><th>Professor</th><th>Turno</th><th></th></tr></thead><tbody>`+
  d.materias.map(m=>`<tr>
    <td class="c-hora">${m.dia}</td><td class="c-turma">${m.turma}</td>
    <td>${m.disciplina}</td><td class="c-dim">${m.professor}</td>
    <td>${m.slot
      ?`<span class="c-hora">${SLOT_LABELS[m.slot]}</span>`
      :`<select class="slot-sel" onchange="setSlot(${m.id},this.value)">${slotOpts}</select>`
    }</td>
    <td><button class="btn danger sm" onclick="rmMateria(${m.id})">rm</button></td>
  </tr>`).join('')+'</tbody></table>';
}
async function setSlot(materia_id,slot){
  if(!slot)return;
  const d=await api('/api/atualizar-slot',{aluno_id:G.alunoId,materia_id,slot});
  if(d.erro){
    document.getElementById('ger-pick').innerHTML=`<div class="msg error">Erro ao salvar turno: ${d.erro}</div>`;
    return;
  }
  loadGer();
  document.getElementById('ger-pick').innerHTML='<div class="msg ok">Turno atualizado com sucesso.</div>';
  setTimeout(()=>{const el=document.getElementById('ger-pick');if(el)el.innerHTML='';},3000);
}
async function rmMateria(id){
  if(!confirm('Remover esta materia?'))return;
  const d=await api('/api/remover-materia',{aluno_id:G.alunoId,materia_id:id});
  if(d.erro){document.getElementById('ger-pick').innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  loadGer();
}
async function gerBuscar(){
  const termo=document.getElementById('ger-inp').value.trim();
  const el=document.getElementById('ger-pick');
  if(!termo){el.innerHTML='';return;}
  const d=await api('/api/buscar-disciplinas',{termo});
  if(!d.registros.length){el.innerHTML='<div class="msg warn">Nenhuma disciplina encontrada. Tente outro termo de busca.</div>';return;}
  el.replaceChildren(mkPickList(d.registros,async row=>{
    const dia=document.getElementById('ger-dia').value;
    if(!dia){el.innerHTML='<div class="msg error">Selecione o dia antes de adicionar.</div>';return;}
    const gerSlot=document.getElementById('ger-slot').value;
    if(!gerSlot){el.innerHTML='<div class="msg error">Selecione o turno de horario antes de adicionar.</div>';return;}
    const d=await api('/api/adicionar-materia',{aluno_id:G.alunoId,dia,turma:row.Turma,disciplina:row.Disciplina,professor:row.Professor,slot:gerSlot});
    if(d.erro){el.innerHTML=`<div class="msg error">Erro ao adicionar: ${d.erro}</div>`;return;}
    el.innerHTML=`<div class="msg ok">&#10003; ${row.Disciplina} adicionada para ${dia} — ${SLOT_LABELS[gerSlot]}.</div>`;
    document.getElementById('ger-inp').value='';
    document.getElementById('ger-slot').value='';
    loadGer();
  }));
}
function cancelCadastro(){
  G.cadUser=null;G.cadMats=[];G._cadDia='';G._cadSlot='';
  document.getElementById('cad-un').value='';
  document.getElementById('cad-email').value='';
  document.getElementById('cad-un-msg').innerHTML='';
  document.getElementById('cad-p2-msg').innerHTML='';
  document.getElementById('cad-pick').innerHTML='';
  document.getElementById('cad-p1').style.display='block';
  document.getElementById('cad-p2').style.display='none';
  document.getElementById('cad-p3').style.display='none';
  document.getElementById('btn-cad-email-toggle').setAttribute('data-ativo','1');
  document.getElementById('sw-cad-email').classList.add('on');
  cadStepUI(1);
  renderDiscTags();
  goto('s-main');
}
function irCadastro(un){goto('s-cadastro');document.getElementById('cad-un').value=un;cadCheckUser();}
async function cadCheckUser(){
  const un=document.getElementById("cad-un").value.trim().toLowerCase();
  const msg=document.getElementById('cad-un-msg');if(!un)return;
  msg.innerHTML='<div class="loading">verificando...</div>';
  const d=await api('/api/verificar-username',{username:un});
  if(!d.disponivel){msg.innerHTML=`<div class="msg error">username "@${un}" ja esta em uso. Tente outro.</div>`;return;}
  G.cadUser=un;G.cadMats=[];G._cadDia='';G._cadSlot='';msg.innerHTML='';
  document.getElementById('cad-un-ok').textContent=`@${un} disponivel.`;
  document.getElementById('cad-p1').style.display='none';
  document.getElementById('cad-p2').style.display='block';
  cadStepUI(2);
  document.getElementById('cad-email').focus();
}
function renderDiscTags(){
  const el=document.getElementById('cad-disc-tags');
  const cnt=document.getElementById('cad-disc-count');
  if(cnt)cnt.textContent=G.cadMats.length;
  if(!G.cadMats.length){
    el.innerHTML='<p style="color:var(--text-dim);font-size:12px;padding:6px 0">nenhuma ainda &mdash; use a busca abaixo para adicionar.</p>';
    return;
  }
  el.innerHTML=G.cadMats.map((m,i)=>`
    <div class="disc-tag">
      <span class="disc-tag-dia">${m.dia}</span>
      <span class="disc-tag-disc">${m.disciplina}<br><span style="color:var(--text-dim);font-size:11px">${m.turma} &mdash; ${m.professor||''}</span></span>
      <span class="disc-tag-slot">${SLOT_LABELS[m.slot]||''}</span>
      <button class="disc-tag-rm" onclick="cadRm(${i})" title="remover">&#10005;</button>
    </div>`).join('');
}
function renderDtList(){renderDiscTags();}
function cadRm(i){G.cadMats.splice(i,1);renderDiscTags();}
async function cadBuscar(){
  const termo=document.getElementById('cad-inp').value.trim();
  const el=document.getElementById('cad-pick');
  if(!G._cadDia){el.innerHTML='<div class="msg warn">Selecione o dia da semana primeiro.</div>';return;}
  if(!G._cadSlot){el.innerHTML='<div class="msg warn">Selecione o turno primeiro.</div>';return;}
  if(!termo){el.innerHTML='';return;}
  el.innerHTML='<div class="loading">buscando...</div>';
  const d=await api('/api/buscar-disciplinas',{termo});
  if(!d.registros.length){el.innerHTML='<div class="msg warn">Nenhuma disciplina encontrada. Tente outro termo.</div>';return;}
  el.replaceChildren(mkPickList(d.registros,row=>{
    const dup=G.cadMats.some(m=>m.dia===G._cadDia&&m.disciplina===row.Disciplina&&m.turma===row.Turma);
    if(dup){el.innerHTML='<div class="msg warn">Ja adicionada.</div>';return;}
    G.cadMats.push({dia:G._cadDia,turma:row.Turma,disciplina:row.Disciplina,professor:row.Professor,slot:G._cadSlot});
    renderDiscTags();
    el.innerHTML=`<div class="msg ok">&#10003; Adicionada: ${row.Disciplina} (${G._cadDia})</div>`;
    document.getElementById('cad-inp').value='';
  }));
}
async function cadSalvar(){
  if(!G.cadUser)return;
  const email=document.getElementById('cad-email').value.trim();
  const msgEl=document.getElementById('cad-pick');
  if(!G.cadMats.length){msgEl.innerHTML='<div class="msg error">Adicione ao menos uma disciplina antes de finalizar.</div>';return;}
  const receber_email=document.getElementById('btn-cad-email-toggle')?.getAttribute('data-ativo')!=='0';
  msgEl.innerHTML='<div class="loading">salvando...</div>';
  const d=await api('/api/cadastrar',{username:G.cadUser,email,materias:G.cadMats,receber_email});
  if(d.erro){msgEl.innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  G.alunoId=d.aluno_id;G.username=d.username;
  document.getElementById('s-aluno-title').textContent=`ola, ${d.username}`;
  document.getElementById('badge-hoje').textContent=G.statusData?.dia||'';
  cancelCadastro();goto('s-aluno');init();
}

async function doRecuperar(){
  const email=document.getElementById('rec-email').value.trim();
  const msg=document.getElementById('rec-msg');
  if(!email){msg.innerHTML='<div class="msg error">Informe seu email.</div>';return;}
  msg.innerHTML='<div class="loading">enviando...</div>';
  const d=await api('/api/recuperar-username',{email});
  if(d.erro){msg.innerHTML=`<div class="msg error">${d.erro}</div>`;return;}
  msg.innerHTML='<div class="msg ok">&#10003; Email enviado! Verifique sua caixa de entrada (e a pasta de spam).</div>';
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
  ADM.pass=pw;
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
  const sw=document.getElementById('sw-adm-lock');
  const lbl=document.getElementById('adm-lock-label');
  const txt=document.getElementById('adm-status-txt');
  // switch: ON = aberto (verde), OFF = fechado (vermelho)
  if(sw){sw.classList.toggle('on',!travado);}
  if(lbl){lbl.textContent=travado?'fechado':'aberto';lbl.style.color=travado?'var(--red)':'var(--green)';}
  if(txt){txt.textContent=travado?'site fechado':'site aberto';txt.style.color=travado?'var(--red)':'var(--green)';}
  // atualizar aviso no menu principal
  const aviso=document.getElementById('main-trava-aviso');
  if(aviso)aviso.style.display=travado?'block':'none';
}
async function admToggleLock(){
  const d=await api('/api/adm/status-trava',admCreds());
  const novo=!d.travado;
  await api('/api/adm/trava',{...admCreds(),travado:novo});
  admAtualizarBadge(novo);
  init(); // sincroniza estado do menu principal
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
  buscarAdmAlunos();
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
      <td><button class="btn sm" data-aid="${r.id}" data-email="${r.email.replace('"','&quot;')}" data-uname="${r.username.replace('"','&quot;')}" onclick="alunoEmailHoje(this)" title="enviar aulas de hoje">&#9993;</button></td>
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
  buscarAdmAlunos();init();
}
async function alunoEmailHoje(btn){
  const aluno_id=btn.dataset.aid,email=btn.dataset.email,username=btn.dataset.uname;
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
  if(el)el.innerHTML=n?`<span style="color:var(--cyan)">${n} selecionado(s)</span> &mdash; <button class="btn sm danger" onclick="limparSelecao()" style="padding:1px 7px">limpar tudo</button>`:'0 selecionado(s)';
  const chips=document.getElementById('pick-chips');
  if(!chips)return;
  if(!n){chips.style.display='none';chips.innerHTML='';return;}
  chips.style.display='flex';
  chips.innerHTML=[...admAlunosSel.values()].map(u=>`<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;background:var(--bg3);border:1px solid var(--cyan);font-size:11px;color:var(--cyan)">@${u.username}<button onclick="removerChip('${u.email}')" style="background:none;border:none;color:var(--red);cursor:pointer;font-size:12px;padding:0 2px;line-height:1">&#10005;</button></span>`).join('');
}
function removerChip(email){
  admAlunosSel.delete(email);
  const cb=document.querySelector(`#adm-alunos-pick input[data-email="${email}"]`);
  if(cb){cb.checked=false;cb.closest('label').style.background='transparent';}
  atualizarContador();
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
let _testeSel=null;

async function loadTesteAlunos(){
  _testeSel=null;
  const area=document.getElementById('teste-search-area');
  if(!area)return;
  area.innerHTML=`
    <div style="position:relative">
      <div class="igroup" style="margin:0">
        <span class="iprefix">@</span>
        <input type="text" id="teste-search" placeholder="buscar aluno por username ou email..."
          autocomplete="off" oninput="debouncedBuscaTeste()" style="flex:1"/>
      </div>
      <div id="teste-suggestions" style="display:none;position:absolute;top:100%;left:0;right:0;z-index:99;
        background:var(--bg2);border:1px solid var(--cyan);max-height:200px;overflow-y:auto"></div>
    </div>`;
  const sendRow=document.getElementById('teste-send-row');
  if(sendRow)sendRow.style.display='none';
}
const debouncedBuscaTeste=debounce(buscaTeste,350);
async function buscaTeste(){
  const inp=document.getElementById('teste-search');
  const sug=document.getElementById('teste-suggestions');
  if(!inp||!sug)return;
  const q=inp.value.trim();
  if(!q){sug.style.display='none';return;}
  const d=await api('/api/adm/alunos/buscar',{...admCreds(),termo:q,limite:20});
  const lista=(d.registros||[]).filter(r=>r.email);
  if(!lista.length){sug.style.display='none';return;}
  sug.style.display='block';
  sug.innerHTML=lista.map(r=>`
    <div data-id="${r.id}" data-username="${encodeURIComponent(r.username)}" data-email="${encodeURIComponent(r.email)}" onclick="selecionarTestAluno(this)"
      style="padding:8px 12px;cursor:pointer;font-size:12px;border-bottom:1px solid var(--border);
      display:flex;gap:10px;align-items:center" onmouseover="this.style.background='var(--bg3)'" onmouseout="this.style.background=''">
      <span style="color:var(--text);min-width:90px;font-weight:bold">@${r.username}</span>
      <span style="color:var(--text-muted)">${r.email}</span>
    </div>`).join('');
}
function selecionarTestAluno(el){
  const id=el.dataset.id,username=decodeURIComponent(el.dataset.username||''),email=decodeURIComponent(el.dataset.email||'');
  _testeSel={id,username,email};
  const inp=document.getElementById('teste-search');
  const sug=document.getElementById('teste-suggestions');
  if(inp)inp.value='';
  if(sug)sug.style.display='none';
  const sendRow=document.getElementById('teste-send-row');
  const info=document.getElementById('teste-sel-info');
  if(info)info.innerHTML=`&#10003; <strong>@${username}</strong> &lt;${email}&gt;`;
  if(sendRow)sendRow.style.display='flex';
  document.getElementById('email-teste-msg').innerHTML='';
}
document.addEventListener('click',e=>{
  const sug=document.getElementById('teste-suggestions');
  if(sug&&!sug.contains(e.target)&&e.target.id!=='teste-search')sug.style.display='none';
});
async function emailTeste(){
  const msg=document.getElementById('email-teste-msg');
  if(!_testeSel){msg.innerHTML='<div class="msg error">Selecione um aluno primeiro.</div>';return;}
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
  const sw=document.getElementById('sw-cad-email');
  if(sw)sw.classList.toggle('on');
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

// ── Swipe-back nativo (History API) ──────────────────────────────────────────
window.addEventListener('popstate',function(e){
  const btn=document.querySelector('.screen.active .btn-back');
  if(btn)btn.click();
  else if(e.state&&e.state.screen)goto(e.state.screen,true);
});
// ── Feedback tatil em botoes (Android/Chrome) ─────────────────────────────
(function(){
  if(!navigator.vibrate)return;
  document.addEventListener('touchstart',function(e){
    const t=e.target.closest('button,.btn,.menu-item,label.sw,.btn-back,summary');
    if(t)navigator.vibrate(8);
  },{passive:true});
})();

function cadStepUI(step){
  ['cad-step1-dot','cad-step2-dot','cad-step3-dot'].forEach((id,i)=>{
    const el=document.getElementById(id);
    if(!el)return;
    el.className='step-dot'+(i+1<step?' done':i+1===step?' active':'');
  });
  ['cad-line1','cad-line2'].forEach((id,i)=>{
    const el=document.getElementById(id);
    if(!el)return;
    el.className='step-line'+(i+1<step?' done':'');
  });
}
function cadChipDia(el){
  document.querySelectorAll('#cad-chips-dia .chip').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
  G._cadDia=el.getAttribute('data-val');
  document.getElementById('cad-pick').innerHTML='';
}
function cadChipSlot(el){
  document.querySelectorAll('#cad-chips-slot .chip').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
  G._cadSlot=el.getAttribute('data-val');
  document.getElementById('cad-pick').innerHTML='';
}
async function cadGoP3(){
  const email=document.getElementById('cad-email').value.trim();
  const msgEl=document.getElementById('cad-p2-msg');
  if(!email){msgEl.innerHTML='<div class="msg error">Informe seu email para continuar.</div>';return;}
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){msgEl.innerHTML='<div class="msg error">Email invalido. Use o formato: nome@dominio.com</div>';return;}
  msgEl.innerHTML='';
  document.getElementById('cad-p2').style.display='none';
  document.getElementById('cad-p3').style.display='block';
  cadStepUI(3);
}
