import { routes } from "./routes.js";

export function router() {
  const app = document.querySelector("#app");
  const path = window.location.hash || "#/";

  const route = routes[path] || routes["#/"];

  app.innerHTML = route.page();

  if (typeof route.init === "function") {
    route.init();
  }
}