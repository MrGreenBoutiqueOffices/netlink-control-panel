/* Browser-only simulation. No API, serial, MQTT or firmware access. */
const MIN_HEIGHT_MM = 620, MAX_HEIGHT_MM = 1270;
const clampHeight = value => Math.max(MIN_HEIGHT_MM, Math.min(MAX_HEIGHT_MM, value));
const panel = document.querySelector('#panel');
const feedback = document.querySelector('#feedback');
const scenario = document.querySelector('#scenario');
const heightInput = document.querySelector('#demo-height');
const pauseButton = document.querySelector('#motion-pause');
const defaultState = () => ({ screen: 'desk', connected: true, height: 740, sit: 740, stand: 1120, target: 780, monitor: 70, monitorOn: true, input: 0, brightness: 100, dim: 1, contrast: false, rotated: false, profile: false, notice: false, firmware: '0.8.0', updateVersion: '0.9.0', hasUpdate: true, updatePhase: 'available', updateProgress: 0, saved: null, motionName: '', paused: false, manual: false });
let state = defaultState();
let motionFrame = 0;
let previousTime = 0;
const names = {desk:'Bureau', confirm:'Hoogte kiezen', moving:'Bewegen', menu:'Meer', monitor:'Monitor', presets:'Voorkeuren', panel:'Paneel', software:'Software', boot:'Opstarten', connecting:'Verbinden', installing:'Installeren', updated:'Bijgewerkt', updateFailed:'Update mislukt', obstructed:'Gestopt', calibrate:'Afstellen', sleep:'Ruststand', welcome:'Welkom'};
const fmt = mm => (Math.round(mm) / 10).toFixed(1).replace('.', ',');
const presetFmt = mm => Number.isInteger(mm / 10) ? String(mm / 10) : fmt(mm);
const icon = (name, cls = '') => `<img class="${cls}" src="assets/${name}.png" alt="" draggable="false">`;
const disabled = condition => condition ? 'disabled' : '';
const back = (label = 'Menu', destination = 'menu') => `<button class="back" data-action="nav" data-to="${destination}" aria-label="Terug naar ${label}">${icon('back')}<span>${label}</span></button>`;
function say(text) { feedback.textContent = text; }
function stopTimer() { stopTargetEdit(); cancelAnimationFrame(motionFrame); motionFrame = 0; previousTime = 0; }
function syncTools() {
  heightInput.value = state.height / 10;
  heightInput.disabled = state.screen === 'moving';
  document.querySelector('#demo-height-value').textContent = `${fmt(state.height)} cm`;
  document.querySelector('#connection').textContent = state.connected ? 'Verbinding verbreken' : 'Opnieuw verbinden';
  document.querySelector('#connection').setAttribute('aria-pressed', String(!state.connected));
  document.querySelector('#connection-status').textContent = state.connected ? 'Demo verbonden' : 'Demo niet verbonden';
  document.querySelector('#screen-name').textContent = names[state.screen];
  if (!scenario.matches(':focus')) scenario.value = !state.connected && state.screen === 'desk' ? 'offline' : state.screen;
  pauseButton.hidden = !(state.screen === 'moving' && state.paused);
}
function side(direction, selected = false) {
  const up = direction === 'up';
  return `<button class="side ${up ? 'right' : ''} ${selected ? 'selected' : ''}" data-action="adjust-height" data-direction="${up ? 1 : -1}" aria-label="${up ? 'Hoger' : 'Lager'}" ${disabled(!state.connected)}>${icon(up ? (selected ? 'up-active' : 'up') : 'down', 'arrow')}<span class="label">${up ? 'HOGER' : 'LAGER'}</span></button>`;
}
function desk(confirming = false) {
  const offline = !state.connected;
  const chosen = confirming && state.manual ? Math.sign(state.target - state.height) : 0;
  const title = offline ? 'LAATST BEKEND' : confirming ? 'HUIDIG' : Math.abs(state.height - state.sit) < 1 ? 'ZITHOOGTE' : Math.abs(state.height - state.stand) < 1 ? 'STAHOOGTE' : 'BUREAUHOOGTE';
  return `${side('down', chosen < 0)}${side('up', chosen > 0)}${state.profile && !confirming ? '<img class=profile-name src=assets/profile-name.png alt=Klaas>' : ''}<div class="desk-title label">${title}</div><div class="height-value"><span>${fmt(state.height)}</span><small class="unit">cm</small></div>${offline ? '<div class="offline-message"><span class="status-dot"></span>Geen verbinding</div>' : confirming ? `<div class="target"><div class="label">NAAR</div><div class="target-value">${fmt(state.target)}<small>cm</small></div></div>` : `<div class="height-gauge" style="--position:${58 - (state.height - MIN_HEIGHT_MM) / (MAX_HEIGHT_MM - MIN_HEIGHT_MM) * 53}px" aria-hidden="true"></div>`}${confirming ? `<button class="cancel" data-action="cancel">Annuleren</button><button class="confirm" data-action="confirm">Bevestigen${icon('check')}</button>` : `<button class="preset ${Math.abs(state.height - state.sit) < 1 ? 'is-current' : ''}" data-action="preset" data-preset="sit" ${disabled(offline)}><span class="label">ZITTEN</span><span class="preset-height">${presetFmt(state.sit)}</span></button><button class="preset stand ${Math.abs(state.height - state.stand) < 1 ? 'is-current' : ''}" data-action="preset" data-preset="stand" ${disabled(offline)}><span class="label">STAAN</span><span class="preset-height">${presetFmt(state.stand)}</span></button><button class="more" data-action="nav" data-to="menu">${icon('more')}${state.notice ? '<i class=update-dot></i>' : ''}<span>Meer</span></button>`}`;
}
function moving() {
  return `<button class="moving-stop" data-action="stop" aria-label="Stop beweging"><span class="moving-caption">${state.motionName} · ${presetFmt(state.target)} CM</span><span class="moving-value"><span id="motion-height">${fmt(state.height)}</span><small>cm</small></span><span class="stop-copy"><strong>Stop</strong><span>Tik ergens op het scherm</span></span></button>`;
}
function menu() {
  const tiles = [['monitor','monitor','Monitor',`${state.monitorOn ? 'Aan' : 'Uit'} · ${state.monitor}%`],['presets','bookmark','Voorkeuren',`${presetFmt(state.sit)} · ${presetFmt(state.stand)} cm`],['panel','settings','Paneel',state.dim ? `Dimmen na ${state.dim} min` : 'Dimmen uit'],['software','software','Software',state.hasUpdate ? `Update ${state.updateVersion} beschikbaar` : `Versie ${state.firmware}`]];
  return back('Bureau','desk') + tiles.map(([to, art, label, detail]) => `<button class="menu-tile" data-action="nav" data-to="${to}">${icon(art)}<span class="tile-title">${label}</span><span class="tile-detail">${detail}</span></button>`).join('');
}
function settings(isPanel) {
  const value = isPanel ? state.brightness : state.monitor;
  const unavailable = !isPanel && !state.connected;
  const activePlus = !isPanel && value < 100;
  return `${isPanel ? back() : back('Bureau','desk')}<div class="settings-title label">${isPanel ? 'HELDERHEID PANEEL' : 'HELDERHEID'}</div><div class="settings-value"><span id="setting-number">${value}</span><small>%</small></div><button class="adjust minus" data-action="brightness" data-delta="-5" aria-label="Helderheid verlagen" ${disabled(unavailable || value <= (isPanel ? 10 : 0))}>${icon('minus')}</button><input class="settings-slider" aria-label="${isPanel ? 'Paneelhelderheid' : 'Monitorhelderheid'}" type="range" min="${isPanel ? 10 : 0}" max="100" step="1" value="${value}" style="--fill:${isPanel ? (value - 10) / .9 : value}%" ${disabled(unavailable)}><button class="adjust plus ${activePlus ? 'selected' : ''}" data-action="brightness" data-delta="5" aria-label="Helderheid verhogen" ${disabled(unavailable || value >= 100)}>${icon(activePlus ? 'plus-active' : 'plus')}</button>${isPanel ? `<button class="option-tile" data-action="dim"><span class="label">DIMMEN</span><span class="option-value">${state.dim ? `Na ${state.dim} min` : 'Uit'}</span></button><button class="option-tile bottom" data-action="rotate"><span class="label">DRAAIEN</span><span class="option-value">${state.rotated ? 'Gedraaid' : 'Normaal'}</span></button>` : `<button class="option-tile" data-action="monitor-power" aria-label="Monitor ${state.monitorOn ? 'uitzetten' : 'aanzetten'}" ${disabled(unavailable)}><span class="label">MONITOR</span><span class="option-value"><span class="status-dot"></span>${state.monitorOn ? 'Aan' : 'Uit'}</span></button><button class="option-tile bottom" data-action="input" aria-label="Monitoringang wijzigen" ${disabled(unavailable)}><span class="label">INGANG</span><span class="option-value">${['HDMI 1','HDMI 2','DisplayPort'][state.input]}</span></button>`}`;
}
function presets() {
  return `${back()}<div class="current-height-label label">HUIDIGE HOOGTE</div><div class="current-height-value">${fmt(state.height)}<small>cm</small></div>${state.profile ? '<span class=profile-save>Opslaan bewaart voor Klaas</span>' : ''}${[['sit','ZITTEN'],['stand','STAAN']].map(([key,name], index) => `<button class="save-preset ${index ? 'bottom' : ''} ${state.saved === key ? 'saved' : ''}" data-action="save" data-preset="${key}" aria-label="Huidige hoogte opslaan als ${name.toLowerCase()}" ${disabled(!state.connected)}><span class="label">${name} · NU ${presetFmt(state[key])} CM</span><span class="save-value">${state.saved === key ? 'Opgeslagen' : `${fmt(state.height)} opslaan`}</span></button>`).join('')}`;
}
const frame = page => `<img class="design-frame" src="../docs/design/reference-${String(page).padStart(2,'0')}.png" alt="" draggable="false">`;
const hit = (action,label,x,y,w,h,extra='') => `<button class="hit" style="left:${x}px;top:${y}px;width:${w}px;height:${h}px" data-action="${action}" aria-label="${label}" ${extra}></button>`;
let updateTimer=0, calibrationTimer=0;
function clearUpdateTimer() { clearTimeout(updateTimer);clearInterval(updateTimer);updateTimer=0; }
function software() {
  const phase=state.updatePhase;
  const page=phase==='checking'?13:phase==='downloading'?14:phase==='current'?15:phase==='error'?16:12;
  let markup=frame(page)+back('Menu','menu');
  const top=phase==='downloading'?57:phase==='error'?62:72;
  markup+=`<div class="software-version" style="top:${top}px">Versie ${state.firmware}</div>`;
  if(phase==='available')markup+=`<div class="software-copy">Versie ${state.updateVersion} beschikbaar</div>`;
  if(phase==='downloading')markup+=`<div class="software-copy download-copy">Versie ${state.updateVersion} downloaden...</div><div class="software-progress"><span style="width:${state.updateProgress}%"></span></div><span class="software-percent">${state.updateProgress}%</span>`;
  if(phase==='available')markup+=hit('update-install','Installeren',432,8,200,78)+hit('update-check','Controleren',432,94,200,78);
  else if(phase==='downloading')markup+=hit('update-cancel','Annuleren',432,8,200,164);
  else if(phase==='checking')markup=markup.replace(/<button class="back".*?<\/button>/,'');
  else markup+=hit('update-check',phase==='error'?'Opnieuw':'Controleren',432,8,200,164);
  return markup;
}
function statusScreen() {
  const pages={boot:17,connecting:18,installing:19,updated:20,updateFailed:21,obstructed:22,calibrate:23,sleep:24,welcome:25};
  let markup=frame(pages[state.screen]);
  if(state.screen==='installing')markup+=`<div class="install-track"><span style="width:${state.updateProgress}%"></span></div><span class="install-percent">${state.updateProgress}%</span>`;
  else if(state.screen==='updateFailed')markup+=hit('update-retry','Opnieuw',464,8,168,78)+hit('status-dismiss','Later',464,94,168,78);
  else if(state.screen==='welcome')markup+=hit('welcome-height','Naar zithoogte',464,8,168,78)+hit('welcome-later','Niet nu',464,94,168,78);
  else if(state.screen==='calibrate')markup+=hit('calibrate-hold','Vasthouden om af te stellen',464,8,168,164);
  else if(state.screen==='obstructed')markup+=hit('status-dismiss','OK',464,8,168,164);
  else if(state.screen==='boot' || state.screen==='connecting' || state.screen==='sleep')markup+=hit('status-dismiss','Verder',0,0,640,180);
  return markup;
}
function checkUpdate() {
  clearUpdateTimer();state.screen='software';state.updatePhase='checking';render();say('Demo: GitHub-release controleren.');
  updateTimer=setTimeout(()=>{state.updatePhase=state.hasUpdate?'available':'current';state.notice=state.hasUpdate;render();},1200);
}
function installUpdate() {
  clearUpdateTimer();state.updatePhase='downloading';state.updateProgress=0;render();
  const advance=()=>{
    state.updateProgress=Math.min(100,state.updateProgress+4);render();
    if(state.updateProgress<100){updateTimer=setTimeout(advance,120);return;}
    state.screen='installing';state.updateProgress=100;render();
    updateTimer=setTimeout(()=>{state.screen='updated';render();updateTimer=setTimeout(()=>{state.firmware=state.updateVersion;state.hasUpdate=false;state.notice=false;state.updatePhase='current';state.screen='software';render();say('Demo-update voltooid, zonder netwerk- of firmwareactie.');},1000);},1400);
  };
  updateTimer=setTimeout(advance,120);
}
function render() {
  panel.className = `panel ${state.connected ? '' : 'offline'} ${state.rotated ? 'rotated' : ''}`;
  const views = {desk: () => desk(), confirm: () => desk(true), moving, menu, monitor: () => settings(false), panel: () => settings(true), presets, software, boot:statusScreen, connecting:statusScreen, installing:statusScreen, updated:statusScreen, updateFailed:statusScreen, obstructed:statusScreen, calibrate:statusScreen, sleep:statusScreen, welcome:statusScreen};
  panel.innerHTML = `<div class="panel-content">${views[state.screen]()}</div>`;
  syncTools();
}
function moveTo(target, name) {
  target = clampHeight(target);
  if (!state.connected) return;
  if (Math.abs(state.height - target) < 1) { say('Het bureau staat al op deze hoogte.'); return; }
  stopTimer(); state.target = target; state.motionName = name; state.screen = 'moving'; state.paused = false; state.manual = false;
  render(); say('Gesimuleerde beweging. Tik op het paneel of druk op Esc om te stoppen.');
  motionFrame = requestAnimationFrame(tick);
}
function tick(time) {
  if (state.screen !== 'moving' || state.paused || !state.connected) return;
  const elapsed = previousTime ? Math.min((time - previousTime) / 1000, .1) : 0;
  previousTime = time;
  const delta = state.target - state.height;
  const travel = Math.min(Math.abs(delta), elapsed * 35);
  state.height += Math.sign(delta) * travel;
  const height = document.querySelector('#motion-height'); if (height) height.textContent = fmt(state.height);
  syncTools();
  if (Math.abs(state.height - state.target) < .1) { state.height = state.target; stopTimer(); state.screen = 'desk'; render(); say(`Doelhoogte bereikt: ${fmt(state.height)} cm.`); return; }
  motionFrame = requestAnimationFrame(tick);
}
function stopMovement(message = 'Beweging gestopt') {
  state.manual = false; stopTimer(); state.height = Math.round(state.height); state.screen = 'desk'; state.paused = false; render(); say(`${message} op ${fmt(state.height)} cm.`);
}
function setConnected(value) {
  stopTimer(); state.connected = value; state.screen = 'desk'; state.paused = false; state.saved = null;
  render(); say(value ? 'Demo opnieuw verbonden. Eerdere bewegingen worden niet hervat.' : 'Verbinding verbroken. Beweging gestopt; de laatst bekende hoogte blijft zichtbaar.');
}

let manualBounds = null, targetDelay = 0, targetRepeat = 0;
function stopTargetEdit() {
  clearTimeout(targetDelay); clearInterval(targetRepeat); targetDelay = 0; targetRepeat = 0; state.manual = false; manualBounds = null;
}
function targetStep(direction) {
  state.target = clampHeight(state.target + direction * 10);
  state.screen = 'confirm'; state.motionName = 'NAAR DOELHOOGTE'; render();
}
function startTargetEdit(direction) {
  if (!state.connected) return;
  stopTargetEdit(); if (state.screen !== 'confirm') state.target = state.height;
  state.manual = true; targetStep(direction);
  targetDelay = setTimeout(() => { targetRepeat = setInterval(() => targetStep(direction), 180); }, 350);
  say('Alleen de doelhoogte wordt aangepast. Bevestig om de gesimuleerde beweging te starten.');
}
panel.addEventListener('pointerdown', event => {
  const calibrate=event.target.closest('[data-action="calibrate-hold"]');
  if(calibrate){event.preventDefault();clearInterval(calibrationTimer);panel.setPointerCapture(event.pointerId);calibrationTimer=setInterval(()=>{state.height=clampHeight(state.height-3);say(`Afstellen: ${fmt(state.height)} cm`);if(state.height===MIN_HEIGHT_MM){clearInterval(calibrationTimer);state.screen='desk';render();}},100);return;}

  const arrow = event.target.closest('[data-action="adjust-height"]'); if (!arrow || arrow.disabled) return;
  event.preventDefault(); const bounds = arrow.getBoundingClientRect(); panel.setPointerCapture(event.pointerId);
  startTargetEdit(Number(arrow.dataset.direction)); manualBounds = bounds;
});
panel.addEventListener('pointermove', event => {
  if (!state.manual || !manualBounds) return;
  if (event.clientX < manualBounds.left || event.clientX > manualBounds.right || event.clientY < manualBounds.top || event.clientY > manualBounds.bottom) {stopTargetEdit();render();}
});
panel.addEventListener('pointerup', event => { const editing=state.manual;clearInterval(calibrationTimer);stopTargetEdit();if(editing)render(); if (panel.hasPointerCapture(event.pointerId)) panel.releasePointerCapture(event.pointerId); });
panel.addEventListener('pointercancel', ()=>{clearInterval(calibrationTimer);stopTargetEdit();render();});
panel.addEventListener('keydown', event => {
  if (!event.target.matches('[data-action="adjust-height"]') || ![' ', 'Enter'].includes(event.key)) return;
  event.preventDefault(); if (!event.repeat) startTargetEdit(Number(event.target.dataset.direction));
});
document.addEventListener('keyup', event => { if (state.manual && [' ', 'Enter'].includes(event.key)) {stopTargetEdit();render();} });
window.addEventListener('blur', ()=>{clearInterval(calibrationTimer);stopTargetEdit();render();});

panel.addEventListener('click', event => {
  const button = event.target.closest('button'); if (!button || button.disabled) return;
  const action = button.dataset.action;
  if(action==='update-check' || action==='update-retry'){checkUpdate();return;}
  if(action==='update-install'){installUpdate();return;}
  if(action==='update-cancel'){clearUpdateTimer();state.updatePhase='available';state.updateProgress=0;render();say('Demo-download geannuleerd. De huidige versie blijft behouden.');return;}
  if(action==='welcome-height'){state.target=state.sit;state.motionName='NAAR ZITHOOGTE';state.screen='confirm';render();return;}
  if(action==='welcome-later' || action==='status-dismiss'){state.screen=state.screen==='boot'?'connecting':'desk';render();return;}
  if(action==='calibrate-hold')return;
  if (action === 'nav') { state.screen = button.dataset.to; state.saved = null; render(); }
  else if (action === 'adjust-height') return;
  else if (action === 'cancel') { stopTargetEdit(); state.screen = 'desk'; render(); say('Hoogtekeuze geannuleerd.'); }
  else if (action === 'confirm') { const target = state.target, name = state.motionName || 'NAAR DOELHOOGTE'; stopTargetEdit(); moveTo(target, name); }
  else if (action === 'preset') { const key = button.dataset.preset; state[key] = clampHeight(state[key]); state.target = state[key]; state.motionName = key === 'sit' ? 'NAAR ZITHOOGTE' : 'NAAR STAHOOGTE'; state.screen = 'confirm'; render(); say('Bevestig de gekozen doelhoogte om de demo te laten bewegen.'); }
  else if (action === 'stop') stopMovement();
  else if (action === 'brightness') { const key = state.screen === 'panel' ? 'brightness' : 'monitor'; state[key] = Math.max(key === 'brightness' ? 10 : 0, Math.min(100, state[key] + Number(button.dataset.delta))); render(); say(`Demohelderheid: ${state[key]}%.`); }
  else if (action === 'monitor-power') { state.monitorOn = !state.monitorOn; render(); say(`Monitor staat in de demo ${state.monitorOn ? 'aan' : 'uit'}.`); }
  else if (action === 'input') { state.input = (state.input + 1) % 3; render(); say('Demo-ingang gewijzigd.'); }
  else if (action === 'dim') { const values = [1, 2, 5, 0]; state.dim = values[(values.indexOf(state.dim) + 1) % values.length]; render(); say(state.dim ? `Dimmen ingesteld op ${state.dim} minuten.` : 'Automatisch dimmen uitgeschakeld.'); }
  else if (action === 'rotate') { state.rotated = !state.rotated; render(); say(state.rotated ? 'Paneel 180 graden gedraaid.' : 'Normale weergave.'); }
  else if (action === 'save') { const key = button.dataset.preset; state[key] = clampHeight(Math.round(state.height)); state.saved = key; render(); say(`${key === 'sit' ? 'Zithoogte' : 'Stahoogte'} opgeslagen op ${fmt(state.height)} cm, alleen in deze demo.`); }
});
panel.addEventListener('input', event => {
  if (!event.target.matches('.settings-slider')) return;
  const key = state.screen === 'panel' ? 'brightness' : 'monitor'; state[key] = Number(event.target.value);
  document.querySelector('#setting-number').textContent = state[key];
  event.target.style.setProperty('--fill', `${key === 'brightness' ? (state[key] - 10) / .9 : state[key]}%`);
  panel.querySelector('.adjust.minus').disabled = state[key] <= (key === 'brightness' ? 10 : 0);
  panel.querySelector('.adjust.plus').disabled = state[key] >= 100;
});
panel.addEventListener('change', event => { if (event.target.matches('.settings-slider')) say(`Demohelderheid: ${event.target.value}%.`); });
const designScenarios=[['desk','1 · Bureau'],['profile','2 · Persoonlijke hoogtes'],['confirm','3 · Hoogte kiezen'],['moving','4 · Bewegen & stoppen'],['offline','5 · Geen verbinding'],['menu','6 · Meer'],['monitor','7 · Monitor'],['presets','8 · Voorkeuren'],['panel','9 · Paneel'],['rotated','10 · Gedraaid'],['notice','11 · Update-indicator'],['software','12 · Software beschikbaar'],['checking','13 · Updates zoeken'],['downloading','14 · Downloaden'],['current','15 · Actueel'],['checkFailed','16 · Controle mislukt'],['boot','17 · Opstarten'],['connecting','18 · Verbinden'],['installing','19 · Installeren'],['updated','20 · Bijgewerkt'],['updateFailed','21 · Update mislukt'],['obstructed','22 · Obstakel'],['calibrate','23 · Afstellen'],['sleep','24 · Ruststand'],['welcome','25 · Welkom']];
scenario.innerHTML=designScenarios.map(([value,label])=>`<option value="${value}">${label}</option>`).join('');
scenario.addEventListener('change', () => {
  stopTimer();clearUpdateTimer();clearInterval(calibrationTimer);const chosen=scenario.value;state=defaultState();state.screen=chosen;state.connected=chosen!=='offline';
  if(['offline','profile','notice'].includes(chosen))state.screen='desk';
  if(chosen==='profile' || chosen==='welcome' || chosen==='presets'){state.profile=true;state.sit=720;state.stand=1140;}
  if(chosen==='profile')state.height=720;
  if(chosen==='notice')state.notice=true;
  if(['checking','downloading','current','checkFailed'].includes(chosen)){state.screen='software';state.updatePhase=chosen==='checkFailed'?'error':chosen;state.updateProgress=64;if(chosen==='current'){state.firmware='0.9.0';state.hasUpdate=false;}}
  if(chosen==='rotated'){state.screen='panel';state.rotated=true;}
  if(chosen==='moving'){state.height=942;state.target=1120;state.motionName='NAAR STAHOOGTE';state.paused=true;}
  if(chosen==='presets')state.height=1086;
  if(chosen==='installing')state.updateProgress=64;
  render();scenario.value=chosen;say('Voorbeeldscherm geladen. Alle bediening en updates zijn gesimuleerd.');
});
heightInput.addEventListener('input', () => { if (state.screen === 'moving') return; state.height = clampHeight(Math.round(Number(heightInput.value) * 10)); state.saved = null; render(); });
document.querySelector('#connection').addEventListener('click', () => setConnected(!state.connected));
document.querySelector('#reset').addEventListener('click', () => { stopTimer();clearUpdateTimer();clearInterval(calibrationTimer); state = defaultState(); render(); say('Demo hersteld naar de beginwaarden.'); });
pauseButton.addEventListener('click', () => { state.paused = false; syncTools(); previousTime = 0; motionFrame = requestAnimationFrame(tick); });
document.addEventListener('keydown', event => { if (event.key !== 'Escape') return; if (state.screen === 'moving') stopMovement(); else if (state.screen === 'confirm') { state.screen = 'desk'; render(); say('Hoogtekeuze geannuleerd.'); } });
document.addEventListener('visibilitychange', () => { if (document.hidden && state.screen === 'moving' && !state.paused) stopMovement('Simulatie onderbroken'); });
function resize() { const padding = window.innerWidth <= 640 ? 16 : 24; const available = document.querySelector('main').clientWidth - (window.innerWidth <= 640 ? 36 : 64) - padding; const scale = Math.min(Number(document.querySelector('#zoom').value), available / 640); document.documentElement.style.setProperty('--scale', Math.max(.2, scale)); }
document.querySelector('#zoom').addEventListener('change', resize); window.addEventListener('resize', resize);
render(); resize();
