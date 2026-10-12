(() => {
  'use strict';

  const tg = window.Telegram && window.Telegram.WebApp;
  const $ = (s) => document.querySelector(s);

  const WD = ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba'];
  const WDS = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'];
  const MON = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'];
  const MONS = ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'];
  const GROUPS = [['Ertalab', 0, 12], ['Kunduzi', 12, 17], ['Kechqurun', 17, 24]];

  const ICON = {
    any: '<svg viewBox="0 0 24 24"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7z"/></svg>',
    phone: '<svg viewBox="0 0 24 24"><path d="M6.6 3.5h2.6l1.4 4-2 1.4a12 12 0 006.5 6.5l1.4-2 4 1.4v2.6a2 2 0 01-2.2 2A17 17 0 014.6 5.7a2 2 0 012-2.2z"/></svg>',
    send: '<svg viewBox="0 0 24 24"><path d="M21 3L10 14"/><path d="M21 3l-7 18-4-7-7-4z"/></svg>',
    x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    lock: '<svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/></svg>',
    check: '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    arrow: '<svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  };

  const S = {
    boot: null, sched: null,
    barber: 0, date: null, time: null,
    tab: 'book', busy: false,
    staff: { date: null, barber: null, data: null },
  };

  // ---------- helpers ----------
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const ver = (v) => !!(tg && tg.isVersionAtLeast && tg.isVersionAtLeast(v));

  function haptic(type) {
    try {
      const h = tg && tg.HapticFeedback;
      if (!h || !ver('6.1')) return;
      if (type === 'select') h.selectionChanged();
      else if (type === 'success' || type === 'error' || type === 'warning') h.notificationOccurred(type);
      else h.impactOccurred(type || 'light');
    } catch (e) { /* ignore */ }
  }

  let toastTimer;
  function toast(msg) {
    const el = $('#toast');
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 2800);
  }

  function confirmBox(msg) {
    return new Promise((res) => {
      if (ver('6.2')) tg.showConfirm(msg, (ok) => res(!!ok));
      else res(window.confirm(msg));
    });
  }

  async function api(path, body) {
    const opt = { method: body ? 'POST' : 'GET', headers: { 'X-Init-Data': (tg && tg.initData) || '' } };
    if (body) {
      opt.headers['Content-Type'] = 'application/json';
      opt.body = JSON.stringify(body);
    }
    let r;
    try { r = await fetch(path, opt); } catch (e) { throw new Error("Internet aloqasini tekshiring"); }
    let j = {};
    try { j = await r.json(); } catch (e) { /* ignore */ }
    if (!r.ok) {
      const err = new Error(j.error || 'Xatolik yuz berdi');
      err.status = r.status;
      throw err;
    }
    return j;
  }

  function parse(iso) {
    const [y, m, d] = iso.split('-').map(Number);
    return { y, m, d, wd: (new Date(y, m - 1, d).getDay() + 6) % 7 };
  }
  function dayDiff(iso) {
    const a = parse(iso), b = parse(S.sched.today);
    return Math.round((Date.UTC(a.y, a.m - 1, a.d) - Date.UTC(b.y, b.m - 1, b.d)) / 864e5);
  }
  function rel(iso) {
    const diff = dayDiff(iso);
    return diff === 0 ? 'Bugun' : diff === 1 ? 'Ertaga' : null;
  }
  function longDate(iso) {
    const p = parse(iso);
    return `${rel(iso) || WD[p.wd]}, ${p.d}-${MON[p.m - 1]}`;
  }
  function shortDate(iso) {
    const p = parse(iso);
    return rel(iso) || `${WDS[p.wd]}, ${p.d}-${MONS[p.m - 1]}`;
  }
  function initials(name) {
    const w = String(name).trim().split(/\s+/);
    return ((w[0] || '')[0] || '').toUpperCase() + ((w[1] || '')[0] || '').toUpperCase();
  }

  // ---------- phone ----------
  function phoneDigits(v) {
    let d = String(v || '').replace(/\D/g, '');
    if (d.length === 9) d = '998' + d;
    return d;
  }
  function validPhone(v) {
    const d = phoneDigits(v);
    if (d.startsWith('998')) return d.length === 12;
    return d.length >= 10 && d.length <= 15;
  }
  function fmtPhone(v) {
    const raw = String(v || '');
    let d = raw.replace(/\D/g, '');
    if (!d) return raw.trim().startsWith('+') ? '+' : '';
    if (d.startsWith('998')) {
      d = d.slice(0, 12);
      return '+' + [d.slice(0, 3), d.slice(3, 5), d.slice(5, 8), d.slice(8, 10), d.slice(10, 12)].filter(Boolean).join(' ');
    }
    if (!raw.trim().startsWith('+') && d.length <= 9) {
      return [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean).join(' ');
    }
    return '+' + d.slice(0, 15);
  }

  // ---------- theme ----------
  // Dizayn doim yorug': Telegram tungi rejimida ham oq fon
  function applyTheme() {
    const bg = '#f4f2ee';
    try {
      if (ver('6.9')) { tg.setHeaderColor(bg); tg.setBackgroundColor(bg); }
      if (ver('7.10')) tg.setBottomBarColor(bg);
    } catch (e) { /* ignore */ }
  }

  // ---------- data ----------
  const slotsOf = (bid, date) => ((S.sched.slots[String(bid)] || {})[date]) || [];
  const freeCount = (bid, date) => slotsOf(bid, date).filter((s) => s[1] === 'f').length;
  function nearest(bid) {
    for (const d of S.sched.days) {
      if (d.closed) continue;
      const s = slotsOf(bid, d.date).find((x) => x[1] === 'f');
      if (s) return { date: d.date, time: s[0] };
    }
    return null;
  }

  async function loadSchedule() {
    S.sched = await api('/api/schedule');
  }

  // ---------- booking view ----------
  function renderBook() {
    renderMine();
    if (!S.boot.active) {
      renderBarbers();
      ensureDate();
      renderDays();
      renderSlots();
    }
    updateCta();
  }

  function renderMine() {
    const a = S.boot.active;
    $('#mine').hidden = !a;
    $('#form').hidden = !!a;
    if (!a) return;
    $('#mine').innerHTML = `
      <div class="ticket">
        <div class="t-top">
          <div class="t-label"><i></i>Sizning navbatingiz</div>
          <div class="t-time">${esc(a.time)}</div>
          <div class="t-date">${esc(longDate(a.date))}</div>
        </div>
        <div class="t-cut"></div>
        <div class="t-bottom">
          <div class="t-row"><span>Usta</span><b>${esc(a.barber_name)}</b></div>
          <div class="t-row"><span>Ism</span><b>${esc(a.name || '')}</b></div>
          <div class="t-row"><span>Telefon</span><b>${esc(fmtPhone(a.phone))}</b></div>
          <button class="btn ghost" id="cancel-mine">Navbatni bekor qilish</button>
        </div>
      </div>
      <p class="note center">Bir vaqtda bitta navbat olish mumkin.<br>Boshqa vaqtga yozilish uchun avval shu navbatni bekor qiling.</p>`;
  }

  function renderBarbers() {
    const opts = [{ id: 0, name: "Farqi yo'q", any: true }].concat(S.boot.barbers);
    $('#barbers').innerHTML = opts.map((o) => {
      const n = nearest(o.id);
      const sub = n ? `${shortDate(n.date)} ${n.time}` : "Joy yo'q";
      return `<button class="barber ${o.id === S.barber ? 'on' : ''}" data-id="${o.id}">
        <span class="tick">${ICON.check}</span>
        <span class="av">${o.any ? ICON.any : esc(initials(o.name))}</span>
        <span class="bn">${esc(o.name)}</span>
        <span class="bs">${n ? '<i></i>' : ''}${esc(sub)}</span>
      </button>`;
    }).join('');
  }

  function ensureDate() {
    const days = S.sched.days;
    const ok = (iso) => days.some((d) => d.date === iso && !d.closed && freeCount(S.barber, iso) > 0);
    if (S.date && ok(S.date)) return;
    const first = days.find((d) => ok(d.date));
    S.date = first ? first.date : days[0].date;
    S.time = null;
  }

  function dayChips(days, selected, countFn, mode) {
    return days.map((d) => {
      const p = parse(d.date);
      const c = d.closed ? 0 : countFn(d.date);
      const off = d.closed || (mode === 'book' && c === 0);
      let bottom;
      if (d.closed) bottom = 'Dam';
      else if (mode === 'book') bottom = c ? `${c} bo'sh` : "To'la";
      else bottom = c ? `${c} ta` : '—';
      return `<button class="day ${d.date === selected ? 'on' : ''} ${off ? 'off' : ''}" data-date="${d.date}" ${off && mode === 'book' ? 'disabled' : ''}>
        <span class="dw">${rel(d.date) || WDS[p.wd]}</span>
        <span class="dd">${p.d}</span>
        <span class="dc">${bottom}</span>
      </button>`;
    }).join('');
  }

  function renderDays() {
    $('#days').innerHTML = dayChips(S.sched.days, S.date, (iso) => freeCount(S.barber, iso), 'book');
    $('#day-note').textContent = S.date ? longDate(S.date) : '';
    const on = $('#days .day.on');
    if (on) on.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  function renderSlots() {
    const list = slotsOf(S.barber, S.date).filter((s) => s[1] !== 'p');
    $('#dur-note').textContent = `~${S.boot.slot_minutes} daqiqa`;
    if (S.time && !list.some((s) => s[0] === S.time && s[1] === 'f')) S.time = null;

    if (!list.some((s) => s[1] === 'f')) {
      const n = nearest(S.barber);
      $('#slots').innerHTML = `<div class="empty">Bu kunda bo'sh vaqt qolmadi.${n
        ? `<br>Eng yaqin bo'sh vaqt: <button class="link" data-jump="${n.date}|${n.time}">${esc(shortDate(n.date))}, ${n.time}</button>`
        : '<br>Boshqa ustani tanlab ko\'ring.'}</div>`;
      return;
    }
    $('#slots').innerHTML = GROUPS.map(([title, from, to]) => {
      const items = list.filter((s) => { const h = +s[0].slice(0, 2); return h >= from && h < to; });
      if (!items.length) return '';
      return `<div class="sg"><div class="sg-t">${title}</div><div class="grid">${items.map(([t, st]) =>
        `<button class="slot ${t === S.time ? 'on' : ''}" data-time="${t}" ${st !== 'f' ? 'disabled' : ''}>${t}</button>`
      ).join('')}</div></div>`;
    }).join('') + `<div class="legend"><span><i></i>Bo'sh</span><span><i class="b"></i>Band</span><span><i class="s"></i>Tanlangan</span></div>`;
  }

  function updateCta() {
    const show = S.tab === 'book' && !S.boot.active;
    $('#cta').hidden = !show;
    if (!show) return;
    const b = $('#book-btn');
    if (!S.time) {
      b.disabled = true;
      b.textContent = 'Kun va vaqtni tanlang';
      return;
    }
    b.disabled = false;
    const who = S.barber ? (S.boot.barbers.find((x) => x.id === S.barber) || {}).name : "Bo'sh usta";
    b.innerHTML = `<span class="c-txt"><small>${esc(who)}</small><b>${esc(shortDate(S.date))}, ${S.time}</b></span>
      <span class="c-go"><span class="c-lbl">Yozilish</span>${ICON.arrow}</span>`;
  }

  function renderContact() {
    const u = S.boot.user;
    const tgEl = $('#tg-user');
    if (u.username) { tgEl.textContent = '@' + u.username; tgEl.classList.remove('none'); }
    else { tgEl.textContent = "Username yo'q"; tgEl.classList.add('none'); }
    if (!$('#name').value) $('#name').value = u.first_name || '';
    if (u.phone && !$('#phone').value) $('#phone').value = fmtPhone(u.phone);
    updateShareBtn();
  }

  function updateShareBtn() {
    const btn = $('#share');
    const ok = validPhone($('#phone').value);
    const canShare = ver('6.9');
    if (ok) {
      btn.hidden = false;
      btn.className = 'chip-btn ok';
      btn.innerHTML = ICON.check + 'Tayyor';
    } else if (canShare) {
      btn.hidden = false;
      btn.className = 'chip-btn';
      btn.innerHTML = ICON.phone + 'Ulashish';
    } else {
      btn.hidden = true;
    }
  }

  function setPhone(p) {
    p = String(p);
    if (!p.startsWith('+')) p = '+' + p;
    $('#phone').value = fmtPhone(p);
    S.boot.user.phone = p;
    updateShareBtn();
    haptic('success');
  }

  function sharePhone() {
    if (validPhone($('#phone').value)) { $('#phone').focus(); return; }
    if (!ver('6.9')) { $('#phone').focus(); return; }
    tg.requestContact(async (ok, res) => {
      if (!ok) { toast("Raqamni qo'lda kiriting"); $('#phone').focus(); return; }
      const c = res && res.responseUnsafe && res.responseUnsafe.contact;
      if (c && c.phone_number) { setPhone(c.phone_number); return; }
      // Raqam botga keladi — server saqlaguncha biroz kutamiz
      for (let i = 0; i < 8; i++) {
        await sleep(700);
        try {
          const b = await api('/api/bootstrap');
          if (b.user.phone) { setPhone(b.user.phone); return; }
        } catch (e) { /* ignore */ }
      }
      toast("Raqamni qo'lda kiriting");
    });
  }

  function flagField(sel, msg) {
    const el = $(sel);
    el.classList.remove('shake');
    void el.offsetWidth;
    el.classList.add('shake');
    setTimeout(() => el.classList.remove('shake'), 500);
    toast(msg);
    haptic('error');
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  async function book() {
    if (S.busy || !S.time) return;
    const name = $('#name').value.trim();
    const phone = $('#phone').value;
    if (!name) { flagField('#contact .card', 'Ismingizni kiriting'); $('#name').focus(); return; }
    if (!validPhone(phone)) { flagField('#phone-field', 'Telefon raqamingizni kiriting'); $('#phone').focus(); return; }

    S.busy = true;
    const btn = $('#book-btn');
    btn.classList.add('loading');
    const lbl = btn.querySelector('.c-lbl');
    if (lbl) lbl.textContent = 'Yozilmoqda';
    try {
      const r = await api('/api/book', { barber_id: S.barber, date: S.date, time: S.time, name, phone });
      haptic('success');
      S.boot.active = r.booking;
      S.boot.user.phone = r.booking.phone;
      S.time = null;
      showDone(r.booking);
      loadSchedule().catch(() => {});
    } catch (e) {
      haptic('error');
      toast(e.message);
      if (e.status === 409) {
        S.time = null;
        try { await loadSchedule(); } catch (x) { /* ignore */ }
        if (/faol navbat/.test(e.message)) await reloadBoot();
      }
    } finally {
      S.busy = false;
      btn.classList.remove('loading');
      renderBook();
    }
  }

  function showDone(bk) {
    $('#done-sub').textContent = `Sizni kutamiz! Vaqtdan ${S.boot.remind_minutes} daqiqa oldin botda eslatma yuboramiz.`;
    $('#done-ticket').innerHTML = `
      <div class="t-row"><span>Usta</span><b>${esc(bk.barber_name)}</b></div>
      <div class="t-row"><span>Kun</span><b>${esc(longDate(bk.date))}</b></div>
      <div class="t-row"><span>Vaqt</span><b>${esc(bk.time)}</b></div>`;
    $('#done').hidden = false;
  }

  async function cancelMine() {
    const a = S.boot.active;
    if (!a) return;
    if (!(await confirmBox(`${shortDate(a.date)}, ${a.time} dagi navbatni bekor qilasizmi?`))) return;
    try {
      await api('/api/cancel', { id: a.id });
      haptic('success');
      toast('Navbat bekor qilindi');
      S.boot.active = null;
      await loadSchedule();
      renderBook();
    } catch (e) {
      toast(e.message);
      await reloadBoot();
    }
  }

  async function reloadBoot() {
    try { S.boot = await api('/api/bootstrap'); renderBook(); } catch (e) { /* ignore */ }
  }

  // ---------- staff view ----------
  async function loadStaff() {
    const q = S.staff.date ? `?date=${S.staff.date}` : '';
    S.staff.data = await api('/api/staff/day' + q);
    S.staff.date = S.staff.data.date;
    if (!S.staff.barber || !S.staff.data.barbers.some((b) => b.id === S.staff.barber)) {
      S.staff.barber = S.staff.data.barbers[0] && S.staff.data.barbers[0].id;
    }
    renderStaff();
  }

  function renderStaff() {
    const data = S.staff.data;
    if (!data) return;
    $('#s-days').innerHTML = dayChips(data.days, data.date, (iso) => data.counts[iso] || 0, 'staff');
    $('#s-barbers').innerHTML = data.barbers.map((b) => {
      const n = b.slots.filter((s) => s.booking && s.booking.kind === 'client').length;
      return `<button data-id="${b.id}" class="${b.id === S.staff.barber ? 'on' : ''}">${esc(b.name)} · ${n}</button>`;
    }).join('');

    const barber = data.barbers.find((b) => b.id === S.staff.barber);
    if (!barber) { $('#s-list').innerHTML = ''; return; }
    const clients = barber.slots.filter((s) => s.booking && s.booking.kind === 'client').length;
    const free = barber.slots.filter((s) => !s.booking && !s.past).length;
    $('#s-stats').innerHTML = `
      <div class="stat dark"><b>${clients}</b><span>navbat</span></div>
      <div class="stat"><b>${free}</b><span>bo'sh vaqt</span></div>`;

    const rows = barber.slots.filter((s) => s.booking || !s.past);
    if (!rows.length) {
      $('#s-list').innerHTML = `<div class="empty">${data.days.find((d) => d.date === data.date && d.closed) ? 'Dam olish kuni' : 'Bu kunda bo\'sh vaqt qolmadi'}</div>`;
      return;
    }
    $('#s-list').innerHTML = rows.map((s) => {
      const b = s.booking;
      const past = s.past ? 'past' : '';
      if (!b) {
        return `<div class="srow free ${past}">
          <div class="st">${s.time}</div>
          <div class="sb"><div class="sn">Bo'sh</div></div>
          <button class="add-btn" data-act="block" data-time="${s.time}">Band qilish</button>
        </div>`;
      }
      if (b.kind === 'blocked') {
        return `<div class="srow blocked ${past}">
          <div class="st">${s.time}</div>
          <div class="sb"><div class="sn">${ICON.lock}Band qilingan</div><div class="sm">Joyida mijoz</div></div>
          <button class="ib" data-act="unblock" data-id="${b.id}" aria-label="Ochish">${ICON.x}</button>
        </div>`;
      }
      const meta = [b.username ? '@' + b.username : '', b.phone ? fmtPhone(b.phone) : ''].filter(Boolean).join(' · ');
      return `<div class="srow booked ${past}">
        <div class="st">${s.time}</div>
        <div class="sb"><div class="sn">${esc(b.name || 'Mijoz')}</div><div class="sm">${esc(meta)}</div></div>
        <div class="acts">
          ${b.phone ? `<a class="ib solid" href="tel:${esc(b.phone)}" aria-label="Qo'ng'iroq">${ICON.phone}</a>` : ''}
          ${b.username ? `<button class="ib" data-act="write" data-u="${esc(b.username)}" aria-label="Yozish">${ICON.send}</button>` : ''}
          <button class="ib" data-act="cancel" data-id="${b.id}" data-label="${esc((b.name || 'Mijoz') + ', ' + s.time)}" aria-label="Bekor qilish">${ICON.x}</button>
        </div>
      </div>`;
    }).join('');
  }

  async function staffAction(btn) {
    const act = btn.dataset.act;
    try {
      if (act === 'write') {
        const url = 'https://t.me/' + btn.dataset.u;
        if (ver('6.1')) tg.openTelegramLink(url); else window.open(url, '_blank');
        return;
      }
      if (act === 'block') {
        await api('/api/staff/block', { barber_id: S.staff.barber, date: S.staff.date, time: btn.dataset.time });
        toast(`${btn.dataset.time} band qilindi`);
      } else if (act === 'unblock') {
        await api('/api/cancel', { id: +btn.dataset.id });
        toast("Vaqt bo'shatildi");
      } else if (act === 'cancel') {
        if (!(await confirmBox(`${btn.dataset.label} — navbatni bekor qilasizmi? Mijozga xabar boradi.`))) return;
        await api('/api/cancel', { id: +btn.dataset.id });
        toast('Navbat bekor qilindi');
      }
      haptic('success');
    } catch (e) {
      haptic('error');
      toast(e.message);
    }
    await loadStaff().catch(() => {});
  }

  function setTab(tab) {
    S.tab = tab;
    document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === tab));
    $('#view-book').hidden = tab !== 'book';
    $('#view-staff').hidden = tab !== 'staff';
    updateCta();
    window.scrollTo(0, 0);
    if (tab === 'staff') loadStaff().catch((e) => toast(e.message));
    else loadSchedule().then(renderBook).catch(() => {});
  }

  // ---------- events ----------
  function bind() {
    $('#barbers').addEventListener('click', (e) => {
      const b = e.target.closest('.barber');
      if (!b) return;
      const id = +b.dataset.id;
      if (id === S.barber) return;
      S.barber = id;
      haptic('select');
      renderBook();
    });
    $('#days').addEventListener('click', (e) => {
      const d = e.target.closest('.day');
      if (!d || d.disabled || d.dataset.date === S.date) return;
      S.date = d.dataset.date;
      S.time = null;
      haptic('select');
      renderDays(); renderSlots(); updateCta();
    });
    $('#slots').addEventListener('click', (e) => {
      const jump = e.target.closest('[data-jump]');
      if (jump) {
        const [d, t] = jump.dataset.jump.split('|');
        S.date = d; S.time = t;
        haptic('select');
        renderDays(); renderSlots(); updateCta();
        return;
      }
      const s = e.target.closest('.slot');
      if (!s || s.disabled) return;
      const first = !S.time;
      S.time = s.dataset.time === S.time ? null : s.dataset.time;
      haptic('select');
      renderSlots(); updateCta();
      if (first && S.time && !validPhone($('#phone').value)) {
        setTimeout(() => $('#contact').scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);
      }
    });
    $('#phone').addEventListener('input', (e) => {
      const el = e.target;
      const atEnd = el.selectionStart === el.value.length;
      const f = fmtPhone(el.value);
      if (f !== el.value && atEnd) el.value = f;
      updateShareBtn();
    });
    $('#phone').addEventListener('blur', (e) => { e.target.value = fmtPhone(e.target.value); updateShareBtn(); });
    $('#share').addEventListener('click', sharePhone);
    $('#book-btn').addEventListener('click', book);
    $('#mine').addEventListener('click', (e) => { if (e.target.closest('#cancel-mine')) cancelMine(); });
    $('#done-ok').addEventListener('click', () => { $('#done').hidden = true; renderBook(); window.scrollTo(0, 0); });
    $('#tabs').addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (b && b.dataset.tab !== S.tab) { haptic('select'); setTab(b.dataset.tab); }
    });
    $('#s-days').addEventListener('click', (e) => {
      const d = e.target.closest('.day');
      if (!d) return;
      S.staff.date = d.dataset.date;
      haptic('select');
      loadStaff().catch((x) => toast(x.message));
    });
    $('#s-barbers').addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      S.staff.barber = +b.dataset.id;
      haptic('select');
      renderStaff();
    });
    $('#s-list').addEventListener('click', (e) => {
      const b = e.target.closest('[data-act]');
      if (b) staffAction(b);
    });

    setInterval(() => {
      if (document.hidden || S.busy || !$('#done').hidden) return;
      if (S.tab === 'book') loadSchedule().then(() => { if (S.tab === 'book') renderBook(); }).catch(() => {});
      else loadStaff().catch(() => {});
    }, 30000);
  }

  // ---------- start ----------
  async function showGate() {
    $('#loader').hidden = true;
    $('#gate').hidden = false;
    try {
      const p = await api('/api/public');
      if (p.bot_username) $('#gate-link').href = 'https://t.me/' + p.bot_username;
    } catch (e) { /* ignore */ }
  }

  async function start() {
    if (!tg || !tg.initData) { showGate(); return; }
    tg.ready();
    tg.expand();
    if (ver('7.7')) tg.disableVerticalSwipes();
    applyTheme();

    try {
      const [boot, sched] = await Promise.all([api('/api/bootstrap'), api('/api/schedule')]);
      S.boot = boot;
      S.sched = sched;
    } catch (e) {
      $('#loader').hidden = true;
      if (e.status === 401) { showGate(); toast(e.message); return; }
      $('#gate').hidden = false;
      $('#gate h2').textContent = 'Xatolik';
      $('#gate p').textContent = e.message;
      $('#gate-link').textContent = 'Qayta urinish';
      $('#gate-link').onclick = (ev) => { ev.preventDefault(); location.reload(); };
      return;
    }

    $('#shop-name').textContent = S.boot.shop;
    if (S.boot.status) {
      $('#status').classList.toggle('open', !!S.boot.status.open);
      $('#status span').textContent = S.boot.status.text;
    }
    $('#tabs').hidden = !S.boot.is_staff;
    bind();
    renderContact();
    renderBook();
    $('#loader').hidden = true;
    $('#app').hidden = false;
  }

  start();
})();
