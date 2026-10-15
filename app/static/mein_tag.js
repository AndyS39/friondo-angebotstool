/* v32 (PLAN_V19 Phase 161/162): Vertriebler-Ansicht „Mein Tag“ (templates/leads/mein_tag.html).
   v33 (PLAN_V20 Phase 173, Design-Entwurf „Außendienst App“): Verhalten der mobilen Ansicht
   und der Seite „Wiedervorlage“ – wird auch über leads/_leiste.html (untere Leiste, base.html)
   geladen, läuft dank Schutz nur einmal.
   - viewport-fit=cover (Safe-Area wie die mobile Erfassung v14).
   - Untere Leiste: Eintrag „Kunden“ klappt das Kopfzeilen-Suchfeld (suche.js) auf und setzt
     den Fokus; ohne Suchfeld führt der Link nach /suche. Body-Klasse mt-mit-leiste als
     Rückfall für Browser ohne :has().
   - Termin-Zeilen und Wiedervorlage-Karten klappen beim Antippen auf (Details bzw. die
     Anruf-Karte aus v32 mit Dialog „Nächster Schritt“, Notizfeld, letzte Aktivitäten);
     Links/Knöpfe/Formulare darin klappen nicht.
   - Abschnitt „Wiedervorlage“ (data-mt-wv): Chips Alle · Hoch · Mittel · Niedrig mit Anzahl
     (auf der Seite bezogen auf die Suchtreffer), Segment „Sortieren: Priorität · Name · Datum“
     (gewählter Eintrag mit ↓/↑, nochmaliges Tippen dreht die Richtung), Suchfeld „Nach Name
     suchen“ (nur Seite), höchstens vier Karten in Mein Tag (data-mt-max) – alles clientseitig
     über data-Attribute der Karten (data-prio, data-rang, data-name, data-datum), Zustand in
     sessionStorage [ANNAHME] (Schlüssel mt_wv_prio / mt_wv_sort / mt_wv_dir).
   - Notizfeld „Notiz zum Gespräch“: Speichern per fetch (Accept: application/json) an
     /leads/notiz/<vorgang>, Bestätigung in der Karte; ohne fetch normales Absenden.
   - Dialog „Nächster Schritt“ (verfolgung.js von N): nach „ns:gespeichert“ wird die Karte
     gedämpft und nach dem Rückgängig-Fenster ausgeblendet (Zähler −1), „ns:rueckgaengig“
     holt sie zurück. Keine Daten in on*-Attributen (v30-Regel). */
(function () {
    'use strict';
    if (window.__meinTagGeladen) { return; }
    window.__meinTagGeladen = true;

    var meta = document.querySelector('meta[name="viewport"]');
    if (meta && meta.getAttribute('content').indexOf('viewport-fit') === -1) {
        meta.setAttribute('content', meta.getAttribute('content') + ', viewport-fit=cover');
    }

    function bereit(fn) {
        if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', fn); } else { fn(); }
    }

    // ---------- untere Leiste ----------
    bereit(function () {
        if (document.querySelector('[data-mt-leiste]')) { document.body.classList.add('mt-mit-leiste'); }
    });
    document.addEventListener('click', function (ev) {
        var kunden = ev.target.closest && ev.target.closest('[data-mt-leiste-kunden]');
        if (!kunden) { return; }
        var form = document.querySelector('form.kopf-suche');
        if (!form) { return; }
        var feld = form.querySelector('input[type="search"]');
        var lupe = form.querySelector('.kopf-suche-lupe');
        if (!feld) { return; }
        ev.preventDefault();
        if (lupe && window.getComputedStyle(lupe).display !== 'none' && !form.classList.contains('offen')) {
            lupe.click();
        }
        window.setTimeout(function () { feld.focus(); feld.select(); }, 30);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // ---------- Aufklappen (Termin-Zeile, Wiedervorlage-Karte) ----------
    function aufklappen(zeile) {
        var ziel = zeile.getAttribute('aria-controls');
        var detail = ziel ? document.getElementById(ziel) : null;
        if (!detail) { return; }
        var offen = detail.hidden;
        detail.hidden = !offen;
        zeile.setAttribute('aria-expanded', offen ? 'true' : 'false');
        var karte = zeile.closest('.mt-wv-karte, .mt-termin');
        if (karte) { karte.classList.toggle('mt-aufgeklappt', offen); }
    }
    document.addEventListener('click', function (ev) {
        var zeile = ev.target.closest && ev.target.closest('[data-mt-aufklappen]');
        if (!zeile) { return; }
        if (ev.target.closest('a, button, input, select, textarea, form, label')) { return; }
        aufklappen(zeile);
    });
    document.addEventListener('keydown', function (ev) {
        if (ev.key !== 'Enter' && ev.key !== ' ') { return; }
        var zeile = ev.target.closest && ev.target.closest('[data-mt-aufklappen]');
        if (!zeile || ev.target !== zeile) { return; }
        ev.preventDefault();
        aufklappen(zeile);
    });

    // ---------- Wiedervorlage: Filter, Sortierung, Suche, Begrenzung ----------
    var speicher = {
        lesen: function (k, standard) { try { return window.sessionStorage.getItem(k) || standard; } catch (e) { return standard; } },
        schreiben: function (k, v) { try { window.sessionStorage.setItem(k, v); } catch (e) { /* privat/gesperrt */ } }
    };
    var SORT_GUELTIG = { prio: 1, name: 1, datum: 1 };
    var PRIO_GUELTIG = { alle: 1, hoch: 1, mittel: 1, niedrig: 1 };

    function wvInit(bereich) {
        var liste = bereich.querySelector('[data-mt-wv-liste]');
        if (!liste) { return; }
        var seite = bereich.hasAttribute('data-mt-wv-seite');
        var max = parseInt(liste.getAttribute('data-mt-max') || '0', 10) || 0;
        var suche = bereich.querySelector('[data-mt-suche]');
        var leer = bereich.querySelector('[data-mt-wv-leer]');
        var leerFilter = bereich.querySelector('[data-mt-wv-leer-filter]');
        var zustand = {
            prio: speicher.lesen('mt_wv_prio', 'alle'),
            sort: speicher.lesen('mt_wv_sort', 'prio'),
            dir: speicher.lesen('mt_wv_dir', '1') === '-1' ? -1 : 1
        };
        if (!PRIO_GUELTIG[zustand.prio]) { zustand.prio = 'alle'; }
        if (!SORT_GUELTIG[zustand.sort]) { zustand.sort = 'prio'; }

        function karten() { return Array.prototype.slice.call(liste.querySelectorAll('.mt-wv-karte')); }
        function schluessel(k) {
            return {
                rang: parseInt(k.getAttribute('data-rang') || '9', 10),
                name: k.getAttribute('data-name') || '',
                datum: k.getAttribute('data-datum') || ''
            };
        }
        function vergleich(a, b) {
            var ka = schluessel(a), kb = schluessel(b), r = 0;
            if (zustand.sort === 'name') {
                r = ka.name.localeCompare(kb.name, 'de');
            } else if (zustand.sort === 'datum') {
                if (!ka.datum && !kb.datum) { r = 0; }
                else if (!ka.datum) { return 1; }        // ohne Kontakt immer ans Ende
                else if (!kb.datum) { return -1; }
                else { r = ka.datum < kb.datum ? -1 : (ka.datum > kb.datum ? 1 : 0); }
            } else {
                r = ka.rang - kb.rang;
                if (r === 0) {
                    if (ka.datum && kb.datum) { r = ka.datum < kb.datum ? -1 : (ka.datum > kb.datum ? 1 : 0); }
                    else if (ka.datum) { r = -1; } else if (kb.datum) { r = 1; }
                }
            }
            return r * zustand.dir;
        }
        function anwenden() {
            var q = suche ? suche.value.trim().toLowerCase() : '';
            var alle = karten();
            var treffer = alle.filter(function (k) { return !q || k.getAttribute('data-name').indexOf(q) >= 0; });
            var zaehler = { alle: treffer.length, hoch: 0, mittel: 0, niedrig: 0 };
            treffer.forEach(function (k) { var p = k.getAttribute('data-prio'); if (zaehler[p] !== undefined) { zaehler[p] += 1; } });
            var sichtbar = treffer.filter(function (k) { return zustand.prio === 'alle' || k.getAttribute('data-prio') === zustand.prio; });
            sichtbar.sort(vergleich);
            alle.forEach(function (k) { k.hidden = true; k.removeAttribute('data-mt-ueberzahl'); });
            sichtbar.forEach(function (k, i) {
                liste.appendChild(k);
                if (max && i >= max) { k.setAttribute('data-mt-ueberzahl', '1'); return; }
                if (!k.classList.contains('mt-fertig-weg')) { k.hidden = false; }
            });
            Object.keys(zaehler).forEach(function (p) {
                bereich.querySelectorAll('[data-mt-prio-zahl="' + p + '"]').forEach(function (el) { el.textContent = String(zaehler[p]); });
            });
            bereich.querySelectorAll('[data-mt-prio]').forEach(function (chip) {
                var an = chip.getAttribute('data-mt-prio') === zustand.prio;
                chip.classList.toggle('aktiv', an);
                chip.setAttribute('aria-pressed', an ? 'true' : 'false');
            });
            bereich.querySelectorAll('[data-mt-sort]').forEach(function (knopf) {
                var an = knopf.getAttribute('data-mt-sort') === zustand.sort;
                knopf.classList.toggle('aktiv', an);
                knopf.setAttribute('aria-pressed', an ? 'true' : 'false');
                var pfeil = knopf.querySelector('[data-mt-pfeil]');
                if (pfeil) { pfeil.textContent = an ? (zustand.dir === 1 ? '↓' : '↑') : ''; }
            });
            if (seite) {
                bereich.querySelectorAll('[data-mt-wv-zahl]').forEach(function (el) { el.textContent = String(sichtbar.length); });
            }
            var gezeigt = sichtbar.filter(function (k) { return !k.hidden; }).length;
            if (leer) { leer.hidden = gezeigt > 0; }
            if (leerFilter) { leerFilter.hidden = !(gezeigt === 0 && alle.length > 0); }
        }
        bereich.addEventListener('click', function (ev) {
            var chip = ev.target.closest('[data-mt-prio]');
            if (chip) {
                zustand.prio = chip.getAttribute('data-mt-prio');
                speicher.schreiben('mt_wv_prio', zustand.prio);
                anwenden();
                return;
            }
            var sort = ev.target.closest('[data-mt-sort]');
            if (sort) {
                var key = sort.getAttribute('data-mt-sort');
                if (key === zustand.sort) { zustand.dir = -zustand.dir; } else { zustand.sort = key; zustand.dir = 1; }
                speicher.schreiben('mt_wv_sort', zustand.sort);
                speicher.schreiben('mt_wv_dir', String(zustand.dir));
                anwenden();
            }
        });
        if (suche) {
            var timer = null;
            suche.addEventListener('input', function () { window.clearTimeout(timer); timer = window.setTimeout(anwenden, 80); });
            suche.addEventListener('search', anwenden);
        }
        bereich.__mtAnwenden = anwenden;
        anwenden();
    }
    bereit(function () {
        document.querySelectorAll('[data-mt-wv]').forEach(wvInit);
    });

    // ---------- Notiz zum Gespräch (fetch) ----------
    function meldung(form, text, klasse) {
        var m = form.querySelector('.mt-notiz-meldung');
        if (!m) { return; }
        m.textContent = text || '';
        m.hidden = !text;
        m.className = 'mt-notiz-meldung dezent' + (klasse ? ' ' + klasse : '');
    }

    document.addEventListener('submit', function (ev) {
        var form = ev.target;
        if (!form.classList || !form.classList.contains('mt-notiz')) { return; }
        if (!window.fetch || !window.FormData) { return; }
        ev.preventDefault();
        var ta = form.querySelector('textarea');
        var text = (ta.value || '').trim();
        if (!text) { meldung(form, 'Bitte eine Notiz eingeben.', 'fehler'); return; }
        var knopf = form.querySelector('button');
        knopf.disabled = true;
        fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin',
                             headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.json().then(function (a) { return a; }, function () { return null; }); })
            .then(function (antwort) {
                knopf.disabled = false;
                if (!antwort) { window.location.reload(); return; }
                if (!antwort.ok) { meldung(form, antwort.meldung || 'Notiz konnte nicht gespeichert werden.', 'fehler'); return; }
                ta.value = '';
                meldung(form, antwort.meldung || 'Notiz gespeichert.', 'ok');
                var karte = form.closest('.mt-wv-karte, .mt-karte');
                var liste = karte && karte.querySelector('.mt-aktivitaeten ul');
                if (liste && antwort.eintrag) {
                    var li = document.createElement('li');
                    var zeit = document.createElement('span'); zeit.className = 'mt-akt-zeit';
                    zeit.textContent = (antwort.eintrag.zeit || '') + ' ';
                    var art = document.createElement('span'); art.className = 'mt-akt-art'; art.textContent = 'Notiz';
                    li.appendChild(zeit); li.appendChild(art);
                    li.appendChild(document.createTextNode(' ' + (antwort.eintrag.benutzer_name || '') + ': ' + (antwort.eintrag.text || '')));
                    liste.insertBefore(li, liste.firstChild);
                    while (liste.children.length > 3) { liste.removeChild(liste.lastChild); }
                }
                // letzter Kontakt = heute (die Notiz ist ein Chat-Eintrag)
                if (karte) {
                    var tage = karte.querySelector('[data-mt-tage]');
                    if (tage) { tage.textContent = '· heute'; tage.classList.remove('warn'); }
                    var heute = new Date();
                    karte.setAttribute('data-datum', heute.getFullYear() + '-' + String(heute.getMonth() + 1).padStart(2, '0') + '-' + String(heute.getDate()).padStart(2, '0'));
                }
            })
            .catch(function () { knopf.disabled = false; meldung(form, 'Speichern fehlgeschlagen (Verbindung).', 'fehler'); });
    });

    // ---------- Dialog „Nächster Schritt“: Karte nach dem Speichern ausblenden ----------
    function karteVon(el) { return el ? el.closest('[data-mt-karte="faellig"]') : null; }

    function zaehlerSetzen(delta) {
        document.querySelectorAll('[data-mt-wv-gesamt], [data-mt-wv-zahl]').forEach(function (zahl) {
            var n = Math.max(0, (parseInt(zahl.textContent, 10) || 0) + delta);
            zahl.textContent = String(n);
        });
    }

    document.addEventListener('ns:gespeichert', function (ev) {
        var karte = karteVon(ev.target);
        if (!karte) { return; }
        var status = (ev.detail && ev.detail.status) || '';
        karte.classList.add('mt-fertig');
        karte.setAttribute('data-mt-status', status);
        var hinweis = karte.querySelector('.ns-bestaetigung-text');
        if (hinweis && status === 'bestellung_angekuendigt') {
            hinweis.textContent += ' – bleibt mit Priorität Hoch in der Wiedervorlage.';
        }
        zaehlerSetzen(-1);
        var sekunden = parseInt((ev.target.getAttribute && ev.target.getAttribute('data-rueckgaengig-s')) || '10', 10);
        window.clearTimeout(karte.__mtTimer);
        karte.__mtTimer = window.setTimeout(function () {
            if (!karte.classList.contains('mt-fertig')) { return; }
            karte.hidden = true;
            karte.classList.add('mt-fertig-weg');
            var bereich = karte.closest('[data-mt-wv]');
            if (bereich && bereich.__mtAnwenden) { bereich.__mtAnwenden(); }
        }, (sekunden + 2) * 1000);
    });

    document.addEventListener('ns:rueckgaengig', function (ev) {
        var karte = karteVon(ev.target);
        if (!karte) { return; }
        window.clearTimeout(karte.__mtTimer);
        karte.hidden = false;
        karte.classList.remove('mt-fertig', 'mt-fertig-weg');
        zaehlerSetzen(1);
    });
})();
