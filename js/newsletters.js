document.addEventListener("DOMContentLoaded", () => {
  const section = document.querySelector(".section");

  newsletters.forEach((slug) => {
    const slide = document.createElement("div");
    slide.className = "slide";

    slide.innerHTML = `
          <iframe src="./newsletter/${slug}.html" loading="lazy"></iframe>
        `;

    section.appendChild(slide);
  });

  const latest = newsletters.length - 1;

  new fullpage("#fullpage", {
    licenseKey: "gplv3-license",
    credits: {
      enabled: false,
    },
    controlArrows: true,
    loopHorizontal: true,
    slidesNavigation: true,
    keyboardScrolling: true,
    afterRender: function () {
      fullpage_api.silentMoveTo(1, latest);
    },
  });
});
