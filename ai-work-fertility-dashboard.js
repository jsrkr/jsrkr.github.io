const dashboardData = window.AI_WORK_FERTILITY_DASHBOARD_V1 || null;

const sliderDefinitions = [
    { key: "remote_work_growth", label: "remote-work share growth", min: -0.03, max: 0.08, step: 0.005 },
    { key: "digital_distraction_growth", label: "screen-leisure growth", min: -0.05, max: 0.08, step: 0.005 },
    { key: "digital_social_growth", label: "online-social-life growth", min: -0.03, max: 0.05, step: 0.005 },
    { key: "face_to_face_change", label: "in-person social change", min: -0.08, max: 0.05, step: 0.005 },
    { key: "gendered_care_penalty", label: "gendered-care burden penalty", min: 0.0, max: 0.08, step: 0.005 },
];

const mechanismOrder = [
    { key: "mechanism_remote_work_flexibility", label: "remote-work time saved" },
    { key: "mechanism_digital_distraction", label: "screen leisure" },
    { key: "mechanism_online_matching", label: "online matching / digital social life" },
    { key: "mechanism_in_person_social", label: "in-person social interaction" },
    { key: "mechanism_care_burden", label: "care burden" },
];

const scenarioCompareDefaults = {
    scenarioA: "remote_work_saves_time",
    scenarioB: "digital_distraction_crowds_out",
};

const SCENARIO_DIFFERENCE_TOLERANCE = 0.05;
const RANKING_DISPLAY_DIGITS = 3;
const DESIRED_HORIZON_YEARS = [2030, 2035, 2040, 2045, 2050, 2055, 2060];
const DEFAULT_HORIZON_YEAR = 2035;
const WOMEN_AGE_LABEL = "15\u201344";

const scenarioAdjustmentProfiles = {
    remote_work_saves_time: {
        remote: 1.0,
        distraction: 0.35,
        online: 0.2,
        inPerson: 0.25,
        care: 0.6,
    },
    digital_distraction_crowds_out: {
        remote: 0.1,
        distraction: 1.0,
        online: 0.2,
        inPerson: 0.45,
        care: 0.15,
    },
    online_life_helps_matching: {
        remote: 0.15,
        distraction: 0.25,
        online: 1.0,
        inPerson: 0.2,
        care: 0.1,
    },
    home_centered_digital_life_increases_care_work: {
        remote: 0.25,
        distraction: 0.15,
        online: 0.05,
        inPerson: 0.05,
        care: 1.1,
    },
};

// Old dashboard scenario keys that have since been renamed. Bookmarked links and stored
// downloads that still reference an old key resolve to the current key instead of breaking.
const SCENARIO_ID_ALIASES = Object.assign(
    { remote_work_increases_care_burden: "home_centered_digital_life_increases_care_work" },
    (dashboardData && dashboardData.scenario_id_aliases) || {}
);

function resolveScenarioId(scenarioId) {
    return SCENARIO_ID_ALIASES[scenarioId] || scenarioId;
}

const MSA_UNAVAILABLE_MESSAGE =
    "MSA-level projections require county-to-MSA fertility inputs and precomputed MSA scenario outputs. These data are not available in the current repository.";

const MSA_RANKINGS_UNAVAILABLE_MESSAGE =
    "MSA rankings will appear once MSA-level scenario outputs are available.";

const sectionIds = [
    "state-map",
    "rankings",
    "us-state",
    "scenarios",
    "compare",
    "assumptions",
    "method",
];

const dashboardState = {
    selectedGeoType: "state",
    selectedStateFips: "06",
    selectedMsaId: "",
    selectedMsaStateFilter: "all",
    selectedModel: "statistical_ridge",
    selectedScenario: "remote_work_saves_time",
    selectedOutcome: "scenario_difference",
    selectedHorizon: DEFAULT_HORIZON_YEAR,
    compareGeoType: "state",
    comparePlaceId: "",
    compareScenarioA: scenarioCompareDefaults.scenarioA,
    compareScenarioB: scenarioCompareDefaults.scenarioB,
    params: {},
};

const lookup = {
    stateByFips: new Map(),
    stateByAbbr: new Map(),
    modelById: new Map(),
    scenarioById: new Map(),
    forecastSeries: new Map(),
    metricsByModelAndGeo: new Map(),
    msaById: new Map(),
    recordsByGeoType: new Map(),
    allForecastRecords: [],
    forecastStartYear: null,
};

const availability = {
    msa: {
        available: false,
        reason: MSA_UNAVAILABLE_MESSAGE,
    },
};

const infoTooltipCopy = {
    control_model: {
        label: "Model",
        description: "Choose which predictive benchmark to display.",
    },
    control_scenario: {
        label: "Scenario",
        description: "Choose the digital-life scenario to compare with the reference path.",
    },
    control_horizon: {
        label: "Horizon year",
        description: "Choose the future year for the state map comparison.",
    },
    control_outcome: {
        label: "Outcome",
        description: "Choose whether to display the scenario difference or projected GFR levels.",
    },
    statistical_ridge: {
        label: "Statistical baseline",
        description: "A traditional statistical projection based on observed fertility trends and available state-level predictors.",
    },
    tree_gradient_boosting: {
        label: "Tree ML benchmark",
        description: "A tree-based machine-learning benchmark that captures nonlinear relationships. It is used as a predictive comparison, not a causal estimate.",
    },
    temporal_neural_net: {
        label: "Neural network benchmark",
        description: "A neural-network predictive benchmark. If performance is weaker than simpler models, interpret it as exploratory.",
    },
    reference_path: {
        label: "Reference path",
        description: "The projected General Fertility Rate under the model-based reference path before any additional scenario shift.",
    },
    reference_path_level: {
        label: "Reference path (GFR level)",
        description: "The projected General Fertility Rate under the model-based reference path before any additional scenario shift.",
    },
    scenario_path: {
        label: "Scenario path",
        description: "The projected General Fertility Rate under the selected scenario, measured as live births per 1,000 women aged " + WOMEN_AGE_LABEL + ".",
    },
    scenario_path_level: {
        label: "Scenario path (GFR level)",
        description: "The projected General Fertility Rate under the selected scenario, measured as live births per 1,000 women aged " + WOMEN_AGE_LABEL + ".",
    },
    scenario_difference: {
        label: "Scenario difference from reference path",
        description: "The selected scenario path minus the model-based reference path, measured in births per 1,000 women aged " + WOMEN_AGE_LABEL + ".",
    },
    gfr_level: {
        label: "GFR level",
        description: "General Fertility Rate, measured as live births per 1,000 women aged " + WOMEN_AGE_LABEL + ".",
    },
    remote_work_saves_time: {
        label: "Remote work saves time",
        description: "Scenario interpretation: this scenario assumes that remote work saves commuting time and increases flexibility. The adjustment is based on the change in remote-work time saved relative to the reference path.",
    },
    digital_distraction_crowds_out: {
        label: "Screen leisure crowds out in-person life",
        description: "Scenario interpretation: ATUS-based screen leisure is used as a broad proxy for digital leisure. It captures screen time broadly, not pure social media use.",
    },
    online_life_helps_matching: {
        label: "Online life helps matching",
        description: "Scenario interpretation: this scenario assumes that online social tools and dating-app search attention make it easier for people to meet partners or maintain relationships. The adjustment is based on the change in an online-dating search-interest proxy relative to the reference path.",
    },
    home_centered_digital_life_increases_care_work: {
        label: "More time at home increases care work",
        description: "Scenario interpretation: more digital life - remote work, online services and shopping, and digital entertainment - can keep people at home more and raise unpaid care and household burdens. The displayed adjustment uses ATUS-based household-work and unpaid-care minutes.",
    },
};

let activeInfoTooltipId = "";
let infoTooltipSequence = 0;
let infoTooltipEventsBound = false;
let utilityPanelEventsBound = false;

document.addEventListener("DOMContentLoaded", function () {
    if (!dashboardData) {
        renderGlobalError("Dashboard data bundle could not be found.");
        return;
    }
    if (typeof window.Plotly === "undefined") {
        renderGlobalError("The Plotly chart library did not load, so the interactive dashboard cannot render.");
        return;
    }

    initializeLookups();
    initializeAvailability();
    initializeState();
    applyUrlState();
    populateControls();
    renderHeroStats();
    renderScenarioStories();
    renderAssumptionSliders();
    bindEvents();
    bindInfoTooltips();
    initializeSectionNavigation();
    exposeDashboardValidation();
    renderDashboard();
});

function initializeLookups() {
    const states = Array.isArray(dashboardData.states) ? dashboardData.states : [];
    states
        .filter(function (state) { return String(state.state_fips || "") !== "00"; })
        .forEach(function (state) {
            lookup.stateByFips.set(String(state.state_fips).padStart(2, "0"), state);
            lookup.stateByAbbr.set(String(state.state_abbr || "").toUpperCase(), state);
        });

    (dashboardData.model_options || []).forEach(function (model) {
        lookup.modelById.set(model.id, model);
    });

    (dashboardData.scenario_options || []).forEach(function (scenario) {
        lookup.scenarioById.set(scenario.id, scenario);
    });

    lookup.recordsByGeoType.set("state", []);
    lookup.recordsByGeoType.set("msa", []);

    lookup.allForecastRecords = normalizeForecastRecords();

    lookup.allForecastRecords.forEach(function (record) {
        const geoType = record.geography_type;
        const geographyId = record.geography_id;
        const key = [geoType, geographyId, record.model, record.scenario].join("|");
        if (!lookup.forecastSeries.has(key)) {
            lookup.forecastSeries.set(key, []);
        }
        lookup.forecastSeries.get(key).push(record);
        lookup.recordsByGeoType.get(geoType).push(record);

        if (geoType === "msa" && !lookup.msaById.has(geographyId)) {
            lookup.msaById.set(geographyId, {
                geography_id: geographyId,
                geography_name: record.geography_name,
                cbsa_code: record.cbsa_code || geographyId,
                msa_name: record.msa_name || record.geography_name,
                state_name: record.state_name || "",
                state_abbr: record.state_abbr || "",
                fertility_series: Array.isArray(record.fertility_series) ? record.fertility_series : [],
                latest: record.latest || {},
            });
        }
    });

    lookup.forecastSeries.forEach(function (records) {
        records.sort(function (a, b) { return a.year - b.year; });
    });

    const allYears = lookup.allForecastRecords.map(function (record) {
        return Number(record.year);
    }).filter(Number.isFinite);
    lookup.forecastStartYear = allYears.length ? Math.min.apply(null, allYears) : null;

    normalizeMetricRecords().forEach(function (metric) {
        const key = [metric.geography_type, metric.model].join("|");
        if (!lookup.metricsByModelAndGeo.has(key)) {
            lookup.metricsByModelAndGeo.set(key, []);
        }
        lookup.metricsByModelAndGeo.get(key).push(metric);
    });
}

function initializeAvailability() {
    const msaRecords = lookup.recordsByGeoType.get("msa") || [];
    const explicitReason = dashboardData.metadata && dashboardData.metadata.msa_unavailable_reason;
    availability.msa.available = lookup.msaById.size > 0 && msaRecords.length > 0;
    availability.msa.reason = explicitReason || MSA_UNAVAILABLE_MESSAGE;
}

function initializeState() {
    const firstState = getAvailableStates()[0];
    if (firstState) {
        dashboardState.selectedStateFips = firstState.state_fips;
    }

    const availableModel = (dashboardData.model_options || []).find(function (model) {
        return model.available;
    });
    if (availableModel) {
        dashboardState.selectedModel = availableModel.id;
    }

    const availableScenarios = getScenarioChoices();
    if (availableScenarios.length) {
        dashboardState.selectedScenario = availableScenarios[0].id;
    }

    const horizonOptions = getAvailableHorizonYears();
    if (horizonOptions.length) {
        dashboardState.selectedHorizon = horizonOptions.includes(DEFAULT_HORIZON_YEAR)
            ? DEFAULT_HORIZON_YEAR
            : horizonOptions[0];
    }

    dashboardState.compareScenarioA = scenarioCompareDefaults.scenarioA;
    dashboardState.compareScenarioB = scenarioCompareDefaults.scenarioB;
    dashboardState.comparePlaceId = dashboardState.selectedStateFips;
    dashboardState.params = {
        remote_work_growth: Number(dashboardData.scenario_defaults && dashboardData.scenario_defaults.remote_work_growth || 0),
        digital_distraction_growth: Number(dashboardData.scenario_defaults && dashboardData.scenario_defaults.digital_distraction_growth || 0),
        digital_social_growth: Number(dashboardData.scenario_defaults && dashboardData.scenario_defaults.digital_social_growth || 0),
        face_to_face_change: Number(dashboardData.scenario_defaults && dashboardData.scenario_defaults.face_to_face_change || 0),
        gendered_care_penalty: Number(dashboardData.scenario_defaults && dashboardData.scenario_defaults.gendered_care_penalty || 0),
    };
}

function applyUrlState() {
    const params = new URLSearchParams(window.location.search);
    const place = params.get("place");
    const model = params.get("model");
    const scenario = resolveScenarioId(params.get("scenario"));
    const year = Number(params.get("year"));
    const outcome = params.get("outcome");

    dashboardState.selectedGeoType = "state";
    dashboardState.compareGeoType = "state";

    if (place) {
        const normalizedState = resolveStateIdentifier(place);
        if (normalizedState) {
            dashboardState.selectedStateFips = normalizedState;
            dashboardState.comparePlaceId = normalizedState;
        }
    }

    if (model && lookup.modelById.has(model)) {
        dashboardState.selectedModel = model;
    }
    if (scenarioChoiceExists(scenario)) {
        dashboardState.selectedScenario = scenario;
    }
    if (Number.isFinite(year) && getAvailableHorizonYears().includes(year)) {
        dashboardState.selectedHorizon = year;
    }
    if ((dashboardData.outcome_options || []).some(function (item) { return item.id === outcome; })) {
        dashboardState.selectedOutcome = outcome;
    }

    if (!lookup.stateByFips.has(dashboardState.selectedStateFips)) {
        const firstState = getAvailableStates()[0];
        dashboardState.selectedStateFips = firstState ? firstState.state_fips : dashboardState.selectedStateFips;
    }

    if (!lookup.modelById.has(dashboardState.selectedModel)) {
        dashboardState.selectedModel = getSelectedModel().id;
    }

    if (!scenarioChoiceExists(dashboardState.selectedScenario)) {
        dashboardState.selectedScenario = scenarioCompareDefaults.scenarioA;
    }

    if (!getAvailableHorizonYears().includes(dashboardState.selectedHorizon)) {
        dashboardState.selectedHorizon = getAvailableHorizonYears().includes(DEFAULT_HORIZON_YEAR)
            ? DEFAULT_HORIZON_YEAR
            : getAvailableHorizonYears()[0];
    }

    if (dashboardState.compareGeoType === "state" && !lookup.stateByFips.has(dashboardState.comparePlaceId)) {
        dashboardState.comparePlaceId = dashboardState.selectedStateFips;
    }
}

function populateControls() {
    populateGlobalControls();
    populateCompareControls();
    syncControls();
}

function populateGlobalControls() {
    const states = getAvailableStates();
    const models = dashboardData.model_options || [];
    const scenarios = getScenarioChoices();
    const outcomes = dashboardData.outcome_options || [];
    const horizonYears = getAvailableHorizonYears();

    document.querySelectorAll('[data-setting="state"]').forEach(function (select) {
        select.innerHTML = states.map(function (state) {
            return '<option value="' + state.state_fips + '">' + state.state_name + "</option>";
        }).join("");
    });

    document.querySelectorAll('[data-setting="model"]').forEach(function (select) {
        select.innerHTML = models.map(function (model) {
            const disabled = model.available ? "" : " disabled";
            return '<option value="' + model.id + '"' + disabled + ">" + getModelDisplayLabel(model) + "</option>";
        }).join("");
    });

    document.querySelectorAll('[data-setting="scenario"]').forEach(function (select) {
        select.innerHTML = scenarios.map(function (scenario) {
            return '<option value="' + scenario.id + '">' + scenario.label + "</option>";
        }).join("");
    });

    document.querySelectorAll('[data-setting="horizon"]').forEach(function (select) {
        select.innerHTML = horizonYears.map(function (year) {
            return '<option value="' + year + '">' + year + "</option>";
        }).join("");
    });

    document.querySelectorAll('[data-setting="outcome"]').forEach(function (select) {
        select.innerHTML = outcomes.map(function (outcome) {
            return '<option value="' + outcome.id + '">' + getOutcomeLabel(outcome.id, outcome.label) + "</option>";
        }).join("");
    });
}

function populateMsaControls() {
    const stateFilterSelect = document.getElementById("msa-state-filter-select");
    const msaSelect = document.getElementById("msa-select");

    if (!stateFilterSelect || !msaSelect) {
        return;
    }

    if (!availability.msa.available) {
        stateFilterSelect.disabled = true;
        msaSelect.disabled = true;
        stateFilterSelect.innerHTML = "<option>MSA data unavailable</option>";
        msaSelect.innerHTML = "<option>MSA data unavailable</option>";
        return;
    }

    const stateOptions = getMsaStateOptions();
    stateFilterSelect.disabled = false;
    stateFilterSelect.innerHTML = ['<option value="all">All states</option>'].concat(
        stateOptions.map(function (option) {
            return '<option value="' + option.value + '">' + option.label + "</option>";
        })
    ).join("");

    populateMsaPlaceOptions();
}

function populateMsaPlaceOptions() {
    const msaSelect = document.getElementById("msa-select");
    if (!msaSelect) {
        return;
    }

    if (!availability.msa.available) {
        msaSelect.disabled = true;
        msaSelect.innerHTML = "<option>MSA data unavailable</option>";
        return;
    }

    const msas = getFilteredMsas();
    msaSelect.disabled = msas.length === 0;
    msaSelect.innerHTML = msas.length
        ? msas.map(function (msa) {
            return '<option value="' + msa.geography_id + '">' + msa.geography_name + "</option>";
        }).join("")
        : "<option>No MSAs match this filter</option>";

    if (!msas.some(function (msa) { return msa.geography_id === dashboardState.selectedMsaId; })) {
        dashboardState.selectedMsaId = msas.length ? msas[0].geography_id : "";
    }
}

function populateCompareControls() {
    const compareScenarioASelect = document.getElementById("compare-scenario-a-select");
    const compareScenarioBSelect = document.getElementById("compare-scenario-b-select");

    const compareScenarios = getScenarioChoices();
    const optionsHtml = compareScenarios.map(function (scenario) {
        return '<option value="' + scenario.id + '">' + scenario.label + "</option>";
    }).join("");
    if (compareScenarioASelect) {
        compareScenarioASelect.innerHTML = optionsHtml;
    }
    if (compareScenarioBSelect) {
        compareScenarioBSelect.innerHTML = optionsHtml;
    }

    populateComparePlaceOptions();
}

function populateComparePlaceOptions() {
    const comparePlaceSelect = document.getElementById("compare-place-select");
    if (!comparePlaceSelect) {
        return;
    }

    const states = getAvailableStates();
    comparePlaceSelect.disabled = false;
    comparePlaceSelect.innerHTML = states.map(function (state) {
        return '<option value="' + state.state_fips + '">' + state.state_name + "</option>";
    }).join("");
    if (!states.some(function (state) { return state.state_fips === dashboardState.comparePlaceId; })) {
        dashboardState.comparePlaceId = dashboardState.selectedStateFips;
    }
}

function bindEvents() {
    document.querySelectorAll("[data-setting]").forEach(function (control) {
        control.addEventListener("change", function (event) {
            const key = event.target.getAttribute("data-setting");
            const value = event.target.value;
            if (key === "state") {
                dashboardState.selectedStateFips = value;
                dashboardState.selectedGeoType = "state";
                if (dashboardState.compareGeoType === "state") {
                    dashboardState.comparePlaceId = value;
                }
            } else if (key === "model") {
                dashboardState.selectedModel = value;
            } else if (key === "scenario") {
                dashboardState.selectedScenario = value;
            } else if (key === "outcome") {
                dashboardState.selectedOutcome = value;
            } else if (key === "horizon") {
                dashboardState.selectedHorizon = Number(value);
            }
            syncControls();
            renderDashboard();
        });
    });

    const scenarioGrid = document.getElementById("scenario-story-grid");
    if (scenarioGrid) {
        scenarioGrid.addEventListener("click", function (event) {
            const button = event.target.closest("[data-run-scenario]");
            if (!button) {
                return;
            }
            dashboardState.selectedScenario = button.getAttribute("data-run-scenario");
            dashboardState.compareScenarioA = dashboardState.selectedScenario;
            syncControls();
            renderDashboard();
        });
    }

    const assumptionGrid = document.getElementById("assumption-slider-grid");
    if (assumptionGrid) {
        assumptionGrid.addEventListener("input", function (event) {
            const input = event.target.closest("[data-slider-key]");
            if (!input) {
                return;
            }
            const key = input.getAttribute("data-slider-key");
            dashboardState.params[key] = Number(input.value);
            const valueNode = document.querySelector('[data-slider-value="' + key + '"]');
            if (valueNode) {
                valueNode.textContent = formatSignedPercentPoints(Number(input.value));
            }
            renderDashboard();
        });
    }

    const msaStateFilterSelect = document.getElementById("msa-state-filter-select");
    if (msaStateFilterSelect) {
        msaStateFilterSelect.addEventListener("change", function (event) {
            dashboardState.selectedMsaStateFilter = event.target.value;
            populateMsaPlaceOptions();
            syncControls();
            renderDashboard();
        });
    }

    const msaSelect = document.getElementById("msa-select");
    if (msaSelect) {
        msaSelect.addEventListener("change", function (event) {
            dashboardState.selectedMsaId = event.target.value;
            dashboardState.selectedGeoType = "msa";
            if (dashboardState.compareGeoType === "msa") {
                dashboardState.comparePlaceId = event.target.value;
            }
            syncControls();
            renderDashboard();
        });
    }

    const comparePlaceSelect = document.getElementById("compare-place-select");
    if (comparePlaceSelect) {
        comparePlaceSelect.addEventListener("change", function (event) {
            dashboardState.comparePlaceId = event.target.value;
            renderDashboard();
        });
    }

    const compareScenarioASelect = document.getElementById("compare-scenario-a-select");
    if (compareScenarioASelect) {
        compareScenarioASelect.addEventListener("change", function (event) {
            dashboardState.compareScenarioA = event.target.value;
            renderDashboard();
        });
    }

    const compareScenarioBSelect = document.getElementById("compare-scenario-b-select");
    if (compareScenarioBSelect) {
        compareScenarioBSelect.addEventListener("change", function (event) {
            dashboardState.compareScenarioB = event.target.value;
            renderDashboard();
        });
    }

    bindUtilityActions();
}

function bindUtilityActions() {
    bindClick("download-current-view-button", downloadCurrentView);
    bindClick("download-all-data-button", downloadAllScenarioData);
    bindClick("download-rankings-button", downloadRankings);
    bindClick("copy-summary-button", copySummary);
    bindClick("copy-link-button", copyCurrentViewLink);
    bindUtilityPanels();
}

function bindUtilityPanels() {
    const nav = document.querySelector(".scenario-utility-nav");
    const detailsNodes = Array.from(document.querySelectorAll("[data-utility-panel]"));
    if (!nav || !detailsNodes.length || utilityPanelEventsBound) {
        return;
    }
    utilityPanelEventsBound = true;

    function syncSummaryState(detailsNode) {
        const summary = detailsNode.querySelector("summary");
        if (summary) {
            summary.setAttribute("aria-expanded", detailsNode.open ? "true" : "false");
        }
    }

    function closePanels(exceptNode) {
        detailsNodes.forEach(function (detailsNode) {
            if (exceptNode && detailsNode === exceptNode) {
                syncSummaryState(detailsNode);
                return;
            }
            detailsNode.open = false;
            syncSummaryState(detailsNode);
        });
    }

    detailsNodes.forEach(function (detailsNode) {
        syncSummaryState(detailsNode);
        detailsNode.addEventListener("toggle", function () {
            if (detailsNode.open) {
                closePanels(detailsNode);
            } else {
                syncSummaryState(detailsNode);
            }
        });
        detailsNode.addEventListener("click", function (event) {
            if (event.target.closest("button")) {
                detailsNode.open = false;
                syncSummaryState(detailsNode);
            }
        });
    });

    document.addEventListener("click", function (event) {
        if (!nav.contains(event.target)) {
            closePanels(null);
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closePanels(null);
        }
    });
}

function bindInfoTooltips() {
    if (infoTooltipEventsBound) {
        return;
    }

    document.addEventListener("click", function (event) {
        const button = event.target.closest("[data-tooltip-button]");
        if (button) {
            event.preventDefault();
            toggleInfoTooltip(button);
            return;
        }

        if (!activeInfoTooltipId) {
            return;
        }
        const activePopover = document.getElementById(activeInfoTooltipId);
        const activeButton = document.querySelector('[data-tooltip-id="' + activeInfoTooltipId + '"]');
        if (!activePopover || !activeButton) {
            closeAllInfoTooltips();
            return;
        }
        if (activePopover.contains(event.target) || activeButton.contains(event.target)) {
            return;
        }
        closeAllInfoTooltips();
    });

    document.addEventListener("keydown", function (event) {
        const button = event.target.closest ? event.target.closest("[data-tooltip-button]") : null;
        if (button && (event.key === "Enter" || event.key === " ")) {
            event.preventDefault();
            toggleInfoTooltip(button);
            return;
        }
        if (event.key === "Escape" && activeInfoTooltipId) {
            closeAllInfoTooltips();
        }
    });

    window.addEventListener("resize", repositionActiveInfoTooltip);
    window.addEventListener("scroll", repositionActiveInfoTooltip, { passive: true });
    infoTooltipEventsBound = true;
}

function toggleInfoTooltip(button) {
    const tooltipId = button.getAttribute("data-tooltip-id");
    if (!tooltipId) {
        return;
    }
    if (activeInfoTooltipId === tooltipId) {
        closeAllInfoTooltips();
        return;
    }
    closeAllInfoTooltips();
    openInfoTooltip(button, tooltipId);
}

function openInfoTooltip(button, tooltipId) {
    const popover = document.getElementById(tooltipId);
    if (!popover) {
        return;
    }
    activeInfoTooltipId = tooltipId;
    button.setAttribute("aria-expanded", "true");
    popover.hidden = false;
    positionInfoTooltip(button, popover);
}

function closeAllInfoTooltips() {
    document.querySelectorAll("[data-tooltip-button]").forEach(function (button) {
        button.setAttribute("aria-expanded", "false");
    });
    document.querySelectorAll(".scenario-info-popover").forEach(function (popover) {
        popover.hidden = true;
        popover.style.top = "";
        popover.style.left = "";
        popover.removeAttribute("data-placement");
    });
    activeInfoTooltipId = "";
}

function repositionActiveInfoTooltip() {
    if (!activeInfoTooltipId) {
        return;
    }
    const popover = document.getElementById(activeInfoTooltipId);
    const button = document.querySelector('[data-tooltip-id="' + activeInfoTooltipId + '"]');
    if (!popover || !button || popover.hidden) {
        return;
    }
    positionInfoTooltip(button, popover);
}

function positionInfoTooltip(button, popover) {
    const margin = 12;
    const buttonRect = button.getBoundingClientRect();
    const popoverRect = popover.getBoundingClientRect();
    const fitsBelow = buttonRect.bottom + 10 + popoverRect.height <= window.innerHeight - margin;
    const top = fitsBelow
        ? buttonRect.bottom + 10
        : Math.max(margin, buttonRect.top - popoverRect.height - 10);
    const left = clamp(
        buttonRect.left + buttonRect.width / 2 - popoverRect.width / 2,
        margin,
        window.innerWidth - popoverRect.width - margin
    );
    popover.style.top = top + "px";
    popover.style.left = left + "px";
    popover.setAttribute("data-placement", fitsBelow ? "bottom" : "top");
}

function bindClick(elementId, handler) {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }
    element.addEventListener("click", handler);
}

function renderDashboard() {
    closeAllInfoTooltips();
    syncControls();
    renderControlInfoSummaries();
    renderMap();
    renderRankings();
    renderStateExplorer();
    renderScenarioStories();
    renderCompare();
    renderMechanismPanel();
    renderModelStatus();
    renderMethodCards();
    updateSelectionStrips();
    updateUtilityActionState();
    updateUrlState();
}

function renderHeroStats() {
    const stateCount = getAvailableStates().length;
    const stateLabel = stateCount === 51 ? "50 states + DC" : stateCount + " state geographies";
    const summaryItems = [
        stateLabel,
        getScenarioChoices().length + " digital-life scenarios",
        (dashboardData.model_options || []).length + " predictive benchmarks",
        "State-year exports available",
    ];

    const summaryNode = document.getElementById("hero-stat-grid");
    if (!summaryNode) {
        return;
    }

    summaryNode.innerHTML = summaryItems.map(function (item) {
        return '<span class="scenario-summary-item">' + item + "</span>";
    }).join('<span class="scenario-summary-separator" aria-hidden="true">&middot;</span>');
}

function renderScenarioStories() {
    const stories = getScenarioChoices();
    const container = document.getElementById("scenario-story-grid");
    if (!container) {
        return;
    }

    container.innerHTML = stories.map(function (scenario, index) {
        return [
            '<article class="dashboard-card scenario-story-card' + (scenario.id === dashboardState.selectedScenario ? " is-active" : "") + '" data-scenario-story="' + scenario.id + '">',
            '<p class="dashboard-section-kicker">Scenario ' + (index + 1) + "</p>",
            "<h3>" + buildInlineInfoLabelHtml(scenario.id, scenario.label) + "</h3>",
            '<p class="scenario-story-copy">' + scenario.hypothesis + "</p>",
            '<button class="scenario-story-button" type="button" data-run-scenario="' + scenario.id + '">Run scenario</button>',
            "</article>",
        ].join("");
    }).join("");
}

function renderAssumptionSliders() {
    const container = document.getElementById("assumption-slider-grid");
    if (!container) {
        return;
    }

    container.innerHTML = sliderDefinitions.map(function (definition) {
        const value = Number(dashboardState.params[definition.key]);
        return [
            '<label class="scenario-slider-card">',
            '<span class="scenario-slider-head">',
            '<span class="scenario-slider-label">' + definition.label + "</span>",
            '<span class="scenario-slider-value" data-slider-value="' + definition.key + '">' + formatSignedPercentPoints(value) + "</span>",
            "</span>",
            '<input type="range" min="' + definition.min + '" max="' + definition.max + '" step="' + definition.step + '" value="' + value + '" data-slider-key="' + definition.key + '">',
            "</label>",
        ].join("");
    }).join("");
}

function renderMap() {
    const mapRows = getStateRowsForCurrentView();
    const values = mapRows.map(function (row) {
        return row[dashboardState.selectedOutcome];
    });
    const scenarioDiffs = mapRows.map(function (row) { return row.scenario_difference; }).filter(Number.isFinite);
    const scenarioExtent = getScenarioDifferenceExtent(scenarioDiffs);

    const model = getSelectedModel();
    const mapBadge = document.getElementById("map-model-badge");
    if (mapBadge && model) {
        mapBadge.textContent = model.label;
    }

    updateFigure1Title();

    if (!values.length || !values.every(Number.isFinite)) {
        renderPlotFallback("state-map-chart", "Unavailable for current selection.");
        updateMapNote(scenarioDiffs);
        renderMapSummary();
        return;
    }

    const trace = {
        type: "choropleth",
        locationmode: "USA-states",
        locations: mapRows.map(function (row) { return row.state_abbr; }),
        z: values,
        customdata: mapRows.map(function (row) {
            return [row.geography_id, row.geography_name, row.reference_path, row.scenario_path, row.scenario_difference, row.main_driver || ""];
        }),
        marker: { line: { color: "#f4efe6", width: 0.8 } },
        colorscale: dashboardState.selectedOutcome === "scenario_difference"
            ? [[0, "#8b3a22"], [0.5, "#f6f1e8"], [1, "#1f6b75"]]
            : [[0, "#f3e5c8"], [0.5, "#d1dcbf"], [1, "#205b62"]],
        zmin: dashboardState.selectedOutcome === "scenario_difference" ? scenarioExtent.min : undefined,
        zmax: dashboardState.selectedOutcome === "scenario_difference" ? scenarioExtent.max : undefined,
        zmid: dashboardState.selectedOutcome === "scenario_difference" ? 0 : undefined,
        hovertemplate:
            "<b>%{customdata[1]}</b><br>" +
            "Model-based reference path: %{customdata[2]:.1f}<br>" +
            "Scenario path: %{customdata[3]:.1f}<br>" +
            "Scenario difference: %{customdata[4]:+.1f}<br>" +
            "Main driver: %{customdata[5]}<extra></extra>",
        colorbar: {
            title: {
                text: dashboardState.selectedOutcome === "scenario_difference"
                    ? "Scenario difference from reference path<br>Live births per 1,000 women aged " + WOMEN_AGE_LABEL
                    : "Live births per 1,000 women aged " + WOMEN_AGE_LABEL,
                side: "right",
            },
            thickness: 12,
            tickfont: { size: 11 },
        },
    };

    const layout = {
        geo: {
            scope: "usa",
            projection: { type: "albers usa" },
            bgcolor: "rgba(0,0,0,0)",
            showlakes: false,
            showland: true,
            landcolor: "#fbf8f2",
            subunitcolor: "#ffffff",
        },
        margin: { t: 8, r: 0, b: 0, l: 0 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        dragmode: false,
    };

    plotChart("state-map-chart", [trace], layout, function (container) {
        if (typeof container.removeAllListeners === "function") {
            container.removeAllListeners("plotly_click");
        }
        container.on("plotly_click", function (event) {
            if (!event.points || !event.points.length) {
                return;
            }
            dashboardState.selectedStateFips = event.points[0].customdata[0];
            dashboardState.selectedGeoType = "state";
            if (dashboardState.compareGeoType === "state") {
                dashboardState.comparePlaceId = dashboardState.selectedStateFips;
            }
            syncControls();
            renderDashboard();
        });
    });

    updateMapNote(scenarioDiffs);
    renderMapSummary();
}

function updateFigure1Title() {
    const titleNode = document.getElementById("figure-1-title");
    if (!titleNode) {
        return;
    }
    if (dashboardState.selectedOutcome === "reference_path") {
        titleNode.textContent = "Figure 1: Reference fertility path across U.S. states";
        return;
    }
    if (dashboardState.selectedOutcome === "scenario_path") {
        titleNode.textContent = "Figure 1: Scenario fertility path across U.S. states";
        return;
    }
    titleNode.textContent = "Figure 1: Scenario difference across U.S. states";
}

function updateMapNote(scenarioDiffs) {
    const noteNode = document.getElementById("state-map-note");
    if (!noteNode) {
        return;
    }
    if (dashboardState.selectedOutcome !== "scenario_difference") {
        noteNode.innerHTML =
            "Values show " + buildInlineInfoLabelHtml("gfr_level") +
            ". Rankings below still use " + buildInlineInfoLabelHtml("scenario_difference") +
            " relative to the " + buildInlineInfoLabelHtml("reference_path") + ".";
        return;
    }
    if (!scenarioDiffs.length) {
        noteNode.textContent = "Range unavailable for the current selection.";
        return;
    }
    const extent = getScenarioDifferenceExtent(scenarioDiffs);
    let text =
        buildScenarioInterpretationNote() + " In the current view, scenario differences range from " +
        formatSignedValue(extent.min, 1) + " to " + formatSignedValue(extent.max, 1) +
        " births per 1,000 women relative to the reference path. The projections can change based on the chosen assumptions.";
    const calibrationNote = buildScenarioCalibrationNote();
    if (calibrationNote) {
        text += " " + calibrationNote;
    }
    const commuteNote = buildScenarioCommuteInputNote();
    if (commuteNote) {
        text += " " + commuteNote;
    }
    const scenarioDirectionNote = getScenarioDirectionNote(scenarioDiffs);
    if (scenarioDirectionNote) {
        text += " " + scenarioDirectionNote;
    }
    const reliabilityNote = buildModelReliabilityNote();
    if (reliabilityNote) {
        text += " " + reliabilityNote;
    }
    noteNode.textContent = text;
}

function getSelectedModelOption() {
    const models = dashboardData.model_options || [];
    return models.find(function (model) { return model.id === dashboardState.selectedModel; }) || null;
}

// Surfaces the bundle's recursive-forecast clamping diagnostic. If a model pins most of its
// forecast state-years at the floor/ceiling clamp, its reference and scenario paths collapse onto
// the same value and the scenario difference is mechanically meaningless -- warn the reader instead
// of letting them compare scenarios with a degenerate model.
function buildModelReliabilityNote() {
    const model = getSelectedModelOption();
    if (!model) {
        return "";
    }
    if (model.forecast_clamped_heavily || model.reliable === false) {
        return "Caution: the " + (model.label || "selected") + " benchmark pins most forecast state-years at the model's forecast clamp, so its reference and scenario paths collapse onto the same value and scenario differences are not meaningful for this model.";
    }
    return "";
}

function getCurrentScenarioDiagnostic() {
    const rows = Array.isArray(dashboardData.scenario_diagnostics) ? dashboardData.scenario_diagnostics : [];
    return rows.find(function (row) {
        return row.model === dashboardState.selectedModel
            && row.scenario === dashboardState.selectedScenario
            && Number(row.year) === Number(dashboardState.selectedHorizon);
    }) || null;
}

function buildScenarioInterpretationNote() {
    const diagnostic = getCurrentScenarioDiagnostic();
    if (dashboardState.selectedScenario === "remote_work_saves_time") {
        let text = "Scenario interpretation: This scenario assumes that remote work saves commuting time and increases flexibility. The adjustment is based on the change in remote-work time saved relative to the reference path. Positive values mean the scenario path is above the reference path.";
        if (diagnostic && typeof diagnostic.legacy_mean_scenario_difference === "number" && diagnostic.legacy_mean_scenario_difference < -0.01) {
            text += " The earlier statistical baseline often fell below the reference path because the legacy scenario package mixed opaque proxy shifts; the current map instead uses a direct calibration anchored to additional remote-work time saved.";
        }
        return text;
    }
    if (dashboardState.selectedScenario === "digital_distraction_crowds_out") {
        return "Scenario interpretation: this scenario uses ATUS-based screen leisure and digital media minutes as proxies for screen-based distraction. It captures digital leisure broadly, not pure social media use.";
    }
    if (dashboardState.selectedScenario === "online_life_helps_matching") {
        return "Scenario interpretation: this scenario assumes that online social life and digital matching tools make it easier for people to meet or maintain relationships. The adjustment is based on the change in an online-dating search-interest proxy relative to the reference path, so the scenario difference shows whether that placed fertility above or below the reference path.";
    }
    if (dashboardState.selectedScenario === "home_centered_digital_life_increases_care_work") {
        return "Scenario interpretation: this scenario assumes that more digital life - remote work, online services and shopping, and digital entertainment - keeps more activities inside the home and increases unpaid care or household-work burdens. It uses ATUS-based household-work and unpaid-care minutes, with a small offsetting remote-work flexibility credit. Negative values mean the added care burden places fertility below the reference path.";
    }
    return "Scenario interpretation: values show how the selected scenario moves fertility above or below the model-based reference path.";
}

function getCurrentScenarioStateRecords() {
    return lookup.allForecastRecords.filter(function (record) {
        return record.geography_type === "state"
            && record.model === dashboardState.selectedModel
            && record.scenario === dashboardState.selectedScenario
            && Number(record.year) === Number(dashboardState.selectedHorizon);
    });
}

function buildScenarioCalibrationNote() {
    if (dashboardState.selectedScenario !== "remote_work_saves_time") {
        return "";
    }
    const meta = dashboardData.metadata && dashboardData.metadata.remote_work_scenario;
    if (!meta) {
        return "";
    }
    return "The default calibration is anchored to the " + String(meta.default_level || "default") +
        " CPS remote-work fertility benchmark: " + formatNumber(Number(meta.default_births_per_1000_per_1sd), 3) +
        " births per 1,000 women for a 1 SD increase in remote-work exposure.";
}

function buildScenarioCommuteInputNote() {
    if (dashboardState.selectedScenario !== "remote_work_saves_time") {
        return "";
    }
    const rows = getCurrentScenarioStateRecords();
    if (!rows.length) {
        return "";
    }
    const qualityLabels = [];
    const labelMap = {
        observed: "state-specific ACS values",
        state_smoothed: "smoothed state values",
        region_fallback: "region fallback",
        national_fallback: "national fallback",
    };
    rows.forEach(function (row) {
        const key = String(row.commute_minutes_quality_state_year || "");
        const label = labelMap[key];
        if (label && qualityLabels.indexOf(label) === -1) {
            qualityLabels.push(label);
        }
    });
    if (!qualityLabels.length) {
        return "";
    }
    return "Commute-time inputs use " + qualityLabels.join(", ") + ".";
}

function getScenarioDifferenceExtent(scenarioDiffs) {
    if (!scenarioDiffs.length) {
        return { min: NaN, max: NaN };
    }
    const maxAbs = Math.max.apply(null, scenarioDiffs.map(function (value) {
        return Math.abs(Number(value));
    }));
    return {
        min: -maxAbs,
        max: maxAbs,
    };
}

function renderMapSummary() {
    const state = getSelectedState();
    const context = getScenarioContext("state", state.state_fips, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
    const titleNode = document.getElementById("map-summary-title");
    const textNode = document.getElementById("map-summary-text");
    if (!titleNode || !textNode) {
        return;
    }

    titleNode.textContent = state.state_name + " | " + dashboardState.selectedHorizon;
    textNode.textContent = buildSummarySentence("state", state.state_name, getSelectedModel().label, getSelectedScenario().label, dashboardState.selectedModel, dashboardState.selectedScenario, context.scenarioDifference, dashboardState.selectedHorizon, context.mainDriver, false);
}

function renderRankings() {
    const rankingsGrid = document.getElementById("rankings-grid");
    if (!rankingsGrid) {
        return;
    }

    const stateRows = getStateRowsForCurrentView();
    const stateAbove = buildRankingRows(stateRows, "upward");
    const stateBelow = buildRankingRows(stateRows, "downward");
    const closestToReference = buildRankingRows(stateRows, "closest");

    const cards = [
        renderRankingCard({
            title: "Largest upward scenario differences",
            rows: stateAbove,
            emptyMessage: "No states are above the reference path in the current view.",
        }),
        renderRankingCard({
            title: "Largest downward scenario differences",
            rows: stateBelow,
            emptyMessage: "No states are below the reference path in the current view.",
        }),
        renderRankingCard({
            title: "States closest to the reference path",
            rows: closestToReference,
            emptyMessage: "No states are near the reference path in the current view.",
        }),
    ];

    rankingsGrid.innerHTML = cards.join("");
}

function renderStateExplorer() {
    const state = getSelectedState();
    const context = getScenarioContext("state", state.state_fips, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
    const titleNode = document.getElementById("state-explorer-title");
    if (titleNode) {
        titleNode.textContent = state.state_name + " through " + dashboardState.selectedHorizon;
    }

    renderStateLegend();
    updateStateLineNote();

    const takeawayNode = document.getElementById("state-takeaway-text");
    if (!hasRenderableStateContext(context)) {
        renderPlotFallback("state-line-chart", "Unavailable for current selection.");
        if (takeawayNode) {
            takeawayNode.textContent = "Unavailable for current selection.";
        }
        return;
    }

    const chartSpec = buildLineChartSpec("state", state.state_name, context);
    plotChart("state-line-chart", chartSpec.traces, chartSpec.layout);
    if (takeawayNode) {
        takeawayNode.textContent = buildSummarySentence("state", state.state_name, getSelectedModel().label, getSelectedScenario().label, dashboardState.selectedModel, dashboardState.selectedScenario, context.scenarioDifference, dashboardState.selectedHorizon, context.mainDriver, true);
    }
}

function renderStateLegend() {
    const legendNode = document.getElementById("state-line-legend");
    if (!legendNode) {
        return;
    }
    legendNode.innerHTML = [
        '<span class="scenario-inline-chip scenario-inline-chip-observed">Observed</span>',
        '<span class="scenario-inline-chip scenario-inline-chip-reference">' + buildInlineInfoLabelHtml("reference_path") + "</span>",
        '<span class="scenario-inline-chip scenario-inline-chip-scenario">' + buildInlineInfoLabelHtml("scenario_path") + "</span>",
    ].join("");
}

function updateStateLineNote() {
    const noteNode = document.getElementById("state-line-note");
    if (!noteNode) {
        return;
    }
    noteNode.textContent =
        "The line chart shows General Fertility Rate levels: live births per 1,000 women aged " + WOMEN_AGE_LABEL + ".";
}

function renderCompare() {
    const geography = getGeographyDisplay("state", dashboardState.comparePlaceId);
    const scenarioA = lookup.scenarioById.get(dashboardState.compareScenarioA);
    const scenarioB = lookup.scenarioById.get(dashboardState.compareScenarioB);
    const metricGrid = document.getElementById("scenario-compare-metric-grid");
    const textNode = document.getElementById("scenario-compare-text");
    if (!geography || !scenarioA || !scenarioB) {
        renderPlotFallback("scenario-compare-chart", "Unavailable for current selection.");
        if (metricGrid) {
            metricGrid.innerHTML = renderCompareMessageCard("Unavailable for current selection.");
        }
        if (textNode) {
            textNode.textContent = "Unavailable for current selection.";
        }
        return;
    }

    const contextA = getScenarioContext("state", geography.geography_id, dashboardState.selectedModel, dashboardState.compareScenarioA, dashboardState.selectedHorizon);
    const contextB = getScenarioContext("state", geography.geography_id, dashboardState.selectedModel, dashboardState.compareScenarioB, dashboardState.selectedHorizon);
    if (!Number.isFinite(contextA.scenarioDifference) || !Number.isFinite(contextB.scenarioDifference)) {
        renderPlotFallback("scenario-compare-chart", "Unavailable for current selection.");
        if (metricGrid) {
            metricGrid.innerHTML = renderCompareMessageCard("Unavailable for current selection.");
        }
        if (textNode) {
            textNode.textContent = "Unavailable for current selection.";
        }
        return;
    }
    const difference = contextA.scenarioDifference - contextB.scenarioDifference;
    const scenarioADifference = normalizeDifferenceForMeaning(contextA.scenarioDifference);
    const scenarioBDifference = normalizeDifferenceForMeaning(contextB.scenarioDifference);
    const normalizedDifference = normalizeDifferenceForMeaning(difference);

    if (metricGrid) {
        metricGrid.innerHTML = [
            renderCompareMetricCard("Scenario A difference from reference path", scenarioA.label, scenarioADifference),
            renderCompareMetricCard("Scenario B difference from reference path", scenarioB.label, scenarioBDifference),
            renderCompareMetricCard("Difference between Scenario A and Scenario B", "Scenario A difference \u2212 Scenario B difference", normalizedDifference),
        ].join("");
    }

    plotChart("scenario-compare-chart", [{
        type: "bar",
        orientation: "h",
        x: [scenarioADifference, scenarioBDifference, normalizedDifference],
        y: [scenarioA.short_label || scenarioA.label, scenarioB.short_label || scenarioB.label, "Scenario A \u2212 Scenario B"],
        marker: {
            color: ["#1f6b75", "#c86d3f", normalizedDifference >= 0 ? "#21484f" : "#8b3a22"],
        },
        hovertemplate: "%{y}: %{x:+.1f}<extra></extra>",
    }], {
        margin: { t: 8, r: 18, b: 30, l: 110 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        xaxis: {
            title: "Births per 1,000 women aged " + WOMEN_AGE_LABEL,
            zeroline: true,
            zerolinecolor: "#d6cab9",
            gridcolor: "#efe6d8",
        },
        yaxis: {
            automargin: true,
        },
    });

    if (textNode) {
        if (isApproximatelyEqualDifference(difference)) {
            textNode.textContent =
                "In " + geography.geography_name +
                ", the " + scenarioA.label +
                " scenario is approximately equal to the " + scenarioB.label +
                " scenario in " + dashboardState.selectedHorizon + ".";
        } else {
            textNode.textContent =
                "In " + geography.geography_name +
                ", the " + scenarioA.label +
                " scenario is " + formatNumber(Math.abs(difference), 1) +
                " births per 1,000 women aged " + WOMEN_AGE_LABEL + " " + (difference > 0 ? "higher" : "lower") +
                " than the " + scenarioB.label +
                " scenario in " + dashboardState.selectedHorizon + ".";
        }
    }
}

function renderMechanismPanel() {
    const primaryGeo = getPrimarySummaryGeography();
    const context = getScenarioContext(primaryGeo.geography_type, primaryGeo.geography_id, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
    const metrics = mechanismOrder.map(function (item) {
        const raw = context.mechanismScores[item.key] || 0;
        return {
            key: item.key,
            label: item.label,
            value: raw,
            normalized: context.maxMechanismAbs === 0 ? 0 : raw / context.maxMechanismAbs,
        };
    });

    const grid = document.getElementById("scenario-mechanism-grid");
    if (!grid) {
        return;
    }

    grid.innerHTML = metrics.map(function (metric) {
        const directionClass = metric.normalized > 0 ? "is-positive" : metric.normalized < 0 ? "is-negative" : "is-neutral";
        const width = Math.round(Math.abs(metric.normalized) * 100);
        const directionText = metric.normalized > 0 ? "above reference" : metric.normalized < 0 ? "below reference" : "near neutral";
        const arrow = metric.normalized > 0 ? "&uarr;" : metric.normalized < 0 ? "&darr;" : "&rarr;";
        return [
            '<div class="scenario-mechanism-row">',
            '<div class="scenario-mechanism-labels">',
            "<strong>" + metric.label + "</strong>",
            "<span>" + arrow + " pushes " + directionText + "</span>",
            "</div>",
            '<div class="scenario-mechanism-bar-shell">',
            '<span class="scenario-mechanism-bar ' + directionClass + '" style="width:' + width + '%"></span>',
            "</div>",
            "</div>",
        ].join("");
    }).join("");
}

function renderModelStatus() {
    const selectedModel = getSelectedModel();
    const rows = (dashboardData.model_options || []).map(function (model) {
        const metrics = getMetricsForModel("state", model.id);
        const validation = metrics.find(function (row) { return row.split === "validation"; });
        const statusText = !model.available
            ? "Unavailable"
            : model.id === "temporal_neural_net"
                ? "Benchmark only"
                : "Available";
        const meta = validation
            ? "Validation RMSE " + formatNumber(validation.rmse, 2) + " | MAE " + formatNumber(validation.mae, 2)
            : ((dashboardData.metadata && dashboardData.metadata.benchmark_note) || "Metrics not available.");
        return [
            '<div class="scenario-model-row' + (selectedModel && model.id === selectedModel.id ? " is-active" : "") + '">',
            "<strong>" + getModelDisplayLabel(model) + "</strong>",
            "<span>" + statusText + "</span>",
            "<small>" + meta + "</small>",
            "</div>",
        ].join("");
    }).join("");

    const panel = document.getElementById("model-status-panel");
    if (panel) {
        panel.innerHTML = rows;
    }
}

function renderMethodCards() {
    const cards = [
        {
            title: "Interpretation",
            body:
                "<p>This dashboard compares a selected " + buildInlineInfoLabelHtml("scenario_path") + " with the " + buildInlineInfoLabelHtml("reference_path") + " for each state and year. The key map outcome is the " + buildInlineInfoLabelHtml("scenario_difference") + ": scenario path minus reference path.</p><p>Use the top Data &amp; Methods panel for the full data, scenario, and limitations overview. Remote-work scenarios in the current build use direct state-year inputs such as remote-work share and commute time saved rather than an opaque flexibility proxy.</p>",
        },
        {
            title: "Models and validation",
            body:
                "<p>Statistical baseline, tree ML benchmark, and neural network benchmark are predictive tools used for projection under assumptions. The neural network benchmark is exploratory and should be read more cautiously than the statistical baseline.</p>" + buildValidationHtml(),
        },
        {
            title: "Downloads and assumptions",
            body:
                "<p>Downloaded values report " + buildInlineInfoLabelHtml("reference_path") + ", " + buildInlineInfoLabelHtml("scenario_path") + ", and " + buildInlineInfoLabelHtml("scenario_difference") + " where available. Level outputs are reported as " + buildInlineInfoLabelHtml("gfr_level") + " unless otherwise noted.</p><p>The assumption sliders adjust the selected scenario around the precomputed path already loaded in the browser. These outputs are scenario comparisons under assumptions, not causal estimates.</p>",
        },
    ];

    const methodGrid = document.getElementById("method-card-grid");
    if (!methodGrid) {
        return;
    }

    methodGrid.innerHTML = cards.map(function (card, index) {
        if (index === 0) {
            return [
                '<article class="dashboard-card scenario-method-card scenario-method-card-static">',
                '<div class="scenario-method-card-title">' + card.title + "</div>",
                '<div class="scenario-method-body">' + card.body + "</div>",
                "</article>",
            ].join("");
        }
        return [
            '<details class="dashboard-card scenario-method-card">',
            "<summary>" + card.title + "</summary>",
            '<div class="scenario-method-body">' + card.body + "</div>",
            "</details>",
        ].join("");
    }).join("");
}

function buildValidationHtml() {
    const tableHtml = buildMetricsTable("state");
    return [
        "<p>" + buildModelSplitNote() + "</p>",
        "<p><strong>State models</strong></p>",
        tableHtml || "<p>State-model metrics are not available in this bundle.</p>",
        "<p>These benchmarks are predictive tools for comparison and validation under assumptions, not causal estimates.</p>",
    ].join("");
}

function buildMetricsTable(geoType) {
    const availableModels = (dashboardData.model_options || []).filter(function (model) {
        return model.available;
    });

    if (!availableModels.length) {
        return "";
    }

    const rows = availableModels.map(function (model) {
        const metrics = getMetricsForModel(geoType, model.id);
        const validation = metrics.find(function (row) { return row.split === "validation"; });
        const test = metrics.find(function (row) { return row.split === "test"; });
        return [
            "<tr>",
            "<th>" + getModelDisplayLabel(model) + "</th>",
            "<td>" + metricCell(validation, "mae") + "</td>",
            "<td>" + metricCell(validation, "rmse") + "</td>",
            "<td>" + metricCell(test, "mae") + "</td>",
            "<td>" + metricCell(test, "rmse") + "</td>",
            "<td>" + metricCell(test, "mape", true) + "</td>",
            "</tr>",
        ].join("");
    }).join("");

    return [
        '<div class="scenario-metrics-wrap">',
        '<table class="scenario-metrics-table">',
        "<thead><tr><th>Model</th><th>Val. MAE</th><th>Val. RMSE</th><th>Test MAE</th><th>Test RMSE</th><th>Test MAPE</th></tr></thead>",
        "<tbody>" + rows + "</tbody>",
        "</table>",
        "</div>",
    ].join("");
}

function getScenarioContext(geoType, geographyId, modelId, scenarioId, horizonYear) {
    const entity = getGeographyEntity(geoType, geographyId);
    const observedSeries = getObservedSeries(geoType, geographyId);
    const lastObserved = observedSeries.length ? observedSeries[observedSeries.length - 1] : null;
    const referenceRecords = getForecastSeries(geoType, geographyId, modelId, "reference_path").filter(function (row) {
        return row.year <= horizonYear;
    });
    const selectedRecords = getForecastSeries(geoType, geographyId, modelId, scenarioId).filter(function (row) {
        return row.year <= horizonYear;
    });

    const finalReferenceRecord = referenceRecords[referenceRecords.length - 1] || null;
    const finalScenarioRecord = selectedRecords[selectedRecords.length - 1] || finalReferenceRecord;
    const manualAdjustmentFinal = scenarioId === "reference_path"
        ? 0
        : computeManualAdjustment(entity, horizonYear, horizonYear, scenarioId);

    const referenceSeries = buildPathSeries(lastObserved, referenceRecords, false, horizonYear, entity, scenarioId);
    const scenarioSeries = buildPathSeries(lastObserved, selectedRecords, true, horizonYear, entity, scenarioId);

    const mechanismScores = combineMechanismScores(finalScenarioRecord, entity, scenarioId);
    const maxMechanismAbs = Math.max.apply(null, mechanismOrder.map(function (item) {
        return Math.abs(mechanismScores[item.key] || 0);
    }).concat([0]));

    const referenceFinal = finalReferenceRecord ? Number(finalReferenceRecord.reference_path) : (lastObserved ? Number(lastObserved.value) : NaN);
    const scenarioFinal = finalScenarioRecord ? Number(finalScenarioRecord.scenario_path) + manualAdjustmentFinal : (lastObserved ? Number(lastObserved.value) : NaN);
    const precomputedScenarioShift = finalScenarioRecord ? Number(finalScenarioRecord.scenario_difference) : NaN;

    return {
        observedSeries: observedSeries,
        referenceSeries: referenceSeries,
        scenarioSeries: scenarioSeries,
        referenceFinal: referenceFinal,
        scenarioFinal: scenarioFinal,
        scenarioDifference: Number.isFinite(referenceFinal) && Number.isFinite(scenarioFinal) ? scenarioFinal - referenceFinal : NaN,
        scenarioShiftComponent: precomputedScenarioShift,
        manualAdjustmentComponent: manualAdjustmentFinal,
        mechanismScores: mechanismScores,
        maxMechanismAbs: maxMechanismAbs,
        mainDriver: finalScenarioRecord && finalScenarioRecord.main_driver ? finalScenarioRecord.main_driver : findMainDriver(mechanismScores),
    };
}

function buildPathSeries(lastObserved, records, useScenarioPath, horizonYear, entity, scenarioId) {
    const series = [];
    if (lastObserved && Number.isFinite(lastObserved.value)) {
        series.push({
            year: lastObserved.year,
            value: Number(lastObserved.value),
        });
    }

    records.forEach(function (record) {
        const manualAdjustment = useScenarioPath ? computeManualAdjustment(entity, record.year, horizonYear, scenarioId) : 0;
        series.push({
            year: Number(record.year),
            value: Number(useScenarioPath ? record.scenario_path : record.reference_path) + manualAdjustment,
        });
    });
    return series;
}

function getScenarioAdjustmentProfile(scenarioId) {
    return scenarioAdjustmentProfiles[scenarioId] || {
        remote: 1.0,
        distraction: 1.0,
        online: 1.0,
        inPerson: 1.0,
        care: 1.0,
    };
}

function computeManualAdjustment(entity, year, horizonYear, scenarioId) {
    if (scenarioId === "reference_path") {
        return 0;
    }

    const latest = entity && entity.latest ? entity.latest : {};
    const defaults = dashboardData.scenario_defaults || {};
    const deltas = {
        remote: Number(dashboardState.params.remote_work_growth) - Number(defaults.remote_work_growth || 0),
        distraction: Number(dashboardState.params.digital_distraction_growth) - Number(defaults.digital_distraction_growth || 0),
        online: Number(dashboardState.params.digital_social_growth) - Number(defaults.digital_social_growth || 0),
        inPerson: Number(dashboardState.params.face_to_face_change) - Number(defaults.face_to_face_change || 0),
        care: Number(dashboardState.params.gendered_care_penalty) - Number(defaults.gendered_care_penalty || 0),
    };

    const remoteShare = Number(latest.remote_work_share || latest.remote_work_share_state_year || 0);
    const datingProxy = Number(latest.dating_search_interest || 0);
    const populationGrowth = Number(latest.population_growth_rate || 0);
    const genaiProxy = Number(latest.genai_search_interest || 0);
    const sensitivities = {
        remote: 1 + remoteShare * 4,
        distraction: 1 + genaiProxy / 200,
        online: 0.9 + datingProxy / 200,
        inPerson: 0.9 + Math.min(0.5, Math.abs(populationGrowth) * 18),
        care: 1 + remoteShare * 3,
    };
    const profile = getScenarioAdjustmentProfile(scenarioId);

    const rawAdjustment =
        44 * deltas.remote * sensitivities.remote * profile.remote -
        34 * deltas.distraction * sensitivities.distraction * profile.distraction +
        28 * deltas.online * sensitivities.online * profile.online +
        26 * deltas.inPerson * sensitivities.inPerson * profile.inPerson -
        40 * deltas.care * sensitivities.care * profile.care;

    const forecastStartYear = getForecastStartYear();
    const horizonSpan = Math.max(1, horizonYear - forecastStartYear);
    const progress = Math.max(0, year - forecastStartYear) / horizonSpan;
    return clamp(rawAdjustment * progress, -8, 8);
}

function combineMechanismScores(record, entity, scenarioId) {
    const score = {
        mechanism_remote_work_flexibility: Number(record ? record.mechanism_remote_work_flexibility : 0) || 0,
        mechanism_digital_distraction: Number(record ? record.mechanism_digital_distraction : 0) || 0,
        mechanism_online_matching: Number(record ? record.mechanism_online_matching : 0) || 0,
        mechanism_in_person_social: Number(record ? record.mechanism_in_person_social : 0) || 0,
        mechanism_care_burden: Number(record ? record.mechanism_care_burden : 0) || 0,
    };

    if (scenarioId === "reference_path") {
        return score;
    }

    const latest = entity && entity.latest ? entity.latest : {};
    const defaults = dashboardData.scenario_defaults || {};
    const remoteDelta = Number(dashboardState.params.remote_work_growth) - Number(defaults.remote_work_growth || 0);
    const distractionDelta = Number(dashboardState.params.digital_distraction_growth) - Number(defaults.digital_distraction_growth || 0);
    const onlineDelta = Number(dashboardState.params.digital_social_growth) - Number(defaults.digital_social_growth || 0);
    const inPersonDelta = Number(dashboardState.params.face_to_face_change) - Number(defaults.face_to_face_change || 0);
    const careDelta = Number(dashboardState.params.gendered_care_penalty) - Number(defaults.gendered_care_penalty || 0);
    const remoteSensitivity = 1 + Number(latest.remote_work_share || latest.remote_work_share_state_year || 0) * 3;
    const profile = getScenarioAdjustmentProfile(scenarioId);

    score.mechanism_remote_work_flexibility += profile.remote * (15 * remoteDelta * remoteSensitivity + 8 * inPersonDelta);
    score.mechanism_digital_distraction += profile.distraction * (-14 * distractionDelta);
    score.mechanism_online_matching += profile.online * (12 * onlineDelta);
    score.mechanism_in_person_social += profile.inPerson * (11 * inPersonDelta - 3 * distractionDelta);
    score.mechanism_care_burden += profile.care * (-16 * careDelta - 4 * remoteDelta);

    return score;
}

function buildLineChartSpec(geoType, label, context) {
    const traces = [];
    if (context.observedSeries.length) {
        traces.push({
            x: context.observedSeries.map(function (row) { return row.year; }),
            y: context.observedSeries.map(function (row) { return row.value; }),
            mode: "lines+markers",
            name: "Observed",
            line: { color: "#b7aea1", width: 2 },
            marker: { size: 5, color: "#b7aea1" },
            hovertemplate: "Observed %{x}: %{y:.1f}<extra></extra>",
        });
    }

    traces.push({
        x: context.referenceSeries.map(function (row) { return row.year; }),
        y: context.referenceSeries.map(function (row) { return row.value; }),
        mode: "lines",
        name: "Reference path",
        line: { color: "#184f58", width: 3 },
        hovertemplate: "Model-based reference path %{x}: %{y:.1f}<extra></extra>",
    });

    traces.push({
        x: context.scenarioSeries.map(function (row) { return row.year; }),
        y: context.scenarioSeries.map(function (row) { return row.value; }),
        mode: "lines",
        name: getSelectedScenario().label,
        line: { color: "#bf6b3c", width: 3 },
        hovertemplate: "Scenario path %{x}: %{y:.1f}<extra></extra>",
    });

    return {
        traces: traces,
        layout: {
            margin: { t: 8, r: 18, b: 48, l: 56 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            xaxis: {
                title: "",
                tickmode: "linear",
                dtick: 2,
                gridcolor: "#e8e0d5",
                zeroline: false,
            },
            yaxis: {
                title: "General Fertility Rate (births per 1,000 women aged " + WOMEN_AGE_LABEL + ")",
                gridcolor: "#e8e0d5",
                zeroline: false,
            },
            legend: {
                orientation: "h",
                y: -0.18,
            },
            annotations: [{
                x: 1,
                y: 1.08,
                xref: "paper",
                yref: "paper",
                showarrow: false,
                text: label + " | " + geoType.toUpperCase(),
                font: { size: 11, color: "#7a6f63" },
            }],
            shapes: [{
                type: "line",
                x0: dashboardState.selectedHorizon,
                x1: dashboardState.selectedHorizon,
                y0: 0,
                y1: 1,
                yref: "paper",
                line: { color: "#8a8176", width: 1, dash: "dot" },
            }],
        },
    };
}

function syncControls() {
    document.querySelectorAll('[data-setting="state"]').forEach(function (select) {
        select.value = dashboardState.selectedStateFips;
    });
    document.querySelectorAll('[data-setting="model"]').forEach(function (select) {
        select.value = dashboardState.selectedModel;
    });
    document.querySelectorAll('[data-setting="scenario"]').forEach(function (select) {
        select.value = dashboardState.selectedScenario;
    });
    document.querySelectorAll('[data-setting="outcome"]').forEach(function (select) {
        select.value = dashboardState.selectedOutcome;
    });
    document.querySelectorAll('[data-setting="horizon"]').forEach(function (select) {
        select.value = String(dashboardState.selectedHorizon);
    });

    const msaStateFilterSelect = document.getElementById("msa-state-filter-select");
    if (msaStateFilterSelect) {
        msaStateFilterSelect.value = dashboardState.selectedMsaStateFilter;
    }
    const msaSelect = document.getElementById("msa-select");
    if (msaSelect && dashboardState.selectedMsaId) {
        msaSelect.value = dashboardState.selectedMsaId;
    }
    const comparePlaceSelect = document.getElementById("compare-place-select");
    if (comparePlaceSelect && dashboardState.comparePlaceId) {
        comparePlaceSelect.value = dashboardState.comparePlaceId;
    }
    const compareScenarioASelect = document.getElementById("compare-scenario-a-select");
    if (compareScenarioASelect) {
        compareScenarioASelect.value = dashboardState.compareScenarioA;
    }
    const compareScenarioBSelect = document.getElementById("compare-scenario-b-select");
    if (compareScenarioBSelect) {
        compareScenarioBSelect.value = dashboardState.compareScenarioB;
    }
}

function updateSelectionStrips() {
    const strip = document.getElementById("map-selection-strip");
    if (!strip) {
        return;
    }

    const selectedModel = getSelectedModel();
    const selectedScenario = getSelectedScenario();
    const selectedOutcome = getSelectedOutcome();
    strip.innerHTML = [
        '<span class="scenario-headline-segment">' + buildInlineInfoLabelHtml(selectedModel.id, selectedModel.label) + "</span>",
        '<span class="scenario-summary-separator" aria-hidden="true">|</span>',
        '<span class="scenario-headline-segment">' + buildInlineInfoLabelHtml(selectedScenario.id, selectedScenario.label) + "</span>",
        '<span class="scenario-summary-separator" aria-hidden="true">|</span>',
        '<span class="scenario-headline-segment">' + escapeHtml(String(dashboardState.selectedHorizon)) + "</span>",
        '<span class="scenario-summary-separator" aria-hidden="true">|</span>',
        '<span class="scenario-headline-segment">' + buildOutcomeLabelHtml(selectedOutcome) + "</span>",
    ].join("");
}

function initializeSectionNavigation() {
    document.querySelectorAll("[data-section-link]").forEach(function (link) {
        link.addEventListener("click", function (event) {
            event.preventDefault();
            const href = link.getAttribute("href");
            const target = href ? document.querySelector(href) : null;
            if (!target) {
                return;
            }
            target.scrollIntoView({ behavior: "smooth", block: "start" });
            window.setTimeout(updateSectionNavigationState, 80);
        });
    });

    document.querySelectorAll("[data-nav-direction]").forEach(function (button) {
        button.addEventListener("click", function () {
            const direction = button.getAttribute("data-nav-direction");
            const activeIndex = getActiveSectionIndex();
            const targetIndex = direction === "up" ? activeIndex - 1 : activeIndex + 1;
            const targetId = sectionIds[targetIndex];
            const targetSection = targetId ? document.getElementById(targetId) : null;
            if (!targetSection) {
                return;
            }
            targetSection.scrollIntoView({ behavior: "smooth", block: "start" });
        });
    });

    window.addEventListener("scroll", updateSectionNavigationState, { passive: true });
    window.addEventListener("resize", updateSectionNavigationState);
    updateSectionNavigationState();
}

function updateSectionNavigationState() {
    const activeIndex = getActiveSectionIndex();
    const activeId = sectionIds[activeIndex];

    document.querySelectorAll("[data-section-link]").forEach(function (link) {
        const isActive = link.getAttribute("href") === "#" + activeId;
        link.classList.toggle("is-active", isActive);
        if (isActive) {
            link.setAttribute("aria-current", "true");
        } else {
            link.removeAttribute("aria-current");
        }
    });

    document.querySelectorAll("[data-nav-direction]").forEach(function (button) {
        const direction = button.getAttribute("data-nav-direction");
        const disabled = (direction === "up" && activeIndex === 0) ||
            (direction === "down" && activeIndex === sectionIds.length - 1);
        button.disabled = disabled;
        button.setAttribute("aria-disabled", disabled ? "true" : "false");
    });
}

function getActiveSectionIndex() {
    const threshold = 180;
    let activeIndex = 0;
    sectionIds.forEach(function (sectionId, index) {
        const section = document.getElementById(sectionId);
        if (!section) {
            return;
        }
        if (section.getBoundingClientRect().top <= threshold) {
            activeIndex = index;
        }
    });
    return activeIndex;
}

function downloadCurrentView() {
    const rows = getCurrentViewExportRows();
    if (!rows.length) {
        setUtilityStatus("Unavailable for current selection.");
        return;
    }
    downloadCsv(rows, "digital-life-fertility-current-view.csv");
    setUtilityStatus("Current view CSV downloaded.");
}

function downloadAllScenarioData() {
    const allRows = lookup.allForecastRecords.filter(function (record) {
        return record.geography_type === "state";
    }).map(function (record) {
        return buildExportRow(record, {});
    });
    if (!allRows.length) {
        setUtilityStatus("Unavailable for current selection.");
        return;
    }
    downloadCsv(allRows, "digital-life-fertility-all-scenarios.csv");
    setUtilityStatus("All currently loaded state-year scenario data downloaded.");
}

function downloadRankings() {
    const rows = getRankingsExportRows();
    if (!rows.length) {
        setUtilityStatus("Unavailable for current selection.");
        return;
    }
    downloadCsv(rows, "digital-life-fertility-rankings.csv");
    setUtilityStatus("Rankings CSV downloaded.");
}

function copySummary() {
    const primary = getPrimarySummaryGeography();
    const context = getScenarioContext(primary.geography_type, primary.geography_id, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
    const summary = buildSummarySentence(primary.geography_type, primary.geography_name, getSelectedModel().label, getSelectedScenario().label, dashboardState.selectedModel, dashboardState.selectedScenario, context.scenarioDifference, dashboardState.selectedHorizon, context.mainDriver, true);
    if (summary === "Summary unavailable for the current selection.") {
        setUtilityStatus(summary);
        return;
    }
    copyTextToClipboard(summary, "Plain-language summary copied.");
}

function copyCurrentViewLink() {
    const url = new URL(window.location.href);
    url.searchParams.set("geo", "state");
    url.searchParams.set("place", getStateAbbreviation(dashboardState.selectedStateFips));
    url.searchParams.set("model", dashboardState.selectedModel);
    url.searchParams.set("scenario", dashboardState.selectedScenario);
    url.searchParams.set("year", String(dashboardState.selectedHorizon));
    url.searchParams.set("outcome", dashboardState.selectedOutcome);
    copyTextToClipboard(url.toString(), "Shareable link copied.");
}

function updateUrlState() {
    const url = new URL(window.location.href);
    url.searchParams.set("geo", "state");
    url.searchParams.set("place", getStateAbbreviation(dashboardState.selectedStateFips));
    url.searchParams.set("model", dashboardState.selectedModel);
    url.searchParams.set("scenario", dashboardState.selectedScenario);
    url.searchParams.set("year", String(dashboardState.selectedHorizon));
    url.searchParams.set("outcome", dashboardState.selectedOutcome);
    window.history.replaceState({}, "", url.toString());
}

function getCurrentViewExportRows() {
    const currentRows = [];
    getStateRowsForCurrentView().forEach(function (row) {
        currentRows.push(buildExportRow(row, getCurrentAssumptionOverrides()));
    });

    getSelectedStateSeriesRows().forEach(function (row) {
        currentRows.push(buildExportRow(row, getCurrentAssumptionOverrides()));
    });

    return dedupeExportRows(currentRows);
}

function getRankingsExportRows() {
    const rows = [];
    const stateRows = getStateRowsForCurrentView();
    const upwardRows = buildRankingRows(stateRows, "upward");
    const downwardRows = buildRankingRows(stateRows, "downward");
    const closestRows = buildRankingRows(stateRows, "closest");

    upwardRows.forEach(function (row) {
        rows.push(buildExportRow(row, { rank: row.rank, ranking_group: "largest_upward_scenario_differences" }));
    });
    downwardRows.forEach(function (row) {
        rows.push(buildExportRow(row, { rank: row.rank, ranking_group: "largest_downward_scenario_differences" }));
    });
    closestRows.forEach(function (row) {
        rows.push(buildExportRow(row, { rank: row.rank, ranking_group: "closest_to_reference_path" }));
    });

    return rows;
}

function getStateRowsForCurrentView() {
    return getAvailableStates().map(function (state) {
        const context = getScenarioContext("state", state.state_fips, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
        return {
            geography_type: "state",
            geography_id: state.state_fips,
            geography_name: state.state_name,
            state_name: state.state_name,
            state_abbr: state.state_abbr,
            year: dashboardState.selectedHorizon,
            model: dashboardState.selectedModel,
            scenario: dashboardState.selectedScenario,
            reference_path: context.referenceFinal,
            scenario_path: context.scenarioFinal,
            scenario_difference: context.scenarioDifference,
            scenario_shift_component: context.scenarioShiftComponent,
            manual_adjustment_component: context.manualAdjustmentComponent,
            main_driver: context.mainDriver,
        };
    });
}

function getMsaRowsForCurrentView() {
    if (!availability.msa.available) {
        return [];
    }
    return getFilteredMsas().map(function (msa) {
        const context = getScenarioContext("msa", msa.geography_id, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
        return {
            geography_type: "msa",
            geography_id: msa.geography_id,
            geography_name: msa.geography_name,
            state_name: msa.state_name || "",
            msa_name: msa.geography_name,
            year: dashboardState.selectedHorizon,
            model: dashboardState.selectedModel,
            scenario: dashboardState.selectedScenario,
            reference_path: context.referenceFinal,
            scenario_path: context.scenarioFinal,
            scenario_difference: context.scenarioDifference,
            scenario_shift_component: context.scenarioShiftComponent,
            manual_adjustment_component: context.manualAdjustmentComponent,
            main_driver: context.mainDriver,
        };
    });
}

function getSelectedStateSeriesRows() {
    return getForecastSeries("state", dashboardState.selectedStateFips, dashboardState.selectedModel, dashboardState.selectedScenario)
        .filter(function (record) { return record.year <= dashboardState.selectedHorizon; })
        .map(function (record) {
            const entity = getSelectedState();
            const adjustment = dashboardState.selectedScenario === "reference_path" ? 0 : computeManualAdjustment(entity, record.year, dashboardState.selectedHorizon, dashboardState.selectedScenario);
            const referencePath = Number(record.reference_path);
            const scenarioPath = Number(record.scenario_path) + adjustment;
            return {
                geography_type: "state",
                geography_id: dashboardState.selectedStateFips,
                geography_name: entity.state_name,
                state_name: entity.state_name,
                state_abbr: entity.state_abbr,
                year: record.year,
                model: dashboardState.selectedModel,
                scenario: dashboardState.selectedScenario,
                reference_path: referencePath,
                scenario_path: scenarioPath,
                scenario_difference: scenarioPath - referencePath,
                scenario_shift_component: Number(record.scenario_difference),
                manual_adjustment_component: adjustment,
                main_driver: record.main_driver || "",
            };
        });
}

function getSelectedMsaSeriesRows() {
    if (!availability.msa.available || !dashboardState.selectedMsaId) {
        return [];
    }
    const entity = lookup.msaById.get(dashboardState.selectedMsaId);
    return getForecastSeries("msa", dashboardState.selectedMsaId, dashboardState.selectedModel, dashboardState.selectedScenario)
        .filter(function (record) { return record.year <= dashboardState.selectedHorizon; })
        .map(function (record) {
            const adjustment = dashboardState.selectedScenario === "reference_path" ? 0 : computeManualAdjustment(entity, record.year, dashboardState.selectedHorizon, dashboardState.selectedScenario);
            const referencePath = Number(record.reference_path);
            const scenarioPath = Number(record.scenario_path) + adjustment;
            return {
                geography_type: "msa",
                geography_id: dashboardState.selectedMsaId,
                geography_name: entity.geography_name,
                state_name: entity.state_name || "",
                msa_name: entity.geography_name,
                year: record.year,
                model: dashboardState.selectedModel,
                scenario: dashboardState.selectedScenario,
                reference_path: referencePath,
                scenario_path: scenarioPath,
                scenario_difference: scenarioPath - referencePath,
                scenario_shift_component: Number(record.scenario_difference),
                manual_adjustment_component: adjustment,
                main_driver: record.main_driver || "",
            };
        });
}

function buildRankingRows(rows, mode) {
    let filtered = rows.filter(function (row) {
        return Number.isFinite(row.scenario_difference);
    });

    if (mode === "upward") {
        filtered = filtered.filter(function (row) {
            return row.scenario_difference > SCENARIO_DIFFERENCE_TOLERANCE;
        }).sort(function (a, b) {
            return b.scenario_difference - a.scenario_difference || a.geography_name.localeCompare(b.geography_name);
        });
    } else if (mode === "downward") {
        filtered = filtered.filter(function (row) {
            return row.scenario_difference < -SCENARIO_DIFFERENCE_TOLERANCE;
        }).sort(function (a, b) {
            return a.scenario_difference - b.scenario_difference || a.geography_name.localeCompare(b.geography_name);
        });
    } else {
        filtered = filtered.sort(function (a, b) {
            return Math.abs(a.scenario_difference) - Math.abs(b.scenario_difference) || a.geography_name.localeCompare(b.geography_name);
        });
    }

    return filtered.slice(0, 5).map(function (row, index) {
        return Object.assign({}, row, { rank: index + 1 });
    });
}

function buildRankingListHtml(rows) {
    return rows.map(function (row) {
        return [
            '<div class="scenario-ranking-row">',
            '<span class="scenario-ranking-rank">' + row.rank + "</span>",
            '<div class="scenario-ranking-copy">',
            '<strong>' + row.geography_name + "</strong>",
            '<span>' + describeRankingDifference(row.scenario_difference) + "</span>",
            '<small>' + (row.main_driver ? "Main driver: " + row.main_driver : "Main driver unavailable") + "</small>",
            "</div>",
            "</div>",
        ].join("");
    }).join("");
}

function renderRankingCard(config) {
    const primarySection = config.rows.length
        ? buildRankingListHtml(config.rows)
        : '<p class="scenario-ranking-empty">' + config.emptyMessage + "</p>";
    return [
        '<section class="scenario-ranking-card">',
        '<div class="scenario-ranking-head">',
        "<p>State rankings</p>",
        "<h4>" + config.title + "</h4>",
        '<div class="scenario-ranking-unit">births per 1,000 women aged ' + WOMEN_AGE_LABEL + " relative to reference path</div>",
        "</div>",
        '<div class="scenario-ranking-list">' + primarySection + "</div>",
        "</section>",
    ].join("");
}

function renderCompareMetricCard(title, subtitle, value) {
    return [
        '<article class="scenario-compare-metric-card">',
        '<p class="scenario-compare-metric-label">' + title + "</p>",
        '<strong class="scenario-compare-metric-value">' + formatSignedValue(value, 1) + "</strong>",
        '<span class="scenario-compare-metric-subtitle">' + subtitle + "</span>",
        "</article>",
    ].join("");
}

function renderCompareMessageCard(message) {
    return [
        '<article class="scenario-compare-metric-card scenario-compare-metric-card-message">',
        '<p class="scenario-compare-metric-label">Scenario comparison</p>',
        '<span class="scenario-compare-metric-subtitle">' + message + "</span>",
        "</article>",
    ].join("");
}

function buildSummarySentence(geoType, geographyName, modelLabel, scenarioLabel, modelId, scenarioId, difference, year, driver, withCaveat) {
    if (!Number.isFinite(difference) || !geographyName || !modelLabel || !scenarioLabel || !year) {
        return "Summary unavailable for the current selection.";
    }
    if (isApproximatelyEqualDifference(difference)) {
        const nearZeroText =
            "In " + geographyName +
            ", under the " + modelLabel +
            " model, the " + scenarioLabel +
            " scenario is approximately equal to the model-based reference path in " + year + ".";
        const nearZeroExplanation = getScenarioSummaryExplanation(modelId, scenarioId, difference);
        return nearZeroExplanation ? nearZeroText + " " + nearZeroExplanation : nearZeroText;
    }
    const preposition = difference > 0 ? "above" : "below";
    const text =
        "In " + geographyName +
        ", under the " + modelLabel +
        " model, the " + scenarioLabel +
        " scenario is " + formatNumber(Math.abs(difference), 1) +
        " births per 1,000 women aged " + WOMEN_AGE_LABEL + " " + preposition +
        " the model-based reference path in " + year +
        ". The main driver is " + (driver || "not available") + ".";
    const explanation = getScenarioSummaryExplanation(modelId, scenarioId, difference);
    return explanation ? text + " " + explanation : text;
}

function getScenarioSummaryExplanation(modelId, scenarioId, difference) {
    if (!Number.isFinite(difference)) {
        return "";
    }
    const diagnostic = getCurrentScenarioDiagnostic();
    if (scenarioId === "remote_work_saves_time" && diagnostic && diagnostic.diagnostic_reason) {
        return diagnostic.diagnostic_reason;
    }
    return "";
}

function getPrimarySummaryGeography() {
    const state = getSelectedState();
    return {
        geography_type: "state",
        geography_id: state.state_fips,
        geography_name: state.state_name,
    };
}

function normalizeForecastRecords() {
    return (dashboardData.forecast_records || []).map(function (record) {
        const geographyType = record.geography_type === "msa" ? "msa" : "state";
        const geographyId = geographyType === "msa"
            ? String(record.geography_id || record.cbsa_code || record.msa_id || record.cbsa || "")
            : String(record.geography_id || record.state_fips || "").padStart(2, "0");
        if (!geographyId) {
            return null;
        }

        const geographyName = geographyType === "msa"
            ? String(record.geography_name || record.msa_name || record.cbsa_name || geographyId)
            : String(record.geography_name || record.state_name || geographyId);

        const referencePath = toFiniteOrNaN(record.reference_path);
        const scenarioPath = toFiniteOrNaN(record.scenario_path);
        const scenarioDifference = Number.isFinite(referencePath) && Number.isFinite(scenarioPath)
            ? scenarioPath - referencePath
            : toFiniteOrNaN(record.scenario_difference);
        const scenarioShiftComponent = toFiniteOrNaN(record.scenario_shift_component);
        const manualAdjustmentComponent = toFiniteOrNaN(record.manual_adjustment_component);

        return {
            geography_type: geographyType,
            geography_id: geographyId,
            geography_name: geographyName,
            state_fips: geometryValue(record.state_fips, geographyType === "state" ? geographyId : ""),
            state_abbr: record.state_abbr || (geometryValue(record.state_fips, "") ? getStateAbbreviation(String(record.state_fips).padStart(2, "0")) : ""),
            state_name: record.state_name || (geographyType === "state" ? geographyName : ""),
            msa_name: record.msa_name || (geographyType === "msa" ? geographyName : ""),
            cbsa_code: record.cbsa_code || (geographyType === "msa" ? geographyId : ""),
            year: Number(record.year),
            model: record.model || record.model_name || "",
            model_label: record.model_label || "",
            scenario: record.scenario || record.scenario_name || "",
            scenario_label: record.scenario_label || "",
            reference_path: referencePath,
            scenario_path: scenarioPath,
            scenario_difference: scenarioDifference,
            scenario_shift_component: Number.isFinite(scenarioShiftComponent) ? scenarioShiftComponent : scenarioDifference,
            manual_adjustment_component: Number.isFinite(manualAdjustmentComponent) ? manualAdjustmentComponent : 0,
            main_driver: record.main_driver || "",
            commute_minutes_quality_state_year: record.commute_minutes_quality_state_year || "",
            mechanism_remote_work_flexibility: toFiniteOrZero(record.mechanism_remote_work_flexibility),
            mechanism_digital_distraction: toFiniteOrZero(record.mechanism_digital_distraction),
            mechanism_online_matching: toFiniteOrZero(record.mechanism_online_matching),
            mechanism_in_person_social: toFiniteOrZero(record.mechanism_in_person_social),
            mechanism_care_burden: toFiniteOrZero(record.mechanism_care_burden),
            fertility_series: Array.isArray(record.fertility_series) ? record.fertility_series : [],
            latest: record.latest || null,
        };
    }).filter(Boolean);
}

function normalizeMetricRecords() {
    const currentMetrics = Array.isArray(dashboardData.model_metrics) ? dashboardData.model_metrics : [];
    const msaMetrics = Array.isArray(dashboardData.msa_model_metrics) ? dashboardData.msa_model_metrics : [];
    return currentMetrics.concat(msaMetrics).map(function (metric) {
        return {
            geography_type: metric.geography_type || "state",
            model: metric.model || metric.model_name || "",
            split: metric.split || "",
            rmse: toFiniteOrNaN(metric.rmse),
            mae: toFiniteOrNaN(metric.mae),
            mape: toFiniteOrNaN(metric.mape),
            r_squared: toFiniteOrNaN(metric.r_squared),
            n_obs: toFiniteOrNaN(metric.n_obs),
        };
    }).filter(function (metric) {
        return Boolean(metric.model);
    });
}

function getObservedSeries(geoType, geographyId) {
    if (geoType === "msa") {
        const msa = lookup.msaById.get(geographyId);
        const rawSeries = msa && Array.isArray(msa.fertility_series) ? msa.fertility_series : [];
        return rawSeries.map(function (row) {
            return {
                year: Number(row.year),
                value: toFiniteOrNaN(row.general_fertility_rate || row.value),
            };
        }).filter(function (row) {
            return Number.isFinite(row.year) && Number.isFinite(row.value);
        }).sort(function (a, b) { return a.year - b.year; });
    }

    const state = lookup.stateByFips.get(geographyId);
    const rawSeries = state && Array.isArray(state.fertility_series) ? state.fertility_series : [];
    return rawSeries.map(function (row) {
        return {
            year: Number(row.year),
            value: toFiniteOrNaN(row.general_fertility_rate),
        };
    }).filter(function (row) {
        return Number.isFinite(row.year) && Number.isFinite(row.value);
    }).sort(function (a, b) { return a.year - b.year; });
}

function getForecastSeries(geoType, geographyId, modelId, scenarioId) {
    const key = [geoType, geographyId, modelId, scenarioId].join("|");
    return lookup.forecastSeries.get(key) || [];
}

function getGeographyEntity(geoType, geographyId) {
    return geoType === "msa" ? lookup.msaById.get(geographyId) : lookup.stateByFips.get(geographyId);
}

function getGeographyDisplay(geoType, geographyId) {
    if (geoType === "msa") {
        const msa = lookup.msaById.get(geographyId);
        if (!msa) {
            return null;
        }
        return {
            geography_id: msa.geography_id,
            geography_name: msa.geography_name,
            geography_type: "msa",
        };
    }
    const state = lookup.stateByFips.get(geographyId);
    if (!state) {
        return null;
    }
    return {
        geography_id: state.state_fips,
        geography_name: state.state_name,
        geography_type: "state",
    };
}

function getMetricsForModel(geoType, modelId) {
    return lookup.metricsByModelAndGeo.get([geoType, modelId].join("|")) || [];
}

function getAvailableStates() {
    return Array.from(lookup.stateByFips.values()).slice().sort(function (a, b) {
        return a.state_name.localeCompare(b.state_name);
    });
}

function getSelectedState() {
    return lookup.stateByFips.get(dashboardState.selectedStateFips) || getAvailableStates()[0];
}

function getSelectedModel() {
    return lookup.modelById.get(dashboardState.selectedModel) || (dashboardData.model_options || [])[0];
}

function getSelectedScenario() {
    return lookup.scenarioById.get(dashboardState.selectedScenario) || getScenarioChoices()[0];
}

function getSelectedOutcome() {
    const selectedOption = (dashboardData.outcome_options || []).find(function (option) {
        return option.id === dashboardState.selectedOutcome;
    }) || (dashboardData.outcome_options || [])[0];
    return selectedOption
        ? Object.assign({}, selectedOption, { label: getOutcomeLabel(selectedOption.id, selectedOption.label) })
        : selectedOption;
}

function getScenarioChoices() {
    return (dashboardData.scenario_options || []).filter(function (scenario) {
        return scenario.id !== "reference_path";
    });
}

function scenarioChoiceExists(scenarioId) {
    return getScenarioChoices().some(function (scenario) {
        return scenario.id === scenarioId;
    });
}

function getAvailableHorizonYears() {
    const availableYears = (dashboardData.horizon_years || []).slice().sort(function (a, b) {
        return a - b;
    });
    const desiredYears = DESIRED_HORIZON_YEARS.filter(function (year) {
        return availableYears.includes(year);
    });
    return desiredYears.length ? desiredYears : availableYears;
}

function getOutcomeLabel(outcomeId, fallbackLabel) {
    if (outcomeId === "reference_path") {
        return "Reference path (GFR level)";
    }
    if (outcomeId === "scenario_path") {
        return "Scenario path (GFR level)";
    }
    return fallbackLabel || "Scenario difference from reference path";
}

function buildOutcomeLabelHtml(outcome) {
    if (!outcome) {
        return buildInlineInfoLabelHtml("scenario_difference");
    }
    if (outcome.id === "reference_path") {
        return buildInlineInfoLabelHtml("reference_path_level");
    }
    if (outcome.id === "scenario_path") {
        return buildInlineInfoLabelHtml("scenario_path_level");
    }
    return buildInlineInfoLabelHtml("scenario_difference");
}

function renderControlInfoSummaries() {
    document.querySelectorAll(".scenario-control").forEach(function (control) {
        const heading = control.firstElementChild;
        const select = control.querySelector("select");
        if (!heading || !select) {
            return;
        }

        const baseLabel = heading.getAttribute("data-control-label") || normalizeInlineText(heading.textContent);
        heading.setAttribute("data-control-label", baseLabel);
        heading.classList.add("scenario-control-heading");

        const labelTermKey = getControlLabelTermKey(select);
        const selectedInfo = getControlSelectedInfo(select);
        heading.innerHTML = [
            '<span class="scenario-control-heading-main">',
            labelTermKey ? buildInlineInfoLabelHtml(labelTermKey, baseLabel) : escapeHtml(baseLabel),
            "</span>",
            selectedInfo.label
                ? '<span class="scenario-control-selection">' +
                    buildControlSelectedValueHtml(selectedInfo.label, selectedInfo.termKey) +
                    "</span>"
                : "",
        ].join("");
    });
}

function getControlLabelTermKey(select) {
    const setting = select.getAttribute("data-setting");
    if (setting === "model") {
        return "control_model";
    }
    if (setting === "scenario" || select.id === "compare-scenario-a-select" || select.id === "compare-scenario-b-select") {
        return "control_scenario";
    }
    if (setting === "horizon") {
        return "control_horizon";
    }
    if (setting === "outcome") {
        return "control_outcome";
    }
    return "";
}

function getControlSelectedInfo(select) {
    const setting = select.getAttribute("data-setting");
    if (setting === "model") {
        const model = lookup.modelById.get(select.value);
        return {
            label: model ? getModelDisplayLabel(model) : getSelectedOptionText(select),
            termKey: model ? model.id : "",
        };
    }
    if (setting === "scenario" || select.id === "compare-scenario-a-select" || select.id === "compare-scenario-b-select") {
        const scenario = lookup.scenarioById.get(select.value);
        return {
            label: scenario ? scenario.label : getSelectedOptionText(select),
            termKey: scenario ? scenario.id : "",
        };
    }
    if (setting === "outcome") {
        return {
            label: getOutcomeLabel(select.value, getSelectedOptionText(select)),
            termKey: getOutcomeInfoKey(select.value),
        };
    }
    return { label: "", termKey: "" };
}

function getOutcomeInfoKey(outcomeId) {
    if (outcomeId === "reference_path") {
        return "reference_path_level";
    }
    if (outcomeId === "scenario_path") {
        return "scenario_path_level";
    }
    return "scenario_difference";
}

function buildControlSelectedValueHtml(label, termKey) {
    return termKey
        ? buildInlineInfoLabelHtml(termKey, label)
        : escapeHtml(label);
}

function getSelectedOptionText(select) {
    const option = select && select.options
        ? select.options[select.selectedIndex]
        : null;
    return option ? normalizeInlineText(option.textContent) : "";
}

function normalizeInlineText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
}

function buildInlineInfoLabelHtml(termKey, labelOverride) {
    const info = infoTooltipCopy[termKey];
    const label = labelOverride || (info ? info.label : termKey);
    return '<span class="scenario-inline-label">' + escapeHtml(label) + buildInfoTooltipButtonHtml(termKey, label) + "</span>";
}

function buildInfoTooltipButtonHtml(termKey, labelOverride) {
    const info = infoTooltipCopy[termKey];
    if (!info) {
        return "";
    }
    infoTooltipSequence += 1;
    const tooltipId = "scenario-info-tooltip-" + termKey + "-" + infoTooltipSequence;
    const buttonLabel = "Explain " + (labelOverride || info.label);
    return [
        '<button type="button" class="scenario-info-button info-marker" data-tooltip-button data-tooltip-id="' + tooltipId + '" aria-label="' + escapeHtml(buttonLabel) + '" aria-expanded="false" aria-controls="' + tooltipId + '" aria-describedby="' + tooltipId + '">',
        '<span aria-hidden="true"><em>i</em></span>',
        "</button>",
        '<span class="scenario-info-popover" id="' + tooltipId + '" role="tooltip" hidden>',
        "<strong>" + escapeHtml(info.label) + "</strong>",
        escapeHtml(info.description),
        "</span>",
    ].join("");
}

function getForecastStartYear() {
    return lookup.forecastStartYear || dashboardState.selectedHorizon;
}

function getMsaStateOptions() {
    const values = Array.from(lookup.msaById.values())
        .map(function (msa) {
            return {
                value: msa.state_abbr || msa.state_name || "",
                label: msa.state_name || msa.state_abbr || "",
            };
        })
        .filter(function (item) { return item.value && item.label; });

    const seen = new Set();
    return values.filter(function (item) {
        if (seen.has(item.value)) {
            return false;
        }
        seen.add(item.value);
        return true;
    }).sort(function (a, b) {
        return a.label.localeCompare(b.label);
    });
}

function getFilteredMsas() {
    const filter = dashboardState.selectedMsaStateFilter;
    return Array.from(lookup.msaById.values()).filter(function (msa) {
        if (filter === "all") {
            return true;
        }
        return msa.state_abbr === filter || msa.state_name === filter;
    }).sort(function (a, b) {
        return a.geography_name.localeCompare(b.geography_name);
    });
}

function findMainDriver(scores) {
    return mechanismOrder.reduce(function (best, item) {
        const currentValue = Math.abs(scores[item.key] || 0);
        return currentValue > best.value
            ? { key: item.key, value: currentValue, label: item.label }
            : best;
    }, { key: null, value: 0, label: "observed trend" }).label;
}

function buildModelSplitNote() {
    const preferred = lookup.modelById.get("statistical_ridge");
    if (!preferred) {
        return "";
    }
    const trainYears = Array.isArray(preferred.train_years) && preferred.train_years.length
        ? preferred.train_years.join(", ")
        : "not reported";
    const validationYears = Array.isArray(preferred.validation_years) && preferred.validation_years.length
        ? preferred.validation_years.join(", ")
        : "not reported";
    const testYears = Array.isArray(preferred.test_years) && preferred.test_years.length
        ? preferred.test_years.join(", ")
        : "not reported";
    return "Current exported backtests use train years " + trainYears + ", validation years " + validationYears + ", and test years " + testYears + ".";
}

function getModelDisplayLabel(model) {
    return model && model.label ? model.label : "Model";
}

function metricCell(row, key, isPercent) {
    if (!row || !Number.isFinite(Number(row[key]))) {
        return "n/a";
    }
    return isPercent ? formatPercent(Number(row[key])) : formatNumber(Number(row[key]), 2);
}

function plotChart(containerId, traces, layout, onReady) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    window.Plotly.react(container, traces, layout, {
        displayModeBar: false,
        responsive: true,
    }).then(function () {
        if (typeof onReady === "function") {
            onReady(container);
        }
    }).catch(function () {
        renderPlotFallback(containerId, "This chart could not be rendered for the selected view.");
    });
}

function renderPlotFallback(containerId, message) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    container.innerHTML = '<div class="scenario-fallback">' + message + "</div>";
}

function renderGlobalError(message) {
    const main = document.querySelector("main");
    if (!main) {
        return;
    }
    main.innerHTML = '<section class="dashboard-card scenario-fallback-shell"><p>' + message + "</p></section>";
}

function buildExportRow(record, overrides) {
    const extra = overrides || {};
    return {
        rank: valueOrBlank(extra.rank),
        ranking_group: valueOrBlank(extra.ranking_group),
        geography_type: valueOrBlank(record.geography_type),
        state_id: valueOrBlank(record.state_id || record.geography_id || record.state_fips),
        state_abbr: valueOrBlank(record.state_abbr || ""),
        state_name: valueOrBlank(record.state_name || ""),
        year: valueOrBlank(record.year),
        model: valueOrBlank(record.model),
        scenario: valueOrBlank(record.scenario),
        reference_path: valueOrBlank(record.reference_path),
        scenario_path: valueOrBlank(record.scenario_path),
        scenario_difference: valueOrBlank(record.scenario_difference),
        scenario_shift_component: valueOrBlank(record.scenario_shift_component),
        manual_adjustment_component: valueOrBlank(record.manual_adjustment_component),
        main_driver: valueOrBlank(record.main_driver || ""),
        remote_work_assumption: valueOrBlank(extra.remote_work_assumption),
        digital_distraction_assumption: valueOrBlank(extra.digital_distraction_assumption),
        online_social_life_assumption: valueOrBlank(extra.online_social_life_assumption),
        face_to_face_assumption: valueOrBlank(extra.face_to_face_assumption),
        care_burden_assumption: valueOrBlank(extra.care_burden_assumption),
    };
}

function getCurrentAssumptionOverrides() {
    return {
        remote_work_assumption: dashboardState.params.remote_work_growth,
        digital_distraction_assumption: dashboardState.params.digital_distraction_growth,
        online_social_life_assumption: dashboardState.params.digital_social_growth,
        face_to_face_assumption: dashboardState.params.face_to_face_change,
        care_burden_assumption: dashboardState.params.gendered_care_penalty,
    };
}

function downloadCsv(rows, filename) {
    const headers = [
        "rank",
        "ranking_group",
        "geography_type",
        "state_id",
        "state_abbr",
        "state_name",
        "year",
        "model",
        "scenario",
        "reference_path",
        "scenario_path",
        "scenario_difference",
        "scenario_shift_component",
        "manual_adjustment_component",
        "main_driver",
        "remote_work_assumption",
        "digital_distraction_assumption",
        "online_social_life_assumption",
        "face_to_face_assumption",
        "care_burden_assumption",
    ];

    const lines = [headers.join(",")].concat(rows.map(function (row) {
        return headers.map(function (header) {
            return escapeCsvValue(row[header]);
        }).join(",");
    }));

    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function escapeCsvValue(value) {
    const text = value === null || typeof value === "undefined" ? "" : String(value);
    if (text.indexOf(",") >= 0 || text.indexOf('"') >= 0 || text.indexOf("\n") >= 0) {
        return '"' + text.replace(/"/g, '""') + '"';
    }
    return text;
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function copyTextToClipboard(text, successMessage) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
            setUtilityStatus(successMessage);
        }).catch(function () {
            fallbackCopy(text, successMessage);
        });
        return;
    }
    fallbackCopy(text, successMessage);
}

function fallbackCopy(text, successMessage) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "readonly");
    textarea.style.position = "absolute";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand("copy");
        setUtilityStatus(successMessage);
    } catch (error) {
        setUtilityStatus("Copy failed in this browser session.");
    }
    document.body.removeChild(textarea);
}

function setUtilityStatus(message) {
    const statusNode = document.getElementById("dashboard-utility-status");
    if (statusNode) {
        statusNode.textContent = message;
    }
}

function updateUtilityActionState() {
    setButtonDisabled("download-current-view-button", getCurrentViewExportRows().length === 0);
    setButtonDisabled("download-all-data-button", !lookup.allForecastRecords.some(function (record) {
        return record.geography_type === "state";
    }));
    setButtonDisabled("download-rankings-button", getRankingsExportRows().length === 0);
    setButtonDisabled("copy-summary-button", getCurrentSummaryText() === "Summary unavailable for the current selection.");
    setButtonDisabled("copy-link-button", !lookup.stateByFips.has(dashboardState.selectedStateFips));
}

function setButtonDisabled(elementId, disabled) {
    const button = document.getElementById(elementId);
    if (!button) {
        return;
    }
    button.disabled = Boolean(disabled);
    button.setAttribute("aria-disabled", disabled ? "true" : "false");
}

function getCurrentSummaryText() {
    const primary = getPrimarySummaryGeography();
    const context = getScenarioContext(primary.geography_type, primary.geography_id, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
    return buildSummarySentence(primary.geography_type, primary.geography_name, getSelectedModel().label, getSelectedScenario().label, dashboardState.selectedModel, dashboardState.selectedScenario, context.scenarioDifference, dashboardState.selectedHorizon, context.mainDriver, true);
}

function dedupeExportRows(rows) {
    const seen = new Set();
    return rows.filter(function (row) {
        const key = [
            row.ranking_group || "",
            row.rank || "",
            row.geography_type || "",
            row.state_id || "",
            row.year || "",
            row.model || "",
            row.scenario || "",
        ].join("|");
        if (seen.has(key)) {
            return false;
        }
        seen.add(key);
        return true;
    });
}

function resolveStateIdentifier(value) {
    const normalized = String(value || "").trim();
    if (lookup.stateByFips.has(normalized.padStart(2, "0"))) {
        return normalized.padStart(2, "0");
    }
    const state = lookup.stateByAbbr.get(normalized.toUpperCase());
    return state ? state.state_fips : "";
}

function getStateAbbreviation(stateFips) {
    const state = lookup.stateByFips.get(String(stateFips).padStart(2, "0"));
    return state ? state.state_abbr : stateFips;
}

function geometryValue(value, fallback) {
    return typeof value === "undefined" || value === null ? fallback : value;
}

function toFiniteOrNaN(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : NaN;
}

function toFiniteOrZero(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
}

function valueOrBlank(value) {
    return value === null || typeof value === "undefined" || (typeof value === "number" && !Number.isFinite(value))
        ? ""
        : value;
}

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function formatNumber(value, digits) {
    if (!Number.isFinite(value)) {
        return "n/a";
    }
    return getRoundedDisplayValue(value, digits).toFixed(digits);
}

function formatPercent(value) {
    if (!Number.isFinite(value)) {
        return "n/a";
    }
    return (value * 100).toFixed(1) + "%";
}

function formatSignedValue(value, digits) {
    if (!Number.isFinite(value)) {
        return "n/a";
    }
    const cleanValue = getRoundedDisplayValue(value, digits);
    const prefix = cleanValue > 0 ? "+" : "";
    return prefix + cleanValue.toFixed(digits);
}

function formatSignedPercentPoints(value) {
    if (!Number.isFinite(value)) {
        return "n/a";
    }
    const prefix = value > 0 ? "+" : "";
    return prefix + (value * 100).toFixed(1) + " pp";
}

function getRoundedDisplayValue(value, digits) {
    const rounded = Number(Number(value).toFixed(digits));
    return Object.is(rounded, -0) ? 0 : rounded;
}

function normalizeDifferenceForMeaning(value) {
    if (!Number.isFinite(value)) {
        return value;
    }
    return Math.abs(value) < SCENARIO_DIFFERENCE_TOLERANCE ? 0 : value;
}

function describeRankingDifference(value) {
    const cleanValue = normalizeDifferenceForMeaning(value);
    if (!Number.isFinite(cleanValue)) {
        return "Unavailable.";
    }
    if (cleanValue === 0) {
        return "Near the reference path.";
    }
    const direction = cleanValue > 0 ? "above" : "below";
    return (
        formatSignedValue(cleanValue, RANKING_DISPLAY_DIGITS) +
        " births per 1,000 women aged " +
        WOMEN_AGE_LABEL +
        " " +
        direction +
        " the reference path."
    );
}

function isApproximatelyEqualDifference(value) {
    return Number.isFinite(value) && Math.abs(value) < SCENARIO_DIFFERENCE_TOLERANCE;
}

function getScenarioDirectionNote(scenarioDiffs) {
    if (dashboardState.selectedScenario !== "remote_work_saves_time" || !scenarioDiffs.length) {
        return "";
    }
    const anyAbove = scenarioDiffs.some(function (value) {
        return Number(value) > SCENARIO_DIFFERENCE_TOLERANCE;
    });
    const anyBelow = scenarioDiffs.some(function (value) {
        return Number(value) < -SCENARIO_DIFFERENCE_TOLERANCE;
    });
    if (!anyAbove && anyBelow) {
        return "In this view, the selected scenario still sits below the reference path in every state, which reflects the current scenario construction rather than causal evidence that remote work lowers fertility.";
    }
    if (anyAbove && !anyBelow) {
        return "In this view, the remote-work time-saved scenario lifts fertility above the reference path in every state.";
    }
    return "";
}

function hasRenderableStateContext(context) {
    return Boolean(
        context &&
        (context.observedSeries.length || context.referenceSeries.length || context.scenarioSeries.length) &&
        Number.isFinite(context.referenceFinal) &&
        Number.isFinite(context.scenarioFinal)
    );
}

function exposeDashboardValidation() {
    window.runFertilityDashboardValidation = runDashboardValidation;
}

function runDashboardValidation() {
    const report = {
        requestedModel: new URLSearchParams(window.location.search).get("model") || "",
        appliedModel: dashboardState.selectedModel,
        urlModelRespected: true,
        dropdownOnlyModels: [],
        dataOnlyModels: [],
        metricOnlyModels: [],
        modelsMissingMetrics: [],
        coverageFailures: [],
        missingValueRecords: [],
        identityFailures: [],
        selectedViewConsistencyFailures: [],
    };

    const modelIds = new Set((dashboardData.model_options || []).map(function (model) { return model.id; }));
    const metricModelIds = new Set((dashboardData.model_metrics || []).map(function (metric) {
        return metric.model || metric.model_name || "";
    }).filter(Boolean));
    const expectedStateCount = getAvailableStates().length;
    const stateCounts = new Map();

    if (report.requestedModel && modelIds.has(report.requestedModel)) {
        report.urlModelRespected = report.requestedModel === report.appliedModel;
    }

    lookup.allForecastRecords.forEach(function (record) {
        if (!modelIds.has(record.model)) {
            report.dataOnlyModels.push(record.model);
        }

        ["reference_path", "scenario_path", "scenario_difference"].forEach(function (field) {
            if (!Number.isFinite(Number(record[field]))) {
                report.missingValueRecords.push({
                    model: record.model,
                    scenario: record.scenario,
                    geography_id: record.geography_id,
                    year: record.year,
                    field: field,
                    value: record[field],
                });
            }
        });

        const identityError = Math.abs((Number(record.scenario_path) - Number(record.reference_path)) - Number(record.scenario_difference));
        if (identityError > 1e-8) {
            report.identityFailures.push({
                model: record.model,
                scenario: record.scenario,
                geography_id: record.geography_id,
                year: record.year,
                identity_error: identityError,
            });
        }

        if (record.geography_type === "state") {
            const key = [record.model, record.scenario, record.year].join("|");
            stateCounts.set(key, (stateCounts.get(key) || 0) + 1);
        }
    });

    (dashboardData.model_options || []).forEach(function (model) {
        if (!lookup.allForecastRecords.some(function (record) { return record.model === model.id; })) {
            report.dropdownOnlyModels.push(model.id);
        }
        if (!metricModelIds.has(model.id)) {
            report.modelsMissingMetrics.push(model.id);
        }
    });

    Array.from(metricModelIds).forEach(function (modelId) {
        if (!modelIds.has(modelId)) {
            report.metricOnlyModels.push(modelId);
        }
    });

    stateCounts.forEach(function (count, key) {
        if (count !== expectedStateCount) {
            const parts = key.split("|");
            report.coverageFailures.push({
                model: parts[0],
                scenario: parts[1],
                year: Number(parts[2]),
                state_count: count,
                expected_state_count: expectedStateCount,
            });
        }
    });

    const selectedState = getSelectedState();
    const mapRow = getStateRowsForCurrentView().find(function (row) {
        return row.geography_id === selectedState.state_fips;
    });
    const seriesRow = getSelectedStateSeriesRows().find(function (row) {
        return Number(row.year) === Number(dashboardState.selectedHorizon);
    });
    const context = getScenarioContext("state", selectedState.state_fips, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
    const summary = getCurrentSummaryText();
    const currentViewRows = getCurrentViewExportRows().filter(function (row) {
        return row.state_id === selectedState.state_fips && Number(row.year) === Number(dashboardState.selectedHorizon);
    });
    const rankingsRows = getRankingsExportRows().filter(function (row) {
        return row.state_id === selectedState.state_fips && Number(row.year) === Number(dashboardState.selectedHorizon);
    });

    if (mapRow && seriesRow) {
        ["reference_path", "scenario_path", "scenario_difference"].forEach(function (field) {
            const mapValue = Number(mapRow[field]);
            const seriesValue = Number(seriesRow[field]);
            const contextValue = Number(
                field === "reference_path"
                    ? context.referenceFinal
                    : field === "scenario_path"
                        ? context.scenarioFinal
                        : context.scenarioDifference
            );
            if (Math.abs(mapValue - seriesValue) > 1e-8 || Math.abs(mapValue - contextValue) > 1e-8) {
                report.selectedViewConsistencyFailures.push({
                    field: field,
                    map_value: mapValue,
                    series_value: seriesValue,
                    context_value: contextValue,
                });
            }
            currentViewRows.forEach(function (row) {
                const exportValue = Number(row[field]);
                if (Math.abs(exportValue - mapValue) > 1e-8) {
                    report.selectedViewConsistencyFailures.push({
                        field: field,
                        map_value: mapValue,
                        export_value: exportValue,
                        source: "current_view_download",
                    });
                }
            });
            rankingsRows.forEach(function (row) {
                if (field !== "scenario_difference") {
                    return;
                }
                const rankingValue = Number(row[field]);
                if (Math.abs(rankingValue - mapValue) > 1e-8) {
                    report.selectedViewConsistencyFailures.push({
                        field: field,
                        map_value: mapValue,
                        ranking_value: rankingValue,
                        source: "rankings_download",
                    });
                }
            });
        });
    }

    if (summary === "Summary unavailable for the current selection.") {
        report.selectedViewConsistencyFailures.push({
            field: "summary",
            issue: "Summary unavailable for the current selection.",
        });
    }

    console.groupCollapsed("Digital Life & Fertility dashboard validation");
    console.log("Validation summary", {
        requestedModel: report.requestedModel || "(none)",
        appliedModel: report.appliedModel,
        urlModelRespected: report.urlModelRespected,
        dropdownOnlyModels: report.dropdownOnlyModels.length,
        dataOnlyModels: report.dataOnlyModels.length,
        metricOnlyModels: report.metricOnlyModels.length,
        modelsMissingMetrics: report.modelsMissingMetrics.length,
        coverageFailures: report.coverageFailures.length,
        missingValueRecords: report.missingValueRecords.length,
        identityFailures: report.identityFailures.length,
        selectedViewConsistencyFailures: report.selectedViewConsistencyFailures.length,
    });
    if (report.coverageFailures.length) {
        console.table(report.coverageFailures);
    }
    if (report.missingValueRecords.length) {
        console.table(report.missingValueRecords.slice(0, 25));
    }
    if (report.identityFailures.length) {
        console.table(report.identityFailures.slice(0, 25));
    }
    if (report.selectedViewConsistencyFailures.length) {
        console.table(report.selectedViewConsistencyFailures.slice(0, 25));
    }
    console.groupEnd();

    return report;
}
