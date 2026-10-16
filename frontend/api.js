/* Small client for the gateway API. Exposes window.KQApi. */
(function () {
  "use strict";

  const API_BASE = window.KQ_CHAT_API_BASE || "";

  class ApiError extends Error {
    constructor(status, message) {
      super(message);
      this.status = status;
    }
  }

  const FIELD_MESSAGES = {
    email: "Enter a valid email address.",
    password: "Passwords need at least 8 characters, including letters and numbers.",
    name: "Enter your full name.",
    flight_number: "Enter a flight number like KQ101.",
  };

  function describe(status, detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      // FastAPI validation errors: report the first field in plain language
      const field = detail[0].loc && detail[0].loc[detail[0].loc.length - 1];
      return FIELD_MESSAGES[field] || "Please check the details you entered.";
    }
    if (status >= 500) return "The service is temporarily unavailable. Please try again shortly.";
    return "Something went wrong. Please try again.";
  }

  async function request(path, { method = "GET", body, query } = {}) {
    const url = new URL(API_BASE + path, window.location.origin);
    if (query) Object.entries(query).forEach(([k, v]) => v != null && url.searchParams.set(k, v));
    let response;
    try {
      response = await fetch(url, {
        method,
        credentials: "same-origin",
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (_) {
      throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
    }
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(response.status, describe(response.status, data && data.detail));
    return data;
  }

  window.KQApi = {
    ApiError,
    request,
    me: () => request("/api/auth/me"),
    login: (email, password) => request("/api/auth/login", { method: "POST", body: { email, password } }),
    register: (name, email, password) => request("/api/auth/register", { method: "POST", body: { name, email, password } }),
    logout: () => request("/api/auth/logout", { method: "POST" }),
    myBookings: () => request("/api/me/bookings"),
    flightStatus: (flightNumber) => request("/api/flights/status", { query: { flight_number: flightNumber } }),
    adminStats: () => request("/api/admin/stats"),
    adminConversations: (status) => request("/api/admin/conversations", { query: { status } }),
    adminTranscript: (id) => request(`/api/admin/conversations/${id}/transcript`),
    adminResolve: (id) => request(`/api/admin/conversations/${id}/resolve`, { method: "POST" }),
  };
})();
