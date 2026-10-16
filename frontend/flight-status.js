/* Flight status page: flight number search and upcoming departures board. */
(function () {
  "use strict";

  const site = window.KQSite;
  const form = document.getElementById("status-form");
  const input = document.getElementById("status-input");
  const message = document.getElementById("status-message");
  const results = document.getElementById("status-results");

  function flightRow(flight) {
    const item = document.createElement("li");
    item.className = "flight-row";
    const number = document.createElement("span");
    number.className = "flight-row__number";
    number.textContent = flight.flight_number;
    const details = document.createElement("span");
    const route = document.createElement("span");
    route.className = "flight-row__route";
    route.textContent = `${flight.origin} → ${flight.destination}`;
    const time = document.createElement("span");
    time.className = "flight-row__time";
    time.textContent = ` · ${site.formatDateTime(flight.departure_time)} – ${site.formatArrival(flight.departure_time, flight.arrival_time)}`;
    details.append(route, time);
    item.append(number, details, site.statusBadge(flight.status));
    return item;
  }

  async function search(value) {
    results.replaceChildren();
    if (!/^[A-Za-z]{2}\s?\d{2,4}$/.test(value)) {
      input.setAttribute("aria-invalid", "true");
      message.textContent = "Enter a flight number like KQ101.";
      input.focus();
      return;
    }
    input.removeAttribute("aria-invalid");
    message.textContent = "Searching…";
    try {
      const flights = await window.KQApi.flightStatus(value);
      flights.forEach((flight) => results.append(flightRow(flight)));
      message.textContent = `${flights.length} upcoming departure${flights.length === 1 ? "" : "s"} for ${flights[0].flight_number}.`;
    } catch (error) {
      message.textContent = error.message;
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    search(input.value.trim());
  });

  // Searches started from the home page arrive as ?flight=KQ101
  const fromHome = new URLSearchParams(window.location.search).get("flight");
  if (fromHome) {
    input.value = fromHome.slice(0, 8);
    search(input.value.trim());
  }

  async function loadBoard() {
    const rows = document.getElementById("board-rows");
    const updated = document.getElementById("board-updated");
    try {
      const flights = await window.KQApi.request("/api/flights/departures", { query: { limit: 12 } });
      rows.replaceChildren(...flights.map((f) => {
        const tr = document.createElement("tr");
        const cells = [f.flight_number, `${f.origin} → ${f.destination}`, site.formatDateTime(f.departure_time), site.formatArrival(f.departure_time, f.arrival_time)];
        cells.forEach((text) => {
          const td = document.createElement("td");
          td.textContent = text;
          tr.append(td);
        });
        const status = document.createElement("td");
        status.append(site.statusBadge(f.status));
        tr.append(status);
        return tr;
      }));
      updated.textContent = `Next ${flights.length} departures · updated ${site.formatTime(new Date())}`;
    } catch (error) {
      updated.textContent = error.message;
    }
  }
  loadBoard();
})();
