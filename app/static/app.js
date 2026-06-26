const form = document.querySelector('#query-form');
const results = document.querySelector('#results');
const groupsRoot = document.querySelector('#result-groups');
const submit = document.querySelector('.submit');
const scoreInput = document.querySelector('#score');
const rankInput = document.querySelector('#rank');
const primaryInput = document.querySelector('#primary');
const rankStatus = document.querySelector('#rank-status');
const passwordInput = document.querySelector('#password');
const passwordStatus = document.querySelector('#password-status');
const checkPasswordBtn = document.querySelector('#check-password');

const labels = {
  rush: { title: '冲击', en: 'REACH', note: '值得尝试，建议服从调剂', icon: '↑' },
  stable: { title: '稳妥', en: 'MATCH', note: '位次适配，作为方案主体', icon: '≈' },
  secure: { title: '保底', en: 'SAFETY', note: '留足余量，控制滑档风险', icon: '✓' },
};

const fmt = value => new Intl.NumberFormat('zh-CN').format(value);
const safeNumber = (selector, fallback, minimum = 0) => {
  const input = document.querySelector(selector);
  const parsed = Number(input.value);
  const value = Number.isFinite(parsed) && parsed >= minimum ? parsed : fallback;
  input.value = value;
  return value;
};

function readableError(data) {
  if (typeof data.detail === 'string') return data.detail;
  const first = Array.isArray(data.detail) ? data.detail[0] : null;
  if (!first) return '请求失败，请检查输入后重试';
  const field = { rush_gap: '冲击范围', stable_gap: '稳妥范围', secure_gap: '保底范围', score: '分数', rank: '位次' }[first.loc?.at(-1)] || '输入值';
  if (first.type === 'greater_than_equal') return `${field}不能小于 ${first.ctx?.ge}`;
  if (first.type === 'greater_than') return `${field}必须大于 ${first.ctx?.gt}`;
  return `${field}不正确`;
}

function collegeCard(item, tier) {
  const history = item.history.map(x => `<span>${x.year}<b>${x.score}分</b><i>${fmt(x.rank)}名</i></span>`).join('');
  const gap = item.rank_gap >= 0 ? `领先 ${fmt(item.rank_gap)} 名` : `落后 ${fmt(Math.abs(item.rank_gap))} 名`;
  return `<article class="college-card ${tier}">
    <div class="prob"><b>${item.probability}%</b><span>模拟概率</span></div>
    <div class="college-main">
      <div class="college-title"><div><h4>${item.college_name}</h4><p>${item.city} · ${item.school_type} · 院校代码 ${item.college_code}</p></div><span>${gap}</span></div>
      <div class="meta"><span>${item.program_group}</span><span>选科 ${item.subject_requirement}</span><span>预测 ${item.predicted_score} 分 / ${fmt(item.predicted_rank)} 名</span></div>
      <details class="history"><summary>查看三年依据 <i>波动 ±${fmt(item.volatility)} 名</i></summary><div>${history}</div></details>
    </div>
  </article>`;
}

function render(data) {
  const p = data.profile;
  document.querySelector('#profile-chips').innerHTML = [
    `${p.province}考生`, `${p.college_region}院校`, `${p.subjects}`, `${p.score} 分`, `${fmt(p.rank)} 名`,
    p.score_line_label ? `<span style="border-color:#e45d43;background:#fef0ed">2026 ${p.score_line_label}</span>` : '',
  ].join('');
  groupsRoot.innerHTML = Object.entries(labels).map(([tier, copy]) => {
    const items = data.recommendations[tier];
    return `<section class="result-group ${tier}">
      <header><div class="tier-mark">${copy.icon}</div><div><p>${copy.en}</p><h3>${copy.title}<span>${copy.note}</span></h3></div><b>${items.length} 所</b></header>
      <div class="college-list">${items.length ? items.map(x => collegeCard(x, tier)).join('') : '<p class="group-empty">此梯度暂无匹配院校</p>'}</div>
    </section>`;
  }).join('');
  const total = Object.values(data.summary).reduce((a, b) => a + b, 0);
  document.querySelector('#empty-state').classList.toggle('hidden', total > 0);
  document.querySelector('#disclaimer-text').textContent = `${data.disclaimer} ${data.methodology}`;

  // Show password remaining count
  if (data.password_remaining !== undefined) {
    const remaining = data.password_remaining;
    const msg = data.password_message || '';
    const warnClass = remaining < 3 ? 'password-warn' : 'password-ok';
    const html = `<section class="password-info ${warnClass}"><h4>密码剩余 <b>${remaining}</b> 次</h4><p>${msg}</p></section>`;
    const refSection = document.querySelector('.reference-2026');
    if (refSection) {
      refSection.insertAdjacentHTML('beforebegin', html);
    }
  }

  // Append 2026 score line reference
  const refHtml = `<section class="reference-2026">
    <header><span style="font-size:24px">📊</span><div><h3>2026年广东（物理）省控线参考</h3><p>广东省教育考试院 2026.06.24 公布 · 院校投档线预计7月中下旬发布</p></div></header>
    <div class="line-grid">
      <div class="line-item"><b>${p.score_line_2026['本科批']}</b><span>本科批<br><small>位次约 ${fmt(p.rank_brackets_2026[425])}</small></span></div>
      <div class="line-item"><b>${p.score_line_2026['特殊类型招生控制线']}</b><span>特控线<br><small>位次约 ${fmt(p.rank_brackets_2026[539])}</small></span></div>
      <div class="line-item ${p.score >= 600 ? 'highlight' : ''}"><b>${p.score >= 600 ? p.score : '-'}</b><span>你的分数<br><small>位次 ${fmt(p.rank)}</small></span></div>
    </div>
    <p class="ref-note">※ 2026年各院校专业组投档线尚未公布。推荐算法基于2023-2025三年加权位次，结果仅供参考。</p>
  </section>`;
  const lastGroup = groupsRoot.querySelector('.result-group:last-child');
  if (lastGroup) {
    lastGroup.insertAdjacentHTML('afterend', refHtml);
  } else {
    groupsRoot.insertAdjacentHTML('beforeend', refHtml);
  }

  results.classList.remove('hidden');
  results.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

checkPasswordBtn.addEventListener('click', async () => {
  const password = passwordInput.value.trim();
  if (!password || password.length !== 6) {
    passwordStatus.textContent = '请输入6位数字密码';
    return;
  }
  passwordStatus.textContent = '验证中…';
  try {
    const response = await fetch(`/api/password/check?password=${encodeURIComponent(password)}`, { method: 'POST' });
    const data = await response.json();
    if (data.valid) {
      passwordStatus.innerHTML = `✅ ${data.message}`;
    } else {
      passwordStatus.textContent = `❌ ${data.message}`;
    }
  } catch {
    passwordStatus.textContent = '验证失败，请稍后重试';
  }
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  const rank = Number(rankInput.value);
  if (!rank || rank <= 1) {
    alert('位次数据未就绪，请先确认首选科目是否正确（本系统目前仅收录物理类数据）');
    return;
  }
  submit.disabled = true;
  submit.querySelector('span').textContent = '正在计算三年位次…';
  const password = passwordInput.value.trim();
  if (!password || password.length !== 6) {
    alert('请输入6位数字密码');
    submit.disabled = false;
    submit.querySelector('span').textContent = '生成我的志愿方案';
    return;
  }
  const body = {
    password,
    province: document.querySelector('#province').value,
    college_region: document.querySelector('#college-region').value,
    subjects: document.querySelector('#primary').value + document.querySelector('#subjects').value,
    score: Number(document.querySelector('#score').value), rank,
    rush_gap: safeNumber('#rush-gap', 3000, 500),
    stable_gap: safeNumber('#stable-gap', 5000, 1000),
    secure_gap: safeNumber('#secure-gap', 12000, 2000),
    exclude_program_types: [...document.querySelectorAll('.exclude-type')].filter(cb => cb.checked).map(cb => cb.dataset.type),
  };
  try {
    const response = await fetch('/api/recommendations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(readableError(data));
    render(data);
  } catch (error) {
    alert(`无法生成方案：${error.message}`);
  } finally {
    submit.disabled = false;
    submit.querySelector('span').textContent = '生成我的志愿方案';
  }
});

let rankTimer;
async function updateRank() {
  const score = Number(scoreInput.value);
  if (!Number.isFinite(score) || score < 0 || score > 750) return;
  rankStatus.textContent = '正在匹配官方分数段数据…';
  try {
    const params = new URLSearchParams({ score, primary: primaryInput.value, province: document.querySelector('#province').value });
    // Fetch 4-year rank data
    const [singleResponse, allResponse] = await Promise.all([
      fetch(`/api/rank?${params}`),
      fetch(`/api/rank/all?${params}`),
    ]);
    const singleData = await singleResponse.json();
    const allData = await allResponse.json();
    if (!singleData.available) throw new Error(singleData.message);

    rankInput.value = singleData.rank;

    // Populate 4-year rank grid
    if (allData.available && allData.years) {
      const yearEls = document.querySelectorAll('#rank-years .ryear b');
      allData.years.forEach((y, i) => {
        if (yearEls[i]) {
          yearEls[i].textContent = fmt(y.rank);
          yearEls[i].className = y.is_current ? 'current' : '';
        }
      });
      rankStatus.innerHTML = `<a href="${allData.source}" target="_blank" rel="noopener">广东省教育考试院 官方一分一段表</a>`;
    } else {
      rankStatus.innerHTML = `<b>${singleData.label}</b>`;
    }
  } catch (error) {
    rankInput.value = '';
    rankStatus.textContent = error.message;
  }
}

scoreInput.addEventListener('input', () => { clearTimeout(rankTimer); rankTimer = setTimeout(updateRank, 250); });
primaryInput.addEventListener('change', updateRank);
updateRank();
