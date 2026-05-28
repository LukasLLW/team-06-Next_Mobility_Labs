import { routes } from "./routes.js";

export function router() {
  const app = document.querySelector("#app");
  const path = window.location.hash || "#/";

  const page = routes[path] || routes["#/"];
  app.innerHTML = page();
}