// ticker
document.addEventListener("DOMContentLoaded", function () {
  // Select the target element
  const tickerContainer = document.getElementById('ticker-container');

  // Create a new Intersection Observer instance
  const observer = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {

      if (entry.isIntersecting) {

        // Perform an action
        tickerContainer.classList.add('visible');

        const counters = document.querySelectorAll('.ticker-value');
        const speed = 500;

        counters.forEach(counter => {
          const animate = () => {
            const value = +counter.getAttribute('targetValue');
            const data = +counter.innerText;

            const time = value / speed;
            if (data < value) {
              counter.innerText = Math.ceil(data + time);
              setTimeout(animate, 1);
            } else {
              counter.innerText = value;
            }
          }

          animate();
        });

        // Unobserve the element if the action should happen only once
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1
  });

  // Start observing the ticker-container div
  observer.observe(tickerContainer);
});


function facebookCardClick() {
  window.open('https://www.facebook.com/RaleighCommunityKickstand/', '_blank');
}

function emailCardClick() {
  location.href = "mailto:raleighcommunitykickstand@gmail.com";
}

function paypalCardClick() {
  var x = document.getElementById("paypalForm").submit();
}
