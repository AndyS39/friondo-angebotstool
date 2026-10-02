/* Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 105) – Icon-Leiste + Boards.
   Wird über das Makro lm_nav (leadmanagement/_nav.html) auf jeder Modulseite
   geladen (defer). Vanilla JS, kein Framework.
   1. Icon-Leiste: Höhe der Kopfleiste als CSS-Variable --lm-kopf, damit die
      fixe Leiste exakt darunter beginnt (Fallback in lead_v2.css).
   2. Boards (data-lm-board): Inline-Bearbeitung per fetch
      (POST /lead-management/boards/zeile/<id>, JSON {feld, wert, …} →
      {ok, meldung, zeile_html}), Status-Dialog mit Pflichtgründen
      (zurueckgestellt: Datum + Grund, unqualifiziert: Grund, verloren: Grund,
      Freitext bei Sonstiges), Markier-Kästchen + „alle sichtbaren markieren“
      + Sammelaktions-Leiste (ein Dialog für alle), Spalten-Dialog mit Drag &
      Drop (POST /lead-management/boards/spalten), Schnellsuche über die
      sichtbaren Zeilen. */
(function () {
    'use strict';
    if (window.__lmBoardsGeladen) { return; }
    window.__lmBoardsGeladen = true;

    // ---------- 1. Icon-Leiste ----------
    function kopfHoehe() {
        const kopf = document.querySelector('.kopfleiste');
        if (!kopf || document.body.classList.contains('einbett')) { return; }
        document.documentElement.style.setProperty('--lm-kopf', kopf.offsetHeight + 'px');
    }
    kopfHoehe();
    window.addEventListener('resize', kopfHoehe);
    window.addEventListener('load', kopfHoehe);
    // Rückfall für Browser ohne :has(): Platz für die Leiste über eine Body-Klasse
    if (document.querySelector('.lm-leiste') && !document.body.classList.contains('einbett')) {
        document.body.classList.add('lm-mit-leiste');
    }
    // „Mehr …“ schließt sich beim Klick daneben
    document.addEventListener('click', function (e) {
        document.querySelectorAll('.lm-leiste-mehr[open]').forEach(function (d) {
            if (!d.contains(e.target)) { d.removeAttribute('open'); }
        });
    });

    // ---------- 2. Boards ----------
    const kopf = document.querySelector('[data-lm-board]');
    if (!kopf) { return; }
    const board = kopf.dataset.lmBoard;
    let daten = { gruende: {}, status: [] };
    try { daten = JSON.parse(document.getElementById('lm-daten').textContent); } catch (e) { /* leer */ }
    const statusInfo = {};
    (daten.status || []).forEach(function (s) { statusInfo[s.key] = s; });

    const meldungEl = document.getElementById('lm-meldung');
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

    // ---- Inline-Felder (delegiert; Zeilen werden ersetzt)
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

    // ---- Markieren + Sammelaktionen
    const sammelform = document.getElementById('lm-sammelform');
    function auswahl() { return Array.from(document.querySelectorAll('input.lm-wahl:checked')); }
    function sammelAktualisieren() {
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
    }
    document.addEventListener('change', function (e) {
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
    if (suche) {
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

    // ---- Sortierung je Spalte (A3): Klick auf den Spaltenkopf sortiert die
    // Zeilen der Gruppe auf/ab; data-wert (ISO-Datum, Zahl) vor Zelltext,
    // deutsche Datumsangaben und Zahlen werden erkannt, sonst Textvergleich.
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
    document.addEventListener('click', function (e) {
        const th = e.target.closest('.lm-tabelle thead th[data-sort]');
        if (!th) { return; }
        const tabelle = th.closest('table');
        const tbody = tabelle.querySelector('tbody');
        if (!tbody) { return; }
        const index = Array.from(th.parentNode.children).indexOf(th);
        const absteigend = th.getAttribute('aria-sort') === 'ascending';
        th.parentNode.querySelectorAll('th[aria-sort]').forEach(function (k) { k.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', absteigend ? 'descending' : 'ascending');
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
    });

    // ---- Spalten-Dialog (Reihenfolge + sichtbar, je Nutzer)
    const dlgSpalten = document.getElementById('dlg-spalten');
    const spaltenKnopf = document.getElementById('lm-spalten-knopf');
    if (dlgSpalten && spaltenKnopf) {
        const liste = document.getElementById('lm-spaltenliste');
        let gezogen = null;
        liste.addEventListener('dragstart', function (e) {
            const li = e.target.closest('li');
            if (!li || li.classList.contains('fest')) { e.preventDefault(); return; }
            gezogen = li; li.classList.add('zieht');
            e.dataTransfer.effectAllowed = 'move';
        });
        liste.addEventListener('dragend', function () {
            if (gezogen) { gezogen.classList.remove('zieht'); }
            gezogen = null;
        });
        liste.addEventListener('dragover', function (e) {
            e.preventDefault();
            const ueber = e.target.closest('li');
            if (!gezogen || !ueber || ueber === gezogen || ueber.classList.contains('fest')) { return; }
            const rect = ueber.getBoundingClientRect();
            const danach = (e.clientY - rect.top) > rect.height / 2;
            liste.insertBefore(gezogen, danach ? ueber.nextSibling : ueber);
        });
        // Tastatur: Alt+Pfeil verschiebt
        liste.addEventListener('keydown', function (e) {
            if (!e.altKey || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) { return; }
            const li = e.target.closest('li');
            if (!li || li.classList.contains('fest')) { return; }
            e.preventDefault();
            if (e.key === 'ArrowUp' && li.previousElementSibling && !li.previousElementSibling.classList.contains('fest')) {
                liste.insertBefore(li, li.previousElementSibling);
            } else if (e.key === 'ArrowDown' && li.nextElementSibling) {
                liste.insertBefore(li.nextElementSibling, li);
            }
            e.target.focus();
        });
        spaltenKnopf.addEventListener('click', function () { dlgSpalten.showModal(); });
        const form = dlgSpalten.querySelector('form');
        async function speichern(zuruecksetzen) {
            const spalten = Array.from(liste.querySelectorAll('li')).map(function (li) {
                return { key: li.dataset.key, sichtbar: li.querySelector('input').checked || li.classList.contains('fest') };
            });
            try {
                const r = await fetch('/lead-management/boards/spalten', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                    body: JSON.stringify({ board: board, spalten: spalten, zuruecksetzen: !!zuruecksetzen })
                });
                const j = await r.json();
                if (j.ok) { window.location.reload(); return; }
                melden(j.meldung || 'Spalten konnten nicht gespeichert werden.', true);
            } catch (e) {
                melden('Spalten konnten nicht gespeichert werden (Verbindung).', true);
            }
        }
        form.addEventListener('submit', function (e) { e.preventDefault(); speichern(false); });
        form.querySelector('button[value=standard]').addEventListener('click', function () { speichern(true); });
        form.querySelector('button[value=abbrechen]').addEventListener('click', function () { dlgSpalten.close(); });
    }
})();
