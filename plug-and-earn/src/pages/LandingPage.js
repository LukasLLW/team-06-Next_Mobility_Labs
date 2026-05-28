export function LandingPage() {
  return `
    <main class="landing-page fleet-mode">
      <header class="site-header">
        <a href="#" class="brand">
          <strong>Plug<span>&</span>Earn</strong>
          <small>V2G MARKETPLACE</small>
        </a>

        <nav class="main-nav">
          <a href="#how-it-works">How it works</a>
          <a href="#solutions">Solutions</a>
          <a href="#pricing">Pricing</a>
          <a href="#resources">Resources</a>
        </nav>

        <div class="header-actions">
          <a href="#/login" class="btn btn-login">Log in</a>
          <a href="#/login" class="btn btn-signup">Sign up</a>
        </div>
      </header>

      <section class="hero-area">
        <div class="segmented-toggle">
          <div class="toggle-slider"></div>

          <button id="fleet-tab" class="toggle-option active" type="button">
            <span class="toggle-icon"></span>
            I operate EV fleets
          </button>

          <button id="grid-tab" class="toggle-option" type="button">
            <span class="toggle-icon"></span>
            I buy grid flexibility
          </button>
        </div>

        <section class="hero">
          <div class="hero-content">
            <p id="hero-label" class="hero-label">FOR FLEET OPERATORS</p>

            <h1 id="hero-title">
              Turn parked EV fleets<br />
              into <span>revenue.</span>
            </h1>

            <p id="hero-text" class="hero-text">
              Offer your available battery capacity to the grid
              and earn money while maintaining your operations.
              We handle the rest.
            </p>

            <div class="hero-buttons">
              <a id="hero-primary" href="#/fleet-calculator" class="hero-primary">
                Calculate earnings <span>→</span>
              </a>

              <a href="#/login" class="hero-secondary">
                Book a demo
              </a>
            </div>
          </div>

          <div class="hero-image-wrap">
            <div class="hero-image fleet-image active"></div>
            <div class="hero-image grid-image"></div>
            <div class="image-fade"></div>
          </div>
        </section>
      </section>
    </main>
  `;
}