import { Header } from "./components/common/Header.js";

export function HowItWorksPage() {
  return `
    <main class="algorithm-page fleet-mode">
      ${Header()}

      <section class="algorithm-wrapper">
        <div class="algorithm-title">
          <h1>Our Algorithm</h1>
          <p>From data to optimal decisions</p>
        </div>

        <section class="algorithm-board">
          <div class="algorithm-steps">
            ${StepOne()}
            <div class="flow-arrow">→</div>

            ${StepTwo()}
            <div class="flow-arrow">→</div>

            ${StepThree()}
            <div class="flow-arrow">→</div>

            ${StepFour()}
            <div class="flow-arrow">→</div>

            ${StepFive()}
          </div>

          <div class="optimized-line">
            <div class="line-left"></div>
            <div class="line-check">✓</div>
            <div class="line-right"></div>
          </div>

          <h2 class="strategy-title">Optimized strategy in action</h2>

          <div class="strategy-bar">
            <div class="strategy-item">
              <img src="./assets/icons/car.svg" alt="" />
              <span>Applied to fleet<br />operations</span>
            </div>

            <div class="strategy-separator"></div>

            <div class="strategy-item">
              <div class="strategy-icon">⚡</div>
              <span>Charge & discharge<br />at the right time</span>
            </div>

            <div class="strategy-separator"></div>

            <div class="strategy-item">
              <img src="./assets/icons/euro.svg" alt="" />
              <span>Maximize long-term<br />net revenue</span>
            </div>

            <div class="strategy-separator"></div>

            <div class="strategy-item">
              <img src="./assets/icons/battery.svg" alt="" />
              <span>Minimize battery wear<br />& extend lifetime</span>
            </div>
          </div>
        </section>
      </section>
    </main>
  `;
}

function StepOne() {
  return `
    <article class="algo-step">
      <div class="step-number">1</div>
      <h3>24h market forecast<br />& ideal strategy</h3>

      <div class="algo-card">
        <div class="price-chart">
          <svg viewBox="0 0 320 190">
            <line x1="30" y1="160" x2="292" y2="160" />
            <line x1="30" y1="160" x2="30" y2="28" />
            <polyline points="30,78 48,70 66,84 84,112 102,128 120,104 138,100 156,66 174,62 192,70 210,50 228,32 246,58 264,62 282,76" />
            <circle cx="102" cy="128" r="7" class="blue-dot" />
            <circle cx="228" cy="32" r="7" class="green-dot" />
            <text x="26" y="18">Price</text>
            <text x="26" y="34">€/MWh</text>
            <text x="88" y="154" class="blue-text">Buy low</text>
            <text x="210" y="18" class="green-text">Sell high</text>
            <text x="28" y="184">0h</text>
            <text x="142" y="184">12h</text>
            <text x="260" y="184">24h</text>
          </svg>
        </div>

        <ul class="algo-list">
          <li><span class="down">↓</span> Charge when prices are low</li>
          <li><span class="up">↑</span> Discharge when prices are high</li>
          <li><span class="grid-symbol">▥</span> Based on German grid forecast next 24h</li>
        </ul>
      </div>
    </article>
  `;
}

function StepTwo() {
  return `
    <article class="algo-step">
      <div class="step-number">2</div>
      <h3>Penalty for excessive<br />cycling</h3>

      <div class="algo-card">
        <div class="scale-graphic">
          <div class="coin">€</div>
          <div class="stress">⌁</div>
          <div class="scale-bar"></div>
          <div class="scale-base"></div>
        </div>

        <p>
          The degradation model is too complex to compute in real time.
          We use a practical penalty that charges the optimizer for too much
          back-and-forth charging behavior.
        </p>

        <div class="formula-box">
          penalty = f(cycling intensity)
        </div>
      </div>
    </article>
  `;
}

function StepThree() {
  return `
    <article class="algo-step">
      <div class="step-number">3</div>
      <h3>Optimization with<br />penalty</h3>

      <div class="algo-card">
        <div class="optimization-graphic">
          <svg viewBox="0 0 320 170">
            <line x1="30" y1="140" x2="292" y2="140" />
            <line x1="30" y1="140" x2="30" y2="25" />
            <line x1="292" y1="140" x2="292" y2="25" />
            <path d="M30 138 C90 118, 105 60, 160 58 C215 60, 230 118, 292 138" class="revenue-line" />
            <path d="M30 30 C70 130, 250 130, 292 30" class="penalty-line" />
            <text x="14" y="20" class="green-text">Revenue</text>
            <text x="248" y="20" class="red-text">Cycling stress</text>
          </svg>
        </div>

        <div class="objective-box">
          <strong>Maximize revenue</strong>
          <span>−</span>
          <strong>Penalty for cycling</strong>
        </div>

        <p>
          The optimizer finds the best charging and discharging strategy for
          the next 24 hours while considering battery stress.
        </p>
      </div>
    </article>
  `;
}

function StepFour() {
  return `
    <article class="algo-step">
      <div class="step-number">4</div>
      <h3>Compare with<br />reality</h3>

      <div class="algo-card">
        <div class="compare-chart">
          <svg viewBox="0 0 320 170">
            <path d="M30 60 C55 120, 80 45, 110 72 C145 110, 158 58, 190 92 C225 126, 245 85, 292 96" class="theory-line" />
            <path d="M30 88 C58 92, 70 118, 98 80 C130 60, 150 102, 182 98 C218 112, 234 126, 292 88" class="actual-line" />
            <text x="30" y="25">Battery usage</text>
            <text x="210" y="42">Theoretical</text>
            <text x="210" y="68">Actual</text>
            <line x1="190" y1="38" x2="205" y2="38" class="legend-green" />
            <line x1="190" y1="64" x2="205" y2="64" class="legend-blue" />
          </svg>
        </div>

        <div class="compare-box">
          <div>
            <img src="./assets/icons/grid.svg" alt="" />
            <span>Theoretical</span>
          </div>
          <strong>vs.</strong>
          <div>
            <img src="./assets/icons/battery.svg" alt="" />
            <span>Actual</span>
          </div>
        </div>

        <p>
          We compare the theoretical strategy and cycling intensity with real
          battery usage and observed fleet behavior.
        </p>
      </div>
    </article>
  `;
}

function StepFive() {
  return `
    <article class="algo-step">
      <div class="step-number">5</div>
      <h3>Continuous learning<br />& penalty tuning</h3>

      <div class="algo-card">
        <div class="learning-graphic">
          <div class="learning-ring">
            <div class="brain">☷</div>
          </div>
        </div>

        <ul class="check-list">
          <li>Adjust penalty level</li>
          <li>Improve model accuracy</li>
          <li>Repeat until prediction matches reality</li>
        </ul>

        <p>
          The penalty is adjusted iteratively until theoretical and real results
          align. The optimized strategy is then applied.
        </p>
      </div>
    </article>
  `;
}