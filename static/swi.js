/* StrangelyWarmIndex — Frontend */

let radarChart = null;

async function scoreText() {
  const text = document.getElementById('swi-text').value.trim();
  if (!text) return alert('Please enter some text to score.');

  showLoading(true);
  hideResults();

  try {
    const resp = await fetch('/api/swi/score', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, include_semantic: true}),
    });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    renderResults(data);
  } catch (e) {
    alert('Error scoring text: ' + e.message);
  } finally {
    showLoading(false);
  }
}

function toggleCompare() {
  const section = document.getElementById('swi-compare-section');
  section.style.display = section.style.display === 'none' ? 'block' : 'none';
}

async function compareTexts() {
  const a = document.getElementById('swi-text-a').value.trim();
  const b = document.getElementById('swi-text-b').value.trim();
  if (!a || !b) return alert('Please enter both texts.');

  showLoading(true);
  hideResults();

  try {
    const resp = await fetch('/api/swi/compare', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({texts: [
        {label: 'Text A', text: a},
        {label: 'Text B', text: b},
      ]}),
    });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    renderCompare(data);
  } catch (e) {
    alert('Error comparing: ' + e.message);
  } finally {
    showLoading(false);
  }
}

function showLoading(show) {
  document.getElementById('swi-loading').style.display = show ? 'flex' : 'none';
}

function hideResults() {
  document.getElementById('swi-results').style.display = 'none';
  document.getElementById('swi-compare-results').style.display = 'none';
}

function renderResults(data) {
  const el = document.getElementById('swi-results');
  el.style.display = 'block';

  // Gauge
  const score = data.overall_score;
  const fill = document.getElementById('swi-gauge-fill');
  const scoreEl = document.getElementById('swi-gauge-score');
  const labelEl = document.getElementById('swi-gauge-label');

  fill.style.width = score + '%';
  fill.className = 'swi-gauge-fill ' + gaugeClass(score);
  scoreEl.textContent = score;
  labelEl.textContent = data.label;

  // Summary
  document.getElementById('swi-summary').textContent = data.summary;

  // Dimensions
  renderDimensions(data.dimensions);

  // Radar
  renderRadar(data.dimensions);

  // Markers
  renderMarkers(data.top_markers);

  // Theme proximity
  if (data.semantic && data.semantic.available && data.semantic.closest_themes) {
    renderThemes(data.semantic.closest_themes);
  }
}

function gaugeClass(score) {
  if (score >= 85) return 'gauge-hot';
  if (score >= 65) return 'gauge-warm';
  if (score >= 40) return 'gauge-mild';
  return 'gauge-cool';
}

function renderDimensions(dims) {
  const container = document.getElementById('swi-dimensions');
  container.innerHTML = '';
  const entries = Object.values(dims).sort((a, b) => b.score - a.score);
  for (const d of entries) {
    const row = document.createElement('div');
    row.className = 'swi-dim-row';
    row.innerHTML = `
      <div class="swi-dim-name">${d.name}</div>
      <div class="swi-dim-bar-bg">
        <div class="swi-dim-bar" style="width:${d.score}%"></div>
      </div>
      <div class="swi-dim-score">${d.score}</div>
      <div class="swi-dim-explain">${d.explanation}</div>
    `;
    container.appendChild(row);
  }
}

function renderRadar(dims) {
  const canvas = document.getElementById('swi-radar');
  const labels = [];
  const values = [];
  for (const d of Object.values(dims)) {
    labels.push(d.name);
    values.push(d.score);
  }

  if (radarChart) radarChart.destroy();

  radarChart = new Chart(canvas, {
    type: 'radar',
    data: {
      labels,
      datasets: [{
        label: 'SWI Score',
        data: values,
        backgroundColor: 'rgba(107, 58, 42, 0.2)',
        borderColor: '#6b3a2a',
        pointBackgroundColor: '#6b3a2a',
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      scales: {
        r: {
          beginAtZero: true,
          max: 100,
          ticks: { stepSize: 20, display: false },
          pointLabels: { font: { size: 11, family: 'Georgia' } },
        }
      },
      plugins: { legend: { display: false } },
    }
  });
}

function renderMarkers(markers) {
  const container = document.getElementById('swi-markers');
  container.innerHTML = '';
  if (!markers || markers.length === 0) {
    container.innerHTML = '<p class="swi-no-data">No distinctive markers found.</p>';
    return;
  }
  for (const m of markers) {
    const tag = document.createElement('span');
    tag.className = 'swi-marker-tag';
    tag.setAttribute('data-dimension', m.dimension || '');
    tag.textContent = m.text;
    tag.title = m.dimension || m.type || '';
    container.appendChild(tag);
  }
}

function renderThemes(themes) {
  const card = document.getElementById('swi-themes-card');
  const container = document.getElementById('swi-themes');
  if (!themes || themes.length === 0) { card.style.display = 'none'; return; }
  card.style.display = 'block';
  container.innerHTML = '';
  for (const [id, score] of themes) {
    const row = document.createElement('div');
    row.className = 'swi-dim-row';
    row.innerHTML = `
      <div class="swi-dim-name">${id.replace(/-/g, ' ')}</div>
      <div class="swi-dim-bar-bg">
        <div class="swi-dim-bar" style="width:${score}%"></div>
      </div>
      <div class="swi-dim-score">${score}</div>
    `;
    container.appendChild(row);
  }
}

function renderCompare(data) {
  const container = document.getElementById('swi-compare-grid');
  const wrap = document.getElementById('swi-compare-results');
  wrap.style.display = 'block';
  container.innerHTML = '';

  for (const r of data.results) {
    const col = document.createElement('div');
    col.className = 'swi-compare-col';
    col.innerHTML = `
      <h3>${r.label_name}</h3>
      <div class="swi-gauge">
        <div class="swi-gauge-fill ${gaugeClass(r.overall_score)}" style="width:${r.overall_score}%"></div>
        <div class="swi-gauge-score">${r.overall_score}</div>
      </div>
      <div class="swi-gauge-label">${r.label}</div>
      <p class="swi-compare-summary">${r.summary}</p>
    `;
    container.appendChild(col);
  }
}
