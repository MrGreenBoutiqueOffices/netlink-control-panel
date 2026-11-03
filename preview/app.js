/* Browser-only simulation. No API, serial, MQTT or firmware access. */
const MIN_HEIGHT_MM = 620, MAX_HEIGHT_MM = 1270;
const clampHeight = value => Math.max(MIN_HEIGHT_MM, Math.min(MAX_HEIGHT_MM, value));
const panel = document.querySelector('#panel');
const feedback = document.querySelector('#feedback');
const scenario = document.querySelector('#scenario');
const heightInput = document.querySelector('#demo-height');
const pauseButton = document.querySelector('#motion-pause');
const defaultState = () => ({ screen: 'desk', connected: true, height: 740, sit: 740, stand: 1120, target: 780, monitor: 70, monitorOn: true, input: 0, brightness: 100, dim: 1, contrast: false, saved: null, motionName: '', paused: false, manual: false });
let state = defaultState();
let motionFrame = 0;
let previousTime = 0;
const names = {desk:'Bureau', confirm:'Hoogte kiezen', moving:'Bewegen', menu:'Meer', monitor:'Monitor', presets:'Voorkeuren', panel:'Paneel'};
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
  scenario.value = !state.connected && state.screen === 'desk' ? 'offline' : state.screen;
  pauseButton.hidden = !(state.screen === 'moving' && state.paused);
}
function side(direction, selected = false) {
  const up = direction === 'up';
  return `<button class="side ${up ? 'right' : ''} ${selected ? 'selected' : ''}" data-action="adjust-height" data-direction="${up ? 1 : -1}" aria-label="${up ? 'Hoger' : 'Lager'}" ${disabled(!state.connected)}>${icon(up ? (selected ? 'up-active' : 'up') : 'down', 'arrow')}<span class="label">${up ? 'HOGER' : 'LAGER'}</span></button>`;
}
function desk(confirming = false) {
  const offline = !state.connected;
  const chosen = confirming ? Math.sign(state.target - state.height) : 0;
  const title = offline ? 'LAATST BEKEND' : confirming ? 'HUIDIG' : Math.abs(state.height - state.sit) < 1 ? 'ZITHOOGTE' : Math.abs(state.height - state.stand) < 1 ? 'STAHOOGTE' : 'BUREAUHOOGTE';
  return `${side('down', chosen < 0)}${side('up', chosen > 0)}<div class="desk-title label">${title}</div><div class="height-value"><span>${fmt(state.height)}</span><small class="unit">cm</small></div>${offline ? '<div class="offline-message"><span class="status-dot"></span>Geen verbinding</div>' : confirming ? `<div class="target"><div class="label">NAAR</div><div class="target-value">${fmt(state.target)}<small>cm</small></div></div>` : `<div class="height-gauge" style="--position:${58 - (state.height - MIN_HEIGHT_MM) / (MAX_HEIGHT_MM - MIN_HEIGHT_MM) * 53}px" aria-hidden="true"></div>`}${confirming ? `<button class="cancel" data-action="cancel">Annuleren</button><button class="confirm" data-action="confirm">Bevestigen${icon('check')}</button>` : `<button class="preset ${Math.abs(state.height - state.sit) < 1 ? 'is-current' : ''}" data-action="preset" data-preset="sit" ${disabled(offline)}><span class="label">ZITTEN</span><span class="preset-height">${presetFmt(state.sit)}</span></button><button class="preset stand ${Math.abs(state.height - state.stand) < 1 ? 'is-current' : ''}" data-action="preset" data-preset="stand" ${disabled(offline)}><span class="label">STAAN</span><span class="preset-height">${presetFmt(state.stand)}</span></button><button class="more" data-action="nav" data-to="menu">${icon('more')}<span>Meer</span></button>`}`;
}
function moving() {
  return `<button class="moving-stop" data-action="stop" aria-label="Stop beweging"><span class="moving-caption">${state.motionName} · ${presetFmt(state.target)} CM</span><span class="moving-value"><span id="motion-height">${fmt(state.height)}</span><small>cm</small></span><span class="stop-copy"><strong>Stop</strong><span>Tik ergens op het scherm</span></span></button>`;
}
function menu() {
  const tiles = [['monitor','monitor','Monitor',`${state.monitorOn ? 'Aan' : 'Uit'} · ${state.monitor}%`],['presets','bookmark','Voorkeuren',`${presetFmt(state.sit)} · ${presetFmt(state.stand)} cm`],['panel','settings','Paneel',state.dim ? `Dimmen na ${state.dim} min` : 'Dimmen uit']];
  return back('Bureau','desk') + tiles.map(([to, art, label, detail]) => `<button class="menu-tile" data-action="nav" data-to="${to}">${icon(art)}<span class="tile-title">${label}</span><span class="tile-detail">${detail}</span></button>`).join('');
}
function settings(isPanel) {
  const value = isPanel ? state.brightness : state.monitor;
  const unavailable = !isPanel && !state.connected;
  const activePlus = !isPanel && value < 100;
  return `${isPanel ? back() : back('Bureau','desk')}<div class="settings-title label">${isPanel ? 'HELDERHEID PANEEL' : 'HELDERHEID'}</div><div class="settings-value"><span id="setting-number">${value}</span><small>%</small></div><button class="adjust minus" data-action="brightness" data-delta="-5" aria-label="Helderheid verlagen" ${disabled(unavailable || value <= (isPanel ? 10 : 0))}>${icon('minus')}</button><input class="settings-slider" aria-label="${isPanel ? 'Paneelhelderheid' : 'Monitorhelderheid'}" type="range" min="${isPanel ? 10 : 0}" max="100" step="1" value="${value}" style="--fill:${isPanel ? (value - 10) / .9 : value}%" ${disabled(unavailable)}><button class="adjust plus ${activePlus ? 'selected' : ''}" data-action="brightness" data-delta="5" aria-label="Helderheid verhogen" ${disabled(unavailable || value >= 100)}>${icon(activePlus ? 'plus-active' : 'plus')}</button>${isPanel ? `<button class="option-tile" data-action="dim"><span class="label">DIMMEN</span><span class="option-value">${state.dim ? `Na ${state.dim} min` : 'Uit'}</span></button><button class="option-tile bottom" data-action="contrast"><span class="label">WEERGAVE</span><span class="option-value">${state.contrast ? 'Hoog contrast' : 'Normaal'}</span></button>` : `<button class="option-tile" data-action="monitor-power" aria-label="Monitor ${state.monitorOn ? 'uitzetten' : 'aanzetten'}" ${disabled(unavailable)}><span class="label">MONITOR</span><span class="option-value"><span class="status-dot"></span>${state.monitorOn ? 'Aan' : 'Uit'}</span></button><button class="option-tile bottom" data-action="input" aria-label="Monitoringang wijzigen" ${disabled(unavailable)}><span class="label">INGANG</span><span class="option-value">${['HDMI 1','HDMI 2','DisplayPort'][state.input]}</span></button>`}`;
}
function presets() {
  return `${back()}<div class="current-height-label label">HUIDIGE HOOGTE</div><div class="current-height-value">${fmt(state.height)}<small>cm</small></div>${[['sit','ZITTEN'],['stand','STAAN']].map(([key,name], index) => `<button class="save-preset ${index ? 'bottom' : ''} ${state.saved === key ? 'saved' : ''}" data-action="save" data-preset="${key}" aria-label="Huidige hoogte opslaan als ${name.toLowerCase()}" ${disabled(!state.connected)}><span class="label">${name} · NU ${presetFmt(state[key])} CM</span><span class="save-value">${state.saved === key ? 'Opgeslagen' : `${fmt(state.height)} opslaan`}</span></button>`).join('')}`;
}
function render() {
  panel.className = `panel ${state.connected ? '' : 'offline'} ${state.contrast ? 'high-contrast' : ''}`;
  const views = {desk: () => desk(), confirm: () => desk(true), moving, menu, monitor: () => settings(false), panel: () => settings(true), presets};
  panel.innerHTML = views[state.screen]();
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
  const arrow = event.target.closest('[data-action="adjust-height"]'); if (!arrow || arrow.disabled) return;
  event.preventDefault(); const bounds = arrow.getBoundingClientRect(); panel.setPointerCapture(event.pointerId);
  startTargetEdit(Number(arrow.dataset.direction)); manualBounds = bounds;
});
panel.addEventListener('pointermove', event => {
  if (!state.manual || !manualBounds) return;
  if (event.clientX < manualBounds.left || event.clientX > manualBounds.right || event.clientY < manualBounds.top || event.clientY > manualBounds.bottom) stopTargetEdit();
});
panel.addEventListener('pointerup', event => { stopTargetEdit(); if (panel.hasPointerCapture(event.pointerId)) panel.releasePointerCapture(event.pointerId); });
panel.addEventListener('pointercancel', stopTargetEdit);
panel.addEventListener('keydown', event => {
  if (!event.target.matches('[data-action="adjust-height"]') || ![' ', 'Enter'].includes(event.key)) return;
  event.preventDefault(); if (!event.repeat) startTargetEdit(Number(event.target.dataset.direction));
});
document.addEventListener('keyup', event => { if (state.manual && [' ', 'Enter'].includes(event.key)) stopTargetEdit(); });
window.addEventListener('blur', stopTargetEdit);

panel.addEventListener('click', event => {
  const button = event.target.closest('button'); if (!button || button.disabled) return;
  const action = button.dataset.action;
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
  else if (action === 'contrast') { state.contrast = !state.contrast; render(); say(state.contrast ? 'Hoog contrast ingeschakeld.' : 'Normale weergave ingeschakeld.'); }
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
scenario.addEventListener('change', () => {
  stopTimer(); const chosen = scenario.value; state = defaultState(); state.screen = chosen === 'offline' ? 'desk' : chosen; state.connected = chosen !== 'offline';
  if (chosen === 'moving') { state.height = 942; state.target = 1120; state.motionName = 'NAAR STAHOOGTE'; state.paused = true; }
  if (chosen === 'presets') state.height = 1086;
  render(); say(chosen === 'moving' ? 'Bewegingsvoorbeeld gepauzeerd om het ontwerp te bekijken. Tik op Stop of hervat de animatie.' : 'Voorbeeldscherm geladen met de waarden uit het ontwerp.');
});
heightInput.addEventListener('input', () => { if (state.screen === 'moving') return; state.height = clampHeight(Math.round(Number(heightInput.value) * 10)); state.saved = null; render(); });
document.querySelector('#connection').addEventListener('click', () => setConnected(!state.connected));
document.querySelector('#reset').addEventListener('click', () => { stopTimer(); state = defaultState(); render(); say('Demo hersteld naar de beginwaarden.'); });
pauseButton.addEventListener('click', () => { state.paused = false; syncTools(); previousTime = 0; motionFrame = requestAnimationFrame(tick); });
document.addEventListener('keydown', event => { if (event.key !== 'Escape') return; if (state.screen === 'moving') stopMovement(); else if (state.screen === 'confirm') { state.screen = 'desk'; render(); say('Hoogtekeuze geannuleerd.'); } });
document.addEventListener('visibilitychange', () => { if (document.hidden && state.screen === 'moving' && !state.paused) stopMovement('Simulatie onderbroken'); });
function resize() { const padding = window.innerWidth <= 640 ? 16 : 24; const available = document.querySelector('main').clientWidth - (window.innerWidth <= 640 ? 36 : 64) - padding; const scale = Math.min(Number(document.querySelector('#zoom').value), available / 640); document.documentElement.style.setProperty('--scale', Math.max(.2, scale)); }
document.querySelector('#zoom').addEventListener('change', resize); window.addEventListener('resize', resize);
render(); resize();
