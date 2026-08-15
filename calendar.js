const MOBILE_BREAKPOINT = 768;
const TIME_ZONE = "America/New_York";

function isMobile() {
  return window.innerWidth < MOBILE_BREAKPOINT;
}

function formatEventDateRange(startInput, endInput, allDay, timeZone) {
  const start = new Date(startInput);
  const end = new Date(endInput);

  if (allDay) {
    return new Intl.DateTimeFormat("en-US", {
      timeZone,
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    }).format(start);
  }

  const datePart = new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(start);

  const startTime = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour: "numeric",
    minute: "2-digit",
  }).format(start);

  const endTime = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour: "numeric",
    minute: "2-digit",
  }).format(end);

  return `${datePart} • ${startTime} to ${endTime}`;
}

function initCalendar() {
  const calendarEl = document.getElementById("calendar");

  const modal = document.getElementById("event-modal");
  const modalClose = document.getElementById("event-modal-close");
  const modalBackdrop = modal.querySelector(".event-modal-backdrop");
  const modalTitle = document.getElementById("event-modal-title");
  const modalDate = document.getElementById("event-modal-date");
  const modalLocation = document.getElementById("event-modal-location");
  const modalDescription = document.getElementById("event-modal-description");
  const modalImage = document.getElementById("event-modal-image");
  const modalLinks = document.getElementById("event-modal-links");

  function openModal() {
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function clearLinks() {
    modalLinks.innerHTML = "";
  }

  function addLinkButton(href, label) {
    if (!href) return;
    const a = document.createElement("a");
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = label;
    modalLinks.appendChild(a);
  }

  function renderEventModal(event) {
    const props = event.extendedProps;

    modalTitle.textContent = event.title || "";

    modalDate.textContent = formatEventDateRange(event.start, event.end, event.allDay, TIME_ZONE);

    modalLocation.textContent = props.location || "";
    modalDescription.innerHTML = props.description || "";

    clearLinks();

    if (event.url) {
      addLinkButton(event.url, "Event Link");
    }

    openModal();
  }

  const today = new Date();

  const calendar = new FullCalendar.Calendar(calendarEl, {
    timeZone: TIME_ZONE,

    initialView: isMobile() ? "listUpcoming" : "dayGridMonth",

    views: {
      dayGridMonth: {
        dayMaxEvents: 2,
      },

      listUpcoming: {
        type: "list",
        duration: { days: 60 },
      },
    },

    height: "auto",
    aspectRatio: 2.0,

    headerToolbar: {
      left: "prev,next",
      center: "title",
      right: "today dayGridMonth,listUpcoming",
    },

    buttons: {
      dayGridMonth: {
        text: "Month",
      },
      listUpcoming: {
        text: "List",
      },
    },

    titleFormat: {
      month: "long",
      year: "numeric",
    },

    eventColor: "#148378",
    eventContrastColor: "#ffffff",

    events: {
      url: "data/calendar.ics",
      format: "ics",
    },

    dayMaxEvents: true,
    fixedWeekCount: false,
    showNonCurrentDates: false,
    displayEventEnd: false,

    eventClass: "rck-event",
    blockEventClass: "rck-block-event",
    listItemEventClass: "rck-list-event",
    blockEventTitleClass: "rck-event-title",

    eventDisplay: "block", // wrap event title

    dayHeaderClass: "rck-day-header",

    dayCellClass(info) {
      return info.isToday ? "rck-day-cell rck-day-cell-today" : "rck-day-cell";
    },

    listDayHeaderClass(info) {
      return info.isToday ? "rck-list-day-header rck-list-day-header-today" : "rck-list-day-header";
    },

    toolbarClass: "rck-toolbar",
    toolbarSectionClass: "rck-toolbar-section",
    toolbarTitleClass: "rck-toolbar-title",
    buttonClass: "rck-calendar-button",

    eventClick(info) {
      info.jsEvent.preventDefault();
      renderEventModal(info.event);
    },
  });

  calendar.render();

  /* ---------------------------------------------------------
   RESPONSIVE RESIZING
   --------------------------------------------------------- */

  let resizeTimer;

  function syncResponsiveView() {
    clearTimeout(resizeTimer);

    resizeTimer = setTimeout(() => {
      const mobile = isMobile();
      const nextView = mobile ? "listMonth" : "dayGridMonth";

      if (calendar.view.type !== nextView) {
        calendar.changeView(nextView);
      }
    }, 150);
  }

  window.addEventListener("resize", syncResponsiveView);

  modalClose.addEventListener("click", closeModal);
  modalBackdrop.addEventListener("click", closeModal);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) {
      closeModal();
    }
  });
}

document.addEventListener("DOMContentLoaded", function () {
  initCalendar();
});
