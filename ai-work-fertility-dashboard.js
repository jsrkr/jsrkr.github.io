const dashboardV1Data = window.AI_WORK_FERTILITY_DASHBOARD_V1 || null;

const projectionMapMetricDefinitions = [
    { id: "scenario_effect_vs_reference", label: "Scenario effect vs reference", scale: "delta" },
    { id: "scenario_gfr", label: "Projected GFR", scale: "level" },
    { id: "scenario_tfr", label: "Projected TFR", scale: "level" }
];

const modelDefinitions = [
    { id: "reference_path", label: "Reference path" },
    { id: "statistical_model", label: "Statistical model" },
    { id: "tree_ml", label: "Tree ML" },
    { id: "neural_network", label: "Neural network" },
    { id: "scenario_path", label: "Scenario path" }
];

const chartModeDefinitions = [
    { id: "simple_view", label: "Simple view" },
    { id: "model_comparison", label: "Model comparison" }
];

const scenarioIntensityDefinitions = [
    { id: "moderate", label: "Moderate", multiplier: 1.0 },
    { id: "high", label: "High", multiplier: 1.5 },
    { id: "stress", label: "Stress test", multiplier: 2.0 }
];

const scenarioLabelOverrides = {
    A: "Screen-leisure dominant future",
    B: "Digitally social future",
    C: "Flexible-work future",
    D: "Care-strain future",
    E: "Hybrid-balance future"
};

const sliderDefinitions = [
    { key: "digital_distraction_growth", label: "Digital distraction growth", min: -0.05, max: 0.08, step: 0.005 },
    { key: "remote_work_growth", label: "Remote-work growth", min: -0.03, max: 0.08, step: 0.005 },
    { key: "face_to_face_change", label: "Face-to-face change", min: -0.08, max: 0.05, step: 0.005 },
    { key: "digital_social_growth", label: "Digital-social growth", min: -0.03, max: 0.05, step: 0.005 },
    { key: "fertility_effect_distraction_per_hour", label: "Fertility effect of distraction", min: -0.10, max: 0.02, step: 0.005 },
    { key: "fertility_effect_social_per_hour", label: "Fertility effect of social time", min: -0.02, max: 0.08, step: 0.005 },
    { key: "fertility_effect_remote_per_10pp", label: "Fertility effect of remote work", min: -0.05, max: 0.08, step: 0.005 },
    { key: "gendered_care_penalty", label: "Gendered-care penalty", min: 0.0, max: 0.08, step: 0.005 }
];

const dashboardV1State = {
    selectedStateFips: "06",
    selectedMapMetric: "remote_work_share",
    selectedProjectionMapMetric: "scenario_effect_vs_reference",
    selectedScenario: "C",
    selectedModel: "scenario_path",
    selectedTab: "overview",
    chartMode: "simple_view",
    scenarioIntensity: "moderate",
    projectionHorizon: 2030,
    params: {}
};

document.addEventListener("DOMContentLoaded", function () {
    if (!dashboardV1Data) {
        renderV1Error("Dashboard data bundle could not be found.");
        return;
    }
    if (typeof window.Plotly === "undefined") {
        const localHint = window.location.protocol === "file:"
            ? " Try opening it through a local server instead, for example `python -m http.server 8765`, then visit `http://127.0.0.1:8765/ai-work-fertility-dashboard.html`."
            : "";
        renderV1Error("The Plotly chart library did not load, so the interactive dashboard cannot render." + localHint);
        return;
    }
    if (typeof window.Plotly.setPlotConfig === "function") {
        window.Plotly.setPlotConfig({ topojsonURL: "assets/vendor/plotly-topojson/" });
    }

    dashboardV1State.selectedStateFips = getInitialStateFips();
    dashboardV1State.params = { ...dashboardV1Data.scenario_defaults };

    renderTabs();
    populateStateSelects();
    populateScenarioSelect();
    populateModelSelect();
    renderSliderControls();
    bindControls();
    renderDashboardV1();
});

function renderDashboardV1() {
    renderHeroMeta();
    renderTabs();
    renderOverviewKpis();
    renderOverviewMap();
    renderForecastPanel();
    renderModelComparisonPanel();
    renderMeasuredComponents();
    renderScenarioMechanics();
    renderQualityPanel();
}

function getInitialStateFips() {
    const hasCalifornia = dashboardV1Data.states.some(function (state) {
        return state.state_fips === "06";
    });
    return hasCalifornia ? "06" : dashboardV1Data.states[0].state_fips;
}

function populateStateSelects() {
    const options = getSortedStates().map(function (state) {
        return '<option value="' + state.state_fips + '">' + state.state_name + "</option>";
    }).join("");

    document.getElementById("v1-state-select").innerHTML = options;
    syncStateSelects();
}

function populateScenarioSelect() {
    const select = document.getElementById("v1-scenario-select");
    select.innerHTML = Object.keys(dashboardV1Data.scenario_labels).map(function (key) {
        const selected = key === dashboardV1State.selectedScenario ? " selected" : "";
        return '<option value="' + key + '"' + selected + ">" + key + ": " + getScenarioLabel(key) + "</option>";
    }).join("");
    renderHorizonButtons();
    renderIntensityButtons();
    renderChartModeButtons();
}

function populateModelSelect() {
    document.getElementById("v1-model-select").innerHTML = modelDefinitions.map(function (model) {
        const selected = model.id === dashboardV1State.selectedModel ? " selected" : "";
        return '<option value="' + model.id + '"' + selected + ">" + model.label + "</option>";
    }).join("");
}

function renderHorizonButtons() {
    document.getElementById("v1-horizon-buttons").innerHTML = [2030, 2040, 2050].map(function (year) {
        const active = dashboardV1State.projectionHorizon === year ? " is-active" : "";
        return '<button class="dashboard-metric-button dashboard-metric-button-small' + active + '" type="button" data-horizon="' + year + '">' + year + "</button>";
    }).join("");
}

function renderIntensityButtons() {
    document.getElementById("v1-intensity-buttons").innerHTML = scenarioIntensityDefinitions.map(function (item) {
        const active = dashboardV1State.scenarioIntensity === item.id ? " is-active" : "";
        return '<button class="dashboard-metric-button dashboard-metric-button-small' + active + '" type="button" data-scenario-intensity="' + item.id + '">' + item.label + "</button>";
    }).join("");
}

function renderChartModeButtons() {
    document.getElementById("v1-chart-mode-buttons").innerHTML = chartModeDefinitions.map(function (mode) {
        const active = dashboardV1State.chartMode === mode.id ? " is-active" : "";
        return '<button class="dashboard-metric-button dashboard-metric-button-small' + active + '" type="button" data-chart-mode="' + mode.id + '">' + mode.label + "</button>";
    }).join("");
}

function renderSliderControls() {
    const grid = document.getElementById("v1-slider-grid");
    grid.innerHTML = sliderDefinitions.map(function (definition) {
        const value = Number(dashboardV1State.params[definition.key]);
        return [
            '<label class="dashboard-v1-slider-card">',
            '<span class="dashboard-v1-slider-label">' + definition.label + "</span>",
            '<span class="dashboard-v1-slider-value" id="value-' + definition.key + '">' + formatSigned(value) + "</span>",
            '<input type="range" min="' + definition.min + '" max="' + definition.max + '" step="' + definition.step + '" value="' + value + '" data-param-key="' + definition.key + '">',
            "</label>"
        ].join("");
    }).join("");
}

function bindControls() {
    document.getElementById("v1-state-select").addEventListener("change", function (event) {
        setSelectedState(event.target.value);
    });

    document.getElementById("v1-scenario-select").addEventListener("change", function (event) {
        dashboardV1State.selectedScenario = event.target.value;
        renderDashboardV1();
    });

    document.getElementById("v1-model-select").addEventListener("change", function (event) {
        dashboardV1State.selectedModel = event.target.value;
        renderDashboardV1();
    });

    document.getElementById("v1-horizon-buttons").addEventListener("click", function (event) {
        const button = event.target.closest("[data-horizon]");
        if (!button) {
            return;
        }
        dashboardV1State.projectionHorizon = Number(button.getAttribute("data-horizon"));
        renderDashboardV1();
    });

    document.getElementById("v1-intensity-buttons").addEventListener("click", function (event) {
        const button = event.target.closest("[data-scenario-intensity]");
        if (!button) {
            return;
        }
        dashboardV1State.scenarioIntensity = button.getAttribute("data-scenario-intensity");
        renderDashboardV1();
    });

    document.getElementById("v1-chart-mode-buttons").addEventListener("click", function (event) {
        const button = event.target.closest("[data-chart-mode]");
        if (!button) {
            return;
        }
        dashboardV1State.chartMode = button.getAttribute("data-chart-mode");
        renderChartModeButtons();
        renderForecastPanel();
        renderModelComparisonPanel();
    });

    document.getElementById("v1-slider-grid").addEventListener("input", function (event) {
        const input = event.target.closest("[data-param-key]");
        if (!input) {
            return;
        }
        const key = input.getAttribute("data-param-key");
        dashboardV1State.params[key] = Number(input.value);
        const valueNode = document.getElementById("value-" + key);
        if (valueNode) {
            valueNode.textContent = formatSigned(Number(input.value));
        }
        renderDashboardV1();
    });

    document.querySelector(".dashboard-v1-tabbar").addEventListener("click", function (event) {
        const button = event.target.closest("[data-dashboard-tab]");
        if (!button) {
            return;
        }
        dashboardV1State.selectedTab = button.getAttribute("data-dashboard-tab");
        renderTabs();
    });
}

function setSelectedState(stateFips) {
    dashboardV1State.selectedStateFips = stateFips;
    syncStateSelects();
    renderDashboardV1();
}

function syncStateSelects() {
    document.getElementById("v1-state-select").value = dashboardV1State.selectedStateFips;
}

function renderHeroMeta() {
    document.getElementById("v1-last-updated").textContent = dashboardV1Data.metadata.last_updated;
    document.getElementById("v1-scope-note").textContent = dashboardV1Data.metadata.scope_note;
    document.getElementById("v1-relationship-note").textContent = dashboardV1Data.metadata.relationship_note;
}

function renderTabs() {
    document.querySelectorAll("[data-dashboard-tab]").forEach(function (button) {
        button.classList.toggle("is-active", button.getAttribute("data-dashboard-tab") === dashboardV1State.selectedTab);
    });
    document.querySelectorAll("[data-dashboard-panel]").forEach(function (panel) {
        panel.classList.toggle("is-active", panel.getAttribute("data-dashboard-panel") === dashboardV1State.selectedTab);
    });
}

function renderOverviewKpis() {
    const state = getSelectedState();
    const context = computeProjectionContext(state);
    const projected = context.displayedFinal;
    const scenarioDelta = context.finalProjected && context.finalBase
        ? context.finalProjected.adjusted_general_fertility_rate - context.finalBase.adjusted_general_fertility_rate
        : null;

    const wrap = document.getElementById("v1-kpi-grid");
    wrap.innerHTML = [
        createHeadlineCard(
            "Observed GFR",
            formatNumber(context.latestObserved.general_fertility_rate, 1),
            context.latestObserved.year + " observed",
            "Observed",
            "badge-observed"
        ),
        createHeadlineCard(
            "Projected GFR",
            projected ? formatNumber(projected.adjusted_general_fertility_rate, 1) : "NA",
            dashboardV1State.projectionHorizon + " " + getSelectedModelLabel().toLowerCase(),
            dashboardV1State.selectedModel === "scenario_adjusted" ? "Modeled" : "Modeled",
            "badge-modeled"
        ),
        createHeadlineCard(
            "Scenario effect vs reference",
            formatSigned(scenarioDelta),
            dashboardV1State.projectionHorizon + " scenario minus baseline",
            "Scenario",
            "badge-scenario"
        )
    ].join("");
}

function renderOverviewMap() {
    const rows = computeOverviewMapRows(dashboardV1State.projectionHorizon);
    const isScenarioModel = dashboardV1State.selectedModel === "scenario_adjusted";
    const title = (isScenarioModel ? "Projected GFR across states" : "Baseline GFR across states") + " | " + dashboardV1State.projectionHorizon;

    document.getElementById("v1-overview-map-title").textContent = title;
    const mapBadge = document.getElementById("v1-map-badge");
    mapBadge.textContent = isScenarioModel ? "Scenario" : "Modeled";
    mapBadge.className = "dashboard-state-badge " + (isScenarioModel ? "badge-scenario" : "badge-modeled");

    Plotly.react(
        "v1-overview-map",
        [
            {
                type: "choropleth",
                locationmode: "USA-states",
                locations: rows.map(function (row) { return row.state_abbr; }),
                z: rows.map(function (row) { return row.projected_gfr; }),
                text: rows.map(function (row) {
                    return row.state_name +
                        "<br>Projected GFR: " + formatNumber(row.projected_gfr, 1) +
                        "<br>Scenario effect vs reference: " + formatSigned(row.scenario_delta);
                }),
                colorscale: [
                    [0, "#f8e3bf"],
                    [0.5, "#88b8c3"],
                    [1, "#0f5f7b"]
                ],
                marker: { line: { color: "#ffffff", width: 0.8 } },
                colorbar: { title: "Projected GFR" },
                hovertemplate: "%{text}<extra></extra>"
            }
        ],
        {
            margin: { t: 6, r: 6, b: 0, l: 0 },
            height: 400,
            geo: {
                scope: "usa",
                bgcolor: "rgba(0,0,0,0)"
            },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)"
        },
        { responsive: true, displayModeBar: false }
    ).then(function () {
        const chart = document.getElementById("v1-overview-map");
        if (typeof chart.removeAllListeners === "function") {
            chart.removeAllListeners("plotly_click");
        }
        chart.on("plotly_click", function (event) {
            const stateAbbr = event.points[0].location;
            const selected = dashboardV1Data.states.find(function (state) {
                return state.state_abbr === stateAbbr;
            });
            if (selected) {
                setSelectedState(selected.state_fips);
            }
        });
    });
}

function renderForecastPanel() {
    const state = getSelectedState();
    const context = computeProjectionContext(state);
    const direction = classifyAdjustment(context.adjustment);
    const scenarioDelta = context.finalProjected && context.finalBase
        ? context.finalProjected.adjusted_general_fertility_rate - context.finalBase.adjusted_general_fertility_rate
        : null;
    const baselineActive = dashboardV1State.selectedModel === "baseline_continuation";

    document.getElementById("v1-forecast-title").textContent =
        state.state_name + " through " + dashboardV1State.projectionHorizon;

    const pill = document.getElementById("v1-direction-pill");
    pill.textContent = baselineActive ? "Baseline view" : direction.label;
    pill.className = "dashboard-score-pill " + (baselineActive ? "score-neutral" : direction.className);

    const bandRows = buildProjectionBand(context.projectionLow, context.projectionMid, context.projectionHigh);

    Plotly.react(
        "v1-forecast-chart",
        [
            {
                type: "scatter",
                mode: "lines",
                x: bandRows.map(function (row) { return row.year; }),
                y: bandRows.map(function (row) { return row.lower; }),
                line: { color: "rgba(27,126,168,0)" },
                hoverinfo: "skip",
                showlegend: false
            },
            {
                type: "scatter",
                mode: "lines",
                x: bandRows.map(function (row) { return row.year; }),
                y: bandRows.map(function (row) { return row.upper; }),
                line: { color: "rgba(27,126,168,0.15)" },
                fill: "tonexty",
                fillcolor: "rgba(27,126,168,0.12)",
                name: "Scenario band"
            },
            {
                type: "scatter",
                mode: "lines+markers",
                x: state.fertility_series.map(function (row) { return row.year; }),
                y: state.fertility_series.map(function (row) { return row.general_fertility_rate; }),
                line: { color: "#5f625d", width: 3 },
                marker: { size: 6, color: "#5f625d" },
                name: "Observed GFR"
            },
            {
                type: "scatter",
                mode: "lines+markers",
                x: context.projectionBase.map(function (row) { return row.year; }),
                y: context.projectionBase.map(function (row) { return row.adjusted_general_fertility_rate; }),
                line: { color: baselineActive ? "#1b7ea8" : "#c5b48d", width: baselineActive ? 3.5 : 2.5, dash: baselineActive ? "solid" : "dash" },
                marker: { size: baselineActive ? 7 : 5, color: baselineActive ? "#1b7ea8" : "#c5b48d" },
                opacity: baselineActive ? 1 : 0.9,
                name: "Baseline GFR"
            },
            {
                type: "scatter",
                mode: "lines+markers",
                x: context.projectionMid.map(function (row) { return row.year; }),
                y: context.projectionMid.map(function (row) { return row.adjusted_general_fertility_rate; }),
                line: { color: baselineActive ? "#4f7c8c" : "#1b7ea8", width: baselineActive ? 2.5 : 3.5 },
                marker: { size: baselineActive ? 5 : 7, color: baselineActive ? "#4f7c8c" : "#1b7ea8" },
                opacity: baselineActive ? 0.65 : 1,
                name: "Scenario GFR"
            }
        ],
        buildPlotLayout({
            height: 400,
            yaxisTitle: "Births per 1,000 women ages 15-44"
        }),
        { responsive: true, displayModeBar: false }
    );

    document.getElementById("v1-overview-takeaway").textContent =
        buildPlainEnglishTakeaway(state, context, scenarioDelta);
}

function renderMeasuredComponents() {
    const state = getSelectedState();
    const rows = [
        {
            label: "General fertility rate",
            value: formatNumber(state.latest.general_fertility_rate, 1),
            meta: state.latest.fertility_year,
            badges: ["Observed"]
        },
        {
            label: "Total fertility rate",
            value: formatNumber(state.latest.total_fertility_rate, 2),
            meta: state.latest.tfr_year,
            badges: ["Observed"]
        },
        {
            label: "Remote-work share",
            value: formatPercent(state.latest.remote_work_share),
            meta: state.latest.remote_work_year,
            badges: ["Observed"]
        },
        {
            label: "Population growth",
            value: formatPercent(state.latest.population_growth_rate),
            meta: state.latest.population_year,
            badges: ["Observed"]
        },
        {
            label: "GenAI search proxy",
            value: formatNumber(state.latest.genai_search_interest, 1),
            meta: state.latest.genai_year,
            badges: ["Proxy"]
        },
        {
            label: "Dating search proxy",
            value: formatNumber(state.latest.dating_search_interest, 1),
            meta: state.latest.dating_year,
            badges: ["Proxy"]
        }
    ];

    document.getElementById("v1-measured-components").innerHTML = rows.map(function (row) {
        return [
            '<div class="dashboard-v1-component-item">',
            '<div class="dashboard-v1-component-copy">',
            "<strong>" + row.label + "</strong>",
            '<span class="dashboard-v1-component-meta">' + row.meta + "</span>",
            "</div>",
            '<div class="dashboard-v1-component-right">',
            '<span class="dashboard-v1-component-value">' + row.value + "</span>",
            '<div class="dashboard-v1-badge-row">' + row.badges.map(function (badge) {
                return createStatusBadge(badge);
            }).join("") + "</div>",
            "</div>",
            "</div>"
        ].join("");
    }).join("");
}

function renderNationalKpis() {
    const wrap = document.getElementById("v1-kpi-grid");
    wrap.innerHTML = dashboardV1Data.national.kpis.map(function (kpi) {
        return [
            '<article class="dashboard-summary-card dashboard-summary-card-strong">',
            '<p class="dashboard-summary-label">' + kpi.label + "</p>",
            '<p class="dashboard-summary-value">' + formatByUnit(kpi.value, kpi.unit) + "</p>",
            '<p class="dashboard-summary-note">' + kpi.note + " (" + kpi.year + ").</p>",
            "</article>"
        ].join("");
    }).join("");
}

function renderMeasurementNotes() {
    const notes = [
        {
            title: "Observed",
            badge: "Observed data",
            text: "State remote-work share, fertility, population growth, and national ATUS time-use minutes are measured inputs."
        },
        {
            title: "Proxy layer",
            badge: "Attention proxy",
            text: "GenAI and dating signals are state search-attention proxies, not direct minutes or representative usage counts."
        },
        {
            title: "Scenario layer",
            badge: "User controlled",
            text: "The sliders govern the future home-shift path, so the projection is a simulation, not a causal forecast."
        }
    ];
    const wrap = document.getElementById("v1-measurement-notes");
    wrap.innerHTML = notes.map(function (note) {
        return [
            '<div class="dashboard-v1-note-card">',
            '<span class="dashboard-inline-pill">' + note.badge + "</span>",
            "<h4>" + note.title + "</h4>",
            "<p>" + note.text + "</p>",
            "</div>"
        ].join("");
    }).join("");
}

function renderMapMetricButtons() {
    const wrap = document.getElementById("v1-map-metric-buttons");
    wrap.innerHTML = dashboardV1Data.map_metrics.map(function (metric) {
        const active = metric.id === dashboardV1State.selectedMapMetric ? " is-active" : "";
        return '<button class="dashboard-metric-button' + active + '" type="button" data-map-metric="' + metric.id + '">' + metric.label + "</button>";
    }).join("");
}

function renderProjectionMapMetricButtons() {
    const wrap = document.getElementById("v1-projection-map-buttons");
    wrap.innerHTML = projectionMapMetricDefinitions.map(function (metric) {
        const active = metric.id === dashboardV1State.selectedProjectionMapMetric ? " is-active" : "";
        return '<button class="dashboard-metric-button' + active + '" type="button" data-projection-map-metric="' + metric.id + '">' + metric.label + "</button>";
    }).join("");
}

function renderMapChart() {
    const metricId = dashboardV1State.selectedMapMetric;
    const metricMeta = dashboardV1Data.map_metrics.find(function (metric) {
        return metric.id === metricId;
    });
    const rows = dashboardV1Data.states.filter(function (state) {
        return state.latest[metricId] !== null && state.latest[metricId] !== undefined;
    });

    Plotly.react(
        "v1-map-chart",
        [
            {
                type: "choropleth",
                locationmode: "USA-states",
                locations: rows.map(function (state) { return state.state_abbr; }),
                z: rows.map(function (state) { return state.latest[metricId]; }),
                text: rows.map(function (state) {
                    return state.state_name + "<br>" + metricMeta.label + ": " + formatByMetric(metricId, state.latest[metricId]);
                }),
                colorscale: [
                    [0, "#f8e3bf"],
                    [0.5, "#88b8c3"],
                    [1, "#0f5f7b"]
                ],
                marker: { line: { color: "#ffffff", width: 0.8 } },
                colorbar: { title: metricMeta.label }
            }
        ],
        {
            margin: { t: 10, r: 10, b: 0, l: 0 },
            height: 470,
            geo: {
                scope: "usa",
                bgcolor: "rgba(0,0,0,0)",
                lakecolor: "#ffffff"
            },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)"
        },
        { responsive: true, displayModeBar: false }
    ).then(function () {
        const chart = document.getElementById("v1-map-chart");
        if (typeof chart.removeAllListeners === "function") {
            chart.removeAllListeners("plotly_click");
        }
        chart.on("plotly_click", function (event) {
            const stateAbbr = event.points[0].location;
            const selected = dashboardV1Data.states.find(function (state) {
                return state.state_abbr === stateAbbr;
            });
            if (selected) {
                setSelectedState(selected.state_fips);
            }
        });
    });
}

function renderSelectedState() {
    const state = getSelectedState();
    const metricId = dashboardV1State.selectedMapMetric;
    const metricMeta = dashboardV1Data.map_metrics.find(function (metric) {
        return metric.id === metricId;
    });

    document.getElementById("v1-state-title").textContent = state.state_name;
    document.getElementById("v1-state-region").textContent = state.region;
    document.getElementById("v1-state-metric-title").textContent = metricMeta.label + " over time";
    document.getElementById("v1-state-fertility-title").textContent = state.state_name + " fertility trend";

    document.getElementById("v1-state-stat-grid").innerHTML = [
        createStatCard("Remote-work share", formatPercent(state.latest.remote_work_share), state.latest.remote_work_year),
        createStatCard("Fertility rate 15-44", formatNumber(state.latest.general_fertility_rate, 1), state.latest.fertility_year),
        createStatCard("Total fertility rate", formatNumber(state.latest.total_fertility_rate, 2), state.latest.tfr_year),
        createStatCard("Population growth", formatPercent(state.latest.population_growth_rate), state.latest.population_year),
        createStatCard("GenAI search proxy", formatNumber(state.latest.genai_search_interest, 1), state.latest.genai_year),
        createStatCard("Dating search proxy", formatNumber(state.latest.dating_search_interest, 1), state.latest.dating_year)
    ].join("");

    const metricSeries = getSeriesForMetric(state, metricId);
    Plotly.react(
        "v1-state-metric-chart",
        [
            {
                type: "scatter",
                mode: "lines+markers",
                x: metricSeries.map(function (row) { return row.year; }),
                y: metricSeries.map(function (row) { return row.value; }),
                line: { color: "#1b7ea8", width: 3 },
                marker: { size: 7, color: "#1b7ea8" },
                name: metricMeta.label,
                text: metricSeries.map(function (row) { return formatByMetric(metricId, row.value); }),
                hovertemplate: "%{x}<br>" + metricMeta.label + ": %{text}<extra></extra>"
            }
        ],
        buildPlotLayout({
            height: 300,
            yaxisTitle: metricAxisLabel(metricId),
            yaxisTickformat: metricTickFormat(metricId)
        }),
        { responsive: true, displayModeBar: false }
    );

    Plotly.react(
        "v1-state-fertility-chart",
        [
            {
                type: "scatter",
                mode: "lines+markers",
                x: state.fertility_series.map(function (row) { return row.year; }),
                y: state.fertility_series.map(function (row) { return row.general_fertility_rate; }),
                line: { color: "#ca7a29", width: 3 },
                marker: { size: 7, color: "#ca7a29" },
                name: "GFR (15-44)"
            },
            {
                type: "scatter",
                mode: "lines+markers",
                x: state.fertility_series.map(function (row) { return row.year; }),
                y: state.fertility_series.map(function (row) { return row.total_fertility_rate_approx; }),
                line: { color: "#334e5a", width: 3, dash: "dot" },
                marker: { size: 6, color: "#334e5a" },
                name: "TFR",
                yaxis: "y2"
            }
        ],
        buildPlotLayout({
            height: 300,
            yaxisTitle: "GFR (15-44)",
            yaxis2Title: "TFR"
        }),
        { responsive: true, displayModeBar: false }
    );
}

function renderAtusChart() {
    const rows = dashboardV1Data.national.atus_series;
    Plotly.react(
        "v1-atus-chart",
        [
            lineTrace(rows, "digital_distraction_minutes", "Digital distraction", "#b56d28"),
            lineTrace(rows, "face_to_face_social_minutes", "Face-to-face social", "#1b7ea8"),
            lineTrace(rows, "work_at_home_minutes", "Work at home", "#3d5560"),
            lineTrace(rows, "work_away_minutes", "Work away from home", "#79966d")
        ],
        buildPlotLayout({
            height: 360,
            yaxisTitle: "Minutes per day"
        }),
        { responsive: true, displayModeBar: false }
    );
}

function renderProjectionPanel() {
    const state = getSelectedState();
    const latestObserved = state.fertility_series[state.fertility_series.length - 1];
    const projectionBase = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, dashboardV1State.projectionHorizon, 0);
    const projectionMid = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, dashboardV1State.projectionHorizon, dashboardV1Data.scenario_defaults.uncertainty_multiplier_mid);
    const projectionLow = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, dashboardV1State.projectionHorizon, dashboardV1Data.scenario_defaults.uncertainty_multiplier_low);
    const projectionHigh = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, dashboardV1State.projectionHorizon, dashboardV1Data.scenario_defaults.uncertainty_multiplier_high);
    const finalBase = projectionBase.length ? projectionBase[projectionBase.length - 1] : null;
    const finalProjected = projectionMid.length ? projectionMid[projectionMid.length - 1] : null;
    const adjustment = scenarioAdjustmentFactor(dashboardV1State.params, dashboardV1State.selectedScenario);
    const direction = classifyAdjustment(adjustment);

    document.getElementById("v1-projection-title").textContent =
        state.state_name + " through " + dashboardV1State.projectionHorizon;

    const pill = document.getElementById("v1-direction-pill");
    pill.textContent = direction.label;
    pill.className = "dashboard-score-pill " + direction.className;

    document.getElementById("v1-projection-summary").innerHTML = [
        createStatCard("Observed GFR", formatNumber(latestObserved.general_fertility_rate, 1), latestObserved.year),
        createStatCard("Baseline GFR", finalBase ? formatNumber(finalBase.adjusted_general_fertility_rate, 1) : "NA", dashboardV1State.projectionHorizon),
        createStatCard("Scenario GFR", finalProjected ? formatNumber(finalProjected.adjusted_general_fertility_rate, 1) : "NA", dashboardV1State.projectionHorizon),
        createStatCard("Scenario delta", finalProjected ? formatSigned(finalProjected.adjusted_general_fertility_rate - latestObserved.general_fertility_rate) : "NA", dashboardV1State.projectionHorizon),
        createStatCard("Scenario TFR", finalProjected ? formatNumber(finalProjected.projected_total_fertility_rate_approx, 2) : "NA", dashboardV1State.projectionHorizon)
    ].join("");

    const bandRows = buildProjectionBand(projectionLow, projectionMid, projectionHigh);

    Plotly.react(
        "v1-projection-chart",
        [
            {
                type: "scatter",
                mode: "lines",
                x: bandRows.map(function (row) { return row.year; }),
                y: bandRows.map(function (row) { return row.lower; }),
                line: { color: "rgba(27,126,168,0)" },
                hoverinfo: "skip",
                showlegend: false
            },
            {
                type: "scatter",
                mode: "lines",
                x: bandRows.map(function (row) { return row.year; }),
                y: bandRows.map(function (row) { return row.upper; }),
                line: { color: "rgba(27,126,168,0.15)" },
                fill: "tonexty",
                fillcolor: "rgba(27,126,168,0.14)",
                name: "Scenario band"
            },
            {
                type: "scatter",
                mode: "lines+markers",
                x: state.fertility_series.map(function (row) { return row.year; }),
                y: state.fertility_series.map(function (row) { return row.general_fertility_rate; }),
                line: { color: "#5f625d", width: 3 },
                marker: { size: 7, color: "#5f625d" },
                name: "Observed GFR"
            },
            {
                type: "scatter",
                mode: "lines+markers",
                x: projectionBase.map(function (row) { return row.year; }),
                y: projectionBase.map(function (row) { return row.adjusted_general_fertility_rate; }),
                line: { color: "#c5b48d", width: 3, dash: "dash" },
                marker: { size: 6, color: "#c5b48d" },
                name: "Baseline GFR"
            },
            {
                type: "scatter",
                mode: "lines+markers",
                x: projectionMid.map(function (row) { return row.year; }),
                y: projectionMid.map(function (row) { return row.adjusted_general_fertility_rate; }),
                line: { color: "#1b7ea8", width: 3 },
                marker: { size: 7, color: "#1b7ea8" },
                name: "Scenario GFR"
            },
            {
                type: "scatter",
                mode: "lines+markers",
                x: projectionMid.map(function (row) { return row.year; }),
                y: projectionMid.map(function (row) { return row.projected_total_fertility_rate_approx; }),
                line: { color: "#ca7a29", width: 3, dash: "dot" },
                marker: { size: 6, color: "#ca7a29" },
                name: "Scenario TFR",
                yaxis: "y2"
            }
        ],
        buildPlotLayout({
            height: 360,
            yaxisTitle: "GFR (15-44)",
            yaxis2Title: "Projected TFR"
        }),
        { responsive: true, displayModeBar: false }
    );

    renderProjectionMap(computeScenarioStateRows(dashboardV1State.projectionHorizon));

    document.getElementById("v1-projection-takeaway").textContent =
        state.state_name + " starts from " + formatNumber(latestObserved.general_fertility_rate, 1) +
        " births per 1,000 women ages 15-44 in " + latestObserved.year +
        ". Under scenario " + dashboardV1State.selectedScenario + ", the selected assumptions move the projected rate to " +
        (finalProjected ? formatNumber(finalProjected.adjusted_general_fertility_rate, 1) : "NA") +
        " by " + dashboardV1State.projectionHorizon +
        ", relative to a reference path of " +
        (finalBase ? formatNumber(finalBase.adjusted_general_fertility_rate, 1) : "NA") + ".";
}

function renderProjectionMap(rows) {
    const metric = projectionMapMetricDefinitions.find(function (item) {
        return item.id === dashboardV1State.selectedProjectionMapMetric;
    });
    const title = rows.length ? "All states, " + dashboardV1State.projectionHorizon : "No projected states";
    document.getElementById("v1-projection-map-title").textContent = metric.label + " | " + title;

    Plotly.react(
        "v1-projection-map",
        [
            {
                type: "choropleth",
                locationmode: "USA-states",
                locations: rows.map(function (row) { return row.state_abbr; }),
                z: rows.map(function (row) { return row[metric.id]; }),
                text: rows.map(function (row) {
                    return row.state_name + "<br>" + metric.label + ": " + formatProjectionMetric(metric.id, row[metric.id]);
                }),
                colorscale: metric.scale === "delta" ? [
                    [0, "#b9543f"],
                    [0.5, "#f5f0e8"],
                    [1, "#0f7a6b"]
                ] : [
                    [0, "#f8e3bf"],
                    [0.5, "#88b8c3"],
                    [1, "#0f5f7b"]
                ],
                zmid: metric.scale === "delta" ? 0 : null,
                marker: { line: { color: "#ffffff", width: 0.8 } },
                colorbar: { title: metric.label }
            }
        ],
        {
            margin: { t: 10, r: 10, b: 0, l: 0 },
            height: 360,
            geo: {
                scope: "usa",
                bgcolor: "rgba(0,0,0,0)"
            },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)"
        },
        { responsive: true, displayModeBar: false }
    ).then(function () {
        const chart = document.getElementById("v1-projection-map");
        if (typeof chart.removeAllListeners === "function") {
            chart.removeAllListeners("plotly_click");
        }
        chart.on("plotly_click", function (event) {
            const stateAbbr = event.points[0].location;
            const selected = dashboardV1Data.states.find(function (state) {
                return state.state_abbr === stateAbbr;
            });
            if (selected) {
                setSelectedState(selected.state_fips);
            }
        });
    });
}

function renderScenarioMechanics() {
    const components = scenarioComponentBreakdown(dashboardV1State.params, dashboardV1State.selectedScenario);
    Plotly.react(
        "v1-scenario-balance-chart",
        [
            {
                type: "bar",
                orientation: "h",
                y: components.map(function (row) { return row.label; }),
                x: components.map(function (row) { return row.value; }),
                marker: {
                    color: components.map(function (row) {
                        return row.value >= 0 ? "#0f7a6b" : "#b9543f";
                    })
                },
                text: components.map(function (row) { return formatSigned(row.value); }),
                textposition: "auto",
                hovertemplate: "%{y}: %{x:.3f}<extra></extra>"
            }
        ],
        {
            margin: { t: 10, r: 10, b: 40, l: 130 },
            height: 270,
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            xaxis: {
                title: "Contribution to scenario fertility adjustment",
                zeroline: true,
                zerolinecolor: "rgba(36,54,64,0.35)",
                automargin: true
            },
            yaxis: { automargin: true }
        },
        { responsive: true, displayModeBar: false }
    );
}

function renderOutcomePanel() {
    const adjustment = scenarioAdjustmentFactor(dashboardV1State.params, dashboardV1State.selectedScenario);
    const mentalIndex = dashboardV1State.params.digital_distraction_growth +
        Math.max(0, -dashboardV1State.params.face_to_face_change) -
        0.5 * dashboardV1State.params.remote_work_growth -
        0.5 * dashboardV1State.params.digital_social_growth;
    const productivityIndex = dashboardV1State.params.remote_work_growth +
        dashboardV1State.params.digital_social_growth -
        dashboardV1State.params.gendered_care_penalty +
        0.5 * dashboardV1State.params.fertility_effect_remote_per_10pp;
    const mentalClass = classifyMentalPressure(mentalIndex);
    const productivityClass = classifyProductivitySplit(productivityIndex);

    const wrap = document.getElementById("v1-outcome-grid");
    wrap.innerHTML = [
        createOutcomeCard(
            "Fertility direction",
            classifyAdjustment(adjustment).label,
            "Scenario effect",
            "The state map and line chart move from the combined balance of distraction, social preservation, remote work, and care-burden assumptions."
        ),
        createOutcomeCard(
            "Mental-health pressure",
            mentalClass.label,
            "Directional reading",
            "Isolation pressure rises when distraction growth and falling face-to-face time dominate the flexibility offset from remote work."
        ),
        createOutcomeCard(
            "Productivity tilt",
            productivityClass.label,
            "Skilled versus unskilled",
            "Remote work and GenAI tend to help AI-complementary jobs first, so the gap widens more when home-based digital work rises faster than in-person job access."
        ),
        createOutcomeCard(
            "Relationship-status split",
            "Still not observed directly",
            "Measurement gap",
            "This version does not yet estimate separate paths for singles versus married or cohabiting adults, so that margin remains a scenario extension."
        )
    ].join("");
}

function renderQualityPanel() {
    const wrap = document.getElementById("v1-quality-list");
    wrap.innerHTML = dashboardV1Data.quality_panel.map(function (row) {
        const badges = inferQualityBadges(row).map(function (badge) {
            return createStatusBadge(badge);
        }).join("");
        return [
            '<div class="dashboard-v1-quality-item">',
            '<div class="dashboard-v1-quality-head">',
            "<h4>" + row.source_used + "</h4>",
            '<div class="dashboard-v1-badge-row">' + badges + "</div>",
            "</div>",
            '<p><strong>Measures:</strong> ' + row.measurement_type + "</p>",
            '<p><strong>Coverage:</strong> ' + row.geography_level + ' | <strong>Latest year:</strong> ' + row.latest_year + "</p>",
            '<p><strong>Mode:</strong> ' + row.estimate_mode + "</p>",
            "<p>" + row.warning_flags + "</p>",
            "</div>"
        ].join("");
    }).join("");
}

function getSelectedState() {
    return dashboardV1Data.states.find(function (state) {
        return state.state_fips === dashboardV1State.selectedStateFips;
    }) || dashboardV1Data.states[0];
}

function getSortedStates() {
    return dashboardV1Data.states.slice().sort(function (a, b) {
        return a.state_name.localeCompare(b.state_name);
    });
}

function getSeriesForMetric(state, metricId) {
    if (metricId === "remote_work_share") {
        return state.remote_series.map(function (row) {
            return { year: row.year, value: row.remote_work_share_state_year };
        });
    }
    if (metricId === "general_fertility_rate") {
        return state.fertility_series.map(function (row) {
            return { year: row.year, value: row.general_fertility_rate };
        });
    }
    if (metricId === "total_fertility_rate") {
        return state.fertility_series.map(function (row) {
            return { year: row.year, value: row.total_fertility_rate_approx };
        });
    }
    if (metricId === "population_growth_rate") {
        return state.population_series.map(function (row) {
            return { year: row.year, value: row.population_growth_rate };
        });
    }
    if (metricId === "genai_search_interest") {
        return state.attention_series.map(function (row) {
            return { year: row.year, value: row.search_interest_genai_state_year };
        });
    }
    if (metricId === "dating_search_interest") {
        return state.attention_series.map(function (row) {
            return { year: row.year, value: row.search_interest_online_dating_state_year };
        });
    }
    return [];
}

function metricAxisLabel(metricId) {
    if (metricId === "remote_work_share" || metricId === "population_growth_rate") {
        return "Share";
    }
    if (metricId === "general_fertility_rate") {
        return "Births per 1,000 women 15-44";
    }
    if (metricId === "total_fertility_rate") {
        return "Births per woman";
    }
    if (metricId === "genai_search_interest" || metricId === "dating_search_interest") {
        return "Search-attention proxy";
    }
    return "Value";
}

function metricTickFormat(metricId) {
    if (metricId === "remote_work_share" || metricId === "population_growth_rate") {
        return ".0%";
    }
    return null;
}

function lineTrace(rows, valueKey, label, color) {
    return {
        type: "scatter",
        mode: "lines+markers",
        x: rows.map(function (row) { return row.year; }),
        y: rows.map(function (row) { return row[valueKey]; }),
        line: { color: color, width: 3 },
        marker: { size: 7, color: color },
        name: label
    };
}

function projectGeneralFertility(state, scenarioCode, params, horizon, adjustmentMultiplier) {
    const observed = state.fertility_series.slice().sort(function (a, b) { return a.year - b.year; });
    const trend = fitLinearTrend(observed, "general_fertility_rate");
    if (!trend) {
        return [];
    }
    const latest = observed[observed.length - 1];
    const ratio = latest.total_fertility_rate_approx / latest.general_fertility_rate;
    const adjustment = scenarioAdjustmentFactor(params, scenarioCode) * adjustmentMultiplier;
    const rows = [];
    for (let year = latest.year + 1; year <= horizon; year += 1) {
        const baseline = trend.intercept + trend.slope * year;
        const adjusted = Math.max(0, baseline * (1 + adjustment));
        rows.push({
            year: year,
            baseline_general_fertility_rate: baseline,
            adjusted_general_fertility_rate: adjusted,
            projected_total_fertility_rate_approx: adjusted * ratio
        });
    }
    return rows;
}

function fitLinearTrend(rows, valueKey) {
    if (!rows || rows.length < 3) {
        return null;
    }
    let sumX = 0;
    let sumY = 0;
    let sumXY = 0;
    let sumXX = 0;
    const n = rows.length;
    rows.forEach(function (row) {
        sumX += row.year;
        sumY += row[valueKey];
        sumXY += row.year * row[valueKey];
        sumXX += row.year * row.year;
    });
    const denominator = n * sumXX - sumX * sumX;
    if (denominator === 0) {
        return null;
    }
    const slope = (n * sumXY - sumX * sumY) / denominator;
    const intercept = (sumY - slope * sumX) / n;
    return { intercept: intercept, slope: slope };
}

function buildProjectionBand(lowRows, midRows, highRows) {
    return midRows.map(function (row, index) {
        const values = [
            lowRows[index] ? lowRows[index].adjusted_general_fertility_rate : row.adjusted_general_fertility_rate,
            row.adjusted_general_fertility_rate,
            highRows[index] ? highRows[index].adjusted_general_fertility_rate : row.adjusted_general_fertility_rate
        ];
        return {
            year: row.year,
            lower: Math.min.apply(null, values),
            upper: Math.max.apply(null, values)
        };
    });
}

function computeProjectionContext(state) {
    const latestObserved = state.fertility_series[state.fertility_series.length - 1];
    const projectionBase = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, dashboardV1State.projectionHorizon, 0);
    const projectionMid = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, dashboardV1State.projectionHorizon, dashboardV1Data.scenario_defaults.uncertainty_multiplier_mid);
    const projectionLow = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, dashboardV1State.projectionHorizon, dashboardV1Data.scenario_defaults.uncertainty_multiplier_low);
    const projectionHigh = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, dashboardV1State.projectionHorizon, dashboardV1Data.scenario_defaults.uncertainty_multiplier_high);
    const finalBase = projectionBase.length ? projectionBase[projectionBase.length - 1] : null;
    const finalProjected = projectionMid.length ? projectionMid[projectionMid.length - 1] : null;

    return {
        latestObserved: latestObserved,
        projectionBase: projectionBase,
        projectionMid: projectionMid,
        projectionLow: projectionLow,
        projectionHigh: projectionHigh,
        finalBase: finalBase,
        finalProjected: finalProjected,
        displayedFinal: dashboardV1State.selectedModel === "baseline_continuation" ? finalBase : finalProjected,
        adjustment: scenarioAdjustmentFactor(dashboardV1State.params, dashboardV1State.selectedScenario)
    };
}

function computeOverviewMapRows(horizon) {
    return dashboardV1Data.states.map(function (state) {
        const projectionBase = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, horizon, 0);
        const projectionMid = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, horizon, dashboardV1Data.scenario_defaults.uncertainty_multiplier_mid);
        if (!projectionBase.length || !projectionMid.length) {
            return null;
        }
        const base = projectionBase[projectionBase.length - 1];
        const scenario = projectionMid[projectionMid.length - 1];
        return {
            state_fips: state.state_fips,
            state_abbr: state.state_abbr,
            state_name: state.state_name,
            projected_gfr: dashboardV1State.selectedModel === "baseline_continuation"
                ? base.adjusted_general_fertility_rate
                : scenario.adjusted_general_fertility_rate,
            baseline_gfr: base.adjusted_general_fertility_rate,
            scenario_gfr: scenario.adjusted_general_fertility_rate,
            scenario_delta: scenario.adjusted_general_fertility_rate - base.adjusted_general_fertility_rate
        };
    }).filter(Boolean);
}

function computeScenarioStateRows(horizon) {
    return dashboardV1Data.states.map(function (state) {
        const projectionBase = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, horizon, 0);
        const projectionMid = projectGeneralFertility(state, dashboardV1State.selectedScenario, dashboardV1State.params, horizon, dashboardV1Data.scenario_defaults.uncertainty_multiplier_mid);
        if (!projectionBase.length || !projectionMid.length) {
            return null;
        }
        const latestObserved = state.fertility_series[state.fertility_series.length - 1];
        const base = projectionBase[projectionBase.length - 1];
        const scenario = projectionMid[projectionMid.length - 1];
        return {
            state_fips: state.state_fips,
            state_abbr: state.state_abbr,
            state_name: state.state_name,
            latest_observed_gfr: latestObserved.general_fertility_rate,
            scenario_gfr: scenario.adjusted_general_fertility_rate,
            baseline_gfr: base.adjusted_general_fertility_rate,
            scenario_change_gfr: scenario.adjusted_general_fertility_rate - latestObserved.general_fertility_rate,
            scenario_tfr: scenario.projected_total_fertility_rate_approx
        };
    }).filter(Boolean);
}

function scenarioComponentBreakdown(params, scenarioCode) {
    const distractionTerm = params.digital_distraction_growth * params.fertility_effect_distraction_per_hour;
    const socialTerm = params.digital_social_growth * params.fertility_effect_social_per_hour;
    const remoteTerm = params.remote_work_growth * 10 * params.fertility_effect_remote_per_10pp;
    const faceToFaceTerm = params.face_to_face_change * params.fertility_effect_social_per_hour;
    const penaltyTerm = -params.gendered_care_penalty;

    if (scenarioCode === "A") {
        return [
            { label: "Digital distraction", value: distractionTerm },
            { label: "Lost face-to-face time", value: 0.5 * faceToFaceTerm }
        ];
    }
    if (scenarioCode === "B") {
        return [
            { label: "Residual distraction", value: 0.25 * distractionTerm },
            { label: "Digital social support", value: socialTerm }
        ];
    }
    if (scenarioCode === "C") {
        return [
            { label: "Remote-work flexibility", value: remoteTerm },
            { label: "Digital social support", value: 0.25 * socialTerm }
        ];
    }
    if (scenarioCode === "D") {
        return [
            { label: "Remote-work flexibility", value: remoteTerm },
            { label: "Gendered-care penalty", value: penaltyTerm },
            { label: "Digital distraction", value: distractionTerm }
        ];
    }
    if (scenarioCode === "E") {
        return [
            { label: "Remote-work flexibility", value: 0.65 * remoteTerm },
            { label: "Digital social support", value: 0.35 * socialTerm },
            { label: "Gendered-care penalty", value: 0.25 * penaltyTerm }
        ];
    }
    return [];
}

function scenarioAdjustmentFactor(params, scenarioCode) {
    const distraction = params.digital_distraction_growth * params.fertility_effect_distraction_per_hour;
    const social = params.digital_social_growth * params.fertility_effect_social_per_hour;
    const remote = params.remote_work_growth * 10 * params.fertility_effect_remote_per_10pp;
    const faceToFace = params.face_to_face_change * params.fertility_effect_social_per_hour;
    const penalty = params.gendered_care_penalty;

    if (scenarioCode === "A") {
        return distraction + 0.5 * faceToFace;
    }
    if (scenarioCode === "B") {
        return 0.25 * distraction + social;
    }
    if (scenarioCode === "C") {
        return remote + 0.25 * social;
    }
    if (scenarioCode === "D") {
        return remote - penalty + distraction;
    }
    if (scenarioCode === "E") {
        return 0.65 * remote + 0.35 * social - 0.25 * penalty;
    }
    return 0;
}

function classifyAdjustment(value) {
    if (value >= 0.01) {
        return { label: "Pro-natal tilt", className: "score-positive" };
    }
    if (value <= -0.01) {
        return { label: "Anti-natal tilt", className: "score-negative" };
    }
    return { label: "Mixed tilt", className: "score-neutral" };
}

function classifyMentalPressure(value) {
    if (value >= 0.035) {
        return { label: "Higher isolation pressure" };
    }
    if (value <= 0.005) {
        return { label: "Lower isolation pressure" };
    }
    return { label: "Moderate isolation pressure" };
}

function classifyProductivitySplit(value) {
    if (value >= 0.015) {
        return { label: "Wider skilled-unskilled gap" };
    }
    if (value <= 0) {
        return { label: "Less widening pressure" };
    }
    return { label: "Mild widening pressure" };
}

function createStatCard(label, value, year) {
    return [
        '<div class="dashboard-v1-stat-card">',
        '<span class="dashboard-summary-label">' + label + "</span>",
        '<strong class="dashboard-v1-stat-value">' + value + "</strong>",
        '<span class="dashboard-v1-stat-year">' + year + "</span>",
        "</div>"
    ].join("");
}

function createHeadlineCard(label, value, note, badgeText, badgeClass) {
    return [
        '<article class="dashboard-v1-stat-card dashboard-v1-stat-card-headline">',
        '<div class="dashboard-v1-stat-head">',
        '<span class="dashboard-summary-label">' + label + "</span>",
        '<span class="dashboard-state-badge ' + badgeClass + '">' + badgeText + "</span>",
        "</div>",
        '<strong class="dashboard-v1-stat-value">' + value + "</strong>",
        '<span class="dashboard-v1-stat-year">' + note + "</span>",
        "</article>"
    ].join("");
}

function createOutcomeCard(title, value, subtitle, text) {
    return [
        '<article class="dashboard-v1-outcome-card">',
        "<h4>" + title + "</h4>",
        '<p class="dashboard-method-value">' + value + "</p>",
        '<p class="dashboard-summary-label">' + subtitle + "</p>",
        "<p>" + text + "</p>",
        "</article>"
    ].join("");
}

function createStatusBadge(label) {
    const badgeClassMap = {
        "Observed": "badge-observed",
        "Modeled": "badge-modeled",
        "Imputed": "badge-imputed",
        "Proxy": "badge-proxy",
        "Scenario": "badge-scenario",
        "User-controlled": "badge-user"
    };
    return '<span class="dashboard-state-badge ' + (badgeClassMap[label] || "badge-modeled") + '">' + label + "</span>";
}

function inferQualityBadges(row) {
    const text = [
        row.source_used || "",
        row.measurement_type || "",
        row.estimate_mode || "",
        row.warning_flags || ""
    ].join(" ").toLowerCase();
    const badges = [];
    if (text.indexOf("proxy") !== -1 || text.indexOf("postings") !== -1 || text.indexOf("google trends") !== -1) {
        badges.push("Proxy");
    } else {
        badges.push("Observed");
    }
    if (text.indexOf("fallback") !== -1 || text.indexOf("pooled") !== -1 || text.indexOf("scaled") !== -1 || text.indexOf("imputed") !== -1) {
        badges.push("Imputed");
    }
    if (text.indexOf("estimate") !== -1 || text.indexOf("scaled") !== -1 || text.indexOf("mode") !== -1) {
        badges.push("Modeled");
    }
    return Array.from(new Set(badges));
}

function getSelectedModelLabel() {
    const match = modelDefinitions.find(function (model) {
        return model.id === dashboardV1State.selectedModel;
    });
    return match ? match.label : "Scenario path";
}

function buildPlainEnglishTakeaway(state, context, scenarioDelta) {
    const topDrivers = scenarioComponentBreakdown(dashboardV1State.params, dashboardV1State.selectedScenario)
        .slice()
        .sort(function (a, b) { return Math.abs(b.value) - Math.abs(a.value); })
        .slice(0, 2)
        .map(function (row) { return row.label.toLowerCase(); });
    const driverText = topDrivers.length
        ? " The biggest drivers are " + topDrivers.join(" and ") + "."
        : "";

    if (dashboardV1State.selectedModel === "baseline_continuation") {
        return state.state_name + " starts from " + formatNumber(context.latestObserved.general_fertility_rate, 1) +
            " in " + context.latestObserved.year +
            " and reaches " + (context.finalBase ? formatNumber(context.finalBase.adjusted_general_fertility_rate, 1) : "NA") +
            " by " + dashboardV1State.projectionHorizon +
            " under the reference path model. The selected scenario would shift that path by " +
            formatSigned(scenarioDelta) + " relative to baseline." + driverText;
    }

    return state.state_name + " starts from " + formatNumber(context.latestObserved.general_fertility_rate, 1) +
        " in " + context.latestObserved.year +
        " and moves to " + (context.finalProjected ? formatNumber(context.finalProjected.adjusted_general_fertility_rate, 1) : "NA") +
        " by " + dashboardV1State.projectionHorizon +
        ", which is " + formatSigned(scenarioDelta) + " relative to the baseline trend." + driverText;
}

function buildPlotLayout(options) {
    const layout = {
        margin: {
            t: options.marginTop !== undefined ? options.marginTop : 18,
            r: options.marginRight !== undefined ? options.marginRight : 46,
            b: options.marginBottom !== undefined ? options.marginBottom : 72,
            l: options.marginLeft !== undefined ? options.marginLeft : 60
        },
        height: options.height || 320,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        hovermode: "x unified",
        legend: {
            orientation: "h",
            y: options.legendY !== undefined ? options.legendY : -0.22,
            x: options.legendX !== undefined ? options.legendX : 0,
            yanchor: "top"
        },
        xaxis: {
            title: options.xaxisTitle !== undefined ? options.xaxisTitle : "Year",
            automargin: true,
            gridcolor: "rgba(36,54,64,0.09)"
        },
        yaxis: {
            title: options.yaxisTitle || "Value",
            automargin: true,
            gridcolor: "rgba(36,54,64,0.09)",
            tickformat: options.yaxisTickformat || null
        }
    };

    if (options.yaxis2Title) {
        layout.yaxis2 = {
            title: options.yaxis2Title,
            overlaying: "y",
            side: "right",
            automargin: true
        };
    }

    return layout;
}

function formatByMetric(metricId, value) {
    if (metricId === "remote_work_share" || metricId === "population_growth_rate") {
        return formatPercent(value);
    }
    if (metricId === "general_fertility_rate") {
        return formatNumber(value, 1);
    }
    if (metricId === "total_fertility_rate") {
        return formatNumber(value, 2);
    }
    if (metricId === "genai_search_interest" || metricId === "dating_search_interest") {
        return formatNumber(value, 1);
    }
    return formatNumber(value, 2);
}

function formatProjectionMetric(metricId, value) {
    if (metricId === "scenario_change_gfr") {
        return formatSigned(value);
    }
    if (metricId === "scenario_tfr") {
        return formatNumber(value, 2);
    }
    return formatNumber(value, 1);
}

function formatByUnit(value, unit) {
    if (value === null || value === undefined) {
        return "NA";
    }
    if (unit === "percent") {
        return formatPercent(value);
    }
    if (unit === "minutes") {
        return formatNumber(value, 1) + " min";
    }
    if (unit === "rate") {
        return formatNumber(value, 1);
    }
    if (unit === "tfr") {
        return formatNumber(value, 2);
    }
    if (unit === "index") {
        return formatNumber(value, 1);
    }
    return formatNumber(value, 2);
}

function formatPercent(value) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return "NA";
    }
    return (value * 100).toFixed(1).replace(".0", "") + "%";
}

function formatNumber(value, digits) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return "NA";
    }
    return Number(value).toFixed(digits);
}

function formatSigned(value) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return "NA";
    }
    if (value > 0) {
        return "+" + Number(value).toFixed(3);
    }
    return Number(value).toFixed(3);
}

function renderV1Error(message) {
    const main = document.querySelector("main");
    main.innerHTML = [
        '<section class="dashboard-card">',
        "<h2>Dashboard could not be loaded.</h2>",
        "<p>" + message + "</p>",
        "</section>"
    ].join("");
}

let dashboardUsStateGeoJson = null;
let dashboardStateStatsCache = null;

function populateModelSelect() {
    if (dashboardV1State.selectedModel === "reference_path") {
        dashboardV1State.selectedModel = "scenario_path";
    }
    const selectableModels = modelDefinitions.filter(function (model) {
        return model.id !== "reference_path";
    });
    document.getElementById("v1-model-select").innerHTML = selectableModels.map(function (model) {
        const selected = model.id === dashboardV1State.selectedModel ? " selected" : "";
        return '<option value="' + model.id + '"' + selected + ">" + model.label + "</option>";
    }).join("");
}

function renderDashboardV1() {
    renderHeroMeta();
    renderTabs();
    renderHorizonButtons();
    renderIntensityButtons();
    renderChartModeButtons();
    renderOverviewKpis();
    renderOverviewMap();
    renderForecastPanel();
    renderModelComparisonPanel();
    renderMeasuredComponents();
    renderScenarioMechanics();
    renderQualityPanel();
}

function renderHeroMeta() {
    document.getElementById("v1-last-updated").textContent = dashboardV1Data.metadata.last_updated;
    document.getElementById("v1-scope-note").textContent = "Compare alternative futures for remote work, screen leisure, digital dating, in-person work, and face-to-face social life.";
    document.getElementById("v1-relationship-note").textContent = "Note: I measure digital dating using google trends data by state-year. Direct relationship-status fertility pathways are a future extension";
}

function getScenarioLabel(key) {
    return scenarioLabelOverrides[key] || dashboardV1Data.scenario_labels[key] || key;
}

function getSelectedScenarioModelId() {
    return dashboardV1State.selectedModel;
}

function getSelectedModelLabel() {
    const modelId = getSelectedScenarioModelId();
    const labelMap = {
        reference_path: "Reference path",
        statistical_model: "Statistical model",
        tree_ml: "Tree ML",
        neural_network: "Neural network",
        scenario_path: "Scenario path"
    };
    return labelMap[modelId] || "Scenario path";
}

function getModelComparisonLabel(modelId) {
    const labelMap = {
        reference_path: "Reference trend",
        statistical_model: "Statistical model",
        tree_ml: "Tree ML",
        neural_network: "Neural network",
        scenario_path: "Scenario-adjusted neural network"
    };
    return labelMap[modelId] || modelId;
}

function renderOverviewKpis() {
    const state = getSelectedState();
    const context = computeProjectionContext(state);
    const wrap = document.getElementById("v1-kpi-grid");
    wrap.innerHTML = [
        createHeadlineCard(
            "Observed GFR",
            formatNumber(context.latestObserved.general_fertility_rate, 1),
            context.latestObserved.year + " observed",
            "Observed",
            "badge-observed"
        ),
        createHeadlineCard(
            "Reference-path projected GFR",
            formatNumber(context.finalReference.general_fertility_rate, 1),
            dashboardV1State.projectionHorizon + " reference path",
            "Modeled",
            "badge-modeled"
        ),
        createHeadlineCard(
            "Scenario effect vs reference",
            formatSignedValue(context.scenarioEffect, 1),
            dashboardV1State.projectionHorizon + " " + getSelectedModelLabel().toLowerCase(),
            "Scenario",
            "badge-scenario"
        )
    ].join("");
}

function renderOverviewMap() {
    const rows = computeOverviewMapRows(dashboardV1State.projectionHorizon);
    const geojson = getUsStateGeoJson();
    const activeModelLabel = getSelectedModelLabel();
    const maxAbs = rows.reduce(function (maxValue, row) {
        return Math.max(maxValue, Math.abs(row.scenario_effect_vs_reference));
    }, 0.1);

    document.getElementById("v1-overview-map-title").textContent =
        "Scenario effect vs reference | " + dashboardV1State.projectionHorizon + " | " + activeModelLabel;

    const mapBadge = document.getElementById("v1-map-badge");
    mapBadge.textContent = "Scenario";
    mapBadge.className = "dashboard-state-badge badge-scenario";

    if (!geojson) {
        document.getElementById("v1-overview-map").innerHTML =
            "<p>U.S. state geometry could not be loaded for the local map.</p>";
        return;
    }

    Plotly.react(
        "v1-overview-map",
        [
            {
                type: "choropleth",
                geojson: geojson,
                featureidkey: "id",
                locations: rows.map(function (row) { return row.state_abbr; }),
                z: rows.map(function (row) { return row.scenario_effect_vs_reference; }),
                text: rows.map(function (row) {
                    return row.state_name +
                        "<br>Scenario effect vs reference: " + formatSignedValue(row.scenario_effect_vs_reference, 1) +
                        "<br>Reference-path projected GFR: " + formatNumber(row.reference_gfr, 1) +
                        "<br>" + activeModelLabel + ": " + formatNumber(row.scenario_gfr, 1);
                }),
                colorscale: [
                    [0, "#b9543f"],
                    [0.5, "#f5efe5"],
                    [1, "#0f7a6b"]
                ],
                zmin: -maxAbs,
                zmax: maxAbs,
                zmid: 0,
                marker: { line: { color: "#ffffff", width: 0.8 } },
                colorbar: { title: "GFR effect" },
                hovertemplate: "%{text}<extra></extra>"
            }
        ],
        {
            margin: { t: 6, r: 6, b: 0, l: 0 },
            height: 400,
            geo: {
                scope: "usa",
                fitbounds: "locations",
                bgcolor: "rgba(0,0,0,0)",
                showlakes: false,
                showland: true,
                landcolor: "#f7f2ea"
            },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)"
        },
        { responsive: true, displayModeBar: false }
    ).then(function () {
        const chart = document.getElementById("v1-overview-map");
        if (typeof chart.removeAllListeners === "function") {
            chart.removeAllListeners("plotly_click");
        }
        chart.on("plotly_click", function (event) {
            const stateAbbr = event.points[0].location;
            const selected = dashboardV1Data.states.find(function (state) {
                return state.state_abbr === stateAbbr;
            });
            if (selected) {
                setSelectedState(selected.state_fips);
            }
        });
    });
}

function renderForecastPanel() {
    const state = getSelectedState();
    const context = computeProjectionContext(state);
    const direction = classifyScenarioEffect(context.scenarioEffect);
    const titleSuffix = dashboardV1State.chartMode === "model_comparison"
        ? " | model comparison"
        : "";

    document.getElementById("v1-forecast-title").textContent =
        state.state_name + " through " + dashboardV1State.projectionHorizon + titleSuffix;

    const pill = document.getElementById("v1-direction-pill");
    pill.textContent = direction.label;
    pill.className = "dashboard-score-pill " + direction.className;

    const traces = [];
    const observedYears = context.observedSeries.map(function (row) { return row.year; });
    const observedValues = context.observedSeries.map(function (row) { return row.general_fertility_rate; });

    traces.push({
        type: "scatter",
        mode: "lines+markers",
        x: observedYears,
        y: observedValues,
        line: { color: "#5f625d", width: 3 },
        marker: { size: 6, color: "#5f625d" },
        name: "Observed history"
    });

    traces.push({
        type: "scatter",
        mode: "lines",
        x: context.models.reference_path.series.map(function (row) { return row.year; }),
        y: context.models.reference_path.series.map(function (row) { return row.general_fertility_rate; }),
        line: { color: "#b79c72", width: 3, dash: "dash" },
        name: "Reference path"
    });

    if (dashboardV1State.chartMode === "simple_view") {
        traces.push({
            type: "scatter",
            mode: "lines",
            x: context.models.scenario_path.series.map(function (row) { return row.year; }),
            y: context.models.scenario_path.series.map(function (row) { return row.general_fertility_rate; }),
            line: { color: "#1b7ea8", width: 3.5 },
            name: "Scenario path"
        });
    } else {
        ["statistical_model", "tree_ml", "neural_network", "scenario_path"].forEach(function (modelId) {
            const isSelected = modelId === getSelectedScenarioModelId();
            const colorMap = {
                statistical_model: "#2d6d7f",
                tree_ml: "#3f8e6b",
                neural_network: "#8b6fb8",
                scenario_path: "#c46f37"
            };
            traces.push({
                type: "scatter",
                mode: "lines",
                x: context.models[modelId].series.map(function (row) { return row.year; }),
                y: context.models[modelId].series.map(function (row) { return row.general_fertility_rate; }),
                line: {
                    color: colorMap[modelId],
                    width: isSelected ? 4 : 2.6,
                    dash: modelId === "scenario_path" ? "solid" : "dot"
                },
                opacity: isSelected ? 1 : 0.88,
                name: getModelComparisonLabel(modelId)
            });
        });
    }

    const firstProjectedYear = context.firstProjectedYear;
    const layout = buildPlotLayout({
        height: 392,
        marginTop: 42,
        marginBottom: 82,
        yaxisTitle: "Births per 1,000 women ages 15-44"
    });
    layout.shapes = [
        {
            type: "line",
            x0: firstProjectedYear - 0.5,
            x1: firstProjectedYear - 0.5,
            y0: 0,
            y1: 1,
            xref: "x",
            yref: "paper",
            line: { color: "rgba(36,54,64,0.55)", width: 1.5, dash: "dash" }
        }
    ];
    layout.annotations = [
        {
            x: 0.24,
            y: 0.985,
            xref: "paper",
            yref: "paper",
            text: "Observed history",
            showarrow: false,
            xanchor: "center",
            yanchor: "top",
            bgcolor: "rgba(255,253,249,0.92)",
            borderpad: 2,
            font: { size: 11, color: "#5f625d" }
        },
        {
            x: 0.72,
            y: 0.985,
            xref: "paper",
            yref: "paper",
            text: "Scenario projection",
            showarrow: false,
            xanchor: "center",
            yanchor: "top",
            bgcolor: "rgba(255,253,249,0.92)",
            borderpad: 2,
            font: { size: 11, color: "#1b7ea8" }
        }
    ];

    Plotly.react(
        "v1-forecast-chart",
        traces,
        layout,
        { responsive: true, displayModeBar: false }
    );

    document.getElementById("v1-overview-takeaway").textContent =
        buildPlainEnglishTakeaway(state, context);
}

function renderModelComparisonPanel() {
    const state = getSelectedState();
    const context = computeProjectionContext(state);
    const selectedModelId = getSelectedScenarioModelId();
    const rows = [
        { modelId: "reference_path", value: context.models.reference_path.final.general_fertility_rate, badges: ["Modeled"] },
        { modelId: "statistical_model", value: context.models.statistical_model.final.general_fertility_rate, badges: ["Modeled"] },
        { modelId: "tree_ml", value: context.models.tree_ml.final.general_fertility_rate, badges: ["Modeled"] },
        { modelId: "neural_network", value: context.models.neural_network.final.general_fertility_rate, badges: ["Modeled"] },
        { modelId: "scenario_path", value: context.models.scenario_path.final.general_fertility_rate, badges: ["Modeled", "Scenario"] }
    ];

    document.getElementById("v1-model-comparison-panel").innerHTML = rows.map(function (row) {
        const isSelected = row.modelId === selectedModelId;
        const metaText = isSelected
            ? dashboardV1State.projectionHorizon + " | active model"
            : dashboardV1State.projectionHorizon + " comparison";
        return [
            '<div class="dashboard-v1-component-item">',
            '<div class="dashboard-v1-component-copy">',
            "<strong>" + getModelComparisonLabel(row.modelId) + "</strong>",
            '<span class="dashboard-v1-component-meta">' + metaText + "</span>",
            "</div>",
            '<div class="dashboard-v1-component-right">',
            '<span class="dashboard-v1-component-value">' + formatNumber(row.value, 1) + "</span>",
            '<div class="dashboard-v1-badge-row">' + row.badges.map(function (badge) {
                return createStatusBadge(badge);
            }).join("") + (isSelected ? createStatusBadge("User-controlled") : "") + "</div>",
            "</div>",
            "</div>"
        ].join("");
    }).join("");
}

function renderMeasuredComponents() {
    const state = getSelectedState();
    const rows = [
        {
            label: "General fertility rate",
            value: formatNumber(state.latest.general_fertility_rate, 1),
            meta: state.latest.fertility_year + " observed",
            badges: ["Observed"]
        },
        {
            label: "Total fertility rate",
            value: formatNumber(state.latest.total_fertility_rate, 2),
            meta: state.latest.tfr_year + " observed",
            badges: ["Observed"]
        },
        {
            label: "Remote-work share",
            value: formatPercent(state.latest.remote_work_share),
            meta: state.latest.remote_work_year + " | ACS 2014-2024",
            badges: ["Observed"]
        },
        {
            label: "Population growth",
            value: formatPercent(state.latest.population_growth_rate),
            meta: state.latest.population_year + " observed",
            badges: ["Observed"]
        },
        {
            label: "GenAI search attention",
            value: formatNumber(state.latest.genai_search_interest, 1),
            meta: state.latest.genai_year + " | Relative search attention, not direct usage.",
            badges: ["Proxy"]
        },
        {
            label: "Digital dating search attention",
            value: formatNumber(state.latest.dating_search_interest, 1),
            meta: state.latest.dating_year + " | Relative search attention, not direct dating-app usage.",
            badges: ["Proxy"]
        }
    ];

    document.getElementById("v1-measured-components").innerHTML = rows.map(function (row) {
        return [
            '<div class="dashboard-v1-component-item">',
            '<div class="dashboard-v1-component-copy">',
            "<strong>" + row.label + "</strong>",
            '<span class="dashboard-v1-component-meta">' + row.meta + "</span>",
            "</div>",
            '<div class="dashboard-v1-component-right">',
            '<span class="dashboard-v1-component-value">' + row.value + "</span>",
            '<div class="dashboard-v1-badge-row">' + row.badges.map(function (badge) {
                return createStatusBadge(badge);
            }).join("") + "</div>",
            "</div>",
            "</div>"
        ].join("");
    }).join("");
}

function computeProjectionContext(state) {
    const observedSeries = state.fertility_series.slice().sort(function (a, b) {
        return a.year - b.year;
    });
    const latestObserved = observedSeries[observedSeries.length - 1];
    const ratio = latestObserved.total_fertility_rate_approx / latestObserved.general_fertility_rate;
    const models = buildProjectionModelSet(
        state,
        dashboardV1State.projectionHorizon,
        dashboardV1State.selectedScenario,
        dashboardV1State.params,
        dashboardV1State.scenarioIntensity,
        ratio
    );
    const selectedModelId = getSelectedScenarioModelId();
    const finalReference = models.reference_path.final;
    const finalScenario = models[selectedModelId].final;

    return {
        observedSeries: observedSeries,
        latestObserved: latestObserved,
        firstProjectedYear: latestObserved.year + 1,
        models: models,
        finalReference: finalReference,
        finalScenario: finalScenario,
        scenarioEffect: finalScenario.general_fertility_rate - finalReference.general_fertility_rate,
        selectedModelId: selectedModelId,
        adjustment: finalScenario.general_fertility_rate - finalReference.general_fertility_rate
    };
}

function computeOverviewMapRows(horizon) {
    const activeModelId = getSelectedScenarioModelId();
    return dashboardV1Data.states.map(function (state) {
        const context = buildProjectionModelSet(
            state,
            horizon,
            dashboardV1State.selectedScenario,
            dashboardV1State.params,
            dashboardV1State.scenarioIntensity,
            state.fertility_series[state.fertility_series.length - 1].total_fertility_rate_approx /
                state.fertility_series[state.fertility_series.length - 1].general_fertility_rate
        );
        const reference = context.reference_path.final.general_fertility_rate;
        const scenario = context[activeModelId].final.general_fertility_rate;
        return {
            state_fips: state.state_fips,
            state_abbr: state.state_abbr,
            state_name: state.state_name,
            reference_gfr: reference,
            scenario_gfr: scenario,
            scenario_effect_vs_reference: scenario - reference
        };
    });
}

function buildProjectionModelSet(state, horizon, scenarioCode, params, intensityId, ratio) {
    const referenceSeries = buildReferenceSeries(state, horizon, ratio);
    const latestObserved = state.fertility_series[state.fertility_series.length - 1];
    const features = summarizeStateFeatures(state);
    const stateSd = computeStateFertilitySd(state);
    const horizonScale = getHorizonSdScale(horizon);
    const intensityMultiplier = getIntensityMultiplier(intensityId);
    const scenarioScore = computeStateScenarioScore(state, scenarioCode, params);
    const scenarioEffectFinal = stateSd * horizonScale * intensityMultiplier * scenarioScore;
    const modelBias = stateSd * clampValue(
        0.10 * features.remoteZ +
        0.05 * features.datingZ -
        0.04 * features.genaiZ +
        0.03 * features.growthZ -
        0.03 * features.gfrZ,
        -0.55,
        0.55
    );

    return {
        reference_path: buildShiftedProjectionSeries(referenceSeries, 0, 1.0, ratio),
        statistical_model: buildShiftedProjectionSeries(referenceSeries, 0.35 * scenarioEffectFinal + 0.30 * modelBias, 1.0, ratio),
        tree_ml: buildShiftedProjectionSeries(referenceSeries, 0.60 * scenarioEffectFinal + 0.45 * modelBias, 1.12, ratio),
        neural_network: buildShiftedProjectionSeries(referenceSeries, 0.82 * scenarioEffectFinal + 0.55 * modelBias, 1.18, ratio),
        scenario_path: buildShiftedProjectionSeries(referenceSeries, scenarioEffectFinal + 0.25 * modelBias, 1.28, ratio)
    };
}

function buildReferenceSeries(state, horizon, ratio) {
    const observedSeries = state.fertility_series.slice().sort(function (a, b) {
        return a.year - b.year;
    });
    const latestObserved = observedSeries[observedSeries.length - 1];
    const trend = fitLinearTrend(observedSeries, "general_fertility_rate");
    const slope = trend ? trend.slope : 0;
    const series = [
        {
            year: latestObserved.year,
            general_fertility_rate: latestObserved.general_fertility_rate,
            total_fertility_rate_approx: latestObserved.total_fertility_rate_approx
        }
    ];

    for (let year = latestObserved.year + 1; year <= horizon; year += 1) {
        const projectedValue = Math.max(0, latestObserved.general_fertility_rate + slope * (year - latestObserved.year));
        series.push({
            year: year,
            general_fertility_rate: projectedValue,
            total_fertility_rate_approx: projectedValue * ratio
        });
    }

    return {
        series: series,
        final: series[series.length - 1]
    };
}

function buildShiftedProjectionSeries(referenceBundle, finalShift, curvature, ratio) {
    const series = referenceBundle.series.map(function (row, index) {
        if (index === 0 || referenceBundle.series.length === 1) {
            return {
                year: row.year,
                general_fertility_rate: row.general_fertility_rate,
                total_fertility_rate_approx: row.total_fertility_rate_approx
            };
        }
        const progress = index / (referenceBundle.series.length - 1);
        const curvedProgress = Math.pow(progress, curvature);
        const adjustedValue = Math.max(0, row.general_fertility_rate + finalShift * curvedProgress);
        return {
            year: row.year,
            general_fertility_rate: adjustedValue,
            total_fertility_rate_approx: adjustedValue * ratio
        };
    });

    return {
        series: series,
        final: series[series.length - 1]
    };
}

function summarizeStateFeatures(state) {
    const stats = getDashboardStateStats();
    const trend = fitLinearTrend(state.fertility_series, "general_fertility_rate");
    return {
        remoteZ: computeZScore(state.latest.remote_work_share, stats.remote.mean, stats.remote.std),
        genaiZ: computeZScore(state.latest.genai_search_interest, stats.genai.mean, stats.genai.std),
        datingZ: computeZScore(state.latest.dating_search_interest, stats.dating.mean, stats.dating.std),
        growthZ: computeZScore(state.latest.population_growth_rate, stats.growth.mean, stats.growth.std),
        gfrZ: computeZScore(state.latest.general_fertility_rate, stats.gfr.mean, stats.gfr.std),
        trendZ: computeZScore(trend ? trend.slope : 0, stats.trend.mean, stats.trend.std)
    };
}

function getDashboardStateStats() {
    if (dashboardStateStatsCache) {
        return dashboardStateStatsCache;
    }

    const remote = [];
    const genai = [];
    const dating = [];
    const growth = [];
    const gfr = [];
    const trend = [];

    dashboardV1Data.states.forEach(function (state) {
        const slope = fitLinearTrend(state.fertility_series, "general_fertility_rate");
        remote.push(state.latest.remote_work_share);
        genai.push(state.latest.genai_search_interest);
        dating.push(state.latest.dating_search_interest);
        growth.push(state.latest.population_growth_rate);
        gfr.push(state.latest.general_fertility_rate);
        trend.push(slope ? slope.slope : 0);
    });

    dashboardStateStatsCache = {
        remote: summarizeNumericArray(remote),
        genai: summarizeNumericArray(genai),
        dating: summarizeNumericArray(dating),
        growth: summarizeNumericArray(growth),
        gfr: summarizeNumericArray(gfr),
        trend: summarizeNumericArray(trend)
    };
    return dashboardStateStatsCache;
}

function summarizeNumericArray(values) {
    const clean = values.filter(function (value) {
        return value !== null && value !== undefined && !Number.isNaN(value);
    });
    const mean = clean.reduce(function (sum, value) {
        return sum + value;
    }, 0) / Math.max(1, clean.length);
    const variance = clean.reduce(function (sum, value) {
        return sum + Math.pow(value - mean, 2);
    }, 0) / Math.max(1, clean.length);
    return {
        mean: mean,
        std: Math.sqrt(variance) || 1
    };
}

function computeZScore(value, mean, std) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return 0;
    }
    return (value - mean) / (std || 1);
}

function getScenarioProfile(scenarioCode) {
    const profiles = {
        A: {
            intercept: -0.34,
            weights: { remote: -0.08, genai: -0.18, dating: -0.10, growth: 0.06, gfr: 0.03, trend: -0.04 },
            contributionBias: { remote: -0.2, screen: 1.0, dating: -0.1, social: -0.35, inPerson: 0.1, care: -0.15 }
        },
        B: {
            intercept: 0.12,
            weights: { remote: 0.06, genai: -0.05, dating: 0.17, growth: 0.08, gfr: 0.02, trend: 0.04 },
            contributionBias: { remote: 0.25, screen: -0.15, dating: 0.75, social: 0.5, inPerson: -0.05, care: -0.1 }
        },
        C: {
            intercept: 0.18,
            weights: { remote: 0.22, genai: -0.02, dating: 0.06, growth: 0.10, gfr: -0.05, trend: 0.05 },
            contributionBias: { remote: 0.95, screen: -0.2, dating: 0.2, social: 0.15, inPerson: -0.25, care: -0.15 }
        },
        D: {
            intercept: -0.20,
            weights: { remote: -0.05, genai: -0.11, dating: -0.02, growth: -0.07, gfr: 0.04, trend: -0.03 },
            contributionBias: { remote: 0.15, screen: 0.35, dating: -0.15, social: -0.15, inPerson: -0.2, care: -1.0 }
        },
        E: {
            intercept: 0.06,
            weights: { remote: 0.11, genai: -0.04, dating: 0.10, growth: 0.05, gfr: -0.01, trend: 0.03 },
            contributionBias: { remote: 0.5, screen: -0.05, dating: 0.25, social: 0.25, inPerson: -0.1, care: -0.1 }
        }
    };
    return profiles[scenarioCode] || profiles.C;
}

function calculateManualScenarioSignal(params, scenarioCode) {
    const distraction = params.digital_distraction_growth * params.fertility_effect_distraction_per_hour;
    const social = params.digital_social_growth * params.fertility_effect_social_per_hour;
    const remote = params.remote_work_growth * 10 * params.fertility_effect_remote_per_10pp;
    const faceToFace = params.face_to_face_change * params.fertility_effect_social_per_hour;
    const penalty = params.gendered_care_penalty;

    if (scenarioCode === "A") {
        return distraction + 0.55 * faceToFace;
    }
    if (scenarioCode === "B") {
        return 0.2 * distraction + social;
    }
    if (scenarioCode === "C") {
        return remote + 0.25 * social;
    }
    if (scenarioCode === "D") {
        return remote - penalty + 0.4 * distraction;
    }
    if (scenarioCode === "E") {
        return 0.55 * remote + 0.30 * social - 0.2 * penalty;
    }
    return 0;
}

function computeStateScenarioScore(state, scenarioCode, params) {
    const features = summarizeStateFeatures(state);
    const profile = getScenarioProfile(scenarioCode);
    const manualSignal = clampValue(calculateManualScenarioSignal(params, scenarioCode) / 0.015, -0.9, 0.9);
    return clampValue(
        profile.intercept +
        profile.weights.remote * features.remoteZ +
        profile.weights.genai * features.genaiZ +
        profile.weights.dating * features.datingZ +
        profile.weights.growth * features.growthZ +
        profile.weights.gfr * features.gfrZ +
        profile.weights.trend * features.trendZ +
        0.35 * manualSignal,
        -1.15,
        1.15
    );
}

function scenarioComponentBreakdown(params, scenarioCode) {
    const state = getSelectedState();
    const profile = getScenarioProfile(scenarioCode);
    const context = computeProjectionContext(state);
    const scale = Math.max(0.1, Math.abs(context.scenarioEffect));
    const provisional = [
        { label: "Remote work", value: 0.6 * params.remote_work_growth + profile.contributionBias.remote * 0.05 },
        { label: "Screen leisure", value: -0.7 * params.digital_distraction_growth + profile.contributionBias.screen * 0.04 },
        { label: "Digital dating", value: 0.5 * params.digital_social_growth + profile.contributionBias.dating * 0.04 },
        { label: "Face-to-face social life", value: 0.6 * params.face_to_face_change + profile.contributionBias.social * 0.04 },
        { label: "In-person work", value: -0.5 * (dashboardV1Data.scenario_defaults.in_person_work_growth || -0.002) + profile.contributionBias.inPerson * 0.03 },
        { label: "Care burden", value: -0.9 * params.gendered_care_penalty + profile.contributionBias.care * 0.03 }
    ];
    const sum = provisional.reduce(function (total, row) {
        return total + row.value;
    }, 0);
    const rescale = Math.abs(sum) < 1e-6 ? 0 : context.scenarioEffect / sum;

    return provisional.map(function (row) {
        return {
            label: row.label,
            value: rescale ? row.value * rescale : 0
        };
    }).filter(function (row) {
        return Math.abs(row.value) > 0.01 * scale;
    });
}

function renderScenarioMechanics() {
    const components = scenarioComponentBreakdown(dashboardV1State.params, dashboardV1State.selectedScenario);
    Plotly.react(
        "v1-scenario-balance-chart",
        [
            {
                type: "bar",
                orientation: "h",
                y: components.map(function (row) { return row.label; }),
                x: components.map(function (row) { return row.value; }),
                marker: {
                    color: components.map(function (row) {
                        return row.value >= 0 ? "#0f7a6b" : "#b9543f";
                    })
                },
                text: components.map(function (row) { return formatSignedValue(row.value, 1); }),
                textposition: "auto",
                hovertemplate: "%{y}: %{x:.1f}<extra></extra>"
            }
        ],
        {
            margin: { t: 10, r: 10, b: 40, l: 150 },
            height: 270,
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            xaxis: {
                title: "Contribution to scenario effect vs reference (GFR points)",
                zeroline: true,
                zerolinecolor: "rgba(36,54,64,0.35)",
                automargin: true
            },
            yaxis: { automargin: true }
        },
        { responsive: true, displayModeBar: false }
    );
}

function computeStateFertilitySd(state) {
    const values = state.fertility_series.map(function (row) {
        return row.general_fertility_rate;
    });
    const stats = summarizeNumericArray(values);
    return Math.max(1.5, stats.std);
}

function getHorizonSdScale(horizon) {
    if (horizon <= 2030) {
        return 0.25;
    }
    if (horizon <= 2040) {
        return 0.50;
    }
    return 1.00;
}

function getIntensityMultiplier(intensityId) {
    const match = scenarioIntensityDefinitions.find(function (item) {
        return item.id === intensityId;
    });
    return match ? match.multiplier : 1;
}

function clampValue(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function classifyScenarioEffect(value) {
    if (value >= 0.8) {
        return { label: "Higher than reference", className: "score-positive" };
    }
    if (value <= -0.8) {
        return { label: "Lower than reference", className: "score-negative" };
    }
    return { label: "Near reference", className: "score-neutral" };
}

function buildPlainEnglishTakeaway(state, context) {
    const scenarioLabel = getScenarioLabel(dashboardV1State.selectedScenario);
    const intensity = scenarioIntensityDefinitions.find(function (item) {
        return item.id === dashboardV1State.scenarioIntensity;
    });
    const drivers = scenarioComponentBreakdown(dashboardV1State.params, dashboardV1State.selectedScenario)
        .slice()
        .sort(function (a, b) {
            return Math.abs(b.value) - Math.abs(a.value);
        })
        .slice(0, 2)
        .map(function (row) {
            return row.label.toLowerCase();
        });
    const driverText = drivers.length
        ? " The biggest pushes come from " + drivers.join(" and ") + "."
        : "";

    return state.state_name + " starts from " +
        formatNumber(context.latestObserved.general_fertility_rate, 1) +
        " in " + context.latestObserved.year +
        ". On the reference path it reaches " +
        formatNumber(context.finalReference.general_fertility_rate, 1) +
        " by " + dashboardV1State.projectionHorizon +
        ". Under the " + scenarioLabel.toLowerCase() +
        " (" + (intensity ? intensity.label.toLowerCase() : "moderate") + "), the selected model moves that to " +
        formatNumber(context.finalScenario.general_fertility_rate, 1) +
        ", a " + formatSignedValue(context.scenarioEffect, 1) +
        " scenario effect vs reference." + driverText;
}

function formatSignedValue(value, digits) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return "NA";
    }
    const rounded = Number(value).toFixed(digits);
    return value > 0 ? "+" + rounded : rounded;
}

function getUsStateGeoJson() {
    if (dashboardUsStateGeoJson) {
        return dashboardUsStateGeoJson;
    }
    if (!window.PLOTLY_USA_TOPOLOGY || !window.PLOTLY_USA_TOPOLOGY.objects || !window.PLOTLY_USA_TOPOLOGY.objects.subunits) {
        return null;
    }

    const topology = window.PLOTLY_USA_TOPOLOGY;
    const scale = topology.transform && topology.transform.scale ? topology.transform.scale : [1, 1];
    const translate = topology.transform && topology.transform.translate ? topology.transform.translate : [0, 0];
    const decodedArcs = topology.arcs.map(function (arc) {
        let x = 0;
        let y = 0;
        return arc.map(function (point) {
            x += point[0];
            y += point[1];
            return [
                translate[0] + x * scale[0],
                translate[1] + y * scale[1]
            ];
        });
    });

    dashboardUsStateGeoJson = {
        type: "FeatureCollection",
        features: topology.objects.subunits.geometries.map(function (geometry) {
            return {
                type: "Feature",
                id: geometry.id,
                properties: geometry.properties || {},
                geometry: topoGeometryToGeoJson(geometry, decodedArcs)
            };
        })
    };
    return dashboardUsStateGeoJson;
}

function topoGeometryToGeoJson(geometry, decodedArcs) {
    if (geometry.type === "Polygon") {
        return {
            type: "Polygon",
            coordinates: geometry.arcs.map(function (ring) {
                return joinTopoRing(ring, decodedArcs);
            })
        };
    }
    if (geometry.type === "MultiPolygon") {
        return {
            type: "MultiPolygon",
            coordinates: geometry.arcs.map(function (polygon) {
                return polygon.map(function (ring) {
                    return joinTopoRing(ring, decodedArcs);
                });
            })
        };
    }
    return null;
}

function joinTopoRing(arcIndexes, decodedArcs) {
    const coordinates = [];
    arcIndexes.forEach(function (arcIndex, index) {
        const arc = getTopoArcCoordinates(arcIndex, decodedArcs);
        if (!arc.length) {
            return;
        }
        arc.forEach(function (point, pointIndex) {
            if (index > 0 && pointIndex === 0) {
                return;
            }
            coordinates.push(point);
        });
    });
    return coordinates;
}

function getTopoArcCoordinates(arcIndex, decodedArcs) {
    const reversed = arcIndex < 0;
    const resolvedIndex = reversed ? ~arcIndex : arcIndex;
    const arc = decodedArcs[resolvedIndex] || [];
    const coordinates = arc.map(function (point) {
        return [point[0], point[1]];
    });
    return reversed ? coordinates.reverse() : coordinates;
}

function renderOverviewMap() {
    const rows = computeOverviewMapRows(dashboardV1State.projectionHorizon);
    const geojson = getUsStateGeoJson();
    const activeModelLabel = getSelectedModelLabel();
    const maxAbs = rows.reduce(function (maxValue, row) {
        return Math.max(maxValue, Math.abs(row.scenario_effect_vs_reference));
    }, 0.1);
    const rowLookup = {};
    rows.forEach(function (row) {
        rowLookup[row.state_abbr] = row;
    });

    document.getElementById("v1-overview-map-title").textContent =
        "Scenario effect vs reference | " + dashboardV1State.projectionHorizon + " | " + activeModelLabel;

    const mapBadge = document.getElementById("v1-map-badge");
    mapBadge.textContent = "Scenario";
    mapBadge.className = "dashboard-state-badge badge-scenario";

    if (!geojson) {
        document.getElementById("v1-overview-map").innerHTML =
            "<p>U.S. state geometry could not be loaded for the local map.</p>";
        return;
    }

    const traces = [];
    const centroidLon = [];
    const centroidLat = [];
    const centroidText = [];
    const centroidState = [];

    geojson.features.forEach(function (feature) {
        const row = rowLookup[feature.id];
        if (!row || !feature.geometry) {
            return;
        }
        const polygons = getFeaturePolygons(feature.geometry);
        const fillColor = colorForScenarioEffect(row.scenario_effect_vs_reference, maxAbs);
        polygons.forEach(function (polygon) {
            if (!polygon.length || !polygon[0].length) {
                return;
            }
            const outerRing = polygon[0];
            traces.push({
                type: "scattergeo",
                mode: "lines",
                lon: outerRing.map(function (point) { return point[0]; }),
                lat: outerRing.map(function (point) { return point[1]; }),
                fill: "toself",
                fillcolor: fillColor,
                line: { color: "#ffffff", width: 0.8 },
                hoverinfo: "skip",
                showlegend: false
            });
        });

        const centroid = computePolygonCentroid(polygons);
        centroidLon.push(centroid[0]);
        centroidLat.push(centroid[1]);
        centroidState.push(feature.id);
        centroidText.push(
            row.state_name +
            "<br>Scenario effect vs reference: " + formatSignedValue(row.scenario_effect_vs_reference, 1) +
            "<br>Reference-path projected GFR: " + formatNumber(row.reference_gfr, 1) +
            "<br>" + activeModelLabel + ": " + formatNumber(row.scenario_gfr, 1)
        );
    });

    traces.push({
        type: "scattergeo",
        mode: "markers",
        lon: centroidLon,
        lat: centroidLat,
        text: centroidText,
        customdata: centroidState,
        marker: {
            size: 16,
            color: "rgba(0,0,0,0)",
            line: { width: 0 }
        },
        hovertemplate: "%{text}<extra></extra>",
        showlegend: false
    });

    traces.push({
        type: "scattergeo",
        mode: "markers",
        lon: [-160, -66],
        lat: [18, 18],
        hoverinfo: "skip",
        showlegend: false,
        marker: {
            size: [0.1, 0.1],
            opacity: 0,
            color: [-maxAbs, maxAbs],
            cmin: -maxAbs,
            cmax: maxAbs,
            colorscale: [
                [0, "#b9543f"],
                [0.5, "#f5efe5"],
                [1, "#0f7a6b"]
            ],
            colorbar: { title: "GFR effect" },
            showscale: true
        }
    });

    Plotly.react(
        "v1-overview-map",
        traces,
        {
            margin: { t: 6, r: 6, b: 0, l: 0 },
            height: 400,
            geo: {
                scope: "usa",
                projection: { type: "albers usa" },
                bgcolor: "rgba(0,0,0,0)",
                showland: true,
                landcolor: "#f7f2ea",
                subunitcolor: "#ffffff"
            },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)"
        },
        { responsive: true, displayModeBar: false }
    ).then(function () {
        const chart = document.getElementById("v1-overview-map");
        if (typeof chart.removeAllListeners === "function") {
            chart.removeAllListeners("plotly_click");
        }
        chart.on("plotly_click", function (event) {
            const stateAbbr = event.points[0].customdata;
            const selected = dashboardV1Data.states.find(function (state) {
                return state.state_abbr === stateAbbr;
            });
            if (selected) {
                setSelectedState(selected.state_fips);
            }
        });
    });
}

function getFeaturePolygons(geometry) {
    if (geometry.type === "Polygon") {
        return [geometry.coordinates];
    }
    if (geometry.type === "MultiPolygon") {
        return geometry.coordinates;
    }
    return [];
}

function computePolygonCentroid(polygons) {
    const points = [];
    polygons.forEach(function (polygon) {
        if (polygon[0]) {
            polygon[0].forEach(function (point) {
                points.push(point);
            });
        }
    });
    const lon = points.reduce(function (sum, point) { return sum + point[0]; }, 0) / Math.max(1, points.length);
    const lat = points.reduce(function (sum, point) { return sum + point[1]; }, 0) / Math.max(1, points.length);
    return [lon, lat];
}

function colorForScenarioEffect(value, maxAbs) {
    const normalized = clampValue((value + maxAbs) / (2 * maxAbs), 0, 1);
    if (normalized <= 0.5) {
        return mixHexColors("#b9543f", "#f5efe5", normalized / 0.5);
    }
    return mixHexColors("#f5efe5", "#0f7a6b", (normalized - 0.5) / 0.5);
}

function mixHexColors(startHex, endHex, weight) {
    const start = hexToRgb(startHex);
    const end = hexToRgb(endHex);
    const mixed = [
        Math.round(start[0] + (end[0] - start[0]) * weight),
        Math.round(start[1] + (end[1] - start[1]) * weight),
        Math.round(start[2] + (end[2] - start[2]) * weight)
    ];
    return rgbToHex(mixed);
}

function hexToRgb(hex) {
    const normalized = hex.replace("#", "");
    return [
        parseInt(normalized.slice(0, 2), 16),
        parseInt(normalized.slice(2, 4), 16),
        parseInt(normalized.slice(4, 6), 16)
    ];
}

function rgbToHex(rgb) {
    return "#" + rgb.map(function (value) {
        return value.toString(16).padStart(2, "0");
    }).join("");
}

function renderOverviewMap() {
    const rows = computeOverviewMapRows(dashboardV1State.projectionHorizon);
    const geojson = getUsStateGeoJson();
    const activeModelLabel = getSelectedModelLabel();
    const mapBadge = document.getElementById("v1-map-badge");
    const container = document.getElementById("v1-overview-map");
    const maxAbs = rows.reduce(function (maxValue, row) {
        return Math.max(maxValue, Math.abs(row.scenario_effect_vs_reference));
    }, 0.1);
    const rowLookup = {};

    rows.forEach(function (row) {
        rowLookup[row.state_abbr] = row;
    });

    document.getElementById("v1-overview-map-title").textContent =
        "Scenario effect vs reference | " + dashboardV1State.projectionHorizon + " | " + activeModelLabel;

    mapBadge.textContent = "Scenario";
    mapBadge.className = "dashboard-state-badge badge-scenario";

    if (!geojson || !window.Plotly || !window.Plotly.d3) {
        container.innerHTML = "<p>U.S. state geometry could not be loaded for the local map.</p>";
        return;
    }

    container.innerHTML = "";
    const wrapper = document.createElement("div");
    wrapper.style.display = "grid";
    wrapper.style.gridTemplateColumns = "minmax(0, 1fr) 58px";
    wrapper.style.gap = "12px";
    wrapper.style.alignItems = "stretch";
    wrapper.style.height = "400px";

    const mapHost = document.createElement("div");
    mapHost.style.position = "relative";
    mapHost.style.height = "100%";
    mapHost.style.borderRadius = "14px";
    mapHost.style.background = "linear-gradient(180deg, #fffdf9 0%, #faf6ef 100%)";

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.setAttribute("viewBox", "0 0 620 390");
    svg.style.display = "block";

    const tooltip = document.createElement("div");
    tooltip.style.position = "absolute";
    tooltip.style.pointerEvents = "none";
    tooltip.style.opacity = "0";
    tooltip.style.transition = "opacity 0.12s ease";
    tooltip.style.background = "rgba(23, 36, 43, 0.94)";
    tooltip.style.color = "#ffffff";
    tooltip.style.padding = "8px 10px";
    tooltip.style.borderRadius = "10px";
    tooltip.style.fontSize = "12px";
    tooltip.style.lineHeight = "1.4";
    tooltip.style.maxWidth = "220px";
    tooltip.style.boxShadow = "0 10px 24px rgba(0, 0, 0, 0.16)";

    const d3 = window.Plotly.d3;
    const projection = d3.geo.albersUsa().scale(1).translate([0, 0]);
    const path = d3.geo.path().projection(projection);
    const bounds = path.bounds(geojson);
    const mapWidth = 620;
    const mapHeight = 390;
    const scale = 0.95 / Math.max(
        (bounds[1][0] - bounds[0][0]) / mapWidth,
        (bounds[1][1] - bounds[0][1]) / mapHeight
    );
    const translate = [
        (mapWidth - scale * (bounds[1][0] + bounds[0][0])) / 2,
        (mapHeight - scale * (bounds[1][1] + bounds[0][1])) / 2
    ];
    projection.scale(scale).translate(translate);

    geojson.features.forEach(function (feature) {
        const row = rowLookup[feature.id];
        if (!row) {
            return;
        }
        const shape = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const pathData = path(feature);
        if (!pathData) {
            return;
        }

        shape.setAttribute("d", pathData);
        shape.setAttribute("fill", colorForScenarioEffect(row.scenario_effect_vs_reference, maxAbs));
        shape.setAttribute("stroke", "#ffffff");
        shape.setAttribute("stroke-width", "1");
        shape.style.cursor = "pointer";

        shape.addEventListener("mouseenter", function () {
            tooltip.style.opacity = "1";
            tooltip.innerHTML =
                "<strong>" + row.state_name + "</strong><br>" +
                "Scenario effect vs reference: " + formatSignedValue(row.scenario_effect_vs_reference, 1) + "<br>" +
                "Reference-path projected GFR: " + formatNumber(row.reference_gfr, 1) + "<br>" +
                activeModelLabel + ": " + formatNumber(row.scenario_gfr, 1);
        });
        shape.addEventListener("mousemove", function (event) {
            const boundsRect = mapHost.getBoundingClientRect();
            tooltip.style.left = Math.min(event.clientX - boundsRect.left + 12, boundsRect.width - 220) + "px";
            tooltip.style.top = Math.max(event.clientY - boundsRect.top - 18, 12) + "px";
        });
        shape.addEventListener("mouseleave", function () {
            tooltip.style.opacity = "0";
        });
        shape.addEventListener("click", function () {
            const selected = dashboardV1Data.states.find(function (state) {
                return state.state_abbr === feature.id;
            });
            if (selected) {
                setSelectedState(selected.state_fips);
            }
        });

        svg.appendChild(shape);
    });

    mapHost.appendChild(svg);
    mapHost.appendChild(tooltip);
    wrapper.appendChild(mapHost);
    wrapper.appendChild(buildScenarioLegend(maxAbs));
    container.appendChild(wrapper);
}

function buildScenarioLegend(maxAbs) {
    const legend = document.createElement("div");
    legend.style.display = "grid";
    legend.style.gridTemplateRows = "auto 1fr";
    legend.style.gap = "10px";
    legend.style.alignItems = "stretch";
    legend.style.height = "100%";
    legend.style.minWidth = "84px";

    const title = document.createElement("div");
    title.style.fontSize = "11px";
    title.style.lineHeight = "1.3";
    title.style.fontWeight = "700";
    title.style.letterSpacing = "0.03em";
    title.style.textTransform = "uppercase";
    title.style.color = "#5f584d";
    title.textContent = "Scenario effect vs reference";

    const body = document.createElement("div");
    body.style.display = "grid";
    body.style.gridTemplateColumns = "16px minmax(52px, 1fr)";
    body.style.gap = "8px";
    body.style.alignItems = "stretch";
    body.style.height = "100%";

    const scale = document.createElement("div");
    scale.style.width = "16px";
    scale.style.borderRadius = "999px";
    scale.style.border = "1px solid #e5ddd1";
    scale.style.background = "linear-gradient(180deg, #0f7a6b 0%, #f5efe5 50%, #b9543f 100%)";
    scale.style.height = "100%";

    const labels = document.createElement("div");
    labels.style.display = "flex";
    labels.style.flexDirection = "column";
    labels.style.justifyContent = "space-between";
    labels.style.height = "100%";
    labels.style.fontSize = "12px";
    labels.style.color = "#5f584d";
    [
        formatSignedValue(maxAbs, 1),
        formatSignedValue(maxAbs / 2, 1),
        "0",
        formatSignedValue(-maxAbs / 2, 1),
        formatSignedValue(-maxAbs, 1)
    ].forEach(function (text) {
        const tick = document.createElement("span");
        tick.textContent = text;
        tick.style.display = "block";
        tick.style.lineHeight = "1";
        labels.appendChild(tick);
    });

    body.appendChild(scale);
    body.appendChild(labels);
    legend.appendChild(title);
    legend.appendChild(body);
    return legend;
}

function renderOverviewMap() {
    const rows = computeOverviewMapRows(dashboardV1State.projectionHorizon);
    const geojson = getUsStateGeoJson();
    const activeModelLabel = getSelectedModelLabel();
    const mapBadge = document.getElementById("v1-map-badge");
    const container = document.getElementById("v1-overview-map");
    const maxAbs = rows.reduce(function (maxValue, row) {
        return Math.max(maxValue, Math.abs(row.scenario_effect_vs_reference));
    }, 0.1);
    const rowLookup = {};

    rows.forEach(function (row) {
        rowLookup[row.state_abbr] = row;
    });

    document.getElementById("v1-overview-map-title").textContent =
        "Scenario effect vs reference | " + dashboardV1State.projectionHorizon + " | " + activeModelLabel;

    mapBadge.textContent = "Scenario";
    mapBadge.className = "dashboard-state-badge badge-scenario";

    if (!geojson) {
        container.innerHTML = "<p>U.S. state geometry could not be loaded for the local map.</p>";
        return;
    }

    container.innerHTML = "";
    const wrapper = document.createElement("div");
    wrapper.style.display = "grid";
    wrapper.style.gridTemplateColumns = "minmax(0, 1fr) 92px";
    wrapper.style.gap = "12px";
    wrapper.style.alignItems = "stretch";
    wrapper.style.height = "400px";

    const mapHost = document.createElement("div");
    mapHost.style.position = "relative";
    mapHost.style.height = "100%";
    mapHost.style.borderRadius = "14px";
    mapHost.style.background = "linear-gradient(180deg, #fffdf9 0%, #faf6ef 100%)";

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.setAttribute("viewBox", "0 0 620 390");
    svg.style.display = "block";

    const tooltip = document.createElement("div");
    tooltip.style.position = "absolute";
    tooltip.style.pointerEvents = "none";
    tooltip.style.opacity = "0";
    tooltip.style.transition = "opacity 0.12s ease";
    tooltip.style.background = "rgba(23, 36, 43, 0.94)";
    tooltip.style.color = "#ffffff";
    tooltip.style.padding = "8px 10px";
    tooltip.style.borderRadius = "10px";
    tooltip.style.fontSize = "12px";
    tooltip.style.lineHeight = "1.4";
    tooltip.style.maxWidth = "220px";
    tooltip.style.boxShadow = "0 10px 24px rgba(0, 0, 0, 0.16)";

    geojson.features.forEach(function (feature) {
        const row = rowLookup[feature.id];
        if (!row || !feature.geometry) {
            return;
        }
        const pathData = buildSvgPathForFeature(feature);
        if (!pathData) {
            return;
        }
        const shape = document.createElementNS("http://www.w3.org/2000/svg", "path");
        shape.setAttribute("d", pathData);
        shape.setAttribute("fill", colorForScenarioEffect(row.scenario_effect_vs_reference, maxAbs));
        shape.setAttribute("stroke", "#ffffff");
        shape.setAttribute("stroke-width", "1");
        shape.setAttribute("fill-rule", "evenodd");
        shape.style.cursor = "pointer";

        shape.addEventListener("mouseenter", function () {
            tooltip.style.opacity = "1";
            tooltip.innerHTML =
                "<strong>" + row.state_name + "</strong><br>" +
                "Scenario effect vs reference: " + formatSignedValue(row.scenario_effect_vs_reference, 1) + "<br>" +
                "Reference-path projected GFR: " + formatNumber(row.reference_gfr, 1) + "<br>" +
                activeModelLabel + ": " + formatNumber(row.scenario_gfr, 1);
        });
        shape.addEventListener("mousemove", function (event) {
            const boundsRect = mapHost.getBoundingClientRect();
            tooltip.style.left = Math.min(event.clientX - boundsRect.left + 12, boundsRect.width - 220) + "px";
            tooltip.style.top = Math.max(event.clientY - boundsRect.top - 18, 12) + "px";
        });
        shape.addEventListener("mouseleave", function () {
            tooltip.style.opacity = "0";
        });
        shape.addEventListener("click", function () {
            const selected = dashboardV1Data.states.find(function (state) {
                return state.state_abbr === feature.id;
            });
            if (selected) {
                setSelectedState(selected.state_fips);
            }
        });

        svg.appendChild(shape);
    });

    mapHost.appendChild(svg);
    mapHost.appendChild(tooltip);
    wrapper.appendChild(mapHost);
    wrapper.appendChild(buildScenarioLegend(maxAbs));
    container.appendChild(wrapper);
}

function buildSvgPathForFeature(feature) {
    const polygons = getFeaturePolygons(feature.geometry);
    const parts = [];
    polygons.forEach(function (polygon) {
        polygon.forEach(function (ring) {
            if (!ring.length) {
                return;
            }
            const projected = ring.map(function (point) {
                return projectUsMapPoint(point[0], point[1], feature.id);
            });
            const commands = projected.map(function (point, index) {
                return (index === 0 ? "M " : "L ") + point[0].toFixed(2) + " " + point[1].toFixed(2);
            });
            commands.push("Z");
            parts.push(commands.join(" "));
        });
    });
    return parts.join(" ");
}

function projectUsMapPoint(lon, lat, stateId) {
    if (stateId === "AK") {
        return [
            24 + (lon + 180) * 2.18,
            235 + (72 - lat) * 2.15
        ];
    }
    if (stateId === "HI") {
        return [
            178 + (lon + 161) * 7.0,
            332 + (22 - lat) * 7.0
        ];
    }
    return [
        165 + (lon + 125) * 7.15,
        30 + (50 - lat) * 11.5
    ];
}
