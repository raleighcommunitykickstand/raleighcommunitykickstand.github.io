/* =========================================================
   SITE
   Small things every page gets, including one-off pages
   (copy _templates/one-off.html to start one).

   Load it at the bottom of the page, after Bootstrap's JS if
   the page uses Bootstrap. Page files (home.js, calendar.js...)
   go after this one.
   ========================================================= */

/* ---------------------------------------------------------
   LINKS TO OTHER WEBSITES
   They open in a new tab so my page stays open behind them.
   Links to my own pages, #sections, and email addresses are
   left alone.
   --------------------------------------------------------- */

function openExternalLinksInNewTabs() {
  document.querySelectorAll('a[href^="http"]').forEach((link) => {
    if (link.host === window.location.host) return;

    link.target = "_blank";
    link.rel = "noopener noreferrer";
  });
}

/* ---------------------------------------------------------
   PHONE MENU
   On phones the navbar links live in a collapsed menu (the
   hamburger button). Bootstrap leaves it open after a link is
   tapped, which covers the section I just jumped to, so I
   close it. On bigger screens there's nothing to close, so
   this does nothing.
   --------------------------------------------------------- */

function closePhoneMenuAfterTap() {
  const menu = document.querySelector(".navbar-collapse");
  if (!menu || !window.bootstrap) return; // no menu, or a page without Bootstrap's JS

  const collapse = bootstrap.Collapse.getOrCreateInstance(menu, { toggle: false });

  menu.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => collapse.hide());
  });
}

document.addEventListener("DOMContentLoaded", () => {
  openExternalLinksInNewTabs();
  closePhoneMenuAfterTap();
});
