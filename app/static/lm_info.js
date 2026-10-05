/* Lead-Management V2, Phase 111 (PLAN_LEAD_V2 I2–I5): Board „Infoabend“ (bis v24 „Info-Veranstaltung“).
   Vanilla JS, kein Framework. Wird nur auf Seiten mit [data-li-board] aktiv.
   - Markier-Kästchen + „alle sichtbaren markieren“ + Sammelaktions-Leiste
     (Status ändern mit Pflichtgründen im Dialog, nächste Veranstaltung,
     Teilgenommen) → POST /lead-management/info-veranstaltung/sammelaktion
   - Teilgenommen-Toggle je Zeile per fetch (…/{id}/teilgenommen, JSON mit
     zeile_html) – ohne JS funktioniert das Formular normal (Redirect).
   - Veranstaltung je Lead (Dropdown) per fetch (…/{id}/veranstaltung); die
     Zeile wandert in die Gruppe der neuen Veranstaltung.
   - Inline-Felder der Phase-105-Tabelle (.lm-inline: Status/Notiz/AD/ID/
     Wiedervorlage) → POST …/{id}/zeile (eigene Route, Zeile wird ersetzt).
   - Schnellsuche über die sichtbaren Zeilen.
   Die Board-Logik von lm_boards.js bleibt aus (kein data-lm-board). */
(function () {
    'use strict';
    const kopf = document.querySelector('[data-li-board]');
    if (!kopf) { return; }
    let daten = { gruende: {}, status: [], zurueck: '/lead-management/info-veranstaltung' };
    try { daten = JSON.parse(document.getElementById('li-daten').textContent); } catch (e) { /* leer */ }
    const statusInfo = {};
    (daten.status || []).forEach(function (s) { statusInfo[s.key] = s; });

    const meldungEl = document.getElementById('li-meldung');
    let meldungTimer = null;
    function melden(text, fehler) {
        if (!meldungEl) { return; }
        meldungEl.textContent = text || '';
        meldungEl.classList.toggle('fehler', !!fehler);
        meldungEl.hidden = !text;
        clearTimeout(meldungTimer);
        if (text && !fehler) { meldungTimer = setTimeout(function () { meldungEl.hidden = true; }, 6000); }
    }

    function zaehlerAktualisieren() {
        document.querySelectorAll('details.li-gruppe').forEach(function (g) {
            const n = g.querySelectorAll('tbody tr[data-vorgang]').length;
            const z = g.querySelector('summary .n');
            if (z) { z.textContent = n; }
            const ja = g.querySelectorAll('tbody tr[data-vorgang] .li-teil.ja').length;
            const nein = g.querySelectorAll('tbody tr[data-vorgang] .li-teil.nein').length;
            const erkl = g.querySelector('summary .erkl');
            if (erkl && g.dataset.gruppe !== 'ohne') {
                const hinweise = g.querySelectorAll('tbody tr.li-hat-hinweis').length;
                erkl.innerHTML = ja + ' teilgenommen · ' + nein + ' nicht · ' + (n - ja - nein) + ' offen'
                    + (hinweise ? ' · <span class="li-rot">' + hinweise + '× bereits im System</span>' : '');
            }
        });
    }

    function zeileErsetzen(zeile, html, zielGruppe) {
        if (!html) { window.location.reload(); return null; }
        const tmp = document.createElement('tbody');
        tmp.innerHTML = html;
        const neu = tmp.firstElementChild;
        if (!neu) { window.location.reload(); return null; }
        const aktuelle = zeile.closest('details.li-gruppe');
        if (zielGruppe && aktuelle && aktuelle.dataset.gruppe !== zielGruppe) {
            const ziel = document.querySelector('details.li-gruppe[data-gruppe="' + zielGruppe + '"]');
            const tbody = ziel ? ziel.querySelector('tbody') : null;
            if (!tbody) { window.location.reload(); return null; }   // Gruppe leer/nicht sichtbar – neu laden
            zeile.remove();
            tbody.prepend(neu);
            ziel.open = true;
            neu.classList.add('lm-neu-hier');
        } else {
            zeile.replaceWith(neu);
            neu.classList.add('lm-geaendert');
        }
        zaehlerAktualisieren();
        sammelAktualisieren();
        return neu;
    }

    async function senden(url, nutzlast, zeile) {
        let antwort;
        try {
            const r = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(nutzlast)
            });
            antwort = await r.json();
        } catch (e) {
            melden('Speichern fehlgeschlagen (Verbindung).', true);
            return null;
        }
        if (antwort.ok && zeile) { zeileErsetzen(zeile, antwort.zeile_html, antwort.gruppe); }
        melden(antwort.meldung, !antwort.ok);
        return antwort;
    }

    // ---- Teilgenommen (Formular → fetch)
    document.addEventListener('submit', function (e) {
        const form = e.target.closest('form.li-teil');
        if (!form) { return; }
        e.preventDefault();
        const knopf = e.submitter;
        const wert = knopf && knopf.name === 'wert' ? knopf.value : 'leer';
        const zeile = form.closest('tr');
        senden(form.action, { wert: wert, zurueck: daten.zurueck }, zeile);
    });

    // ---- Veranstaltung je Lead (Dropdown → fetch, Zeile wandert)
    document.addEventListener('change', function (e) {
        const sel = e.target.closest('select.li-veranst-wahl');
        if (!sel) { return; }
        const form = sel.closest('form');
        const zeile = form.closest('tr');
        senden(form.action, { veranstaltung_id: sel.value, zurueck: daten.zurueck }, zeile);
    });

    // ---- Status-Dialog (Pflichtgründe) für Inline-Status und Sammelaktion
    const dlgStatus = document.getElementById('dlg-li-status');
    function statusDialog(ziel, ok, abbruch) {
        if (!dlgStatus) { ok({}); return; }
        const info = statusInfo[ziel] || {};
        const gruppe = info.grund || '';
        const form = dlgStatus.querySelector('form');
        const grundSel = form.querySelector('select[name=grund]');
        const bisFeld = form.querySelector('#dlg-li-status-bis-feld');
        const bis = form.querySelector('input[name=bis]');
        const text = form.querySelector('input[name=grund_text]');
        form.querySelector('#dlg-li-status-titel').textContent = 'Status „' + (info.label || ziel) + '“ setzen';
        form.querySelector('#dlg-li-status-hinweis').textContent =
            gruppe === 'zurueckgestellt' ? 'Zurückgestellt braucht ein Wiedervorlage-Datum und einen Grund (Blatt Gründe).'
            : gruppe === 'verloren' ? 'Verloren braucht einen Grund; offene Angebote des Vorgangs werden mit diesem Grund abgelehnt.'
            : 'Grund aus der Steuerdatei (Blatt Gründe); bei „Sonstiges“ ist der Freitext Pflicht.';
        grundSel.innerHTML = '';
        (daten.gruende[gruppe] || []).forEach(function (g) {
            const o = document.createElement('option');
            o.value = g.grund; o.textContent = g.grund; o.dataset.freitext = g.freitext ? '1' : '';
            grundSel.appendChild(o);
        });
        bisFeld.hidden = gruppe !== 'zurueckgestellt';
        bis.value = ''; text.value = '';
        if (gruppe === 'zurueckgestellt') {
            const d = new Date(); d.setDate(d.getDate() + 14);
            bis.value = d.toISOString().slice(0, 10);
        }
        const abbrechenKnopf = form.querySelector('button[value=abbrechen]');
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
        form.addEventListener('submit', beiOk);
        abbrechenKnopf.addEventListener('click', beiAbbruch);
        dlgStatus.addEventListener('cancel', beiAbbruch);
        dlgStatus.showModal();
    }

    // ---- Inline-Felder der Phase-105-Tabelle (eigene Route, Zeile ersetzen)
    document.addEventListener('change', function (e) {
        const el = e.target.closest('.lm-inline');
        // Prüfung Phase 111: nur Felder in den Tabellen dieses Boards (der Seitenkopf
        // [data-li-board] enthält die Zeilen nicht – lm_boards.js ist hier ohnehin inaktiv)
        if (!el || !el.closest('table.li-tabelle')) { return; }
        const feld = el.dataset.feld;
        const zeile = el.closest('tr');
        const id = el.dataset.vorgang;
        const url = '/lead-management/info-veranstaltung/' + id + '/zeile';
        if (feld === 'status') {
            const ziel = el.value;
            const info = statusInfo[ziel] || {};
            const zuruecksetzen = function () { el.value = el.dataset.aktuell; };
            if (info.grund) {
                statusDialog(ziel, function (werte) {
                    senden(url, Object.assign({ feld: 'status', wert: ziel, zurueck: daten.zurueck }, werte), zeile)
                        .then(function (a) { if (!a || !a.ok) { zuruecksetzen(); } });
                }, zuruecksetzen);
            } else {
                senden(url, { feld: 'status', wert: ziel, zurueck: daten.zurueck }, zeile)
                    .then(function (a) { if (!a || !a.ok) { zuruecksetzen(); } });
            }
            return;
        }
        senden(url, { feld: feld, wert: el.value, zurueck: daten.zurueck }, zeile);
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && e.target.classList && e.target.classList.contains('lm-notiz')) {
            e.preventDefault(); e.target.blur();
        }
    });

    // ---- Rückfall-Dialog „Kein Interesse“ (ohne Phase-107-Makro)
    const dlgKein = document.getElementById('dlg-li-keininteresse');
    document.addEventListener('click', function (e) {
        const knopf = e.target.closest('button.li-kein-interesse[data-vorgang]');
        if (!knopf || !dlgKein) { return; }
        dlgKein.dataset.vorgang = knopf.dataset.vorgang;
        dlgKein.querySelector('form').action = '/lead-management/anruf/' + knopf.dataset.vorgang;
        dlgKein.showModal();
    });
    if (dlgKein) {
        const sel = dlgKein.querySelector('select[name=grund]');
        sel.addEventListener('change', function () {
            const pflicht = sel.selectedOptions[0] && sel.selectedOptions[0].dataset.freitext === '1';
            sel.form.querySelector('input[name=grund_text]').required = !!pflicht;
        });
    }

    // ---- Markieren + Sammelaktionen
    const sammelform = document.getElementById('li-sammelform');
    function auswahl() { return Array.from(document.querySelectorAll('input.li-wahl:checked')); }
    function sammelAktualisieren() {
        const n = auswahl().length;
        if (sammelform) {
            sammelform.hidden = n === 0;
            const z = document.getElementById('li-sammel-anzahl');
            if (z) { z.textContent = n; }
        }
        document.querySelectorAll('tr[data-vorgang]').forEach(function (tr) {
            const cb = tr.querySelector('input.li-wahl');
            tr.classList.toggle('markiert', !!(cb && cb.checked));
        });
        document.querySelectorAll('input.li-wahl-alle').forEach(function (kopfBox) {
            const tabelle = kopfBox.closest('table');
            const sichtbar = Array.from(tabelle.querySelectorAll('tbody tr[data-vorgang]')).filter(function (tr) { return !tr.hidden; });
            const an = sichtbar.filter(function (tr) { const cb = tr.querySelector('input.li-wahl'); return cb && cb.checked; });
            kopfBox.checked = sichtbar.length > 0 && an.length === sichtbar.length;
            kopfBox.indeterminate = an.length > 0 && an.length < sichtbar.length;
        });
    }
    document.addEventListener('change', function (e) {
        if (e.target.classList.contains('li-wahl-alle')) {
            const tabelle = e.target.closest('table');
            tabelle.querySelectorAll('tbody tr[data-vorgang]').forEach(function (tr) {
                if (tr.hidden) { return; }
                const cb = tr.querySelector('input.li-wahl');
                if (cb) { cb.checked = e.target.checked; }
            });
            sammelAktualisieren();
        } else if (e.target.classList.contains('li-wahl')) {
            sammelAktualisieren();
        }
    });
    const leeren = document.getElementById('li-sammel-leeren');
    if (leeren) {
        leeren.addEventListener('click', function () {
            document.querySelectorAll('input.li-wahl:checked').forEach(function (cb) { cb.checked = false; });
            sammelAktualisieren();
        });
    }
    if (sammelform) {
        const aktionSel = document.getElementById('li-sammel-aktion');
        const statusWrap = sammelform.querySelector('.li-sammel-status');
        const teilWrap = sammelform.querySelector('.li-sammel-teil');
        function aktionUmschalten() {
            if (statusWrap) { statusWrap.hidden = aktionSel.value !== 'status'; }
            if (teilWrap) { teilWrap.hidden = aktionSel.value !== 'teilgenommen'; }
        }
        if (aktionSel) { aktionSel.addEventListener('change', aktionUmschalten); aktionUmschalten(); }
        sammelform.addEventListener('submit', function (e) {
            if (auswahl().length === 0) { e.preventDefault(); melden('Keine Leads markiert.', true); return; }
            if (sammelform.dataset.bereit === '1') { sammelform.dataset.bereit = ''; return; }
            if (aktionSel && aktionSel.value === 'status') {
                const ziel = document.getElementById('li-sammel-status').value;
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

    // ---- Schnellsuche über die sichtbaren Zeilen (Server-Filter per Enter)
    const suche = document.getElementById('li-suche');
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
})();
