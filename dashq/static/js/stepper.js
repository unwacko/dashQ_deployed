// The − and + buttons next to each menu item
document.querySelectorAll("[data-stepper]").forEach(function (box) {
  var input = box.querySelector("input");
  box.querySelectorAll("button").forEach(function (button) {
    button.addEventListener("click", function () {
      var next = Number(input.value || 0) + Number(button.dataset.step);
      input.value = Math.max(0, Math.min(20, next));
    });
  });
});
