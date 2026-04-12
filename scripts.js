const TICKER_VALUES = [
  197, // events
  914, // repairs
  2163, // distributed
];

const TICKER_SPEED = 100;

function animateTicker() {
  const tickerContainer = document.getElementById("ticker-container");
  if (!tickerContainer) return;

  const counters = tickerContainer.querySelectorAll(".ticker-value");

  const observer = new IntersectionObserver(
    (entries, observerInstance) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;

        tickerContainer.classList.add("visible");

        counters.forEach((counter, index) => {
          const target = TICKER_VALUES[index] ?? 0;

          function animate() {
            const current = +counter.innerText;
            const step = target / TICKER_SPEED;

            if (current < target) {
              counter.innerText = Math.ceil(current + step);
              requestAnimationFrame(animate);
            } else {
              counter.innerText = target;
            }
          }

          animate();
        });

        observerInstance.unobserve(entry.target);
      });
    },
    {
      threshold: 0.1,
    },
  );

  observer.observe(tickerContainer);
}

function setupExternalLinks() {
  document.querySelectorAll("a[href]").forEach((a) => {
    const href = a.getAttribute("href");
    if (!href) return;

    if (href.startsWith("#")) return;
    if (href.startsWith("mailto:")) return;
    if (href.startsWith("javascript:")) return;

    const isExternal = href.startsWith("http");

    if (isExternal) {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    }
  });
}

function updateNavbarSpacer() {
  const nav = document.getElementById("mainNav");
  const spacer = document.getElementById("navbar-spacer");

  if (!nav || !spacer) return;

  spacer.style.height = nav.offsetHeight + "px";
}

function setupScrollSpyAndNavbar() {
  const mainNav = document.body.querySelector("#mainNav");

  if (mainNav) {
    new bootstrap.ScrollSpy(document.body, {
      target: "#mainNav",
      rootMargin: "0px 0px -40%",
    });
  }

  const navbarToggler = document.body.querySelector(".navbar-toggler");

  const responsiveNavItems = document.querySelectorAll("#navbarResponsive .nav-link");

  responsiveNavItems.forEach((item) => {
    item.addEventListener("click", () => {
      if (window.getComputedStyle(navbarToggler).display !== "none") {
        navbarToggler.click();
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  animateTicker();
  setupExternalLinks();
  updateNavbarSpacer();
  setupScrollSpyAndNavbar();
});

window.addEventListener("resize", updateNavbarSpacer);
