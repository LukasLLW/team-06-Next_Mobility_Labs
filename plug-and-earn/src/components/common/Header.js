export function Header() {
  return `
    <header class="site-header">
      <a href="#/" class="brand">
        <strong>Plug<span>&</span>Earn</strong>
        <small>V2G MARKETPLACE</small>
      </a>

      <nav class="main-nav">
        <a href="#/how-it-works">How it works</a>
        <a href="#solutions">Solutions</a>
        <a href="#pricing">Pricing</a>
        <a href="#resources">Resources</a>
      </nav>

      <div class="header-actions">
        <a href="#/login" class="btn btn-login">Log in</a>
        <a href="#/login" class="btn btn-signup">Sign up</a>
      </div>
    </header>
  `;
}