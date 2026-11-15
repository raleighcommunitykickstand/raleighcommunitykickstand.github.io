/* =========================================================
   HOME
   Scripts only the homepage (index.html) uses. Loaded after
   site.js.

   (The navbar highlighting the section I'm scrolled to is
   Bootstrap's ScrollSpy, turned on with the data-bs-spy
   attributes on <body> in index.html, so there's no code for
   it here.)
   ========================================================= */

/* ---------------------------------------------------------
   TICKER
   The big numbers (events hosted, repairs, bikes given away).
   The real totals are written in index.html, so that's the
   only place I update them. When the numbers scroll into
   view, they count up from 0 to those totals.
   --------------------------------------------------------- */

const TICKER_DURATION = 1600; // ms to count all the way up

function setUpTicker() {
  const ticker = document.getElementById("ticker-container");
  if (!ticker) return;

  // Anyone who has animations turned off just sees the totals
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const counters = [...ticker.querySelectorAll(".ticker-value")].map((el) => ({
    el,
    total: Number(el.textContent.replace(/\D/g, "")), // digits only, in case I ever write "2,398"
  }));

  counters.forEach(({ el }) => (el.textContent = "0"));

  // Start counting the first time any of the ticker is on screen
  const observer = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer.disconnect();

      const start = performance.now();

      function countUp(now) {
        const progress = Math.min((now - start) / TICKER_DURATION, 1);

        counters.forEach(({ el, total }) => (el.textContent = Math.round(total * progress)));

        if (progress < 1) requestAnimationFrame(countUp);
      }

      requestAnimationFrame(countUp);
    },
    { threshold: 0.1 },
  );

  observer.observe(ticker);
}

document.addEventListener("DOMContentLoaded", setUpTicker);
