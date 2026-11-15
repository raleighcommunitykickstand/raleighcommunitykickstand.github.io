/* =========================================================
   CALENDAR
   My events from data/calendar.ics (a copy of the Google
   Calendar that the update-calendar GitHub Action refreshes),
   drawn with FullCalendar 7 in two places:
     - calendar.html: the full calendar (#calendar)
     - index.html: the Upcoming Events agenda (#agenda)
   Clicking an event on either one opens the same pop-up.

   Needs FullCalendar, its Bootstrap theme and iCalendar
   plugins, ical.js, and Bootstrap's JS loaded first.
   ========================================================= */

const MOBILE_BREAKPOINT = 768; // matches the phone styles in css/calendar.css
const TIME_ZONE = "America/New_York";

function isMobile() {
  return window.innerWidth < MOBILE_BREAKPOINT;
}

/* ---------------------------------------------------------
   EVENT POP-UP HELPERS
   --------------------------------------------------------- */

// "Saturday, November 15, 2026 • 1:00 PM to 3:00 PM" (just the date for all-day events)
function formatEventDate(start, end, allDay) {
  const date = start.toLocaleDateString("en-US", {
    timeZone: TIME_ZONE,
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  if (allDay) return date;

  const time = (d) => d.toLocaleTimeString("en-US", { timeZone: TIME_ZONE, hour: "numeric", minute: "2-digit" });

  return end ? `${date} • ${time(start)} to ${time(end)}` : `${date} • ${time(start)}`;
}

// Google Calendar descriptions are HTML. I keep the simple formatting (links, line
// breaks, bold, lists) and drop everything else, so nobody with edit access to the
// calendar can sneak a script onto my site.
const ALLOWED_TAGS = ["A", "B", "STRONG", "I", "EM", "U", "BR", "P", "UL", "OL", "LI"];
const DROPPED_TAGS = ["SCRIPT", "STYLE", "IFRAME", "OBJECT", "EMBED"];

function cleanDescription(html) {
  const source = new DOMParser().parseFromString(html, "text/html").body; // parsing doesn't run anything
  const clean = document.createDocumentFragment();
  copyAllowed(source, clean);
  return clean;
}

function copyAllowed(from, to) {
  for (const node of from.childNodes) {
    if (node.nodeType === Node.TEXT_NODE) {
      to.append(node.textContent);
    } else if (node.nodeType !== Node.ELEMENT_NODE || DROPPED_TAGS.includes(node.tagName)) {
      continue;
    } else if (ALLOWED_TAGS.includes(node.tagName)) {
      const el = document.createElement(node.tagName); // a fresh tag, so no attributes come along
      const href = node.getAttribute("href") || "";
      if (node.tagName === "A" && /^(https?:|mailto:)/i.test(href)) {
        el.href = href;
        if (!href.startsWith("mailto:")) {
          el.target = "_blank";
          el.rel = "noopener noreferrer";
        }
      }
      copyAllowed(node, el);
      to.append(el);
    } else {
      copyAllowed(node, to); // other tags (span, div...): keep just what's inside them
    }
  }
}

/* ---------------------------------------------------------
   EVENT POP-UP
   The Bootstrap modal in calendar.html and index.html.
   Returns the function that fills it in and opens it.
   --------------------------------------------------------- */

function setUpEventModal() {
  const modalEl = document.getElementById("event-modal");
  const modal = new bootstrap.Modal(modalEl);
  const modalTitle = document.getElementById("event-modal-title");
  const modalDate = document.getElementById("event-modal-date");
  const modalLocation = document.getElementById("event-modal-location");
  const modalDescription = document.getElementById("event-modal-description");

  // When the pop-up closes, put keyboard focus back on the event that opened it
  let openedFrom = null;
  modalEl.addEventListener("hidden.bs.modal", () => openedFrom?.focus());

  return function showEvent(event, eventEl) {
    const props = event.extendedProps;
    openedFrom = eventEl;

    modalTitle.textContent = event.title || "";
    modalDate.textContent = formatEventDate(event.start, event.end, event.allDay);
    modalLocation.textContent = props.location || "";
    modalDescription.replaceChildren(cleanDescription(props.description || ""));

    modal.show();
  };
}

/* ---------------------------------------------------------
   SHARED CALENDAR SETTINGS
   Same events, colors, and rck-* class names for the full
   calendar page and the homepage agenda.
   --------------------------------------------------------- */

function sharedOptions(showEvent) {
  const theme = getComputedStyle(document.documentElement);

  return {
    timeZone: TIME_ZONE,

    views: {
      // The next 60 days as a list (phones on the calendar page, and the homepage agenda)
      listUpcoming: {
        type: "list",
        duration: { days: 60 },
      },
    },

    events: {
      url: "data/calendar.ics",
      format: "ics",
    },

    // Teal events with white text, read from css/theme.css so the colors live in one place
    eventColor: theme.getPropertyValue("--rck-teal").trim(),
    eventContrastColor: theme.getPropertyValue("--rck-white").trim(),

    displayEventEnd: false,

    eventClass: "rck-event",
    listItemEventClass: "rck-list-event",
    listItemEventTimeClass: "rck-list-event-time",
    listItemEventTitleClass: "rck-list-event-title",

    listDayHeaderClass(info) {
      return info.isToday ? "rck-list-day-header rck-list-day-header-today" : "rck-list-day-header";
    },

    eventClick(info) {
      info.jsEvent.preventDefault();
      showEvent(info.event, info.el);
    },
  };
}

/* ---------------------------------------------------------
   FULL CALENDAR (calendar.html)
   Month view on bigger screens, list view on phones.
   --------------------------------------------------------- */

function initFullCalendar(calendarEl, showEvent) {
  const shared = sharedOptions(showEvent);

  const calendar = new FullCalendar.Calendar(calendarEl, {
    ...shared,

    initialView: isMobile() ? "listUpcoming" : "dayGridMonth",

    views: {
      ...shared.views,
      dayGridMonth: {
        dayMaxEvents: 2,
      },
    },

    height: "auto",

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

    fixedWeekCount: false,
    showNonCurrentDates: false,

    blockEventClass: "rck-block-event",
    blockEventTimeClass: "rck-event-time",
    blockEventTitleClass: "rck-event-title",

    eventDisplay: "block", // wrap event title

    dayHeaderClass: "rck-day-header",

    dayCellClass(info) {
      return info.isToday ? "rck-day-cell rck-day-cell-today" : "rck-day-cell";
    },

    toolbarClass: "rck-toolbar",
    toolbarSectionClass: "rck-toolbar-section",
    toolbarTitleClass: "rck-toolbar-title",
    buttonClass: "rck-calendar-button",
  });

  calendar.render();

  // Switch between month and list when the window crosses the phone width
  let resizeTimer;

  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);

    resizeTimer = setTimeout(() => {
      const nextView = isMobile() ? "listUpcoming" : "dayGridMonth"; // same views as on page load

      if (calendar.view.type !== nextView) {
        calendar.changeView(nextView);
      }
    }, 150);
  });
}

/* ---------------------------------------------------------
   HOMEPAGE AGENDA (index.html)
   The same 60-day list as the calendar page, with no toolbar.
   The box is cut off just after the first few events and
   scrolls for the rest (like Google Calendar's agenda embed).
   --------------------------------------------------------- */

const AGENDA_EVENTS_SHOWN = 3;
const AGENDA_PEEK = 20; // px of the next row left showing, so it's clear the list scrolls

function initAgenda(agendaEl, showEvent) {
  // Cap the box's height at the bottom of the 3rd event (titles can wrap, so I measure instead of guessing)
  function fitToFirstEvents() {
    const cutoffEvent = agendaEl.querySelectorAll(".rck-list-event")[AGENDA_EVENTS_SHOWN - 1];
    const hasMore = agendaEl.querySelectorAll(".rck-list-event").length > AGENDA_EVENTS_SHOWN;

    if (!cutoffEvent || !hasMore) {
      agendaEl.style.maxHeight = ""; // 3 or fewer events: show them all
      return;
    }

    const top = agendaEl.getBoundingClientRect().top - agendaEl.scrollTop;
    agendaEl.style.maxHeight = `${cutoffEvent.getBoundingClientRect().bottom - top + AGENDA_PEEK}px`;
  }

  const agenda = new FullCalendar.Calendar(agendaEl, {
    ...sharedOptions(showEvent),

    initialView: "listUpcoming",
    headerToolbar: false,
    height: "auto",
  });

  agenda.render();

  // Measure again whenever the full list changes height: when the events finish
  // loading and drawing, or when titles wrap differently after a resize
  new ResizeObserver(fitToFirstEvents).observe(agendaEl.firstElementChild);
}

document.addEventListener("DOMContentLoaded", () => {
  const showEvent = setUpEventModal();

  const calendarEl = document.getElementById("calendar");
  const agendaEl = document.getElementById("agenda");

  if (calendarEl) initFullCalendar(calendarEl, showEvent);
  if (agendaEl) initAgenda(agendaEl, showEvent);
});
