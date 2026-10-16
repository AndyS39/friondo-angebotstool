/* v32 (PLAN_V19 Phase 161/162): Vertriebler-Ansicht „Mein Tag“ (templates/leads/mein_tag.html).
   v33 (PLAN_V20 Phase 173, Design-Entwurf „Außendienst App“): Verhalten der mobilen Ansicht
   und der Seite „Wiedervorlage“ – wird auch über leads/_leiste.html (untere Leiste, base.html)
   geladen, läuft dank Schutz nur einmal.
   - viewport-fit=cover (Safe-Area wie die mobile Erfassung v14).
   - Untere Leiste: Body-Klasse mt-mit-leiste als Rückfall für Browser ohne :has(). v38
     (PLAN_V23 Phase 204): der Eintrag „Kunden“ (Kopfzeilen-Suche aufklappen) ist durch den
     Reiter „Vergangene Termine“ ersetzt – die Suche bleibt über die Lupe im Hauptmenü.
   v38 (PLAN_V23 Phase 203/204), Abschnitte am Ende:
   - Leads VOT Desktop: Klappzustand der Gruppen je Benutzer in localStorage (Schlüssel
     lv_gruppen_<benutzer-id>; „Vergangene Termine“ standardmäßig zu, die übrigen offen).
   - Kanal-Menü hinter dem Pfeil der Kanalzelle (data-lv-kanal-pfeil): Einträge aus
     <template data-lv-kanal-optionen>, aktueller Wert markiert, Tastatur (Pfeile, Enter, Escape),
     Klick außerhalb schließt; Auswahl → POST /leads/{id}/kanal (Accept: application/json) →
     Badge-HTML aus der Antwort ersetzt das Badge, Meldung in #lm-meldung.
   - Dialog „Termin nicht stattgefunden“ (data-ta-dialog, Makro termin_ausgefallen_dialog):
     Knopf data-ta-oeffnen füllt Titel/Ziel; Grund steuert Pflicht-Freitext und Vorbelegung der
     Folge (data-ta-vorbelegung); „Kunde möchte keinen neuen Termin“ klappt „Kunden
     disqualifizieren?“ auf (Pflichtgrund, Freitext bei Sonstiges); Senden per fetch (JSON) →
     Karte/Zeile des Termins verschwindet, Zähler sinken, Meldung; Abbrechen/Escape ändert nichts.
   - Seite „Vergangene Termine“: Suchfeld filtert die Karten nach Name (clientseitig), leere
     Tage werden ausgeblendet, Zähler und Leerzustand folgen.
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

    // ---------- v38 (Phase 203): Klappzustand der Leads-VOT-Gruppen je Benutzer ----------
    var lokal = {
        lesen: function (k) { try { return JSON.parse(window.localStorage.getItem(k) || '{}') || {}; } catch (e) { return {}; } },
        schreiben: function (k, v) { try { window.localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* privat/gesperrt */ } }
    };
    bereit(function () {
        var wurzel = document.querySelector('[data-lv-gruppen]');
        if (!wurzel) { return; }
        var schluessel = 'lv_gruppen_' + (wurzel.getAttribute('data-benutzer') || '0');
        var zustand = lokal.lesen(schluessel);
        wurzel.querySelectorAll('details[data-gruppe]').forEach(function (d) {
            var key = d.getAttribute('data-gruppe');
            if (Object.prototype.hasOwnProperty.call(zustand, key)) { d.open = !!zustand[key]; }
            d.addEventListener('toggle', function () {
                var jetzt = lokal.lesen(schluessel);
                jetzt[key] = d.open;
                lokal.schreiben(schluessel, jetzt);
            });
        });
    });

    // ---------- v38 (Phase 203): Kanal-Menü hinter dem Pfeil (Leads VOT Desktop) ----------
    function seitenMeldung(text, fehler) {
        var el = document.getElementById('lm-meldung') || document.querySelector('[data-mt-meldung]');
        if (!el) { return; }
        el.textContent = text || '';
        el.classList.toggle('fehler', !!fehler);
        el.hidden = !text;
        window.clearTimeout(el.__mtTimer);
        if (text && !fehler) { el.__mtTimer = window.setTimeout(function () { el.hidden = true; }, 6000); }
    }

    (function kanalMenue() {
        var menue = document.querySelector('[data-lv-kanal-menue]');
        var vorlage = document.querySelector('template[data-lv-kanal-optionen]');
        if (!menue || !vorlage || !vorlage.content) { return; }
        var aktiverPfeil = null;
        var geoeffnetUm = 0;

        function eintraege() { return Array.prototype.slice.call(menue.querySelectorAll('[role="menuitemradio"]')); }

        function positionieren() {
            if (!aktiverPfeil || menue.hidden) { return; }
            var rect = aktiverPfeil.getBoundingClientRect();
            menue.style.top = Math.round(rect.bottom + 4) + 'px';
            var links = Math.max(8, Math.min(rect.left - 8, window.innerWidth - menue.offsetWidth - 8));
            menue.style.left = Math.round(links) + 'px';
        }

        function schliessen(fokus) {
            if (menue.hidden) { return; }
            menue.hidden = true;
            menue.innerHTML = '';
            if (aktiverPfeil) {
                aktiverPfeil.setAttribute('aria-expanded', 'false');
                if (fokus) { try { aktiverPfeil.focus(); } catch (e) { /* egal */ } }
            }
            aktiverPfeil = null;
        }

        function eintrag(wert, text, aktuell) {
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'lv-kanal-eintrag' + (aktuell ? ' aktuell' : '');
            b.setAttribute('role', 'menuitemradio');
            b.setAttribute('aria-checked', aktuell ? 'true' : 'false');
            b.setAttribute('data-wert', wert);
            b.textContent = text;
            return b;
        }

        function oeffnen(pfeil) {
            schliessen(false);
            var aktuell = (pfeil.getAttribute('data-aktuell') || '').toLowerCase();
            menue.innerHTML = '';
            menue.appendChild(eintrag('', '– (Sync-Automatik)', aktuell === ''));
            var gefunden = aktuell === '';
            Array.prototype.forEach.call(vorlage.content.querySelectorAll('option'), function (o) {
                var ist = (o.value || '').toLowerCase() === aktuell;
                if (ist) { gefunden = true; }
                menue.appendChild(eintrag(o.value, o.textContent, ist));
            });
            if (!gefunden) {
                var roh = pfeil.getAttribute('data-aktuell') || '';
                menue.appendChild(eintrag(roh, roh + (roh === '?' ? ' – Vertriebskanal klären' : ' (nicht mehr wählbar)'), true));
            }
            aktiverPfeil = pfeil;
            menue.hidden = false;
            positionieren();
            pfeil.setAttribute('aria-expanded', 'true');
            geoeffnetUm = Date.now();
            var start = menue.querySelector('[aria-checked="true"]') || menue.firstElementChild;
            // Fokus ohne Scroll – ein Scroll-Ereignis direkt nach dem Öffnen würde das Menü sonst schließen
            if (start) { try { start.focus({ preventScroll: true }); } catch (e) { start.focus(); } }
        }

        function speichern(wert) {
            var pfeil = aktiverPfeil;
            if (!pfeil) { return; }
            var zelle = pfeil.closest('[data-lv-kanal-zelle]');
            var url = pfeil.getAttribute('data-url');
            schliessen(true);
            if (!window.fetch || !zelle || !url) { return; }
            var daten = new FormData();
            daten.append('kanal', wert);
            pfeil.disabled = true;
            fetch(url, { method: 'POST', body: daten, credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
                .then(function (r) { return r.json().then(function (a) { return a; }, function () { return null; }); })
                .then(function (antwort) {
                    pfeil.disabled = false;
                    if (!antwort) { window.location.reload(); return; }
                    if (!antwort.ok) { seitenMeldung(antwort.meldung || 'Kanal konnte nicht gespeichert werden.', true); return; }
                    var badge = zelle.querySelector('[data-lv-kanal-badge]');
                    if (badge) {
                        if (antwort.badge_html) { badge.innerHTML = antwort.badge_html; }
                        else { badge.innerHTML = ''; var leer = document.createElement('span'); leer.className = 'dezent'; leer.textContent = '–'; badge.appendChild(leer); }
                    }
                    zelle.setAttribute('data-wert', antwort.kanal || '');
                    pfeil.setAttribute('data-aktuell', antwort.kanal || '');
                    var manuell = zelle.querySelector('[data-lv-kanal-manuell]');
                    if (manuell) { manuell.hidden = !antwort.manuell; }
                    seitenMeldung(antwort.meldung || 'Kanal gespeichert.', false);
                })
                .catch(function () { pfeil.disabled = false; seitenMeldung('Speichern fehlgeschlagen (Verbindung).', true); });
        }

        document.addEventListener('click', function (ev) {
            var pfeil = ev.target.closest && ev.target.closest('[data-lv-kanal-pfeil]');
            if (pfeil) {
                ev.preventDefault();
                if (aktiverPfeil === pfeil && !menue.hidden) { schliessen(true); } else { oeffnen(pfeil); }
                return;
            }
            var wahl = ev.target.closest && ev.target.closest('[data-lv-kanal-menue] [role="menuitemradio"]');
            if (wahl) { speichern(wahl.getAttribute('data-wert') || ''); return; }
            if (!menue.hidden && !menue.contains(ev.target)) { schliessen(false); }
        });
        document.addEventListener('keydown', function (ev) {
            if (menue.hidden) { return; }
            var liste = eintraege();
            var i = liste.indexOf(document.activeElement);
            if (ev.key === 'Escape') { ev.preventDefault(); schliessen(true); }
            else if (ev.key === 'ArrowDown') { ev.preventDefault(); (liste[(i + 1) % liste.length] || liste[0]).focus(); }
            else if (ev.key === 'ArrowUp') { ev.preventDefault(); (liste[(i - 1 + liste.length) % liste.length] || liste[0]).focus(); }
            else if (ev.key === 'Home') { ev.preventDefault(); liste[0] && liste[0].focus(); }
            else if (ev.key === 'End') { ev.preventDefault(); liste[liste.length - 1] && liste[liste.length - 1].focus(); }
            else if (ev.key === 'Tab') { schliessen(false); }
            else if ((ev.key === 'Enter' || ev.key === ' ') && i >= 0) { ev.preventDefault(); speichern(liste[i].getAttribute('data-wert') || ''); }
        });
        // Scrollen schließt das Menü (feste Position) – nicht in den ersten 300 ms nach dem Öffnen
        // (Scroll-Ereignisse aus Fokus/scrollIntoView); Größenänderung positioniert nur neu
        window.addEventListener('scroll', function () { if (Date.now() - geoeffnetUm > 300) { schliessen(false); } }, true);
        window.addEventListener('resize', positionieren);
    })();

    // ---------- v38 (Phase 204): Dialog „Termin nicht stattgefunden“ ----------
    (function terminAusgefallen() {
        var dialog = document.querySelector('[data-ta-dialog]');
        if (!dialog) { return; }
        var form = dialog.querySelector('[data-ta-form]');
        var untertitel = dialog.querySelector('[data-ta-untertitel]');
        var grundText = dialog.querySelector('[data-ta-grund-text]');
        var dq = dialog.querySelector('[data-ta-dq]');
        var dqGrund = dialog.querySelector('[data-ta-dq-grund]');
        var dqText = dialog.querySelector('[data-ta-dq-text]');
        var fehler = dialog.querySelector('[data-ta-fehler]');
        var senden = dialog.querySelector('[data-ta-senden]');
        var vorbelegung = {};
        try { vorbelegung = JSON.parse(form.getAttribute('data-ta-vorbelegung') || '{}') || {}; } catch (e) { vorbelegung = {}; }
        var aktuellerKnopf = null;

        function gewaehlt(name) { var el = form.querySelector('input[name="' + name + '"]:checked'); return el ? el.value : ''; }
        function fehlerZeigen(text) { if (!fehler) { return; } fehler.textContent = text || ''; fehler.hidden = !text; }

        function grundAnwenden(vorbelegen) {
            var grund = gewaehlt('grund');
            var sonstiges = grund === 'sonstiges';
            if (grundText) {
                grundText.hidden = !sonstiges;
                var feld = grundText.querySelector('input');
                if (feld) { feld.required = sonstiges; if (sonstiges) { feld.focus(); } }
            }
            if (vorbelegen && vorbelegung[grund]) {
                var ziel = form.querySelector('input[name="folge"][value="' + vorbelegung[grund] + '"]');
                if (ziel) { ziel.checked = true; }
            }
            folgeAnwenden();
        }

        function folgeAnwenden() {
            var folge = gewaehlt('folge');
            var kein = folge === 'kein_termin';
            if (dq) { dq.hidden = !kein; }
            if (dqGrund) { dqGrund.required = kein; }
            if (senden) { senden.textContent = kein ? senden.getAttribute('data-text-dq') : senden.getAttribute('data-text-neu'); senden.classList.toggle('gefaehrlich', kein); }
            form.querySelectorAll('.ta-folge').forEach(function (l) { var r = l.querySelector('input'); l.classList.toggle('gewaehlt', !!(r && r.checked)); });
            dqGrundAnwenden();
        }

        function dqGrundAnwenden() {
            if (!dqGrund || !dqText) { return; }
            var opt = dqGrund.options[dqGrund.selectedIndex];
            var pflicht = !!(opt && opt.getAttribute('data-freitext-pflicht') === '1') && !dq.hidden;
            dqText.hidden = !pflicht;
            var feld = dqText.querySelector('input');
            if (feld) { feld.required = pflicht; }
        }

        function oeffnen(knopf) {
            aktuellerKnopf = knopf;
            form.reset();
            form.action = knopf.getAttribute('data-ta-url') || '';
            if (untertitel) { untertitel.textContent = (knopf.getAttribute('data-ta-name') || '') + ' · ' + (knopf.getAttribute('data-ta-zeit') || ''); }
            fehlerZeigen('');
            var erster = form.querySelector('input[name="grund"]');
            if (erster) { erster.checked = true; }
            grundAnwenden(true);
            if (typeof dialog.showModal === 'function') { if (!dialog.open) { dialog.showModal(); } } else { dialog.setAttribute('open', ''); }
            var fokus = form.querySelector('input[name="grund"]:checked');
            if (fokus) { try { fokus.focus(); } catch (e) { /* egal */ } }
        }

        function schliessen() {
            if (typeof dialog.close === 'function' && dialog.open) { dialog.close(); } else { dialog.removeAttribute('open'); }
            var knopf = aktuellerKnopf;
            aktuellerKnopf = null;
            if (knopf && document.body.contains(knopf)) { try { knopf.focus(); } catch (e) { /* egal */ } }
        }

        function zaehlerMinus(selektor) {
            document.querySelectorAll(selektor).forEach(function (el) {
                var n = Math.max(0, (parseInt(el.textContent, 10) || 0) - 1);
                el.textContent = String(n);
            });
        }

        function terminEntfernen(terminId) {
            document.querySelectorAll('[data-termin="' + terminId + '"]').forEach(function (el) {
                var tag = el.closest('[data-mt-vg-tag]');
                var gruppe = el.closest('details.lm-gruppe');
                el.remove();
                if (tag && !tag.querySelector('[data-mt-vergangen]')) { tag.remove(); }
                if (gruppe) {
                    var n = gruppe.querySelectorAll('tbody tr').length;
                    var z = gruppe.querySelector('summary .n');
                    if (z) { z.textContent = String(n); }
                }
            });
            zaehlerMinus('[data-mt-vg-zahl]');
            var liste = document.querySelector('[data-mt-vg-liste]');
            var leer = document.querySelector('[data-mt-vg-leer]');
            if (liste && leer && !liste.querySelector('[data-mt-vergangen]')) {
                leer.hidden = false;
                var alles = leer.querySelector('[data-mt-vg-leer-alles]');
                if (alles) { alles.hidden = false; }
            }
            var heute = document.querySelector('#termine-heute .mt-zaehler');
            var heuteListe = document.querySelector('#termine-heute .mt-zeitstrahl');
            if (heute && heuteListe) {
                var m = heuteListe.querySelectorAll('.mt-termin').length;
                heute.textContent = m + ' Termin' + (m === 1 ? '' : 'e');
            }
        }

        document.addEventListener('click', function (ev) {
            var knopf = ev.target.closest && ev.target.closest('[data-ta-oeffnen]');
            if (knopf) { ev.preventDefault(); oeffnen(knopf); return; }
            var abbruch = ev.target.closest && ev.target.closest('[data-ta-abbrechen]');
            if (abbruch && dialog.contains(abbruch)) { ev.preventDefault(); schliessen(); return; }
            if (dialog.open && ev.target === dialog) { schliessen(); }   // Klick auf den Hintergrund
        });
        dialog.addEventListener('cancel', function (ev) { ev.preventDefault(); schliessen(); });
        form.addEventListener('change', function (ev) {
            var el = ev.target;
            if (el.name === 'grund') { grundAnwenden(true); }
            else if (el.name === 'folge') { folgeAnwenden(); }
            else if (el.name === 'dq_grund') { dqGrundAnwenden(); }
        });
        form.addEventListener('submit', function (ev) {
            if (!window.fetch || !window.FormData) { return; }
            ev.preventDefault();
            fehlerZeigen('');
            var folge = gewaehlt('folge');
            if (folge === 'kein_termin' && dqGrund && !dqGrund.value) { fehlerZeigen('Kunden disqualifizieren: bitte einen Grund wählen.'); dqGrund.focus(); return; }
            var knopf = aktuellerKnopf;
            var terminId = knopf ? knopf.getAttribute('data-ta-termin') : '';
            senden.disabled = true;
            fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
                .then(function (r) { return r.json().then(function (a) { return a; }, function () { return null; }); })
                .then(function (antwort) {
                    senden.disabled = false;
                    if (!antwort) { form.submit(); return; }
                    if (!antwort.ok) { fehlerZeigen(antwort.meldung || 'Speichern fehlgeschlagen.'); return; }
                    schliessen();
                    if (terminId) { terminEntfernen(terminId); }
                    seitenMeldung(antwort.meldung || 'Gespeichert.', false);
                    var top = document.querySelector('.mt-mobil, .mt-desktop');
                    if (top && !document.getElementById('lm-meldung') && !document.querySelector('[data-mt-meldung]')) {
                        var p = document.createElement('p'); p.className = 'meldung'; p.setAttribute('role', 'status');
                        p.textContent = antwort.meldung || 'Gespeichert.'; top.insertBefore(p, top.firstChild);
                    }
                    document.dispatchEvent(new CustomEvent('ta:gespeichert', { detail: antwort }));
                })
                .catch(function () { senden.disabled = false; fehlerZeigen('Speichern fehlgeschlagen (Verbindung).'); });
        });
    })();

    // ---------- v38 (Phase 204): Seite „Vergangene Termine“ – Suche nach Name ----------
    bereit(function () {
        var bereich = document.querySelector('[data-mt-vergangene]');
        if (!bereich) { return; }
        var suche = bereich.querySelector('[data-mt-suche]');
        var leer = bereich.querySelector('[data-mt-vg-leer]');
        var leerAlles = bereich.querySelector('[data-mt-vg-leer-alles]');
        var leerSuche = bereich.querySelector('[data-mt-vg-leer-suche]');
        function anwenden() {
            var q = suche ? suche.value.trim().toLowerCase() : '';
            var gesamt = 0, sichtbar = 0;
            bereich.querySelectorAll('[data-mt-vg-tag]').forEach(function (tag) {
                var n = 0;
                tag.querySelectorAll('[data-mt-vergangen]').forEach(function (k) {
                    gesamt += 1;
                    var treffer = !q || (k.getAttribute('data-name') || '').indexOf(q) >= 0;
                    k.hidden = !treffer;
                    if (treffer) { n += 1; }
                });
                tag.hidden = n === 0;
                var z = tag.querySelector('[data-mt-vg-tag-zahl]');
                if (z) { z.textContent = String(n); }
                sichtbar += n;
            });
            bereich.querySelectorAll('[data-mt-vg-zahl]').forEach(function (el) { el.textContent = String(sichtbar); });
            if (leer) { leer.hidden = sichtbar > 0; }
            if (leerAlles) { leerAlles.hidden = !(sichtbar === 0 && gesamt === 0); }
            if (leerSuche) { leerSuche.hidden = !(sichtbar === 0 && gesamt > 0); }
        }
        if (suche) {
            var timer = null;
            suche.addEventListener('input', function () { window.clearTimeout(timer); timer = window.setTimeout(anwenden, 80); });
            suche.addEventListener('search', anwenden);
        }
        document.addEventListener('ta:gespeichert', function () { window.setTimeout(anwenden, 0); });
    });
})();
