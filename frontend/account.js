/* My bookings page: lists the passenger's bookings with assistant shortcuts. */
(function () {
  "use strict";

  const list = document.getElementById("bookings");
  const empty = document.getElementById("bookings-empty");
  const errorBox = document.getElementById("bookings-error");
  const subtitle = document.getElementById("account-subtitle");
  const template = document.getElementById("booking-template");
  const site = window.KQSite;

  function actionButton(label, message, primary = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `btn btn--small ${primary ? "btn--primary" : "btn--secondary"}`;
    button.textContent = label;
    button.addEventListener("click", () => window.KQChat.open(message, message));
    return button;
  }

  function renderBooking(booking) {
    const card = template.content.firstElementChild.cloneNode(true);
    const flight = booking.flight;
    const ref = booking.booking_ref;
    card.setAttribute("aria-label", `Booking ${ref}, ${flight.origin} to ${flight.destination}`);
    card.querySelector(".booking__ref").textContent = `BOOKING ${ref}`;
    card.querySelector(".booking__status").append(site.statusBadge(booking.status));
    card.querySelector(".from-city").textContent = flight.origin;
    card.querySelector(".from-time").textContent = site.formatDateTime(flight.departure_time);
    card.querySelector(".to-city").textContent = flight.destination;
    card.querySelector(".to-time").textContent = site.formatDateTime(flight.arrival_time);
    card.querySelector(".meta-flight").textContent = `Flight ${flight.flight_number}`;

    const flightStatus = card.querySelector(".meta-flight-status");
    flightStatus.append("Flight status: ", site.statusBadge(flight.status));

    const actions = card.querySelector(".booking__actions");
    if (booking.status === "confirmed") {
      actions.append(
        actionButton("Change date", `I want to change booking ${ref}`, true),
        actionButton("Cancel booking", `Cancel booking ${ref}`),
        actionButton("Check-in status", `Am I checked in for ${ref}?`),
      );
    } else if (booking.status === "checked_in") {
      actions.append(actionButton("Flight status", `What is the status of flight ${flight.flight_number}?`, true));
    } else {
      actions.append(actionButton("Book a new flight", "I want to book a flight", true));
    }
    return card;
  }

  async function load() {
    const user = await site.requireRole("passenger");
    if (!user) return;
    subtitle.textContent = `Welcome back, ${user.name.split(" ")[0]}. Manage your trips here or ask the assistant.`;
    try {
      const bookings = await window.KQApi.myBookings();
      list.replaceChildren(...bookings.map(renderBooking));
      empty.hidden = bookings.length > 0;
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      list.setAttribute("aria-busy", "false");
    }
  }

  document.getElementById("find-flights").addEventListener("click", () =>
    window.KQChat.open("I want to book a flight", "I want to book a flight"));
  load();
})();
