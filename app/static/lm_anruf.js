/* Lead-Management V2, Phase 107 (PLAN_LEAD_V2 D1): Stoppuhr für die
   manuelle Dauer-Erfassung je Anruf – Vertrag im Briefing:
   - startet beim Klick auf a[href^="tel:"] oder auf einen Ergebnis-Button
     (button[name=ergebnis], button[data-ergebnis], [data-anruf-start]),
   - zeigt mm:ss in .lm-stoppuhr (mit data-vorgang=<id> je Zeile, ohne
     data-vorgang als Einzelanzeige z. B. in der Kartei),
   - füllt beim Absenden input[name=dauer_sek] in Formularen mit der Klasse
     lm-anruf-form (der Vorgang kommt aus dem nächsten [data-vorgang]-Vorfahren
     des Formulars – Zeile oder Dialog), danach Reset.
   Zusätzlich: Dauer-Korrektur (.lm-dauer-form) ohne Seitensprung per fetch.
   Vanilla JS, kein Framework; andere Phasen binden die Datei nur ein. */
(function () {
    'use strict';
    const uhr = { vorgang: null, start: null, timer: null };

    function fmt(sek) {
        sek = Math.max(0, Math.floor(sek));
        const h = Math.floor(sek / 3600), m = Math.floor((sek % 3600) / 60), s = sek % 60;
        const mm = String(m).padStart(2, '0'), ss = String(s).padStart(2, '0');
        return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
    }
    function sekunden() {
        return uhr.start ? Math.round((Date.now() - uhr.start) / 1000) : 0;
    }
    // Anzeige-Elemente: .lm-stoppuhr (Anrufliste) und [data-stoppuhr] (Kartei,
    // Phase 106) – ohne data-vorgang gilt die Anzeige für den laufenden Anruf
    const ANZEIGE = '.lm-stoppuhr, [data-stoppuhr]';
    function anzeigen() {
        return Array.from(document.querySelectorAll(ANZEIGE)).filter(el =>
            !el.dataset.vorgang || uhr.vorgang == null || el.dataset.vorgang == String(uhr.vorgang));
    }
    function anzeige() {
        const text = fmt(sekunden());
        anzeigen().forEach(el => { el.textContent = text; el.hidden = false; el.classList.add('laeuft'); });
    }
    function reset() {
        if (uhr.timer) clearInterval(uhr.timer);
        uhr.timer = null; uhr.start = null; uhr.vorgang = null;
        document.querySelectorAll(ANZEIGE).forEach(el => {
            el.classList.remove('laeuft');
            if (el.dataset.vorgang || el.hasAttribute('data-stoppuhr')) el.hidden = true;
            else el.textContent = '00:00';
        });
    }
    function start(vorgang) {
        vorgang = vorgang == null ? null : String(vorgang);
        if (uhr.start && uhr.vorgang === vorgang) return;      // läuft schon für diesen Lead
        reset();
        uhr.vorgang = vorgang; uhr.start = Date.now();
        uhr.timer = setInterval(anzeige, 1000);
        anzeige();
    }
    function vorgangVon(el) {
        const c = el && el.closest('[data-vorgang]');
        return c && c.dataset.vorgang ? c.dataset.vorgang : null;
    }

    // Start: tel:-Link oder Ergebnis-Button (capture, damit der Start vor dem Submit liegt)
    document.addEventListener('click', e => {
        const tel = e.target.closest && e.target.closest('a[href^="tel:"]');
        if (tel) { start(vorgangVon(tel)); return; }
        const knopf = e.target.closest && e.target.closest(
            'button[name="ergebnis"], button[data-ergebnis], [data-anruf-start]');
        if (knopf && !knopf.disabled) {
            const v = vorgangVon(knopf);
            if (!(uhr.start && (uhr.vorgang === v || uhr.vorgang === null))) start(v);
        }
    }, true);

    // Absenden: Dauer in das Formular schreiben, danach zurücksetzen
    document.addEventListener('submit', e => {
        const form = e.target;
        if (!form.classList || !form.classList.contains('lm-anruf-form')) return;
        const feld = form.querySelector('input[name="dauer_sek"]');
        if (feld) {
            const v = vorgangVon(form);
            const passt = uhr.start && (v == null || uhr.vorgang == null || uhr.vorgang === v);
            const sek = passt ? sekunden() : 0;
            feld.value = sek >= 1 ? String(sek) : '';
        }
        setTimeout(reset, 0);
    }, true);

    // Dialog geschlossen ohne Absenden: Uhr läuft weiter (der Anruf läuft ja noch) – nichts tun.

    // D1: Dauer-Korrektur ohne Seitensprung (Accept: application/json, v17-Muster)
    document.addEventListener('submit', e => {
        const form = e.target;
        if (!form.classList || !form.classList.contains('lm-dauer-form')) return;
        if (!window.fetch || !window.FormData) return;          // Fallback: normaler POST
        e.preventDefault();
        const daten = new FormData(form);
        const feld = form.querySelector('input[name="dauer_sek"]');
        fetch(form.action, { method: 'POST', body: daten, headers: { Accept: 'application/json' } })
            .then(r => r.json().then(d => ({ ok: r.ok, d })))
            .then(({ ok, d }) => {
                form.classList.remove('fehler', 'ok');
                if (ok && d.ok) {
                    if (feld) feld.value = d.dauer;
                    form.classList.add('ok');
                    form.title = 'Dauer gespeichert – Korrektur als Systemeintrag protokolliert';
                } else {
                    form.classList.add('fehler');
                    form.title = (d && d.fehler) || 'Korrektur nicht möglich';
                }
            })
            .catch(() => { form.classList.add('fehler'); form.title = 'Korrektur nicht möglich'; });
    });

    window.lmAnruf = { start, reset, sekunden, fmt };
})();
