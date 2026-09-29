/* Projektierung V4 (PLAN_PROJ_V4 Phase 90.4/90.5) – gemeinsame Helfer für
   Projektakte, Board, Meine Aufgaben und das Montage-Backend:
   1. Zeitfelder im 15-Minuten-Takt (step 900): leere Felder werden auf das
      nächste Viertel vorbelegt, Eingaben auf 15 Minuten gerundet.
   2. Aufgaben-Aktionen per fetch (Accept: application/json) – die Zeile wird
      an Ort und Stelle ersetzt, Zähler/Ampel aktualisiert; schlägt fetch fehl,
      wird das Formular klassisch abgeschickt (Server-Redirect als Fallback).
   3. Alle übrigen POST-Formulare: Scroll-Position je URL in sessionStorage
      merken und nach dem Redirect wiederherstellen. */
(function () {
    'use strict';

    // ---------- 1. 15-Minuten-Takt ----------
    function zwei(n) { return (n < 10 ? '0' : '') + n; }

    function naechstesViertel(jetzt) {
        const d = new Date(jetzt.getTime());
        d.setSeconds(0, 0);
        const rest = d.getMinutes() % 15;
        if (rest) { d.setMinutes(d.getMinutes() + (15 - rest)); }
        return d;
    }

    function rundeViertel(stunde, minute) {
        let gesamt = Math.round((stunde * 60 + minute) / 15) * 15;
        if (gesamt >= 24 * 60) { gesamt = 24 * 60 - 15; }
        return [Math.floor(gesamt / 60), gesamt % 60];
    }

    function viertelFeld(feld) {
        if (feld.dataset.pjViertel) { return; }
        feld.dataset.pjViertel = '1';
        if (!feld.value && !feld.hasAttribute('data-leer-lassen')) {
            const d = naechstesViertel(new Date());
            const zeit = zwei(d.getHours()) + ':' + zwei(d.getMinutes());
            if (feld.type === 'time') {
                feld.value = zeit;
            } else if (feld.type === 'datetime-local' && feld.required) {
                feld.value = d.getFullYear() + '-' + zwei(d.getMonth() + 1) + '-'
                    + zwei(d.getDate()) + 'T' + zeit;
            }
        }
        feld.addEventListener('change', function () {
            const m = feld.value.match(/(\d{2}):(\d{2})$/);
            if (!m) { return; }
            const r = rundeViertel(parseInt(m[1], 10), parseInt(m[2], 10));
            feld.value = feld.value.slice(0, -5) + zwei(r[0]) + ':' + zwei(r[1]);
        });
    }

    function viertelFelderInit(wurzel) {
        (wurzel || document).querySelectorAll(
            'input[type=time][step="900"], input[type=datetime-local][step="900"]'
        ).forEach(viertelFeld);
    }

    // ---------- 2. Aufgaben-Aktionen per fetch ----------
    function meldungZeigen(text) {
        if (!text) { return; }
        let kasten = document.getElementById('pj-live-meldung');
        if (!kasten) {
            kasten = document.createElement('div');
            kasten.id = 'pj-live-meldung';
            kasten.className = 'pj-live-meldung';
            kasten.setAttribute('role', 'status');
            document.body.appendChild(kasten);
        }
        kasten.textContent = text;
        kasten.hidden = false;
        clearTimeout(kasten._timer);
        kasten._timer = setTimeout(function () { kasten.hidden = true; }, 4000);
    }

    function antwortAnwenden(daten) {
        if (daten.zeile_html && daten.aufgabe_id) {
            const alt = document.getElementById('aufgabe-' + daten.aufgabe_id);
            if (alt) {
                const hilfe = document.createElement('div');
                hilfe.innerHTML = daten.zeile_html.trim();
                const neu = hilfe.firstElementChild;
                if (neu) {
                    // aufgeklappte Details bleiben aufgeklappt
                    const offen = alt.querySelector('details[open]');
                    alt.replaceWith(neu);
                    if (offen) {
                        const d = neu.querySelector('details');
                        if (d) { d.open = true; }
                    }
                    viertelFelderInit(neu);
                }
            }
        }
        (daten.pakete || []).forEach(function (p) {
            const el = document.querySelector('[data-paket-cnt="' + p.instanz_id + '"]');
            if (el) { el.textContent = p.text; }
        });
        if (daten.ampel_html && daten.gewerk_id) {
            const el = document.getElementById('pj-ampel-' + daten.gewerk_id);
            if (el) { el.innerHTML = daten.ampel_html; }
        }
        if (daten.gewerk_id && daten.waechter !== undefined) {
            const el = document.getElementById('pj-waechter-' + daten.gewerk_id);
            if (el) {
                el.textContent = daten.waechter;
                el.hidden = !daten.waechter;
            }
        }
        if (daten.restarbeit) {
            const el = document.getElementById('restarbeit-' + daten.restarbeit.id);
            if (el) { el.classList.toggle('done', !!daten.restarbeit.erledigt); }
        }
        (daten.weitere || []).forEach(antwortAnwenden);
        meldungZeigen(daten.meldung);
    }

    function senden(form) {
        if (!window.fetch || !form) {
            form.submit();
            return false;
        }
        const daten = new FormData(form);
        fetch(form.action, {
            method: 'POST', body: daten, credentials: 'same-origin',
            headers: {'Accept': 'application/json'}
        }).then(function (antwort) {
            const typ = antwort.headers.get('content-type') || '';
            if (!antwort.ok || typ.indexOf('application/json') < 0) {
                throw new Error('keine JSON-Antwort');
            }
            return antwort.json();
        }).then(antwortAnwenden).catch(function () {
            scrollMerken();
            form.submit();          // Fallback: klassischer POST + Redirect
        });
        return false;
    }
    window.pjSenden = senden;

    // Formulare mit data-pj-ajax: Absenden (Enter) ebenfalls per fetch
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (form && form.matches && form.matches('form[data-pj-ajax]')) {
            e.preventDefault();
            senden(form);
        }
    }, true);

    // ---------- 3. Scroll-Position bei klassischen POSTs ----------
    const bereich = /^\/(projektierung|montage)(\/|$)/.test(location.pathname);

    function schluessel() { return 'pjScroll:' + location.pathname; }

    function scrollMerken() {
        try { sessionStorage.setItem(schluessel(), String(window.scrollY)); }
        catch (fehler) { /* privater Modus – egal */ }
    }

    if (bereich) {
        document.addEventListener('submit', function (e) {
            const form = e.target;
            if (form && (form.method || '').toLowerCase() === 'post'
                    && !form.matches('form[data-pj-ajax]')) {
                scrollMerken();
            }
        });
        // form.submit() aus onchange-Handlern feuert kein submit-Ereignis
        const originalSubmit = HTMLFormElement.prototype.submit;
        HTMLFormElement.prototype.submit = function () {
            if ((this.method || '').toLowerCase() === 'post') { scrollMerken(); }
            return originalSubmit.call(this);
        };
    }

    document.addEventListener('DOMContentLoaded', function () {
        viertelFelderInit(document);
        if (!bereich) { return; }
        let wert = null;
        try {
            wert = sessionStorage.getItem(schluessel());
            sessionStorage.removeItem(schluessel());
        } catch (fehler) { wert = null; }
        if (wert !== null && !location.hash) {
            window.scrollTo(0, parseInt(wert, 10) || 0);
        }
    });
})();
