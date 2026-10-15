/* v34 (PLAN_V21 Phase 181): Diktierfunktion für Textfelder – Knopf „Diktieren“ (Makro
   diktat_knopf in _diktat.html) an den Freitext-Feldern der mobilen Erfassung, am Notizen-Chat
   und in den Montage-Formularen. Web Speech API (SpeechRecognition / webkitSpeechRecognition),
   Sprache de-DE, Zwischenergebnisse werden live am Cursor eingeblendet, erkannter Text wird am
   Cursor angefügt (vorhandener Text bleibt); Stopp per Knopf oder automatisch nach einer
   Sprechpause (continuous = false – der Browser beendet die Erkennung selbst).
   Die Browser-Spracherkennung läuft NUR in einem sicheren Kontext (HTTPS bzw. localhost) – das
   Tool läuft heute über http im VPN. Ohne window.isSecureContext oder ohne SpeechRecognition zeigt
   der Knopf stattdessen den Hinweis „Diktat: bitte das Mikrofon Ihrer Handy-Tastatur verwenden“
   (das Tastatur-Diktat von iOS/Android funktioniert in jedem Textfeld). Vorbereitung HTTPS:
   docs/https-intern.md. Farben nur über die Tokens aus style.css (kein Hex). */
(function () {
    'use strict';
    var HINWEIS = 'Diktat: bitte das Mikrofon Ihrer Handy-Tastatur verwenden';
    var TEXT_START = 'Diktieren';
    var TEXT_STOPP = 'Stopp';
    var Erkennung = window.SpeechRecognition || window.webkitSpeechRecognition || null;
    var laufend = null;   // { knopf, feld, rec, basis, rest }

    function verfuegbar() {
        return !!(window.isSecureContext && Erkennung);
    }

    function stil() {
        if (document.getElementById('diktat-stil')) { return; }
        var s = document.createElement('style');
        s.id = 'diktat-stil';
        s.textContent =
            '.diktat-block{display:inline-flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin:.3rem 0 0}' +
            '.diktat-knopf{display:inline-flex;align-items:center;gap:.35rem;min-height:36px}' +
            '.diktat-knopf .symbol-svg{width:1.1em;height:1.1em}' +
            '.diktat-knopf[aria-pressed="true"]{color:var(--status-rot);border-color:var(--status-rot);' +
            'background:var(--status-rot-bg)}' +
            '.diktat-knopf[aria-pressed="true"] .symbol-svg{animation:diktat-puls 1s ease-in-out infinite}' +
            '.diktat-hinweis{font-size:var(--t-xs, .8rem);color:var(--text-dezent)}' +
            '.diktat-hinweis[hidden]{display:none}' +
            '.diktat-zwischen{color:var(--text-dezent);font-style:italic;font-size:var(--t-xs, .8rem)}' +
            '@keyframes diktat-puls{0%,100%{opacity:1}50%{opacity:.35}}';
        document.head.appendChild(s);
    }

    function feldVon(knopf) {
        var ziel = knopf.getAttribute('data-ziel') || '';
        return ziel ? document.getElementById(ziel) : null;
    }

    function hinweisVon(knopf) {
        var block = knopf.closest('.diktat-block');
        return block ? block.querySelector('.diktat-hinweis') : null;
    }

    function hinweisZeigen(knopf, text) {
        var h = hinweisVon(knopf);
        if (!h) { return; }
        h.textContent = text;
        h.hidden = false;
    }

    function zustand(knopf, aktiv) {
        knopf.setAttribute('aria-pressed', aktiv ? 'true' : 'false');
        var t = knopf.querySelector('.diktat-text');
        if (t) { t.textContent = aktiv ? TEXT_STOPP : TEXT_START; }
    }

    function ereignis(feld, name) {
        try { feld.dispatchEvent(new Event(name, { bubbles: true })); } catch (e) { /* alte Browser */ }
    }

    function schreiben(feld, basis, endgueltig, zwischen, rest) {
        var mitte = endgueltig + (zwischen ? zwischen : '');
        feld.value = basis + mitte + rest;
        var pos = (basis + mitte).length;
        try { feld.setSelectionRange(pos, pos); } catch (e) { /* z. B. input type=search */ }
        ereignis(feld, 'input');
    }

    function stopp(abbruch) {
        if (!laufend) { return; }
        var l = laufend;
        laufend = null;
        try { if (abbruch) { l.rec.abort(); } else { l.rec.stop(); } } catch (e) { /* schon beendet */ }
        zustand(l.knopf, false);
    }

    function start(knopf, feld) {
        stil();
        var rec;
        try { rec = new Erkennung(); } catch (e) { hinweisZeigen(knopf, HINWEIS); return; }
        rec.lang = 'de-DE';
        rec.continuous = false;        // Pause beendet die Erkennung (Stopp per Pause)
        rec.interimResults = true;
        rec.maxAlternatives = 1;
        var pos = (typeof feld.selectionStart === 'number') ? feld.selectionStart : feld.value.length;
        var ende = (typeof feld.selectionEnd === 'number') ? feld.selectionEnd : pos;
        var basis = feld.value.slice(0, pos);
        var rest = feld.value.slice(ende);
        if (basis && !/\s$/.test(basis)) { basis += ' '; }
        if (rest && !/^\s/.test(rest)) { rest = ' ' + rest; }
        var endgueltig = '';
        laufend = { knopf: knopf, feld: feld, rec: rec, basis: basis, rest: rest };
        rec.onresult = function (ev) {
            var fertig = '', zwischen = '';
            for (var i = 0; i < ev.results.length; i++) {
                var t = ev.results[i][0] ? ev.results[i][0].transcript : '';
                if (ev.results[i].isFinal) { fertig += t; } else { zwischen += t; }
            }
            endgueltig = fertig;
            schreiben(feld, basis, endgueltig, zwischen, rest);
        };
        rec.onerror = function (ev) {
            var art = ev && ev.error ? ev.error : '';
            if (art === 'not-allowed' || art === 'service-not-allowed') {
                hinweisZeigen(knopf, 'Mikrofon nicht freigegeben – ' + HINWEIS);
            } else if (art && art !== 'aborted' && art !== 'no-speech') {
                hinweisZeigen(knopf, 'Diktat nicht möglich (' + art + ') – ' + HINWEIS);
            }
        };
        rec.onend = function () {
            schreiben(feld, basis, endgueltig, '', rest);
            ereignis(feld, 'change');
            if (laufend && laufend.rec === rec) { laufend = null; }
            zustand(knopf, false);
            try { feld.focus({ preventScroll: true }); } catch (e) { feld.focus(); }
        };
        zustand(knopf, true);
        try {
            rec.start();
        } catch (e) {
            laufend = null;
            zustand(knopf, false);
            hinweisZeigen(knopf, HINWEIS);
        }
    }

    function knopfKlick(knopf) {
        var feld = feldVon(knopf);
        if (!feld) { return; }
        if (!verfuegbar()) { hinweisZeigen(knopf, HINWEIS); return; }
        if (laufend && laufend.knopf === knopf) { stopp(false); return; }
        if (laufend) { stopp(false); }
        start(knopf, feld);
    }

    function einrichten() {
        var knoepfe = document.querySelectorAll('.diktat-knopf');
        if (!knoepfe.length) { return; }
        stil();
        if (!verfuegbar()) {
            Array.prototype.forEach.call(knoepfe, function (knopf) {
                knopf.hidden = true;
                knopf.setAttribute('data-diktat', 'aus');
                hinweisZeigen(knopf, HINWEIS);
            });
            return;
        }
        Array.prototype.forEach.call(knoepfe, function (knopf) {
            knopf.setAttribute('data-diktat', 'an');
        });
    }

    document.addEventListener('click', function (ev) {
        var knopf = ev.target && ev.target.closest ? ev.target.closest('.diktat-knopf') : null;
        if (!knopf) { return; }
        ev.preventDefault();
        knopfKlick(knopf);
    });
    window.addEventListener('pagehide', function () { stopp(true); });
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', einrichten);
    } else {
        einrichten();
    }

    window.friondoDiktat = { verfuegbar: verfuegbar, stopp: stopp, HINWEIS: HINWEIS };
})();
