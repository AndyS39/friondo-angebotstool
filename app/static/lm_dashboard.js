/* Lead-Management v31 (PLAN_LEAD_V5 Phasen 154/158) – „Mein Dashboard“.
   1. Kacheln verschieben: Stift (#lm-dash-stift) → Bearbeitungsmodus (body.lm-dash-bearbeiten):
      jede Karte des Rasters (#lm-dash-raster > .lm-karte[data-kachel]) bekommt einen Griff und
      ist per HTML5 Drag & Drop verschiebbar – Platzhalter (.lm-kachel-platzhalter) zeigt die
      Zielposition, Loslassen rastet ein (keine Größenänderung). Haken (#lm-dash-haken) speichert
      die Reihenfolge je Nutzer (POST data-url, JSON {keys}), Escape/Abbrechen stellt die
      Ausgangsreihenfolge wieder her, „Zurücksetzen“ sendet {zuruecksetzen:true}. Alle Daten
      kommen aus data-Attributen (kein tojson in on*-Attributen, v30-Regel).
   2. „Fällig heute“: Erledigt per fetch (Accept: application/json) – die Zeile bleibt stehen,
      durchgestrichen, mit „Rückgängig“ (POST aktion=rueckgaengig + alter Zeitpunkt aus der
      Antwort); ohne JavaScript läuft das Formular wie bisher mit Neuladen.
   3. Sicherheitsabfragen über data-bestaetigen an Formularen (statt onsubmit-Attributen). */
(function () {
    'use strict';
    if (window.__lmDashboardGeladen) { return; }
    window.__lmDashboardGeladen = true;

    const raster = document.getElementById('lm-dash-raster');
    const werkzeuge = document.getElementById('lm-dash-werkzeuge');
    const meldungEl = document.getElementById('lm-dash-meldung');
    function melden(text, fehler) {
        if (!meldungEl) { return; }
        meldungEl.textContent = text || '';
        meldungEl.classList.toggle('fehler', !!fehler);
        meldungEl.hidden = !text;
    }

    // ---------- 3. Sicherheitsabfragen (data-bestaetigen) ----------
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!(form instanceof HTMLFormElement)) { return; }
        if (form.dataset.gesperrt) { e.preventDefault(); melden(form.dataset.gesperrt, true); return; }
        if (form.dataset.bestaetigen && form.dataset.bestaetigt !== '1' && !window.confirm(form.dataset.bestaetigen)) {
            e.preventDefault();
        }
    }, true);

    // ---------- 2. Erledigt per fetch + Rückgängig ----------
    async function erledigtSenden(form) {
        const zeile = form.closest('tr');
        const leiste = form.closest('.lm-wv-aktion-leiste');
        const daten = new URLSearchParams(new FormData(form));
        let antwort = null;
        try {
            const r = await fetch(form.action, {
                method: 'POST',
                headers: { 'Accept': 'application/json' },
                body: daten
            });
            antwort = await r.json();
        } catch (x) {
            return false;   // Rückfall: normales Absenden
        }
        if (!antwort || !antwort.ok) { melden((antwort && antwort.meldung) || 'Erledigt fehlgeschlagen.', true); return true; }
        melden(antwort.meldung, false);
        if (zeile) { zeile.classList.add('erledigt'); }
        if (leiste) {
            leiste.innerHTML = '';
            const text = document.createElement('span');
            text.className = 'lm-wv-erledigt-text';
            text.textContent = 'Erledigt ✓';
            leiste.appendChild(text);
            if (antwort.rueckgaengig) {
                const knopf = document.createElement('button');
                knopf.type = 'button';
                knopf.className = 'lm-wv-rueckgaengig';
                knopf.textContent = 'Rückgängig';
                knopf.title = 'Wiedervorlage wiederherstellen';
                knopf.addEventListener('click', function () { rueckgaengig(form.action, antwort.rueckgaengig, zeile, leiste, form); });
                leiste.appendChild(document.createTextNode(' · '));
                leiste.appendChild(knopf);
            }
        }
        const kachel = document.querySelector('.lm-dash-kacheln .stat-zahl.dringend');
        if (kachel && /^\d+$/.test(kachel.textContent.trim())) {
            kachel.textContent = String(Math.max(0, parseInt(kachel.textContent, 10) - 1));
        }
        return true;
    }
    async function rueckgaengig(url, info, zeile, leiste, form) {
        const daten = new URLSearchParams();
        daten.set('art', info.art || 'lead');
        daten.set('aktion', 'rueckgaengig');
        daten.set('datum', info.datum || '');
        daten.set('quelle', info.quelle || '');
        let antwort = null;
        try {
            const r = await fetch(url, { method: 'POST', headers: { 'Accept': 'application/json' }, body: daten });
            antwort = await r.json();
        } catch (x) { melden('Rückgängig fehlgeschlagen (Verbindung).', true); return; }
        if (!antwort || !antwort.ok) { melden((antwort && antwort.meldung) || 'Rückgängig fehlgeschlagen.', true); return; }
        melden(antwort.meldung, false);
        // Zeile wiederherstellen: Seite neu laden zeigt den Originalzustand (Chip, Menü)
        window.location.reload();
    }
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!(form instanceof HTMLFormElement) || !form.classList.contains('lm-wv-erledigt-form')) { return; }
        if (form.dataset.bestaetigen && !window.confirm(form.dataset.bestaetigen)) { e.preventDefault(); return; }
        e.preventDefault();
        erledigtSenden(form).then(function (ok) { if (!ok) { form.dataset.bestaetigt = '1'; form.submit(); } });
    });

    // ---------- 1. Kacheln verschieben ----------
    if (!raster || !werkzeuge) { return; }
    const url = werkzeuge.dataset.url || '/lead-management/dashboard/kacheln';
    const stift = document.getElementById('lm-dash-stift');
    const haken = document.getElementById('lm-dash-haken');
    const reset = document.getElementById('lm-dash-reset');
    const abbruch = document.getElementById('lm-dash-abbruch');
    const hinweis = document.getElementById('lm-dash-hinweis');
    let bearbeiten = false;
    let ausgang = [];
    let platzhalter = null;
    let gezogen = null;

    function karten() { return Array.from(raster.querySelectorAll(':scope > .lm-karte[data-kachel]')); }
    function reihenfolge() { return karten().map(function (k) { return k.dataset.kachel; }); }
    function anordnen(keys) {
        const vorhanden = {};
        karten().forEach(function (k) { vorhanden[k.dataset.kachel] = k; });
        keys.forEach(function (key) { if (vorhanden[key]) { raster.appendChild(vorhanden[key]); } });
    }
    function modus(an) {
        bearbeiten = an;
        document.body.classList.toggle('lm-dash-bearbeiten', an);
        if (stift) { stift.hidden = an; }
        if (haken) { haken.hidden = !an; }
        if (reset) { reset.hidden = !an; }
        if (abbruch) { abbruch.hidden = !an; }
        if (hinweis) { hinweis.hidden = !an; }
        karten().forEach(function (k) { k.setAttribute('draggable', an ? 'true' : 'false'); });
        if (an) { ausgang = reihenfolge(); }
    }
    async function senden(nutzlast) {
        try {
            const r = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(nutzlast)
            });
            const j = await r.json();
            if (!j.ok) { melden(j.meldung || 'Reihenfolge konnte nicht gespeichert werden.', true); return null; }
            return j;
        } catch (x) {
            melden('Reihenfolge konnte nicht gespeichert werden (Verbindung).', true);
            return null;
        }
    }
    if (stift) { stift.addEventListener('click', function () { modus(true); }); }
    if (abbruch) { abbruch.addEventListener('click', function () { anordnen(ausgang); modus(false); }); }
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && bearbeiten) { anordnen(ausgang); modus(false); }
    });
    if (haken) {
        haken.addEventListener('click', function () {
            senden({ keys: reihenfolge() }).then(function (j) {
                if (!j) { return; }
                melden(j.meldung || 'Reihenfolge gespeichert.', false);
                modus(false);
            });
        });
    }
    if (reset) {
        reset.addEventListener('click', function () {
            if (!window.confirm('Kacheln auf die Standardreihenfolge zurücksetzen? Gilt nur für Sie.')) { return; }
            senden({ zuruecksetzen: true }).then(function (j) {
                if (!j) { return; }
                anordnen(j.keys || []);
                ausgang = reihenfolge();
                melden(j.meldung || 'Kacheln zurückgesetzt.', false);
                modus(false);
            });
        });
    }

    // Drag & Drop: Platzhalter vor/nach der Zielkarte, Einrasten beim Loslassen
    function platzhalterErzeugen() {
        if (!platzhalter) {
            platzhalter = document.createElement('div');
            platzhalter.className = 'lm-kachel-platzhalter';
            platzhalter.setAttribute('aria-hidden', 'true');
        }
        return platzhalter;
    }
    function platzhalterEntfernen() { if (platzhalter && platzhalter.parentNode) { platzhalter.parentNode.removeChild(platzhalter); } }
    raster.addEventListener('dragstart', function (e) {
        if (!bearbeiten) { e.preventDefault(); return; }
        const karte = e.target.closest && e.target.closest('.lm-karte[data-kachel]');
        if (!karte) { return; }
        gezogen = karte;
        karte.classList.add('lm-kachel-zieht');
        const ph = platzhalterErzeugen();
        ph.style.minHeight = Math.max(72, karte.offsetHeight) + 'px';
        try { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', karte.dataset.kachel); } catch (x) { /* egal */ }
    });
    raster.addEventListener('dragover', function (e) {
        if (!bearbeiten || !gezogen) { return; }
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const ziel = e.target.closest && e.target.closest('.lm-karte[data-kachel]');
        const ph = platzhalterErzeugen();
        if (ziel && ziel !== gezogen) {
            const rect = ziel.getBoundingClientRect();
            const danach = (e.clientY - rect.top) > rect.height / 2;
            if (danach) { ziel.after(ph); } else { ziel.before(ph); }
        } else if (!ziel && e.target === raster && !ph.parentNode) {
            raster.appendChild(ph);
        }
    });
    function ablegen() {
        if (!gezogen) { return; }
        if (platzhalter && platzhalter.parentNode) { platzhalter.replaceWith(gezogen); }
        gezogen.classList.remove('lm-kachel-zieht');
        gezogen = null;
        platzhalterEntfernen();
    }
    raster.addEventListener('drop', function (e) { if (!bearbeiten) { return; } e.preventDefault(); ablegen(); });
    raster.addEventListener('dragend', function () { if (gezogen) { gezogen.classList.remove('lm-kachel-zieht'); gezogen = null; } platzhalterEntfernen(); });
    // Tastatur: im Bearbeitungsmodus verschieben Pfeiltasten die fokussierte Karte (Griff)
    raster.addEventListener('keydown', function (e) {
        if (!bearbeiten) { return; }
        const karte = e.target.closest && e.target.closest('.lm-karte[data-kachel]');
        if (!karte) { return; }
        if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
            const vorher = karte.previousElementSibling;
            if (vorher) { e.preventDefault(); vorher.before(karte); karte.querySelector('.lm-kachel-griff').focus(); }
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
            const nachher = karte.nextElementSibling;
            if (nachher) { e.preventDefault(); nachher.after(karte); karte.querySelector('.lm-kachel-griff').focus(); }
        }
    });
})();
