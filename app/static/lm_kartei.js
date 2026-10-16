/* Lead-Management V2 (v23, PLAN_LEAD_V2 Phase 106) – Kundenkartei.
   v25 (PLAN_LEAD_V3 Phase 119): Kartei neu aufgeteilt – Autospeichern je Feld
   (POST /lead-management/lead/{id}/feld, JSON {feld, wert}; Speichern bei blur
   für Text bzw. change für Select/Checkbox, doppelte Übertragung desselben Werts
   unterdrückt, Häkchen „gespeichert“ 2 s, bei Fehler roter Text unter dem Feld
   und alter Wert bleibt), Terminvorschläge im Block Termine (fetch
   GET /lead-management/lead/{id}/termin/vorschlaege.json nach dem Seitenaufbau,
   Platzhalter / 404-Hinweis / Zustände adresse_fehlt · hv_lead · keine, Button
   „Vormerken“ → POST /lead/{id}/termin mit ad_id, beginn, quelle=assistent;
   nach dem Autospeichern der Adresse Nachladen ohne Neuladen), Reiter mit
   Tastatur, Timeline-/E-Mail-Filter, MFH-Zusatzfelder, fetch-Formulare mit
   Neuladen (Notiz, To-Do), Merken der Blöcke je Browser (localStorage), Tasten
   1–7 (2/3/4 posten direkt ohne Dialog, 5/7 Dialog). Vanilla JS, kein Framework.
   Fallback für dialogOeffnen, falls das Makro anruf_dialoge (Agent B) es nicht
   mehr definiert.
   v31 (PLAN_LEAD_V5 Phasen 153/155/157/158/159): Autospeichern für alle Formulare
   `form.lk-autospeichern` (Kundenfelder + Objekt-Karten, je eigene data-feld-url;
   Antwort liefert pflicht_keys und objekt_pflicht_keys je Objekt), MFH-Felder und
   Frage „Rechnungsadresse identisch?“ je Formular, Großkunde-Häkchen, Statuswechsel aus
   Statuskette/Dropdown (Dialog mit Pflichtgrund/Datum, POST …/status), E-Mail-Dialog
   (GET …/mail-dialog.json → Vorschau, POST …/mail-senden), Sprung zum Block Termine
   (?tab=termin, Knopf „Termine“), Kalender-Slot öffnet den Assistenten, Testphase
   (Vormerken/Terminierung gesperrt mit Tooltip), Timeline-Filter nach Herkunft. */
(function () {
    'use strict';

    function $(sel, wurzel) { return (wurzel || document).querySelector(sel); }
    function $$(sel, wurzel) { return Array.prototype.slice.call((wurzel || document).querySelectorAll(sel)); }

    var kopf = $('.lk-kopf');
    var karteiUrl = kopf && kopf.dataset.vorgang ? '/lead-management/lead/' + kopf.dataset.vorgang : location.pathname;

    function neuLaden(meldung, anker) {
        var url = karteiUrl + (meldung ? '?meldung=' + encodeURIComponent(meldung) : '') + (anker ? '#' + anker : '');
        location.href = url;
        if (location.hash === ('#' + anker)) { location.reload(); }
    }

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
    function zuVerlauf() {
        var mitte = $('.lk-mitte');
        if (mitte && mitte.scrollIntoView) { mitte.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    }
    $$('[data-tab-link]').forEach(function (k) {
        k.addEventListener('click', function () { tabZeigen(k.dataset.tabLink, true); zuVerlauf(); });
    });
    if (location.hash && location.hash.indexOf('#tab-') === 0) {
        tabZeigen(location.hash.substring(5), false);
    }
    // Schnellaktion „Anrufen“ (tel:) → Reiter Anruf mit den Ergebnis-Buttons öffnen
    $$('[data-anruf-link]').forEach(function (a) {
        a.addEventListener('click', function () { tabZeigen('anrufe', false); });
    });

    /* ---------- v31: Sprung zum Block Termine (?tab=termin, Knopf „Termine“, #termine) ---------- */
    function zuTerminen() {
        var block = document.getElementById('termine');
        if (!block) { return; }
        block.open = true;
        if (block.scrollIntoView) { block.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    }
    $$('[data-springe="termine"]').forEach(function (k) {
        k.addEventListener('click', function (ev) { ev.preventDefault(); zuTerminen(); });
    });
    $$('[data-historie-oeffnen]').forEach(function (k) {
        k.addEventListener('click', function () { var h = document.getElementById('lk-termin-historie'); if (h) { h.open = true; } });
    });
    if ((kopf && kopf.dataset.springeZu === 'termine') || location.hash === '#termine') {
        setTimeout(zuTerminen, 30);
    }

    /* ---------- Timeline: Suche + Filter (Typ, v31: Herkunft) ---------- */
    var tlSuche = $('#lk-tl-suche');
    var tlFilter = $$('#lk-tl-filter input');
    var tlZahl = $('#lk-tl-zahl');
    var tlHerkunft = '';
    function timelineFiltern() {
        var q = (tlSuche ? tlSuche.value : '').trim().toLowerCase();
        var aktiv = {};
        tlFilter.forEach(function (c) { aktiv[c.value] = c.checked; });
        var karten = $$('#lk-timeline .lk-karte');
        var sichtbar = 0;
        karten.forEach(function (k) {
            var ok = (aktiv[k.dataset.typ] !== false) && (!q || (k.dataset.text || '').indexOf(q) >= 0)
                && (!tlHerkunft || (k.dataset.herkunft || 'lead') === tlHerkunft);
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
    function chipGruppe(id, setzen, danach) {
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
                danach();
            });
        });
    }
    chipGruppe('lk-mail-herkunft', function (w) { mailHerkunft = w; }, mailsFiltern);
    chipGruppe('lk-mail-richtung', function (w) { mailRichtung = w; }, mailsFiltern);
    chipGruppe('lk-tl-herkunft', function (w) { tlHerkunft = w; }, timelineFiltern);

    /* ---------- Kundeninfo / Objekt-Karten: MFH-Felder und Rechnungsfrage je Formular ---------- */
    function mfhUmschalten(select) {
        var form = select.closest('form') || document;
        var mfh = $('[data-mfh]', form) || $('#lk-mfh', form);
        if (!mfh) { return; }
        var opt = select.options[select.selectedIndex];
        mfh.hidden = !(opt && opt.dataset.parteien === '1');
    }
    $$('select[data-objektart-wahl], #lk-objektart').forEach(function (sel) {
        sel.addEventListener('change', function () { mfhUmschalten(sel); });
        mfhUmschalten(sel);
    });
    function rechnungUmschalten(radio) {
        var mfh = radio.closest('[data-mfh]') || radio.closest('.lk-mfh');
        if (!mfh) { return; }
        var felder = $('[data-rechnung-felder]', mfh);
        if (!felder) { return; }
        var nein = radio.value === '1' || radio.value === 'nein';
        felder.hidden = !nein;
    }
    $$('[data-rechnung-frage] input[type=radio]').forEach(function (r) {
        r.addEventListener('change', function () { if (r.checked) { rechnungUmschalten(r); } });
    });

    /* ---------- Autospeichern je Feld (Kundenfelder + Objekt-Karten, v31) ---------- */
    var stammdaten = $('#lk-stammdaten');
    var formulare = $$('form.lk-autospeichern');
    var ADRESSE = ['strasse', 'plz', 'ort'];
    var timer = {};

    function wrapVon(el) { return el.closest('[data-feld-wrap]') || el.closest('.lk-feld'); }
    function statusElement(wrap) { return wrap ? $('.lk-feld-status', wrap) : null; }

    function statusZeigen(wrap, art, text, dauer) {
        var st = statusElement(wrap);
        if (!st) { return; }
        var key = (wrap.closest('form') && wrap.closest('form').dataset.objekt ? wrap.closest('form').dataset.objekt + ':' : '') + (wrap.dataset.feldWrap || '');
        if (timer[key]) { clearTimeout(timer[key]); timer[key] = null; }
        st.className = 'lk-feld-status ' + art;
        st.textContent = text;
        wrap.classList.toggle('lk-feld-fehlerhaft', art === 'fehler');
        if (dauer) {
            timer[key] = setTimeout(function () { st.textContent = ''; st.className = 'lk-feld-status'; }, dauer);
        }
    }

    function wertLesen(el) {
        if (el.type === 'checkbox' && el.dataset.feldTeil) {
            var gruppe = el.closest('[data-feld-gruppe]');
            return $$('input[type=checkbox]', gruppe).filter(function (c) { return c.checked; })
                .map(function (c) { return c.value; });
        }
        if (el.type === 'checkbox') { return el.checked ? '1' : ''; }
        if (el.type === 'radio') {
            var form = el.closest('form') || document;
            var gewaehlt = $$('input[type=radio][name="' + el.name + '"]', form).filter(function (r) { return r.checked; })[0];
            return gewaehlt ? gewaehlt.value : '';
        }
        return el.value;
    }
    function wertSchluessel(wert) { return Array.isArray(wert) ? wert.join(',') : String(wert == null ? '' : wert); }

    function wertSetzen(el, wert) {
        if (el.type === 'checkbox' && el.dataset.feldTeil) {
            var gruppe = el.closest('[data-feld-gruppe]');
            var codes = String(wert || '').split(',');
            $$('input[type=checkbox]', gruppe).forEach(function (c) { c.checked = codes.indexOf(c.value) >= 0; });
            return;
        }
        if (el.type === 'checkbox') { el.checked = wert === '1'; return; }
        if (el.type === 'radio') {
            var form = el.closest('form') || document;
            $$('input[type=radio][name="' + el.name + '"]', form).forEach(function (r) { r.checked = (r.value === String(wert == null ? '' : wert)); });
            return;
        }
        el.value = wert == null ? '' : wert;
    }

    function merkerVon(el) {
        if (el.dataset.feldTeil) { return el.closest('[data-feld-gruppe]'); }
        if (el.type === 'radio') { return el.closest('[data-feld-wrap]') || el; }
        return el;
    }

    function pflichtAktualisieren(d) {
        if (!d || !Array.isArray(d.pflicht_keys)) { return; }
        var keys = d.pflicht_keys;
        formulare.forEach(function (form) {
            var meine = keys;
            if (form.dataset.objekt && d.objekt_pflicht_keys) {
                meine = d.objekt_pflicht_keys[form.dataset.objekt] || [];
            }
            $$('[data-feld-wrap]', form).forEach(function (w) {
                if (!w.classList.contains('lk-pflicht')) { return; }
                w.classList.toggle('lk-pflicht-offen', meine.indexOf(w.dataset.feldWrap) >= 0);
                if (w.dataset.feldWrap === 'ad_id') {
                    w.classList.toggle('lk-feld-ad-offen', meine.indexOf('ad_id') >= 0);
                    var hinweis = $('[data-ad-hinweis]', w);
                    if (hinweis) { hinweis.hidden = meine.indexOf('ad_id') < 0; }
                }
            });
        });
        var n = typeof d.pflicht_anzahl === 'number' ? d.pflicht_anzahl : (d.pflicht_offen || []).length;
        $$('[data-pflicht-text]').forEach(function (z) { z.textContent = n + ' Pflichtfeld' + (n === 1 ? '' : 'er') + ' offen'; });
        var zaehler = $('#lk-pflicht-zaehler');
        if (zaehler) {
            zaehler.classList.toggle('offen', n > 0);
            zaehler.classList.toggle('ok', n === 0);
            zaehler.title = n ? (d.pflicht_offen || []).join(', ') : 'Alle Pflichtfelder gefüllt';
        }
        var hinweis = stammdaten ? $('[data-pflicht-hinweis]', stammdaten) : null;
        if (hinweis) { hinweis.className = n ? 'lm-rot' : 'dezent'; }
        if (stammdaten) { stammdaten.dataset.pflichtKeys = keys.join(','); }
        terminierungAktualisieren(d.terminierung);
    }

    function terminierungAktualisieren(t) {
        var knopf = $('#lk-terminierung-knopf');
        if (!knopf || !t || t.erledigt) { return; }
        var fehlliste = $('#lk-fehlliste');
        var hinweis = $('[data-rolle="terminierung-hinweis"]');
        // v31 (Phase 159): Testphase – der Knopf bleibt gesperrt (Tooltip), nur die Fehlliste läuft mit
        // v35 (PLAN_LEAD_V6 Phase 183, Agent T): Testphase mit aktiver TAIFUN-Übergabe – der Knopf bleibt
        // aktiv (nur Export: keine Buchung, keine Mail), Tooltip/Bestätigung entsprechend
        var taifunTest = knopf.dataset.taifunTestphase === '1';
        var testphase = (knopf.dataset.testphase === '1' || t.aktiv === false) && !taifunTest;
        if (t.bereit && !testphase) {
            knopf.disabled = false;
            knopf.type = 'submit';
            knopf.removeAttribute('aria-disabled');
            if (taifunTest) {
                knopf.title = 'Testphase: nur Übergabe an TAIFUN, keine Buchung, keine Mail';
                knopf.onclick = function () { return confirm('Testphase: nur Übergabe an TAIFUN – keine Buchung, keine Mail. Jetzt die TAIFUN-Datei schreiben?'); };
                if (fehlliste) { fehlliste.hidden = true; }
                if (hinweis) { hinweis.hidden = true; }
                return;
            }
            knopf.title = 'Phase Terminiert · Outlook · Terminbestätigung (ICS) · Übergabe Leads VOT';
            knopf.onclick = function () { return confirm('Terminierung: Phase Terminiert, Outlook-Termin schreiben und Terminbestätigung mit ICS planen?'); };
            if (fehlliste) { fehlliste.hidden = true; }
            if (hinweis) { hinweis.textContent = 'Vorgemerkter Termin wird mit „Terminierung“ (oben rechts) bestätigt (Mail, Kalender, Phase).'; hinweis.hidden = false; }
        } else {
            knopf.disabled = true;
            knopf.type = 'button';
            knopf.setAttribute('aria-disabled', 'true');
            knopf.onclick = null;
            if (t.bereit && testphase) {
                if (fehlliste) { fehlliste.hidden = true; }
                if (hinweis) { hinweis.hidden = true; }
                return;
            }
            if (!testphase) { knopf.title = 'Gesperrt – es fehlt: ' + (t.fehlend || []).join(', '); }
            if (fehlliste) {
                fehlliste.hidden = false;
                var titel = $('[data-rolle="fehlliste-titel"]', fehlliste);
                if (titel && !titel.textContent.trim()) { titel.textContent = 'Terminierung gesperrt – was fehlt?'; }
                var ul = $('[data-rolle="fehlliste"]', fehlliste);
                if (ul) {
                    ul.textContent = '';
                    (t.fehlend || []).forEach(function (f) { var li = document.createElement('li'); li.textContent = f; ul.appendChild(li); });
                }
            }
            if (hinweis) {
                hinweis.hidden = false;
                hinweis.textContent = 'Terminierung gesperrt – es fehlt: ' + (t.fehlend || []).join(', ') + '. Der Button „Terminierung“ oben rechts wird frei, sobald alles gefüllt ist.';
            }
        }
    }

    function avatarAktualisieren(feld, el) {
        var avatar = stammdaten ? $('[data-avatar="' + feld + '"]', stammdaten) : null;
        if (!avatar || el.tagName !== 'SELECT') { return; }
        var opt = el.options[el.selectedIndex];
        var name = opt && opt.value ? opt.textContent.split(' · ')[0].split(' – ')[0].split(' (nicht')[0].trim() : '';
        var teile = name.split(/[\s,.\-]+/).filter(Boolean);
        avatar.textContent = !teile.length ? '–' : (teile.length === 1 ? teile[0].slice(0, 2) : (teile[0][0] + teile[teile.length - 1][0])).toUpperCase();
        avatar.title = name || 'nicht zugewiesen';
    }

    function grosskundeBadge(an) {
        var name = $('.lk-name');
        var badge = $('[data-rolle="grosskunde-badge"]');
        if (an && !badge && name) {
            badge = document.createElement('span');
            badge.className = 'abzeichen lm-grosskunde';
            badge.dataset.rolle = 'grosskunde-badge';
            badge.title = 'Als Großkunde gekennzeichnet';
            badge.textContent = 'Großkunde';
            name.insertBefore(badge, name.firstElementChild);
        } else if (!an && badge) {
            badge.remove();
        }
    }

    function feldSpeichern(el) {
        var form = el.closest('form.lk-autospeichern');
        if (!form || form.dataset.readonly === '1' || !window.fetch) { return; }
        var feld = el.dataset.feld || el.dataset.feldTeil;
        if (!feld) { return; }
        var wrap = wrapVon(el);
        var wert = wertLesen(el);
        var schluessel = wertSchluessel(wert);
        var merker = merkerVon(el);
        if (merker.dataset.letzter === undefined) { merker.dataset.letzter = merker.dataset.start || ''; }
        if (schluessel === merker.dataset.letzter) { return; }           // doppelte Übertragung unterdrücken
        // gleicher Wert bereits unterwegs? (Attribut fehlt = nichts unterwegs – ein leerer
        // Wert '' muss speicherbar bleiben, z. B. Firma löschen)
        if (merker.dataset.laeuft !== undefined && merker.dataset.laeuft === schluessel) { return; }
        merker.dataset.laeuft = schluessel;
        var body = { feld: feld, wert: wert };
        var erzwingen = $('[data-erzwingen]', wrap || form);
        if (feld === 'ad_id' && erzwingen && erzwingen.checked) { body.erzwingen = '1'; }
        if (wrap) { wrap.classList.add('lk-speichert'); }
        statusZeigen(wrap, 'laeuft', '…');
        fetch(form.dataset.feldUrl, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify(body)
        })
            .then(function (r) { return r.json().then(function (d) { return { status: r.status, d: d }; }).catch(function () { return { status: r.status, d: null }; }); })
            .then(function (a) {
                var d = a.d || {};
                if (wrap) { wrap.classList.remove('lk-speichert'); }
                if (a.status === 200 && d.ok) {
                    var neu = d.wert == null ? '' : d.wert;
                    if (!el.dataset.feldTeil && el.tagName !== 'SELECT' && el.type !== 'checkbox' && el.type !== 'radio') { el.value = neu; }
                    merker.dataset.letzter = wertSchluessel(neu);
                    statusZeigen(wrap, 'ok', d.geaendert === false ? 'unverändert' : '✓ gespeichert', 2000);
                    if (d.meldung && d.geaendert !== false && d.meldung !== 'Gespeichert.') {
                        var info = $('.lk-feld-info', wrap || form);
                        if (!info && wrap) { info = document.createElement('small'); info.className = 'lk-feld-info dezent'; wrap.appendChild(info); }
                        if (info) { info.textContent = d.meldung; setTimeout(function () { info.textContent = ''; }, 6000); }
                    }
                    pflichtAktualisieren(d);
                    if (feld === 'leadmanager_id' || feld === 'ad_id') { avatarAktualisieren(feld, el); }
                    if (feld === 'grosskunde') { grosskundeBadge(neu === '1'); }
                    if (feld === 'rechnung_abweichend' && el.type === 'radio') { rechnungUmschalten(el); }
                    if (ADRESSE.indexOf(feld) >= 0 && d.geaendert !== false && !form.dataset.objekt) { vorschlaegeNachAdresse(d.adresse_vollstaendig); }
                    if (ADRESSE.indexOf(feld) >= 0 && d.geaendert !== false && form.dataset.objekt) { vorschlaegeNachAdresse(undefined, true); }
                } else {
                    wertSetzen(el, merker.dataset.letzter);                 // alter Wert bleibt stehen
                    if (feld === 'objektart') { mfhUmschalten(el); }
                    statusZeigen(wrap, 'fehler', (d && d.meldung) || (a.status === 404 ? 'Keine Berechtigung – nicht gespeichert.' : 'Nicht gespeichert.'));
                    pflichtAktualisieren(d);
                }
            })
            .catch(function () {
                if (wrap) { wrap.classList.remove('lk-speichert'); }
                wertSetzen(el, merker.dataset.letzter);
                statusZeigen(wrap, 'fehler', 'Verbindung fehlgeschlagen – nicht gespeichert.');
            })
            .then(function () { delete merker.dataset.laeuft; });
    }

    formulare.forEach(function (form) {
        if (form.dataset.readonly === '1') { return; }
        $$('[data-feld]', form).forEach(function (el) {
            var merker = merkerVon(el);
            if (merker.dataset.start === undefined) {
                merker.dataset.start = wertSchluessel(wertLesen(el));
                merker.dataset.letzter = merker.dataset.start;
            }
            var istText = el.tagName === 'INPUT' && el.type !== 'checkbox' && el.type !== 'radio';
            if (istText || el.tagName === 'TEXTAREA') {
                el.addEventListener('blur', function () { feldSpeichern(el); });
                el.addEventListener('keydown', function (ev) {
                    if (ev.key === 'Enter') { ev.preventDefault(); el.blur(); }
                    if (ev.key === 'Escape') { wertSetzen(el, merkerVon(el).dataset.letzter); el.blur(); }
                });
            } else {
                el.addEventListener('change', function () { feldSpeichern(el); });
            }
        });
        $$('[data-feld-gruppe]', form).forEach(function (g) {
            g.dataset.start = $$('input[type=checkbox]', g).filter(function (c) { return c.checked; }).map(function (c) { return c.value; }).join(',');
            g.dataset.letzter = g.dataset.start;
            $$('input[type=checkbox][data-feld-teil]', g).forEach(function (c) {
                c.addEventListener('change', function () { feldSpeichern(c); });
            });
        });
        // Fallback-Formular (noscript) nie per Enter absenden – Enter speichert das Feld
        form.addEventListener('submit', function (ev) { if (window.fetch) { ev.preventDefault(); } });
    });

    /* ---------- v31: Statuswechsel aus der Kartei (Statuskette + Dropdown) ---------- */
    var statusDaten = { eintraege: [], gruende: {}, setzbar: [] };
    try {
        var roh = document.getElementById('lk-status-daten');
        if (roh) { statusDaten = JSON.parse(roh.textContent || '{}') || statusDaten; }
    } catch (e) { /* ohne Daten kein Dialog */ }
    var statusInfo = {};
    (statusDaten.eintraege || []).forEach(function (s) { statusInfo[s.key] = s; });
    var dlgStatus = document.getElementById('dlg-kartei-status');
    var statusWahl = document.getElementById('lk-status-wahl');

    function statusSenden(ziel, werte) {
        var url = (dlgStatus && dlgStatus.dataset.statusUrl) || (statusWahl && statusWahl.dataset.statusUrl) || (karteiUrl + '/status');
        var body = Object.assign({ wert: ziel }, werte || {});
        return fetch(url, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify(body)
        }).then(function (r) { return r.json().then(function (d) { return { status: r.status, d: d }; }); });
    }

    function statusDialog(ziel, ok, abbruch) {
        if (!dlgStatus) { ok({}); return; }
        var info = statusInfo[ziel] || {};
        var gruppe = info.grund || (ziel === 'nachbearbeitung' ? 'nachbearbeitung' : '');
        var form = $('form', dlgStatus);
        var grundSel = $('select[name=grund]', form);
        var grundFeld = $('#lk-status-grund-feld', form);
        var bisFeld = $('#lk-status-bis-feld', form);
        var bis = $('input[name=bis]', form);
        var text = $('input[name=grund_text]', form);
        var fehler = $('#lk-status-fehler', form);
        $('#lk-status-titel', form).textContent = 'Status „' + (info.label || ziel) + '“ setzen';
        $('#lk-status-hinweis', form).textContent =
            gruppe === 'zurueckgestellt' ? 'Zurückgestellt braucht ein Wiedervorlage-Datum und einen Grund (Blatt Gründe).'
            : gruppe === 'verloren' ? 'Verloren braucht einen Grund; alle offenen Angebote des Vorgangs werden mit diesem Grund auf Abgelehnt gesetzt.'
            : gruppe === 'nachbearbeitung' ? 'Nachbearbeitung: Zurückstellen mit Pflicht-Wiedervorlage (Kunde noch nicht bereit für den Vor-Ort-Termin).'
            : 'Grund aus der Steuerdatei (Blatt Gründe); bei „Sonstiges“ ist der Freitext Pflicht.';
        grundSel.innerHTML = '';
        ((statusDaten.gruende || {})[gruppe] || []).forEach(function (g) {
            var o = document.createElement('option');
            o.value = g.grund; o.textContent = g.grund; o.dataset.freitext = g.freitext ? '1' : '';
            grundSel.appendChild(o);
        });
        grundFeld.hidden = gruppe === 'nachbearbeitung';
        bisFeld.hidden = !(gruppe === 'zurueckgestellt' || gruppe === 'nachbearbeitung');
        bis.value = '';
        text.value = '';
        fehler.hidden = true;
        if (gruppe === 'zurueckgestellt' || gruppe === 'nachbearbeitung') {
            var d = new Date(); d.setDate(d.getDate() + 14);
            bis.value = d.toISOString().slice(0, 10);
        }
        var abbrechenKnopf = $('button[value=abbrechen]', form);
        function schliessen() {
            form.removeEventListener('submit', beiOk);
            abbrechenKnopf.removeEventListener('click', beiAbbruch);
            dlgStatus.removeEventListener('cancel', beiAbbruch);
            if (dlgStatus.open) { dlgStatus.close(); }
        }
        function beiOk(e) {
            e.preventDefault();
            if (gruppe !== 'nachbearbeitung') {
                var gewaehlt = grundSel.selectedOptions[0];
                if (!gewaehlt) { fehler.textContent = 'Bitte einen Grund wählen.'; fehler.hidden = false; return; }
                if (gewaehlt.dataset.freitext && !text.value.trim()) {
                    text.focus(); text.setCustomValidity('Freitext ist bei diesem Grund Pflicht.');
                    text.reportValidity(); text.setCustomValidity(''); return;
                }
            }
            if ((gruppe === 'zurueckgestellt' || gruppe === 'nachbearbeitung') && !bis.value) { bis.focus(); bis.reportValidity(); return; }
            var werte = { grund: grundSel.value, grund_text: text.value.trim(), bis: bis.value };
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

    function statusWechseln(ziel, zuruecksetzen) {
        if (!ziel || !window.fetch) { return; }
        var info = statusInfo[ziel] || {};
        if (info.dialog) {
            var dlg = document.getElementById(info.dialog);
            if (dlg && dlg.showModal) { dlg.showModal(); }
            if (zuruecksetzen) { zuruecksetzen(); }
            return;
        }
        function senden(werte) {
            statusSenden(ziel, werte).then(function (a) {
                if (a.d && a.d.ok) { neuLaden(a.d.meldung || ('Status ' + (info.label || ziel) + ' gesetzt.')); return; }
                alert((a.d && a.d.meldung) || 'Status nicht gesetzt.');
                if (zuruecksetzen) { zuruecksetzen(); }
            }).catch(function () { alert('Verbindung fehlgeschlagen – Status nicht gesetzt.'); if (zuruecksetzen) { zuruecksetzen(); } });
        }
        if (info.grund) {
            statusDialog(ziel, senden, zuruecksetzen);
        } else if (confirm('Status „' + (info.label || ziel) + '“ setzen?')) {
            senden({});
        } else if (zuruecksetzen) { zuruecksetzen(); }
    }
    if (statusWahl) {
        statusWahl.addEventListener('change', function () {
            var ziel = statusWahl.value;
            statusWechseln(ziel, function () { statusWahl.value = ''; });
        });
    }
    $$('.lk-schritt[data-status]').forEach(function (li) {
        li.addEventListener('click', function () { statusWechseln(li.dataset.status, null); });
        li.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); statusWechseln(li.dataset.status, null); }
        });
    });

    /* ---------- v31: E-Mail-Dialog mit Vorlage, Vorschau, ICS ---------- */
    var dlgMail = document.getElementById('dlg-mail');
    if (dlgMail && window.fetch) {
        var mailForm = $('form', dlgMail);
        var vorlageSel = $('[data-rolle="vorlage"]', dlgMail);
        var objektWahl = $('[data-rolle="objekt-wahl"]', dlgMail);
        var objektSel = $('[data-rolle="objekt"]', dlgMail);
        var terminWahl = $('[data-rolle="termin-wahl"]', dlgMail);
        var terminSel = $('[data-rolle="termin"]', dlgMail);
        var betreffFeld = $('[data-rolle="betreff"]', dlgMail);
        var textFeld = $('[data-rolle="text"]', dlgMail);
        var geaendertFeld = $('[data-rolle="text-geaendert"]', dlgMail);
        var icsZeile = $('[data-rolle="ics"]', dlgMail);
        var icsName = $('[data-rolle="ics-name"]', dlgMail);
        var fehlendeListe = $('[data-rolle="fehlende"]', dlgMail);
        var ladeHinweis = $('[data-rolle="laden"]', dlgMail);
        var fehlerZeile = $('[data-rolle="fehler"]', dlgMail);
        var sendenKnopf = $('[data-rolle="senden"]', dlgMail);
        var anFeld = $('[data-rolle="an"]', dlgMail);
        var absenderFeld = $('[data-rolle="absender"]', dlgMail);
        var vorschauText = '';
        var vorschauHtml = '';
        var vorlagenGefuellt = false;
        var mailLauf = 0;

        // Vertrag T (routers/lm_mail.py): GET …/mail/vorschau.json?vorlage=&objekt_id=&termin_id= →
        // {ok, vorlage, vorlage_key, betreff, html, text, fehlende[], anhaenge[], termin_id, objekt_id,
        //  mail_versand_aktiv, mailsperre_hinweis, vorlagen[{key, name, kategorie}]}
        function vorschauLaden() {
            var meinLauf = ++mailLauf;
            var params = new URLSearchParams();
            if (vorlageSel.value) { params.set('vorlage', vorlageSel.value); }
            if (objektSel && objektSel.value) { params.set('objekt_id', objektSel.value); }
            if (terminSel && terminSel.value) { params.set('termin_id', terminSel.value); }
            ladeHinweis.hidden = false;
            fehlerZeile.hidden = true;
            sendenKnopf.disabled = true;
            fetch(dlgMail.dataset.dialogUrl + '?' + params.toString(), { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
                .then(function (r) { return r.json().then(function (d) { return { status: r.status, d: d }; }); })
                .then(function (a) {
                    if (meinLauf !== mailLauf) { return; }
                    var d = a.d || {};
                    ladeHinweis.hidden = true;
                    if (a.status !== 200 || d.ok === false) {
                        fehlerZeile.textContent = d.meldung || 'Vorschau derzeit nicht verfügbar.';
                        fehlerZeile.hidden = false;
                        return;
                    }
                    if (!vorlagenGefuellt && Array.isArray(d.vorlagen) && d.vorlagen.length) {
                        vorlageSel.innerHTML = '';
                        var kategorie = null, gruppe = null;
                        d.vorlagen.forEach(function (v) {
                            if (v.kategorie && v.kategorie !== kategorie) {
                                kategorie = v.kategorie;
                                gruppe = document.createElement('optgroup');
                                gruppe.label = kategorie;
                                vorlageSel.appendChild(gruppe);
                            }
                            var o = document.createElement('option');
                            o.value = v.key; o.textContent = v.name;
                            (gruppe || vorlageSel).appendChild(o);
                        });
                        vorlagenGefuellt = true;
                    }
                    if (d.vorlage) { vorlageSel.value = d.vorlage; }
                    if (objektSel && d.objekt_id != null && d.objekt_id !== '') { objektSel.value = String(d.objekt_id); }
                    if (terminSel && d.termin_id != null && d.termin_id !== '' && terminSel.value === '') {
                        // vom Server gewählter Termin anzeigen, Auswahl „automatisch“ bleibt bestehen
                        terminSel.title = 'automatisch gewählt: Termin ' + d.termin_id;
                    }
                    betreffFeld.value = d.betreff || '';
                    textFeld.value = d.text || '';
                    vorschauText = d.text || '';
                    vorschauHtml = d.html || '';
                    geaendertFeld.value = '';
                    var anhaenge = Array.isArray(d.anhaenge) ? d.anhaenge : [];
                    icsZeile.hidden = !anhaenge.length;
                    icsName.textContent = anhaenge.join(', ');
                    fehlendeListe.innerHTML = '';
                    (d.fehlende || []).forEach(function (f) { var li = document.createElement('li'); li.textContent = f; fehlendeListe.appendChild(li); });
                    fehlendeListe.hidden = !(d.fehlende || []).length;
                    var erlaubt = !(d.fehlende || []).length;
                    sendenKnopf.disabled = !erlaubt;
                    sendenKnopf.title = !erlaubt ? 'Senden gesperrt – Pflichtdaten fehlen'
                        : (d.mail_versand_aktiv === false ? ((d.mailsperre_hinweis || 'Mailsperre') + ' – wird gesperrt eingereiht')
                            : 'In die Warteschlange einreihen (Absender ' + ((absenderFeld && absenderFeld.textContent) || 'termin@') + ')');
                })
                .catch(function (fehler) {
                    if (meinLauf !== mailLauf) { return; }
                    ladeHinweis.hidden = true;
                    fehlerZeile.textContent = 'Vorschau derzeit nicht verfügbar.';
                    fehlerZeile.hidden = false;
                    if (window.console) { console.error('Mail-Vorschau', fehler); }
                });
        }
        $$('[data-mail-dialog]').forEach(function (k) {
            k.addEventListener('click', function () {
                if (dlgMail.showModal && !dlgMail.open) { dlgMail.showModal(); }
                vorschauLaden();
            });
        });
        vorlageSel.addEventListener('change', vorschauLaden);
        if (objektSel) { objektSel.addEventListener('change', function () { if (terminSel) { terminSel.value = ''; } vorschauLaden(); }); }
        if (terminSel) { terminSel.addEventListener('change', vorschauLaden); }
        textFeld.addEventListener('input', function () { geaendertFeld.value = textFeld.value.trim() !== vorschauText.trim() ? '1' : ''; });
        // Vertrag T: POST …/mail/senden JSON {vorlage, betreff, text, objekt_id, termin_id} →
        // {ok, meldung, eintrag_id, status}; 422 bei fehlenden Pflichtdaten. Unveränderter Text
        // geht als Original-HTML der Vorlage (Vertriebler-Bild als CID) in die Warteschlange.
        mailForm.addEventListener('submit', function (ev) {
            ev.preventDefault();
            if (sendenKnopf.disabled) { return; }
            sendenKnopf.disabled = true;
            var geaendert = geaendertFeld.value === '1' || textFeld.value.trim() !== vorschauText.trim();
            var body = {
                vorlage: vorlageSel.value, betreff: betreffFeld.value,
                text: geaendert ? textFeld.value : (vorschauHtml || textFeld.value),
                objekt_id: objektSel ? objektSel.value : '', termin_id: terminSel ? terminSel.value : ''
            };
            fetch(dlgMail.dataset.sendenUrl, {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify(body)
            })
                .then(function (r) { return r.json().then(function (d) { return { status: r.status, d: d }; }); })
                .then(function (a) {
                    if (a.d && a.d.ok) { dlgMail.close(); neuLaden(a.d.meldung || 'E-Mail eingereiht.', 'lk-verlauf'); return; }
                    fehlerZeile.textContent = (a.d && a.d.meldung) || 'E-Mail nicht eingereiht.';
                    fehlerZeile.hidden = false;
                    sendenKnopf.disabled = false;
                })
                .catch(function () { fehlerZeile.textContent = 'Verbindung fehlgeschlagen – nicht gesendet.'; fehlerZeile.hidden = false; sendenKnopf.disabled = false; });
        });
    }

    /* ---------- Block Termine: Terminvorschläge ---------- */
    var vorschlaege = $('#lk-vorschlaege');
    function hinweisSetzen(status, text, klasse) {
        if (!vorschlaege) { return; }
        var hinweis = $('[data-rolle="hinweis"]', vorschlaege);
        var liste = $('[data-rolle="liste"]', vorschlaege);
        if (liste) { liste.hidden = true; liste.textContent = ''; }
        if (hinweis) {
            hinweis.hidden = false;
            hinweis.className = 'lk-vorschlaege-hinweis ' + (klasse || 'dezent');
            hinweis.dataset.status = status;
            hinweis.textContent = text;
        }
        vorschlaege.dataset.zustand = status;
    }
    // v31 (Phase 153, Vertrag T): Vormerken je Objekt per fetch an vormerken_url (JSON {objekt_id,
    // ad_id, beginn, umweg}) → {ok, meldung, offen, gesamt, objekte_hinweis, bestaetigung_vorbelegung}
    var vormerkenUrl = vorschlaege ? (vorschlaege.dataset.vormerken || '') : '';
    var testphaseHinweis = '';
    function aktuellesObjekt() {
        var sel = vorschlaege ? $('[data-rolle="objekt"]', vorschlaege) : null;
        return sel && sel.value ? sel.value : (vorschlaege && vorschlaege.dataset.objektId ? vorschlaege.dataset.objektId : '');
    }
    function vormerken(form, knopf) {
        if (!window.fetch || !vormerkenUrl) { return false; }
        knopf.disabled = true;
        var daten = {};
        $$('input[type=hidden]', form).forEach(function (i) { daten[i.name] = i.value; });
        if (aktuellesObjekt()) { daten.objekt_id = aktuellesObjekt(); }
        fetch(vormerkenUrl, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify(daten)
        })
            .then(function (r) { return r.json().then(function (d) { return { status: r.status, d: d }; }); })
            .then(function (a) {
                if (a.d && a.d.ok) { neuLaden(a.d.meldung || 'Termin vorgemerkt.', 'termine'); return; }
                alert((a.d && a.d.meldung) || 'Vormerken nicht möglich.');
                knopf.disabled = false;
            })
            .catch(function () { alert('Verbindung fehlgeschlagen – nicht vorgemerkt.'); knopf.disabled = false; });
        return true;
    }
    function vorschlagZeile(v, buchen, buchbar) {
        var li = document.createElement('li');
        // v29 (PLAN_LEAD_V4 Phase 143): Vorschlag 1 „Ideal“ – Rahmen Friondo-Blau, Badge, Begründung
        li.className = 'lk-vorschlag' + (v.ideal ? ' lk-ideal' : '');
        var kopfZeile = document.createElement('div');
        kopfZeile.className = 'lk-vorschlag-kopf';
        var zeit = document.createElement('strong');
        zeit.textContent = v.beginn_text || v.beginn || '';
        var wer = document.createElement('span');
        wer.className = 'lk-vorschlag-ad';
        wer.textContent = v.ad_name ? ' · ' + v.ad_name : '';
        kopfZeile.appendChild(zeit); kopfZeile.appendChild(wer);
        if (v.ideal) {
            var badge = document.createElement('span');
            badge.className = 'lmt-ideal-badge';
            badge.textContent = 'Ideal';
            badge.title = v.ideal_grund || 'Bester Vorschlag';
            kopfZeile.appendChild(badge);
        }
        // v37 (PLAN_LEAD_V7 Phase 198): Strecke in Kilometern – „Anfahrt 18,4 km · 24 Min · Umweg
        // +3,2 km · 5 Min“ (geschätzt mit Kennzeichen) statt nur „Umweg +n Min“
        var strecke = [];
        if (v.anfahrt_text) { strecke.push('Anfahrt ' + v.anfahrt_text); }
        if (v.umweg_text) { strecke.push('Umweg ' + v.umweg_text); }
        else if (v.umweg_min !== undefined && v.umweg_min !== null && v.umweg_min !== '') { strecke.push('Umweg +' + v.umweg_min + ' Min'); }
        if (strecke.length) {
            var umweg = document.createElement('span');
            umweg.className = 'dezent lk-vorschlag-strecke';
            umweg.textContent = ' · ' + strecke.join(' · ');
            kopfZeile.appendChild(umweg);
        }
        li.appendChild(kopfZeile);
        if (v.ideal && v.ideal_grund) {
            var ideal = document.createElement('div');
            ideal.className = 'lk-vorschlag-ideal-grund';
            ideal.textContent = v.ideal_grund;
            li.appendChild(ideal);
        }
        if (v.begruendung) {
            var grund = document.createElement('div');
            grund.className = 'lk-vorschlag-grund dezent';
            grund.textContent = Array.isArray(v.begruendung) ? v.begruendung.join(' · ') : v.begruendung;
            li.appendChild(grund);
        }
        var form = document.createElement('form');
        form.method = 'post';
        form.action = vormerkenUrl || buchen;
        form.className = 'lk-inline lk-vormerken';
        var objektId = v.objekt_id != null ? v.objekt_id : aktuellesObjekt();
        [['ad_id', v.ad_id], ['beginn', v.beginn], ['quelle', 'assistent'], ['umweg', v.umweg_min], ['objekt_id', objektId]].forEach(function (p) {
            if ((p[0] === 'objekt_id' || p[0] === 'umweg') && (p[1] === undefined || p[1] === null || p[1] === '')) { return; }
            var inp = document.createElement('input');
            inp.type = 'hidden'; inp.name = p[0]; inp.value = p[1] == null ? '' : p[1];
            form.appendChild(inp);
        });
        var knopf = document.createElement('button');
        knopf.type = 'submit';
        knopf.className = 'knopf klein';
        knopf.textContent = 'Vormerken';
        // v31 (Phase 159): Testphase – gesperrt mit Tooltip (testphase_hinweis aus vorschlaege.json)
        knopf.title = buchbar ? 'Termin vormerken (Status vorgemerkt, „Terminierung“ bucht alle vorgemerkten Objekttermine)'
            : (testphaseHinweis || vorschlaege.dataset.sperreText || 'Vormerken gesperrt');
        knopf.disabled = !buchbar;
        if (!buchbar) { knopf.setAttribute('aria-disabled', 'true'); }
        form.appendChild(knopf);
        form.addEventListener('submit', function (ev) { if (vormerken(form, knopf)) { ev.preventDefault(); } });
        li.appendChild(form);
        return li;
    }
    function objektWahlNachziehen(d) {
        // Objektauswahl aus vorschlaege.json (objekte, mehrere_objekte, objekt_id); Hinweis „n von m ohne Termin“
        var wahl = $('[data-rolle="objekt-wahl"]', vorschlaege);
        var sel = $('[data-rolle="objekt"]', vorschlaege);
        if (sel && Array.isArray(d.objekte) && d.objekte.length && !sel.options.length) {
            d.objekte.forEach(function (o) {
                var opt = document.createElement('option');
                opt.value = String(o.id);
                opt.textContent = (o.bezeichnung || ('Objekt ' + o.id)) + (o.adresse ? ' – ' + o.adresse : '');
                sel.appendChild(opt);
            });
        }
        if (wahl) { wahl.hidden = !d.mehrere_objekte; }
        if (sel && d.objekt_id != null && d.objekt_id !== '' && sel.value !== String(d.objekt_id)) { sel.value = String(d.objekt_id); }
        if (d.objekt_id != null && d.objekt_id !== '') { vorschlaege.dataset.objektId = String(d.objekt_id); }
        if (d.vormerken_url) { vormerkenUrl = d.vormerken_url; }
        if (d.testphase_hinweis) { testphaseHinweis = d.testphase_hinweis; }
        var hinweis = $('[data-rolle="ohne-termin"]');
        if (hinweis && typeof d.objekte_hinweis === 'string') {
            hinweis.hidden = !d.objekte_hinweis;
            if (d.objekte_hinweis) { hinweis.textContent = d.objekte_hinweis + ' – die Terminierung bucht alle vorgemerkten Objekttermine in einem Schritt, Objekte ohne Termin bleiben offen.'; }
        }
    }
    function vorschlaegeRendern(d) {
        if (!vorschlaege) { return; }
        objektWahlNachziehen(d || {});
        var status = d && d.status ? d.status : 'keine';
        if (status === 'adresse_fehlt') {
            hinweisSetzen('adresse_fehlt', vorschlaege.dataset.textAdresse, 'lm-warn');
            return;
        }
        if (status === 'hv_lead') {
            hinweisSetzen('hv_lead', d.hinweis || ('Lead liegt bei ' + (vorschlaege.dataset.hvName || 'Handelsvertreter')
                + ' (Handelsvertreter), Terminierung durch den Vertreter'), 'lm-blau');
            return;
        }
        var liste = Array.isArray(d.vorschlaege) ? d.vorschlaege : [];
        if (status !== 'ok' || !liste.length) {
            hinweisSetzen('keine', d.hinweis || 'Derzeit keine freien Vorschläge – „Alle Vorschläge / manuell“ öffnen oder manuell buchen.', 'dezent');
            return;
        }
        var ol = $('[data-rolle="liste"]', vorschlaege);
        var hinweis = $('[data-rolle="hinweis"]', vorschlaege);
        ol.textContent = '';
        // v29: genau `anzahl` Vorschläge (Parameter vorschlaege_anzahl, Standard 3)
        var anzahl = parseInt(d.anzahl, 10) || 3;
        // buchbar kommt aus vorschlaege.json (= terminierung_aktiv); ohne Feld gilt das Seiten-Flag
        var buchbar = typeof d.buchbar === 'boolean' ? d.buchbar : vorschlaege.dataset.buchbar === '1';
        liste.slice(0, anzahl).forEach(function (v) {
            ol.appendChild(vorschlagZeile(v, vorschlaege.dataset.buchen, buchbar));
        });
        ol.hidden = false;
        if (hinweis) {
            hinweis.hidden = !d.hinweis;
            hinweis.className = 'lk-vorschlaege-hinweis dezent';
            hinweis.dataset.status = 'ok';
            hinweis.textContent = d.hinweis || '';
        }
        vorschlaege.dataset.zustand = 'ok';
    }
    function vorschlaegeLaden(neu) {
        if (!vorschlaege || !window.fetch) { return; }
        hinweisSetzen('laden', vorschlaege.dataset.textLaden, 'dezent');
        // ?neu=1 verwirft den 10-Minuten-Cache (Button „Neu laden“, Vertrag Agent D);
        // v31: ?objekt_id= Vorschläge je Objekt (Vertrag T)
        var params = [];
        if (neu) { params.push('neu=1'); }
        if (aktuellesObjekt()) { params.push('objekt_id=' + encodeURIComponent(aktuellesObjekt())); }
        var url = vorschlaege.dataset.url + (params.length ? (vorschlaege.dataset.url.indexOf('?') >= 0 ? '&' : '?') + params.join('&') : '');
        fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
            .then(function (r) {
                if (r.status === 404) { throw new Error('404'); }
                if (!r.ok) { throw new Error(String(r.status)); }
                return r.json();
            })
            .then(vorschlaegeRendern)
            .catch(function () { hinweisSetzen('nicht_verfuegbar', vorschlaege.dataset.textFehler, 'dezent'); });
    }
    function adresseVollstaendig() {
        if (!stammdaten) { return false; }
        var felder = ADRESSE.map(function (f) { return $('[data-feld="' + f + '"]', stammdaten); });
        if (felder.some(function (el) { return !el; })) {
            // mehrere Objekte: Adresse steht in der Karte des Hauptobjekts
            var haupt = $('.lk-objekt.haupt form.lk-autospeichern');
            if (!haupt) { return false; }
            felder = ADRESSE.map(function (f) { return $('[data-feld="' + f + '"]', haupt); });
        }
        return felder.every(function (el) { return el && el.value.trim(); });
    }
    function vorschlaegeNachAdresse(vollstaendig, neu) {
        if (!vorschlaege || vorschlaege.dataset.zustand === 'hv_lead') { return; }
        var ok = typeof vollstaendig === 'boolean' ? vollstaendig : adresseVollstaendig();
        if (ok) { vorschlaegeLaden(neu); } else { hinweisSetzen('adresse_fehlt', vorschlaege.dataset.textAdresse, 'lm-warn'); }
    }
    if (vorschlaege) {
        $$('[data-vorschlaege-neu]', vorschlaege).forEach(function (k) {
            k.addEventListener('click', function () { vorschlaegeNachAdresse(undefined, true); });
        });
        var objektSelVorschlag = $('[data-rolle="objekt"]', vorschlaege);
        if (objektSelVorschlag) {
            objektSelVorschlag.addEventListener('change', function () { vorschlaege.dataset.objektId = objektSelVorschlag.value; vorschlaegeNachAdresse(undefined, false); });
        }
        if (vorschlaege.dataset.zustand === 'laden') {
            // nach dem Seitenaufbau (nicht blockierend)
            setTimeout(vorschlaegeLaden, 50);
        }
    }

    /* ---------- v31: Kalenderansicht im Block Termine – Klick auf einen Slot öffnet den Assistenten ---------- */
    var kalender = document.getElementById('lmt-kalender');
    if (kalender && kalender.dataset.assistent) {
        kalender.addEventListener('click', function (e) {
            var td = e.target.closest('td[data-beginn]');
            if (!td) { return; }
            var beginn = td.dataset.beginn || '';
            location.href = kalender.dataset.assistent + '?ad_id=' + encodeURIComponent(td.dataset.ad || '')
                + '&datum=' + encodeURIComponent(beginn.slice(0, 10)) + '&uhrzeit=' + encodeURIComponent(beginn.slice(11, 16)) + '#manuell';
        });
    }

    /* ---------- fetch-Formulare: absenden, dann Kartei neu laden ---------- */
    $$('form[data-fetch="reload"]').forEach(function (form) {
        form.addEventListener('submit', function (ev) {
            if (!window.fetch || !window.FormData) { return; }
            ev.preventDefault();
            var knopf = $('button[type=submit]', form);
            if (knopf) { knopf.disabled = true; }
            fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin', redirect: 'follow' })
                .then(function () { location.reload(); })
                .catch(function () { if (knopf) { knopf.disabled = false; } form.submit(); });
        });
    });

    /* ---------- v37 (PLAN_LEAD_V7 Phase 198): Objekte-Akkordeon – Zustand je Nutzer (Server) ---------- */
    var akkordeon = $('[data-objekte-akkordeon]');
    if (akkordeon && akkordeon.dataset.zustandUrl) {
        var akkTimer = null;
        akkordeon.addEventListener('toggle', function () {
            if (!window.fetch) { return; }
            clearTimeout(akkTimer);
            var zu = !akkordeon.open;
            akkTimer = setTimeout(function () {
                fetch(akkordeon.dataset.zustandUrl, {
                    method: 'POST', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                    body: JSON.stringify({ zu: zu })
                }).catch(function () { /* nur Komfort – beim nächsten Laden gilt der Standard */ });
            }, 250);
        });
    }

    /* ---------- Blöcke merken (nur Komfort je Browser) ---------- */
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

    /* ---------- Fallback dialogOeffnen (Makro anruf_dialoge kann sich ändern) ---------- */
    if (typeof window.dialogOeffnen !== 'function') {
        var ziele = {
            rueckruf: function (id) { return '/lead-management/anruf/' + id; },
            keininteresse: function (id) { return '/lead-management/anruf/' + id; },
            nichterreicht: function (id) { return '/lead-management/anruf/' + id; },
            zurueck: function (id) { return '/lead-management/lead/' + id + '/zurueckstellen'; },
            reaktivieren: function (id) { return '/lead-management/lead/' + id + '/reaktivieren'; }
        };
        // v25 (Phase 120): Nicht erreicht/Mailbox/Besetzt ohne Dialog – direkt senden
        var direkt = { nichterreicht: 'nicht_erreicht', mailbox: 'mailbox', besetzt: 'besetzt' };
        window.dialogOeffnen = function (art, vorgangId) {
            if (direkt[art] && window.lmAnruf && window.lmAnruf.ergebnisSenden) {
                window.lmAnruf.ergebnisSenden(vorgangId, direkt[art], anruf && anruf.dataset.zurueck);
                return;
            }
            var dlg = document.getElementById('dlg-' + art);
            if (!dlg) {
                if (window.console) { console.warn('Dialog fehlt: dlg-' + art); }
                return;
            }
            dlg.dataset.vorgang = vorgangId;
            var form = dlg.querySelector('form');
            if (form && ziele[art]) { form.action = ziele[art](vorgangId); }
            if (dlg.showModal) { dlg.showModal(); } else { dlg.setAttribute('open', ''); }
        };
    }

    /* ---------- Tasten 1–7 wie in der Anrufliste (2/3/4/6 direkt, 5/7 Dialog) ---------- */
    var anruf = $('.lk-anruf');
    if (anruf) {
        var tasten = { '1': 'erreicht', '2': 'nicht_erreicht', '3': 'besetzt', '4': 'mailbox', '6': 'falsche_nummer' };
        var dialoge = { '5': 'rueckruf', '7': 'keininteresse' };
        document.addEventListener('keydown', function (ev) {
            if (ev.ctrlKey || ev.altKey || ev.metaKey) { return; }
            var ziel = ev.target;
            var tag = ziel && ziel.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (ziel && ziel.isContentEditable)) { return; }
            if (document.querySelector('dialog[open]')) { return; }
            if (tasten[ev.key]) {
                var knopf = $('button[name=ergebnis][value="' + tasten[ev.key] + '"]', anruf);
                if (knopf && !knopf.disabled) { ev.preventDefault(); tabZeigen('anrufe', false); knopf.click(); }
            } else if (dialoge[ev.key] && typeof window.dialogOeffnen === 'function') {
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
