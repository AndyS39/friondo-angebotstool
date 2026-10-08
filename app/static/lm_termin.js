// Lead-Management V2 (v23, Phase 108): Terminassistent – Mini-Karte je
// Vorschlag (Leaflet lokal, OSM-Kacheln wie karte.html), Live-Konfliktprüfung
// des manuellen Formulars (GET /lead-management/termin/konflikt) und
// 15-Minuten-Rundung der Uhrzeit. Vanilla JS, kein Framework.
// v29 (PLAN_LEAD_V4 Phase 143): zweiter Block unten – Kalenderansicht per fetch.
(function () {
    'use strict';

    // --- Mini-Karte -----------------------------------------------------------------
    const kartenDiv = document.getElementById('lmt-karte');
    let karte = null;
    let ebene = null;

    function karteInit() {
        if (!kartenDiv || typeof L === 'undefined' || karte) return;
        const lat = parseFloat(kartenDiv.dataset.lat) || 51.4344;
        const lon = parseFloat(kartenDiv.dataset.lon) || 6.7623;
        karte = L.map('lmt-karte').setView([lat, lon], 11);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende'
        }).addTo(karte);
        L.Icon.Default.prototype.options.imagePath = '/static/leaflet/images/';
        ebene = L.layerGroup().addTo(karte);
    }

    async function tourZeigen(adId, datum, nr) {
        karteInit();
        if (!karte) return;
        ebene.clearLayers();
        const titel = document.getElementById('lmt-karte-titel');
        if (titel) titel.textContent = 'Mini-Karte: Tagestour Vorschlag ' + (nr || '');
        const params = new URLSearchParams({
            ad_id: adId, datum: datum,
            lat: kartenDiv.dataset.lat || '', lon: kartenDiv.dataset.lon || ''
        });
        let daten;
        try {
            const antwort = await fetch('/lead-management/karte/tag?' + params.toString());
            daten = await antwort.json();
        } catch (e) {
            return;
        }
        const punkte = [];
        for (const p of (daten.pins || [])) {
            if (p.art === 'termin') {
                L.marker([p.lat, p.lon]).bindTooltip(p.nr + '. ' + p.zeit,
                    {permanent: true, direction: 'top'}).addTo(ebene);
                punkte.push([p.lat, p.lon]);
            } else if (p.art === 'kandidat') {
                L.circleMarker([p.lat, p.lon], {radius: 11, color: '#d4a017', fillOpacity: 0.9})
                    .bindTooltip('★ Kandidat', {permanent: true, direction: 'top'}).addTo(ebene);
                punkte.push([p.lat, p.lon]);
            }
        }
        if (punkte.length > 1) {
            L.polyline(punkte, {color: '#3f86c6', dashArray: '6 6'}).addTo(ebene);
            karte.fitBounds(punkte, {padding: [30, 30]});
        } else if (punkte.length === 1) {
            karte.setView(punkte[0], 12);
        }
    }

    document.querySelectorAll('.lmt-vorschlag').forEach(function (kartenElement) {
        const knopf = kartenElement.querySelector('.lmt-karte-knopf');
        const zeigen = function () {
            document.querySelectorAll('.lmt-vorschlag.aktiv').forEach(function (x) { x.classList.remove('aktiv'); });
            kartenElement.classList.add('aktiv');
            tourZeigen(kartenElement.dataset.ad, kartenElement.dataset.datum, kartenElement.dataset.nr);
            if (kartenDiv) kartenDiv.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        };
        if (knopf) knopf.addEventListener('click', zeigen);
    });
    if (kartenDiv) {
        tourZeigen(kartenDiv.dataset.ad, kartenDiv.dataset.datum, 1);
    }

    // --- Manuelles Formular: Rundung + Konfliktprüfung ----------------------------------
    const form = document.getElementById('lmt-manuell');
    if (!form) return;
    const datum = form.querySelector('input[name=datum]');
    const uhrzeit = form.querySelector('input[name=uhrzeit]');
    const ad = form.querySelector('select[name=ad_id]');
    const box = document.getElementById('lmt-konflikte');
    const bestaetigen = document.getElementById('lmt-bestaetigen');
    const schritt = Math.max(5, Math.round((parseInt(uhrzeit.step, 10) || 900) / 60));

    function runden() {
        if (!uhrzeit.value) return;
        const teile = uhrzeit.value.split(':');
        let minuten = parseInt(teile[0], 10) * 60 + parseInt(teile[1], 10);
        minuten = Math.round(minuten / schritt) * schritt;
        if (minuten >= 24 * 60) minuten = 24 * 60 - schritt;
        const h = String(Math.floor(minuten / 60)).padStart(2, '0');
        const m = String(minuten % 60).padStart(2, '0');
        const neu = h + ':' + m;
        if (neu !== uhrzeit.value) uhrzeit.value = neu;
    }

    let laufend = null;
    async function pruefen() {
        if (!datum.value || !uhrzeit.value || !ad || !ad.value) { box.hidden = true; return; }
        const params = new URLSearchParams({
            ad_id: ad.value, beginn: datum.value + 'T' + uhrzeit.value,
            vorgang_id: form.dataset.vorgang || ''
        });
        const meinLauf = {};
        laufend = meinLauf;
        let daten;
        try {
            const antwort = await fetch(form.dataset.konfliktUrl + '?' + params.toString());
            daten = await antwort.json();
        } catch (e) {
            return;
        }
        if (laufend !== meinLauf) return;
        box.innerHTML = '';
        box.classList.remove('sperre', 'warnung', 'frei');
        if (!daten.texte || !daten.texte.length) {
            box.textContent = 'Keine Konflikte für ' + uhrzeit.value + ' Uhr.';
            box.classList.add('frei');
            box.hidden = false;
            if (bestaetigen) bestaetigen.classList.add('lmt-versteckt');
            return;
        }
        const titel = document.createElement('strong');
        titel.textContent = daten.sperren ? 'Nicht buchbar: ' : 'Konflikte (Bestätigung nötig): ';
        box.appendChild(titel);
        const liste = document.createElement('ul');
        daten.texte.forEach(function (t) {
            const li = document.createElement('li');
            li.textContent = t;
            liste.appendChild(li);
        });
        box.appendChild(liste);
        box.classList.add(daten.sperren ? 'sperre' : 'warnung');
        box.hidden = false;
        if (bestaetigen) {
            if (daten.sperren) bestaetigen.classList.add('lmt-versteckt');
            else bestaetigen.classList.remove('lmt-versteckt');
        }
    }

    uhrzeit.addEventListener('change', function () { runden(); pruefen(); });
    datum.addEventListener('change', pruefen);
    if (ad) ad.addEventListener('change', pruefen);
    if (datum.value && uhrzeit.value) pruefen();
})();


// --- v29 (PLAN_LEAD_V4 Phase 143): Kalenderansicht des Assistenten ---------------------
// Lädt GET …/termin/kalender.json?woche=YYYY-MM-DD (Cache 10 Min, ?neu=1 erzwingt) und
// baut die Wochenansicht Mo–Sa im 15-Minuten-Raster: je Tag eine Spaltengruppe, darin
// eine Spalte je Kandidat (plus „Weitere Kalender“ grau „außerhalb der Vorauswahl“).
// Zellen: frei (Arbeitszeit) · außerhalb · vergangen · Tool-Termin (Art, vorgemerkt
// gestrichelt, eigener Lead umrandet) · Sperrzeit (HV) · Outlook belegt · Vorschlag
// (1 = Ideal). Klick auf einen freien Slot oder einen Vorschlags-Slot füllt das
// Formular „Manuell setzen“ (Datum, Uhrzeit, Vertriebler) und stößt die
// Konfliktprüfung an; Kalender außerhalb der Vorauswahl zeigen den Warnhinweis.
(function () {
    'use strict';
    const wurzel = document.getElementById('lmt-kalender');
    if (!wurzel || !window.fetch) { return; }
    const tabelle = wurzel.querySelector('[data-rolle="tabelle"]');
    const hinweis = wurzel.querySelector('[data-rolle="hinweis"]');
    const wocheText = wurzel.querySelector('[data-rolle="woche"]');
    const form = document.getElementById('lmt-manuell');
    const adWahl = document.getElementById('lmt-ad-wahl');
    const weitereOptgroup = document.getElementById('lmt-weitere-optgroup');
    const warnung = document.getElementById('lmt-ausserhalb');
    let daten = null;
    let woche = '';            // '' = Woche des ersten Vorschlags (Server-Standard)
    let laufend = null;

    function pad(n) { return String(n).padStart(2, '0'); }
    function minuten(iso) {   // 'YYYY-MM-DDTHH:MM' → Minuten seit Tagesbeginn
        return parseInt(iso.slice(11, 13), 10) * 60 + parseInt(iso.slice(14, 16), 10);
    }
    function datumVon(iso) { return iso.slice(0, 10); }
    function jetztIso() {
        const d = new Date();
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    }
    function hinweisSetzen(text, klasse) {
        if (!hinweis) { return; }
        hinweis.textContent = text || '';
        hinweis.hidden = !text;
        hinweis.className = 'lmt-kalender-hinweis ' + (klasse || 'dezent');
    }

    // Belegung je Zelle: {typ, text, start, extra} – Vorschlag schlägt alles
    function belegungen(spalte, tag) {
        const liste = [];
        (spalte.termine || []).forEach(function (t) {
            if (datumVon(t.beginn) !== tag) { return; }
            liste.push({ art: t.typ === 'sperrzeit' ? 'sperrzeit' : 'termin', von: minuten(t.beginn),
                         bis: t.ende ? Math.max(minuten(t.ende), minuten(t.beginn) + 15) : minuten(t.beginn) + 90,
                         text: t.text, typ: t.typ, status: t.status, eigener: t.eigener,
                         titel: (t.typ_name || t.typ) + ' ' + t.beginn.slice(11, 16) + (t.ende ? '–' + t.ende.slice(11, 16) : '') + ' · ' + t.text + (t.status === 'vorgemerkt' ? ' (vorgemerkt)' : '') });
        });
        (spalte.belegt || []).forEach(function (b) {
            if (datumVon(b.beginn) !== tag && datumVon(b.ende) !== tag) { return; }
            const von = datumVon(b.beginn) === tag ? minuten(b.beginn) : 0;
            const bis = datumVon(b.ende) === tag ? minuten(b.ende) : 24 * 60;
            liste.push({ art: 'belegt', von: von, bis: bis, text: 'Outlook', titel: 'Outlook belegt ' + b.beginn.slice(11, 16) + '–' + b.ende.slice(11, 16) });
        });
        return liste;
    }

    function bauen(d) {
        tabelle.textContent = '';
        const spalten = d.spalten || [];
        const tage = d.tage || [];
        if (!spalten.length) {
            hinweisSetzen('Kein Vertriebler für die Kalenderansicht – Kandidatenkreis leer. Über „Weitere Kalender“ lassen sich Kalender einblenden.', 'dezent');
            return;
        }
        const raster = d.raster || { von: 480, bis: 1080, schritt: 15 };
        const schritt = raster.schritt || 15;
        const jetzt = jetztIso();
        const thead = document.createElement('thead');
        const zeile1 = document.createElement('tr');
        const ecke = document.createElement('th'); ecke.className = 'lmt-k-zeit'; ecke.textContent = d.woche_text || '';
        zeile1.appendChild(ecke);
        tage.forEach(function (tag) {
            const th = document.createElement('th'); th.className = 'lmt-k-tag'; th.colSpan = spalten.length; th.textContent = tag.label;
            zeile1.appendChild(th);
        });
        thead.appendChild(zeile1);
        const zeile2 = document.createElement('tr');
        const ecke2 = document.createElement('th'); ecke2.className = 'lmt-k-zeit'; zeile2.appendChild(ecke2);
        tage.forEach(function () {
            spalten.forEach(function (sp, i) {
                const th = document.createElement('th');
                th.className = 'lmt-k-ad' + (sp.kandidat ? '' : ' lmt-k-ausserhalb') + (i === spalten.length - 1 ? ' lmt-k-tag' : '');
                th.textContent = sp.name.split(' ').slice(-1)[0];
                th.title = sp.name + (sp.kandidat ? ' (Kandidat)' : ' – außerhalb der Vorauswahl: ' + (sp.grund || '')) + (sp.hv ? ' · Handelsvertreter (nur Tool-Termine, Sperrzeiten)' : '') + (sp.outlook ? ' · Outlook belegt eingeblendet' : '');
                if (!sp.kandidat) { const s = document.createElement('small'); s.textContent = 'außerhalb der Vorauswahl'; th.appendChild(s); }
                zeile2.appendChild(th);
            });
        });
        thead.appendChild(zeile2);
        tabelle.appendChild(thead);
        const tbody = document.createElement('tbody');
        const vorschlaege = d.vorschlaege || [];
        const belegtCache = {};
        tage.forEach(function (tag) {
            spalten.forEach(function (sp) { belegtCache[tag.datum + '|' + sp.ad_id] = belegungen(sp, tag.datum); });
        });
        for (let m = raster.von; m < raster.bis; m += schritt) {
            const tr = document.createElement('tr');
            const tz = document.createElement('td'); tz.className = 'lmt-k-zeit';
            if (m % 60 === 0) { tz.textContent = pad(Math.floor(m / 60)) + ':00'; }
            tr.appendChild(tz);
            tage.forEach(function (tag) {
                spalten.forEach(function (sp, i) {
                    const td = document.createElement('td');
                    const zeiten = (sp.arbeitszeiten || {})[tag.datum];
                    const iso = tag.datum + 'T' + pad(Math.floor(m / 60)) + ':' + pad(m % 60);
                    const klassen = [];
                    if ((m + schritt) % 60 === 0) { klassen.push('lmt-k-stunde'); }
                    if (i === spalten.length - 1) { klassen.push('lmt-k-tagende'); }
                    let belegt = null;
                    belegtCache[tag.datum + '|' + sp.ad_id].forEach(function (b) {
                        if (m >= b.von && m < b.bis && (!belegt || b.art !== 'belegt')) { belegt = b; }
                    });
                    const vorschlag = vorschlaege.find(function (v) {
                        return v.ad_id === sp.ad_id && datumVon(v.beginn) === tag.datum && m >= minuten(v.beginn)
                            && m < (v.ende ? minuten(v.ende) : minuten(v.beginn) + 90);
                    });
                    if (vorschlag) {
                        klassen.push('lmt-k-vorschlag');
                        if (vorschlag.ideal) { klassen.push('lmt-k-ideal'); }
                        if (m === minuten(vorschlag.beginn)) {
                            klassen.push('lmt-k-start');
                            const text = document.createElement('span'); text.className = 'lmt-k-text';
                            const nr = document.createElement('span'); nr.className = 'lmt-k-nr'; nr.textContent = vorschlag.nr;
                            text.appendChild(nr); text.appendChild(document.createTextNode(vorschlag.ideal ? 'Ideal' : 'Vorschlag'));
                            td.appendChild(text);
                        }
                        td.title = 'Vorschlag ' + vorschlag.nr + (vorschlag.ideal ? ' (Ideal)' : '') + ' · ' + vorschlag.beginn.slice(11, 16) + ' · ' + sp.name + ' – Klick übernimmt den Slot ins Formular';
                        td.dataset.ad = sp.ad_id; td.dataset.beginn = vorschlag.beginn; td.dataset.ausserhalb = sp.kandidat ? '' : '1';
                    } else if (belegt) {
                        klassen.push(belegt.art === 'termin' ? 'lmt-k-termin lmt-k-typ-' + (belegt.typ || 'vot') : (belegt.art === 'sperrzeit' ? 'lmt-k-sperrzeit' : 'lmt-k-belegt'));
                        if (belegt.status === 'vorgemerkt') { klassen.push('lmt-k-vorgemerkt'); }
                        if (belegt.eigener) { klassen.push('lmt-k-eigener'); }
                        if (m === belegt.von || (m === raster.von && belegt.von < raster.von)) {
                            klassen.push('lmt-k-start');
                            const text = document.createElement('span'); text.className = 'lmt-k-text'; text.textContent = belegt.text;
                            td.appendChild(text);
                        }
                        td.title = belegt.titel;
                    } else if (!zeiten || m < zeiten[0] || m + schritt > zeiten[1]) {
                        klassen.push('lmt-k-aus');
                        td.title = sp.name + ': außerhalb der Arbeitszeit';
                    } else if (iso < jetzt) {
                        klassen.push('lmt-k-vergangen');
                        td.title = 'vergangen';
                    } else {
                        klassen.push('lmt-k-frei');
                        td.title = tag.label + ' ' + iso.slice(11, 16) + ' · ' + sp.name + (sp.kandidat ? '' : ' (außerhalb der Vorauswahl)') + ' – Klick = manuell buchen';
                        td.dataset.ad = sp.ad_id; td.dataset.beginn = iso; td.dataset.ausserhalb = sp.kandidat ? '' : '1';
                    }
                    td.className = klassen.join(' ');
                    tr.appendChild(td);
                });
            });
            tbody.appendChild(tr);
        }
        tabelle.appendChild(tbody);
        const texte = [];
        if (d.aus_cache) { texte.push('Stand ' + (d.berechnet_um || '') + ' (zwischengespeichert, „Neu laden“ erzwingt)'); }
        if (!d.sync) { texte.push('Outlook-Belegt nur bei kalender_sync = an – angezeigt werden Tool-Termine und Sperrzeiten.'); }
        (d.hinweise || []).forEach(function (h) { texte.push(h); });
        hinweisSetzen(texte.join(' · '), 'dezent');
    }

    async function laden(neu) {
        hinweisSetzen('Kalender wird geladen …', 'dezent');
        const params = new URLSearchParams();
        if (woche) { params.set('woche', woche); }
        if (neu) { params.set('neu', '1'); }
        const meinLauf = {};
        laufend = meinLauf;
        let d;
        try {
            const antwort = await fetch(wurzel.dataset.url + (params.toString() ? '?' + params.toString() : ''),
                { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
            if (!antwort.ok) { throw new Error(String(antwort.status)); }
            d = await antwort.json();
        } catch (e) {
            hinweisSetzen('Kalender derzeit nicht verfügbar.', 'lm-warn');
            return;
        }
        if (laufend !== meinLauf) { return; }
        daten = d;
        woche = d.woche || woche;
        if (wocheText) { wocheText.textContent = d.woche_text || ''; }
        bauen(d);
    }

    wurzel.querySelectorAll('[data-woche]').forEach(function (knopf) {
        knopf.addEventListener('click', function () {
            if (!daten) { return; }
            const art = knopf.dataset.woche;
            if (art === 'vor') { woche = daten.vorherige; }
            else if (art === 'nach') { woche = daten.naechste; }
            else { woche = ''; }
            laden(false);
        });
    });
    wurzel.querySelectorAll('[data-kalender-neu]').forEach(function (knopf) {
        knopf.addEventListener('click', function () { laden(true); });
    });

    // Klick auf freien Slot / Vorschlags-Slot → Formular „Manuell setzen“
    tabelle.addEventListener('click', function (e) {
        const td = e.target.closest('td[data-beginn]');
        if (!td || !form) { return; }
        const beginn = td.dataset.beginn;
        const datum = form.querySelector('input[name=datum]');
        const uhrzeit = form.querySelector('input[name=uhrzeit]');
        if (datum) { datum.value = beginn.slice(0, 10); }
        if (uhrzeit) { uhrzeit.value = beginn.slice(11, 16); }
        if (adWahl) {
            adWahl.value = td.dataset.ad;
            if (adWahl.value !== td.dataset.ad && weitereOptgroup) {
                // Kalender außerhalb der Vorauswahl: Option ergänzen
                const sp = (daten.spalten || []).find(function (s) { return String(s.ad_id) === String(td.dataset.ad); });
                const o = document.createElement('option'); o.value = td.dataset.ad; o.dataset.ausserhalb = '1';
                o.textContent = sp ? sp.name : td.dataset.ad; weitereOptgroup.appendChild(o); weitereOptgroup.hidden = false;
                adWahl.value = td.dataset.ad;
            }
            adWahl.dispatchEvent(new Event('change'));
        }
        if (uhrzeit) { uhrzeit.dispatchEvent(new Event('change')); }
        const ziel = document.getElementById('manuell');
        if (ziel) { ziel.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    });

    // Warnhinweis „außerhalb der Vorauswahl“ je nach gewähltem Vertriebler
    function warnungPruefen() {
        if (!warnung || !adWahl) { return; }
        const o = adWahl.selectedOptions[0];
        warnung.hidden = !(o && o.dataset.ausserhalb === '1');
    }
    if (adWahl) { adWahl.addEventListener('change', warnungPruefen); warnungPruefen(); }

    // „Weitere Kalender“: Auswahl je Nutzer speichern, Spalten und Formular nachziehen
    const weitere = document.getElementById('lmt-weitere');
    if (weitere) {
        weitere.addEventListener('change', async function (e) {
            const box = e.target.closest('input[type=checkbox][name=weitere]');
            if (!box) { return; }
            const ids = Array.from(weitere.querySelectorAll('input[type=checkbox][name=weitere]:checked')).map(function (b) { return b.value; });
            try {
                const r = await fetch(wurzel.dataset.auswahlUrl, {
                    method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                    body: JSON.stringify({ ids: ids }), credentials: 'same-origin' });
                const j = await r.json();
                if (!j.ok) { hinweisSetzen(j.meldung || 'Auswahl nicht gespeichert.', 'lm-warn'); return; }
            } catch (x) {
                hinweisSetzen('Auswahl nicht gespeichert (Verbindung).', 'lm-warn');
                return;
            }
            const summary = weitere.querySelector('summary');
            if (summary) { summary.textContent = 'Weitere Kalender' + (ids.length ? ' (' + ids.length + ')' : ''); }
            weitere.classList.toggle('aktiv', ids.length > 0);
            if (weitereOptgroup) {
                weitereOptgroup.textContent = '';
                weitere.querySelectorAll('input[type=checkbox][name=weitere]:checked').forEach(function (b) {
                    const o = document.createElement('option'); o.value = b.value; o.dataset.ausserhalb = '1'; o.textContent = b.dataset.name || b.value;
                    weitereOptgroup.appendChild(o);
                });
                weitereOptgroup.hidden = ids.length === 0;
            }
            laden(false);
        });
        document.addEventListener('click', function (e) { if (weitere.open && !weitere.contains(e.target)) { weitere.removeAttribute('open'); } });
    }

    setTimeout(function () { laden(false); }, 80);   // nachgelagert – die Seite rendert ohne Graph
})();
