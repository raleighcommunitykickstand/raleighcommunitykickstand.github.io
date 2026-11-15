/* =========================================================
   NEWSLETTERS
   newsletters.html: every issue side by side as slides
   (fullPage.js), with arrows and dots to flip between them.
   It opens on the newest issue.

   The list of issues ("newsletters") comes from
   newsletter/newsletters.js, which utils/md2mjml.py rewrites
   every time I build an issue, so there's nothing to update
   here when a new one comes out.
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  const section = document.querySelector("#fullpage .section");

  // One slide per issue, each showing that issue's HTML page
  newsletters.forEach((slug) => {
    const slide = document.createElement("div");
    slide.className = "slide";

    const frame = document.createElement("iframe");
    frame.src = `newsletter/${slug}.html`;
    frame.title = `Newsletter ${slug}`; // what screen readers announce for the frame
    frame.loading = "lazy"; // issues load as I flip to them, not all at once

    slide.append(frame);
    section.append(slide);
  });

  new fullpage("#fullpage", {
    licenseKey: "gplv3-license", // fullPage.js is free for GPLv3 open-source sites like this one
    credits: { enabled: false },
    controlArrows: true,
    loopHorizontal: true, // past the newest issue wraps around to the oldest
    slidesNavigation: true, // the dots along the bottom
    keyboardScrolling: true, // arrow keys flip issues

    // Jump straight to the newest issue (the last slide) without animating
    afterRender() {
      fullpage_api.silentMoveTo(1, newsletters.length - 1);
    },
  });
});
