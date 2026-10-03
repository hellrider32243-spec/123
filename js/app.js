"use strict";

const LETTERS = ["А", "Б", "В", "Г"];
const STORE_KEY = "erudit-archive-v1";
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const ICONS = {
  history: '<path d="M9 7.5h11.5A2.5 2.5 0 0 1 23 10v13H12a3 3 0 0 0-3 3V7.5z"/><path d="M9 26a3 3 0 0 1 3-3h11"/>',
  science: '<circle cx="16" cy="16" r="2.2"/><ellipse cx="16" cy="16" rx="10" ry="4.2"/><ellipse cx="16" cy="16" rx="10" ry="4.2" transform="rotate(60 16 16)"/><ellipse cx="16" cy="16" rx="10" ry="4.2" transform="rotate(120 16 16)"/>',
  geo: '<path d="M16 27s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z"/><circle cx="16" cy="15" r="2.2"/>',
  lit: '<path d="M8 24c3-1 5.2-4.5 6-8 2 3 5 5.5 10 6"/><path d="M14 16c1.2-4 4-8 9-11-1 4-1.2 7-1 11"/><path d="M8 24c1.5 1.4 3.6 2 6 2"/>',
  art: '<rect x="7" y="8" width="18" height="14" rx="2"/><path d="M7 18l5-4 4 3 3-2 6 5"/>',
  nature: '<path d="M16 27V14"/><path d="M16 18c0-6 4-9 9-9-1 6-4 9-9 9z"/><path d="M16 20c0-5-3.5-8-8-8 1 5 3.5 8 8 8z"/>'
};

const state = {
  screen: "home",
  mode: null,
  category: null,
  questions: [],
  index: 0,
  points: 0,
  streak: 0,
  bestStreak: 0,
  answers: [],
  hintUsed: false,
  locked: false,
  hidden: new Set(),
  timeTotal: 20,
  timeLeft: 20,
  correctCount: 0,
  recordBroken: false
};

let store = loadStore();
let cleanups = [];
let timerId = 0;
let audioCtx = null;

function loadStore() {
  const blank = { best: {}, rounds: 0, daily: null, sound: false };
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return blank;
    const data = JSON.parse(raw);
    return {
      best: { ...blank.best, ...(data.best || {}) },
      rounds: Number.isFinite(Number(data.rounds)) ? Number(data.rounds) : 0,
      daily: data.daily || null,
      sound: Boolean(data.sound)
    };
  } catch (error) {
    return blank;
  }
}

function saveStore() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(store));
  } catch (error) {
    /* Private mode can block storage; the round still plays. */
  }
}

function esc(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[ch]));
}

function format(n) {
  return new Intl.NumberFormat("ru-RU").format(n);
}

function plural(n, one, few, many) {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return one;
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return few;
  return many;
}

function questionsWord(n) {
  return `${n} ${plural(n, "вопрос", "вопроса", "вопросов")}`;
}

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function todayKey() {
  const d = new Date();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

function shuffle(list) {
  const copy = [...list];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function categoryById(id) {
  return window.QUIZ_DATA.categories.find((item) => item.id === id);
}

function bestOf(key) {
  const n = Number(store.best?.[key] || 0);
  return Number.isFinite(n) ? n : 0;
}

function countIn(id) {
  return window.QUIZ_DATA.questions.filter((item) => item.category === id).length;
}

function dailyQuestion() {
  const bank = window.QUIZ_DATA.questions;
  return bank[hash(todayKey()) % bank.length];
}

function dailyStamp() {
  const saved = store.daily;
  if (!saved || saved.date !== todayKey()) return { done: false, correct: false };
  return { done: true, correct: Boolean(saved.correct) };
}

function icon(name) {
  return `<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round">${ICONS[name] || ""}</svg>`;
}

function difficultyLabel(level) {
  return ["", "лёгкий", "средний", "крепкий"][level] || "средний";
}

function dots(level) {
  return [1, 2, 3].map((i) => `<i class="${i <= level ? "on" : ""}"></i>`).join("");
}

function modeTitle() {
  if (state.mode === "marathon") return "Марафон";
  if (state.mode === "blitz") return "Блиц";
  if (state.mode === "daily") return "Вопрос дня";
  return categoryById(state.category)?.title || "Зал";
}

function modeKey() {
  if (state.mode === "hall") return state.category;
  return state.mode;
}

function current() {
  return state.questions[state.index];
}

function rank(percent) {
  if (percent >= 95) return ["Легенда зала", "Редкая точность. Такой результат хочется перечитывать."];
  if (percent >= 80) return ["Эрудит", "Уверенное знание и чувство детали."];
  if (percent >= 60) return ["Знаток", "Крепкая база. Ещё один заход добавит блеска."];
  if (percent >= 40) return ["Любопытный", "Вы уже в зале. Короткие объяснения доберут остальное."];
  return ["Следопыт", "Каждый ответ оставляет след. Повторите заход — карта станет яснее."];
}

function clearEffects() {
  cleanups.forEach((fn) => fn());
  cleanups = [];
  stopTimer();
}

function header() {
  const trailing = state.screen === "home"
    ? '<button class="nav-btn" type="button" data-action="halls">Залы</button>'
    : '<button class="nav-btn" type="button" data-action="home">На главную</button>';
  return `
    <header class="header">
      <a class="logo" href="#top" data-action="home">
        <span class="logo-mark">Э</span>
        <span><strong>Эрудит</strong><small>вопросы на эрудицию</small></span>
      </a>
      <nav class="nav">
        ${trailing}
        <button class="icon-btn ${store.sound ? "is-on" : ""}" type="button" data-action="sound" aria-pressed="${store.sound ? "true" : "false"}" aria-label="${store.sound ? "Выключить звук" : "Включить звук"}">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 10h4l5-4v12l-5-4H4z"/>
            <path d="M16 9.5a3.5 3.5 0 0 1 0 5"/>
            ${store.sound ? "" : '<path d="M5 5l14 14"/>'}
          </svg>
        </button>
      </nav>
    </header>
  `;
}

function footer() {
  const rounds = store.rounds;
  return `
    <footer class="footer">
      <span>Кабинет любопытства</span>
      <span>Сыграно ${rounds} ${plural(rounds, "партия", "партии", "партий")}</span>
    </footer>
  `;
}

function optionView(text, index, extra) {
  return `
    <button class="option" type="button" data-action="pick" data-index="${index}" ${extra || ""}>
      <span class="letter">${LETTERS[index]}</span>
      <span>${esc(text)}</span>
    </button>
  `;
}

function ticketMarkup(item) {
  return `
    <div class="ticket-body">
      <div class="ticket-top"><span>Витрина архива</span><span>${esc(item.tag)}</span></div>
      <h2>${esc(item.question)}</h2>
      <div class="options">
        ${item.options.map((text, index) => `<div class="option" data-demo="${index}"><span class="letter">${LETTERS[index]}</span><span>${esc(text)}</span></div>`).join("")}
      </div>
      <p class="ticket-note" hidden>${esc(item.note)}</p>
    </div>
  `;
}

function homeScreen() {
  const data = window.QUIZ_DATA;
  const stamp = dailyStamp();
  const daily = dailyQuestion();
  const dailyCat = categoryById(daily.category);
  const marathonBest = bestOf("marathon");
  const blitzBest = bestOf("blitz");
  const dailyBlock = stamp.done
    ? `
      <div class="daily">
        <div>
          <p class="eyebrow">Вопрос дня</p>
          <p class="daily-title">${stamp.correct ? "Сегодняшний билет взят точно." : "Сегодняшний билет уже открыт."}</p>
          <p class="muted">${esc(dailyCat.title)} · штамп дня сохранён</p>
        </div>
        <button class="btn ghost" type="button" data-action="play" data-mode="daily">Открыть снова</button>
      </div>`
    : `
      <div class="daily">
        <div>
          <p class="eyebrow">Вопрос дня</p>
          <p class="daily-title">В зале «${esc(dailyCat.title)}» лежит сегодняшний билет.</p>
          <p class="muted">Один вопрос, тридцать секунд, новый каждый день.</p>
        </div>
        <button class="btn primary" type="button" data-action="play" data-mode="daily">Открыть билет</button>
      </div>`;

  return `
    <section class="hero">
      <div>
        <p class="eyebrow">Кабинет любопытства</p>
        <h1>Живой зал<br>вопросов на<br><em>эрудицию</em></h1>
        <p class="lede">Шесть тем, честный таймер и короткое объяснение после каждого ответа. Идите марафоном, успевайте в блице или откройте один зал.</p>
        <div class="actions">
          <button class="btn primary" type="button" data-action="play" data-mode="marathon">Марафон · 12 вопросов</button>
          <button class="btn ghost" type="button" data-action="play" data-mode="blitz">Блиц · 10 секунд</button>
        </div>
        ${dailyBlock}
        <div class="chips">
          <span class="chip"><strong>${data.questions.length}</strong> ${plural(data.questions.length, "вопрос", "вопроса", "вопросов")} в архиве</span>
          <span class="chip">Марафон ${marathonBest ? `<strong>${format(marathonBest)}</strong>` : "без рекорда"}</span>
          <span class="chip">Блиц ${blitzBest ? `<strong>${format(blitzBest)}</strong>` : "без рекорда"}</span>
        </div>
      </div>
      <div class="ticket" id="ticket" aria-hidden="true"></div>
    </section>
    <section id="halls">
      <div class="section-head">
        <h2>Шесть залов</h2>
        <p class="muted">В каждом по ${questionsWord(countIn(data.categories[0].id))}.</p>
      </div>
      <div class="hall-grid">
        ${data.categories.map((cat, index) => {
          const best = bestOf(cat.id);
          const total = countIn(cat.id);
          return `
            <button class="hall" type="button" data-action="play" data-mode="hall" data-category="${cat.id}" style="--hue:${cat.hue}">
              ${icon(cat.icon)}
              <span class="hall-index">${String(index + 1).padStart(2, "0")}</span>
              <h3>${esc(cat.title)}</h3>
              <p>${esc(cat.text)}</p>
              <span class="meta">${questionsWord(total)}${best ? ` · рекорд ${format(best)}` : ""}</span>
            </button>`;
        }).join("")}
      </div>
    </section>
    <section class="marquee-block">
      <div class="marquee" aria-hidden="true">
        <div class="marquee-track">
          ${[...data.facts, ...data.facts].map((fact) => `<span>${esc(fact)}</span><i></i>`).join("")}
        </div>
      </div>
    </section>
  `;
}

function quizScreen() {
  const q = current();
  const cat = categoryById(q.category);
  const last = state.index + 1 === state.questions.length;
  return `
    <section class="quiz-screen">
      <div class="quiz-sticky">
        <div class="quiz-top">
          <div class="crumbs">${esc(modeTitle())} · ${state.index + 1} из ${state.questions.length}</div>
          <div class="hud">
            <span class="chip">очки <strong id="points">${format(state.points)}</strong></span>
            <span class="chip">серия <strong id="streak">${state.streak}</strong></span>
            <div class="timer" id="timer" aria-label="Таймер">
              <svg viewBox="0 0 44 44">
                <circle class="track" cx="22" cy="22" r="18"></circle>
                <circle class="value" id="time-ring" cx="22" cy="22" r="18"></circle>
              </svg>
              <span class="time-num" id="time-num">${state.timeTotal}</span>
            </div>
          </div>
        </div>
        <div class="bar" aria-hidden="true"><span id="bar"></span></div>
      </div>
      <article class="sheet">
        <div class="sheet-tools">
          <div>
            <p class="sheet-kicker" style="color: hsl(${cat.hue} 62% 28%)">${esc(cat.kicker)}</p>
            <div class="diff"><span class="diff-dots">${dots(q.difficulty)}</span>${difficultyLabel(q.difficulty)}</div>
          </div>
          <button class="hint-btn" type="button" id="hint" data-action="hint" ${state.hintUsed ? "disabled" : ""}>
            ${state.hintUsed ? "Подсказка использована" : "Убрать два"}
          </button>
        </div>
        <h2 id="question">${esc(q.question)}</h2>
        <div class="options" id="options">
          ${q.options.map((text, index) => optionView(text, index)).join("")}
        </div>
        <p class="score-note">Быстрый ответ и серия повышают очки.</p>
        <div class="explain" id="explain" hidden>
          <p class="verdict" id="verdict"></p>
          <p>${esc(q.explanation)}</p>
          <p>Верный ответ: <strong>${esc(q.options[q.answer])}</strong></p>
        </div>
        <div class="sheet-foot" id="next-wrap" hidden>
          <button class="btn primary" type="button" data-action="next">${last ? "К итогам" : "Дальше"}</button>
        </div>
        <p class="sr" id="status" aria-live="polite"></p>
      </article>
      <p class="keys">Клавиши 1–4 — ответ, H — убрать два, Enter — дальше</p>
    </section>
  `;
}

function resultScreen() {
  const total = state.questions.length;
  const percent = Math.round((state.correctCount / total) * 100);
  const [title, copy] = rank(percent);
  const best = bestOf(modeKey());
  return `
    <section class="result-screen">
      <p class="eyebrow">${esc(modeTitle())} завершён</p>
      <div class="ring-wrap">
        <div class="ring" id="ring">
          <div class="ring-hole">
            <div>
              <strong id="pct">0</strong>
              <span>%</span>
            </div>
          </div>
        </div>
      </div>
      <h2>${esc(title)}</h2>
      <p class="result-copy">${esc(copy)} Верных ответов: ${state.correctCount} из ${total}.</p>
      <div class="chips" style="justify-content:center">
        <span class="chip">очки <strong>${format(state.points)}</strong></span>
        <span class="chip">серия <strong>${state.bestStreak}</strong></span>
        <span class="chip">рекорд <strong>${format(best)}</strong></span>
        ${state.recordBroken ? '<span class="chip record">новый рекорд</span>' : ""}
      </div>
      <div class="actions result-actions">
        <button class="btn primary" type="button" data-action="again">Ещё раз</button>
        <button class="btn ghost" type="button" data-action="home">На главную</button>
        <button class="btn ghost" type="button" data-action="copy">Скопировать итог</button>
      </div>
      <button class="text-btn" type="button" data-action="review" aria-expanded="false" aria-controls="review">Разобрать ответы</button>
      <div class="review" id="review" hidden>
        <div class="filters">
          <button class="filter is-on" type="button" data-action="filter" data-filter="all">Все</button>
          <button class="filter" type="button" data-action="filter" data-filter="bad">Только промахи</button>
        </div>
        ${state.answers.map((item) => {
          const ok = item.picked === item.answer;
          const yours = item.timedOut ? "время вышло" : item.options[item.picked];
          return `
            <article class="review-item" data-ok="${ok ? "1" : "0"}">
              <p class="q">${esc(item.question)}</p>
              <p>Ваш ответ: <strong class="${ok ? "ok-text" : "bad-text"}">${esc(yours)}</strong></p>
              ${ok ? "" : `<p>Верно: <strong class="ok-text">${esc(item.options[item.answer])}</strong></p>`}
              <p class="muted">${esc(item.explanation)}</p>
            </article>`;
        }).join("")}
      </div>
    </section>
  `;
}

function render() {
  clearEffects();
  const main = state.screen === "quiz" ? quizScreen() : state.screen === "result" ? resultScreen() : homeScreen();
  const titles = {
    home: "Эрудит — вопросы на эрудицию",
    quiz: `${modeTitle()} · вопрос ${state.index + 1} — Эрудит`,
    result: `Итог · ${modeTitle()} — Эрудит`
  };
  document.title = titles[state.screen];
  document.getElementById("app").innerHTML = `<div class="wrap" id="top">${header()}${`<main id="main">${main}</main>`}${state.screen === "quiz" ? "" : footer()}</div>`;
  window.scrollTo(0, 0);
  if (state.screen === "home") mountTicket();
  if (state.screen === "quiz") {
    setProgress(false);
    startTimer();
  }
  if (state.screen === "result") mountResult();
}

function mountTicket() {
  const root = document.getElementById("ticket");
  if (!root) return;
  const items = window.QUIZ_DATA.showcase;
  let index = 0;
  let markTimer = 0;
  let swapTimer = 0;
  const paint = () => {
    const item = items[index];
    root.innerHTML = ticketMarkup(item);
    clearTimeout(markTimer);
    const reveal = () => {
      root.querySelector(`[data-demo="${item.answer}"]`)?.classList.add("is-correct");
      const note = root.querySelector(".ticket-note");
      if (note) note.hidden = false;
    };
    if (reduceMotion) {
      reveal();
      return;
    }
    markTimer = setTimeout(reveal, 700);
  };
  paint();
  if (reduceMotion) return;
  const interval = setInterval(() => {
    root.querySelector(".ticket-body")?.classList.add("is-out");
    clearTimeout(swapTimer);
    swapTimer = setTimeout(() => {
      index = (index + 1) % items.length;
      paint();
    }, 260);
  }, 4600);
  cleanups.push(() => {
    clearInterval(interval);
    clearTimeout(markTimer);
    clearTimeout(swapTimer);
  });
}

function setProgress(answered) {
  const bar = document.getElementById("bar");
  if (!bar || !state.questions.length) return;
  const value = ((state.index + (answered ? 1 : 0)) / state.questions.length) * 100;
  bar.style.width = `${value}%`;
}

function startTimer() {
  stopTimer();
  const total = state.timeTotal;
  const end = Date.now() + total * 1000;
  const tick = () => {
    const left = Math.max(0, (end - Date.now()) / 1000);
    state.timeLeft = left;
    paintTimer(left, total);
    if (left <= 0) {
      stopTimer();
      timeoutAnswer();
    }
  };
  tick();
  timerId = window.setInterval(tick, 100);
}

function stopTimer() {
  clearInterval(timerId);
  timerId = 0;
}

function paintTimer(left, total) {
  const num = document.getElementById("time-num");
  const ring = document.getElementById("time-ring");
  const wrap = document.getElementById("timer");
  if (!num || !ring || !wrap) return;
  num.textContent = String(Math.ceil(left));
  const length = 2 * Math.PI * 18;
  const ratio = total === 0 ? 0 : left / total;
  ring.style.strokeDasharray = String(length);
  ring.style.strokeDashoffset = String(length * (1 - ratio));
  wrap.classList.toggle("is-urgent", left <= 5 && left > 0);
}

function paintHud() {
  const points = document.getElementById("points");
  const streak = document.getElementById("streak");
  if (points) points.textContent = format(state.points);
  if (streak) streak.textContent = String(state.streak);
}

function popPoints(amount) {
  const host = document.querySelector(".sheet");
  if (!host) return;
  const el = document.createElement("span");
  el.className = "points-pop";
  el.textContent = `+${amount}`;
  host.appendChild(el);
  window.setTimeout(() => el.remove(), 900);
}

function reveal(picked, ok, timedOut) {
  const q = current();
  document.querySelectorAll("#options .option").forEach((btn) => {
    const index = Number(btn.dataset.index);
    btn.disabled = true;
    if (index === q.answer) btn.classList.add("is-correct");
    else if (index === picked) btn.classList.add("is-wrong");
    else btn.classList.add("is-dim");
  });
  const verdict = document.getElementById("verdict");
  verdict.textContent = ok ? `Верно · +${state.answers[state.answers.length - 1].points}` : timedOut ? "Время вышло" : "Мимо";
  verdict.classList.toggle("ok", ok);
  verdict.classList.toggle("bad", !ok);
  document.getElementById("explain").hidden = false;
  document.getElementById("next-wrap").hidden = false;
  setProgress(true);
  paintHud();
  const status = document.getElementById("status");
  if (status) {
    status.textContent = ok
      ? `Верно. ${q.explanation}`
      : `Мимо. Верный ответ: ${q.options[q.answer]}. ${q.explanation}`;
  }
  if (!ok) {
    const sheet = document.querySelector(".sheet");
    sheet?.classList.remove("is-shake");
    void sheet?.offsetWidth;
    sheet?.classList.add("is-shake");
  }
}

function choose(index) {
  if (state.locked || state.screen !== "quiz") return;
  if (state.hidden.has(index)) return;
  const q = current();
  if (!q || index < 0 || index > 3) return;
  state.locked = true;
  stopTimer();
  const ok = index === q.answer;
  let gained = 0;
  if (ok) {
    state.streak += 1;
    state.bestStreak = Math.max(state.bestStreak, state.streak);
    const speed = Math.round((state.timeLeft / state.timeTotal) * 50);
    const bonus = state.streak >= 2 ? (state.streak - 1) * 10 : 0;
    gained = 100 + speed + bonus;
    state.points += gained;
    tone(523, 0, 0.12, "sine", 0.04);
    tone(784, 0.09, 0.16, "sine", 0.03);
    popPoints(gained);
  } else {
    state.streak = 0;
    tone(180, 0, 0.22, "triangle", 0.04);
  }
  state.answers.push(snapshot(q, index, false, gained));
  reveal(index, ok, false);
}

function timeoutAnswer() {
  if (state.locked || state.screen !== "quiz") return;
  state.locked = true;
  state.streak = 0;
  const q = current();
  state.answers.push(snapshot(q, null, true, 0));
  tone(160, 0, 0.24, "triangle", 0.035);
  reveal(null, false, true);
}

function snapshot(q, picked, timedOut, points) {
  return {
    question: q.question,
    options: q.options,
    answer: q.answer,
    explanation: q.explanation,
    picked,
    timedOut,
    points
  };
}

function useHint() {
  if (state.locked || state.hintUsed || state.screen !== "quiz") return;
  const q = current();
  const wrong = shuffle([0, 1, 2, 3].filter((index) => index !== q.answer));
  state.hintUsed = true;
  wrong.slice(0, 2).forEach((index) => state.hidden.add(index));
  document.querySelectorAll("#options .option").forEach((btn) => {
    if (state.hidden.has(Number(btn.dataset.index))) {
      btn.classList.add("is-out");
      btn.disabled = true;
    }
  });
  const hint = document.getElementById("hint");
  if (hint) {
    hint.disabled = true;
    hint.textContent = "Подсказка использована";
  }
  tone(440, 0, 0.08, "sine", 0.02);
}

function nextQuestion() {
  if (!state.locked) return;
  if (state.index + 1 >= state.questions.length) {
    finish();
    return;
  }
  state.index += 1;
  state.locked = false;
  state.hidden = new Set();
  render();
}

function finish() {
  state.correctCount = state.answers.filter((item) => item.picked === item.answer).length;
  const key = modeKey();
  const previous = bestOf(key);
  state.recordBroken = state.points > previous;
  if (state.recordBroken) store.best[key] = state.points;
  store.rounds += 1;
  if (state.mode === "daily" && (!store.daily || store.daily.date !== todayKey())) {
    store.daily = {
      date: todayKey(),
      correct: state.correctCount === 1,
      points: state.points
    };
  }
  saveStore();
  state.screen = "result";
  if (state.correctCount / state.questions.length >= 0.8) {
    tone(523, 0, 0.12, "sine", 0.04);
    tone(659, 0.1, 0.14, "sine", 0.035);
    tone(784, 0.2, 0.22, "sine", 0.03);
  }
  render();
}

function pickQuestions(mode, categoryId) {
  const bank = window.QUIZ_DATA.questions;
  if (mode === "daily") return [dailyQuestion()];
  if (mode === "marathon") {
    const picked = window.QUIZ_DATA.categories.flatMap((cat) => (
      shuffle(bank.filter((item) => item.category === cat.id)).slice(0, 2)
    ));
    return shuffle(picked);
  }
  const pool = shuffle(bank.filter((item) => !categoryId || item.category === categoryId));
  const size = mode === "blitz" ? 10 : 8;
  return pool.slice(0, size);
}

function start(mode, category) {
  state.screen = "quiz";
  state.mode = mode;
  state.category = category || null;
  state.questions = pickQuestions(mode, category);
  state.index = 0;
  state.points = 0;
  state.streak = 0;
  state.bestStreak = 0;
  state.answers = [];
  state.hintUsed = false;
  state.locked = false;
  state.hidden = new Set();
  state.timeTotal = mode === "blitz" ? 10 : mode === "daily" ? 30 : 20;
  state.timeLeft = state.timeTotal;
  state.correctCount = 0;
  state.recordBroken = false;
  render();
}

function goHome() {
  if (state.screen === "home") {
    window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
    return;
  }
  state.screen = "home";
  render();
}

function goHalls() {
  if (state.screen !== "home") {
    state.screen = "home";
    render();
  }
  document.getElementById("halls")?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
}

function mountResult() {
  const total = state.questions.length || 1;
  const percent = Math.round((state.correctCount / total) * 100);
  const node = document.getElementById("pct");
  const ring = document.getElementById("ring");
  if (reduceMotion) {
    if (node) node.textContent = String(percent);
    if (ring) ring.style.setProperty("--p", String(percent));
  } else {
    const start = performance.now();
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / 900);
      const eased = 1 - (1 - progress) ** 3;
      if (node) node.textContent = String(Math.round(percent * eased));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    requestAnimationFrame(() => ring?.style.setProperty("--p", String(percent)));
    if (percent >= 70) burst();
  }
}

function burst() {
  const canvas = document.getElementById("fx");
  const ctx = canvas.getContext("2d");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = window.innerWidth;
  const h = window.innerHeight;
  canvas.width = Math.floor(w * dpr);
  canvas.height = Math.floor(h * dpr);
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const colors = ["#f0c27a", "#f6f1e6", "#8ee0b8", "#ffb0a4", "#9ecbff"];
  const bits = Array.from({ length: 88 }, () => ({
    x: w / 2,
    y: h * 0.34,
    vx: (Math.random() - 0.5) * 14,
    vy: Math.random() * -12 - 4,
    g: 0.18 + Math.random() * 0.08,
    s: 4 + Math.random() * 4,
    c: colors[Math.floor(Math.random() * colors.length)],
    r: Math.random() * Math.PI,
    vr: (Math.random() - 0.5) * 0.2
  }));
  const started = performance.now();
  const frame = (now) => {
    const t = (now - started) / 1600;
    ctx.clearRect(0, 0, w, h);
    bits.forEach((bit) => {
      bit.vy += bit.g;
      bit.x += bit.vx;
      bit.y += bit.vy;
      bit.r += bit.vr;
      ctx.save();
      ctx.translate(bit.x, bit.y);
      ctx.rotate(bit.r);
      ctx.globalAlpha = Math.max(0, 1 - t);
      ctx.fillStyle = bit.c;
      ctx.fillRect(-bit.s / 2, -bit.s / 2, bit.s, bit.s * 0.62);
      ctx.restore();
    });
    if (t < 1) requestAnimationFrame(frame);
    else ctx.clearRect(0, 0, w, h);
  };
  requestAnimationFrame(frame);
}

function audio() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  if (!audioCtx) audioCtx = new Ctx();
  if (audioCtx.state === "suspended") audioCtx.resume();
  return audioCtx;
}

function tone(freq, when, dur, type, gain) {
  if (!store.sound) return;
  const ctx = audio();
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const amp = ctx.createGain();
  osc.type = type || "sine";
  osc.frequency.value = freq;
  const start = ctx.currentTime + when;
  amp.gain.setValueAtTime(gain || 0.03, start);
  amp.gain.exponentialRampToValueAtTime(0.0001, start + dur);
  osc.connect(amp);
  amp.connect(ctx.destination);
  osc.start(start);
  osc.stop(start + dur);
}

async function copyResult() {
  const text = `Эрудит · ${modeTitle()}: ${state.correctCount} из ${state.questions.length}, ${format(state.points)} очков.`;
  const button = document.querySelector("[data-action=copy]");
  try {
    await navigator.clipboard.writeText(text);
    if (button) {
      const previous = button.textContent;
      button.textContent = "Скопировано";
      window.setTimeout(() => {
        button.textContent = previous;
      }, 1400);
    }
  } catch (error) {
    if (button) button.textContent = text;
  }
}

function onClick(event) {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  if (target.tagName === "A") event.preventDefault();
  const action = target.dataset.action;
  if (action === "home") goHome();
  if (action === "halls") goHalls();
  if (action === "sound") {
    store.sound = !store.sound;
    saveStore();
    if (store.sound) {
      audio();
      tone(660, 0, 0.08, "sine", 0.03);
    }
    document.querySelectorAll("[data-action=sound]").forEach((btn) => {
      btn.classList.toggle("is-on", store.sound);
      btn.setAttribute("aria-pressed", store.sound ? "true" : "false");
      btn.setAttribute("aria-label", store.sound ? "Выключить звук" : "Включить звук");
      btn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 10h4l5-4v12l-5-4H4z"/>
          <path d="M16 9.5a3.5 3.5 0 0 1 0 5"/>
          ${store.sound ? "" : '<path d="M5 5l14 14"/>'}
        </svg>`;
    });
  }
  if (action === "play") start(target.dataset.mode, target.dataset.category || null);
  if (action === "pick") choose(Number(target.dataset.index));
  if (action === "hint") useHint();
  if (action === "next") nextQuestion();
  if (action === "again") start(state.mode, state.category);
  if (action === "copy") copyResult();
  if (action === "review") {
    const review = document.getElementById("review");
    if (!review) return;
    review.hidden = !review.hidden;
    target.setAttribute("aria-expanded", String(!review.hidden));
    if (!review.hidden) review.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
  }
  if (action === "filter") {
    document.querySelectorAll("[data-filter]").forEach((btn) => {
      btn.classList.toggle("is-on", btn === target);
    });
    document.querySelectorAll(".review-item").forEach((item) => {
      item.hidden = target.dataset.filter === "bad" && item.dataset.ok === "1";
    });
  }
}

function onKey(event) {
  if (event.repeat) return;
  if (event.key === "Enter" && state.screen === "home" && !event.target.closest("button, a")) {
    start("marathon");
    return;
  }
  if (state.screen !== "quiz") return;
  const map = { Digit1: 0, Digit2: 1, Digit3: 2, Digit4: 3, Numpad1: 0, Numpad2: 1, Numpad3: 2, Numpad4: 3 };
  if (!state.locked && map[event.code] != null) {
    event.preventDefault();
    choose(map[event.code]);
  }
  if ((event.key === "h" || event.key === "H" || event.key === "р" || event.key === "Р") && !state.locked) {
    useHint();
  }
  if (event.key === "Enter" && state.locked && !event.target.closest("[data-action=next]")) {
    event.preventDefault();
    nextQuestion();
  }
}

function initSky() {
  const canvas = document.getElementById("sky");
  const ctx = canvas.getContext("2d");
  let width = 0;
  let height = 0;
  let points = [];
  const resize = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.round(Math.min(64, Math.max(24, width / 28)));
    points = Array.from({ length: count }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.22,
      vy: (Math.random() - 0.5) * 0.22,
      r: Math.random() * 1.3 + 0.4
    }));
  };
  const draw = () => {
    ctx.clearRect(0, 0, width, height);
    points.forEach((point) => {
      point.x += point.vx;
      point.y += point.vy;
      if (point.x < 0 || point.x > width) point.vx *= -1;
      if (point.y < 0 || point.y > height) point.vy *= -1;
      ctx.beginPath();
      ctx.fillStyle = "rgba(240, 194, 122, 0.8)";
      ctx.arc(point.x, point.y, point.r, 0, Math.PI * 2);
      ctx.fill();
    });
    for (let i = 0; i < points.length; i += 1) {
      for (let j = i + 1; j < points.length; j += 1) {
        const a = points[i];
        const b = points[j];
        const dist = Math.hypot(a.x - b.x, a.y - b.y);
        if (dist < 130) {
          ctx.strokeStyle = `rgba(186, 214, 224, ${(1 - dist / 130) * 0.28})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }
  };
  resize();
  draw();
  window.addEventListener("resize", () => {
    resize();
    draw();
  });
  if (reduceMotion) return;
  const loop = () => {
    if (!document.hidden) draw();
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}

function init() {
  if (!window.QUIZ_DATA) {
    document.getElementById("app").textContent = "Архив вопросов не загрузился.";
    return;
  }
  initSky();
  window.addEventListener("pointermove", (event) => {
    document.documentElement.style.setProperty("--mx", `${event.clientX}px`);
    document.documentElement.style.setProperty("--my", `${event.clientY}px`);
  }, { passive: true });
  document.addEventListener("click", onClick);
  document.addEventListener("keydown", onKey);
  render();
}

init();
