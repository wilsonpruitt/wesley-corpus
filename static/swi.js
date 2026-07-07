/* StrangelyWarmIndex — Frontend */

let radarChart = null;
let lastScoreResult = null;
let selectedExpected = null;

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
    lastScoreResult = data;
    lastScoreResult._inputText = text;
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
  // Reset feedback form
  selectedExpected = null;
  const fbSubmit = document.getElementById('fb-submit');
  if (fbSubmit) fbSubmit.disabled = false;
  const fbStatus = document.getElementById('fb-status');
  if (fbStatus) fbStatus.textContent = '';
  document.querySelectorAll('.swi-feedback-options button').forEach(b => b.classList.remove('btn-active'));
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

  // Engine badge
  renderEngineBadge(data.engine);

  // Word count advisory
  var advisoryCard = document.getElementById('swi-advisory-card');
  var advisoryEl = document.getElementById('swi-advisory');
  if (data.word_count_advisory) {
    advisoryEl.textContent = data.word_count_advisory;
    advisoryCard.style.display = 'block';
  } else {
    advisoryCard.style.display = 'none';
  }

  // Summary
  document.getElementById('swi-summary').textContent = data.summary;

  // Dimensions
  renderDimensions(data.dimensions);

  // Radar
  renderRadar(data.dimensions);

  // Markers
  renderMarkers(data.top_markers);

  // Counter-indicators (AI judge only — v1 lexicon fallback has no equivalent)
  renderCounterIndicators(data.counter_indicators);

  // Theme proximity
  if (data.semantic && data.semantic.available && data.semantic.closest_themes) {
    renderThemes(data.semantic.closest_themes);
  }
}

function renderEngineBadge(engine) {
  const badge = document.getElementById('swi-engine-badge');
  if (!engine) { badge.style.display = 'none'; return; }
  if (engine === 'judge') {
    badge.textContent = 'AI Judge';
    badge.className = 'swi-engine-badge engine-judge';
  } else {
    badge.textContent = 'Classic Lexicon';
    badge.className = 'swi-engine-badge engine-lexicon-fallback';
  }
  badge.style.display = 'inline-block';
}

function renderCounterIndicators(counters) {
  const card = document.getElementById('swi-counters-card');
  const container = document.getElementById('swi-counters');
  if (!counters || Object.keys(counters).length === 0) {
    card.style.display = 'none';
    return;
  }
  card.style.display = 'block';
  container.innerHTML = '';
  for (const c of Object.values(counters)) {
    const row = document.createElement('div');
    row.className = 'swi-counter-row';

    const name = document.createElement('div');
    name.className = 'swi-counter-name';
    name.textContent = c.name;

    const stance = document.createElement('div');
    stance.className = 'swi-counter-stance stance-' + c.stance;
    stance.textContent = c.stance;

    const note = document.createElement('div');
    note.className = 'swi-counter-note';
    note.textContent = c.note || '';

    row.append(name, stance, note);
    container.appendChild(row);
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

    const name = document.createElement('div');
    name.className = 'swi-dim-name';
    name.textContent = d.name;

    const barBg = document.createElement('div');
    barBg.className = 'swi-dim-bar-bg';
    const bar = document.createElement('div');
    bar.className = 'swi-dim-bar';
    bar.style.width = d.score + '%';
    barBg.appendChild(bar);

    const score = document.createElement('div');
    score.className = 'swi-dim-score';
    score.textContent = d.score;

    const explain = document.createElement('div');
    explain.className = 'swi-dim-explain';
    explain.textContent = d.explanation;

    row.append(name, barBg, score, explain);
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

function selectExpected(btn) {
  selectedExpected = btn.dataset.expected;
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('btn-active'));
  btn.classList.add('btn-active');
}

async function submitFeedback() {
  if (!selectedExpected) return alert('Please select whether the score seems too high, about right, or too low.');
  if (!lastScoreResult) return;

  const body = {
    text_snippet: (lastScoreResult._inputText || '').slice(0, 500),
    overall_score: lastScoreResult.overall_score,
    expected: selectedExpected,
    expected_score: parseInt(document.getElementById('fb-expected-score').value) || null,
    comment: document.getElementById('fb-comment').value.trim(),
    author: document.getElementById('fb-author').value.trim(),
  };

  const status = document.getElementById('fb-status');
  try {
    const resp = await fetch('/api/swi/feedback', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(await resp.text());
    status.textContent = 'Thanks! Feedback submitted.';
    status.className = 'swi-feedback-status status-ok';
    document.getElementById('fb-submit').disabled = true;
  } catch (e) {
    status.textContent = 'Error: ' + e.message;
    status.className = 'swi-feedback-status status-err';
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

    const h3 = document.createElement('h3');
    h3.textContent = r.label_name;

    const gauge = document.createElement('div');
    gauge.className = 'swi-gauge';
    const fill = document.createElement('div');
    fill.className = 'swi-gauge-fill ' + gaugeClass(r.overall_score);
    fill.style.width = r.overall_score + '%';
    const scoreEl = document.createElement('div');
    scoreEl.className = 'swi-gauge-score';
    scoreEl.textContent = r.overall_score;
    gauge.append(fill, scoreEl);

    const gaugeLabel = document.createElement('div');
    gaugeLabel.className = 'swi-gauge-label';
    gaugeLabel.textContent = r.label;

    const summary = document.createElement('p');
    summary.className = 'swi-compare-summary';
    summary.textContent = r.summary;

    col.append(h3, gauge, gaugeLabel, summary);
    container.appendChild(col);
  }
}
