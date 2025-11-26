// ticker
document.addEventListener("DOMContentLoaded", function () {
  // Select the target element
  const tickerContainer = document.getElementById("ticker-container");

  // Create a new Intersection Observer instance
  const observer = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          // Perform an action
          tickerContainer.classList.add("visible");
          const counters = document.querySelectorAll(".ticker-value");
          const speed = 100;

          counters.forEach((counter) => {
            const animate = () => {
              const value = +counter.getAttribute("targetValue");
              const data = +counter.innerText;

              const time = value / speed;
              if (data < value) {
                counter.innerText = Math.ceil(data + time);
                requestAnimationFrame(animate);
              } else {
                counter.innerText = value;
              }
            };

            animate();
          });

          // Unobserve the element if the action should happen only once
          observer.unobserve(entry.target);
        }
      });
    },
    {
      threshold: 0.1,
    }
  );

  // Start observing the ticker-container div
  observer.observe(tickerContainer);
});

// Make external links open in a new tab
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("a[href]").forEach((a) => {
    const href = a.getAttribute("href");

    // Skip anchors (#about, #fix, etc.)
    if (href.startsWith("#")) return;

    // Skip mailto:
    if (href.startsWith("mailto:")) return;

    // Skip JavaScript links (just in case)
    if (href.startsWith("javascript:")) return;

    // Detect external: begins with http AND not your own domain
    const isExternal = href.startsWith("http");

    if (isExternal) {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    }
  });
});

// function facebookCardClick() {
//   window.open('https://www.facebook.com/RaleighCommunityKickstand/', '_blank');
// }

// function emailCardClick() {
//   location.href = "mailto:raleighcommunitykickstand@gmail.com";
// }

// function paypalCardClick() {
//   var x = document.getElementById("paypalForm").submit();
// }
