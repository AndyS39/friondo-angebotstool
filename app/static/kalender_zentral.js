// v33 (PLAN_V20 Phase 169, Agent K): zentraler Planungskalender /kalender.
// Liest den Seitenkontext aus <script type="application/json" id="kz-kontext"> (Personen mit
// Gruppe, Vorbelegung, Raster), lädt die Einträge nachgelagert über GET /kalender/daten.json
// (von, bis, personen) und baut das Raster ausschließlich über DOM-Methoden (kein innerHTML
// mit Daten). Ansichten Tag | Woche | Monat, Sa/So einblendbar, Gruppen-Chips, Namenssuche
// (filtert lokal), Auswahl je Nutzer und Einstieg über POST /kalender/einstellung gemerkt.
// Drag & Drop: Tool-Termine mit verschiebbar = true → POST /kalender/verschieben; meldet der
// Server Konflikte (bestaetigung_noetig), fragt der Dialog #kz-konflikt nach. Doppelklick auf
// freie Fläche: Dialog #kz-neu mit Suche (/kalender/suche.json) → Link in den Termin-Dialog des
// Moduls mit vorbelegtem Datum und Person. Unter 600 px startet die Tagesansicht.
(function () {
    'use strict';
    const kontextEl = document.getElementById('kz-kontext');
    const raster = document.getElementById('kz-raster');
    if (!kontextEl || !raster) { return; }
    const K = JSON.parse(kontextEl.textContent || '{}');
    const rahmen = document.getElementById('kz-rahmen');
    const leer = document.getElementById('kz-leer');
    const status = document.getElementById('kz-status');
    const zeitraumEl = document.getElementById('kz-zeitraum');
    const datumFeld = document.getElementById('kz-datum');
    const sucheFeld = document.getElementById('kz-suche');
    const wochenendeFeld = document.getElementById('kz-wochenende');
    const nurPerson = document.getElementById('kz-nur-person');
    const WOCHENTAGE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
    const WOCHENTAGE_LANG = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];
    const MONATE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September',
                    'Oktober', 'November', 'Dezember'];
    const ZEILE = 30;          // px, siehe --kz-zeile
    const LANE = 26;           // px je Überlappungs-Zeile
    const MONAT_PUNKTE = 6;

    const zustand = {
        ansicht: K.auswahl.ansicht || 'woche',
        datum: K.auswahl.datum || K.heute,
        gruppen: new Set(K.auswahl.gruppen || []),
        wochenende: !!K.auswahl.wochenende,
        q: K.auswahl.q || '',
        person: K.auswahl.person || null,
        zu: new Set(),
        daten: null,
        laufendeNr: 0,
        drag: null,
        offen: null
    };
    const urlParameter = new URLSearchParams(location.search);
    if (window.innerWidth < 600 && !urlParameter.get('ansicht')) {
        zustand.ansicht = 'tag';
        document.querySelectorAll('[data-ansicht]').forEach(function (x) {
            const an = x.dataset.ansicht === 'tag';
            x.classList.toggle('on', an);
            x.setAttribute('aria-selected', an ? 'true' : 'false');
        });
    }
    const gruppenInfo = {};
    (K.gruppen || []).forEach(function (g) { gruppenInfo[g.key] = g; });
    const personenInfo = {};
    (K.personen || []).forEach(function (p) { personenInfo[p.id] = p; });

    // --- Hilfen ----------------------------------------------------------------------
    function el(tag, klasse, text) {
        const e = document.createElement(tag);
        if (klasse) { e.className = klasse; }
        if (text !== undefined && text !== null) { e.textContent = text; }
        return e;
    }
    function zwei(n) { return (n < 10 ? '0' : '') + n; }
    function tagAus(text) {
        const t = (text || '').slice(0, 10).split('-');
        return new Date(parseInt(t[0], 10), parseInt(t[1], 10) - 1, parseInt(t[2], 10));
    }
    function isoTag(d) { return d.getFullYear() + '-' + zwei(d.getMonth() + 1) + '-' + zwei(d.getDate()); }
    function isoZeit(d) { return isoTag(d) + 'T' + zwei(d.getHours()) + ':' + zwei(d.getMinutes()); }
    function zeitAus(text) {
        if (!text) { return null; }
        const d = tagAus(text);
        if (text.length >= 16) {
            d.setHours(parseInt(text.slice(11, 13), 10), parseInt(text.slice(14, 16), 10), 0, 0);
        }
        return d;
    }
    function plusTage(d, n) { const x = new Date(d.getTime()); x.setDate(x.getDate() + n); return x; }
    function kw(d) {
        const x = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
        const tag = x.getUTCDay() || 7;
        x.setUTCDate(x.getUTCDate() + 4 - tag);
        const jahrStart = new Date(Date.UTC(x.getUTCFullYear(), 0, 1));
        return Math.ceil(((x - jahrStart) / 86400000 + 1) / 7);
    }
    function datumText(d) { return zwei(d.getDate()) + '.' + zwei(d.getMonth() + 1) + '.'; }
    function uhr(d) { return zwei(d.getHours()) + ':' + zwei(d.getMinutes()); }
    function initialen(name) {
        const teile = (name || '').trim().split(/\s+/).filter(Boolean);
        if (!teile.length) { return '?'; }
        const a = teile[0].charAt(0);
        const b = teile.length > 1 ? teile[teile.length - 1].charAt(0) : teile[0].charAt(1);
        return (a + (b || '')).toUpperCase();
    }
    function meldung(text, fehler) {
        if (!status) { return; }
        status.textContent = text || '';
        status.classList.toggle('kz-fehler', !!fehler);
    }

    // --- Zeitraum und Personen ---------------------------------------------------------
    function zeitraum() {
        const d = tagAus(zustand.datum);
        if (zustand.ansicht === 'tag') { return {von: d, bis: d}; }
        if (zustand.ansicht === 'monat') {
            const von = new Date(d.getFullYear(), d.getMonth(), 1);
            const bis = new Date(d.getFullYear(), d.getMonth() + 1, 0);
            return {von: von, bis: bis};
        }
        const versatz = (d.getDay() + 6) % 7;
        const von = plusTage(d, -versatz);
        return {von: von, bis: plusTage(von, 6)};
    }
    function zeitraumText() {
        const z = zeitraum();
        const d = tagAus(zustand.datum);
        if (zustand.ansicht === 'tag') {
            return WOCHENTAGE_LANG[(d.getDay() + 6) % 7] + ', ' + datumText(d) + d.getFullYear();
        }
        if (zustand.ansicht === 'monat') { return MONATE[d.getMonth()] + ' ' + d.getFullYear(); }
        return WOCHENTAGE[0] + ' ' + datumText(z.von) + ' – ' + WOCHENTAGE[6] + ' ' + datumText(z.bis)
            + z.bis.getFullYear() + ' · KW ' + kw(z.von);
    }
    function gruppenPersonen() {
        return (K.personen || []).filter(function (p) {
            if (zustand.person && p.id !== zustand.person) { return false; }
            if (K.nur_lesen) { return true; }
            return zustand.gruppen.has(p.gruppe);
        });
    }
    function sichtbarePersonen() {
        const q = zustand.q.trim().toLowerCase();
        return gruppenPersonen().filter(function (p) {
            return !q || p.name.toLowerCase().indexOf(q) >= 0;
        });
    }
    function tageDerAnsicht() {
        const tage = (zustand.daten && zustand.daten.tage) || [];
        if (zustand.ansicht === 'tag' || zustand.wochenende) { return tage; }
        return tage.filter(function (t) { return !t.wochenende; });
    }

    // --- Laden -------------------------------------------------------------------------
    function laden() {
        const z = zeitraum();
        const ids = gruppenPersonen().map(function (p) { return p.id; });
        const nr = ++zustand.laufendeNr;
        raster.setAttribute('aria-busy', 'true');
        zeitraumEl.textContent = zeitraumText();
        if (datumFeld) { datumFeld.value = zustand.datum; }
        urlNachziehen();
        if (!ids.length) {
            zustand.daten = {tage: [], eintraege: []};
            rendern();
            return;
        }
        const url = K.daten_url + '?von=' + isoTag(z.von) + '&bis=' + isoTag(z.bis)
            + '&personen=' + ids.join(',') + '&ansicht=' + zustand.ansicht;
        fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
            .then(function (r) { return r.json(); })
            .then(function (daten) {
                if (nr !== zustand.laufendeNr) { return; }
                zustand.daten = daten;
                rendern();
                meldung((daten.eintraege || []).length + ' Einträge · ' + ids.length + ' Personen'
                    + (daten.dauer_ms !== undefined ? ' · ' + daten.dauer_ms + ' ms' : ''));
            })
            .catch(function () {
                if (nr !== zustand.laufendeNr) { return; }
                raster.setAttribute('aria-busy', 'false');
                meldung('Einträge konnten nicht geladen werden.', true);
            });
    }
    function urlNachziehen() {
        const p = new URLSearchParams();
        if (K.einstieg && K.einstieg !== 'eigene') { p.set('gruppe', K.einstieg); }
        p.set('ansicht', zustand.ansicht);
        p.set('datum', zustand.datum);
        if (zustand.q) { p.set('q', zustand.q); }
        if (zustand.person) { p.set('person', String(zustand.person)); }
        if (zustand.wochenende) { p.set('wochenende', '1'); }
        try { history.replaceState(null, '', location.pathname + '?' + p.toString()); } catch (e) { /* egal */ }
    }
    function einstellungSpeichern(felder) {
        if (K.nur_lesen || !K.einstellung_url) { return; }
        const daten = Object.assign({einstieg: K.einstieg}, felder);
        fetch(K.einstellung_url, {method: 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify(daten)}).catch(function () { /* still */ });
    }

    // --- Rendern -----------------------------------------------------------------------
    function eintraegeFuer(personId, tagIso) {
        const alle = (zustand.daten && zustand.daten.eintraege) || [];
        const tagVon = tagAus(tagIso);
        const tagBis = plusTage(tagVon, 1);
        return alle.filter(function (e) {
            if (e.personen.indexOf(personId) < 0) { return false; }
            const b = zeitAus(e.beginn);
            const en = zeitAus(e.ende) || plusTage(b, 0);
            return b < tagBis && en > tagVon;
        });
    }
    function tooltip(e) {
        const b = zeitAus(e.beginn), en = zeitAus(e.ende);
        const teile = [e.art_name];
        if (e.ganztaegig) {
            teile.push(datumText(b) + (en && plusTage(b, 1) < en ? ' – ' + datumText(plusTage(en, -1)) : ''));
        } else {
            teile.push(datumText(b) + ' ' + uhr(b) + (en ? '–' + uhr(en) : ''));
        }
        if (e.kunde) { teile.push(e.kunde); }
        if (e.ort) { teile.push(e.ort); }
        if (e.text && e.text !== e.art_name) { teile.push(e.text); }
        const namen = e.personen.map(function (id) { return personenInfo[id] ? personenInfo[id].name : ''; })
            .filter(Boolean);
        if (namen.length > 1) { teile.push('Personen: ' + namen.join(', ')); }
        if (e.verschiebbar) { teile.push('ziehen zum Verschieben'); }
        return teile.join(' · ');
    }
    function eintragElement(e, lane, links, breite) {
        const a = el(e.link ? 'a' : 'div', 'kz-eintrag ' + e.farbe_klasse + (e.ganztaegig ? ' kz-ganz' : '')
            + (e.link ? '' : ' kz-ohne-link'));
        if (e.link) { a.href = e.link; }
        a.style.left = links + '%';
        a.style.width = Math.max(breite, 1.5) + '%';
        a.style.top = (2 + lane * LANE) + 'px';
        a.title = tooltip(e);
        a.dataset.key = e.key;
        const b = zeitAus(e.beginn);
        if (!e.ganztaegig) { a.appendChild(el('span', 'kz-zeit', uhr(b))); }
        if (e.quelle === 'belegt' || e.quelle === 'abwesenheit' || e.art === 'sperrzeit') {
            a.appendChild(el('span', '', e.text || e.art_name));
        } else {
            a.appendChild(el('b', '', e.kunde || e.text || e.art_name));
            if (e.kunde && e.ort) { a.appendChild(el('span', 'kz-ort', e.ort)); }
            if (e.kunde && e.art !== 'vot' && e.text) { a.appendChild(el('span', 'kz-ort', e.art_name)); }
        }
        if (e.verschiebbar && !K.nur_lesen) {
            a.draggable = true;
            a.addEventListener('dragstart', function (ev) { dragStart(ev, e, a); });
            a.addEventListener('dragend', function () { a.classList.remove('kz-zieht'); zustand.drag = null; });
        }
        return a;
    }
    function lanesBerechnen(liste, tagVon, tagBis) {
        // Überlappungen → Lane je Eintrag (sortiert nach Beginn)
        const r = zustand.daten.raster;
        const sortiert = liste.slice().sort(function (x, y) { return x.beginn < y.beginn ? -1 : 1; });
        const enden = [];
        return sortiert.map(function (e) {
            const b = zeitAus(e.beginn), en = zeitAus(e.ende);
            let von = e.ganztaegig ? r.von : Math.max(r.von, b < tagVon ? r.von : b.getHours() * 60 + b.getMinutes());
            let bis = e.ganztaegig ? r.bis : Math.min(r.bis, !en || en >= tagBis ? r.bis : en.getHours() * 60 + en.getMinutes());
            if (bis <= von) { bis = Math.min(r.bis, von + r.schritt); }
            if (von >= r.bis) { von = r.bis - r.schritt; bis = r.bis; }
            let lane = 0;
            while (lane < enden.length && enden[lane] > von) { lane++; }
            enden[lane] = bis;
            return {e: e, lane: lane, von: von, bis: bis};
        });
    }
    function namensZelle(p, kopf) {
        const z = el('div', 'kz-zelle kz-name' + (kopf ? ' kz-kopfzelle' : ''));
        if (kopf) { z.textContent = 'Mitarbeiter'; return z; }
        const av = el('span', 'avatar avatar-' + ((p.id % 8) + 1), initialen(p.name));
        av.title = p.name;
        z.appendChild(av);
        const t = el('span', 'kz-name-text');
        t.appendChild(el('b', '', p.name));
        t.appendChild(el('small', '', p.rolle || p.gruppe_name));
        z.appendChild(t);
        return z;
    }
    function gruppenKopf(gruppe, anzahl) {
        const g = el('div', 'kz-gruppenkopf' + (zustand.zu.has(gruppe) ? ' zu' : ''));
        g.appendChild(document.createTextNode(gruppenInfo[gruppe] ? gruppenInfo[gruppe].name : gruppe));
        g.appendChild(el('span', 'kz-zahl', String(anzahl)));
        g.setAttribute('role', 'button');
        g.tabIndex = 0;
        const umschalten = function () {
            if (zustand.zu.has(gruppe)) { zustand.zu.delete(gruppe); } else { zustand.zu.add(gruppe); }
            rendern();
        };
        g.addEventListener('click', umschalten);
        g.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); umschalten(); } });
        return g;
    }
    function rendern() {
        raster.setAttribute('aria-busy', 'false');
        while (raster.firstChild) { raster.removeChild(raster.firstChild); }
        const personen = sichtbarePersonen();
        const tage = tageDerAnsicht();
        raster.className = 'kz-raster kz-ansicht-' + zustand.ansicht;
        raster.style.setProperty('--kz-tage', String(Math.max(tage.length, 1)));
        if (leer) { leer.hidden = personen.length > 0; }
        if (!personen.length || !zustand.daten) { return; }
        const r = zustand.daten.raster || {von: 420, bis: 1080, schritt: 15};
        const stunden = Math.max(1, (r.bis - r.von) / 60);
        raster.style.setProperty('--kz-stunde', (100 / stunden) + '%');
        // Kopfzeile
        raster.appendChild(namensZelle(null, true));
        tage.forEach(function (t) {
            const d = tagAus(t.datum);
            const z = el('div', 'kz-zelle kz-kopfzelle' + (t.heute ? ' kz-heute' : '') + (t.wochenende ? ' kz-we' : ''));
            z.appendChild(el('span', '', (zustand.ansicht === 'monat' ? WOCHENTAGE[(d.getDay() + 6) % 7] + ' ' + d.getDate()
                : WOCHENTAGE[(d.getDay() + 6) % 7] + ' ' + datumText(d))));
            if (zustand.ansicht !== 'monat') {
                const st = el('span', 'kz-stunden');
                const schritt = zustand.ansicht === 'tag' ? 1 : Math.max(1, Math.round(stunden / 3));
                for (let h = r.von / 60; h <= r.bis / 60; h += schritt) {
                    st.appendChild(el('span', '', zwei(Math.floor(h)) + ':' + zwei(Math.round((h % 1) * 60))));
                }
                z.appendChild(st);
            }
            raster.appendChild(z);
        });
        // Zeilen je Gruppe
        const reihenfolge = (K.gruppen || []).map(function (g) { return g.key; });
        reihenfolge.forEach(function (gruppe) {
            const der = personen.filter(function (p) { return p.gruppe === gruppe; });
            if (!der.length) { return; }
            raster.appendChild(gruppenKopf(gruppe, der.length));
            if (zustand.zu.has(gruppe)) { return; }
            der.forEach(function (p) {
                const zellen = [];
                let maxLanes = 1;
                tage.forEach(function (t) {
                    const liste = eintraegeFuer(p.id, t.datum);
                    if (zustand.ansicht === 'monat') {
                        zellen.push(monatsZelle(p, t, liste));
                        return;
                    }
                    const tagVon = tagAus(t.datum), tagBis = plusTage(tagVon, 1);
                    const z = el('div', 'kz-zelle kz-tag kz-frei' + (t.wochenende ? ' kz-we' : '') + (t.heute ? ' kz-heute-tag' : ''));
                    z.dataset.person = String(p.id);
                    z.dataset.datum = t.datum;
                    const lanes = lanesBerechnen(liste, tagVon, tagBis);
                    lanes.forEach(function (x) {
                        const links = ((x.von - r.von) / (r.bis - r.von)) * 100;
                        const breite = ((x.bis - x.von) / (r.bis - r.von)) * 100;
                        z.appendChild(eintragElement(x.e, x.lane, links, breite));
                        maxLanes = Math.max(maxLanes, x.lane + 1);
                    });
                    dropZiel(z, p, t.datum, liste);
                    zellen.push(z);
                });
                const name = namensZelle(p, false);
                const hoehe = (4 + maxLanes * LANE) + 'px';
                name.style.minHeight = hoehe;
                raster.appendChild(name);
                zellen.forEach(function (z) { z.style.minHeight = hoehe; raster.appendChild(z); });
            });
        });
    }
    function monatsZelle(p, t, liste) {
        const z = el('div', 'kz-monat-zelle' + (t.wochenende ? ' kz-we' : ''));
        z.dataset.person = String(p.id);
        z.dataset.datum = t.datum;
        const abwesend = liste.some(function (e) { return e.quelle === 'abwesenheit'; });
        if (abwesend) { z.classList.add('kz-abwesend'); z.title = liste.filter(function (e) { return e.quelle === 'abwesenheit'; }).map(tooltip).join(' · '); }
        const sichtbar = liste.filter(function (e) { return e.quelle !== 'abwesenheit'; });
        sichtbar.slice(0, MONAT_PUNKTE).forEach(function (e) {
            const punkt = el(e.link ? 'a' : 'span', 'kz-punkt ' + e.farbe_klasse);
            if (e.link) { punkt.href = e.link; }
            punkt.title = tooltip(e);
            punkt.dataset.key = e.key;
            if (e.verschiebbar && !K.nur_lesen) {
                punkt.draggable = true;
                punkt.addEventListener('dragstart', function (ev) { dragStart(ev, e, punkt); });
                punkt.addEventListener('dragend', function () { punkt.classList.remove('kz-zieht'); zustand.drag = null; });
            }
            z.appendChild(punkt);
        });
        if (sichtbar.length > MONAT_PUNKTE) { z.appendChild(el('span', 'kz-mehr', '+' + (sichtbar.length - MONAT_PUNKTE))); }
        dropZiel(z, p, t.datum, liste);
        return z;
    }

    // --- Drag & Drop -------------------------------------------------------------------
    function dragStart(ev, e, element) {
        zustand.drag = {eintrag: e, element: element, anteil: 0};
        const breite = element.offsetWidth || 1;
        zustand.drag.anteil = Math.max(0, Math.min(1, (ev.offsetX || 0) / breite));
        element.classList.add('kz-zieht');
        try {
            ev.dataTransfer.effectAllowed = 'move';
            ev.dataTransfer.setData('text/plain', e.key);
        } catch (x) { /* egal */ }
    }
    function dropZiel(zelle, p, datum, liste) {
        if (K.nur_lesen) { return; }
        zelle.addEventListener('dragover', function (ev) {
            if (!zustand.drag) { return; }
            ev.preventDefault();
            zelle.classList.add('drop');
        });
        zelle.addEventListener('dragleave', function () { zelle.classList.remove('drop'); });
        zelle.addEventListener('drop', function (ev) {
            ev.preventDefault();
            zelle.classList.remove('drop');
            if (!zustand.drag) { return; }
            const d = zustand.drag;
            zustand.drag = null;
            const beginn = neuerBeginn(d.eintrag, d.anteil, zelle, ev, datum);
            verschieben(d.eintrag, beginn, p.id, false);
        });
        zelle.addEventListener('dblclick', function (ev) {
            if (ev.target !== zelle) { return; }
            const r = zustand.daten.raster;
            let minute = r.von;
            if (zustand.ansicht !== 'monat') {
                const rect = zelle.getBoundingClientRect();
                minute = r.von + ((ev.clientX - rect.left) / Math.max(rect.width, 1)) * (r.bis - r.von);
            }
            minute = Math.round(minute / r.schritt) * r.schritt;
            const beginn = tagAus(datum);
            beginn.setHours(Math.floor(minute / 60), minute % 60, 0, 0);
            neuerTermin(p, beginn);
        });
    }
    function neuerBeginn(e, anteil, zelle, ev, datum) {
        const alt = zeitAus(e.beginn);
        const neu = tagAus(datum);
        if (e.ganztaegig) { return isoZeit(neu); }
        if (zustand.ansicht === 'monat') {
            neu.setHours(alt.getHours(), alt.getMinutes(), 0, 0);
            return isoZeit(neu);
        }
        const r = zustand.daten.raster;
        const rect = zelle.getBoundingClientRect();
        const minuteZeiger = r.von + ((ev.clientX - rect.left) / Math.max(rect.width, 1)) * (r.bis - r.von);
        const en = zeitAus(e.ende);
        const dauer = en ? Math.max(r.schritt, (en - alt) / 60000) : 60;
        let minute = Math.round((minuteZeiger - anteil * dauer) / r.schritt) * r.schritt;
        minute = Math.max(0, Math.min(24 * 60 - r.schritt, minute));
        neu.setHours(Math.floor(minute / 60), minute % 60, 0, 0);
        return isoZeit(neu);
    }
    function verschieben(e, beginn, personId, bestaetigt) {
        const daten = {quelle: e.quelle, id: e.id, beginn: beginn, person_id: personId, bestaetigt: bestaetigt};
        meldung('Verschiebe …');
        fetch(K.verschieben_url, {method: 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: JSON.stringify(daten)})
            .then(function (r) { return r.json(); })
            .then(function (antwort) {
                if (antwort.bestaetigung_noetig) {
                    konfliktDialog(antwort.konflikte || [], e, beginn, function () { verschieben(e, beginn, personId, true); });
                    meldung('');
                    return;
                }
                if (!antwort.ok) {
                    meldung(antwort.meldung || 'Verschieben nicht möglich.', true);
                    return;
                }
                meldung(antwort.meldung || 'Termin verschoben.');
                laden();
            })
            .catch(function () { meldung('Verschieben fehlgeschlagen (Verbindung).', true); });
    }
    function konfliktDialog(konflikte, e, beginn, weiter) {
        const dlg = document.getElementById('kz-konflikt');
        const liste = document.getElementById('kz-konflikt-liste');
        const ziel = document.getElementById('kz-konflikt-ziel');
        if (!dlg || !liste) { if (window.confirm('Konflikte: ' + konflikte.join('; ') + '\nTrotzdem verschieben?')) { weiter(); } return; }
        while (liste.firstChild) { liste.removeChild(liste.firstChild); }
        konflikte.forEach(function (k) { liste.appendChild(el('li', '', k)); });
        const b = zeitAus(beginn);
        ziel.textContent = (e.kunde || e.art_name) + ' → ' + WOCHENTAGE[(b.getDay() + 6) % 7] + ' ' + datumText(b)
            + (e.ganztaegig ? '' : ' ' + uhr(b));
        const ja = document.getElementById('kz-konflikt-ja');
        const nein = document.getElementById('kz-konflikt-nein');
        const schliessen = function () { if (dlg.open) { dlg.close(); } ja.onclick = null; nein.onclick = null; };
        ja.onclick = function () { schliessen(); weiter(); };
        nein.onclick = function () { schliessen(); meldung('Verschieben abgebrochen.'); };
        if (typeof dlg.showModal === 'function') { dlg.showModal(); } else { dlg.setAttribute('open', ''); }
    }

    // --- Doppelklick: neuer Termin über die Suche des Moduls --------------------------------
    function neuerTermin(p, beginn) {
        if (K.nur_lesen) { return; }
        const art = (gruppenInfo[p.gruppe] && gruppenInfo[p.gruppe].neu_art) || 'lead';
        const dlg = document.getElementById('kz-neu');
        const titel = document.getElementById('kz-neu-titel');
        const text = document.getElementById('kz-neu-text');
        const feld = document.getElementById('kz-neu-suche');
        const liste = document.getElementById('kz-neu-liste');
        if (!dlg || !feld || !liste) { return; }
        const artText = {lead: 'Vor-Ort-/Vorab-Termin (Terminassistent)', projekt: 'Projekt-Termin (Projektakte)',
                         vorgang: 'Service-Einsatz (Vorgangsakte)'}[art] || 'Termin';
        titel.textContent = 'Neuer Termin – ' + p.name;
        text.textContent = artText + ' am ' + WOCHENTAGE_LANG[(beginn.getDay() + 6) % 7] + ', ' + datumText(beginn)
            + beginn.getFullYear() + ' um ' + uhr(beginn) + ' Uhr – ' + (art === 'projekt' ? 'Projekt' : 'Kunde')
            + ' wählen, dann öffnet sich der Termin-Dialog des Moduls.';
        feld.placeholder = art === 'projekt' ? 'Projektnummer oder Kunde …' : 'Kunde suchen (Name, Ort, Telefon) …';
        feld.value = '';
        while (liste.firstChild) { liste.removeChild(liste.firstChild); }
        zustand.offen = {art: art, person: p.id, beginn: isoZeit(beginn)};
        if (typeof dlg.showModal === 'function') { dlg.showModal(); } else { dlg.setAttribute('open', ''); }
        feld.focus();
    }
    function neuSuchen() {
        const feld = document.getElementById('kz-neu-suche');
        const liste = document.getElementById('kz-neu-liste');
        if (!zustand.offen || !feld || !liste) { return; }
        const q = feld.value.trim();
        if (q.length < 2) { while (liste.firstChild) { liste.removeChild(liste.firstChild); } return; }
        const o = zustand.offen;
        const url = K.suche_url + '?q=' + encodeURIComponent(q) + '&art=' + o.art + '&person=' + o.person
            + '&beginn=' + encodeURIComponent(o.beginn);
        fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
            .then(function (r) { return r.json(); })
            .then(function (antwort) {
                if (feld.value.trim() !== q) { return; }
                while (liste.firstChild) { liste.removeChild(liste.firstChild); }
                const treffer = antwort.treffer || [];
                if (!treffer.length) { liste.appendChild(el('div', 'kz-neu-leer', 'Keine Treffer.')); return; }
                treffer.forEach(function (t) {
                    const a = el('a', 'kz-neu-treffer');
                    a.href = t.link;
                    a.setAttribute('role', 'option');
                    a.appendChild(el('b', '', t.name));
                    a.appendChild(el('small', '', [t.ort, t.zusatz].filter(Boolean).join(' · ')));
                    liste.appendChild(a);
                });
            })
            .catch(function () { /* still */ });
    }

    // --- Bedienelemente -----------------------------------------------------------------
    document.querySelectorAll('[data-ansicht]').forEach(function (b) {
        b.addEventListener('click', function () {
            zustand.ansicht = b.dataset.ansicht;
            document.querySelectorAll('[data-ansicht]').forEach(function (x) {
                x.classList.toggle('on', x === b);
                x.setAttribute('aria-selected', x === b ? 'true' : 'false');
            });
            einstellungSpeichern({ansicht: zustand.ansicht});
            laden();
        });
    });
    document.querySelectorAll('[data-schritt]').forEach(function (b) {
        b.addEventListener('click', function () {
            const n = parseInt(b.dataset.schritt, 10);
            const d = tagAus(zustand.datum);
            if (zustand.ansicht === 'monat') { d.setMonth(d.getMonth() + n, 1); }
            else { d.setDate(d.getDate() + n * (zustand.ansicht === 'woche' ? 7 : 1)); }
            zustand.datum = isoTag(d);
            laden();
        });
    });
    document.querySelectorAll('[data-heute]').forEach(function (b) {
        b.addEventListener('click', function () { zustand.datum = K.heute || isoTag(new Date()); laden(); });
    });
    if (datumFeld) {
        datumFeld.addEventListener('change', function () {
            if (datumFeld.value) { zustand.datum = datumFeld.value; laden(); }
        });
    }
    document.querySelectorAll('.kz-gruppe input').forEach(function (cb) {
        cb.addEventListener('change', function () {
            const chip = cb.closest('.kz-gruppe');
            if (cb.checked) { zustand.gruppen.add(cb.value); } else { zustand.gruppen.delete(cb.value); }
            if (chip) { chip.classList.toggle('on', cb.checked); }
            einstellungSpeichern({gruppen: Array.from(zustand.gruppen)});
            laden();
        });
    });
    document.querySelectorAll('[data-gruppen-alle], [data-gruppen-keine]').forEach(function (b) {
        b.addEventListener('click', function () {
            const alle = b.hasAttribute('data-gruppen-alle');
            document.querySelectorAll('.kz-gruppe input').forEach(function (cb) {
                if (cb.disabled) { return; }
                cb.checked = alle;
                const chip = cb.closest('.kz-gruppe');
                if (chip) { chip.classList.toggle('on', alle); }
                if (alle) { zustand.gruppen.add(cb.value); } else { zustand.gruppen.delete(cb.value); }
            });
            einstellungSpeichern({gruppen: Array.from(zustand.gruppen)});
            laden();
        });
    });
    if (wochenendeFeld) {
        wochenendeFeld.addEventListener('change', function () {
            zustand.wochenende = wochenendeFeld.checked;
            const chip = wochenendeFeld.closest('.pj-chip');
            if (chip) { chip.classList.toggle('on', zustand.wochenende); }
            einstellungSpeichern({wochenende: zustand.wochenende});
            urlNachziehen();
            rendern();
        });
    }
    if (sucheFeld) {
        let timer = null;
        sucheFeld.addEventListener('input', function () {
            clearTimeout(timer);
            timer = setTimeout(function () { zustand.q = sucheFeld.value; urlNachziehen(); rendern(); }, 150);
        });
    }
    if (nurPerson) {
        const name = document.getElementById('kz-nur-person-name');
        const p = personenInfo[zustand.person];
        if (name) { name.textContent = p ? p.name : ('#' + zustand.person); }
        const x = nurPerson.querySelector('.kz-chip-x');
        if (x) {
            x.addEventListener('click', function () {
                zustand.person = null;
                nurPerson.remove();
                laden();
            });
        }
    }
    const neuFeld = document.getElementById('kz-neu-suche');
    if (neuFeld) {
        let timer = null;
        neuFeld.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(neuSuchen, 200); });
    }
    const neuSchliessen = document.getElementById('kz-neu-schliessen');
    if (neuSchliessen) {
        neuSchliessen.addEventListener('click', function () {
            const dlg = document.getElementById('kz-neu');
            zustand.offen = null;
            if (dlg && dlg.open) { dlg.close(); } else if (dlg) { dlg.removeAttribute('open'); }
        });
    }
    document.querySelectorAll('dialog.kz-dialog').forEach(function (dlg) {
        dlg.addEventListener('click', function (ev) { if (ev.target === dlg) { dlg.close(); zustand.offen = null; } });
    });

    laden();
})();
