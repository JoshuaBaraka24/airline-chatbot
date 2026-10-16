/* About page: renders photo credits from assets/photos/credits.json. */
(function () {
  "use strict";

  function link(href, text) {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = text;
    a.rel = "noopener";
    return a;
  }

  async function loadCredits() {
    const tbody = document.getElementById("credit-rows");
    try {
      const response = await fetch("assets/photos/credits.json", { cache: "no-store" });
      const credits = await response.json();
      tbody.replaceChildren(...credits.map((c) => {
        const tr = document.createElement("tr");

        const photo = document.createElement("td");
        const img = document.createElement("img");
        img.src = c.file;
        img.alt = "";
        photo.append(img);

        const usedFor = document.createElement("td");
        usedFor.textContent = c.used_for;

        const title = document.createElement("td");
        title.append(link(c.source, c.title), document.createElement("br"), `by ${c.author}`);

        const license = document.createElement("td");
        license.append(c.license_url ? link(c.license_url, c.license) : c.license);

        tr.append(photo, usedFor, title, license);
        return tr;
      }));
    } catch (_) {
      tbody.firstElementChild.firstElementChild.textContent = "Credits could not be loaded; see assets/photos/credits.json.";
    }
  }
  loadCredits();
})();
