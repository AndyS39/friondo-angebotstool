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
   mehr definiert. */
(function () {
    'use strict';

    function $(sel, wurzel) { return (wurzel || document).querySelector(sel); }
    function $$(sel, wurzel) { return Array.prototype.slice.call((wurzel || document).querySelectorAll(sel)); }

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
    // Schnellaktion „Anrufen“ (tel:) → Reiter Anrufnotizen mit den Ergebnis-Buttons öffnen
    $$('[data-anruf-link]').forEach(function (a) {
        a.addEventListener('click', function () { tabZeigen('anrufe', false); });
    });

    /* ---------- Timeline: Suche + Filter ---------- */
    var tlSuche = $('#lk-tl-suche');
    var tlFilter = $$('#lk-tl-filter input');
    var tlZahl = $('#lk-tl-zahl');
    function timelineFiltern() {
        var q = (tlSuche ? tlSuche.value : '').trim().toLowerCase();
        var aktiv = {};
        tlFilter.forEach(function (c) { aktiv[c.value] = c.checked; });
        var karten = $$('#lk-timeline .lk-karte');
        var sichtbar = 0;
        karten.forEach(function (k) {
            var ok = (aktiv[k.dataset.typ] !== false) && (!q || (k.dataset.text || '').indexOf(q) >= 0);
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
    function chipGruppe(id, setzen) {
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
                mailsFiltern();
            });
        });
    }
    chipGruppe('lk-mail-herkunft', function (w) { mailHerkunft = w; });
    chipGruppe('lk-mail-richtung', function (w) { mailRichtung = w; });

    /* ---------- Kundeninfo: MFH-Felder ---------- */
    var objektart = $('#lk-objektart');
    var mfh = $('#lk-mfh');
    function mfhUmschalten() {
        if (!objektart || !mfh) { return; }
        var opt = objektart.options[objektart.selectedIndex];
        mfh.hidden = !(opt && opt.dataset.parteien === '1');
    }
    if (objektart) { objektart.addEventListener('change', mfhUmschalten); mfhUmschalten(); }

    /* ---------- Kundeninfo: Autospeichern je Feld ---------- */
    var stammdaten = $('#lk-stammdaten');
    var ADRESSE = ['strasse', 'plz', 'ort'];
    var timer = {};

    function wrapVon(el) { return el.closest('[data-feld-wrap]') || el.closest('.lk-feld'); }
    function statusElement(wrap) { return wrap ? $('.lk-feld-status', wrap) : null; }

    function statusZeigen(wrap, art, text, dauer) {
        var st = statusElement(wrap);
        if (!st) { return; }
        var key = wrap.dataset.feldWrap || '';
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
        el.value = wert == null ? '' : wert;
    }

    function pflichtAktualisieren(d) {
        if (!d || !Array.isArray(d.pflicht_keys)) { return; }
        var keys = d.pflicht_keys;
        $$('[data-feld-wrap]', stammdaten).forEach(function (w) {
            if (!w.classList.contains('lk-pflicht')) { return; }
            w.classList.toggle('lk-pflicht-offen', keys.indexOf(w.dataset.feldWrap) >= 0);
        });
        var n = typeof d.pflicht_anzahl === 'number' ? d.pflicht_anzahl : (d.pflicht_offen || []).length;
        $$('[data-pflicht-text]').forEach(function (z) { z.textContent = n + ' Pflichtfeld' + (n === 1 ? '' : 'er') + ' offen'; });
        var zaehler = $('#lk-pflicht-zaehler');
        if (zaehler) {
            zaehler.classList.toggle('offen', n > 0);
            zaehler.classList.toggle('ok', n === 0);
            zaehler.title = n ? (d.pflicht_offen || []).join(', ') : 'Alle Pflichtfelder gefüllt';
        }
        var hinweis = $('[data-pflicht-hinweis]', stammdaten);
        if (hinweis) { hinweis.className = n ? 'lm-rot' : 'dezent'; }
        if (stammdaten) { stammdaten.dataset.pflichtKeys = keys.join(','); }
        terminierungAktualisieren(d.terminierung);
    }

    function terminierungAktualisieren(t) {
        var knopf = $('#lk-terminierung-knopf');
        if (!knopf || !t || t.erledigt) { return; }
        var fehlliste = $('#lk-fehlliste');
        var hinweis = $('[data-rolle="terminierung-hinweis"]');
        if (t.bereit) {
            knopf.disabled = false;
            knopf.type = 'submit';
            knopf.removeAttribute('aria-disabled');
            knopf.title = 'Phase Terminiert · Outlook · Terminbestätigung (ICS) · Übergabe Leads VOT';
            knopf.onclick = function () { return confirm('Terminierung: Phase Terminiert, Outlook-Termin schreiben und Terminbestätigung mit ICS planen?'); };
            if (fehlliste) { fehlliste.hidden = true; }
            if (hinweis) { hinweis.textContent = 'Vorgemerkter Termin wird mit „Terminierung“ (oben rechts) bestätigt (Mail, Kalender, Phase).'; hinweis.hidden = false; }
        } else {
            knopf.disabled = true;
            knopf.type = 'button';
            knopf.setAttribute('aria-disabled', 'true');
            knopf.title = 'Gesperrt – es fehlt: ' + (t.fehlend || []).join(', ');
            knopf.onclick = null;
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
        var avatar = $('[data-avatar="' + feld + '"]', stammdaten);
        if (!avatar || el.tagName !== 'SELECT') { return; }
        var opt = el.options[el.selectedIndex];
        var name = opt && opt.value ? opt.textContent.split(' · ')[0].split(' – ')[0].trim() : '';
        var teile = name.split(/[\s,.\-]+/).filter(Boolean);
        avatar.textContent = !teile.length ? '–' : (teile.length === 1 ? teile[0].slice(0, 2) : (teile[0][0] + teile[teile.length - 1][0])).toUpperCase();
        avatar.title = name || 'nicht zugewiesen';
    }

    function feldSpeichern(el) {
        if (!stammdaten || stammdaten.dataset.readonly === '1' || !window.fetch) { return; }
        var feld = el.dataset.feld || el.dataset.feldTeil;
        if (!feld) { return; }
        var wrap = wrapVon(el);
        var wert = wertLesen(el);
        var schluessel = wertSchluessel(wert);
        var merker = (el.dataset.feldTeil ? el.closest('[data-feld-gruppe]') : el);
        if (merker.dataset.letzter === undefined) { merker.dataset.letzter = merker.dataset.start || ''; }
        if (schluessel === merker.dataset.letzter) { return; }           // doppelte Übertragung unterdrücken
        // gleicher Wert bereits unterwegs? (Attribut fehlt = nichts unterwegs – ein leerer
        // Wert '' muss speicherbar bleiben, z. B. Firma löschen)
        if (merker.dataset.laeuft !== undefined && merker.dataset.laeuft === schluessel) { return; }
        merker.dataset.laeuft = schluessel;
        var body = { feld: feld, wert: wert };
        var erzwingen = $('[data-erzwingen]', wrap || stammdaten);
        if (feld === 'ad_id' && erzwingen && erzwingen.checked) { body.erzwingen = '1'; }
        if (wrap) { wrap.classList.add('lk-speichert'); }
        statusZeigen(wrap, 'laeuft', '…');
        fetch(stammdaten.dataset.feldUrl, {
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
                    if (!el.dataset.feldTeil && el.tagName !== 'SELECT' && el.type !== 'checkbox') { el.value = neu; }
                    merker.dataset.letzter = wertSchluessel(neu);
                    statusZeigen(wrap, 'ok', d.geaendert === false ? 'unverändert' : '✓ gespeichert', 2000);
                    if (d.meldung && d.geaendert !== false && d.meldung !== 'Gespeichert.') {
                        var info = $('.lk-feld-info', wrap || stammdaten);
                        if (!info && wrap) { info = document.createElement('small'); info.className = 'lk-feld-info dezent'; wrap.appendChild(info); }
                        if (info) { info.textContent = d.meldung; setTimeout(function () { info.textContent = ''; }, 6000); }
                    }
                    pflichtAktualisieren(d);
                    if (feld === 'leadmanager_id' || feld === 'ad_id') { avatarAktualisieren(feld, el); }
                    if (ADRESSE.indexOf(feld) >= 0 && d.geaendert !== false) { vorschlaegeNachAdresse(d.adresse_vollstaendig); }
                } else {
                    wertSetzen(el, merker.dataset.letzter);                 // alter Wert bleibt stehen
                    if (feld === 'objektart') { mfhUmschalten(); }
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

    if (stammdaten && stammdaten.dataset.readonly !== '1') {
        $$('[data-feld]', stammdaten).forEach(function (el) {
            el.dataset.start = wertSchluessel(wertLesen(el));
            el.dataset.letzter = el.dataset.start;
            var istText = el.tagName === 'INPUT' && el.type !== 'checkbox' && el.type !== 'radio';
            if (istText || el.tagName === 'TEXTAREA') {
                el.addEventListener('blur', function () { feldSpeichern(el); });
                el.addEventListener('keydown', function (ev) {
                    if (ev.key === 'Enter') { ev.preventDefault(); el.blur(); }
                    if (ev.key === 'Escape') { wertSetzen(el, el.dataset.letzter); el.blur(); }
                });
            } else {
                el.addEventListener('change', function () { feldSpeichern(el); });
            }
        });
        $$('[data-feld-gruppe]', stammdaten).forEach(function (g) {
            g.dataset.start = $$('input[type=checkbox]', g).filter(function (c) { return c.checked; }).map(function (c) { return c.value; }).join(',');
            g.dataset.letzter = g.dataset.start;
            $$('input[type=checkbox][data-feld-teil]', g).forEach(function (c) {
                c.addEventListener('change', function () { feldSpeichern(c); });
            });
        });
        // Fallback-Formular (noscript) nie per Enter absenden – Enter speichert das Feld
        stammdaten.addEventListener('submit', function (ev) { if (window.fetch) { ev.preventDefault(); } });
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
    function vorschlagZeile(v, buchen, buchbar) {
        var li = document.createElement('li');
        li.className = 'lk-vorschlag';
        var kopf = document.createElement('div');
        kopf.className = 'lk-vorschlag-kopf';
        var zeit = document.createElement('strong');
        zeit.textContent = v.beginn_text || v.beginn || '';
        var wer = document.createElement('span');
        wer.className = 'lk-vorschlag-ad';
        wer.textContent = v.ad_name ? ' · ' + v.ad_name : '';
        kopf.appendChild(zeit); kopf.appendChild(wer);
        if (v.umweg_min !== undefined && v.umweg_min !== null && v.umweg_min !== '') {
            var umweg = document.createElement('span');
            umweg.className = 'dezent';
            umweg.textContent = ' · Umweg +' + v.umweg_min + ' Min';
            kopf.appendChild(umweg);
        }
        li.appendChild(kopf);
        if (v.begruendung) {
            var grund = document.createElement('div');
            grund.className = 'lk-vorschlag-grund dezent';
            grund.textContent = Array.isArray(v.begruendung) ? v.begruendung.join(' · ') : v.begruendung;
            li.appendChild(grund);
        }
        var form = document.createElement('form');
        form.method = 'post';
        form.action = buchen;
        form.className = 'lk-inline lk-vormerken';
        [['ad_id', v.ad_id], ['beginn', v.beginn], ['quelle', 'assistent']].forEach(function (p) {
            var inp = document.createElement('input');
            inp.type = 'hidden'; inp.name = p[0]; inp.value = p[1] == null ? '' : p[1];
            form.appendChild(inp);
        });
        var knopf = document.createElement('button');
        knopf.type = 'submit';
        knopf.className = 'knopf klein';
        knopf.textContent = 'Vormerken';
        knopf.title = buchbar ? 'Termin vormerken (Status vorgemerkt, Bestätigung über „Terminierung“)' : 'Demo-Modus: Buchung nur für Demo-Leads';
        knopf.disabled = !buchbar;
        form.appendChild(knopf);
        li.appendChild(form);
        return li;
    }
    function vorschlaegeRendern(d) {
        if (!vorschlaege) { return; }
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
        liste.slice(0, 5).forEach(function (v) {
            ol.appendChild(vorschlagZeile(v, vorschlaege.dataset.buchen, vorschlaege.dataset.buchbar === '1'));
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
        // ?neu=1 verwirft den 10-Minuten-Cache (Button „Neu laden“, Vertrag Agent D)
        var url = vorschlaege.dataset.url + (neu ? (vorschlaege.dataset.url.indexOf('?') >= 0 ? '&' : '?') + 'neu=1' : '');
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
        return ADRESSE.every(function (f) { var el = $('[data-feld="' + f + '"]', stammdaten); return el && el.value.trim(); });
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
        if (vorschlaege.dataset.zustand === 'laden') {
            // nach dem Seitenaufbau (nicht blockierend)
            setTimeout(vorschlaegeLaden, 50);
        }
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
