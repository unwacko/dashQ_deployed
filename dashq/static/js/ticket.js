// The customer's ticket page. htmx refreshes #status every 3 seconds;
// this file only reacts to it: sound, vibration and red screen when it's their turn,
// until the customer presses "Stop alert" (staff can resend it).
var alarm = document.getElementById("alarm");
var soundButton = document.getElementById("sound-btn");

// Phones only allow sound after a tap, so we ask for one tap first
if (soundButton) {
  soundButton.addEventListener("click", function () {
    alarm.volume = 0.01;
    alarm.play().then(function () {
      alarm.pause();
      alarm.currentTime = 0;
      alarm.volume = 1;
    }).catch(function () {});
    soundButton.classList.add("on");
    soundButton.querySelector("span").textContent = "Sound alerts are on";
  });
}

function checkTurn() {
  var flag = document.getElementById("turn-flag");
  if (!flag) return;
  var myTurn = flag.dataset.turn === "1";
  var wasMyTurn = document.body.classList.contains("your-turn");
  document.body.classList.toggle("your-turn", myTurn);
  if (myTurn && !wasMyTurn) {
    alarm.currentTime = 0;
    alarm.play().catch(function () {});
    if (navigator.vibrate) navigator.vibrate([400, 200, 400, 200, 400]);
  }
  // "Stop alert" was pressed: silence it straight away
  if (!myTurn && wasMyTurn) {
    alarm.pause();
    if (navigator.vibrate) navigator.vibrate(0);
  }
  // The visit just ended (done, or removed by staff): reload to show the "all done" page
  if (flag.dataset.done === "1" && soundButton) location.reload();
}

// Keep beeping every 6 seconds while it's still their turn
setInterval(function () {
  if (document.body.classList.contains("your-turn")) alarm.play().catch(function () {});
}, 6000);

// "Leave the line?" check before the form is sent
document.querySelectorAll("[data-confirm]").forEach(function (button) {
  button.addEventListener("click", function (event) {
    if (!confirm(button.dataset.confirm)) event.preventDefault();
  });
});

document.body.addEventListener("htmx:afterSettle", checkTurn);
checkTurn();
