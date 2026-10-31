const $ = (s) => document.querySelector(s);
const el = {
  drop: $('#drop'), input: $('#fileInput'),
  studio: $('#studio'), fName: $('#fName'), chips: $('#chips'), btnClear: $('#btnClear'),
  imgSrc: $('#imgSrc'), imgOut: $('#imgOut'), outHint: $('#outHint'), outCap: $('#outCap'),
  colorPicker: $('#colorPicker'), colorHex: $('#colorHex'), btnPick: $('#btnPick'),
  tol: $('#tol'), tolVal: $('#tolVal'), soft: $('#soft'), softVal: $('#softVal'),
  despill: $('#despill'), shrink: $('#shrink'),
  seg: $('#fmtSeg'), tierSeg: $('#tierSeg'), scaleSeg: $('#scaleSeg'),
  btnRun: $('#btnRun'),
  running: $('#running'), stageText: $('#stageText'), pctText: $('#pctText'), barFill: $('#barFill'),
  result: $('#result'), resInfo: $('#resInfo'), dl: $('#dl'),
  btnFolder: $('#btnFolder'), btnAgain: $('#btnAgain'), resNote: $('#resNote'),
  error: $('#error'), outDir: $('#outDir'), btnQuit: $('#btnQuit'),
};

let state = {
  jobId: null, meta: null, fmt: 'gif', tier: 'original', scale: 1,
  timer: null, previewUrl: null, running: false,
};

fetch('/api/info').then(r => r.json()).then(d => { el.outDir.textContent = d.output_dir; }).catch(() => {});

/* ---------------- 选择文件 ---------------- */
el.drop.addEventListener('click', () => el.input.click());
el.input.addEventListener('change', () => { if (el.input.files[0]) upload(el.input.files[0]); });
['dragenter', 'dragover'].forEach(t => el.drop.addEventListener(t, e => { e.preventDefault(); el.drop.classList.add('drag'); }));
['dragleave', 'drop'].forEach(t => el.drop.addEventListener(t, e => { e.preventDefault(); el.drop.classList.remove('drag'); }));
el.drop.addEventListener('drop', e => {
  const f = e.dataTransfer.files && e.dataTransfer.files[0];
  if (f) upload(f);
});
window.addEventListener('dragover', e => e.preventDefault());
window.addEventListener('drop', e => e.preventDefault());

async function upload(file) {
  hideError();
  el.drop.classList.add('busy');
  const fd = new FormData();
  fd.append('file', file);
  try {
    const r = await fetch('/api/upload', { method: 'POST', body: fd });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || '上传失败');
    state.jobId = d.job_id;
    state.meta = d;
    renderMeta(file, d);
    el.studio.classList.remove('hidden');
    el.drop.classList.add('hidden');
    el.result.classList.add('hidden');
    el.imgSrc.src = '/api/file/' + d.job_id + '/source?t=' + Date.now();
    el.imgOut.removeAttribute('src');
    el.outHint.classList.remove('hidden');
    el.outCap.textContent = '结果';
    setColor(d.suggest_color || '#00ff00');
    schedulePreview(60);
  } catch (e) {
    showError(e.message);
  } finally {
    el.drop.classList.remove('busy');
  }
}

function renderMeta(file, d) {
  el.fName.textContent = file.name;
  const parts = [
    `${d.width} × ${d.height}`,
    d.animated ? `${d.frames} 帧` : '静态图',
    d.animated ? `${(d.duration_ms / 1000).toFixed(2)} 秒` : null,
    fmtSize(d.bytes),
  ].filter(Boolean);
  el.chips.innerHTML = parts.map(p => `<span class="chip">${p}</span>`).join('');
}

function fmtSize(b) {
  if (!b && b !== 0) return '—';
  const u = ['B', 'KB', 'MB'];
  let i = 0, n = b;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i === 0 ? n : n.toFixed(1)) + ' ' + u[i];
}

/* ---------------- 参数 ---------------- */
function setColor(hex) {
  const v = normHex(hex);
  el.colorHex.value = v;
  el.colorPicker.value = v;
}

function normHex(s) {
  s = (s || '').trim();
  if (!s.startsWith('#')) s = '#' + s;
  if (/^#[0-9a-fA-F]{3}$/.test(s)) s = '#' + s.slice(1).split('').map(c => c + c).join('');
  return /^#[0-9a-fA-F]{6}$/.test(s) ? s.toLowerCase() : '#00ff00';
}

el.colorPicker.addEventListener('input', () => {
  el.colorHex.value = el.colorPicker.value;
  schedulePreview();
});
el.colorHex.addEventListener('input', () => {
  const v = el.colorHex.value.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(v)) { el.colorPicker.value = v; schedulePreview(); }
});
el.colorHex.addEventListener('blur', () => setColor(el.colorHex.value));
el.btnPick.addEventListener('click', () => {
  if (state.meta) { setColor(state.meta.suggest_color || '#00ff00'); schedulePreview(); }
});

el.tol.addEventListener('input', () => { el.tolVal.textContent = el.tol.value; schedulePreview(); });
el.soft.addEventListener('input', () => { el.softVal.textContent = el.soft.value; schedulePreview(); });
el.despill.addEventListener('change', () => schedulePreview());
el.shrink.addEventListener('change', () => schedulePreview());

function bindSeg(box, cb) {
  if (!box) return;
  box.addEventListener('click', (e) => {
    const item = e.target.closest('.seg-item');
    if (!item) return;
    box.querySelectorAll('.seg-item').forEach(s => s.classList.toggle('is-active', s === item));
    const radio = item.querySelector('input');
    if (radio) radio.checked = true;
    cb(item);
  });
}

bindSeg(el.seg, (it) => { state.fmt = it.dataset.fmt; });
bindSeg(el.tierSeg, (it) => { state.tier = it.dataset.tier; });
bindSeg(el.scaleSeg, (it) => { state.scale = parseFloat(it.dataset.scale) || 1; });

/* ---------------- 实时单帧预览 ---------------- */
let previewTimer = null;
function schedulePreview(delay = 260) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(doPreview, delay);
}

async function doPreview() {
  if (!state.jobId || state.running) return;
  try {
    const r = await fetch('/api/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: state.jobId,
        color: el.colorHex.value,
        tolerance: +el.tol.value,
        softness: +el.soft.value,
        despill: el.despill.checked,
        shrink: el.shrink.checked,
      }),
    });
    if (!r.ok) return;
    const blob = await r.blob();
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = URL.createObjectURL(blob);
    el.imgOut.src = state.previewUrl;
    el.outHint.classList.add('hidden');
    el.outCap.textContent = '效果预览（第 1 帧）';
  } catch (e) { /* 忽略瞬时失败 */ }
}

/* ---------------- 处理 ---------------- */
el.btnRun.addEventListener('click', async () => {
  if (!state.jobId || state.running) return;
  hideError();
  state.running = true;
  el.btnRun.disabled = true;
  el.btnRun.textContent = '处理中…';
  el.result.classList.add('hidden');
  el.running.classList.remove('hidden');
  try {
    const r = await fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: state.jobId,
        color: el.colorHex.value,
        tolerance: +el.tol.value,
        softness: +el.soft.value,
        despill: el.despill.checked,
        shrink: el.shrink.checked,
        format: state.fmt,
        tier: state.tier,
        scale: state.scale,
      }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || '启动失败');
    poll();
  } catch (e) {
    showError(e.message);
    finishRun();
  }
});

function poll() {
  clearInterval(state.timer);
  state.timer = setInterval(async () => {
    if (!state.jobId) return;
    try {
      const r = await fetch('/api/job/' + state.jobId);
      const j = await r.json();
      const p = Math.max(0, Math.min(100, j.progress || 0));
      el.barFill.style.width = p + '%';
      el.pctText.textContent = p.toFixed(0) + '%';
      el.stageText.textContent = j.stage || '处理中…';
      if (j.status === 'done') {
        clearInterval(state.timer);
        showResult(j);
      } else if (j.status === 'error') {
        clearInterval(state.timer);
        finishRun();
        showError(j.error || '处理失败');
      }
    } catch (e) { /* 网络抖动忽略 */ }
  }, 400);
}

function finishRun() {
  state.running = false;
  el.btnRun.disabled = false;
  el.btnRun.textContent = '去背景';
  el.running.classList.add('hidden');
}

function showResult(j) {
  finishRun();
  const res = j.result;
  el.result.classList.remove('hidden');
  el.imgOut.src = '/api/file/' + state.jobId + '/result?t=' + Date.now();
  el.outHint.classList.add('hidden');
  el.outCap.textContent = '结果（' + String(res.kind).toUpperCase() + '）';
  el.dl.href = '/api/file/' + state.jobId + '/result?download=1';
  el.dl.textContent = '下载 ' + res.name;
  el.dl.setAttribute('download', res.name);

  const before = state.meta ? state.meta.bytes : 0;
  const delta = before ? ((res.size / before - 1) * 100) : 0;
  const frText = res.encoded_frames && res.encoded_frames !== res.frames
    ? `${res.frames}→${res.encoded_frames} 帧` : `${res.frames} 帧`;
  el.resInfo.textContent = `${res.width}×${res.height} · ${frText} · ${fmtSize(res.size)}`
    + (before ? `（原 ${fmtSize(before)}，${delta >= 0 ? '+' : ''}${delta.toFixed(0)}%）` : '');

  const tierName = { original: '原画质', standard: '标准', strong: '强力', max: '极限' }[res.tier || 'original'] || '';
  el.resNote.textContent = `${tierName}档 · ` + (res.kind === 'gif'
    ? 'GIF 只有「透明 / 不透明」两种状态，边缘会偏硬；体积还是太大就选「强力 / 极限」，或者切到 WebP。'
    : 'WebP 保留平滑的透明度，能在浏览器、微信、大部分新软件里正常显示；同样画质下通常只有 GIF 的 1/3~1/2。');
}

/* ---------------- 其它 ---------------- */
el.btnClear.addEventListener('click', () => {
  clearInterval(state.timer);
  if (state.previewUrl) { URL.revokeObjectURL(state.previewUrl); state.previewUrl = null; }
  state.jobId = null; state.meta = null; state.running = false;
  el.studio.classList.add('hidden');
  el.drop.classList.remove('hidden');
  el.input.value = '';
  el.running.classList.add('hidden');
  el.result.classList.add('hidden');
  el.btnRun.disabled = false;
  el.btnRun.textContent = '去背景';
  hideError();
});

el.btnAgain.addEventListener('click', () => { el.result.classList.add('hidden'); el.btnRun.scrollIntoView({ behavior: 'smooth', block: 'center' }); });

el.btnFolder.addEventListener('click', async () => {
  try {
    const r = await fetch('/api/job/' + state.jobId);
    const j = await r.json();
    const dir = (j.result && j.result.dir) || '';
    const resp = await fetch('/api/reveal', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ dir }),
    });
    if (!resp.ok) {
      const d = await resp.json().catch(() => ({}));
      throw new Error(d.error || '打不开文件夹');
    }
  } catch (e) { showError(e.message || '打不开文件夹'); }
});

el.btnQuit.addEventListener('click', async () => {
  if (!confirm('确定要关闭 GIF 去背景吗？')) return;
  try { await fetch('/api/quit', { method: 'POST' }); } catch (e) {}
  document.body.innerHTML = '<div style="display:grid;place-items:center;height:100vh;font:15px/1.6 system-ui;color:#6a7a77">服务已关闭，可以直接关掉这个页面。</div>';
});

function showError(msg) { el.error.textContent = msg; el.error.classList.remove('hidden'); }
function hideError() { el.error.classList.add('hidden'); }

/* 演示模式：?demo=studio 用于预览界面 */
if (new URLSearchParams(location.search).get('demo') === 'studio') {
  el.studio.classList.remove('hidden');
  el.drop.classList.add('hidden');
  el.fName.textContent = '猫猫跳舞.gif';
  el.chips.innerHTML = ['480 × 360', '36 帧', '2.88 秒', '1.4 MB'].map(p => `<span class="chip">${p}</span>`).join('');
}
