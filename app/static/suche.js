// v32 (PLAN_V19 Phase 164): Kundensuche in der Kopfzeile (base.html).
// Vorschläge beim Tippen (Debounce 200 ms, ab zwei Zeichen, höchstens acht
// Treffer aus /suche.json), Pfeiltasten + Enter öffnen den markierten Treffer,
// Escape schließt; Enter ohne Auswahl schickt das Formular an /suche?q= (Trefferseite).
// Unter 600 px klappt das Lupen-Symbol das Feld in voller Breite aus (CSS .offen).
// Die Treffer werden ausschließlich über DOM-Methoden aufgebaut (kein innerHTML
// mit Daten) – Kundennamen landen nie als HTML im Dokument.
(function () {
    "use strict";
    var form = document.querySelector("form.kopf-suche");
    if (!form) {
        return;
    }
    var feld = form.querySelector("input[type=search]");
    var liste = form.querySelector(".kopf-suche-liste");
    var lupe = form.querySelector(".kopf-suche-lupe");
    var jsonPfad = form.getAttribute("data-suche-json") || "/suche.json";
    var timer = null;
    var laufendeNr = 0;
    var treffer = [];
    var aktiv = -1;

    function schliessen() {
        liste.hidden = true;
        while (liste.firstChild) {
            liste.removeChild(liste.firstChild);
        }
        treffer = [];
        aktiv = -1;
        feld.setAttribute("aria-expanded", "false");
    }

    function element(tag, klasse, text) {
        var e = document.createElement(tag);
        if (klasse) {
            e.className = klasse;
        }
        if (text) {
            e.textContent = text;
        }
        return e;
    }

    function markieren(index) {
        var eintraege = liste.querySelectorAll(".kopf-suche-treffer");
        if (!eintraege.length) {
            return;
        }
        if (index < 0) {
            index = eintraege.length - 1;
        }
        if (index >= eintraege.length) {
            index = 0;
        }
        for (var i = 0; i < eintraege.length; i++) {
            eintraege[i].classList.toggle("aktiv", i === index);
            eintraege[i].setAttribute("aria-selected", i === index ? "true" : "false");
        }
        aktiv = index;
    }

    function zeigen(daten) {
        schliessen();
        treffer = daten.treffer || [];
        if (!treffer.length) {
            liste.appendChild(element("div", "kopf-suche-leer", "Keine Treffer"));
            liste.hidden = false;
            return;
        }
        for (var i = 0; i < treffer.length; i++) {
            var t = treffer[i];
            var a = element("a", "kopf-suche-treffer");
            a.href = t.link;
            a.setAttribute("role", "option");
            a.setAttribute("data-index", String(i));
            a.setAttribute("aria-label", t.name + (t.ort ? ", " + t.ort : ""));
            var zeile1 = element("span", "kopf-suche-name", t.name);
            if (t.sparten && t.sparten.length) {
                for (var s = 0; s < t.sparten.length; s++) {
                    zeile1.appendChild(element("span", "abzeichen interesse-" + String(t.sparten[s]).toLowerCase(), t.sparten[s]));
                }
            }
            a.appendChild(zeile1);
            var zeile2 = element("span", "kopf-suche-ort", [t.plz, t.ort].join(" ").trim());
            if (t.verfolgung_text) {
                zeile2.appendChild(element("span", "kopf-suche-chip", t.verfolgung_text));
            }
            a.appendChild(zeile2);
            liste.appendChild(a);
        }
        if (daten.mehr) {
            var mehr = element("a", "kopf-suche-mehr", "Alle Treffer anzeigen …");
            mehr.href = daten.mehr;
            liste.appendChild(mehr);
        }
        liste.hidden = false;
        feld.setAttribute("aria-expanded", "true");
    }

    function laden() {
        var q = feld.value.trim();
        if (q.length < 2) {
            schliessen();
            return;
        }
        var nr = ++laufendeNr;
        fetch(jsonPfad + "?q=" + encodeURIComponent(q), {
            headers: { "Accept": "application/json" },
            credentials: "same-origin"
        }).then(function (antwort) {
            return antwort.ok ? antwort.json() : null;
        }).then(function (daten) {
            if (nr !== laufendeNr || !daten || feld.value.trim() !== q) {
                return;
            }
            zeigen(daten);
        }).catch(function () {
            schliessen();
        });
    }

    feld.addEventListener("input", function () {
        clearTimeout(timer);
        timer = setTimeout(laden, 200);
    });
    feld.addEventListener("focus", function () {
        if (feld.value.trim().length >= 2 && liste.hidden) {
            laden();
        }
    });
    feld.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            schliessen();
            return;
        }
        if (liste.hidden) {
            return;
        }
        if (e.key === "ArrowDown") {
            e.preventDefault();
            markieren(aktiv + 1);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            markieren(aktiv - 1);
        } else if (e.key === "Enter") {
            if (aktiv >= 0 && treffer[aktiv]) {
                e.preventDefault();
                window.location.href = treffer[aktiv].link;
            }
        }
    });
    liste.addEventListener("mousemove", function (e) {
        var ziel = e.target.closest ? e.target.closest(".kopf-suche-treffer") : null;
        if (ziel) {
            markieren(parseInt(ziel.getAttribute("data-index"), 10));
        }
    });
    document.addEventListener("click", function (e) {
        if (!form.contains(e.target)) {
            schliessen();
        }
    });
    form.addEventListener("submit", function (e) {
        if (feld.value.trim().length < 2) {
            e.preventDefault();
            feld.focus();
        }
    });
    if (lupe) {
        lupe.addEventListener("click", function () {
            form.classList.toggle("offen");
            if (form.classList.contains("offen")) {
                feld.focus();
            } else {
                schliessen();
            }
        });
    }
})();
