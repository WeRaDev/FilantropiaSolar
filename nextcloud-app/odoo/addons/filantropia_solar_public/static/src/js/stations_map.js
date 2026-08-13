/**
 * Filantropia public stations Leaflet map.
 * Expects window.FS_STATIONS (array) and #fs-stations-map.
 * Optional: .fs-station-list-item[data-station-id|data-lat|data-lng] for list→map focus.
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

    function stationKey(s) {
        if (!s) {
            return "";
        }
        return String(
            s.id ||
                s.installation_id ||
                s.installationId ||
                ((s.latitude != null ? s.latitude : "") +
                    "," +
                    (s.longitude != null ? s.longitude : ""))
        );
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
        var byId = {};
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
            var cat = String(s.public_category || s.lifecycle_state || "").toLowerCase();
            var statusLabel =
                cat === "planned"
                    ? "Planeada"
                    : cat === "existing" || cat === "running"
                      ? "Em opera\u00e7\u00e3o"
                      : cat || "";
            var html =
                "<strong>" +
                esc(s.name || "Station") +
                "</strong>";
            if (statusLabel) {
                html +=
                    " <span class=\"fs-status-badge fs-status-" +
                    (cat === "planned"
                        ? "planned"
                        : cat === "existing" || cat === "running"
                          ? "running"
                          : "other") +
                    "\">" +
                    esc(statusLabel) +
                    "</span>";
            }
            html +=
                "<br/>" +
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
            var key = stationKey(s);
            if (key) {
                byId[key] = { marker: m, lat: lat, lng: lng };
            }
            // also index by lat,lng string
            byId[String(lat) + "," + String(lng)] = { marker: m, lat: lat, lng: lng };
        });
        if (markers.length) {
            map.fitBounds(L.featureGroup(markers).getBounds().pad(0.15));
        } else {
            map.setView([38.7223, -9.1393], 5);
        }

        function focusStation(el) {
            if (!el) {
                return;
            }
            var id = el.getAttribute("data-station-id") || "";
            var lat = parseFloat(el.getAttribute("data-lat"));
            var lng = parseFloat(el.getAttribute("data-lng"));
            var entry = null;
            if (id && byId[id]) {
                entry = byId[id];
            } else if (isFinite(lat) && isFinite(lng) && byId[String(lat) + "," + String(lng)]) {
                entry = byId[String(lat) + "," + String(lng)];
            } else if (isFinite(lat) && isFinite(lng)) {
                entry = { marker: null, lat: lat, lng: lng };
            }
            if (!entry) {
                return;
            }
            map.setView([entry.lat, entry.lng], Math.max(map.getZoom(), 12), {
                animate: true,
            });
            if (entry.marker) {
                entry.marker.openPopup();
            }
            document.querySelectorAll(".fs-station-list-item.is-active").forEach(function (n) {
                n.classList.remove("is-active");
            });
            el.classList.add("is-active");
        }

        document.querySelectorAll(".fs-station-list-item").forEach(function (el) {
            el.style.cursor = "pointer";
            el.setAttribute("role", "button");
            el.setAttribute("tabindex", "0");
            el.addEventListener("click", function (ev) {
                // allow real links inside the row
                if (ev.target && ev.target.closest && ev.target.closest("a")) {
                    return;
                }
                focusStation(el);
            });
            el.addEventListener("keydown", function (ev) {
                if (ev.key === "Enter" || ev.key === " ") {
                    ev.preventDefault();
                    focusStation(el);
                }
            });
        });

        window.FS_MAP = map;
        window.FS_FOCUS_STATION = focusStation;
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
