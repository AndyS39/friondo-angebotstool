/* Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 106) – Kundenkartei.
   Vanilla JS, kein Framework: Reiter (Tabs mit Tastatur), Timeline-Suche und
   Typ-Filter, E-Mail-Filter (Herkunft/Richtung), MFH-Zusatzfelder, Dirty-
   Markierung + Speichern-Leiste der Stammdaten, Auto-Submit der Zuweisungs-
   Dropdowns, fetch-Formulare mit Neuladen (Notiz, To-Do), Merken der
   rechten Bereiche je Browser (localStorage, nur Komfort). */
(function () {
    'use strict';

    function $(sel, wurzel) { return (wurzel || document).querySelector(sel); }
    function $$(sel, wurzel) { return Array.prototype.slice.call((wurzel || document).querySelectorAll(sel)); }

    /* ---------- Reiter ---------- */
    var tabs = $$('.lk-tab');
    var panels = $$('.lk-panel');
    var gueltig = tabs.map(function (t) { return t.dataset.tab; });

    function tabZeigen(key, fokus) {
        if (gueltig.indexOf(key) < 0) { return; }
        tabs.forEach(function (t) {
            var aktiv = t.dataset.tab === key;
            t.setAttribute('aria-selected', aktiv ? 'true' : 'false');
            t.setAttribute('tabindex', aktiv ? '0' : '-1');
            if (aktiv && fokus) { t.focus(); }
        });
        panels.forEach(function (p) { p.hidden = p.id !== 'panel-' + key; });
        var form = $('#lk-stammdaten input[name=tab]');
        if (form) { form.value = key; }
        $$('input[name=tab]').forEach(function (i) { i.value = key; });
        try {
            if (history.replaceState) {
                history.replaceState(null, '', location.pathname + location.search.replace(/([?&])tab=[^&]*/, '$1').replace(/[?&]$/, '') + '#tab-' + key);
            }
        } catch (e) { /* egal */ }
    }

    tabs.forEach(function (t, i) {
        t.addEventListener('click', function () { tabZeigen(t.dataset.tab, false); });
        t.addEventListener('keydown', function (ev) {
            var ziel = null;
            if (ev.key === 'ArrowRight') { ziel = tabs[(i + 1) % tabs.length]; }
            if (ev.key === 'ArrowLeft') { ziel = tabs[(i - 1 + tabs.length) % tabs.length]; }
            if (ev.key === 'Home') { ziel = tabs[0]; }
            if (ev.key === 'End') { ziel = tabs[tabs.length - 1]; }
            if (ziel) { ev.preventDefault(); tabZeigen(ziel.dataset.tab, true); }
        });
    });
    $$('[data-tab-link]').forEach(function (k) {
        k.addEventListener('click', function () {
            tabZeigen(k.dataset.tabLink, true);
            var mitte = $('.lk-mitte');
            if (mitte && mitte.scrollIntoView) { mitte.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
        });
    });
    if (location.hash && location.hash.indexOf('#tab-') === 0) {
        tabZeigen(location.hash.substring(5), false);
    }

    /* ---------- Timeline: Suche + Filter ---------- */
    var tlSuche = $('#lk-tl-suche');
    var tlFilter = $$('#lk-tl-filter input');
    var tlZahl = $('#lk-tl-zahl');
    function timelineFiltern() {
        var q = (tlSuche ? tlSuche.value : '').trim().toLowerCase();
        var aktiv = {};
        tlFilter.forEach(function (c) { aktiv[c.value] = c.checked; });
        var karten = $$('#lk-timeline .lk-karte');
        var sichtbar = 0;
        karten.forEach(function (k) {
            var ok = (aktiv[k.dataset.typ] !== false) && (!q || (k.dataset.text || '').indexOf(q) >= 0);
            k.hidden = !ok;
            if (ok) { sichtbar += 1; }
        });
        if (tlZahl) { tlZahl.textContent = sichtbar + ' von ' + karten.length + ' Einträgen'; }
        var leer = $('#lk-timeline .lk-leer-filter');
        if (leer) { leer.hidden = !(karten.length && !sichtbar); }
    }
    if (tlSuche) { tlSuche.addEventListener('input', timelineFiltern); }
    tlFilter.forEach(function (c) { c.addEventListener('change', timelineFiltern); });

    /* ---------- E-Mail-Verlauf: Herkunft + Richtung ---------- */
    var mailHerkunft = '';
    var mailRichtung = '';
    function mailsFiltern() {
        var karten = $$('#lk-mails .lk-mail');
        var sichtbar = 0;
        karten.forEach(function (k) {
            var ok = (!mailHerkunft || k.dataset.herkunft === mailHerkunft)
                && (!mailRichtung || k.dataset.richtung === mailRichtung);
            k.hidden = !ok;
            if (ok) { sichtbar += 1; }
        });
        var leer = $('#lk-mails .lk-leer-filter');
        if (leer) { leer.hidden = !(karten.length && !sichtbar); }
    }
    function chipGruppe(id, setzen) {
        var gruppe = $('#' + id);
        if (!gruppe) { return; }
        $$('.lk-chip', gruppe).forEach(function (chip) {
            chip.addEventListener('click', function () {
                $$('.lk-chip', gruppe).forEach(function (c) {
                    c.classList.remove('aktiv');
                    c.setAttribute('aria-pressed', 'false');
                });
                chip.classList.add('aktiv');
                chip.setAttribute('aria-pressed', 'true');
                setzen(chip.dataset.wert || '');
                mailsFiltern();
            });
        });
    }
    chipGruppe('lk-mail-herkunft', function (w) { mailHerkunft = w; });
    chipGruppe('lk-mail-richtung', function (w) { mailRichtung = w; });

    /* ---------- Stammdaten: MFH-Felder, Dirty-Markierung ---------- */
    var objektart = $('#lk-objektart');
    var mfh = $('#lk-mfh');
    function mfhUmschalten() {
        if (!objektart || !mfh) { return; }
        var opt = objektart.options[objektart.selectedIndex];
        mfh.hidden = !(opt && opt.dataset.parteien === '1');
    }
    if (objektart) { objektart.addEventListener('change', mfhUmschalten); mfhUmschalten(); }

    var stammdaten = $('#lk-stammdaten');
    if (stammdaten) {
        var dirty = $('.lk-dirty', stammdaten);
        var leiste = $('.lk-speichern', stammdaten);
        var markieren = function () {
            if (dirty) { dirty.hidden = false; }
            if (leiste) { leiste.classList.add('aktiv'); }
            stammdaten.dataset.dirty = '1';
        };
        $$('input, select, textarea', stammdaten).forEach(function (f) {
            f.addEventListener('change', markieren);
            if (f.tagName === 'INPUT' && (f.type === 'text' || f.type === 'tel' || f.type === 'email' || f.type === 'number')) {
                f.addEventListener('input', markieren);
            }
        });
        stammdaten.addEventListener('submit', function () { stammdaten.dataset.dirty = ''; });
        window.addEventListener('beforeunload', function (ev) {
            if (stammdaten.dataset.dirty === '1') { ev.preventDefault(); ev.returnValue = ''; }
        });
    }

    /* ---------- Auto-Submit (Innendienst/Außendienst) ---------- */
    $$('select[data-autosubmit]').forEach(function (s) {
        s.addEventListener('change', function () {
            if (stammdaten) { stammdaten.dataset.dirty = ''; }
            s.form.submit();
        });
    });

    /* ---------- fetch-Formulare: absenden, dann Kartei neu laden ---------- */
    $$('form[data-fetch="reload"]').forEach(function (form) {
        form.addEventListener('submit', function (ev) {
            if (!window.fetch || !window.FormData) { return; }
            ev.preventDefault();
            var knopf = $('button[type=submit]', form);
            if (knopf) { knopf.disabled = true; }
            fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin', redirect: 'follow' })
                .then(function () {
                    if (stammdaten) { stammdaten.dataset.dirty = ''; }
                    location.reload();
                })
                .catch(function () { if (knopf) { knopf.disabled = false; } form.submit(); });
        });
    });

    /* ---------- Rechte Bereiche merken (nur Komfort je Browser) ---------- */
    $$('.lk-bereich[data-bereich]').forEach(function (d) {
        var key = 'lk-bereich-' + d.dataset.bereich;
        try {
            var wert = localStorage.getItem(key);
            if (wert === 'zu') { d.open = false; }
            if (wert === 'auf') { d.open = true; }
        } catch (e) { /* privat/gesperrt */ }
        d.addEventListener('toggle', function () {
            try { localStorage.setItem(key, d.open ? 'auf' : 'zu'); } catch (e) { /* egal */ }
        });
    });

    /* ---------- Tasten 1–7 wie in der Anrufliste (C1; Dialoge aus Phase 107) ---------- */
    var anruf = $('.lk-anruf');
    if (anruf) {
        var tasten = { '1': 'erreicht', '3': 'besetzt', '4': 'mailbox', '6': 'falsche_nummer' };
        var dialoge = { '2': 'nichterreicht', '5': 'rueckruf', '7': 'keininteresse' };
        document.addEventListener('keydown', function (ev) {
            if (ev.ctrlKey || ev.altKey || ev.metaKey) { return; }
            var ziel = ev.target;
            var tag = ziel && ziel.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (ziel && ziel.isContentEditable)) { return; }
            if (document.querySelector('dialog[open]')) { return; }
            if (tasten[ev.key]) {
                var knopf = $('button[name=ergebnis][value="' + tasten[ev.key] + '"]', anruf);
                if (knopf && !knopf.disabled) { ev.preventDefault(); knopf.click(); }
            } else if (dialoge[ev.key] && typeof window.dialogOeffnen === 'function') {
                if (ev.key === '2' && anruf.dataset.gesperrt === '1') { return; }
                ev.preventDefault();
                window.dialogOeffnen(dialoge[ev.key], anruf.dataset.vorgang);
            }
        });
    }

    /* ---------- Stoppuhr-Anzeige (lm_anruf.js füllt dauer_sek) ---------- */
    var anzeige = $('[data-stoppuhr]');
    var start = null;
    function tick() {
        if (start === null || !anzeige) { return; }
        var sek = Math.round((Date.now() - start) / 1000);
        anzeige.hidden = false;
        anzeige.textContent = 'Gespräch ' + Math.floor(sek / 60) + ':' + ('0' + (sek % 60)).slice(-2);
        var feld = $('.lk-anruf-form input[name=dauer_sek]');
        if (feld && !feld.value) { feld.dataset.lk = String(sek); }
        setTimeout(tick, 1000);
    }
    $$('a[href^="tel:"]').forEach(function (a) {
        a.addEventListener('click', function () { if (start === null) { start = Date.now(); tick(); } });
    });
    // Fallback ohne lm_anruf.js: Dauer beim Absenden eintragen, wenn noch leer
    $$('form.lm-anruf-form').forEach(function (f) {
        f.addEventListener('submit', function () {
            var feld = $('input[name=dauer_sek]', f);
            if (feld && !feld.value && start !== null) {
                feld.value = String(Math.round((Date.now() - start) / 1000));
            }
        });
    });
})();
