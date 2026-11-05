// biome-ignore lint/suspicious/noRedundantUseStrict: Preserve strict mode for classic browser scripts.
"use strict";

// Shared page behavior. Avoid introducing fake authentication state.
document.querySelectorAll(".nav-links a").forEach((link) => {
  if (link.getAttribute("href") === location.pathname.split("/").pop()) {
    link.classList.add("active");
    link.setAttribute("aria-current", "page");
  }
});
