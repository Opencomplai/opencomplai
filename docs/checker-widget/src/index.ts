import { mount } from "./ui";

// Auto-mount when the DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => mount());
} else {
  mount();
}

export { mount };
