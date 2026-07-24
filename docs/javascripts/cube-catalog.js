// Enhance the generated "Find a field" table: chips, filter, Measures toggle,
// capped scroll. Runs on Material's document$ so it survives instant-nav.
(function () {
  function classify(text) {
    if (text === "sensitive") return "cube-chip cube-chip--sensitive";
    return "cube-chip"; // kind / type share the calm chip
  }

  // The first table after the heading. Material wraps tables in a
  // `.md-typeset__scrollwrap` div at runtime, so the table is not always a
  // direct sibling — descend into wrapper elements, and stop at the next
  // heading so we never grab a later section's table.
  function findTable(heading) {
    for (var el = heading.nextElementSibling; el; el = el.nextElementSibling) {
      if (el.tagName === "TABLE") return el;
      if (/^H[1-6]$/.test(el.tagName)) return null;
      if (el.querySelector) {
        var t = el.querySelector("table");
        if (t) return t;
      }
    }
    return null;
  }

  function enhance() {
    const heading = document.getElementById("find-a-field");
    if (!heading) return;
    const table = findTable(heading);
    if (!table || table.dataset.cubeEnhanced) return;
    table.dataset.cubeEnhanced = "1";
    // Tagging the table with a class removes it from Material's
    // `table:not([class])` default styling and its runtime scroll-wrap, so our
    // fixed column widths win and no horizontal scrollbar appears.
    table.classList.add("cube-finder-table");

    // Restyle the backtick code spans in the Tags column (3rd) into chips.
    table.querySelectorAll("tbody tr td:nth-child(3) code").forEach((code) => {
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
    input.placeholder = "Filter fields, views, tags, or description keywords…";
    const measures = document.createElement("button");
    measures.type = "button";
    measures.className = "cube-finder-measures";
    measures.textContent = "Measures";
    measures.setAttribute("aria-pressed", "false");
    controls.append(input, measures);

    // Lift the table out of any Material scroll wrapper into our own capped,
    // vertical-only scroll box, then place the controls above it.
    const host = table.closest(".md-typeset__scrollwrap") || table;
    const scroll = document.createElement("div");
    scroll.className = "cube-finder-scroll";
    host.replaceWith(scroll);
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
