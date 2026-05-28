import { LandingPage } from "./pages/LandingPage.js";

const app = document.querySelector("#app");

let activeMode = "fleet";

function render() {
  app.innerHTML = LandingPage(activeMode);
  bindEvents();
}

function bindEvents() {
  const fleetButton = document.querySelector("#fleet-tab");
  const gridButton = document.querySelector("#grid-tab");

  fleetButton.addEventListener("click", () => {
    activeMode = "fleet";
    render();
  });

  gridButton.addEventListener("click", () => {
    activeMode = "grid";
    render();
  });
}

render();