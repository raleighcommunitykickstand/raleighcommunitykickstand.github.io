/* =========================================================
   ZINE
   spokecity.html: shows media/docs/spoke-city.pdf like a
   printed zine, drawn with pdf.js.

   Wide screens: front cover by itself, then two-page spreads
   (2-3, 4-5...) like an open booklet, then the back cover by
   itself if it's on its own page.
   Narrow screens: one page at a time.
   ========================================================= */

const ZINE_PDF = "media/docs/spoke-city.pdf";
const SPREAD_MIN_WIDTH = 960; // narrower than this: one page at a time
const SIDE_PADDING = 40; // #zine-container's 20px padding on each side (spokecity.html)

const container = document.getElementById("zine-container");
const indicator = document.getElementById("page-indicator");

let pdfDoc = null;
let currentPage = 1; // the page I'm on (1 = front cover)
let renderCount = 0; // lets a slow, older render know a newer one has replaced it

function showsSpreads() {
  return window.innerWidth >= SPREAD_MIN_WIDTH;
}

/* ---------------------------------------------------------
   WHICH PAGES ARE SHOWING
   --------------------------------------------------------- */

// The first page of the spread a page belongs to: the cover is alone, then 2-3, 4-5...
function spreadStart(page) {
  if (page === 1) return 1;
  return page % 2 === 0 ? page : page - 1;
}

function visiblePages() {
  if (!showsSpreads()) return [currentPage];

  const start = spreadStart(currentPage);
  const isAlone = start === 1 || start === pdfDoc.numPages; // front cover, or a back cover on its own page

  return isAlone ? [start] : [start, start + 1];
}

/* ---------------------------------------------------------
   FLIPPING PAGES
   --------------------------------------------------------- */

function nextPage() {
  if (!pdfDoc) return;

  if (!showsSpreads()) {
    currentPage = Math.min(currentPage + 1, pdfDoc.numPages);
  } else {
    const start = spreadStart(currentPage);
    const next = start === 1 ? 2 : start + 2;
    if (next <= pdfDoc.numPages) currentPage = next;
  }

  render();
}

function prevPage() {
  if (!pdfDoc) return;

  if (!showsSpreads()) {
    currentPage = Math.max(currentPage - 1, 1);
  } else {
    const start = spreadStart(currentPage);
    currentPage = start <= 2 ? 1 : start - 2;
  }

  render();
}

/* ---------------------------------------------------------
   DRAWING
   The new pages are drawn off screen first and then swapped
   in all at once, so the zine never goes blank or jumps
   while a page is drawing.
   --------------------------------------------------------- */

// Draw one page into a canvas that's `width` pixels wide on screen
async function drawPage(pageNumber, width) {
  const page = await pdfDoc.getPage(pageNumber);
  const scale = width / page.getViewport({ scale: 1 }).width;

  // Extra pixels on high-res screens (phones, retina) so the text is sharp, not blurry
  const viewport = page.getViewport({ scale: scale * window.devicePixelRatio });

  const canvas = document.createElement("canvas");
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  canvas.style.width = `${width}px`;
  canvas.style.opacity = "0"; // fades in once it's on the page

  await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
  return canvas;
}

async function render() {
  const thisRender = ++renderCount;
  const pages = visiblePages();

  // "Page 1 / 28" or "Page 2–3 / 28" (updated right away, before the pages finish drawing)
  indicator.textContent = `Page ${pages.join("–")} / ${pdfDoc.numPages}`;

  // Half the width for each page of a spread; the front cover is the same size as one spread page
  const pageWidth = (window.innerWidth - SIDE_PADDING) / (showsSpreads() ? 2 : 1);

  const canvases = await Promise.all(pages.map((page) => drawPage(page, pageWidth)));

  // If I clicked again (or resized) while these were drawing, a newer render takes over
  if (thisRender !== renderCount) return;

  container.classList.toggle("single-page", pages.length === 1);
  container.replaceChildren(...canvases);
  requestAnimationFrame(() => canvases.forEach((canvas) => (canvas.style.opacity = "1")));
}

/* ---------------------------------------------------------
   START
   --------------------------------------------------------- */

document.getElementById("zine-prev").addEventListener("click", prevPage);
document.getElementById("zine-next").addEventListener("click", nextPage);

// Redraw at the new size after the window stops resizing (it may also switch between spreads and single pages)
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => pdfDoc && render(), 200);
});

pdfjsLib.getDocument(ZINE_PDF).promise.then((pdf) => {
  pdfDoc = pdf;
  render();
});
