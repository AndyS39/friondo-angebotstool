/* v35 (PLAN_LEAD_V6 Phase 186, Agent B): Sofortsuche und gespeicherte Filter im Lead-Modul.
   Vanilla JS, kein Framework, keine externen Quellen. Eingebunden je Seite (Hauptboard/Deals,
   Kontaktiert, Infoabend, Handelsvertreter, Anrufliste, Kanban, To-Dos); die Karte löst ihre
   Pins direkt über ihr eigenes Skript (karte.html).

   1. Sofortsuche: jedes Formular mit data-lm-sofort="1" wirkt ohne Enter –
      Suchfelder 300 ms nach dem letzten Tastendruck, Auswahlfelder/Häkchen/Datum sofort,
      Enter (submit) sofort, Escape leert das Suchfeld. Die URL spiegelt den Filter
      (history.replaceState, teilbar; die Zurück-Navigation der v30 bleibt). Laufende
      Anfragen werden bei neuer Eingabe verworfen (AbortController). Geladen wird dieselbe
      Seite mit ?fragment=1: liefert der Server JSON {ziele: {name: html}} (Boards,
      Kontaktiert), werden nur diese Bereiche getauscht, sonst die ganze Seite geparst und die
      Bereiche data-lm-sofort-ziel="<name>" daraus übernommen (Infoabend, HV, Anrufliste,
      Kanban, To-Dos). Getauscht wird der INHALT des Bereichs (Kinder + Attribute), damit
      Verweise anderer Skripte auf das Element (Sticky-Geometrie, Scrollleiste) gültig bleiben.
      Der Klappzustand von <details> mit data-gruppe/data-hv bleibt über den Tausch erhalten.
      Danach feuert document „lm-sofort:geladen“ (lm_boards.js, lm_info.js, lm_hv.js, die
      Anrufliste und lm_anruf.js hängen sich daran).
   2. Chip-Links: data-lm-sofort-links="a,b,c" am Formular nennt die Parameter, die Links
      innerhalb des Formulars (oder in Containern mit data-lm-sofort-link-quelle="<form-id>")
      steuern – Klick übernimmt diese Parameter aus dem Link in versteckte Felder (fehlt ein
      Parameter im Link, wird er entfernt), alle anderen Felder bleiben, dann sofort laden.
      data-lm-sofort-leeren="feld" an einem Link leert nur dieses Feld.
   3. Gespeicherte Filter (Makro filter_speicher in _tabelle.html, Formular mit
      data-lm-sofort-filter="<board>"): Anwenden setzt die Felder aus data-werte (JSON), die
      gemerkte Sortierung (POST /boards/spalten {sort}) und den Klappzustand der Gruppen, dann
      laden; „Filter speichern“ sammelt Felder + Sortierung (#lm-daten) + eingeklappte Gruppen
      → POST /lead-management/boards/filter; ★ Standard beim Öffnen, Stift Umbenennen,
      Nutzer-Symbol für alle freigeben (Innendienst/Admin), Papierkorb Löschen/Freigabe entfernen,
      „Filter zurücksetzen“ leert alle Felder und setzt filter=0 (Standardfilter greift dann
      nicht erneut). Die Liste wird nach jeder Aktion aus der JSON-Antwort neu aufgebaut
      (nur DOM-Methoden, kein innerHTML mit Daten). */
(function () {
    'use strict';
    if (window.__lmSofortGeladen) { return; }
    window.__lmSofortGeladen = true;
    var VERZOEGERUNG = 300;
    var NEUTRAL = ['meldung', 'fehler', 'kopien', 'fragment'];
    var FILTER_URL = '/lead-management/boards/filter';
    var SPALTEN_URL = '/lead-management/boards/spalten';

    function element(tag, klasse, text) {
        var e = document.createElement(tag);
        if (klasse) { e.className = klasse; }
        if (text !== undefined && text !== null) { e.textContent = text; }
        return e;
    }
    function melden(text, fehler) {
        var el = document.getElementById('lm-meldung') || document.getElementById('li-meldung');
        if (!el) { if (fehler && text) { window.alert(text); } return; }
        el.textContent = text || '';
        el.classList.toggle('fehler', !!fehler);
        el.hidden = !text;
        clearTimeout(el.__lmTimer);
        if (text && !fehler) { el.__lmTimer = setTimeout(function () { el.hidden = true; }, 6000); }
    }
    function svgKopie(selektor) {
        var quelle = document.querySelector(selektor);
        return quelle ? quelle.cloneNode(true) : null;
    }

    // ---------- Formularwerte ----------
    function formParams(form) {
        var p = new URLSearchParams();
        new FormData(form).forEach(function (v, k) {
            if (String(v).trim() !== '') { p.append(k, v); }
        });
        return p;
    }
    function formWerte(form) {
        // {name: wert | [werte]} ohne leere Werte – Basis der gespeicherten Filter
        var werte = {};
        new FormData(form).forEach(function (v, k) {
            if (String(v).trim() === '' || k === 'fragment' || k === 'filter') { return; }
            if (werte[k] === undefined) { werte[k] = v; }
            else if (Array.isArray(werte[k])) { werte[k].push(v); }
            else { werte[k] = [werte[k], v]; }
        });
        return werte;
    }
    function feldSetzen(form, name, wert) {
        // Wert(e) in alle Felder dieses Namens schreiben; fehlt ein Feld, als hidden anlegen
        var werte = Array.isArray(wert) ? wert.map(String) : (wert === null || wert === undefined ? [] : [String(wert)]);
        var felder = Array.from(form.querySelectorAll('[name="' + CSS.escape(name) + '"]'));
        if (!felder.length) {
            if (!werte.length) { return; }
            var h = document.createElement('input');
            h.type = 'hidden'; h.name = name; h.value = werte[0]; h.dataset.lmSofortHidden = '1';
            form.appendChild(h);
            return;
        }
        felder.forEach(function (f) {
            if (f.type === 'checkbox' || f.type === 'radio') {
                f.checked = werte.indexOf(f.value) >= 0 || (f.type === 'checkbox' && werte.length === 1 && werte[0] === '1' && f.value === '1');
                var chip = f.closest('.lm-filterchip');
                if (chip) { chip.classList.toggle('aktiv', f.checked); }
            } else if (f.tagName === 'SELECT' && f.multiple) {
                Array.from(f.options).forEach(function (o) { o.selected = werte.indexOf(o.value) >= 0; });
            } else if (f.type === 'hidden' && f.dataset.lmSofortHidden === '1' && !werte.length) {
                f.remove();
            } else {
                f.value = werte.length ? werte[0] : '';
            }
        });
    }
    function formLeeren(form) {
        Array.from(form.elements).forEach(function (f) {
            if (!f.name || f.name === 'board') { return; }
            if (f.type === 'checkbox' || f.type === 'radio') {
                f.checked = false;
                var chip = f.closest('.lm-filterchip');
                if (chip) { chip.classList.remove('aktiv'); }
            } else if (f.type === 'hidden') {
                if (f.dataset.lmSofortHidden === '1') { f.remove(); }
                else if (f.name !== 'meine' && f.name !== 'sicht' && f.name !== 'vorgang_id') { f.value = ''; }
            } else if (f.tagName === 'SELECT') {
                f.selectedIndex = 0;
                if (f.options.length && f.options[0].value !== '') { f.value = ''; }
            } else if (f.tagName === 'INPUT' || f.tagName === 'TEXTAREA') {
                f.value = '';
            }
        });
    }
    function sichtbareWerte(form) {
        return Array.from(form.elements).some(function (f) {
            if (!f.name || f.type === 'hidden' || f.tagName === 'BUTTON') { return false; }
            if (f.type === 'checkbox' || f.type === 'radio') { return f.checked; }
            return String(f.value || '').trim() !== '' && !(f.tagName === 'SELECT' && f.selectedIndex === 0 && f.options[0].value === '');
        });
    }

    // ---------- Bereiche tauschen ----------
    function klappzustand(wurzel) {
        var zustand = {};
        wurzel.querySelectorAll('details[data-gruppe], details[data-hv]').forEach(function (d) {
            zustand[d.dataset.gruppe || ('hv:' + d.dataset.hv)] = d.open;
        });
        return zustand;
    }
    function klappzustandSetzen(wurzel, zustand) {
        wurzel.querySelectorAll('details[data-gruppe], details[data-hv]').forEach(function (d) {
            var key = d.dataset.gruppe || ('hv:' + d.dataset.hv);
            if (key in zustand) { d.open = zustand[key]; }
        });
    }
    function bereichErsetzen(ziel, neuHtml, form) {
        var tmp = document.createElement('div');
        tmp.innerHTML = neuHtml;
        var neu = tmp.firstElementChild;
        if (!neu) { return; }
        if (form && ziel.contains(form)) { return; }     // das Formular selbst wird nie getauscht
        var zustand = klappzustand(ziel);
        // Attribute (hidden, class, title) übernehmen, Inhalt tauschen – das Element bleibt
        Array.from(ziel.attributes).forEach(function (a) {
            if (a.name !== 'data-lm-sofort-ziel' && !neu.hasAttribute(a.name)) { ziel.removeAttribute(a.name); }
        });
        Array.from(neu.attributes).forEach(function (a) { ziel.setAttribute(a.name, a.value); });
        ziel.replaceChildren.apply(ziel, Array.from(neu.childNodes));
        klappzustandSetzen(ziel, zustand);
    }
    function zieleAusHtml(html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var map = {};
        doc.querySelectorAll('[data-lm-sofort-ziel]').forEach(function (el) {
            var name = el.getAttribute('data-lm-sofort-ziel');
            if (!(name in map)) { map[name] = el.outerHTML; }
        });
        return map;
    }
    function anwenden(map, form) {
        Object.keys(map).forEach(function (name) {
            var ziel = document.querySelector('[data-lm-sofort-ziel="' + CSS.escape(name) + '"]');
            if (ziel) { bereichErsetzen(ziel, map[name], form); }
        });
        document.querySelectorAll('[data-lm-sofort-ziel][aria-busy]').forEach(function (z) { z.removeAttribute('aria-busy'); });
        document.dispatchEvent(new CustomEvent('lm-sofort:geladen', { detail: { form: form } }));
    }

    // ---------- Laden ----------
    function Steuerung(form) {
        var self = this;
        this.form = form;
        this.timer = null;
        this.abbrecher = null;
        this.basis = (form.getAttribute('action') || window.location.pathname).split('?')[0];
        this.laden = function () {
            clearTimeout(self.timer);
            var params = formParams(form);
            var url = self.basis + (params.toString() ? '?' + params.toString() : '');
            try { window.history.replaceState(window.history.state, '', url); } catch (e) { /* egal */ }
            var leeren = form.querySelector('.lm-filter-leeren');
            if (leeren) { leeren.hidden = !sichtbareWerte(form); }
            if (self.abbrecher) { self.abbrecher.abort(); }
            self.abbrecher = new AbortController();
            var signal = self.abbrecher.signal;
            params.set('fragment', '1');
            document.querySelectorAll('[data-lm-sofort-ziel]').forEach(function (z) { z.setAttribute('aria-busy', 'true'); });
            form.classList.add('lm-laedt');
            fetch(self.basis + '?' + params.toString(), {
                headers: { 'X-Requested-With': 'lm-sofort', 'Accept': 'application/json, text/html' },
                credentials: 'same-origin', signal: signal
            }).then(function (r) {
                if (!r.ok) { throw new Error('HTTP ' + r.status); }
                var typ = r.headers.get('content-type') || '';
                return typ.indexOf('application/json') >= 0
                    ? r.json().then(function (j) { return j.ziele || {}; })
                    : r.text().then(zieleAusHtml);
            }).then(function (map) {
                if (signal.aborted) { return; }
                form.classList.remove('lm-laedt');
                anwenden(map, form);
            }).catch(function (e) {
                if (signal.aborted) { return; }
                form.classList.remove('lm-laedt');
                document.querySelectorAll('[data-lm-sofort-ziel][aria-busy]').forEach(function (z) { z.removeAttribute('aria-busy'); });
                melden('Liste konnte nicht aktualisiert werden (' + (e && e.message ? e.message : 'Verbindung') + ').', true);
            });
        };
        this.verzoegert = function () {
            clearTimeout(self.timer);
            self.timer = setTimeout(self.laden, VERZOEGERUNG);
        };
    }
    var steuerungen = new WeakMap();
    function steuerung(form) {
        var s = steuerungen.get(form);
        if (!s) { s = new Steuerung(form); steuerungen.set(form, s); }
        return s;
    }
    function istTextfeld(el) {
        return el.tagName === 'INPUT' && ['search', 'text', 'tel', 'number', 'email'].indexOf(el.type) >= 0;
    }

    document.querySelectorAll('form[data-lm-sofort]').forEach(function (form) {
        var s = steuerung(form);
        form.addEventListener('input', function (e) {
            if (istTextfeld(e.target)) { s.verzoegert(); }
        });
        form.addEventListener('change', function (e) {
            var el = e.target;
            if (istTextfeld(el)) { s.laden(); return; }
            var chip = el.closest('.lm-filterchip');
            if (chip && el.type === 'checkbox') { chip.classList.toggle('aktiv', el.checked); }
            s.laden();
        });
        form.addEventListener('submit', function (e) { e.preventDefault(); s.laden(); });
        form.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && istTextfeld(e.target) && e.target.value) {
                e.preventDefault(); e.target.value = ''; s.laden();
            }
        });
        // „Filter zurücksetzen“ / „Zurücksetzen“-Link des Formulars: leeren statt Seitenwechsel
        form.addEventListener('click', function (e) {
            var leerLink = e.target.closest('.lm-filter-leeren');
            if (leerLink && form.contains(leerLink)) {
                e.preventDefault();
                formLeeren(form);
                if (form.dataset.lmSofortFilter) { feldSetzen(form, 'filter', '0'); }
                filterNameSetzen(form, '');
                s.laden();
                return;
            }
            var leeren = e.target.closest('[data-lm-sofort-leeren]');
            if (leeren && form.contains(leeren)) {
                e.preventDefault();
                feldSetzen(form, leeren.dataset.lmSofortLeeren, []);
                var det = leeren.closest('details');
                if (det) { det.removeAttribute('open'); }
                s.laden();
            }
        });
    });

    // ---------- Chip-Links (innerhalb des Formulars oder in Quell-Containern) ----------
    function linkFormular(link) {
        var form = link.closest('form[data-lm-sofort][data-lm-sofort-links]');
        if (form) { return form; }
        var quelle = link.closest('[data-lm-sofort-link-quelle]');
        if (!quelle) { return null; }
        var f = document.getElementById(quelle.dataset.lmSofortLinkQuelle);
        return f && f.dataset.lmSofort !== undefined ? f : null;
    }
    document.addEventListener('click', function (e) {
        var link = e.target.closest ? e.target.closest('a[href]') : null;
        if (!link || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) { return; }
        if (link.classList.contains('lm-filter-leeren') || link.hasAttribute('data-lm-sofort-leeren')) { return; }
        var form = linkFormular(link);
        if (!form) { return; }
        var s = steuerung(form);
        var ziel;
        try { ziel = new URL(link.getAttribute('href'), window.location.origin); } catch (x) { return; }
        if (ziel.pathname !== s.basis) { return; }        // Links auf andere Seiten bleiben Links
        e.preventDefault();
        var namen = (form.dataset.lmSofortLinks || '').split(',').map(function (n) { return n.trim(); }).filter(Boolean);
        namen.forEach(function (name) {
            var werte = ziel.searchParams.getAll(name);
            feldSetzen(form, name, werte);
        });
        s.laden();
    });

    // ---------- Gespeicherte Filter ----------
    function filterNameSetzen(form, name) {
        var label = document.getElementById('lm-filter-aktiv-name');
        if (label) { label.textContent = name ? 'Filter: ' + name : 'Gespeicherte Filter'; }
    }
    function lmDaten() {
        try { return JSON.parse(document.getElementById('lm-daten').textContent) || {}; } catch (e) { return {}; }
    }
    function gruppenZu() {
        var zu = [];
        document.querySelectorAll('[data-lm-sofort-ziel] details[data-gruppe], [data-lm-sofort-ziel] details[data-hv]').forEach(function (d) {
            if (!d.open) { zu.push(d.dataset.gruppe || ('hv:' + d.dataset.hv)); }
        });
        return zu;
    }
    function werteSammeln(form) {
        var werte = formWerte(form);
        var daten = lmDaten();
        if (daten.sort && daten.sort.key) { werte.sort = { key: daten.sort.key, richtung: daten.sort.richtung || 'auf' }; }
        var zu = gruppenZu();
        if (zu.length) { werte.gruppen_zu = zu; }
        return werte;
    }
    function filterPost(speicher, nutzlast) {
        nutzlast.board = speicher.dataset.board;
        return fetch(FILTER_URL, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify(nutzlast)
        }).then(function (r) { return r.json(); }).catch(function () {
            return { ok: false, meldung: 'Filter konnten nicht gespeichert werden (Verbindung).' };
        });
    }
    function listeBauen(speicher, j) {
        var liste = document.getElementById('lm-filterliste');
        if (!liste) { return; }
        while (liste.firstChild) { liste.removeChild(liste.firstChild); }
        var darfFreigeben = !!j.darf_freigeben;
        speicher.dataset.standardId = j.standard_id || '';
        if (!j.filter || !j.filter.length) {
            liste.appendChild(element('li', 'dezent lm-filter-leer', 'Noch keine gespeicherten Filter – Suche und Chips setzen, dann „Filter speichern“.'));
            return;
        }
        j.filter.forEach(function (f) {
            var li = element('li', (f.geteilt ? 'geteilt' : '') + (f.standard ? ' standard' : ''));
            li.dataset.id = f.id; li.dataset.name = f.name; li.dataset.geteilt = f.geteilt ? '1' : '';
            li.dataset.werte = JSON.stringify(f.werte || {});
            var anwendenKnopf = element('button', 'lm-filter-anwenden', f.name);
            anwendenKnopf.type = 'button'; anwendenKnopf.title = 'Filter anwenden';
            li.appendChild(anwendenKnopf);
            if (f.geteilt) {
                var b = element('span', 'abzeichen', 'alle');
                b.title = 'Für alle freigegeben' + (f.von_name ? ' von ' + f.von_name : '') + ' – schreibgeschützt';
                li.appendChild(document.createTextNode(' ')); li.appendChild(b);
            }
            if (f.standard) {
                var sb = element('span', 'abzeichen lm-filter-standard-badge', 'Standard');
                sb.title = 'Standard beim Öffnen';
                li.appendChild(document.createTextNode(' ')); li.appendChild(sb);
            }
            var werkzeuge = element('span', 'lm-filter-werkzeuge');
            var stern = element('button', 'lm-filter-standard' + (f.standard ? ' aktiv' : ''), '★');
            stern.type = 'button'; stern.setAttribute('aria-pressed', f.standard ? 'true' : 'false');
            stern.title = f.standard ? 'Standard beim Öffnen – Klick hebt ihn auf' : 'Als Standard beim Öffnen setzen';
            werkzeuge.appendChild(stern);
            function knopfMitSymbol(klasse, titel, quelle) {
                var k = element('button', klasse); k.type = 'button'; k.title = titel; k.setAttribute('aria-label', titel);
                var svg = svgKopie(quelle);
                if (svg) { k.appendChild(svg); } else { k.textContent = titel.charAt(0); }
                return k;
            }
            if (!f.geteilt) { werkzeuge.appendChild(knopfMitSymbol('lm-filter-umbenennen', 'Umbenennen', '#lm-filterspeicher .lm-filter-umbenennen svg, #lm-spaltenwahl summary svg')); }
            if (darfFreigeben && !f.geteilt) { werkzeuge.appendChild(knopfMitSymbol('lm-filter-freigeben', f.geteilt_id ? 'Freigabe für alle aktualisieren' : 'Für alle freigeben (schreibgeschützte Kopie bei allen Nutzern)', '#lm-filterspeicher .lm-filter-freigeben svg')); }
            if (f.loeschbar) { werkzeuge.appendChild(knopfMitSymbol('lm-filter-loeschen', f.geteilt ? 'Freigabe entfernen' : 'Filter löschen', '#lm-filterspeicher .lm-filter-loeschen svg')); }
            li.appendChild(werkzeuge);
            liste.appendChild(li);
        });
        var datalist = document.getElementById('dlg-filter-namen');
        if (datalist) {
            while (datalist.firstChild) { datalist.removeChild(datalist.firstChild); }
            j.filter.filter(function (f) { return !f.geteilt; }).forEach(function (f) {
                var o = document.createElement('option'); o.value = f.name; datalist.appendChild(o);
            });
        }
    }
    function filterAnwenden(form, speicher, li) {
        var werte = {};
        try { werte = JSON.parse(li.dataset.werte || '{}'); } catch (e) { werte = {}; }
        var s = steuerung(form);
        formLeeren(form);
        Object.keys(werte).forEach(function (k) {
            if (k === 'sort' || k === 'gruppen_zu') { return; }
            feldSetzen(form, k, werte[k]);
        });
        form.querySelectorAll('.lm-filterchip input[type=checkbox]').forEach(function (cb) {
            cb.closest('.lm-filterchip').classList.toggle('aktiv', cb.checked);
        });
        filterNameSetzen(form, li.dataset.name || '');
        var daten = lmDaten();
        var sortNeu = werte.sort && werte.sort.key ? werte.sort : null;
        var sortAlt = daten.sort && daten.sort.key ? daten.sort : null;
        var gleich = (!sortNeu && !sortAlt) || (sortNeu && sortAlt && sortNeu.key === sortAlt.key && (sortNeu.richtung || 'auf') === (sortAlt.richtung || 'auf'));
        var zu = Array.isArray(werte.gruppen_zu) ? werte.gruppen_zu : [];
        function danach() {
            s.laden();
            if (zu.length) {
                document.addEventListener('lm-sofort:geladen', function einmal() {
                    document.removeEventListener('lm-sofort:geladen', einmal);
                    document.querySelectorAll('[data-lm-sofort-ziel] details[data-gruppe], [data-lm-sofort-ziel] details[data-hv]').forEach(function (d) {
                        var key = d.dataset.gruppe || ('hv:' + d.dataset.hv);
                        d.open = zu.indexOf(key) < 0;
                    });
                });
            }
        }
        if (gleich || !sortNeu) { danach(); return; }
        fetch(SPALTEN_URL, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({ board: speicher.dataset.board, sort: sortNeu })
        }).then(function (r) { return r.json(); }).then(function (j) {
            if (j && j.ok) {
                var el = document.getElementById('lm-daten');
                if (el) { try { var d = JSON.parse(el.textContent); d.sort = j.sort; el.textContent = JSON.stringify(d); } catch (e) { /* egal */ } }
            }
        }).catch(function () { /* Sortierung bleibt */ }).then(danach);
    }
    document.querySelectorAll('.lm-filterspeicher').forEach(function (speicher) {
        var form = document.querySelector('form[data-lm-sofort][data-lm-sofort-filter="' + CSS.escape(speicher.dataset.board) + '"]')
            || speicher.closest('form[data-lm-sofort]');
        if (!form) { return; }
        var dialog = document.getElementById('dlg-filter');
        speicher.addEventListener('click', function (e) {
            var li = e.target.closest('li[data-id]');
            var knopf = e.target.closest('button');
            if (!knopf) { return; }
            e.preventDefault();
            if (knopf.id === 'lm-filter-speichern') {
                if (!dialog) { return; }
                var nameFeld = dialog.querySelector('input[name=name]');
                var stdFeld = dialog.querySelector('input[name=standard]');
                nameFeld.value = ''; stdFeld.checked = false;
                dialog.showModal(); nameFeld.focus();
                return;
            }
            if (knopf.id === 'lm-filter-zuruecksetzen') {
                formLeeren(form);
                feldSetzen(form, 'filter', '0');
                filterNameSetzen(form, '');
                speicher.removeAttribute('open');
                steuerung(form).laden();
                return;
            }
            if (!li) { return; }
            var id = li.dataset.id, name = li.dataset.name || '';
            if (knopf.classList.contains('lm-filter-anwenden')) {
                speicher.removeAttribute('open');
                filterAnwenden(form, speicher, li);
                return;
            }
            var nutzlast = null;
            if (knopf.classList.contains('lm-filter-standard')) {
                nutzlast = { aktion: 'standard', id: knopf.classList.contains('aktiv') ? null : id };
            } else if (knopf.classList.contains('lm-filter-umbenennen')) {
                var neu = window.prompt('Neuer Name für den Filter „' + name + '“:', name);
                if (neu === null || !neu.trim()) { return; }
                nutzlast = { aktion: 'umbenennen', id: id, name: neu.trim() };
            } else if (knopf.classList.contains('lm-filter-freigeben')) {
                if (!window.confirm('Filter „' + name + '“ für alle Nutzer freigeben? Die Kopie ist bei den anderen schreibgeschützt.')) { return; }
                nutzlast = { aktion: 'freigeben', id: id };
            } else if (knopf.classList.contains('lm-filter-loeschen')) {
                var geteilt = li.dataset.geteilt === '1';
                if (!window.confirm(geteilt ? 'Freigabe des Filters „' + name + '“ entfernen?' : 'Filter „' + name + '“ löschen?')) { return; }
                nutzlast = { aktion: geteilt ? 'freigabe_entfernen' : 'loeschen', id: id };
            }
            if (!nutzlast) { return; }
            filterPost(speicher, nutzlast).then(function (j) {
                melden(j.meldung, !j.ok);
                if (j.filter) { listeBauen(speicher, j); }
            });
        });
        if (dialog) {
            var dlgForm = dialog.querySelector('form');
            dlgForm.addEventListener('submit', function (e) {
                e.preventDefault();
                var name = dlgForm.querySelector('input[name=name]').value.trim();
                if (!name) { dlgForm.querySelector('input[name=name]').focus(); return; }
                var standard = dlgForm.querySelector('input[name=standard]').checked;
                dialog.close();
                filterPost(speicher, { aktion: 'speichern', name: name, standard: standard, werte: werteSammeln(form) })
                    .then(function (j) {
                        melden(j.meldung, !j.ok);
                        if (j.ok) { filterNameSetzen(form, name); }
                        if (j.filter) { listeBauen(speicher, j); }
                    });
            });
            var abbrechen = dlgForm.querySelector('button[value=abbrechen]');
            if (abbrechen) { abbrechen.addEventListener('click', function () { dialog.close(); }); }
        }
    });
    // Aufklappmenüs schließen sich beim Klick daneben (wie Spaltenwähler)
    document.addEventListener('click', function (e) {
        document.querySelectorAll('.lm-filterspeicher[open]').forEach(function (d) {
            if (!d.contains(e.target)) { d.removeAttribute('open'); }
        });
    });
})();
