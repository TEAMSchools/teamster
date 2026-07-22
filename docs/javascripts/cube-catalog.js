// Enhance the generated "Find a field" table: chips, filter, Measures toggle,
// capped scroll. Runs on Material's document$ so it survives instant-nav.
(function () {
  function classify(text) {
    if (text === "sensitive") return "cube-chip cube-chip--sensitive";
    return "cube-chip"; // domain / kind / type all share the calm chip
  }

  function enhance() {
    const heading = document.getElementById("find-a-field");
    if (!heading) return;
    let table = heading.nextElementSibling;
    while (table && table.tagName !== "TABLE") table = table.nextElementSibling;
    if (!table || table.dataset.cubeEnhanced) return;
    table.dataset.cubeEnhanced = "1";

    // Restyle the backtick code spans in the Details column into chips.
    table.querySelectorAll("tbody tr td:nth-child(2) code").forEach((code) => {
      const span = document.createElement("span");
      span.className = classify(code.textContent);
      span.textContent = code.textContent;
      code.replaceWith(span);
    });

    // Controls: filter box + Measures toggle.
    const controls = document.createElement("div");
    controls.className = "cube-finder-controls";
    const input = document.createElement("input");
    input.type = "search";
    input.placeholder = "Filter fields, tags, or description keywords…";
    const measures = document.createElement("button");
    measures.type = "button";
    measures.className = "cube-finder-measures";
    measures.textContent = "Measures";
    measures.setAttribute("aria-pressed", "false");
    controls.append(input, measures);

    const scroll = document.createElement("div");
    scroll.className = "cube-finder-scroll";
    table.replaceWith(scroll);
    scroll.append(table);
    scroll.parentNode.insertBefore(controls, scroll);

    const rows = Array.from(table.querySelectorAll("tbody tr"));
    let measuresOnly = false;

    function apply() {
      const q = input.value.trim().toLowerCase();
      rows.forEach((row) => {
        const text = row.textContent.toLowerCase();
        const isMeasure = /\bmeasure\b/.test(text);
        const hit = (!q || text.includes(q)) && (!measuresOnly || isMeasure);
        row.hidden = !hit;
      });
    }
    input.addEventListener("input", apply);
    measures.addEventListener("click", () => {
      measuresOnly = !measuresOnly;
      measures.setAttribute("aria-pressed", measuresOnly ? "true" : "false");
      apply();
    });
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(enhance);
  } else {
    document.addEventListener("DOMContentLoaded", enhance);
  }
})();
