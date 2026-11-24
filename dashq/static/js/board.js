// The live board. Two libraries do the work:
//  - auto-animate: cards slide in, out and between lines on their own
//  - SortableJS: drag a card to change its place, or drop it in another line
import autoAnimate from "https://cdn.jsdelivr.net/npm/@formkit/auto-animate@0.8.2/index.mjs";

var dragging = false;
var doneLists = new WeakSet();

function setupLists() {
  document.querySelectorAll(".lane-list").forEach(function (list) {
    if (doneLists.has(list)) return;
    doneLists.add(list);
    autoAnimate(list, { duration: 260 });
    Sortable.create(list, {
      group: "lines",                       // cards can move between all lines
      animation: 180,
      forceFallback: true,                  // smooth mouse-based dragging in every browser
      fallbackOnBody: true,
      filter: "button, select, .lane-empty",
      preventOnFilter: false,
      onStart: function () { dragging = true; },
      onEnd: function (event) {
        dragging = false;
        var card = event.item;
        var next = card.nextElementSibling;
        htmx.ajax("POST", "/app/ticket/" + card.dataset.id + "/move", {
          target: "#live",
          swap: "morph:innerHTML",
          values: { line_id: event.to.dataset.line, before_id: next && next.dataset.id ? next.dataset.id : "" },
        });
      },
    });
  });
}

// Skip the 3-second refresh while someone is dragging, typing, or has a form open
document.body.addEventListener("htmx:beforeRequest", function (event) {
  var live = document.getElementById("live");
  if (event.detail.elt !== live) return;
  var typing = live.contains(document.activeElement) && document.activeElement.matches("input, select, textarea");
  if (dragging || typing || live.querySelector("details[open]")) event.preventDefault();
});

document.body.addEventListener("htmx:afterSettle", setupLists);
setupLists();
