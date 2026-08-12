/**
 * Filantropia public stations Leaflet map.
 * Expects window.FS_STATIONS (array) and #fs-stations-map.
 */
(function () {
    function esc(t) {
        return String(t == null ? "" : t)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function absUrl(raw) {
        var w = String(raw || "").trim();
        if (!w) {
            return "";
        }
        if (!/^https?:\/\//i.test(w)) {
            w = "https://" + w;
        }
        return w;
    }

    function init() {
        if (typeof L === "undefined") {
            return;
        }
        var mapEl = document.getElementById("fs-stations-map");
        if (!mapEl) {
            return;
        }
        var stations = window.FS_STATIONS || [];
        var map = L.map("fs-stations-map");
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 18,
            attribution: "&copy; OpenStreetMap contributors",
        }).addTo(map);

        var markers = [];
        stations.forEach(function (s) {
            var lat = parseFloat(s.latitude);
            var lng = parseFloat(s.longitude);
            if (!isFinite(lat) || !isFinite(lng)) {
                return;
            }
            var m = L.marker([lat, lng]).addTo(map);
            var saved =
                s.money_saved_display != null && s.money_saved_display !== ""
                    ? s.money_saved_display
                    : s.money_saved_eur != null
                      ? Math.round(Number(s.money_saved_eur))
                      : "\u2014";
            var info = s.info || s.description || s.short_description || "";
            var html =
                "<strong>" +
                esc(s.name || "Station") +
                "</strong><br/>" +
                esc(s.location || "") +
                "<br/>" +
                esc(s.capacity_kwp || 0) +
                " kWp<br/>" +
                "<strong>Poupan\u00e7a estimada:</strong> " +
                esc(saved) +
                " EUR/ano";
            if (s.savings_is_indicative) {
                html += " <em>(indicativa)</em>";
            }
            if (info) {
                html += "<br/><strong>Descri\u00e7\u00e3o:</strong> " + esc(info);
            }
            var w = absUrl(s.website_href || s.website);
            if (w) {
                html +=
                    '<br/><a href="' +
                    esc(w) +
                    '" target="_blank" rel="noopener">Website</a>';
            }
            m.bindPopup(html);
            markers.push(m);
        });
        if (markers.length) {
            map.fitBounds(L.featureGroup(markers).getBounds().pad(0.15));
        } else {
            map.setView([38.7223, -9.1393], 5);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
