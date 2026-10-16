/* Staff dashboard (FR-06): statistics, conversation log, transcripts, resolving escalations. */
(function () {
  "use strict";

  const api = window.KQApi;
  const site = window.KQSite;
  const $ = (id) => document.getElementById(id);
  const rows = $("conversation-rows");
  const filter = $("status-filter");
  const dialog = $("transcript");

  const INTENT_LABELS = {
    check_flight_status: "Flight status", change_booking: "Change booking", cancel_booking: "Cancel booking",
    new_booking: "New booking", baggage_policy: "Baggage", check_in_procedure: "Check-in help",
    check_in_status: "Check-in status", escalate_to_agent: "Asked for an agent", out_of_scope: "Out of scope",
    inform: "Gave details", affirm: "Yes", deny: "No", greet: "Greeting", goodbye: "Goodbye",
    thank_you: "Thanks", bot_capabilities: "What can you do?", nlu_fallback: "Not understood",
  };
  const label = (intent) => INTENT_LABELS[intent] || intent || "–";

  function showError(message) {
    $("admin-error").textContent = message;
    $("admin-error").hidden = false;
  }

  function renderBars(listId, entries) {
    const list = $(listId);
    const max = Math.max(1, ...entries.map(([, count]) => count));
    list.replaceChildren(...entries.map(([name, count]) => {
      const item = document.createElement("li");
      const text = document.createElement("div");
      text.className = "bar__label";
      const nameSpan = document.createElement("span");
      nameSpan.textContent = name;
      const countSpan = document.createElement("strong");
      countSpan.textContent = count;
      text.append(nameSpan, countSpan);
      const track = document.createElement("div");
      track.className = "bar__track";
      track.setAttribute("aria-hidden", "true");
      const fill = document.createElement("div");
      fill.className = "bar__fill";
      fill.style.width = `${Math.round((count / max) * 100)}%`;
      track.append(fill);
      item.append(text, track);
      return item;
    }));
    if (!entries.length) {
      const item = document.createElement("li");
      item.className = "muted";
      item.textContent = "No data yet.";
      list.append(item);
    }
  }

  async function loadStats() {
    const stats = await api.adminStats();
    $("stat-total").textContent = stats.total;
    $("stat-today").textContent = stats.today;
    $("stat-active").textContent = stats.active;
    $("stat-escalated").textContent = stats.escalated;
    $("stat-turns").textContent = stats.avg_turns;
    renderBars("intent-bars", stats.top_intents.map((row) => [label(row.intent), row.count]));
    const bookingLabels = { confirmed: "Confirmed", checked_in: "Checked in", cancelled: "Cancelled" };
    renderBars("booking-bars", Object.entries(stats.bookings).map(([status, count]) => [bookingLabels[status] || status, count]));
  }

  function cell(content) {
    const td = document.createElement("td");
    if (content instanceof Node) td.append(content);
    else td.textContent = content;
    return td;
  }

  function conversationRow(conversation) {
    const tr = document.createElement("tr");
    const passenger = conversation.passenger_name || "Guest";
    const actions = document.createElement("div");
    actions.className = "row-actions";

    const view = document.createElement("button");
    view.type = "button";
    view.className = "btn btn--secondary btn--small";
    view.textContent = "View";
    view.setAttribute("aria-label", `View transcript of conversation started ${site.formatDateTime(conversation.start_time)}`);
    view.addEventListener("click", () => openTranscript(conversation));
    actions.append(view);

    if (conversation.status === "escalated") {
      const resolve = document.createElement("button");
      resolve.type = "button";
      resolve.className = "btn btn--primary btn--small";
      resolve.textContent = "Mark resolved";
      resolve.addEventListener("click", async () => {
        resolve.disabled = true;
        try {
          await api.adminResolve(conversation.conversation_id);
          await refresh();
          $("log-status").textContent = "Conversation marked as resolved.";
        } catch (error) {
          showError(error.message);
          resolve.disabled = false;
        }
      });
      actions.append(resolve);
    }

    tr.append(
      cell(site.formatDateTime(conversation.start_time)),
      cell(passenger),
      cell(String(conversation.turn_count)),
      cell(label(conversation.last_intent)),
      cell(site.statusBadge(conversation.status)),
      cell(actions),
    );
    return tr;
  }

  async function loadConversations() {
    $("log-status").textContent = "Loading conversations…";
    const conversations = await api.adminConversations(filter.value || null);
    rows.replaceChildren(...conversations.map(conversationRow));
    $("log-empty").hidden = conversations.length > 0;
    $("log-status").textContent = `${conversations.length} conversation${conversations.length === 1 ? "" : "s"} shown.`;
  }

  async function openTranscript(conversation) {
    const body = $("transcript-body");
    $("transcript-title").textContent =
      `Transcript · ${conversation.passenger_name || "Guest"} · ${site.formatDateTime(conversation.start_time)}`;
    body.replaceChildren();
    const loading = document.createElement("p");
    loading.className = "muted";
    loading.textContent = "Loading…";
    body.append(loading);
    dialog.showModal();
    try {
      const lines = await api.adminTranscript(conversation.conversation_id);
      body.replaceChildren(...lines.map((line) => {
        const bubble = document.createElement("p");
        bubble.className = `transcript__line transcript__line--${line.speaker}`;
        bubble.append(document.createTextNode(line.text));
        const meta = document.createElement("span");
        meta.className = "transcript__meta";
        const when = line.timestamp ? site.formatTime(line.timestamp * 1000) : "";
        meta.textContent = [line.speaker === "passenger" ? "Passenger" : "Assistant", when, line.intent ? label(line.intent) : ""]
          .filter(Boolean).join(" · ");
        bubble.append(meta);
        return bubble;
      }));
      if (!lines.length) loading.textContent = "No messages recorded.";
    } catch (error) {
      loading.textContent = error.message;
    }
  }

  async function refresh() {
    try {
      await Promise.all([loadStats(), loadConversations()]);
      $("admin-error").hidden = true;
    } catch (error) {
      showError(error.message);
    }
  }

  $("transcript-close").addEventListener("click", () => dialog.close());
  filter.addEventListener("change", refresh);
  $("refresh-btn").addEventListener("click", refresh);

  site.requireRole("admin").then((user) => user && refresh());
})();
