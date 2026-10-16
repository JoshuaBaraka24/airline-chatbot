/* Virtual Assistant page. Example prompts are handled by the shared data-chat handler in site.js. */
(function () {
  "use strict";
  document.getElementById("start-chat").addEventListener("click", () => window.KQChat.open());
})();
