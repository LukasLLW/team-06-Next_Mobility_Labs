import { LandingPage } from "./pages/LandingPage.js";
import { LoginPage } from "./pages/LoginPage.js";
import { FleetCalculatorPage } from "./pages/fleet/FleetCalculatorPage.js";
import { FleetDashboardPage } from "./pages/fleet/FleetDashboardPage.js";
import { FleetEarningsDetailPage } from "./pages/fleet/FleetEarningsDetailPage.js";
import { GridMarketplacePage } from "./pages/grid/GridMarketplacePage.js";
import { GridDashboardPage } from "./pages/grid/GridDashboardPage.js";
import { GridBookingDetailPage } from "./pages/grid/GridBookingDetailPage.js";

export const routes = {
  "#/": LandingPage,
  "#/login": LoginPage,

  "#/fleet-calculator": FleetCalculatorPage,
  "#/fleet-dashboard": FleetDashboardPage,
  "#/fleet-earnings": FleetEarningsDetailPage,

  "#/grid-marketplace": GridMarketplacePage,
  "#/grid-dashboard": GridDashboardPage,
  "#/grid-booking": GridBookingDetailPage,
};