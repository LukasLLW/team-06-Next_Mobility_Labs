import { LandingPage, initLandingPage } from "./pages/LandingPage.js";
import {
  FleetCalculatorPage,
  initFleetCalculatorPage,
} from "./pages/fleet/FleetCalculatorPage.js?v=3000";
import { HowItWorksPage } from "./how_it_works.js";

export const routes = {
  "#/": {
    page: LandingPage,
    init: initLandingPage,
  },

  "#/fleet-calculator": {
    page: FleetCalculatorPage,
    init: initFleetCalculatorPage,
  },

  "#/how-it-works": {
    page: HowItWorksPage,
  },

  "#how-it-works": {
    page: HowItWorksPage,
  },
};