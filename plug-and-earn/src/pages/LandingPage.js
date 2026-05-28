const pageContent = {
  fleet: {
    modeClass: "fleet-mode",
    label: "FOR FLEET OPERATORS",
    title: `Turn parked EV fleets into <span>revenue.</span>`,
    subtitle:
      "Offer your available battery capacity to the grid and earn money while maintaining your operations. Plug&Earn handles forecasting, matching and settlement.",
    primaryCta: "Calculate earnings",
    primaryHref: "#/fleet-calculator",
    secondaryCta: "Book a demo",
    imageClass: "fleet-image",
    trustTitle: "Trusted by leading fleets",
    logos: ["DB Schenker", "Hermes", "Coca-Cola", "DPD", "REWE"],
    features: [
      {
        icon: "↗",
        title: "Maximize revenue",
        text: "Earn with every available kWh delivered to the grid.",
      },
      {
        icon: "🛡",
        title: "Battery protected",
        text: "Reserve SOC and degradation limits protect your vehicles.",
      },
      {
        icon: "⏱",
        title: "Zero operational effort",
        text: "We optimize, operate and handle settlement.",
      },
    ],
    stats: [
      { value: "1.4M+", label: "EVs on platform" },
      { value: "€18.5M+", label: "Paid to fleet operators" },
      { value: "18.7 t", label: "CO₂ savings generated" },
      { value: "120+", label: "Fleet partners" },
    ],
    steps: [
      {
        title: "You connect your fleet",
        text: "We integrate your vehicles and chargers securely.",
      },
      {
        title: "We optimize & trade",
        text: "Our AI finds the most valuable grid opportunities.",
      },
      {
        title: "Energy flows",
        text: "Your batteries charge or discharge when it pays off.",
      },
      {
        title: "You earn",
        text: "Get paid for every kWh delivered to the grid.",
      },
    ],
  },

  grid: {
    modeClass: "grid-mode",
    label: "FOR ENERGY BUYERS",
    title: `Access reliable flexibility when the <span>grid needs it.</span>`,
    subtitle:
      "Source verified EV battery capacity from commercial fleets. Flexible, scalable and measurable FCR capacity by region and time window.",
    primaryCta: "View available capacity",
    primaryHref: "#/grid-marketplace",
    secondaryCta: "Book a demo",
    imageClass: "grid-image",
    trustTitle: "Trusted by leading energy companies",
    logos: ["E.ON", "RWE", "Mainova", "TenneT", "LEW"],
    features: [
      {
        icon: "✓",
        title: "Verified capacity",
        text: "All fleets are vetted and continuously monitored.",
      },
      {
        icon: "⌖",
        title: "Where & when you need it",
        text: "Granular availability by region and time window.",
      },
      {
        icon: "▥",
        title: "Reliable & measurable",
        text: "Transparent reporting and reliability scoring.",
      },
    ],
    stats: [
      { value: "2.1 GW", label: "Available capacity" },
      { value: "8", label: "Countries covered" },
      { value: "24/7", label: "Real-time availability" },
      { value: "92%", label: "Avg. reliability score" },
    ],
    steps: [
      {
        title: "Find capacity",
        text: "Search available flexibility by region and time.",
      },
      {
        title: "Book & activate",
        text: "Reserve capacity and activate in a few clicks.",
      },
      {
        title: "We deliver",
        text: "Capacity is delivered when the grid needs it.",
      },
      {
        title: "You benefit",
        text: "Improve grid stability and achieve energy goals.",
      },
    ],
  },
};

function renderFeatures(features) {
  return features
    .map(
      (item) => `
        <article class="feature-card">
          <div class="feature-icon">${item.icon}</div>
          <div>
            <h3>${item.title}</h3>
            <p>${item.text}</p>
          </div>
        </article>
      `
    )
    .join("");
}

function renderStats(stats) {
  return stats
    .map(
      (item) => `
        <div class="stat-item">
          <strong>${item.value}</strong>
          <span>${item.label}</span>
        </div>
      `
    )
    .join("");
}

function renderSteps(steps) {
  return steps
    .map(
      (item, index) => `
        <article class="step-card">
          <div class="step-icon">
            <span>${index + 1}</span>
          </div>
          <h3>${item.title}</h3>
          <p>${item.text}</p>
        </article>
      `
    )
    .join("");
}

function renderLogos(logos) {
  return logos.map((logo) => `<span>${logo}</span>`).join("");
}

export function LandingPage(mode = "fleet") {
  const content = pageContent[mode];

  return `
    <main class="landing-page ${content.modeClass}" data-mode="${mode}">
      <header class="site-header">
        <a class="brand" href="#">
          <strong>Plug<span>&</span>Earn</strong>
          <small>V2G MARKETPLACE</small>
        </a>

        <nav class="nav-links">
          <a href="#how-it-works">How it works</a>
          <a href="#solutions">Solutions</a>
          <a href="#pricing">Pricing</a>
          <a href="#resources">Resources</a>
        </nav>

        <div class="nav-actions">
          <a class="login-btn" href="#/login">Log in</a>
          <a class="signup-btn" href="#/login">Sign up</a>
        </div>
      </header>

      <section class="mode-switch">
        <button id="fleet-tab" class="switch-btn ${mode === "fleet" ? "active" : ""}" data-mode="fleet">
          <span>▱</span>
          I operate EV fleets
        </button>

        <button id="grid-tab" class="switch-btn ${mode === "grid" ? "active" : ""}" data-mode="grid">
          <span>▥</span>
          I buy grid flexibility
        </button>
      </section>

      <section class="hero-section ${content.imageClass}">
        <div class="hero-copy">
          <p class="audience-label">${content.label}</p>

          <h1>${content.title}</h1>

          <p class="hero-subtitle">
            ${content.subtitle}
          </p>

          <div class="hero-actions">
            <a id="primary-cta" class="primary-cta" href="${content.primaryHref}">
              ${content.primaryCta}
              <span>→</span>
            </a>

            <a class="secondary-cta" href="#/login">
              ${content.secondaryCta}
            </a>
          </div>
        </div>

        <div class="hero-background-card">
          <div class="city-fade"></div>
          <div class="energy-line"></div>
        </div>
      </section>

      <section class="feature-row">
        ${renderFeatures(content.features)}
      </section>

      <section class="stats-panel">
        ${renderStats(content.stats)}
      </section>

      <section id="how-it-works" class="how-section">
        <div class="section-heading">
          <h2>How it works</h2>
        </div>

        <div class="steps-grid">
          ${renderSteps(content.steps)}
        </div>
      </section>

      <section class="logo-section">
        <p>${content.trustTitle}</p>
        <div class="logo-row">
          ${renderLogos(content.logos)}
        </div>
      </section>
    </main>
  `;
}

export { pageContent };