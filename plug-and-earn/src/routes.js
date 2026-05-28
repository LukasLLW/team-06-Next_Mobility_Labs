import { LandingPage, initLandingPage } from "./pages/LandingPage.js";
import { FleetCalculatorPage } from "./pages/fleet/FleetCalculatorPage.js";

export const routes = {
  "#/": {
    page: LandingPage,
    init: initLandingPage,
  },

  "#/fleet-calculator": {
    page: FleetCalculatorPage,
  },
};