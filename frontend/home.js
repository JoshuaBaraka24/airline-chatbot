/* Home page: hero buttons. Topic and destination shortcuts are handled in site.js. */
(function () {
  "use strict";

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
