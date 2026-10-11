// v30 (PLAN_V18 Phase 147): Zurueck-Navigation "eine Ansicht zurueck" und
// (Phase 145) Umschalter der Darstellung. Eingebunden in base.html auf allen Seiten.
//
// Verlauf je Browser-Tab in sessionStorage ("friondo_verlauf", hoechstens 30
// Eintraege): bei jedem Seitenaufbau wird der aktuelle Pfad (mit Query, ohne #)
// angehaengt - nicht, wenn er dem obersten Eintrag entspricht (Neuladen, Umleitung
// nach einem Speichern). Klick auf "Zurueck" nimmt den obersten ANDEREN Eintrag,
// entfernt ihn (und die Eintraege der aktuellen Seite darueber) und navigiert
// dorthin: einmal Zurueck = eine Ansicht, zweimal = zwei Ansichten, nie Schleifen.
// Leerer Verlauf (Direktaufruf, neuer Tab) -> Standard-Ruecksprungseite der Route
// (Attribut data-zurueck-standard am Knopf). Kein Browser-Zurueck, kein Tastenkuerzel.
(function () {
    "use strict";
    var SCHLUESSEL = "friondo_verlauf";
    var MAXIMUM = 30;
    var aktuell = window.location.pathname + window.location.search;

    function verlaufLesen() {
        try {
            var roh = window.sessionStorage.getItem(SCHLUESSEL);
            var liste = roh ? JSON.parse(roh) : [];
            return Array.isArray(liste) ? liste : [];
        } catch (e) {
            return [];
        }
    }

    function verlaufSchreiben(liste) {
        try {
            if (liste.length > MAXIMUM) {
                liste = liste.slice(liste.length - MAXIMUM);
            }
            window.sessionStorage.setItem(SCHLUESSEL, JSON.stringify(liste));
        } catch (e) {
            // sessionStorage gesperrt (privater Modus) - dann nur die Standardseite
        }
    }

    function seiteMerken() {
        var liste = verlaufLesen();
        if (liste.length === 0 || liste[liste.length - 1] !== aktuell) {
            liste.push(aktuell);
            verlaufSchreiben(liste);
        }
    }

    // Liefert das Ziel fuer "Zurueck" und kuerzt den Verlauf entsprechend;
    // null = kein anderer Eintrag vorhanden.
    function zurueckZiel() {
        var liste = verlaufLesen();
        var i = liste.length - 1;
        while (i >= 0 && liste[i] === aktuell) {
            i -= 1;
        }
        if (i < 0) {
            verlaufSchreiben([]);
            return null;
        }
        var ziel = liste[i];
        verlaufSchreiben(liste.slice(0, i));
        return ziel;
    }

    function zurueckKnopf() {
        var knopf = document.querySelector("[data-zurueck-standard]");
        if (!knopf) {
            return;
        }
        knopf.addEventListener("click", function (ereignis) {
            ereignis.preventDefault();
            var ziel = zurueckZiel() || knopf.getAttribute("data-zurueck-standard") || "/";
            window.location.assign(ziel);
        });
    }

    // Phase 145: Darstellung - Radio-Chips "Geraet / Hell / Dunkel" im Menue.
    // (a) sofort auf <html data-theme>, (b) POST /einstellungen/darstellung (JSON),
    // (c) Cookie setzt der Server in der Antwort.
    function darstellungUmschalter() {
        var felder = document.querySelectorAll("input[name='darstellung'][data-darstellung]");
        if (!felder.length) {
            return;
        }
        var meta = document.querySelector("meta[name='theme-color'][data-theme-color]");
        Array.prototype.forEach.call(felder, function (feld) {
            feld.addEventListener("change", function () {
                var wert = feld.value;
                var wurzel = document.documentElement;
                if (wert === "hell" || wert === "dunkel") {
                    wurzel.setAttribute("data-theme", wert);
                } else {
                    wurzel.removeAttribute("data-theme");
                }
                Array.prototype.forEach.call(felder, function (anderes) {
                    var chip = anderes.closest(".darstellung-chip");
                    if (chip) {
                        chip.classList.toggle("aktiv", anderes === feld);
                    }
                });
                if (meta) {
                    var dunkel = wert === "dunkel" || (wert === "geraet" && window.matchMedia
                        && window.matchMedia("(prefers-color-scheme: dark)").matches);
                    meta.removeAttribute("media");
                    meta.setAttribute("content", dunkel ? meta.getAttribute("data-dunkel")
                                                        : meta.getAttribute("data-hell"));
                    var zweite = document.querySelector("meta[data-theme-color-dunkel]");
                    if (zweite) {
                        zweite.parentNode.removeChild(zweite);
                    }
                }
                try {
                    window.fetch("/einstellungen/darstellung", {
                        method: "POST",
                        headers: {"Content-Type": "application/json", "Accept": "application/json"},
                        body: JSON.stringify({wert: wert}),
                        credentials: "same-origin"
                    });
                } catch (e) {
                    // ohne fetch bleibt die Wahl nur fuer diese Seite
                }
            });
        });
    }

    seiteMerken();
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            zurueckKnopf();
            darstellungUmschalter();
        });
    } else {
        zurueckKnopf();
        darstellungUmschalter();
    }
}());
