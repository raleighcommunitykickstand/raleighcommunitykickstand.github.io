const url = "spoke_city.pdf";
const windowThreshold = 960;
const container = document.getElementById("zine-container");
let pdfDoc = null;
let currentPageIndex = 0;

const loadingTask = pdfjsLib.getDocument(url);
loadingTask.promise.then((pdf) => {
  pdfDoc = pdf;
  render();
  updatePageIndicator();
});

function isNarrow() {
  return window.innerWidth < windowThreshold;
}

function render() {
  const narrow = isNarrow();
  const isFirstOrLast = currentPageIndex === 0 || currentPageIndex === pdfDoc.numPages - 1;
  const isSingle = narrow || isFirstOrLast;
  container.className = isSingle ? "single-page" : "";

  const pages = isSingle ? [currentPageIndex + 1] : [currentPageIndex + 1, currentPageIndex + 2];

  const availableWidth = window.innerWidth - 40;
  const targetWidthPerPage = isSingle ? availableWidth : availableWidth / 2;

  if (narrow && isSingle) {
    // NARROW SCREEN — pre-calculate height of single page
    pdfDoc.getPage(pages[0]).then((page) => {
      const unscaled = page.getViewport({ scale: 1 });
      const scale = targetWidthPerPage / unscaled.width;
      const expectedHeight = unscaled.height * scale;

      // Lock container size
      container.style.width = targetWidthPerPage + "px";
      container.style.height = expectedHeight + "px";
      container.style.minWidth = container.style.width;
      container.style.minHeight = container.style.height;

      container.innerHTML = "";
      renderAndInsertPages(pages, false); // forceHalfWidth = true for narrow
    });
  } else {
    // WIDE SCREEN
    Promise.all(pages.map((num) => pdfDoc.getPage(num))).then((loadedPages) => {
      const scaledSizes = loadedPages.map((page) => {
        const unscaled = page.getViewport({ scale: 1 });
        const scale = targetWidthPerPage / unscaled.width;
        return {
          width: unscaled.width * scale,
          height: unscaled.height * scale,
          scale,
        };
      });

      let maxHeight = Math.max(...scaledSizes.map((s) => s.height));
      const totalWidth = scaledSizes.reduce((sum, s) => sum + s.width, 0);

      // Special case: front or back single page on wide screen
      if (!narrow && isFirstOrLast) {
        let spreadPagesNums;
        if (currentPageIndex === 0) {
          spreadPagesNums = [2, 3].filter((n) => n <= pdfDoc.numPages);
        } else {
          spreadPagesNums = [pdfDoc.numPages - 1, pdfDoc.numPages].filter((n) => n <= pdfDoc.numPages && n > 0);
        }

        if (spreadPagesNums.length === 2) {
          Promise.all(spreadPagesNums.map((num) => pdfDoc.getPage(num))).then((spreadPages) => {
            const spreadHeights = spreadPages.map((page) => {
              const unscaled = page.getViewport({ scale: 1 });
              const scale = availableWidth / 2 / unscaled.width;
              return unscaled.height * scale;
            });
            const spreadMaxHeight = Math.max(...spreadHeights);
            maxHeight = Math.max(maxHeight, spreadMaxHeight);

            container.style.width = availableWidth + "px";
            container.style.height = maxHeight + "px";
            container.style.minWidth = container.style.width;
            container.style.minHeight = container.style.height;

            container.innerHTML = "";
            renderAndInsertPages(pages, true);
          });
          return; // skip the rest of this branch for now
        }
      }

      // Standard two-page render path
      container.style.width = totalWidth + "px";
      container.style.height = maxHeight + "px";
      container.style.minWidth = container.style.width;
      container.style.minHeight = container.style.height;

      container.innerHTML = "";
      renderAndInsertPages(pages, isSingle && !narrow, scaledSizes);
    });
  }
}

function renderAndInsertPages(pageNumbers, forceHalfWidth = false, scaledSizes = null) {
  const isSingle = container.classList.contains("single-page");
  const availableWidth = window.innerWidth - 40;

  let pending = pageNumbers.length;
  const canvases = [];

  pageNumbers.forEach((num, index) => {
    pdfDoc.getPage(num).then((page) => {
      let scale, viewport;

      if (scaledSizes && scaledSizes[index]) {
        // Use precomputed scale and sizes to avoid mismatch
        scale = scaledSizes[index].width / page.getViewport({ scale: 1 }).width;
        viewport = page.getViewport({ scale });
      } else {
        const targetWidthPerPage = isSingle && !forceHalfWidth ? availableWidth : availableWidth / 2;
        const unscaledViewport = page.getViewport({ scale: 1 });
        scale = targetWidthPerPage / unscaledViewport.width;
        viewport = page.getViewport({ scale });
      }

      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.opacity = "0";
      canvas.style.transition = "opacity 0.3s ease";

      const context = canvas.getContext("2d");
      page.render({ canvasContext: context, viewport }).promise.then(() => {
        canvases[index] = canvas;
        pending--;

        if (pending === 0) {
          // Append all canvases at once, then fade in
          canvases.forEach((c) => container.appendChild(c));
          requestAnimationFrame(() => {
            canvases.forEach((c) => (c.style.opacity = "1"));
          });

          // Clear locked container dimensions after render
          container.style.width = "";
          container.style.height = "";
          container.style.minWidth = "";
          container.style.minHeight = "";
        }
      });
    });
  });
}

function nextPage() {
  if (isNarrow()) {
    if (currentPageIndex + 1 < pdfDoc.numPages) {
      currentPageIndex += 1;
    }
  } else {
    if (currentPageIndex === 0) {
      currentPageIndex = 1;
    } else if (currentPageIndex + 2 < pdfDoc.numPages) {
      currentPageIndex += 2;
    } else if (currentPageIndex + 1 < pdfDoc.numPages) {
      currentPageIndex += 1;
    }
  }
  render();
  updatePageIndicator();
}

function prevPage() {
  if (isNarrow()) {
    if (currentPageIndex > 0) {
      currentPageIndex -= 1;
    }
  } else {
    if (currentPageIndex === 1) {
      currentPageIndex = 0;
    } else if (currentPageIndex - 2 >= 1) {
      currentPageIndex -= 2;
    }
  }
  render();
  updatePageIndicator();
}

function updatePageIndicator() {
  const narrow = isNarrow();
  const isFirstOrLast = currentPageIndex === 0 || currentPageIndex === pdfDoc.numPages - 1;
  const isSingle = narrow || isFirstOrLast;

  const indicator = document.getElementById("page-indicator");
  let display;

  if (isSingle) {
    display = `${currentPageIndex + 1} / ${pdfDoc.numPages}`;
  } else {
    const secondPage = Math.min(currentPageIndex + 2, pdfDoc.numPages);
    display = `${currentPageIndex + 1}–${secondPage} / ${pdfDoc.numPages}`;
  }

  indicator.textContent = `Page ${display}`;
}

function debounce(func, delay) {
  let timeout;
  return function () {
    clearTimeout(timeout);
    timeout = setTimeout(func, delay);
  };
}

// window.addEventListener('resize', render);
window.addEventListener("resize", debounce(render, 200));
