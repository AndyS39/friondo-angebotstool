// Lead-Management V2 (v23, Phase 108): Terminassistent – Mini-Karte je
// Vorschlag (Leaflet lokal, OSM-Kacheln wie karte.html), Live-Konfliktprüfung
// des manuellen Formulars (GET /lead-management/termin/konflikt) und
// 15-Minuten-Rundung der Uhrzeit. Vanilla JS, kein Framework.
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
