/* Home page: flight status search and "ask the assistant" shortcuts. */
(function () {
  "use strict";

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
    time.textContent = ` · ${window.KQSite.formatDateTime(flight.departure_time)} – ${window.KQSite.formatTime(flight.arrival_time)}`;
    details.append(route, time);

    item.append(number, details, window.KQSite.statusBadge(flight.status));
    return item;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const value = input.value.trim();
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
  });

  document.querySelectorAll("[data-ask]").forEach((button) => {
    button.addEventListener("click", () => window.KQChat.open(button.dataset.ask, button.dataset.label));
  });
  document.getElementById("hero-chat").addEventListener("click", () => window.KQChat.open());

  window.KQSite.ready.then((user) => {
    const manage = document.getElementById("hero-manage");
    if (user && user.role === "admin") {
      manage.href = "admin.html";
      manage.textContent = "Open staff dashboard";
    } else if (!user) {
      manage.href = "login.html?next=account.html";
    }
  });
})();
