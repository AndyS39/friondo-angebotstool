/* Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 105) – Icon-Leiste + Boards.
   Wird über das Makro lm_nav (leadmanagement/_nav.html) auf jeder Modulseite
   geladen (defer). Vanilla JS, kein Framework.
   1. Icon-Leiste: Höhe der Kopfleiste als CSS-Variable --lm-kopf, damit die
      fixe Leiste exakt darunter beginnt (Fallback in lead_v2.css); v25
      zusätzlich --lm-kopf-fest = Höhe der Kopfzeile, falls sie sticky/fixed
      ist (sonst 0) – darunter bleibt der Filterblock der Boards stehen.
   2. Boards (data-lm-board): Inline-Bearbeitung per fetch
      (POST /lead-management/boards/zeile/<id>, JSON {feld, wert, …} →
      {ok, meldung, zeile_html}), Status-Dialog mit Pflichtgründen
      (zurueckgestellt: Datum + Grund, unqualifiziert: Grund, verloren: Grund,
      Freitext bei Sonstiges), Markier-Kästchen + „alle sichtbaren markieren“
      + Sammelaktions-Leiste (ein Dialog für alle), Schnellsuche über die
      sichtbaren Zeilen.
   3. v25 (PLAN_LEAD_V3 Phase 118) Spalten je Nutzer (POST /lead-management/
      boards/spalten, nur der angemeldete Nutzer): Klick auf den Spaltenkopf
      sortiert auf/ab und merkt die Sortierung ({sort}), Stift im Spaltenkopf
      benennt um ({umbenennen}, leer = Standard), HTML5 Drag & Drop am
      Spaltenkopf verschiebt die Spalte (Platzhalter beim Ziehen, Speichern
      per fetch nach dem Loslassen, {spalten}), Spaltenwähler „Spalten“ in
      der Filterleiste blendet ein/aus (Häkchen → {spalten} → Neuladen),
      „Zurücksetzen“ stellt den Standard her ({zuruecksetzen}). Sticky-
      Geometrie: der Filterblock bleibt oben stehen, der Tabellen-Container
      (.lm-tabellen) scrollt horizontal und vertikal, sein Platz wird aus
      Fensterhöhe − Kopfzeile − Filterblock berechnet (--lm-tabellen-hoehe).
      Infoabend und Handelsvertreter-Ansicht tragen kein data-lm-board (eigene
      Skripte lm_info.js / lm_hv.js für Zeilen und Sammelaktionen), sondern
      data-lm-spalten-board="info|handelsvertreter": dann laufen hier NUR die
      Spaltenwerkzeuge (Teil 3) und die Sticky-Geometrie; Spaltenköpfe mit
      draggable="false" (Kundenname, im Infoabend auch Status) sind kein
      Ablageziel – ihre Position ist serverseitig fest. */
(function () {
    'use strict';
    if (window.__lmBoardsGeladen) { return; }
    window.__lmBoardsGeladen = true;

    // ---------- 1. Icon-Leiste ----------
    function kopfHoehe() {
        const kopf = document.querySelector('.kopfleiste');
        const wurzel = document.documentElement.style;
        if (!kopf || document.body.classList.contains('einbett')) {
            wurzel.setProperty('--lm-kopf-fest', '0px');
            return;
        }
        wurzel.setProperty('--lm-kopf', kopf.offsetHeight + 'px');
        const lage = window.getComputedStyle(kopf).position;
        wurzel.setProperty('--lm-kopf-fest', (lage === 'sticky' || lage === 'fixed') ? kopf.offsetHeight + 'px' : '0px');
    }
    kopfHoehe();
    window.addEventListener('resize', kopfHoehe);
    window.addEventListener('load', kopfHoehe);
    // Rückfall für Browser ohne :has(): Platz für die Leiste über eine Body-Klasse
    if (document.querySelector('.lm-leiste') && !document.body.classList.contains('einbett')) {
        document.body.classList.add('lm-mit-leiste');
    }
    // „Mehr …“ und der Spaltenwähler schließen sich beim Klick daneben
    document.addEventListener('click', function (e) {
        document.querySelectorAll('.lm-leiste-mehr[open], .lm-spaltenwahl[open]').forEach(function (d) {
            if (!d.contains(e.target)) { d.removeAttribute('open'); }
        });
    });

    // ---------- 2. Boards ----------
    const kopf = document.querySelector('[data-lm-board]');
    // v25: Infoabend/HV-Ansicht – nur Spaltenwerkzeuge (Teil 3) + Sticky-Geometrie
    const spaltenTraeger = document.querySelector('[data-lm-spalten-board]');
    if (!kopf && !spaltenTraeger) { return; }
    const board = kopf ? kopf.dataset.lmBoard : spaltenTraeger.dataset.lmSpaltenBoard;
    const nurSpalten = !kopf;
    let daten = { gruende: {}, status: [], sort: null, spalten: [] };
    try { daten = Object.assign(daten, JSON.parse(document.getElementById('lm-daten').textContent)); } catch (e) { /* leer */ }
    const statusInfo = {};
    (daten.status || []).forEach(function (s) { statusInfo[s.key] = s; });

    const meldungEl = document.getElementById('lm-meldung') || document.getElementById('li-meldung');
    let meldungTimer = null;
    function melden(text, fehler) {
        if (!meldungEl) { return; }
        meldungEl.textContent = text || '';
        meldungEl.classList.toggle('fehler', !!fehler);
        meldungEl.hidden = !text;
        clearTimeout(meldungTimer);
        if (text && !fehler) { meldungTimer = setTimeout(function () { meldungEl.hidden = true; }, 6000); }
    }

    // ---- Zähler der Gruppenköpfe nach Zeilenänderung
    function zaehlerAktualisieren() {
        document.querySelectorAll('details.lm-gruppe').forEach(function (g) {
            const n = g.querySelectorAll('tbody tr[data-vorgang]').length;
            const z = g.querySelector('summary .n');
            if (z) { z.textContent = n; }
        });
    }

    // ---- fetch: Zeile ändern
    async function zeileSenden(vorgangId, nutzlast, zeile, danach) {
        nutzlast.board = board;
        let antwort;
        try {
            const r = await fetch('/lead-management/boards/zeile/' + vorgangId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(nutzlast)
            });
            antwort = await r.json();
        } catch (e) {
            melden('Speichern fehlgeschlagen (Verbindung).', true);
            if (danach) { danach(false); }
            return null;
        }
        if (antwort.ok && zeile) {
            if (antwort.zeile_html) {
                const ziel = zeile.closest('details.lm-gruppe');
                const neueGruppe = antwort.gruppe;
                const tmp = document.createElement('tbody');
                tmp.innerHTML = antwort.zeile_html;
                const neu = tmp.firstElementChild;
                if (neueGruppe && ziel && ziel.dataset.gruppe !== neueGruppe) {
                    // Status steuert Gruppe (H2): Zeile wandert in die passende Gruppe
                    const zielGruppe = document.querySelector('details.lm-gruppe[data-gruppe="' + neueGruppe + '"]');
                    const tbody = zielGruppe ? zielGruppe.querySelector('tbody') : null;
                    zeile.remove();
                    if (tbody && neu) {
                        tbody.prepend(neu);
                        neu.classList.add('lm-neu-hier');
                        zielGruppe.open = true;
                    } else if (zielGruppe && neu) {
                        // Gruppe war leer: Tabelle fehlt – Seite neu laden
                        window.location.reload();
                        return antwort;
                    }
                } else if (neu) {
                    zeile.replaceWith(neu);
                    neu.classList.add('lm-geaendert');
                }
            } else if (antwort.verschoben) {
                zeile.remove();
                melden(antwort.meldung + ' ' + antwort.verschoben, false);
                zaehlerAktualisieren();
                if (danach) { danach(true); }
                return antwort;
            }
            zaehlerAktualisieren();
        }
        melden(antwort.meldung, !antwort.ok);
        if (danach) { danach(!!antwort.ok); }
        return antwort;
    }

    // ---- Status-Dialog (Pflichtgründe), gemeinsam für Inline und Sammelaktion
    const dlgStatus = document.getElementById('dlg-status');
    function statusDialog(ziel, ok, abbruch) {
        if (!dlgStatus) { ok({}); return; }
        const info = statusInfo[ziel] || {};
        const gruppe = info.grund || '';
        const form = dlgStatus.querySelector('form');
        const grundSel = form.querySelector('select[name=grund]');
        const bisFeld = form.querySelector('#dlg-status-bis-feld');
        const bis = form.querySelector('input[name=bis]');
        const text = form.querySelector('input[name=grund_text]');
        form.querySelector('#dlg-status-titel').textContent = 'Status „' + (info.label || ziel) + '“ setzen';
        form.querySelector('#dlg-status-hinweis').textContent =
            gruppe === 'zurueckgestellt' ? 'Zurückgestellt braucht ein Wiedervorlage-Datum und einen Grund (Blatt Gründe).'
            : gruppe === 'verloren' ? 'Verloren braucht einen Grund; alle offenen Angebote des Vorgangs werden mit diesem Grund auf Abgelehnt gesetzt.'
            : 'Grund aus der Steuerdatei (Blatt Gründe); bei „Sonstiges“ ist der Freitext Pflicht.';
        grundSel.innerHTML = '';
        (daten.gruende[gruppe] || []).forEach(function (g) {
            const o = document.createElement('option');
            o.value = g.grund; o.textContent = g.grund; o.dataset.freitext = g.freitext ? '1' : '';
            grundSel.appendChild(o);
        });
        bisFeld.hidden = gruppe !== 'zurueckgestellt';
        bis.value = '';
        text.value = '';
        if (gruppe === 'zurueckgestellt') {
            const d = new Date(); d.setDate(d.getDate() + 14);
            bis.value = d.toISOString().slice(0, 10);
        }
        function schliessen() {
            form.removeEventListener('submit', beiOk);
            abbrechenKnopf.removeEventListener('click', beiAbbruch);
            dlgStatus.removeEventListener('cancel', beiAbbruch);
            if (dlgStatus.open) { dlgStatus.close(); }
        }
        function beiOk(e) {
            e.preventDefault();
            const gewaehlt = grundSel.selectedOptions[0];
            if (!gewaehlt) { melden('Bitte einen Grund wählen.', true); return; }
            if (gewaehlt.dataset.freitext && !text.value.trim()) {
                text.focus(); text.setCustomValidity('Freitext ist bei diesem Grund Pflicht.');
                text.reportValidity(); text.setCustomValidity(''); return;
            }
            if (gruppe === 'zurueckgestellt' && !bis.value) { bis.focus(); bis.reportValidity(); return; }
            const werte = { grund: grundSel.value, grund_text: text.value.trim(), bis: bis.value };
            schliessen();
            ok(werte);
        }
        function beiAbbruch(e) {
            if (e) { e.preventDefault(); }
            schliessen();
            if (abbruch) { abbruch(); }
        }
        const abbrechenKnopf = form.querySelector('button[value=abbrechen]');
        form.addEventListener('submit', beiOk);
        abbrechenKnopf.addEventListener('click', beiAbbruch);
        dlgStatus.addEventListener('cancel', beiAbbruch);
        dlgStatus.showModal();
    }

    function statusWechsel(select) {
        const ziel = select.value;
        const zeile = select.closest('tr');
        const id = select.dataset.vorgang;
        const info = statusInfo[ziel] || {};
        const zuruecksetzen = function () { select.value = select.dataset.aktuell; };
        if (info.grund) {
            statusDialog(ziel, function (werte) {
                zeileSenden(id, Object.assign({ feld: 'status', wert: ziel }, werte), zeile,
                    function (ok) { if (!ok) { zuruecksetzen(); } });
            }, zuruecksetzen);
        } else {
            zeileSenden(id, { feld: 'status', wert: ziel }, zeile, function (ok) { if (!ok) { zuruecksetzen(); } });
        }
    }

    // ---- Inline-Felder (delegiert; Zeilen werden ersetzt) – nicht auf Infoabend/HV
    // (dort schreiben lm_info.js bzw. lm_hv.js über eigene Routen)
    if (!nurSpalten) {
        document.addEventListener('change', function (e) {
            const el = e.target.closest('.lm-inline');
            if (!el) { return; }
            const feld = el.dataset.feld;
            if (feld === 'status') { statusWechsel(el); return; }
            const zeile = el.closest('tr');
            zeileSenden(el.dataset.vorgang, { feld: feld, wert: el.value }, zeile);
        });
        // Notiz: Enter speichert (blur löst change aus)
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && e.target.classList && e.target.classList.contains('lm-notiz')) {
                e.preventDefault(); e.target.blur();
            }
        });
    }

    // ---- Sticky-Geometrie (v25): Filterblock bleibt stehen, Tabellen-Container scrollt
    const filterblock = document.getElementById('lm-filterblock');
    const tabellen = document.getElementById('lm-tabellen');
    function layoutAktualisieren() {
        if (!tabellen) { return; }
        if (window.innerWidth <= 900) { tabellen.style.removeProperty('--lm-tabellen-hoehe'); return; }
        const kopfFest = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--lm-kopf-fest')) || 0;
        const filterHoehe = filterblock ? filterblock.offsetHeight : 0;
        const hoehe = Math.max(240, window.innerHeight - kopfFest - filterHoehe - 28);
        tabellen.style.setProperty('--lm-tabellen-hoehe', hoehe + 'px');
    }
    layoutAktualisieren();
    window.addEventListener('resize', layoutAktualisieren);
    window.addEventListener('load', layoutAktualisieren);
    if (filterblock && window.ResizeObserver) {
        new ResizeObserver(function () { layoutAktualisieren(); }).observe(filterblock);
    }

    // ---- Markieren + Sammelaktionen (Boards; Infoabend/HV haben eigene Kästchen li-wahl)
    const sammelform = document.getElementById('lm-sammelform');
    function auswahl() { return Array.from(document.querySelectorAll('input.lm-wahl:checked')); }
    function sammelAktualisieren() {
        if (nurSpalten) { layoutAktualisieren(); return; }
        const n = auswahl().length;
        if (!sammelform) { return; }
        sammelform.hidden = n === 0;
        const z = document.getElementById('lm-sammel-anzahl');
        if (z) { z.textContent = n; }
        document.querySelectorAll('tr[data-vorgang]').forEach(function (tr) {
            const cb = tr.querySelector('input.lm-wahl');
            tr.classList.toggle('markiert', !!(cb && cb.checked));
        });
        document.querySelectorAll('input.lm-wahl-alle').forEach(function (kopfBox) {
            const tabelle = kopfBox.closest('table');
            const sichtbar = Array.from(tabelle.querySelectorAll('tbody tr[data-vorgang]'))
                .filter(function (tr) { return !tr.hidden; });
            const an = sichtbar.filter(function (tr) { const cb = tr.querySelector('input.lm-wahl'); return cb && cb.checked; });
            kopfBox.checked = sichtbar.length > 0 && an.length === sichtbar.length;
            kopfBox.indeterminate = an.length > 0 && an.length < sichtbar.length;
        });
        layoutAktualisieren();
    }
    document.addEventListener('change', function (e) {
        if (nurSpalten) { return; }
        if (e.target.classList.contains('lm-wahl-alle')) {
            const tabelle = e.target.closest('table');
            tabelle.querySelectorAll('tbody tr[data-vorgang]').forEach(function (tr) {
                if (tr.hidden) { return; }
                const cb = tr.querySelector('input.lm-wahl');
                if (cb) { cb.checked = e.target.checked; }
            });
            sammelAktualisieren();
        } else if (e.target.classList.contains('lm-wahl')) {
            sammelAktualisieren();
        }
    });
    const leeren = document.getElementById('lm-sammel-leeren');
    if (leeren) {
        leeren.addEventListener('click', function () {
            document.querySelectorAll('input.lm-wahl:checked').forEach(function (cb) { cb.checked = false; });
            sammelAktualisieren();
        });
    }
    if (sammelform) {
        const aktionSel = document.getElementById('lm-sammel-aktion');
        const statusWrap = sammelform.querySelector('.lm-sammel-status');
        function aktionUmschalten() {
            if (statusWrap) { statusWrap.hidden = aktionSel.value !== 'status'; }
        }
        if (aktionSel) { aktionSel.addEventListener('change', aktionUmschalten); aktionUmschalten(); }
        sammelform.addEventListener('submit', function (e) {
            if (auswahl().length === 0) { e.preventDefault(); melden('Keine Leads markiert.', true); return; }
            if (sammelform.dataset.bereit === '1') { sammelform.dataset.bereit = ''; return; }
            if (aktionSel && aktionSel.value === 'status') {
                const ziel = document.getElementById('lm-sammel-status').value;
                const info = statusInfo[ziel] || {};
                if (info.grund) {
                    e.preventDefault();
                    statusDialog(ziel, function (werte) {
                        sammelform.querySelector('input[name=grund]').value = werte.grund;
                        sammelform.querySelector('input[name=grund_text]').value = werte.grund_text;
                        sammelform.querySelector('input[name=bis]').value = werte.bis;
                        sammelform.dataset.bereit = '1';
                        sammelform.requestSubmit();
                    });
                    return;
                }
            }
            if (!window.confirm(auswahl().length + ' Lead(s) – Sammelaktion ausführen?')) { e.preventDefault(); }
        });
    }
    sammelAktualisieren();

    // ---- Schnellsuche über die sichtbaren Zeilen (Server-Filter bleibt per Enter)
    const suche = document.getElementById('lm-suche');
    if (suche && !nurSpalten) {
        let timer = null;
        suche.addEventListener('input', function () {
            clearTimeout(timer);
            timer = setTimeout(function () {
                const q = suche.value.trim().toLowerCase();
                const ziffern = q.replace(/[^\d+]/g, '');
                document.querySelectorAll('tr[data-vorgang]').forEach(function (tr) {
                    const text = tr.dataset.suche || '';
                    let treffer = !q || text.indexOf(q) >= 0;
                    if (!treffer && ziffern.length >= 4) {
                        treffer = text.replace(/[^\d+]/g, '').indexOf(ziffern) >= 0;
                    }
                    tr.hidden = !treffer;
                });
                sammelAktualisieren();
            }, 120);
        });
    }

    // ---------- 3. Spalten je Nutzer (v25) ----------
    async function spaltenSenden(nutzlast) {
        nutzlast.board = board;
        try {
            const r = await fetch('/lead-management/boards/spalten', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(nutzlast)
            });
            const j = await r.json();
            if (!j.ok) { melden(j.meldung || 'Spalten konnten nicht gespeichert werden.', true); return null; }
            if (j.spalten) { daten.spalten = j.spalten; }
            if ('sort' in j) { daten.sort = j.sort; }
            return j;
        } catch (e) {
            melden('Spalten konnten nicht gespeichert werden (Verbindung).', true);
            return null;
        }
    }
    function alleTabellen() { return Array.from(document.querySelectorAll('.lm-tabelle')); }
    function spaltenIndex(tabelle, key) {
        const koepfe = Array.from(tabelle.querySelectorAll('thead th'));
        return koepfe.findIndex(function (th) { return th.dataset.key === key; });
    }
    // sichtbare Reihenfolge aus der ersten Tabelle, dahinter die ausgeblendeten Spalten
    function aktuelleSpaltenliste() {
        const erste = alleTabellen()[0];
        const sichtbar = erste ? Array.from(erste.querySelectorAll('thead th[data-key]')).map(function (th) { return th.dataset.key; }) : [];
        const bekannt = {};
        (daten.spalten || []).forEach(function (sp) { bekannt[sp.key] = sp; });
        const liste = sichtbar.map(function (key) {
            const sp = bekannt[key] || { key: key, name: '' };
            return { key: key, sichtbar: true, name: sp.name || '' };
        });
        (daten.spalten || []).forEach(function (sp) {
            if (sichtbar.indexOf(sp.key) < 0) { liste.push({ key: sp.key, sichtbar: !!sp.sichtbar && sichtbar.length === 0, name: sp.name || '' }); }
        });
        return liste;
    }

    // ---- Sortierung je Spalte (A3): Klick auf den Spaltenkopf sortiert alle
    // Gruppen auf/ab und merkt die Spalte (v25); data-wert (ISO-Datum, Zahl) vor
    // Zelltext, deutsche Datumsangaben und Zahlen werden erkannt, sonst Text.
    function sortWert(td) {
        if (!td) { return ''; }
        if (td.dataset.wert !== undefined) { return td.dataset.wert; }
        const inp = td.querySelector('input.lm-notiz, select');
        if (inp) {
            return inp.tagName === 'SELECT'
                ? (inp.selectedOptions[0] ? inp.selectedOptions[0].textContent.trim() : '')
                : inp.value;
        }
        return td.textContent.replace(/\s+/g, ' ').trim();
    }
    function sortSchluessel(wert) {
        if (wert === '' || wert === null || wert === undefined) { return null; }
        const de = /^(?:\w{2}\s+)?(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2}))?/.exec(wert);
        if (de) { return de[3] + '-' + de[2] + '-' + de[1] + ' ' + (de[4] || '00') + ':' + (de[5] || '00'); }
        if (/^-?\d+([.,]\d+)?$/.test(wert)) { return parseFloat(wert.replace(',', '.')); }
        return wert.toLowerCase();
    }
    function tabelleSortieren(tabelle, key, absteigend) {
        const tbody = tabelle.querySelector('tbody');
        const index = spaltenIndex(tabelle, key);
        if (!tbody || index < 0) { return; }
        tabelle.querySelectorAll('thead th[aria-sort]').forEach(function (k) { k.removeAttribute('aria-sort'); });
        const th = tabelle.querySelectorAll('thead th')[index];
        if (th) { th.setAttribute('aria-sort', absteigend ? 'descending' : 'ascending'); }
        const zeilen = Array.from(tbody.querySelectorAll('tr[data-vorgang]'));
        zeilen.sort(function (a, b) {
            const ka = sortSchluessel(sortWert(a.children[index]));
            const kb = sortSchluessel(sortWert(b.children[index]));
            if (ka === null && kb === null) { return 0; }
            if (ka === null) { return 1; }          // leere Werte immer ans Ende
            if (kb === null) { return -1; }
            let v = 0;
            if (typeof ka === 'number' && typeof kb === 'number') { v = ka - kb; }
            else { v = String(ka).localeCompare(String(kb), 'de'); }
            return absteigend ? -v : v;
        });
        zeilen.forEach(function (tr) { tbody.appendChild(tr); });
    }
    document.addEventListener('click', function (e) {
        if (e.target.closest('.lm-th-stift, .lm-th-eingabe')) { return; }
        const th = e.target.closest('.lm-tabelle thead th[data-sort]');
        if (!th) { return; }
        const key = th.dataset.sort;
        const absteigend = th.getAttribute('aria-sort') === 'ascending';
        alleTabellen().forEach(function (t) { tabelleSortieren(t, key, absteigend); });
        spaltenSenden({ sort: { key: key, richtung: absteigend ? 'ab' : 'auf' } });
    });

    // ---- Umbenennen: Stift im Spaltenkopf → Eingabe im Kopf, Enter/Verlassen speichert,
    // Escape bricht ab; leer = Standardname. Gilt nur für den angemeldeten Nutzer.
    function kopfTexteSetzen(key, titel, name) {
        document.querySelectorAll('.lm-tabelle thead th[data-key="' + key + '"]').forEach(function (th) {
            const t = th.querySelector('.lm-th-text');
            if (t) { t.textContent = titel; }
            th.dataset.name = name || '';
            const fest = key === 'lead' || th.getAttribute('draggable') === 'false';
            th.title = titel + ' – Klick sortiert (auf/ab, wird gemerkt)' + (fest ? '' : ' · Ziehen verschiebt die Spalte');
        });
        const li = document.querySelector('#lm-spaltenliste li[data-key="' + key + '"] .lm-sp-name');
        if (li) { li.textContent = titel; }
    }
    document.addEventListener('click', function (e) {
        const stift = e.target.closest('.lm-th-stift');
        if (!stift) { return; }
        e.preventDefault(); e.stopPropagation();
        const th = stift.closest('th');
        if (!th || th.querySelector('.lm-th-eingabe')) { return; }
        const key = th.dataset.key;
        const textEl = th.querySelector('.lm-th-text');
        const eingabe = document.createElement('input');
        eingabe.type = 'text'; eingabe.className = 'lm-th-eingabe'; eingabe.maxLength = 60;
        eingabe.value = th.dataset.name || '';
        eingabe.placeholder = th.dataset.standard || '';
        eingabe.title = 'Eigener Spaltenname – leer = Standard „' + (th.dataset.standard || '') + '“';
        eingabe.setAttribute('aria-label', 'Spaltenname');
        const draggableVorher = th.getAttribute('draggable') || 'true';   // feste Spalten bleiben fest
        th.setAttribute('draggable', 'false');
        textEl.hidden = true; stift.hidden = true;
        th.insertBefore(eingabe, textEl);
        let fertig = false;
        async function abschliessen(speichern) {
            if (fertig) { return; }
            fertig = true;
            const neu = eingabe.value.trim();
            eingabe.remove(); textEl.hidden = false; stift.hidden = false;
            th.setAttribute('draggable', key === 'lead' ? 'false' : draggableVorher);
            if (!speichern || neu === (th.dataset.name || '')) { return; }
            const j = await spaltenSenden({ umbenennen: { key: key, name: neu } });
            if (!j) { return; }
            const sp = (j.spalten || []).find(function (s) { return s.key === key; });
            kopfTexteSetzen(key, sp ? sp.titel : (neu || th.dataset.standard), sp ? sp.name : neu);
            melden(j.meldung, false);
        }
        eingabe.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') { ev.preventDefault(); abschliessen(true); }
            else if (ev.key === 'Escape') { ev.preventDefault(); abschliessen(false); }
            ev.stopPropagation();
        });
        eingabe.addEventListener('blur', function () { abschliessen(true); });
        eingabe.addEventListener('click', function (ev) { ev.stopPropagation(); });
        eingabe.focus(); eingabe.select();
    });

    // ---- Verschieben per HTML5 Drag & Drop am Spaltenkopf: Platzhalter (gezogene
    // Spalte gedimmt, Einfügekante am Ziel), nach dem Loslassen Spalten in allen
    // Gruppen umsortieren und Reihenfolge per fetch speichern.
    let gezogenKey = null;
    function zielMarkierungLoeschen() {
        document.querySelectorAll('.lm-th-ziel-vor, .lm-th-ziel-nach').forEach(function (th) {
            th.classList.remove('lm-th-ziel-vor', 'lm-th-ziel-nach');
        });
    }
    function spalteMarkieren(key, an) {
        alleTabellen().forEach(function (t) {
            const i = spaltenIndex(t, key);
            if (i < 0) { return; }
            t.querySelectorAll('tr').forEach(function (tr) {
                const zelle = tr.children[i];
                if (zelle) { zelle.classList.toggle('lm-sp-platzhalter', an); }
            });
        });
    }
    function spalteVerschieben(key, zielKey, danach) {
        alleTabellen().forEach(function (t) {
            const von = spaltenIndex(t, key);
            let nach = spaltenIndex(t, zielKey);
            if (von < 0 || nach < 0 || von === nach) { return; }
            t.querySelectorAll('tr').forEach(function (tr) {
                const zelle = tr.children[von];
                const ziel = tr.children[nach];
                if (!zelle || !ziel) { return; }
                if (danach) { ziel.after(zelle); } else { ziel.before(zelle); }
            });
        });
    }
    document.addEventListener('dragstart', function (e) {
        const th = e.target.closest && e.target.closest('.lm-tabelle thead th[data-key]');
        if (!th || th.getAttribute('draggable') !== 'true') { return; }
        gezogenKey = th.dataset.key;
        th.classList.add('lm-th-zieht');
        spalteMarkieren(gezogenKey, true);
        try { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', gezogenKey); } catch (x) { /* IE */ }
    });
    // feste Spalten (draggable="false": Kundenname, im Infoabend auch Status) sind kein Ablageziel
    function ablageziel(e) {
        const th = e.target.closest && e.target.closest('.lm-tabelle thead th[data-key]');
        if (!th || th.dataset.key === gezogenKey || th.dataset.key === 'lead'
            || th.getAttribute('draggable') === 'false') { return null; }
        return th;
    }
    document.addEventListener('dragover', function (e) {
        if (!gezogenKey) { return; }
        const th = ablageziel(e);
        if (!th) { return; }
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const rect = th.getBoundingClientRect();
        const danach = (e.clientX - rect.left) > rect.width / 2;
        zielMarkierungLoeschen();
        th.classList.add(danach ? 'lm-th-ziel-nach' : 'lm-th-ziel-vor');
    });
    document.addEventListener('drop', function (e) {
        if (!gezogenKey) { return; }
        const th = ablageziel(e);
        if (!th) { return; }
        e.preventDefault();
        const rect = th.getBoundingClientRect();
        const danach = (e.clientX - rect.left) > rect.width / 2;
        spalteVerschieben(gezogenKey, th.dataset.key, danach);
        zielMarkierungLoeschen();
        spaltenSenden({ spalten: aktuelleSpaltenliste() }).then(function (j) {
            if (j) { melden(j.meldung, false); }
        });
    });
    document.addEventListener('dragend', function () {
        if (gezogenKey) { spalteMarkieren(gezogenKey, false); }
        document.querySelectorAll('.lm-th-zieht').forEach(function (th) { th.classList.remove('lm-th-zieht'); });
        zielMarkierungLoeschen();
        gezogenKey = null;
    });

    // ---- Spaltenwähler „Spalten“ (Häkchen = sichtbar) + „Zurücksetzen“
    const spaltenliste = document.getElementById('lm-spaltenliste');
    if (spaltenliste) {
        spaltenliste.addEventListener('change', function (e) {
            const cb = e.target.closest('input[type=checkbox][data-key]');
            if (!cb) { return; }
            const sichtbarKeys = aktuelleSpaltenliste().filter(function (sp) { return sp.sichtbar; }).map(function (sp) { return sp.key; });
            const reihenfolge = Array.from(spaltenliste.querySelectorAll('li[data-key]')).map(function (li) { return li.dataset.key; });
            const bekannt = {};
            (daten.spalten || []).forEach(function (sp) { bekannt[sp.key] = sp; });
            // sichtbare Reihenfolge aus der Tabelle, ausgeblendete in Listenreihenfolge dahinter
            const keys = sichtbarKeys.concat(reihenfolge.filter(function (k) { return sichtbarKeys.indexOf(k) < 0; }));
            const liste = keys.map(function (key) {
                const box = spaltenliste.querySelector('input[data-key="' + key + '"]');
                return { key: key, sichtbar: key === 'lead' || !!(box && box.checked), name: (bekannt[key] || {}).name || '' };
            });
            spaltenSenden({ spalten: liste }).then(function (j) { if (j) { window.location.reload(); } });
        });
    }
    const reset = document.getElementById('lm-spalten-reset');
    if (reset) {
        reset.addEventListener('click', function () {
            if (!window.confirm('Spalten dieses Boards auf den Standard zurücksetzen (Reihenfolge, Sichtbarkeit, Namen, Sortierung)? Gilt nur für Sie.')) { return; }
            spaltenSenden({ zuruecksetzen: true }).then(function (j) { if (j) { window.location.reload(); } });
        });
    }
})();
