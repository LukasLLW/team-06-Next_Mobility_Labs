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
            <div class="flow-arrow"><i class="bi bi-arrow-right"></i></div>

            ${StepTwo()}
            <div class="flow-arrow"><i class="bi bi-arrow-right"></i></div>

            ${StepThree()}
            <div class="flow-arrow"><i class="bi bi-arrow-right"></i></div>

            ${StepFour()}
            <div class="flow-arrow"><i class="bi bi-arrow-right"></i></div>

            ${StepFive()}
          </div>

          <div class="optimized-line">
            <div class="line-left"></div>
            <div class="line-check"><i class="bi bi-check-lg"></i></div>
            <div class="line-right"></div>
          </div>

          <h2 class="strategy-title">Optimized strategy in action</h2>

          <div class="strategy-bar">
            <div class="strategy-item">
              <i class="bi bi-car-front"></i>
              <span>Applied to fleet<br />operations</span>
            </div>

            <div class="strategy-separator"></div>

            <div class="strategy-item">
              <i class="bi bi-lightning-charge"></i>
              <span>Charge & discharge<br />at the right time</span>
            </div>

            <div class="strategy-separator"></div>

            <div class="strategy-item">
              <i class="bi bi-currency-euro"></i>
              <span>Maximize long-term<br />net revenue</span>
            </div>

            <div class="strategy-separator"></div>

            <div class="strategy-item">
              <i class="bi bi-battery-charging"></i>
              <span>Minimize battery wear<br />& extend lifetime</span>
            </div>
          </div>
        </section>
        ${OutlookSection()}
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
          <li><i class="bi bi-arrow-down-short down"></i> Charge when prices are low</li>
          <li><i class="bi bi-arrow-up-short up"></i> Discharge when prices are high</li>
          <li><i class="bi bi-grid-3x3-gap grid-symbol"></i> Based on German grid forecast next 24h</li>
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
          <div class="coin"><i class="bi bi-currency-euro"></i></div>
          <div class="stress"><i class="bi bi-activity"></i></div>
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
          <span><i class="bi bi-dash-lg"></i></span>
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
            <i class="bi bi-cpu"></i>
            <span>Theoretical</span>
          </div>
          <strong>vs.</strong>
          <div>
            <i class="bi bi-battery-full"></i>
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
            <div class="brain"><i class="bi bi-bezier2"></i></div>
          </div>
        </div>

        <ul class="check-list">
          <li><i class="bi bi-sliders"></i> Adjust penalty level</li>
          <li><i class="bi bi-graph-up-arrow"></i> Improve model accuracy</li>
          <li><i class="bi bi-repeat"></i> Repeat until prediction matches reality</li>
        </ul>

        <p>
          The penalty is adjusted iteratively until theoretical and real results
          align. The optimized strategy is then applied.
        </p>
      </div>
    </article>
  `;
}

function OutlookSection() {
  return `
    <section class="outlook-board">
      <div class="outlook-title">
        <h2>Our FTR (Follow The Region) Algorithm</h2>
        <p>Always energy available where it’s needed</p>
      </div>

      <div class="outlook-steps">
        ${OutlookStepOne()}
        <div class="outlook-arrow"><i class="bi bi-arrow-right"></i></div>

        ${OutlookStepTwo()}
        <div class="outlook-arrow"><i class="bi bi-arrow-right"></i></div>

        ${OutlookStepThree()}
        <div class="outlook-arrow"><i class="bi bi-arrow-right"></i></div>

        ${OutlookStepFour()}
        <div class="outlook-arrow"><i class="bi bi-arrow-right"></i></div>

        ${OutlookStepFive()}
        <div class="outlook-arrow"><i class="bi bi-arrow-right"></i></div>

        ${OutlookStepSix()}
      </div>

      <div class="outlook-line">
        <div class="outlook-line-left"></div>
        <div class="outlook-check"><i class="bi bi-check-lg"></i></div>
        <div class="outlook-line-right"></div>
      </div>

      <h3 class="outlook-result-title">
        Result: Energy where it’s needed, when it’s needed
      </h3>

      <div class="outlook-result-bar">
        <div class="outlook-result-item">
          <div class="outlook-result-icon"><i class="bi bi-geo-alt"></i></div>
          <span>High availability in<br />future hotspots</span>
        </div>

        <div class="outlook-result-separator"></div>

        <div class="outlook-result-item">
          <div class="outlook-result-icon"><i class="bi bi-lightning-charge"></i></div>
          <span>More opportunities<br />to generate revenue</span>
        </div>

        <div class="outlook-result-separator"></div>

        <div class="outlook-result-item">
          <i class="bi bi-diagram-3"></i>
          <span>Better reliability for<br />grid & customers</span>
        </div>

        <div class="outlook-result-separator"></div>

        <div class="outlook-result-item">
          <i class="bi bi-currency-euro"></i>
          <span>Higher utilization &<br />fleet profitability</span>
        </div>

        <div class="outlook-result-separator"></div>

        <div class="outlook-result-item">
          <div class="outlook-result-icon green"><i class="bi bi-globe-europe-africa"></i></div>
          <span>More sustainable<br />energy ecosystem</span>
        </div>
      </div>
    </section>
  `;
}

function OutlookStepOne() {
  return `
    <article class="outlook-step">
      <div class="outlook-step-number">1</div>
      <h3>24h demand forecast<br />by region</h3>

      <div class="outlook-card">
        <div class="map-card-title">Predicted energy demand<br />(next 24h)</div>

        <div class="germany-map demand-map">
          <img src="./assets/images/map-placeholder.svg" alt="" />
          <span class="hotspot hotspot-one"></span>
          <span class="hotspot hotspot-two"></span>
          <span class="hotspot hotspot-three"></span>

          <div class="map-scale">
            <span>High</span>
            <div class="scale-gradient red"></div>
            <span>Low</span>
          </div>
        </div>

        <p>
          We forecast energy demand hotspots for the next 24 hours for all relevant regions.
        </p>

        <div class="outlook-note">
          <div class="outlook-note-icon"><i class="bi bi-geo-alt"></i></div>
          <strong>Identify where energy<br />will be needed</strong>
        </div>
      </div>
    </article>
  `;
}

function OutlookStepTwo() {
  return `
    <article class="outlook-step">
      <div class="outlook-step-number">2</div>
      <h3>Ensure local headroom<br />in advance</h3>

      <div class="outlook-card">
        <div class="map-card-title">Fleet state of charge example</div>

        <div class="headroom-map">
          <img src="./assets/images/map-placeholder.svg" alt="" />

          <span class="soc-bubble soc-one">95%</span>
          <span class="soc-bubble soc-two">90%</span>
          <span class="soc-bubble soc-three">85%</span>
          <span class="soc-bubble soc-four">80%</span>
          <span class="soc-bubble soc-five">70%</span>
          <span class="soc-bubble soc-six">60%</span>
          <span class="soc-bubble soc-seven">50%</span>
          <span class="soc-bubble soc-eight">30%</span>

          <div class="headroom-legend">
            <span>Low headroom</span>
            <div></div>
            <span>High headroom</span>
          </div>
        </div>

        <p>
          We ensure that vehicles in expected hotspots have enough available capacity in advance.
        </p>

        <div class="outlook-note">
          <i class="bi bi-battery-charging"></i>
          <strong>Keep headroom where<br />it matters</strong>
        </div>
      </div>
    </article>
  `;
}

function OutlookStepThree() {
  return `
    <article class="outlook-step">
      <div class="outlook-step-number">3</div>
      <h3>Calculate headroom<br />value per region</h3>

      <div class="outlook-card">
        <div class="map-card-title">Headroom value<br />(next 24h)</div>

        <div class="germany-map value-map">
          <img src="./assets/images/map-placeholder.svg" alt="" />
          <span class="blue-hotspot blue-one"></span>
          <span class="blue-hotspot blue-two"></span>
          <span class="blue-hotspot blue-three"></span>

          <div class="map-scale">
            <span>High<br />value</span>
            <div class="scale-gradient blue"></div>
            <span>Low<br />value</span>
          </div>
        </div>

        <p>
          We calculate a regional “headroom value” based on forecasted shortages and the ability to respond.
        </p>

        <div class="outlook-note">
          <div class="outlook-note-icon"><i class="bi bi-activity"></i></div>
          <strong>Quantify flexibility<br />value by location</strong>
        </div>
      </div>
    </article>
  `;
}

function OutlookStepFour() {
  return `
    <article class="outlook-step">
      <div class="outlook-step-number">4</div>
      <h3>Add FTR value to<br />optimization</h3>

      <div class="outlook-card">
        <div class="map-card-title">Optimization objective</div>

        <div class="objective-row">
          <div class="objective-circle green"><i class="bi bi-currency-euro"></i></div>
          <span>+</span>
          <div class="objective-circle blue"><i class="bi bi-geo-alt"></i></div>
          <span>=</span>
          <div class="objective-circle purple"><i class="bi bi-activity"></i></div>
        </div>

        <div class="objective-labels">
          <span>Revenue<br />(energy)</span>
          <span>FTR value<br />(headroom)</span>
          <span>Total<br />objective</span>
        </div>

        <p>
          The FTR value is added to the standard revenue optimization to guide charging and discharging decisions.
        </p>

        <div class="outlook-note">
          <div class="outlook-note-icon"><i class="bi bi-plus-circle"></i></div>
          <strong>Smarter decisions<br />with future grid needs</strong>
        </div>
      </div>
    </article>
  `;
}

function OutlookStepFive() {
  return `
    <article class="outlook-step">
      <div class="outlook-step-number">5</div>
      <h3>Execute & keep energy<br />ready in hotspots</h3>

      <div class="outlook-card">
        <div class="map-card-title">Energy available<br />when needed</div>

        <div class="germany-map ready-map">
          <img src="./assets/images/map-placeholder.svg" alt="" />
          <span class="battery-marker marker-one"><i class="bi bi-battery-full"></i></span>
          <span class="battery-marker marker-two"><i class="bi bi-battery-full"></i></span>
          <span class="battery-marker marker-three"><i class="bi bi-battery-full"></i></span>
          <span class="battery-marker marker-four"><i class="bi bi-battery-full"></i></span>
          <span class="blue-hotspot blue-one"></span>
          <span class="blue-hotspot blue-two"></span>
        </div>

        <p>
          The fleet is positioned with enough available energy in high-value regions before demand peaks occur.
        </p>

        <div class="outlook-note">
          <div class="outlook-note-icon"><i class="bi bi-lightning"></i></div>
          <strong>Be ready when the<br />market needs you</strong>
        </div>
      </div>
    </article>
  `;
}

function OutlookStepSix() {
  return `
    <article class="outlook-step">
      <div class="outlook-step-number">6</div>
      <h3>Adapt & improve<br />continuously</h3>

      <div class="outlook-card">
        <div class="outlook-learning">
          <div class="outlook-learning-ring">
            <div class="outlook-brain"><i class="bi bi-bezier2"></i></div>
          </div>
        </div>

        <ul class="outlook-check-list">
          <li><i class="bi bi-arrow-left-right"></i> Compare forecast vs. reality</li>
          <li><i class="bi bi-calculator"></i> Improve headroom value calculation</li>
          <li><i class="bi bi-arrow-repeat"></i> Continuously refine FTR strategy</li>
        </ul>

        <div class="outlook-note">
          <div class="outlook-note-icon"><i class="bi bi-shield-check"></i></div>
          <strong>Learn, adapt,<br />outperform</strong>
        </div>
      </div>
    </article>
  `;
}