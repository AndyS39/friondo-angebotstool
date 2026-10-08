/* Projektierung V4 (PLAN_PROJ_V4 Phase 90.4/90.5) – gemeinsame Helfer für
   Projektakte, Board, Meine Aufgaben und das Montage-Backend:
   1. Zeitfelder im 15-Minuten-Takt (step 900): leere Felder werden auf das
      nächste Viertel vorbelegt, Eingaben auf 15 Minuten gerundet.
   2. Aufgaben-Aktionen per fetch (Accept: application/json) – die Zeile wird
      an Ort und Stelle ersetzt, Zähler/Ampel aktualisiert; schlägt fetch fehl,
      wird das Formular klassisch abgeschickt (Server-Redirect als Fallback).
   3. Alle übrigen POST-Formulare: Scroll-Position je URL in sessionStorage
      merken und nach dem Redirect wiederherstellen. Gilt seit v22 (PLAN_V15
      Phase 103) auch für den Angebots-Editor /angebote/<id> (Zeilen-Editor,
      USt, Vertriebler, Profil, Sortierung, Texte …) – nicht für die Liste
      /angebote. Mit Anker (#pos<id> nach „Position hinzufügen“) wird nicht
      wiederhergestellt, der Anker gewinnt. */
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
    // v28 (PLAN_PROJ_V6 Phase 133/134): Dialoge nutzen Meldung + Zeilen-Update
    window.pjMeldung = meldungZeigen;
    window.pjAntwortAnwenden = antwortAnwenden;

    // Formulare mit data-pj-ajax: Absenden (Enter) ebenfalls per fetch
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (form && form.matches && form.matches('form[data-pj-ajax]')) {
            e.preventDefault();
            senden(form);
        }
    }, true);

    // ---------- 3. Scroll-Position bei klassischen POSTs ----------
    // v22: zusätzlich der Angebots-Editor /angebote/<Ziffern> (nicht die Liste)
    const bereich = /^\/(projektierung|montage)(\/|$)|^\/angebote\/\d+(\/|$)/.test(location.pathname);

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

/* ======================================================================
   v28 (PLAN_PROJ_V6 Phasen 133–135) – Board, Dialog „Phase ändern“, Termin-Dialog
   1. Board (/projektierung): Höhe = Viewport − Position (min 480 px), jede Spalte
      scrollt für sich (CSS), Dummy-Scrollbalken ÜBER dem Board synchron zum
      Board, Shift + Mausrad scrollt waagerecht.
   2. Dialog „Phase ändern“ (Akte dlg-phase-<gewerk>, Board dlg-phase-board):
      lädt GET /projektierung/gewerk/{id}/waechter?ziel= und zeigt die offenen
      Punkte mit Häkchen „erledigt“ (POST …/erledigt-umschalten) und Knopf
      „entfällt“ (POST …/entfaellt mit Grund); Begründung Pflicht nur laut JSON.
   3. Termin-Dialog (Makro termin_dialog): Art-Umschaltung, Team → Besetzung
      (Chips), Ende-Vorbelegung, Terminvorschläge, Senden per fetch (JSON),
      bei Erfolg Neuladen (Terminstatus, Block Termine, Kacheln ändern sich).
   ====================================================================== */
(function () {
    'use strict';

    function fetchJson(url, optionen) {
        const o = Object.assign({credentials: 'same-origin'}, optionen || {});
        o.headers = Object.assign({'Accept': 'application/json'}, o.headers || {});
        return fetch(url, o).then(function (antwort) {
            return antwort.json().then(function (daten) {
                daten.__status = antwort.status;
                return daten;
            });
        });
    }

    function el(tag, klasse, text) {
        const e = document.createElement(tag);
        if (klasse) { e.className = klasse; }
        if (text !== undefined) { e.textContent = text; }
        return e;
    }

    // ---------- 1. Board ----------
    function boardInit() {
        const board = document.querySelector('.pj-board');
        if (!board) { return; }
        const note = document.querySelector('.pj-board ~ .pj-note');
        const hscroll = document.getElementById('pj-hscroll');

        function hoeheSetzen() {
            // Alles außer dem Board (Kopf, Kacheln, Filter, Hinweis, Fußabstand) =
            // Seitenhöhe − aktuelle Board-Höhe; das Board füllt den Rest des
            // Viewports. Nachtrag 08.10.2026 (Antwort Andreas, „entscheide du“):
            // Mindesthöhe 480 px (Plan) nur bei Viewport-Höhe ≥ 900 px, darunter
            // 320 px – damit bleibt bei 1366 × 768 kein Seiten-Scroll (gleiche
            // Schwelle wie die Media-Query in projektierung_v28.css). Gemessen wird
            // mit übergroßem Board: bei kurzem Inhalt (wenige Karten) ist scrollHeight
            // sonst auf die Viewport-Höhe geklemmt (body min-height 100vh) und der
            // Rest zu groß – das Board bliebe dann auf der Mindesthöhe stehen.
            board.style.setProperty('--pj-board-h', (window.innerHeight * 2) + 'px');
            const rest = document.documentElement.scrollHeight - board.offsetHeight;
            const frei = window.innerHeight - rest - 2;
            const minimum = window.innerHeight >= 900 ? 480 : 320;
            const hoehe = Math.max(minimum, Math.floor(frei));
            board.style.setProperty('--pj-board-h', hoehe + 'px');
            if (hscroll) {
                hscroll.firstElementChild.style.width = board.scrollWidth + 'px';
            }
        }
        hoeheSetzen();
        window.addEventListener('resize', hoeheSetzen);
        setTimeout(hoeheSetzen, 50);

        // Dummy-Scrollbalken oben ↔ Board (beide Richtungen, ohne Rückkopplung)
        if (hscroll) {
            let sperre = false;
            hscroll.addEventListener('scroll', function () {
                if (sperre) { return; }
                sperre = true; board.scrollLeft = hscroll.scrollLeft; sperre = false;
            });
            board.addEventListener('scroll', function () {
                if (sperre) { return; }
                sperre = true; hscroll.scrollLeft = board.scrollLeft; sperre = false;
            });
        }
        // Shift + Mausrad → waagerecht (falls der Browser es nicht selbst tut)
        board.addEventListener('wheel', function (e) {
            if (e.shiftKey && e.deltaY && !e.deltaX) {
                board.scrollLeft += e.deltaY;
                e.preventDefault();
            }
        }, {passive: false});
        window.pjBoardHoehe = hoeheSetzen;
    }

    // ---------- 2. Dialog „Phase ändern“ ----------
    function waechterZeile(punkt, liste) {
        const zeile = el('div', 'pj-wz');
        if (punkt.aufgabe_id) {
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.title = 'erledigt';
            cb.dataset.aufgabe = punkt.aufgabe_id;
            zeile.appendChild(cb);
            const txt = el('span', 'txt', punkt.text);
            if (punkt.gruppe) { txt.appendChild(el('small', '', punkt.gruppe)); }
            zeile.appendChild(txt);
            const entf = el('button', 'pj-btn', 'entfällt');
            entf.type = 'button';
            entf.title = 'Aufgabe mit Grund auf „entfällt“ setzen';
            const feld = el('span', 'pj-entf-feld');
            feld.hidden = true;
            const grund = document.createElement('input');
            grund.type = 'text'; grund.placeholder = 'Grund (Pflicht)'; grund.maxLength = 300;
            const ok = el('button', 'pj-btn', 'OK');
            ok.type = 'button';
            feld.appendChild(grund); feld.appendChild(ok);
            zeile.appendChild(entf); zeile.appendChild(feld);
            entf.addEventListener('click', function () {
                feld.hidden = !feld.hidden;
                if (!feld.hidden) { grund.focus(); }
            });
            cb.addEventListener('change', function () {
                cb.disabled = true;
                const fd = new FormData();
                fetchJson('/projektierung/aufgabe/' + punkt.aufgabe_id + '/erledigt-umschalten',
                          {method: 'POST', body: fd})
                    .then(function (d) {
                        cb.disabled = false;
                        zeile.classList.toggle('done', cb.checked);
                        if (window.pjAntwortAnwenden && d.ok) { window.pjAntwortAnwenden(d); }
                        zaehlerAktualisieren(liste);
                    })
                    .catch(function () { cb.disabled = false; cb.checked = !cb.checked; });
            });
            ok.addEventListener('click', function () {
                if (!grund.value.trim()) { grund.focus(); return; }
                const fd = new FormData();
                fd.append('grund', grund.value.trim());
                fetchJson('/projektierung/aufgabe/' + punkt.aufgabe_id + '/entfaellt',
                          {method: 'POST', body: fd})
                    .then(function (d) {
                        if (!d.ok) { if (window.pjMeldung) { window.pjMeldung(d.meldung || 'Fehler'); } return; }
                        zeile.classList.add('entf');
                        zeile.classList.remove('done');
                        cb.checked = false; cb.disabled = true; entf.hidden = true; feld.hidden = true;
                        txt.appendChild(el('small', '', 'entfällt – ' + grund.value.trim()));
                        if (window.pjAntwortAnwenden) { window.pjAntwortAnwenden(d); }
                        zaehlerAktualisieren(liste);
                    })
                    .catch(function () { if (window.pjMeldung) { window.pjMeldung('Senden fehlgeschlagen'); } });
            });
        } else {
            zeile.appendChild(el('span', 'txt', '• ' + punkt.text));
        }
        return zeile;
    }

    function zaehlerAktualisieren(liste) {
        const offen = liste.querySelectorAll('.pj-wz:not(.done):not(.entf)').length;
        const z = liste.querySelector('.pj-waechter-zaehler');
        if (z) {
            z.textContent = offen ? (offen + ' offene' + (offen === 1 ? 'r Punkt' : ' Punkte'))
                                  : 'Alle Punkte erledigt';
        }
    }

    function phaseLaden(dialog, gewerkId, ziel) {
        const form = dialog.querySelector('form');
        const liste = form.querySelector('[data-offen]');
        const hinweis = form.querySelector('[data-hinweis]');
        const begr = form.querySelector('[data-begruendung]');
        const label = form.querySelector('[data-begruendung-label]');
        const senden = form.querySelector('[data-senden]');
        const meld = form.querySelector('[data-meldung]');
        if (meld) { meld.hidden = true; meld.textContent = ''; }
        liste.innerHTML = '';
        liste.appendChild(el('div', 'dezent', 'Offene Punkte werden geladen …'));
        return fetchJson('/projektierung/gewerk/' + gewerkId + '/waechter?ziel=' + encodeURIComponent(ziel))
            .then(function (d) {
                liste.innerHTML = '';
                dialog.dataset.begruendungPflicht = d.begruendung_pflicht ? '1' : '0';
                dialog.dataset.sperre = d.sperre || '';
                if (hinweis) {
                    hinweis.textContent = d.sperre || d.hinweis || '';
                    hinweis.classList.toggle('crit', !!d.sperre || (d.modus === 'sperren' && d.offen.length > 0));
                }
                if (d.offen.length) {
                    liste.appendChild(el('div', 'pj-waechter-zaehler',
                        d.offen.length + ' offene' + (d.offen.length === 1 ? 'r Punkt' : ' Punkte')
                        + ' (' + d.phase_name + ' → ' + d.ziel_name + ')'));
                    d.offen.forEach(function (p) { liste.appendChild(waechterZeile(p, liste)); });
                } else if (!d.sperre) {
                    liste.appendChild(el('div', 'pj-waechter-ok', '✓ Keine offenen Punkte für „' + d.ziel_name + '“.'));
                }
                if (begr) {
                    begr.required = !!d.begruendung_pflicht;
                    begr.placeholder = d.begruendung_pflicht ? 'Pflicht' : 'optional';
                }
                if (label) {
                    label.textContent = d.begruendung_pflicht
                        ? (d.rueckwaerts ? 'Begründung (Pflicht – rückwärts)' : 'Begründung (Pflicht – Modus sperren)')
                        : 'Begründung (optional)';
                }
                if (senden) { senden.disabled = !!d.sperre; }
                return d;
            })
            .catch(function () {
                liste.innerHTML = '';
                liste.appendChild(el('div', 'dezent', 'Offene Punkte konnten nicht geladen werden – der Server prüft beim Übernehmen.'));
            });
    }

    function phaseDialogOeffnen(id, optionen) {
        const dialog = document.getElementById(id);
        if (!dialog) { return; }
        const o = optionen || {};
        const form = dialog.querySelector('form');
        const zielFeld = form.querySelector('[data-ziel]');
        if (o.gewerk) { dialog.dataset.gewerk = o.gewerk; }
        if (o.ziel && zielFeld) {
            if (zielFeld.tagName === 'SELECT') { zielFeld.value = o.ziel; }
            else { zielFeld.value = o.ziel; }
        }
        if (o.action) { form.action = o.action; }
        if (o.titel) { const h = dialog.querySelector('h3'); if (h) { h.textContent = o.titel; } }
        const begr = form.querySelector('[data-begruendung]');
        if (begr) { begr.value = ''; }
        dialog.showModal();
        const ziel = zielFeld ? zielFeld.value : '';
        phaseLaden(dialog, dialog.dataset.gewerk, ziel);
    }
    window.pjPhaseDialogOeffnen = phaseDialogOeffnen;

    document.addEventListener('change', function (e) {
        const t = e.target;
        if (t && t.matches && t.matches('.pj-phase-dlg [data-ziel]')) {
            const dialog = t.closest('dialog');
            phaseLaden(dialog, dialog.dataset.gewerk, t.value);
        }
    });

    // Akte: klassischer POST (Server prüft erneut); Board: fetch (data-pj-phase-fetch)
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form || !form.matches || !form.matches('form[data-pj-phase]')) { return; }
        const dialog = form.closest('dialog');
        const begr = form.querySelector('[data-begruendung]');
        const meld = form.querySelector('[data-meldung]');
        if (dialog && dialog.dataset.sperre) {
            e.preventDefault();
            if (meld) { meld.textContent = dialog.dataset.sperre; meld.hidden = false; }
            return;
        }
        if (dialog && dialog.dataset.begruendungPflicht === '1' && begr && !begr.value.trim()) {
            e.preventDefault();
            if (meld) { meld.textContent = 'Bitte eine Begründung angeben (Pflicht).'; meld.hidden = false; }
            begr.focus();
            return;
        }
        if (form.hasAttribute('data-pj-phase-fetch') && window.fetch) {
            e.preventDefault();
            const knopf = form.querySelector('[data-senden]');
            if (knopf) { knopf.disabled = true; }
            fetchJson(form.action, {method: 'POST', body: new FormData(form)})
                .then(function (d) {
                    if (knopf) { knopf.disabled = false; }
                    if (!d.ok) {
                        if (meld) { meld.textContent = d.meldung || 'Phasenwechsel abgelehnt.'; meld.hidden = false; }
                        return;
                    }
                    dialog.close();
                    if (typeof window.pjBoardKarteVerschieben === 'function') {
                        window.pjBoardKarteVerschieben(dialog.dataset.gewerk, form.querySelector('[data-ziel]').value, d);
                    }
                    if (window.pjMeldung) { window.pjMeldung(d.meldung); }
                })
                .catch(function () {
                    if (knopf) { knopf.disabled = false; }
                    if (meld) { meld.textContent = 'Senden fehlgeschlagen – bitte erneut versuchen.'; meld.hidden = false; }
                });
        }
    }, true);

    // ---------- 3. Termin-Dialog ----------
    const ARTEN_TEAM = {montage: 'montage', elektro: 'montage', sub: 'sub'};

    function arbeitstagePlus(datum, tage) {
        const d = new Date(datum + 'T12:00:00');
        let rest = tage;
        while (rest > 0) {
            d.setDate(d.getDate() + 1);
            if (d.getDay() !== 0 && d.getDay() !== 6) { rest -= 1; }
        }
        return d.toISOString().slice(0, 10);
    }

    function monteurName(form, id) {
        const opt = form.querySelector('[data-monteur-wahl] option[value="' + id + '"]');
        return opt ? opt.textContent : ('#' + id);
    }

    function chipsRendern(form) {
        const chips = form.querySelector('[data-chips]');
        const felder = form.querySelector('[data-besetzung-felder]');
        if (!chips || !felder) { return; }
        chips.innerHTML = '';
        const ids = Array.prototype.map.call(felder.querySelectorAll('input[name=besetzung]'),
                                            function (i) { return i.value; });
        if (!ids.length) {
            chips.appendChild(el('span', 'pj-chips-leer', 'noch keine Besetzung – Team wählen oder Monteur hinzufügen'));
            return;
        }
        ids.forEach(function (id) {
            const chip = el('span', 'pj-chip-b', monteurName(form, id));
            const x = el('button', '', '×');
            x.type = 'button'; x.title = 'aus der Besetzung entfernen';
            x.addEventListener('click', function () {
                form.dataset.besetzungManuell = '1';
                besetzungSetzen(form, ids.filter(function (i) { return i !== id; }));
            });
            chip.appendChild(x);
            chips.appendChild(chip);
        });
    }

    function besetzungSetzen(form, ids) {
        const felder = form.querySelector('[data-besetzung-felder]');
        if (!felder) { return; }
        felder.innerHTML = '';
        const gesehen = {};
        (ids || []).forEach(function (id) {
            id = String(id).trim();
            if (!id || gesehen[id]) { return; }
            gesehen[id] = true;
            const i = document.createElement('input');
            i.type = 'hidden'; i.name = 'besetzung'; i.value = id;
            felder.appendChild(i);
        });
        chipsRendern(form);
    }

    function teamMitglieder(form) {
        const team = form.querySelector('[data-team]');
        const opt = team && team.options[team.selectedIndex];
        const roh = opt && opt.dataset.mitglieder ? opt.dataset.mitglieder : '';
        return roh ? roh.split(',').filter(Boolean) : [];
    }

    function artAnwenden(form) {
        const artFeld = form.querySelector('[data-art]');
        const art = artFeld ? artFeld.value : 'montage';
        const zeigen = {
            team: art === 'montage' || art === 'elektro' || art === 'sub',
            sub: art === 'sub',
            person: art === 'feinplanung' || art === 'abnahme' || art === 'sonstige',
            besetzung: art === 'montage' || art === 'elektro' || art === 'sub',
            vorschlaege: art === 'montage' && !form.action.match(/\/termin\/\d+\/bearbeiten/)
        };
        Object.keys(zeigen).forEach(function (k) {
            const block = form.querySelector('[data-feld="' + k + '"]');
            if (block) { block.hidden = !zeigen[k]; }
        });
        // Team-Liste: Montage-Teams für Montage/Elektro, Sub-Teams für Sub-Einsatz
        const team = form.querySelector('[data-team]');
        if (team) {
            const typ = ARTEN_TEAM[art] || '';
            Array.prototype.forEach.call(team.options, function (o) {
                if (!o.value) { return; }
                o.hidden = typ && o.dataset.typ !== typ;
            });
            const aktuell = team.options[team.selectedIndex];
            if (aktuell && aktuell.hidden) { team.value = ''; }
            team.required = art === 'montage' || art === 'elektro';
            const pflicht = form.querySelector('[data-team-pflicht]');
            if (pflicht) { pflicht.textContent = team.required ? '(Pflicht)' : (art === 'sub' ? '(oder Subunternehmer)' : ''); }
        }
        const person = form.querySelector('[name=person_id]');
        if (person) {
            person.required = art === 'feinplanung' || art === 'abnahme';
            const pflicht = form.querySelector('[data-person-pflicht]');
            if (pflicht) { pflicht.textContent = person.required ? '(Pflicht)' : '(optional)'; }
        }
        const endeHinweis = form.querySelector('[data-ende-hinweis]');
        if (endeHinweis) {
            const dauer = parseInt(form.dataset.dauer || '5', 10);
            endeHinweis.textContent = (art === 'montage' || art === 'elektro')
                ? '(leer = Beginn + ' + (dauer - 1) + ' Arbeitstage)' : '(leer = Beginn)';
        }
        endeVorbelegen(form);
    }

    function endeVorbelegen(form) {
        const beginn = form.querySelector('[data-beginn]');
        const ende = form.querySelector('[data-ende]');
        if (!beginn || !ende || !beginn.value || ende.dataset.manuell === '1') { return; }
        const art = (form.querySelector('[data-art]') || {}).value || 'montage';
        const dauer = parseInt(form.dataset.dauer || '5', 10);
        ende.value = (art === 'montage' || art === 'elektro')
            ? arbeitstagePlus(beginn.value, Math.max(0, dauer - 1)) : beginn.value;
    }

    function vorschlaegeLaden(form) {
        const dialog = form.closest('dialog');
        const liste = form.querySelector('[data-vorschlaege-liste]');
        const gewerk = dialog ? dialog.dataset.gewerk : '';
        if (!liste || !gewerk) { return; }
        liste.innerHTML = '';
        liste.appendChild(el('div', 'dezent', 'Vorschläge werden berechnet …'));
        const team = form.querySelector('[data-team]');
        const url = '/projektierung/gewerk/' + gewerk + '/terminvorschlaege.json'
            + '?team_id=' + encodeURIComponent(team && team.value ? team.value : '0')
            + '&dauer_tage=' + encodeURIComponent(form.dataset.dauerWahl || '0');
        fetchJson(url).then(function (d) {
            liste.innerHTML = '';
            if (!d.ok) { liste.appendChild(el('div', 'pj-note crit', d.meldung || 'Fehler')); return; }
            if (d.hinweis) { liste.appendChild(el('div', 'pj-note', d.hinweis)); }
            if (!d.vorschlaege.length) {
                liste.appendChild(el('div', 'dezent', 'Keine freien Fenster in den nächsten 26 Wochen.'));
                return;
            }
            d.vorschlaege.forEach(function (v) {
                const k = el('button', 'pj-vorschlag');
                k.type = 'button';
                k.appendChild(el('b', '', v.beginn_text + '–' + v.ende_text));
                k.appendChild(el('span', '', v.team_name + ' · ' + v.begruendung));
                k.appendChild(el('span', 'um', 'Umweg ' + v.umweg_text));
                k.addEventListener('click', function () {
                    if (team) { team.value = String(v.team_id); }
                    const beginn = form.querySelector('[data-beginn]');
                    const ende = form.querySelector('[data-ende]');
                    if (beginn) { beginn.value = v.beginn; }
                    if (ende) { ende.value = v.ende; ende.dataset.manuell = '1'; }
                    form.dataset.besetzungManuell = '0';
                    besetzungSetzen(form, v.besetzung || []);
                    if (window.pjMeldung) { window.pjMeldung('Vorschlag übernommen: ' + v.beginn_text + '–' + v.ende_text + ' · ' + v.team_name); }
                });
                liste.appendChild(k);
            });
        }).catch(function () {
            liste.innerHTML = '';
            liste.appendChild(el('div', 'pj-note crit', 'Vorschläge konnten nicht geladen werden.'));
        });
    }

    function terminDialogOeffnen(id, optionen) {
        const dialog = document.getElementById(id);
        if (!dialog) { return; }
        const o = optionen || {};
        const form = dialog.querySelector('form');
        if (o.gewerk) {
            dialog.dataset.gewerk = o.gewerk;
            form.action = '/projektierung/gewerk/' + o.gewerk + '/termin';
        }
        if (o.sparte !== undefined) {
            dialog.dataset.sparte = o.sparte;
            const s = dialog.querySelector('[data-sparte-text]');
            if (s) { s.textContent = o.sparte; }
        }
        if (o.zurueck) {
            let z = form.querySelector('input[name=zurueck]');
            if (!z) { z = document.createElement('input'); z.type = 'hidden'; z.name = 'zurueck'; form.appendChild(z); }
            z.value = o.zurueck;
        }
        const artFeld = form.querySelector('[data-art]');
        if (o.art && artFeld && !artFeld.disabled) { artFeld.value = o.art; }
        const meld = form.querySelector('[data-meldung]');
        if (meld) { meld.hidden = true; meld.textContent = ''; }
        artAnwenden(form);
        chipsRendern(form);
        dialog.showModal();
    }
    window.pjTerminDialogOeffnen = terminDialogOeffnen;

    document.addEventListener('change', function (e) {
        const t = e.target;
        if (!t || !t.matches) { return; }
        const form = t.closest('form[data-pj-termin]');
        if (!form) { return; }
        if (t.matches('[data-art]')) { artAnwenden(form); }
        else if (t.matches('[data-team]')) {
            if (form.dataset.besetzungManuell !== '1') { besetzungSetzen(form, teamMitglieder(form)); }
            else if (!form.querySelector('input[name=besetzung]')) { besetzungSetzen(form, teamMitglieder(form)); }
        }
        else if (t.matches('[data-beginn]')) { endeVorbelegen(form); }
        else if (t.matches('[data-ende]')) { t.dataset.manuell = t.value ? '1' : '0'; }
        else if (t.matches('[data-monteur-wahl]')) {
            if (t.value) {
                form.dataset.besetzungManuell = '1';
                const ids = Array.prototype.map.call(form.querySelectorAll('input[name=besetzung]'),
                                                    function (i) { return i.value; });
                ids.push(t.value);
                besetzungSetzen(form, ids);
                t.value = '';
            }
        }
    });

    document.addEventListener('click', function (e) {
        const k = e.target && e.target.closest ? e.target.closest('[data-vorschlaege]') : null;
        if (k) { vorschlaegeLaden(k.closest('form')); }
    });

    // Senden per fetch – Erfolg: Meldung + Neuladen (Block Termine, Terminstatus)
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form || !form.matches || !form.matches('form[data-pj-termin]') || !window.fetch) { return; }
        e.preventDefault();
        const meld = form.querySelector('[data-meldung]');
        const knopf = form.querySelector('button[type=submit]');
        if (knopf) { knopf.disabled = true; }
        const artFeld = form.querySelector('[data-art]');
        const fd = new FormData(form);
        if (artFeld && artFeld.disabled && !fd.get('art')) { fd.append('art', artFeld.value); }
        fetchJson(form.action, {method: 'POST', body: fd})
            .then(function (d) {
                if (knopf) { knopf.disabled = false; }
                if (!d.ok) {
                    if (meld) { meld.textContent = d.meldung || 'Speichern abgelehnt.'; meld.hidden = false; }
                    return;
                }
                let text = d.meldung || 'Gespeichert.';
                if (d.konflikte && d.konflikte.length) { text += ' ⚠ Konflikt: ' + d.konflikte.slice(0, 3).join('; '); }
                try { sessionStorage.setItem('pjMeldung', text); } catch (fehler) { /* egal */ }
                const dialog = form.closest('dialog');
                if (dialog) { dialog.close(); }
                const zurueck = fd.get('zurueck');
                const ziel = (zurueck && String(zurueck).indexOf('/projektierung') === 0) ? String(zurueck) : (location.pathname + location.search);
                const trenner = ziel.indexOf('?') >= 0 ? '&' : '?';
                location.href = ziel.split('#')[0] + trenner + 'meldung=' + encodeURIComponent(text) + '#termine';
            })
            .catch(function () {
                if (knopf) { knopf.disabled = false; }
                if (meld) { meld.textContent = 'Senden fehlgeschlagen – bitte erneut versuchen.'; meld.hidden = false; }
            });
    }, true);

    document.addEventListener('DOMContentLoaded', function () {
        boardInit();
        document.querySelectorAll('form[data-pj-termin]').forEach(function (form) {
            artAnwenden(form);
            chipsRendern(form);
        });
    });
})();
