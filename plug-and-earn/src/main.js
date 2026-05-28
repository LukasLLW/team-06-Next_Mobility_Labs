import { LandingPage } from "./pages/LandingPage.js";

const app = document.querySelector("#app");

app.innerHTML = LandingPage();

const page = document.querySelector(".landing-page");

const fleetTab = document.querySelector("#fleet-tab");
const gridTab = document.querySelector("#grid-tab");

const heroLabel = document.querySelector("#hero-label");
const heroTitle = document.querySelector("#hero-title");
const heroText = document.querySelector("#hero-text");
const heroPrimary = document.querySelector("#hero-primary");

const fleetImage = document.querySelector(".fleet-image");
const gridImage = document.querySelector(".grid-image");

const content = {
  fleet: {
    label: "FOR FLEET OPERATORS",
    title: `Turn parked EV fleets<br />into <span>revenue.</span>`,
    text:
      "Offer your available battery capacity to the grid and earn money while maintaining your operations. We handle the rest.",
    cta: "Calculate earnings",
    href: "#/fleet-calculator",
  },

  grid: {
    label: "FOR ENERGY BUYERS",
    title: `Access reliable <br />when the grid needs it.`,
    text:
      "Source verified EV battery capacity from commercial fleets. Flexible. Scalable. Sustainable.",
    cta: "View available capacity",
    href: "#/grid-marketplace",
  },
};

function setMode(mode) {
  const data = content[mode];

  page.classList.add("is-changing");

  page.classList.toggle("fleet-mode", mode === "fleet");
  page.classList.toggle("grid-mode", mode === "grid");

  fleetTab.classList.toggle("active", mode === "fleet");
  gridTab.classList.toggle("active", mode === "grid");

  fleetImage.classList.toggle("active", mode === "fleet");
  gridImage.classList.toggle("active", mode === "grid");

  setTimeout(() => {
    heroLabel.textContent = data.label;
    heroTitle.innerHTML = data.title;
    heroText.textContent = data.text;
    heroPrimary.innerHTML = `${data.cta} <span>→</span>`;
    heroPrimary.href = data.href;

    page.classList.remove("is-changing");
  }, 130);
}

fleetTab.addEventListener("click", () => setMode("fleet"));
gridTab.addEventListener("click", () => setMode("grid"));