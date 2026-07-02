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
const MSA_SCENARIO_DIFFERENCE_TOLERANCE = 0.005;
const RANKING_DISPLAY_DIGITS = 3;
const STATE_SUMMARY_DISPLAY_DIGITS = 2;
const MSA_SUMMARY_DISPLAY_DIGITS = 3;
const DESIRED_HORIZON_YEARS = [2030, 2035, 2040, 2045, 2050, 2055, 2060];
const DEFAULT_HORIZON_YEAR = 2035;
const CHOROPLETH_MIN_DOMAIN_SPAN = 0.001;
const CHOROPLETH_RELATIVE_PADDING_FACTOR = 0.001;
const WOMEN_AGE_LABEL = "15\u201344";
const FALLBACK_STATE_MODEL_ID = "statistical_ridge";
const FALLBACK_MSA_MODEL_ID = "tree_gradient_boosting";

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

function titleCaseSegment(text) {
    return String(text || "")
        .toLowerCase()
        .replace(/(^|[\s\-\/\(\[])["']?([a-z])/g, function (match, prefix, letter) {
            return prefix + letter.toUpperCase();
        });
}

function formatMsaDisplayName(name) {
    const raw = String(name || "").trim();
    if (!raw) {
        return "";
    }
    const parts = raw.split(",");
    const metroName = titleCaseSegment(parts.shift() || "");
    const stateParts = parts.map(function (part) {
        return String(part || "").trim().toUpperCase();
    }).filter(Boolean);
    return [metroName].concat(stateParts).join(", ");
}

function formatCbsaTypeLabel(cbsaType) {
    if (cbsaType === "metropolitan") {
        return "Metropolitan";
    }
    if (cbsaType === "micropolitan") {
        return "Micropolitan";
    }
    return "Unknown / not labeled";
}

function getMsaCbsaContextNote() {
    return String(
        dashboardData
        && dashboardData.metadata
        && dashboardData.metadata.msa_cbsa_context_note
        || ""
    ).trim();
}

function getMsaCoverageExplanation() {
    return "The analysis is conducted at the MSA level. County shapes are used only as a display layer, so counties inside the same estimated MSA receive the same MSA-level value.";
}

const MSA_UNAVAILABLE_MESSAGE =
    "MSA-level projections require county-to-MSA fertility inputs and precomputed MSA scenario outputs. These data are not available in the current repository.";

const MSA_RANKINGS_UNAVAILABLE_MESSAGE =
    "MSA rankings will appear once MSA-level scenario outputs are available.";

const MSA_GEOMETRY_UNAVAILABLE_MESSAGE =
    "MSA map geometry is unavailable. MSA results are still available in the table and chart.";

const MSA_RESULTS_UNAVAILABLE_MESSAGE =
    "No MSA-level scenario effects are available for this selected model, scenario, outcome, and year.";

const COUNTY_GEOMETRY_UNAVAILABLE_MESSAGE =
    "County display geometry is unavailable. MSA results are still available in the selector, chart, and downloads.";

const COUNTY_GEOMETRY_LOADING_MESSAGE =
    "Preparing county display geometry for the MSA view.";

const sectionIds = [
    "us-state",
    "compare",
    "assumptions",
    "method",
];

const MSA_GEOMETRY_ID_KEYS = [
    "geography_id",
    "cbsa_code",
    "cbsa",
    "cbsafp",
    "CBSAFP",
    "GEOID",
    "GEOIDCBSA",
    "geoid",
    "metro_id",
];

const dashboardState = {
    selectedGeoType: "state",
    selectedStateFips: "06",
    selectedMsaId: "",
    selectedMsaStateFilter: "all",
    selectedModel: FALLBACK_STATE_MODEL_ID,
    modelExplicitlyChosen: false,
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
    countyDisplayByFips: new Map(),
    countyDisplayRows: [],
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

const FORECAST_BOUND_FLOOR = 5;
const FORECAST_BOUND_CEILING = 150;

const scenarioStoryIcons = {
    remote_work_saves_time: "fa-briefcase",
    digital_distraction_crowds_out: "fa-desktop",
    online_life_helps_matching: "fa-users",
    home_centered_digital_life_increases_care_work: "fa-house",
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
        label: "Display metric",
        description: "Choose which GFR-based display metric to show: change relative to the reference path or projected levels.",
    },
    statistical_ridge: {
        label: "Statistical baseline",
        description: "A traditional statistical projection based on observed fertility trends and available state-level predictors. In the State view, it is the primary benchmark because it is transparent, stable, and performs well out of sample.",
    },
    tree_gradient_boosting: {
        label: "Tree ML benchmark",
        description: "A tree-based machine-learning benchmark that captures nonlinear relationships. In the State view, it is shown as a robustness benchmark with strong held-out accuracy. In the Metro patterns view, it is the preferred display model because it preserves metropolitan variation better.",
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
    model_reliability_warning: {
        label: "Why this warning?",
        description: "This label is based on validation accuracy, geography coverage, and whether forecasts hit the model's lower or upper bound. When many forecasts hit a bound, maps and rankings can become less informative because place-to-place differences are compressed.",
    },
    state_primary_forecast_view: {
        label: "Why State is primary",
        description: "The State view is the primary forecast view because state-level models are more stable out of sample. The statistical baseline is the primary State benchmark because it is transparent, stable, and performs well out of sample, while Tree ML is shown as a robustness benchmark.",
    },
};

let activeInfoTooltipId = "";
let infoTooltipSequence = 0;
let infoTooltipEventsBound = false;
let utilityPanelEventsBound = false;
let countyGeometryLoadPromise = null;
let countyGeometryLoadError = "";

document.addEventListener("DOMContentLoaded", function () {
    if (!dashboardData) {
        renderGlobalError("Dashboard data bundle could not be found.");
        return;
    }
    if (typeof window.Plotly === "undefined") {
        renderGlobalError("The Plotly chart library did not load, so the interactive dashboard cannot render.");
        return;
    }

    logDashboardDebug("Dashboard JS starting", {
        href: window.location.href,
    });
    initializeLookups();
    initializeAvailability();
    initializeState();
    applyUrlState();
    populateControls();
    renderHeroStats();
    renderScenarioStories();
    renderAssumptionSliders();
    bindEvents();
    initializeMsaCaptionToggle();
    bindInfoTooltips();
    initializeSectionNavigation();
    exposeDashboardValidation();
    renderDashboard();
});

function initializeLookups() {
    const states = Array.isArray(dashboardData.states) ? dashboardData.states : [];
    const msas = Array.isArray(dashboardData.msas) ? dashboardData.msas : [];
    const countyDisplayRows = decodeCountyDisplayRecords();
    states
        .filter(function (state) { return String(state.state_fips || "") !== "00"; })
        .forEach(function (state) {
            lookup.stateByFips.set(String(state.state_fips).padStart(2, "0"), state);
            lookup.stateByAbbr.set(String(state.state_abbr || "").toUpperCase(), state);
        });
    msas.forEach(function (msa) {
        const geographyId = String(msa.geography_id || msa.cbsa_code || "");
        if (!geographyId) {
            return;
        }
        lookup.msaById.set(geographyId, {
            geography_id: geographyId,
            geography_name: formatMsaDisplayName(msa.geography_name || msa.msa_name || geographyId),
            cbsa_code: msa.cbsa_code || geographyId,
            msa_name: formatMsaDisplayName(msa.msa_name || msa.geography_name || geographyId),
            cbsa_type: msa.cbsa_type || "unknown",
            state_fips: msa.state_fips || "",
            state_name: msa.state_name || "",
            state_abbr: msa.state_abbr || "",
            region: msa.region || "",
            fertility_series: Array.isArray(msa.fertility_series) ? msa.fertility_series : [],
            latest: msa.latest || {},
        });
    });
    lookup.countyDisplayByFips.clear();
    lookup.countyDisplayRows = countyDisplayRows.map(function (row) {
        const countyFips = String(row.county_fips || "").padStart(5, "0");
        const stateFips = String(row.state_fips || countyFips.slice(0, 2) || "").padStart(2, "0");
        const county = {
            county_fips: countyFips,
            county_name: String(row.county_name || countyFips),
            state_fips: stateFips,
            state_abbr: String(row.state_abbr || getStateAbbreviation(stateFips) || ""),
            state_name: String(row.state_name || (lookup.stateByFips.get(stateFips) || {}).state_name || ""),
            cbsa_code: String(row.cbsa_code || ""),
            cbsa_name: formatMsaDisplayName(row.cbsa_name || ""),
            cbsa_type: String(row.cbsa_type || ""),
            estimate_status: String(row.estimate_status || "outside_cbsa"),
            estimated_geography_id: String(row.estimated_geography_id || ""),
            estimated_geography_name: formatMsaDisplayName(row.estimated_geography_name || row.cbsa_name || ""),
        };
        lookup.countyDisplayByFips.set(county.county_fips, county);
        return county;
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
        if (geoType === "msa") {
            const msaEntity = lookup.msaById.get(geographyId);
            if (msaEntity) {
                record.geography_name = msaEntity.geography_name || record.geography_name || geographyId;
                record.cbsa_code = msaEntity.cbsa_code || record.cbsa_code || geographyId;
                record.msa_name = msaEntity.msa_name || record.msa_name || record.geography_name;
                record.cbsa_type = msaEntity.cbsa_type || record.cbsa_type || "unknown";
                record.state_fips = msaEntity.state_fips || record.state_fips || "";
                record.state_abbr = msaEntity.state_abbr || record.state_abbr || "";
                record.state_name = msaEntity.state_name || record.state_name || "";
            }
        }
        const key = [geoType, geographyId, record.model, record.scenario].join("|");
        if (!lookup.forecastSeries.has(key)) {
            lookup.forecastSeries.set(key, []);
        }
        lookup.forecastSeries.get(key).push(record);
        lookup.recordsByGeoType.get(geoType).push(record);

        if (geoType === "msa" && !lookup.msaById.has(geographyId)) {
            lookup.msaById.set(geographyId, {
                geography_id: geographyId,
                geography_name: formatMsaDisplayName(record.geography_name),
                cbsa_code: record.cbsa_code || geographyId,
                msa_name: formatMsaDisplayName(record.msa_name || record.geography_name),
                cbsa_type: record.cbsa_type || "unknown",
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
    lookup.forecastStartYear = allYears.length ? finiteArrayMin(allYears) : null;

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
    const hasMsaData = lookup.msaById.size > 0 && msaRecords.length > 0;
    availability.msa.available = hasMsaData;
    availability.msa.reason = hasMsaData ? "" : (explicitReason || MSA_UNAVAILABLE_MESSAGE);
}

function initializeState() {
    const firstState = getAvailableStates()[0];
    const firstMsa = getFilteredMsas()[0];
    if (firstState) {
        dashboardState.selectedStateFips = firstState.state_fips;
    }
    if (firstMsa) {
        dashboardState.selectedMsaId = firstMsa.geography_id;
    }

    dashboardState.selectedModel = getPreferredModelForGeo("state");
    dashboardState.modelExplicitlyChosen = false;

    const availableScenarios = getScenarioControlChoices();
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

function getReliabilityReport() {
    return dashboardData && dashboardData.model_reliability_diagnostics
        ? dashboardData.model_reliability_diagnostics
        : {};
}

function getDefaultModelIdForGeo(geoType) {
    const report = getReliabilityReport();
    const defaults = report.default_model_by_geo || {};
    return defaults[geoType] || (geoType === "msa" ? FALLBACK_MSA_MODEL_ID : FALLBACK_STATE_MODEL_ID);
}

function getModelReliabilitySummary(geoType, modelId) {
    const report = getReliabilityReport();
    const rows = Array.isArray(report.summary) ? report.summary : [];
    return rows.find(function (row) {
        return row
            && row.geography_level === geoType
            && row.model === modelId;
    }) || null;
}

function getPreferredModelForGeo(geoType) {
    const preferredId = getDefaultModelIdForGeo(geoType);
    const models = dashboardData.model_options || [];
    const preferred = models.find(function (model) {
        return model.id === preferredId && model.available;
    });
    if (preferred) {
        return preferred.id;
    }
    const availableModel = models.find(function (model) {
        return model.available;
    });
    return availableModel ? availableModel.id : dashboardState.selectedModel;
}

function applyPreferredModelForGeo(geoType) {
    if (dashboardState.modelExplicitlyChosen) {
        return;
    }
    dashboardState.selectedModel = getPreferredModelForGeo(geoType);
}

function setSelectedGeoType(geoType) {
    dashboardState.selectedGeoType = geoType === "msa" && availability.msa.available
        ? "msa"
        : "state";
    applyPreferredModelForGeo(dashboardState.selectedGeoType);
}

function applyUrlState() {
    const params = new URLSearchParams(window.location.search);
    const geo = params.get("geo");
    const place = params.get("place");
    const model = params.get("model");
    const scenario = resolveScenarioId(params.get("scenario"));
    const year = Number(params.get("year"));
    const outcome = params.get("outcome");

    dashboardState.modelExplicitlyChosen = false;
    setSelectedGeoType("state");
    dashboardState.compareGeoType = "state";
    if ((geo === "msa" || geo === "cbsa") && availability.msa.available) {
        setSelectedGeoType("msa");
    }

    if (place) {
        if (dashboardState.selectedGeoType === "msa" && lookup.msaById.has(place)) {
            dashboardState.selectedMsaId = place;
            dashboardState.comparePlaceId = place;
        } else {
            const normalizedState = resolveStateIdentifier(place);
            if (normalizedState) {
                dashboardState.selectedStateFips = normalizedState;
                dashboardState.comparePlaceId = normalizedState;
            }
        }
    }

    if (model && lookup.modelById.has(model)) {
        dashboardState.selectedModel = model;
        dashboardState.modelExplicitlyChosen = true;
    } else {
        applyPreferredModelForGeo(dashboardState.selectedGeoType);
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
        dashboardState.selectedModel = getPreferredModelForGeo(dashboardState.selectedGeoType);
    }

    if (!scenarioChoiceExists(dashboardState.selectedScenario, dashboardState.selectedGeoType)) {
        const choices = getScenarioChoicesForGeoType(dashboardState.selectedGeoType);
        dashboardState.selectedScenario = choices.length ? choices[0].id : scenarioCompareDefaults.scenarioA;
    }

    if (!getAvailableHorizonYears().includes(dashboardState.selectedHorizon)) {
        dashboardState.selectedHorizon = getAvailableHorizonYears().includes(DEFAULT_HORIZON_YEAR)
            ? DEFAULT_HORIZON_YEAR
            : getAvailableHorizonYears()[0];
    }

    if (dashboardState.selectedGeoType === "msa" && !lookup.msaById.has(dashboardState.selectedMsaId)) {
        const firstMsa = getFilteredMsas()[0];
        dashboardState.selectedMsaId = firstMsa ? firstMsa.geography_id : dashboardState.selectedMsaId;
    }
    syncCompareGeoTypeToSelectedView();
}

function syncCompareGeoTypeToSelectedView() {
    dashboardState.compareGeoType = dashboardState.selectedGeoType === "msa" && availability.msa.available
        ? "msa"
        : "state";

    if (dashboardState.compareGeoType === "msa") {
        const selectedMsa = getSelectedMsa();
        const filteredMsas = getFilteredMsas();
        const hasCurrentSelection = filteredMsas.some(function (msa) {
            return msa.geography_id === dashboardState.comparePlaceId;
        });
        if (!hasCurrentSelection) {
            dashboardState.comparePlaceId = selectedMsa
                ? selectedMsa.geography_id
                : (filteredMsas[0] ? filteredMsas[0].geography_id : "");
        }
        return;
    }

    if (!lookup.stateByFips.has(dashboardState.comparePlaceId)) {
        dashboardState.comparePlaceId = dashboardState.selectedStateFips;
    }
}

function populateControls() {
    syncCompareGeoTypeToSelectedView();
    populateGlobalControls();
    populateMsaControls();
    populateCompareControls();
    syncControls();
}

function populateGlobalControls() {
    const states = getAvailableStates();
    const models = dashboardData.model_options || [];
    const scenarios = getScenarioControlChoices();
    const outcomes = dashboardData.outcome_options || [];
    const horizonYears = getAvailableHorizonYears();

    document.querySelectorAll('[data-setting="state"]').forEach(function (select) {
        select.innerHTML = states.map(function (state) {
            return '<option value="' + state.state_fips + '">' + state.state_name + "</option>";
        }).join("");
    });

    document.querySelectorAll('[data-setting="model"]').forEach(function (select) {
        const syncTarget = select.getAttribute("data-sync");
        const geoType = syncTarget === "msa"
            ? "msa"
            : (syncTarget === "compare" && dashboardState.compareGeoType === "msa" ? "msa" : "state");
        select.innerHTML = models.map(function (model) {
            const disabled = model.available ? "" : " disabled";
            return '<option value="' + model.id + '"' + disabled + ">" + getModelDisplayLabel(model, geoType) + "</option>";
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
    const comparePlaceLabel = document.getElementById("compare-place-label");

    const compareGeoType = dashboardState.compareGeoType === "msa" && availability.msa.available
        ? "msa"
        : "state";
    const compareScenarios = getScenarioChoicesForGeoType(compareGeoType);
    const optionsHtml = compareScenarios.map(function (scenario) {
        return '<option value="' + scenario.id + '">' + scenario.label + "</option>";
    }).join("");
    if (comparePlaceLabel) {
        comparePlaceLabel.textContent = compareGeoType === "msa" ? "MSA" : "State";
    }
    if (compareScenarioASelect) {
        compareScenarioASelect.innerHTML = optionsHtml;
    }
    if (compareScenarioBSelect) {
        compareScenarioBSelect.innerHTML = optionsHtml;
    }

    if (compareScenarios.length) {
        if (!compareScenarios.some(function (scenario) { return scenario.id === dashboardState.compareScenarioA; })) {
            dashboardState.compareScenarioA = compareScenarios[0].id;
        }
        if (!compareScenarios.some(function (scenario) { return scenario.id === dashboardState.compareScenarioB; })) {
            dashboardState.compareScenarioB = compareScenarios[Math.min(1, compareScenarios.length - 1)].id;
        }
    }

    populateComparePlaceOptions();
}

function populateComparePlaceOptions() {
    const comparePlaceSelect = document.getElementById("compare-place-select");
    if (!comparePlaceSelect) {
        return;
    }

    if (dashboardState.compareGeoType === "msa" && availability.msa.available) {
        const msas = getFilteredMsas();
        comparePlaceSelect.disabled = msas.length === 0;
        comparePlaceSelect.innerHTML = msas.length
            ? msas.map(function (msa) {
                return '<option value="' + msa.geography_id + '">' + msa.geography_name + "</option>";
            }).join("")
            : "<option>No MSAs match this filter</option>";
        if (!msas.some(function (msa) { return msa.geography_id === dashboardState.comparePlaceId; })) {
            dashboardState.comparePlaceId = dashboardState.selectedMsaId || (msas[0] ? msas[0].geography_id : "");
        }
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
                setSelectedGeoType("state");
                if (dashboardState.compareGeoType === "state") {
                    dashboardState.comparePlaceId = value;
                }
            } else if (key === "model") {
                dashboardState.selectedModel = value;
                dashboardState.modelExplicitlyChosen = true;
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
            const storyCard = event.target.closest("[data-scenario-story]");
            if (!storyCard) {
                return;
            }
            dashboardState.selectedScenario = storyCard.getAttribute("data-scenario-story");
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
            setSelectedGeoType("msa");
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

function initializeMsaCaptionToggle() {
    const toggle = document.getElementById("msa-map-caption-toggle");
    const detailsNode = document.getElementById("msa-map-note");
    if (!toggle || !detailsNode) {
        return;
    }
    toggle.setAttribute("aria-expanded", "false");
    detailsNode.hidden = true;
    toggle.addEventListener("click", function () {
        const isExpanded = toggle.getAttribute("aria-expanded") === "true";
        toggle.setAttribute("aria-expanded", isExpanded ? "false" : "true");
        detailsNode.hidden = isExpanded;
    });
}

function bindUtilityActions() {
    bindClick("download-current-view-button", downloadCurrentView);
    bindClick("download-all-data-button", downloadAllScenarioData);
    bindClick("download-rankings-button", downloadRankings);
    bindClick("download-benchmarks-button", downloadBenchmarks);
    bindClick("download-county-display-layer-button", downloadCountyDisplayLayer);
    bindClick("copy-summary-button", copySummary);
    bindClick("copy-link-button", copyCurrentViewLink);
    bindUtilityPanels();
}

function bindUtilityPanels() {
    const root = document.querySelector(".scenario-dashboard");
    const detailsNodes = root ? Array.from(root.querySelectorAll("[data-utility-panel]")) : [];
    if (!root || !detailsNodes.length || utilityPanelEventsBound) {
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
        if (!event.target.closest("[data-utility-panel]")) {
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
    syncCompareGeoTypeToSelectedView();
    populateCompareControls();
    const scenarioChoices = getScenarioControlChoices();
    if (scenarioChoices.length && !scenarioChoiceExists(dashboardState.selectedScenario, dashboardState.selectedGeoType)) {
        dashboardState.selectedScenario = scenarioChoices[0].id;
    }
    closeAllInfoTooltips();
    syncControls();
    if (availability.msa.available) {
        emitMsaDiagnostics();
    }
    renderControlInfoSummaries();
    renderGeoPanels();
    renderMap();
    renderRankings();
    renderStateExplorer();
    renderMsaSummary();
    renderMsaExplorer();
    renderScenarioStories();
    renderCompare();
    renderMechanismPanel();
    renderModelStatus();
    renderMethodCards();
    updateSelectionStrips();
    updateUtilityActionState();
    updateUrlState();
    updateSectionNavigationState();
}

function renderGeoPanels() {
    const statePanel = document.getElementById("state-panel");
    const msaPanel = document.getElementById("msa-panel");
    const isMsa = dashboardState.selectedGeoType === "msa" && availability.msa.available;

    if (statePanel) {
        statePanel.hidden = isMsa;
        statePanel.classList.toggle("is-active", !isMsa);
    }
    if (msaPanel) {
        msaPanel.hidden = !isMsa;
        msaPanel.classList.toggle("is-active", isMsa);
    }
}

function renderHeroStats() {
    const stateCount = getAvailableStates().length;
    const stateLabel = stateCount === 51 ? "50 states + DC" : stateCount + " state geographies";
    const summaryNode = document.getElementById("hero-stat-grid");
    if (!summaryNode) {
        return;
    }

    const summaryItems = [
        '<span class="scenario-summary-item">' + escapeHtml(stateLabel) + "</span>",
        buildHeroSummaryDetails(
            getScenarioChoices().length + " digital-life scenarios",
            "scenario-summary-scenarios",
            getScenarioChoices().map(function (scenario) {
                return [
                    '<details class="scenario-summary-panel-entry">',
                    '<summary>' + escapeHtml(scenario.label) + "</summary>",
                    "<p>" + escapeHtml(getHeroScenarioDefinition(scenario.id)) + "</p>",
                    "</details>",
                ].join("");
            }).join("")
        ),
        buildHeroSummaryDetails(
            (dashboardData.model_options || []).length + " predictive benchmarks",
            "scenario-summary-benchmarks",
            (dashboardData.model_options || []).map(function (model) {
                return [
                    '<details class="scenario-summary-panel-entry">',
                    '<summary>' + escapeHtml(getModelDisplayLabel(model)) + "</summary>",
                    "<p>" + escapeHtml(getHeroBenchmarkDefinition(model.id)) + "</p>",
                    "</details>",
                ].join("");
            }).join("")
        ),
        '<span class="scenario-summary-item">State-year exports available</span>',
        '<a href="#state-map" class="scenario-summary-link scenario-summary-link-inline">Jump to map &#8595;</a>',
    ];

    summaryNode.innerHTML = summaryItems.join('<span class="scenario-summary-separator" aria-hidden="true">&middot;</span>');
}

function renderScenarioStories() {
    const stories = getScenarioChoices();
    const container = document.getElementById("scenario-story-grid");
    if (!container) {
        return;
    }
    if (dashboardState.selectedGeoType === "msa") {
        container.innerHTML = "";
        return;
    }

    container.innerHTML = stories.map(function (scenario, index) {
        const storyYear = getScenarioStoryYear();
        const averageDifference = getAverageScenarioDifference(scenario.id, storyYear);
        const summaryText = Number.isFinite(averageDifference)
            ? formatSignedValue(averageDifference, 2) + " by " + storyYear
            : "Summary unavailable";
        return [
            '<button class="dashboard-card scenario-story-card' + (scenario.id === dashboardState.selectedScenario ? " is-active" : "") + '" type="button" data-scenario-story="' + scenario.id + '">',
            '<span class="scenario-story-topline">Scenario ' + (index + 1) + "</span>",
            '<span class="scenario-story-head">',
            '<span class="scenario-story-icon" aria-hidden="true"><i class="fa-solid ' + (scenarioStoryIcons[scenario.id] || "fa-circle") + '"></i></span>',
            '<span class="scenario-story-head-copy">',
            "<strong>" + escapeHtml(scenario.label) + "</strong>",
            "</span>",
            '<span class="scenario-story-chevron" aria-hidden="true"><i class="fa-solid fa-chevron-right"></i></span>',
            "</span>",
            '<span class="scenario-story-summary">' + escapeHtml(summaryText) + "</span>",
            "</button>",
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
    renderStateMap();
    renderMsaMap();
}

function renderStateMap() {
    const mapRows = getStateRowsForCurrentView();
    const values = mapRows.map(function (row) {
        return row[dashboardState.selectedOutcome];
    });
    const scenarioDiffs = mapRows.map(function (row) { return row.scenario_difference; }).filter(Number.isFinite);
    const finiteValues = values.map(function (value) { return Number(value); }).filter(Number.isFinite);
    const colorDomain = getChoroplethColorDomain(values, {
        outcomeId: dashboardState.selectedOutcome,
        minimumSpan: CHOROPLETH_MIN_DOMAIN_SPAN,
        relativePaddingFactor: CHOROPLETH_RELATIVE_PADDING_FACTOR,
    });
    logDashboardDebug("Rendering state map", buildMapRenderDebugDetails("state", mapRows.length, {
        finiteValueCount: finiteValues.length,
        minValue: finiteValues.length ? finiteArrayMin(finiteValues) : NaN,
        maxValue: finiteValues.length ? finiteArrayMax(finiteValues) : NaN,
        colorDomainZmin: colorDomain.zmin,
        colorDomainZmax: colorDomain.zmax,
        constantValueDomain: colorDomain.isConstant,
        constantValue: colorDomain.constantValue,
        referencePathFallback: isReferencePathSelection(dashboardState.selectedScenario),
        neutralDifferenceFallback: isReferenceScenarioNeutralDifferenceSelection(),
    }));

    const model = getSelectedModel();
    const mapBadge = document.getElementById("map-model-badge");
    if (mapBadge && model) {
        mapBadge.textContent = model.label;
    }

    updateFigure1Title();

    if (!values.length || !values.every(Number.isFinite)) {
        console.error("State map could not be prepared for the selected view.", {
            geo: dashboardState.selectedGeoType,
            model: dashboardState.selectedModel,
            scenario: dashboardState.selectedScenario,
            year: dashboardState.selectedHorizon,
            outcome: dashboardState.selectedOutcome,
            geographyRecordCount: mapRows.length,
        });
        renderPlotFallback("state-map-chart", "Unavailable for current selection.");
        updateMapNote(scenarioDiffs, colorDomain);
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
        zmin: colorDomain.zmin,
        zmax: colorDomain.zmax,
        hovertemplate:
            "<b>%{customdata[1]}</b><br>" +
            "Model-based reference path: %{customdata[2]:.1f}<br>" +
            "Projected path under this scenario: %{customdata[3]:.1f}<br>" +
            "Change relative to reference path: %{customdata[4]:+.1f}<br>" +
            "Main driver: %{customdata[5]}<extra></extra>",
        colorbar: {
            title: {
                text: dashboardState.selectedOutcome === "scenario_difference"
                    ? "Change relative to reference path<br>Live births per 1,000 women aged " + WOMEN_AGE_LABEL
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
        logDashboardDebug("State map rendered", buildMapRenderDebugDetails("state", mapRows.length, {
            containerId: "state-map-chart",
            containerHasSvg: doesContainerHaveSvg(container),
        }));
        if (typeof container.removeAllListeners === "function") {
            container.removeAllListeners("plotly_click");
        }
        container.on("plotly_click", function (event) {
            if (!event.points || !event.points.length) {
                return;
            }
            dashboardState.selectedStateFips = event.points[0].customdata[0];
            setSelectedGeoType("state");
            if (dashboardState.compareGeoType === "state") {
                dashboardState.comparePlaceId = dashboardState.selectedStateFips;
            }
            syncControls();
            renderDashboard();
        });
    });

    updateMapNote(scenarioDiffs, colorDomain);
    renderMapSummary();
}

function setMsaMapStatus(message, tone) {
    const statusNode = document.getElementById("msa-map-status");
    if (!statusNode) {
        return;
    }
    const text = String(message || "").trim();
    statusNode.classList.remove("is-error");
    statusNode.classList.remove("is-visible");
    if (!text) {
        statusNode.textContent = "";
        statusNode.hidden = true;
        return;
    }
    statusNode.hidden = false;
    statusNode.classList.add("is-visible");
    statusNode.textContent = text;
    if (tone === "error") {
        statusNode.classList.add("is-error");
    }
}

function renderMsaMap() {
    updateMsaFigure1Title();
    if (!document.getElementById("msa-map-chart")) {
        return;
    }
    if (dashboardState.selectedGeoType !== "msa") {
        setMsaMapStatus("");
        return;
    }
    if (!availability.msa.available) {
        setMsaMapStatus("");
        renderPlotFallback("msa-map-chart", availability.msa.reason);
        return;
    }

    const geometry = getCountyGeometrySource();
    if (!geometry) {
        if (!countyGeometryLoadPromise && !countyGeometryLoadError) {
            ensureCountyGeometryLoaded()
                .then(function () {
                    if (dashboardState.selectedGeoType === "msa") {
                        renderDashboard();
                    }
                })
                .catch(function (error) {
                    if (dashboardState.selectedGeoType === "msa") {
                        renderDashboard();
                    }
                });
        }
        const message = countyGeometryLoadPromise
            ? COUNTY_GEOMETRY_LOADING_MESSAGE
            : (countyGeometryLoadError || COUNTY_GEOMETRY_UNAVAILABLE_MESSAGE);
        setMsaMapStatus(message, countyGeometryLoadPromise ? "loading" : "error");
        clearPlotContainer("msa-map-chart");
        setPlotContainerCompactState("msa-map-chart", true);
        return;
    }

    setMsaMapStatus("");
    const countyRows = getCountyDisplayRowsForCurrentView();
    const estimatedRows = countyRows.filter(function (row) {
        return row.estimate_status === "estimated_msa" && Number.isFinite(row.selected_outcome_value);
    });
    logDashboardDebug("MSA county geometry loaded successfully", buildMsaGeometrySuccessDebugDetails(
        geometry,
        estimatedRows.length,
        countyRows.length
    ));
    if (!estimatedRows.length) {
        renderPlotFallback("msa-map-chart", MSA_RESULTS_UNAVAILABLE_MESSAGE);
        return;
    }

    const metropolitanContextRows = countyRows.filter(function (row) {
        return row.estimate_status === "metropolitan_context_only";
    });
    const micropolitanContextRows = countyRows.filter(function (row) {
        return row.estimate_status === "micropolitan_context_only";
    });
    const outsideRows = countyRows.filter(function (row) {
        return row.estimate_status === "outside_cbsa";
    });

    const scenarioDiffs = estimatedRows.map(function (row) { return row.scenario_difference; }).filter(Number.isFinite);
    const selectedValues = estimatedRows.map(function (row) { return row.selected_outcome_value; });
    const finiteSelectedValues = selectedValues.map(function (value) { return Number(value); }).filter(Number.isFinite);
    const colorDomain = getChoroplethColorDomain(selectedValues, {
        outcomeId: dashboardState.selectedOutcome,
        minimumSpan: CHOROPLETH_MIN_DOMAIN_SPAN,
        relativePaddingFactor: CHOROPLETH_RELATIVE_PADDING_FACTOR,
    });
    logDashboardDebug("Rendering MSA map", buildMapRenderDebugDetails("msa", estimatedRows.length, {
        finiteValueCount: finiteSelectedValues.length,
        minValue: finiteSelectedValues.length ? finiteArrayMin(finiteSelectedValues) : NaN,
        maxValue: finiteSelectedValues.length ? finiteArrayMax(finiteSelectedValues) : NaN,
        colorDomainZmin: colorDomain.zmin,
        colorDomainZmax: colorDomain.zmax,
        constantValueDomain: colorDomain.isConstant,
        constantValue: colorDomain.constantValue,
        countyRowCount: countyRows.length,
        estimatedCountyCount: estimatedRows.length,
        metropolitanContextCountyCount: metropolitanContextRows.length,
        micropolitanContextCountyCount: micropolitanContextRows.length,
        outsideCountyCount: outsideRows.length,
        referencePathFallback: isReferencePathSelection(dashboardState.selectedScenario),
        neutralDifferenceFallback: isReferenceScenarioNeutralDifferenceSelection(),
    }));
    const traces = [];

    if (outsideRows.length) {
        traces.push(buildCountyContextTrace(geometry, outsideRows, "#efefef"));
    }
    if (metropolitanContextRows.length) {
        traces.push(buildCountyContextTrace(geometry, metropolitanContextRows, "#e6ddd0"));
    }
    if (micropolitanContextRows.length) {
        traces.push(buildCountyContextTrace(geometry, micropolitanContextRows, "#f3ead8"));
    }

    traces.push({
        type: "choropleth",
        geojson: geometry,
        featureidkey: "id",
        locationmode: "geojson-id",
        locations: estimatedRows.map(function (row) { return row.county_fips; }),
        z: estimatedRows.map(function (row) { return row.selected_outcome_value; }),
        customdata: estimatedRows.map(function (row) {
            return [row.estimate_status, row.estimated_geography_id, row.county_fips];
        }),
        text: estimatedRows.map(buildEstimatedCountyHoverText),
        marker: { line: { color: "#f4efe6", width: 0.4 } },
        colorscale: dashboardState.selectedOutcome === "scenario_difference"
            ? [[0, "#8b3a22"], [0.5, "#f6f1e8"], [1, "#1f6b75"]]
            : [[0, "#f3e5c8"], [0.5, "#d1dcbf"], [1, "#205b62"]],
        zmin: colorDomain.zmin,
        zmax: colorDomain.zmax,
        hovertemplate: "%{text}<extra></extra>",
        colorbar: {
            title: {
                text: dashboardState.selectedOutcome === "scenario_difference"
                    ? "Change relative to reference path<br>Live births per 1,000 women aged " + WOMEN_AGE_LABEL
                    : "Live births per 1,000 women aged " + WOMEN_AGE_LABEL,
                side: "right",
            },
            thickness: 12,
            tickfont: { size: 11 },
        },
    });

    const layout = {
        geo: {
            scope: "usa",
            projection: { type: "albers usa" },
            bgcolor: "rgba(0,0,0,0)",
            showlakes: false,
            showland: true,
            landcolor: "#fbf8f2",
            showsubunits: true,
            subunitcolor: "#d9d1c4",
            subunitwidth: 0.6,
        },
        margin: { t: 8, r: 0, b: 0, l: 0 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        dragmode: false,
    };

    plotChart("msa-map-chart", traces, layout, function (container) {
        logDashboardDebug("MSA map rendered", buildMapRenderDebugDetails("msa", estimatedRows.length, {
            containerId: "msa-map-chart",
            containerHasSvg: doesContainerHaveSvg(container),
            countyRowCount: countyRows.length,
            estimatedCountyCount: estimatedRows.length,
        }));
        if (typeof container.removeAllListeners === "function") {
            container.removeAllListeners("plotly_click");
        }
        container.on("plotly_click", function (event) {
            if (!event.points || !event.points.length) {
                return;
            }
            const customdata = event.points[0].customdata || [];
            if (customdata[0] !== "estimated_msa" || !customdata[1] || !lookup.msaById.has(customdata[1])) {
                setUtilityStatus("This county is shown for geographic context only and has no MSA scenario estimate.");
                return;
            }
            dashboardState.selectedMsaId = customdata[1];
            setSelectedGeoType("msa");
            syncControls();
            renderDashboard();
        });
    });
}

function getCountyGeometrySource() {
    return window.AI_WORK_FERTILITY_DASHBOARD_COUNTY_GEOMETRY
        || dashboardData.county_geojson
        || dashboardData.county_geometry
        || null;
}

function getCountyGeometryAssetPath() {
    return String(
        document.body && document.body.getAttribute("data-county-geometry-src")
        || ""
    ).trim();
}

function loadScriptOnce(src) {
    return new Promise(function (resolve, reject) {
        const existing = document.querySelector('script[data-dynamic-src="' + src + '"]');
        if (existing) {
            if (existing.getAttribute("data-loaded") === "true") {
                resolve();
                return;
            }
            existing.addEventListener("load", function handleLoad() {
                existing.removeEventListener("load", handleLoad);
                resolve();
            });
            existing.addEventListener("error", function handleError(event) {
                existing.removeEventListener("error", handleError);
                const loadError = event && event.error ? event.error : new Error("Script load failed.");
                loadError.failedUrl = src;
                reject(loadError);
            });
            return;
        }

        const script = document.createElement("script");
        script.src = src;
        script.async = true;
        script.setAttribute("data-dynamic-src", src);
        script.addEventListener("load", function () {
            script.setAttribute("data-loaded", "true");
            resolve();
        });
        script.addEventListener("error", function (event) {
            const loadError = event && event.error ? event.error : new Error("Script load failed.");
            loadError.failedUrl = src;
            reject(loadError);
        });
        document.body.appendChild(script);
    });
}

function ensureCountyGeometryLoaded() {
    if (getCountyGeometrySource()) {
        return Promise.resolve();
    }
    if (countyGeometryLoadError) {
        return Promise.reject(new Error(countyGeometryLoadError));
    }
    if (countyGeometryLoadPromise) {
        return countyGeometryLoadPromise;
    }
    const assetPath = getCountyGeometryAssetPath();
    if (!assetPath) {
        countyGeometryLoadError = COUNTY_GEOMETRY_UNAVAILABLE_MESSAGE;
        console.error("County display geometry asset path is missing.", {
            url: assetPath,
        });
        return Promise.reject(new Error(countyGeometryLoadError));
    }
    countyGeometryLoadPromise = loadScriptOnce(assetPath)
        .then(function () {
            countyGeometryLoadPromise = null;
            if (!getCountyGeometrySource()) {
                countyGeometryLoadError = COUNTY_GEOMETRY_UNAVAILABLE_MESSAGE;
                console.error("County display geometry loaded without an accessible geometry payload.", {
                    url: assetPath,
                });
                throw new Error(countyGeometryLoadError);
            }
        })
        .catch(function (error) {
            countyGeometryLoadPromise = null;
            countyGeometryLoadError = extractErrorMessage(error) || COUNTY_GEOMETRY_UNAVAILABLE_MESSAGE;
            console.error("County display geometry failed to load.", {
                url: error && error.failedUrl ? error.failedUrl : assetPath,
                error: error,
            });
            throw error;
        });
    return countyGeometryLoadPromise;
}

function formatEstimateStatusLabel(status) {
    if (status === "estimated_msa") {
        return "Estimated MSA";
    }
    if (status === "metropolitan_context_only") {
        return "Metropolitan CBSA, no scenario estimate available";
    }
    if (status === "micropolitan_context_only") {
        return "Micropolitan CBSA, no scenario estimate available";
    }
    return "Outside CBSA / not in analytical universe";
}

function buildEstimatedCountyHoverText(row) {
    const lines = [
        "<b>" + escapeHtml(row.county_name) + "</b>",
        escapeHtml(row.state_name || row.state_abbr || ""),
        "Analytical MSA: " + escapeHtml(row.estimated_geography_name || row.estimated_geography_id || "Unknown"),
    ];
    if (row.cbsa_name && row.cbsa_name !== row.estimated_geography_name) {
        lines.push("2023 CBSA: " + escapeHtml(row.cbsa_name));
    }
    if (row.cbsa_type) {
        lines.push("CBSA type: " + escapeHtml(formatCbsaTypeLabel(row.cbsa_type)));
    }
    lines.push("Estimate status: " + escapeHtml(formatEstimateStatusLabel(row.estimate_status)));
    if (dashboardState.selectedOutcome !== "scenario_difference" && Number.isFinite(row.selected_outcome_value)) {
        lines.push(
            escapeHtml(getOutcomeLabel(dashboardState.selectedOutcome, "")) + ": "
            + escapeHtml(formatNumber(row.selected_outcome_value, 3))
        );
    }
    if (Number.isFinite(row.scenario_difference)) {
        lines.push(
            "Scenario effect: "
            + escapeHtml(formatSignedValue(row.scenario_difference, 3))
            + " births per 1,000 women aged " + WOMEN_AGE_LABEL
        );
    }
    if (row.main_driver) {
        lines.push("Main driver: " + escapeHtml(row.main_driver));
    }
    return lines.join("<br>");
}

function buildContextCountyHoverText(row) {
    const lines = [
        "<b>" + escapeHtml(row.county_name) + "</b>",
        escapeHtml(row.state_name || row.state_abbr || ""),
        "CBSA / MSA: " + escapeHtml(row.cbsa_name || "None"),
    ];
    if (row.cbsa_type) {
        lines.push("CBSA type: " + escapeHtml(formatCbsaTypeLabel(row.cbsa_type)));
    } else {
        lines.push("CBSA type: Outside CBSA");
    }
    lines.push("Estimate status: " + escapeHtml(formatEstimateStatusLabel(row.estimate_status)));
    lines.push("No scenario estimate available");
    return lines.join("<br>");
}

function buildCountyContextTrace(geometry, rows, fillColor) {
    return {
        type: "choropleth",
        geojson: geometry,
        featureidkey: "id",
        locationmode: "geojson-id",
        locations: rows.map(function (row) { return row.county_fips; }),
        z: rows.map(function () { return 1; }),
        customdata: rows.map(function (row) {
            return [row.estimate_status, "", row.county_fips];
        }),
        text: rows.map(buildContextCountyHoverText),
        hovertemplate: "%{text}<extra></extra>",
        colorscale: [[0, fillColor], [1, fillColor]],
        showscale: false,
        marker: { line: { color: "#ddd4c8", width: 0.35 } },
    };
}

function getMsaGeometrySource() {
    return window.AI_WORK_FERTILITY_DASHBOARD_MSA_GEOMETRY
        || dashboardData.msa_geojson
        || dashboardData.msa_geometry
        || dashboardData.msa_map_geojson
        || null;
}

function prepareMsaGeometry(source, rows) {
    if (!source || source.type !== "FeatureCollection" || !Array.isArray(source.features)) {
        return {
            geojson: null,
            rows: [],
            message: MSA_GEOMETRY_UNAVAILABLE_MESSAGE,
        };
    }

    const rowById = new Map();
    rows.forEach(function (row) {
        rowById.set(String(row.geography_id), row);
    });

    const matchedIds = new Set();
    const unmatchedGeometryIds = [];
    const features = source.features.reduce(function (accumulator, feature) {
        const geometryId = resolveMsaGeometryId(feature);
        if (!geometryId) {
            return accumulator;
        }
        const row = rowById.get(geometryId);
        if (!row) {
            unmatchedGeometryIds.push(geometryId);
            return accumulator;
        }
        matchedIds.add(geometryId);
        const featureCopy = {
            type: "Feature",
            id: geometryId,
            geometry: feature.geometry,
            properties: Object.assign({}, feature.properties || {}, { __dashboard_msa_id: geometryId }),
        };
        accumulator.push(featureCopy);
        return accumulator;
    }, []);

    const unmatchedResultIds = rows
        .map(function (row) { return String(row.geography_id); })
        .filter(function (id) { return !matchedIds.has(id); });

    logMsaGeometryDiagnostics(rows.length, source.features.length, matchedIds.size, unmatchedResultIds, unmatchedGeometryIds);

    return {
        geojson: features.length ? { type: "FeatureCollection", features: features } : null,
        rows: rows.filter(function (row) { return matchedIds.has(String(row.geography_id)); }),
        message: features.length
            ? ""
            : "MSA map geometry is unavailable. MSA results are still available in the table and chart.",
    };
}

function resolveMsaGeometryId(feature) {
    if (!feature) {
        return "";
    }
    if (feature.id) {
        return String(feature.id);
    }
    const properties = feature.properties || {};
    for (let index = 0; index < MSA_GEOMETRY_ID_KEYS.length; index += 1) {
        const key = MSA_GEOMETRY_ID_KEYS[index];
        if (properties[key]) {
            return String(properties[key]);
        }
    }
    return "";
}

function logMsaGeometryDiagnostics(resultRowCount, featureCount, matchedCount, unmatchedResultIds, unmatchedGeometryIds) {
    if (!unmatchedResultIds.length && !unmatchedGeometryIds.length) {
        return;
    }
    console.warn("MSA geometry join diagnostics", {
        msa_result_rows: resultRowCount,
        msa_geometry_features: featureCount,
        matched_ids: matchedCount,
        unmatched_result_ids: unmatchedResultIds.length,
        unmatched_geometry_ids: unmatchedGeometryIds.length,
        sample_unmatched_result_ids: unmatchedResultIds.slice(0, 10),
        sample_unmatched_geometry_ids: unmatchedGeometryIds.slice(0, 10),
    });
}

function updateFigure1Title() {
    const titleNode = document.getElementById("figure-1-title");
    if (!titleNode) {
        return;
    }
    if (dashboardState.selectedOutcome === "reference_path") {
        titleNode.textContent = "Model-based reference path across states";
        return;
    }
    if (dashboardState.selectedOutcome === "scenario_path") {
        titleNode.textContent = "Projected fertility under this scenario across states";
        return;
    }
    titleNode.textContent = "How fertility changes across states under this scenario";
}

function updateMsaFigure1Title() {
    const titleNode = document.getElementById("msa-map-title");
    if (!titleNode) {
        return;
    }
    if (dashboardState.selectedOutcome === "reference_path") {
        titleNode.textContent = "Model-based reference path across MSAs";
        return;
    }
    if (dashboardState.selectedOutcome === "scenario_path") {
        titleNode.textContent = "Projected fertility under this scenario across MSAs";
        return;
    }
    titleNode.textContent = "How fertility changes across MSAs under this scenario";
}

function updateMapNote(scenarioDiffs, colorDomain) {
    const noteNode = document.getElementById("state-map-note");
    if (!noteNode) {
        return;
    }
    const constantValueNote = getConstantValueMapNote(colorDomain);
    const referencePathNote = getReferencePathSelectionNote();
    if (dashboardState.selectedOutcome !== "scenario_difference") {
        noteNode.innerHTML =
            "Values show fertility levels for the selected outcome. Rankings at right still use " +
            buildInlineInfoLabelHtml("scenario_difference", "change relative to the reference path") +
            (constantValueNote ? ". " + escapeHtml(constantValueNote) : ".");
        return;
    }
    if (!scenarioDiffs.length) {
        noteNode.textContent = "Range unavailable for the current selection.";
        return;
    }
    let text =
        "Positive values mean the selected scenario is above the model-based reference path. Negative values mean it is below. " +
        buildScenarioInterpretationNote();
    const scenarioDirectionNote = getScenarioDirectionNote(scenarioDiffs);
    if (scenarioDirectionNote) {
        text += " " + scenarioDirectionNote;
    }
    if (referencePathNote) {
        text += " " + referencePathNote;
    }
    if (constantValueNote) {
        text += " " + constantValueNote;
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

function buildModelReliabilityNote() {
    const model = getSelectedModelOption();
    if (!model) {
        return "";
    }
    const diagnostics = getModelReliabilityDiagnostics(dashboardState.selectedGeoType, model.id);
    if (diagnostics && (diagnostics.status === "USE CAUTION" || diagnostics.status === "BENCHMARK ONLY")) {
        return diagnostics.warningText || "";
    }
    return "";
}

function getModelReliabilityDiagnostics(geoType, modelId) {
    const summary = getModelReliabilitySummary(geoType, modelId);
    const metrics = getMetricsForModel(geoType, modelId);
    const test = metrics.find(function (row) { return row.split === "test"; }) || null;
    const negativeTestR2 = Boolean(test && Number.isFinite(test.r_squared) && Number(test.r_squared) <= 0);
    if (summary) {
        return {
            available: true,
            status: summary.status || "AVAILABLE",
            statusBadge: summary.status_badge || "Available",
            warningText: summary.warning_text || "",
            reasonForLabel: summary.reason_for_label || "",
            recommendedDefault: Boolean(summary.recommended_default),
            reliable: summary.status !== "USE CAUTION",
            negativeTestR2: negativeTestR2,
            referenceBoundaryShare: Number.isFinite(Number(summary.reference_boundary_share))
                ? Number(summary.reference_boundary_share)
                : NaN,
            peakReferenceBoundaryShare: Number.isFinite(Number(summary.peak_reference_boundary_share))
                ? Number(summary.peak_reference_boundary_share)
                : NaN,
            sameBoundZeroShare: Number.isFinite(Number(summary.same_bound_zero_share))
                ? Number(summary.same_bound_zero_share)
                : NaN,
            coverageShare: Number.isFinite(Number(summary.coverage_share))
                ? Number(summary.coverage_share)
                : NaN,
        };
    }

    const referenceRows = (lookup.recordsByGeoType.get(geoType) || []).filter(function (record) {
        return record.model === modelId
            && record.scenario === "reference_path"
            && Number.isFinite(Number(record.reference_path));
    });
    const n = referenceRows.length;
    const lowerBoundShare = n
        ? referenceRows.filter(function (record) {
            return Number(record.reference_path) <= FORECAST_BOUND_FLOOR + 1e-3;
        }).length / n
        : 0;
    const upperBoundShare = n
        ? referenceRows.filter(function (record) {
            return Number(record.reference_path) >= FORECAST_BOUND_CEILING - 1e-3;
        }).length / n
        : 0;
    const boundaryShare = lowerBoundShare + upperBoundShare;
    const status = boundaryShare > 0.20 || negativeTestR2 ? "USE CAUTION" : "AVAILABLE";

    return {
        available: n > 0,
        status: status,
        statusBadge: status === "USE CAUTION" ? "Use caution" : "Available",
        warningText: status === "USE CAUTION"
            ? "Use caution. Many forecasts are near the model's lower or upper bound, or held-out fit is weak."
            : "Available.",
        reasonForLabel: "",
        recommendedDefault: false,
        reliable: status !== "USE CAUTION",
        negativeTestR2: negativeTestR2,
        referenceBoundaryShare: boundaryShare,
        peakReferenceBoundaryShare: boundaryShare,
        sameBoundZeroShare: NaN,
        coverageShare: 1,
    };
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
        let text = "Remote work can save commuting time and increase schedule flexibility.";
        if (diagnostic && typeof diagnostic.legacy_mean_scenario_difference === "number" && diagnostic.legacy_mean_scenario_difference < -0.01) {
            text += " Earlier versions behaved differently because they relied on a more opaque proxy mix.";
        }
        return text;
    }
    if (dashboardState.selectedScenario === "digital_distraction_crowds_out") {
        return "Screen leisure and digital media time may reduce time available for in-person interaction, dating, or family formation.";
    }
    if (dashboardState.selectedScenario === "online_life_helps_matching") {
        return "Online social life and digital matching tools may make it easier for people to meet, match, or maintain relationships.";
    }
    if (dashboardState.selectedScenario === "home_centered_digital_life_increases_care_work") {
        return "More digital life may keep more activities inside the home and increase unpaid care or household work burdens.";
    }
    return "This view shows how the selected scenario moves fertility above or below the model-based reference path.";
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

function getReferencePathSelectionNote() {
    return isReferenceScenarioNeutralDifferenceSelection()
        ? "Reference path selected: change relative to reference is zero by definition."
        : "";
}

function isReferencePathSelection(scenarioId) {
    return String(scenarioId || dashboardState.selectedScenario || "") === "reference_path";
}

function isReferenceScenarioNeutralDifferenceSelection(scenarioId, outcomeId) {
    return isReferencePathSelection(scenarioId)
        && String(outcomeId || dashboardState.selectedOutcome || "") === "scenario_difference";
}

function getScenarioSnapshotValues(context, outcomeId, scenarioId) {
    const resolvedOutcomeId = String(outcomeId || dashboardState.selectedOutcome || "scenario_difference");
    const resolvedScenarioId = String(scenarioId || dashboardState.selectedScenario || "");
    const referencePath = context ? Number(context.referenceFinal) : NaN;
    const referenceScenario = isReferencePathSelection(resolvedScenarioId);
    const scenarioPath = referenceScenario
        ? referencePath
        : (context ? Number(context.scenarioFinal) : NaN);
    const scenarioDifference = referenceScenario
        ? 0
        : (context ? Number(context.scenarioDifference) : NaN);
    let selectedOutcomeValue = scenarioDifference;
    if (resolvedOutcomeId === "reference_path") {
        selectedOutcomeValue = referencePath;
    } else if (resolvedOutcomeId === "scenario_path") {
        selectedOutcomeValue = scenarioPath;
    }
    return {
        reference_path: referencePath,
        scenario_path: scenarioPath,
        scenario_difference: scenarioDifference,
        selected_outcome_value: selectedOutcomeValue,
        usedReferenceFallback: referenceScenario,
    };
}

function getConstantValueMapNote(colorDomain) {
    if (!colorDomain || !colorDomain.isConstant) {
        return "";
    }
    if (colorDomain.outcomeId === "scenario_difference") {
        return colorDomain.constantValue === 0
            ? "All places equal the reference path for this view."
            : "All places show the same change relative to the reference path for this view.";
    }
    if (colorDomain.outcomeId === "reference_path") {
        return "All places share the same model-based reference-path value for this view.";
    }
    if (colorDomain.outcomeId === "scenario_path") {
        return "All places share the same projected scenario-path value for this view.";
    }
    return "All places share the same value for this view.";
}

function getChoroplethColorDomain(values, options) {
    const config = options || {};
    const finiteValues = (values || []).map(function (value) {
        return Number(value);
    }).filter(Number.isFinite);
    const outcomeId = config.outcomeId || "scenario_difference";
    const minimumSpan = Number.isFinite(Number(config.minimumSpan))
        ? Number(config.minimumSpan)
        : CHOROPLETH_MIN_DOMAIN_SPAN;
    const relativePaddingFactor = Number.isFinite(Number(config.relativePaddingFactor))
        ? Number(config.relativePaddingFactor)
        : CHOROPLETH_RELATIVE_PADDING_FACTOR;

    if (!finiteValues.length) {
        return {
            outcomeId: outcomeId,
            isConstant: false,
            constantValue: NaN,
            zmin: NaN,
            zmax: NaN,
        };
    }

    if (outcomeId === "scenario_difference") {
        const maxAbs = finiteArrayMax(finiteValues.map(function (value) {
            return Math.abs(value);
        }));
        const span = Math.max(maxAbs, minimumSpan);
        return {
            outcomeId: outcomeId,
            isConstant: finiteValues.every(function (value) { return value === finiteValues[0]; }),
            constantValue: finiteValues[0],
            zmin: -span,
            zmax: span,
        };
    }

    const minValue = finiteArrayMin(finiteValues);
    const maxValue = finiteArrayMax(finiteValues);
    if (minValue === maxValue) {
        const padding = Math.max(minimumSpan, Math.abs(minValue) * relativePaddingFactor);
        return {
            outcomeId: outcomeId,
            isConstant: true,
            constantValue: minValue,
            zmin: minValue - padding,
            zmax: maxValue + padding,
        };
    }

    return {
        outcomeId: outcomeId,
        isConstant: false,
        constantValue: NaN,
        zmin: minValue,
        zmax: maxValue,
    };
}

function getScenarioDifferenceToleranceForGeo(geoType) {
    return geoType === "msa" ? MSA_SCENARIO_DIFFERENCE_TOLERANCE : SCENARIO_DIFFERENCE_TOLERANCE;
}

function getScenarioDifferenceToleranceForRows(rows, fallbackGeoType) {
    const sampleRow = rows.find(function (row) {
        return row && row.geography_type;
    });
    return getScenarioDifferenceToleranceForGeo(
        sampleRow && sampleRow.geography_type ? sampleRow.geography_type : (fallbackGeoType || dashboardState.selectedGeoType)
    );
}

function getSummaryDisplayDigitsForGeo(geoType) {
    return geoType === "msa" ? MSA_SUMMARY_DISPLAY_DIGITS : STATE_SUMMARY_DISPLAY_DIGITS;
}

function getSummaryDisplayDigitsForRows(rows, fallbackGeoType) {
    const sampleRow = rows.find(function (row) {
        return row && row.geography_type;
    });
    return getSummaryDisplayDigitsForGeo(
        sampleRow && sampleRow.geography_type ? sampleRow.geography_type : (fallbackGeoType || dashboardState.selectedGeoType)
    );
}

function getMsaStateFilterLabel() {
    if (dashboardState.selectedMsaStateFilter === "all") {
        return "All states";
    }
    const state = lookup.stateByAbbr.get(String(dashboardState.selectedMsaStateFilter || "").toUpperCase());
    if (state) {
        return state.state_name;
    }
    return dashboardState.selectedMsaStateFilter || "Selected state";
}

function getMsaScopeSuffix() {
    return dashboardState.selectedMsaStateFilter === "all" ? "" : " in " + getMsaStateFilterLabel();
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
    const stateRows = getStateRowsForCurrentView();
    const stateAbove = buildRankingRows(stateRows, "upward");
    const stateBelow = buildRankingRows(stateRows, "downward");
    const stateCards = [
        renderRankingCard({
            title: "Top 5 states where this scenario raises fertility the most",
            rows: stateAbove,
            emptyMessage: "No states are above the reference path in the current view.",
        }),
        renderRankingCard({
            title: "Top 5 states where this scenario lowers fertility the most",
            rows: stateBelow,
            emptyMessage: "No states are below the reference path in the current view.",
        }),
        renderOverallImpactCard(stateRows),
    ];
    const stateGrid = document.getElementById("rankings-grid");
    if (stateGrid) {
        stateGrid.innerHTML = stateCards.join("");
    }

    const msaGrid = document.getElementById("msa-rankings-grid");
    if (!msaGrid) {
        return;
    }
    if (!availability.msa.available) {
        msaGrid.innerHTML = renderRankingCard({
            title: "MSA rankings unavailable",
            rows: [],
            emptyMessage: availability.msa.reason || MSA_RANKINGS_UNAVAILABLE_MESSAGE,
        });
        return;
    }

    const msaRows = getMsaRowsForCurrentView();
    const msaScopeSuffix = getMsaScopeSuffix();
    const hasMsaDifferences = hasFiniteScenarioDifferences(msaRows);
    const msaAbove = buildRankingRows(msaRows, "upward");
    const msaBelow = buildRankingRows(msaRows, "downward");
    msaGrid.innerHTML = [
        renderRankingCard({
            title: "Top 5 MSAs" + msaScopeSuffix + " where this scenario raises fertility the most",
            rows: msaAbove,
            emptyMessage: hasMsaDifferences
                ? "No MSAs are above the reference path in the current view."
                : MSA_RESULTS_UNAVAILABLE_MESSAGE,
        }),
        renderRankingCard({
            title: "Top 5 MSAs" + msaScopeSuffix + " where this scenario lowers fertility the most",
            rows: msaBelow,
            emptyMessage: hasMsaDifferences
                ? "No MSAs are below the reference path in the current view."
                : MSA_RESULTS_UNAVAILABLE_MESSAGE,
        }),
        renderOverallImpactCard(msaRows, {
            unitLabel: "MSA-average change" + (msaScopeSuffix ? msaScopeSuffix : ""),
            geographyPlural: "MSAs",
            unavailableMessage: MSA_RESULTS_UNAVAILABLE_MESSAGE,
        }),
    ].join("");
}

function renderStateExplorer() {
    const state = getSelectedState();
    const context = getScenarioContext("state", state.state_fips, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
    const figureTitleNode = document.getElementById("figure-2-title");
    const titleNode = document.getElementById("state-explorer-title");
    if (figureTitleNode) {
        figureTitleNode.textContent = "Selected state trends: " + state.state_name;
    }
    if (titleNode) {
        titleNode.textContent = "Observed, model-based reference path, and projected path through " + dashboardState.selectedHorizon;
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

function renderMsaSummary() {
    const titleNode = document.getElementById("msa-summary-title");
    const textNode = document.getElementById("msa-summary-text");
    if (!titleNode || !textNode) {
        return;
    }
    if (!availability.msa.available) {
        titleNode.textContent = "Selected MSA";
        textNode.textContent = availability.msa.reason;
        return;
    }
    const msa = getSelectedMsa();
    if (!msa) {
        titleNode.textContent = "Selected MSA";
        textNode.textContent = "MSA data unavailable.";
        return;
    }
    if (!hasScenarioSeries("msa", msa.geography_id, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon)) {
        titleNode.textContent = msa.geography_name + " | " + dashboardState.selectedHorizon;
        textNode.textContent = MSA_RESULTS_UNAVAILABLE_MESSAGE;
        return;
    }
    const context = getScenarioContext("msa", msa.geography_id, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
    titleNode.textContent = msa.geography_name + " | " + dashboardState.selectedHorizon;
    textNode.textContent = buildSummarySentence("msa", msa.geography_name, getSelectedModel().label, getSelectedScenario().label, dashboardState.selectedModel, dashboardState.selectedScenario, context.scenarioDifference, dashboardState.selectedHorizon, context.mainDriver, false);
}

function renderMsaExplorer() {
    const titleNode = document.getElementById("msa-explorer-title");
    const noteNode = document.getElementById("msa-line-note");
    const takeawayNode = document.getElementById("msa-takeaway-text");
    const legendNode = document.getElementById("msa-line-legend");
    if (!titleNode || !noteNode || !takeawayNode || !legendNode) {
        return;
    }
    if (!availability.msa.available) {
        renderPlotFallback("msa-line-chart", availability.msa.reason);
        titleNode.textContent = availability.msa.reason;
        noteNode.textContent = availability.msa.reason;
        takeawayNode.textContent = availability.msa.reason;
        legendNode.innerHTML = "";
        return;
    }
    const msa = getSelectedMsa();
    if (!msa) {
        renderPlotFallback("msa-line-chart", "MSA data unavailable.");
        titleNode.textContent = "MSA data unavailable.";
        noteNode.textContent = "MSA data unavailable.";
        takeawayNode.textContent = "MSA data unavailable.";
        legendNode.innerHTML = "";
        return;
    }
    const context = getScenarioContext("msa", msa.geography_id, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
    const contextNote = getMsaCbsaContextNote();
    const proxyNote = getMsaProxyScenarioNote(dashboardState.selectedScenario);
    titleNode.textContent = "Observed, model-based reference path, and projected path through " + dashboardState.selectedHorizon;
    legendNode.innerHTML = [
        '<span class="scenario-inline-chip scenario-inline-chip-observed">Observed</span>',
        '<span class="scenario-inline-chip scenario-inline-chip-reference">' + buildInlineInfoLabelHtml("reference_path", "Model-based reference path") + "</span>",
        '<span class="scenario-inline-chip scenario-inline-chip-scenario">' + escapeHtml(getSelectedScenario().label) + "</span>",
    ].join("");
    noteNode.textContent =
        "Observed MSA fertility appears through the latest ACS year. Scenario paths use only the MSA scenarios supported by the current ACS and ATUS inputs. " +
        getMsaCoverageExplanation() +
        " Interpret metro-level paths as exploratory spatial patterns rather than exact local forecasts." +
        (dashboardState.selectedScenario === "reference_path"
            ? " Reference path selected: the projected scenario line overlaps the reference path by definition."
            : "") +
        (contextNote ? " " + contextNote : "") +
        (proxyNote ? " " + proxyNote : "");
    if (!hasScenarioSeries("msa", msa.geography_id, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon)) {
        renderPlotFallback("msa-line-chart", MSA_RESULTS_UNAVAILABLE_MESSAGE);
        takeawayNode.textContent = MSA_RESULTS_UNAVAILABLE_MESSAGE;
        return;
    }
    if (!hasRenderableStateContext(context)) {
        renderPlotFallback("msa-line-chart", "Unavailable for current selection.");
        takeawayNode.textContent = "Unavailable for current selection.";
        return;
    }
    const chartSpec = buildLineChartSpec("msa", msa.geography_name, context);
    plotChart("msa-line-chart", chartSpec.traces, chartSpec.layout);
    takeawayNode.textContent = buildSummarySentence("msa", msa.geography_name, getSelectedModel().label, getSelectedScenario().label, dashboardState.selectedModel, dashboardState.selectedScenario, context.scenarioDifference, dashboardState.selectedHorizon, context.mainDriver, true);
}

function renderStateLegend() {
    const legendNode = document.getElementById("state-line-legend");
    if (!legendNode) {
        return;
    }
    legendNode.innerHTML = [
        '<span class="scenario-inline-chip scenario-inline-chip-observed">Observed</span>',
        '<span class="scenario-inline-chip scenario-inline-chip-reference">' + buildInlineInfoLabelHtml("reference_path", "Model-based reference path") + "</span>",
        '<span class="scenario-inline-chip scenario-inline-chip-scenario">' + escapeHtml(getSelectedScenario().label) + "</span>",
    ].join("");
}

function updateStateLineNote() {
    const noteNode = document.getElementById("state-line-note");
    if (!noteNode) {
        return;
    }
    noteNode.textContent =
        "Both lines can move down over time. The key comparison is whether the projected path under this scenario stays above or below the model-based reference path."
        + (dashboardState.selectedScenario === "reference_path"
            ? " Reference path selected: the projected scenario line overlaps the reference path by definition."
            : "");
}

function getCompareMetricConfig(geoType) {
    const digits = geoType === "msa" ? 3 : 1;
    if (dashboardState.selectedOutcome === "reference_path") {
        return {
            key: "referenceFinal",
            digits: digits,
            valueLabel: "Model-based reference path",
            valueUnit: "Births per 1,000 women aged " + WOMEN_AGE_LABEL,
            stripText: "Reference path is model-based and does not vary by scenario for a fixed geography and model.",
            noteText: "The selected display metric is the model-based reference path. Scenario A and Scenario B should match exactly for the same geography, model, and horizon year.",
            comparisonLabel: "Difference between displayed values",
            formatValue: function (value) {
                return formatNumber(value, digits);
            },
        };
    }
    if (dashboardState.selectedOutcome === "scenario_path") {
        return {
            key: "scenarioFinal",
            digits: digits,
            valueLabel: "Projected path under this scenario",
            valueUnit: "Births per 1,000 women aged " + WOMEN_AGE_LABEL,
            stripText: "Scenario comparison = Scenario A projected path \u2212 Scenario B projected path",
            noteText: "The selected display metric is the projected GFR level under each scenario at the chosen horizon year.",
            comparisonLabel: "Difference between displayed values",
            formatValue: function (value) {
                return formatNumber(value, digits);
            },
        };
    }
    return {
        key: "scenarioDifference",
        digits: digits,
        valueLabel: "Scenario difference from reference path",
        valueUnit: "Births per 1,000 women aged " + WOMEN_AGE_LABEL,
        stripText: "Scenario comparison = Scenario A difference \u2212 Scenario B difference",
        noteText: "The selected display metric is change relative to the model-based reference path at the chosen horizon year.",
        comparisonLabel: "Difference between Scenario A and Scenario B",
        formatValue: function (value) {
            return formatSignedValue(normalizeDifferenceForMeaning(value), digits);
        },
    };
}

function getCompareProxyNote(geoType, scenarioIds) {
    if (geoType !== "msa") {
        return "";
    }
    const notes = scenarioIds.map(function (scenarioId) {
        return getMsaProxyScenarioNote(scenarioId);
    }).filter(Boolean);
    return notes.length ? notes[0] : "";
}

function renderCompare() {
    const geoType = dashboardState.compareGeoType === "msa" && availability.msa.available
        ? "msa"
        : "state";
    const geography = getGeographyDisplay(geoType, dashboardState.comparePlaceId);
    const scenarioA = lookup.scenarioById.get(dashboardState.compareScenarioA);
    const scenarioB = lookup.scenarioById.get(dashboardState.compareScenarioB);
    const metricGrid = document.getElementById("scenario-compare-metric-grid");
    const stripNode = document.getElementById("scenario-compare-strip");
    const noteNode = document.getElementById("scenario-compare-note");
    const textNode = document.getElementById("scenario-compare-text");
    const metricConfig = getCompareMetricConfig(geoType);
    if (!geography || !scenarioA || !scenarioB) {
        renderPlotFallback("scenario-compare-chart", "Unavailable for current selection.");
        if (metricGrid) {
            metricGrid.innerHTML = renderCompareMessageCard("Unavailable for current selection.");
        }
        if (stripNode) {
            stripNode.textContent = metricConfig.stripText;
        }
        if (noteNode) {
            noteNode.textContent = metricConfig.noteText;
        }
        if (textNode) {
            textNode.textContent = "Unavailable for current selection.";
        }
        return;
    }

    const contextA = getScenarioContext(geoType, geography.geography_id, dashboardState.selectedModel, dashboardState.compareScenarioA, dashboardState.selectedHorizon);
    const contextB = getScenarioContext(geoType, geography.geography_id, dashboardState.selectedModel, dashboardState.compareScenarioB, dashboardState.selectedHorizon);
    const scenarioAValue = Number(contextA[metricConfig.key]);
    const scenarioBValue = Number(contextB[metricConfig.key]);
    if (!Number.isFinite(scenarioAValue) || !Number.isFinite(scenarioBValue)) {
        renderPlotFallback("scenario-compare-chart", "Unavailable for current selection.");
        if (metricGrid) {
            metricGrid.innerHTML = renderCompareMessageCard("Unavailable for current selection.");
        }
        if (stripNode) {
            stripNode.textContent = metricConfig.stripText;
        }
        if (noteNode) {
            noteNode.textContent = metricConfig.noteText;
        }
        if (textNode) {
            textNode.textContent = "Unavailable for current selection.";
        }
        return;
    }
    const difference = scenarioAValue - scenarioBValue;
    const proxyNote = dashboardState.selectedOutcome === "reference_path"
        ? ""
        : getCompareProxyNote(geoType, [dashboardState.compareScenarioA, dashboardState.compareScenarioB]);
    const formattedScenarioAValue = dashboardState.selectedOutcome === "scenario_difference"
        ? formatSignedValue(normalizeDifferenceForMeaning(scenarioAValue), metricConfig.digits)
        : formatNumber(scenarioAValue, metricConfig.digits);
    const formattedScenarioBValue = dashboardState.selectedOutcome === "scenario_difference"
        ? formatSignedValue(normalizeDifferenceForMeaning(scenarioBValue), metricConfig.digits)
        : formatNumber(scenarioBValue, metricConfig.digits);
    const formattedDifferenceValue = dashboardState.selectedOutcome === "scenario_difference"
        ? formatSignedValue(normalizeDifferenceForMeaning(difference), metricConfig.digits)
        : formatSignedValue(difference, metricConfig.digits);
    const formattedDifferenceMagnitude = dashboardState.selectedOutcome === "scenario_difference"
        ? formatNumber(Math.abs(normalizeDifferenceForMeaning(difference)), metricConfig.digits)
        : formatNumber(Math.abs(difference), metricConfig.digits);
    if (stripNode) {
        stripNode.textContent = metricConfig.stripText;
    }
    if (noteNode) {
        noteNode.textContent = metricConfig.noteText + (proxyNote ? " " + proxyNote : "");
    }

    if (metricGrid) {
        metricGrid.innerHTML = [
            renderCompareMetricCard(
                "Scenario A " + metricConfig.valueLabel.toLowerCase(),
                scenarioA.label,
                scenarioAValue,
                { digits: metricConfig.digits, formattedValue: formattedScenarioAValue }
            ),
            renderCompareMetricCard(
                "Scenario B " + metricConfig.valueLabel.toLowerCase(),
                scenarioB.label,
                scenarioBValue,
                { digits: metricConfig.digits, formattedValue: formattedScenarioBValue }
            ),
            renderCompareMetricCard(
                metricConfig.comparisonLabel,
                "Scenario A \u2212 Scenario B",
                difference,
                { digits: metricConfig.digits, formattedValue: formattedDifferenceValue }
            ),
        ].join("");
    }

    plotChart("scenario-compare-chart", [{
        type: "bar",
        orientation: "h",
        x: [scenarioAValue, scenarioBValue, difference],
        y: [scenarioA.short_label || scenarioA.label, scenarioB.short_label || scenarioB.label, "Scenario A \u2212 Scenario B"],
        marker: {
            color: ["#1f6b75", "#c86d3f", difference >= 0 ? "#21484f" : "#8b3a22"],
        },
        hovertemplate: "%{y}: %{x:.3f}<extra></extra>",
    }], {
        margin: { t: 8, r: 18, b: 30, l: 110 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        xaxis: {
            title: metricConfig.valueUnit,
            zeroline: true,
            zerolinecolor: "#d6cab9",
            gridcolor: "#efe6d8",
        },
        yaxis: {
            automargin: true,
        },
    });

    if (textNode) {
        if (isApproximatelyEqualDifference(difference, geoType)) {
            textNode.textContent =
                "In " + geography.geography_name +
                ", the " + scenarioA.label +
                " scenario is approximately equal to the " + scenarioB.label +
                " scenario for the selected display metric in " + dashboardState.selectedHorizon + "."
                + (proxyNote ? " " + proxyNote : "");
        } else {
            textNode.textContent =
                "In " + geography.geography_name +
                ", the " + scenarioA.label +
                " scenario is " + formattedDifferenceMagnitude +
                " " + metricConfig.valueUnit.toLowerCase() + " " + (difference > 0 ? "higher" : "lower") +
                " than the " + scenarioB.label +
                " scenario in " + dashboardState.selectedHorizon + "."
                + (proxyNote ? " " + proxyNote : "");
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

function buildWhyThisWarningLinkHtml() {
    return [
        '<span class="scenario-model-help">',
        escapeHtml("Why this warning?"),
        buildInfoTooltipTextLinkHtml("model_reliability_warning", "Why this warning?"),
        "</span>",
    ].join("");
}

function buildBenchmarkPanelIntroHtml(geoType) {
    if (geoType === "msa") {
        return [
            '<p class="scenario-benchmark-note">Check robustness across models before interpreting any single MSA.</p>',
        ].join("");
    }
    return [
        '<p class="scenario-benchmark-note">The State view is the primary forecast view. State-level models are more stable and perform better out of sample, so this view is best for the main interpretation. ',
        buildInfoTooltipTextLinkHtml("state_primary_forecast_view", "Why this is primary"),
        "</p>",
    ].join("");
}

function renderModelStatus() {
    const selectedModel = getSelectedModel();

    function buildRows(geoType) {
        return (dashboardData.model_options || []).map(function (model) {
            const metrics = getMetricsForModel(geoType, model.id);
            const validation = metrics.find(function (row) { return row.split === "validation"; });
            const test = metrics.find(function (row) { return row.split === "test"; });
            const diagnostics = getModelReliabilityDiagnostics(geoType, model.id);
            const statusText = diagnostics.available
                ? (diagnostics.statusBadge || "Available")
                : "Unavailable";
            const detail = diagnostics.available
                ? (diagnostics.warningText || "Metrics not available.")
                : "Unavailable for the current bundle.";
            const meta = validation && test
                ? "Validation RMSE " + formatNumber(validation.rmse, 2)
                    + " | Test RMSE " + formatNumber(test.rmse, 2)
                    + (Number.isFinite(Number(test.r_squared))
                        ? " | Test R^2 " + formatNumber(test.r_squared, 2)
                        : "")
                : (
                    geoType === "msa"
                        ? "MSA benchmark metrics are not available in this bundle."
                        : ((dashboardData.metadata && dashboardData.metadata.benchmark_note) || "Metrics not available.")
                );
            return [
                '<div class="scenario-model-row' + (selectedModel && model.id === selectedModel.id ? " is-active" : "") + '">',
                "<strong>" + getModelDisplayLabel(model, geoType) + "</strong>",
                "<span>" + escapeHtml(statusText) + "</span>",
                "<small>" + escapeHtml(detail) + "</small>",
                meta ? "<small>" + escapeHtml(meta) + "</small>" : "",
                diagnostics.available ? buildWhyThisWarningLinkHtml() : "",
                "</div>",
            ].join("");
        }).join("");
    }

    const statePanel = document.getElementById("model-status-panel");
    if (statePanel) {
        statePanel.innerHTML = buildBenchmarkPanelIntroHtml("state") + buildRows("state");
    }
    const msaPanel = document.getElementById("msa-model-status-panel");
    if (msaPanel) {
        msaPanel.innerHTML = buildBenchmarkPanelIntroHtml("msa") + buildRows("msa");
    }
}

function renderMethodCards() {
    const msaOnlineMatchingNote = getMsaOnlineMatchingOverlayNote();
    const stateModelRecommendationNote = getStateModelRecommendationNote();
    const msaModelRecommendationNote = getMsaModelRecommendationNote();
    const cards = [
        {
            title: "Interpretation",
            body:
                "<p>This dashboard compares a selected " + buildInlineInfoLabelHtml("scenario_path") + " with the " + buildInlineInfoLabelHtml("reference_path") + " for each state and year. The key map outcome is the " + buildInlineInfoLabelHtml("scenario_difference") + ": scenario path minus reference path.</p><p>The State view is the primary forecast view. State-level models are more stable out of sample, so it is the main interpretation layer for scenario effects.</p><p>The Metro patterns view is exploratory. It helps show where digital-life scenarios may matter more or less across metropolitan labor markets, but it is best used for broad spatial patterns rather than exact local forecasts.</p><p>In the Metro patterns view, county polygons are used only as display geography; the analytical estimates remain at the identified MSA / CBSA level. Remote-work and online-matching MSA scenarios may use parent-state proxy inputs merged onto each MSA when fully MSA-native inputs are not available. MSA-specific reference paths are retained, but the scenario shock itself is proxy-based.</p>"
                + (stateModelRecommendationNote ? "<p>" + escapeHtml(stateModelRecommendationNote) + "</p>" : "")
                + (msaOnlineMatchingNote ? "<p>" + escapeHtml(msaOnlineMatchingNote) + "</p>" : "")
                + (msaModelRecommendationNote ? "<p>" + escapeHtml(msaModelRecommendationNote) + "</p>" : "")
                + "<p><a href=\"dashboard-methodology.html\">Open the full dashboard methodology note.</a></p>",
        },
        {
            title: "Models and validation",
            body:
                "<p>Statistical baseline, tree ML benchmark, and neural network benchmark are predictive tools used for projection under assumptions. Reliability labels are assigned separately for State and MSA views using held-out accuracy, coverage, and lower- or upper-bound diagnostics.</p>" + buildValidationHtml(),
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
    const stateTableHtml = buildMetricsTable("state");
    const msaTableHtml = buildMetricsTable("msa");
    const stateModelRecommendationNote = getStateModelRecommendationNote();
    const msaModelRecommendationNote = getMsaModelRecommendationNote();
    return [
        "<p>" + buildModelSplitNote() + "</p>",
        stateModelRecommendationNote ? "<p>" + escapeHtml(stateModelRecommendationNote) + "</p>" : "",
        "<p><strong>State models</strong></p>",
        stateTableHtml || "<p>State-model metrics are not available in this bundle.</p>",
        msaModelRecommendationNote ? "<p>" + escapeHtml(msaModelRecommendationNote) + "</p>" : "",
        "<p><strong>MSA models</strong></p>",
        msaTableHtml || "<p>MSA-model metrics are not available in this bundle.</p>",
        "<p>Reliability labels are assigned separately for State and MSA views using validation accuracy, coverage, and lower- or upper-bound diagnostics.</p>",
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
    const useReferencePath = scenarioId === "reference_path";

    const finalReferenceRecord = referenceRecords[referenceRecords.length - 1] || null;
    const finalScenarioRecord = useReferencePath
        ? (selectedRecords[selectedRecords.length - 1] || finalReferenceRecord)
        : (selectedRecords[selectedRecords.length - 1] || null);
    const manualAdjustmentFinal = geoType === "msa" || scenarioId === "reference_path"
        ? 0
        : computeManualAdjustment(entity, horizonYear, horizonYear, scenarioId);

    const referenceSeries = buildPathSeries(lastObserved, referenceRecords, false, horizonYear, entity, scenarioId);
    const scenarioSeries = buildPathSeries(lastObserved, selectedRecords, true, horizonYear, entity, scenarioId);

    const mechanismScores = combineMechanismScores(finalScenarioRecord, entity, scenarioId);
    const maxMechanismAbs = finiteArrayMax(mechanismOrder.map(function (item) {
        return Math.abs(mechanismScores[item.key] || 0);
    }).concat([0]));

    const referenceFinal = finalReferenceRecord ? Number(finalReferenceRecord.reference_path) : (lastObserved ? Number(lastObserved.value) : NaN);
    const scenarioFinal = useReferencePath
        ? referenceFinal
        : (finalScenarioRecord ? Number(finalScenarioRecord.scenario_path) + manualAdjustmentFinal : NaN);
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
        mainDriver: finalScenarioRecord && finalScenarioRecord.main_driver ? finalScenarioRecord.main_driver : (Number.isFinite(scenarioFinal) ? findMainDriver(mechanismScores) : ""),
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
        const manualAdjustment = useScenarioPath && entity && entity.geography_id && lookup.msaById.has(entity.geography_id)
            ? 0
            : (useScenarioPath ? computeManualAdjustment(entity, record.year, horizonYear, scenarioId) : 0);
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

function formatLineChartAnnotationLabel(label, geoType) {
    const suffix = " | " + String(geoType || "").toUpperCase();
    const base = String(label || "").trim() || "Selected geography";
    const maxLength = geoType === "msa" ? 44 : 64;
    if ((base + suffix).length <= maxLength) {
        return base + suffix;
    }
    return base.slice(0, Math.max(0, maxLength - suffix.length - 3)).trimEnd() + "..." + suffix;
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
        name: "Model-based reference path",
        line: { color: "#184f58", width: 3 },
        hovertemplate: "Model-based reference path %{x}: %{y:.1f}<extra></extra>",
    });

    traces.push({
        x: context.scenarioSeries.map(function (row) { return row.year; }),
        y: context.scenarioSeries.map(function (row) { return row.value; }),
        mode: "lines",
        name: getSelectedScenario().label,
        line: { color: "#bf6b3c", width: 3 },
        hovertemplate: "Projected path under this scenario %{x}: %{y:.1f}<extra></extra>",
    });

    return {
        traces: traces,
        layout: {
            margin: { t: geoType === "msa" ? 34 : 20, r: 18, b: 48, l: 56 },
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
                y: 1.02,
                xref: "paper",
                yref: "paper",
                xanchor: "right",
                yanchor: "bottom",
                align: "right",
                showarrow: false,
                text: formatLineChartAnnotationLabel(label, geoType),
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
    const selectedModel = getSelectedModel();
    const selectedScenario = getSelectedScenario();
    const selectedOutcome = getSelectedOutcome();
    const html = [
        '<span class="scenario-headline-segment">' + buildInlineInfoLabelHtml(selectedModel.id, selectedModel.label) + "</span>",
        '<span class="scenario-summary-separator" aria-hidden="true">|</span>',
        '<span class="scenario-headline-segment">' + escapeHtml(String(dashboardState.selectedHorizon)) + "</span>",
        '<span class="scenario-summary-separator" aria-hidden="true">|</span>',
        '<span class="scenario-headline-segment">' + buildOutcomeLabelHtml(selectedOutcome) + "</span>",
        '<span class="scenario-summary-separator" aria-hidden="true">|</span>',
        '<span class="scenario-headline-segment">' + buildInlineInfoLabelHtml(selectedScenario.id, selectedScenario.label) + "</span>",
    ].join("");
    const strip = document.getElementById("map-selection-strip");
    if (strip) {
        strip.innerHTML = html;
    }
    const msaStrip = document.getElementById("msa-selection-strip");
    if (msaStrip) {
        msaStrip.innerHTML = html;
    }
}

function initializeSectionNavigation() {
    document.querySelectorAll("[data-section-link]").forEach(function (link) {
        link.addEventListener("click", function (event) {
            event.preventDefault();
            const geoLink = link.getAttribute("data-geo-link");
            if (geoLink) {
                if (geoLink === "msa" && !availability.msa.available) {
                    setUtilityStatus(availability.msa.reason);
                    return;
                }
                setSelectedGeoType(geoLink === "msa" ? "msa" : "state");
                populateControls();
                syncControls();
                renderDashboard();
            }
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
        const geoLink = link.getAttribute("data-geo-link");
        const isPrimaryGeoLink = geoLink && activeId === "us-state";
        const isActive = isPrimaryGeoLink
            ? geoLink === dashboardState.selectedGeoType
            : (!geoLink && link.getAttribute("href") === "#" + activeId);
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
        setUtilityStatus(dashboardState.selectedGeoType === "msa"
            ? "No MSA rows match the current filters."
            : "Unavailable for current selection.");
        return;
    }
    downloadCsv(rows, buildCurrentViewDownloadFilename());
    setUtilityStatus(dashboardState.selectedGeoType === "msa"
        ? "MSA current-view CSV downloaded."
        : "Current view CSV downloaded.");
}

function downloadAllScenarioData() {
    const allRows = lookup.allForecastRecords.filter(function (record) {
        return record.geography_type === dashboardState.selectedGeoType;
    }).map(function (record) {
        return buildExportRow(record, {
            download_scope: "all_loaded_data",
            view_segment: "all_loaded_rows",
        });
    });
    if (!allRows.length) {
        setUtilityStatus(dashboardState.selectedGeoType === "msa"
            ? "No MSA rows are currently loaded."
            : "Unavailable for current selection.");
        return;
    }
    downloadCsv(allRows, buildAllScenarioDataDownloadFilename());
    setUtilityStatus("All currently loaded "
        + (dashboardState.selectedGeoType === "msa" ? "msa" : "state")
        + "-year scenario data downloaded.");
}

function downloadRankings() {
    const rows = getRankingsExportRows();
    if (!rows.length) {
        setUtilityStatus("Unavailable for current selection.");
        return;
    }
    downloadCsv(rows, buildRankingsDownloadFilename());
    setUtilityStatus("Rankings CSV downloaded.");
}

function downloadBenchmarks() {
    const rows = (dashboardState.selectedGeoType === "msa"
        ? (Array.isArray(dashboardData.msa_model_metrics) ? dashboardData.msa_model_metrics : [])
        : (Array.isArray(dashboardData.model_metrics) ? dashboardData.model_metrics : [])
    ).map(function (row) {
        return {
            geography_type: row.geography_type || dashboardState.selectedGeoType,
            geography_id: dashboardState.selectedGeoType === "msa" ? (dashboardState.selectedMsaId || "") : dashboardState.selectedStateFips,
            geography_name: dashboardState.selectedGeoType === "msa"
                ? ((getSelectedMsa() && getSelectedMsa().geography_name) || "")
                : getSelectedState().state_name,
            model: row.model || row.model_name || "",
            split: row.split || "",
            rmse: row.rmse,
            mae: row.mae,
            mape: row.mape,
            r_squared: row.r_squared,
            n_obs: row.n_obs,
        };
    });
    if (!rows.length) {
        setUtilityStatus("Benchmarks unavailable for the current selection.");
        return;
    }
    downloadBenchmarkCsv(rows, "digital-life-fertility-" + dashboardState.selectedGeoType + "-benchmarks.csv");
    setUtilityStatus("Benchmark CSV downloaded.");
}

function downloadCountyDisplayLayer() {
    const rows = getCountyDisplayRowsForCurrentView(false).map(function (row) {
        const hasEstimate = row.estimate_status === "estimated_msa";
        return {
            county_fips: valueOrBlank(row.county_fips),
            county_name: valueOrBlank(row.county_name),
            state_fips: valueOrBlank(row.state_fips),
            state_abbr: valueOrBlank(row.state_abbr),
            state_name: valueOrBlank(row.state_name),
            cbsa_code: valueOrBlank(row.cbsa_code),
            cbsa_name: valueOrBlank(row.cbsa_name),
            cbsa_type: valueOrBlank(row.cbsa_type),
            estimate_status: valueOrBlank(row.estimate_status),
            estimated_geography_id: valueOrBlank(row.estimated_geography_id),
            estimated_geography_name: valueOrBlank(row.estimated_geography_name),
            selected_horizon_year: valueOrBlank(dashboardState.selectedHorizon),
            scenario: valueOrBlank(dashboardState.selectedScenario),
            scenario_label: valueOrBlank(getSelectedScenario().label),
            outcome: valueOrBlank(dashboardState.selectedOutcome),
            outcome_label: valueOrBlank(getSelectedOutcome().label),
            scenario_effect: hasEstimate ? valueOrBlank(row.scenario_difference) : "",
            selected_outcome_value: hasEstimate ? valueOrBlank(row.selected_outcome_value) : "",
            unit_label: hasEstimate ? getDashboardUnitLabel() : "",
        };
    });
    if (!rows.length) {
        setUtilityStatus("County display layer is unavailable.");
        return;
    }
    downloadCountyDisplayLayerCsv(rows, "county_cbsa_display_layer.csv");
    setUtilityStatus("County-CBSA display layer CSV downloaded.");
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
    url.searchParams.set("geo", dashboardState.selectedGeoType);
    url.searchParams.set("place", dashboardState.selectedGeoType === "msa"
        ? dashboardState.selectedMsaId
        : getStateAbbreviation(dashboardState.selectedStateFips));
    url.searchParams.set("model", dashboardState.selectedModel);
    url.searchParams.set("scenario", dashboardState.selectedScenario);
    url.searchParams.set("year", String(dashboardState.selectedHorizon));
    url.searchParams.set("outcome", dashboardState.selectedOutcome);
    copyTextToClipboard(url.toString(), "Shareable link copied.");
}

function updateUrlState() {
    const url = new URL(window.location.href);
    url.searchParams.set("geo", dashboardState.selectedGeoType);
    url.searchParams.set("place", dashboardState.selectedGeoType === "msa"
        ? dashboardState.selectedMsaId
        : getStateAbbreviation(dashboardState.selectedStateFips));
    url.searchParams.set("model", dashboardState.selectedModel);
    url.searchParams.set("scenario", dashboardState.selectedScenario);
    url.searchParams.set("year", String(dashboardState.selectedHorizon));
    url.searchParams.set("outcome", dashboardState.selectedOutcome);
    window.history.replaceState({}, "", url.toString());
}

function getCurrentViewExportRows() {
    const currentRows = [];
    if (dashboardState.selectedGeoType === "msa") {
        getMsaRowsForCurrentView().forEach(function (row) {
            currentRows.push(buildExportRow(row, Object.assign(getCurrentAssumptionOverrides(), {
                download_scope: "current_view",
                view_segment: "filtered_geography_snapshot",
            })));
        });
        getSelectedMsaSeriesRows().forEach(function (row) {
            currentRows.push(buildExportRow(row, Object.assign(getCurrentAssumptionOverrides(), {
                download_scope: "current_view",
                view_segment: "selected_geography_series",
            })));
        });
    } else {
        getStateRowsForCurrentView().forEach(function (row) {
            currentRows.push(buildExportRow(row, Object.assign(getCurrentAssumptionOverrides(), {
                download_scope: "current_view",
                view_segment: "filtered_geography_snapshot",
            })));
        });
        getSelectedStateSeriesRows().forEach(function (row) {
            currentRows.push(buildExportRow(row, Object.assign(getCurrentAssumptionOverrides(), {
                download_scope: "current_view",
                view_segment: "selected_geography_series",
            })));
        });
    }

    return dedupeExportRows(currentRows);
}

function getRankingsExportRows() {
    const rows = [];
    const baseRows = dashboardState.selectedGeoType === "msa" ? getMsaRowsForCurrentView() : getStateRowsForCurrentView();
    const upwardRows = buildRankingRows(baseRows, "upward");
    const downwardRows = buildRankingRows(baseRows, "downward");
    const closestRows = buildRankingRows(baseRows, "closest");

    upwardRows.forEach(function (row) {
        rows.push(buildExportRow(row, {
            rank: row.rank,
            ranking_group: "largest_upward_scenario_differences",
            download_scope: "rankings",
            view_segment: "ranking_rows",
        }));
    });
    downwardRows.forEach(function (row) {
        rows.push(buildExportRow(row, {
            rank: row.rank,
            ranking_group: "largest_downward_scenario_differences",
            download_scope: "rankings",
            view_segment: "ranking_rows",
        }));
    });
    closestRows.forEach(function (row) {
        rows.push(buildExportRow(row, {
            rank: row.rank,
            ranking_group: "closest_to_reference_path",
            download_scope: "rankings",
            view_segment: "ranking_rows",
        }));
    });

    return rows;
}

function getStateRowsForCurrentView() {
    return getAvailableStates().map(function (state) {
        const context = getScenarioContext("state", state.state_fips, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
        const snapshot = getScenarioSnapshotValues(context, dashboardState.selectedOutcome, dashboardState.selectedScenario);
        return {
            geography_type: "state",
            geography_id: state.state_fips,
            geography_name: state.state_name,
            state_name: state.state_name,
            state_abbr: state.state_abbr,
            year: dashboardState.selectedHorizon,
            model: dashboardState.selectedModel,
            scenario: dashboardState.selectedScenario,
            reference_path: snapshot.reference_path,
            scenario_path: snapshot.scenario_path,
            scenario_difference: snapshot.scenario_difference,
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
    return buildMsaRowsForSelection(getFilteredMsas());
}

function getAllMsaRowsForCurrentSelection() {
    if (!availability.msa.available) {
        return [];
    }
    return buildMsaRowsForSelection(Array.from(lookup.msaById.values()).sort(function (a, b) {
        return a.geography_name.localeCompare(b.geography_name);
    }));
}

function buildMsaRowsForSelection(msas) {
    return msas.map(function (msa) {
        const context = getScenarioContext("msa", msa.geography_id, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon);
        const snapshot = getScenarioSnapshotValues(context, dashboardState.selectedOutcome, dashboardState.selectedScenario);
        return {
            geography_type: "msa",
            geography_id: msa.geography_id,
            geography_name: msa.geography_name,
            state_fips: msa.state_fips || "",
            state_abbr: msa.state_abbr || "",
            state_name: msa.state_name || "",
            cbsa_code: msa.cbsa_code || msa.geography_id,
            msa_name: msa.geography_name,
            year: dashboardState.selectedHorizon,
            model: dashboardState.selectedModel,
            scenario: dashboardState.selectedScenario,
            reference_path: snapshot.reference_path,
            scenario_path: snapshot.scenario_path,
            scenario_difference: snapshot.scenario_difference,
            scenario_shift_component: context.scenarioShiftComponent,
            manual_adjustment_component: context.manualAdjustmentComponent,
            main_driver: context.mainDriver,
        };
    });
}

function getCountyDisplayRowsForCurrentView(applyStateFilter) {
    if (!availability.msa.available) {
        return [];
    }
    const shouldApplyStateFilter = applyStateFilter !== false;
    const filter = dashboardState.selectedMsaStateFilter;
    const msaRowsById = new Map();
    const msaRows = shouldApplyStateFilter
        ? getMsaRowsForCurrentView()
        : getAllMsaRowsForCurrentSelection();
    msaRows.forEach(function (row) {
        msaRowsById.set(String(row.geography_id || ""), row);
    });
    return lookup.countyDisplayRows.filter(function (county) {
        if (!shouldApplyStateFilter || filter === "all") {
            return true;
        }
        return county.state_abbr === filter || county.state_name === filter;
    }).map(function (county) {
        const estimatedGeographyId = String(county.estimated_geography_id || "");
        const parentRow = estimatedGeographyId ? msaRowsById.get(estimatedGeographyId) : null;
        const parentEntity = estimatedGeographyId ? lookup.msaById.get(estimatedGeographyId) : null;
        return {
            county_fips: county.county_fips,
            county_name: county.county_name,
            state_fips: county.state_fips,
            state_abbr: county.state_abbr,
            state_name: county.state_name,
            cbsa_code: county.cbsa_code || "",
            cbsa_name: county.cbsa_name || "",
            cbsa_type: county.cbsa_type || "",
            estimate_status: county.estimate_status || "outside_cbsa",
            estimated_geography_id: estimatedGeographyId,
            estimated_geography_name: (parentEntity && parentEntity.geography_name) || county.estimated_geography_name || "",
            reference_path: parentRow ? toFiniteOrNaN(parentRow.reference_path) : NaN,
            scenario_path: parentRow ? toFiniteOrNaN(parentRow.scenario_path) : NaN,
            scenario_difference: parentRow ? toFiniteOrNaN(parentRow.scenario_difference) : NaN,
            selected_outcome_value: parentRow ? toFiniteOrNaN(parentRow[dashboardState.selectedOutcome]) : NaN,
            main_driver: parentRow ? String(parentRow.main_driver || "") : "",
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
    const entity = getSelectedMsa();
    return getForecastSeries("msa", dashboardState.selectedMsaId, dashboardState.selectedModel, dashboardState.selectedScenario)
        .filter(function (record) { return record.year <= dashboardState.selectedHorizon; })
        .map(function (record) {
            const adjustment = 0;
            const referencePath = Number(record.reference_path);
            const scenarioPath = Number(record.scenario_path) + adjustment;
            return {
                geography_type: "msa",
                geography_id: dashboardState.selectedMsaId,
                geography_name: entity.geography_name,
                state_fips: entity.state_fips || "",
                state_abbr: entity.state_abbr || "",
                state_name: entity.state_name || "",
                cbsa_code: entity.cbsa_code || dashboardState.selectedMsaId,
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

function hasScenarioSeries(geoType, geographyId, modelId, scenarioId, horizonYear) {
    if (scenarioId === "reference_path") {
        return getForecastSeries(geoType, geographyId, modelId, "reference_path").some(function (record) {
            return record.year <= horizonYear;
        });
    }
    return getForecastSeries(geoType, geographyId, modelId, scenarioId).some(function (record) {
        return record.year <= horizonYear;
    });
}

function buildRankingRows(rows, mode) {
    const tolerance = getScenarioDifferenceToleranceForRows(rows);
    let filtered = rows.filter(function (row) {
        return Number.isFinite(row.scenario_difference);
    });

    if (mode === "upward") {
        filtered = filtered.filter(function (row) {
            return row.scenario_difference > tolerance;
        }).sort(function (a, b) {
            return b.scenario_difference - a.scenario_difference || a.geography_name.localeCompare(b.geography_name);
        });
    } else if (mode === "downward") {
        filtered = filtered.filter(function (row) {
            return row.scenario_difference < -tolerance;
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
            '<span>' + describeRankingDifference(row.scenario_difference, row.geography_type) + "</span>",
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
        "<h4>" + config.title + "</h4>",
        '<div class="scenario-ranking-unit">Change relative to the model-based reference path, births per 1,000 women aged ' + WOMEN_AGE_LABEL + "</div>",
        "</div>",
        '<div class="scenario-ranking-list">' + primarySection + "</div>",
        "</section>",
    ].join("");
}

function renderCompareMetricCard(title, subtitle, value, options) {
    const cardOptions = options || {};
    const formattedValue = typeof cardOptions.formattedValue === "string"
        ? cardOptions.formattedValue
        : formatSignedValue(value, Number.isFinite(cardOptions.digits) ? cardOptions.digits : 1);
    return [
        '<article class="scenario-compare-metric-card">',
        '<p class="scenario-compare-metric-label">' + title + "</p>",
        '<strong class="scenario-compare-metric-value">' + formattedValue + "</strong>",
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
    if (isApproximatelyEqualDifference(difference, geoType)) {
        return "In " + geographyName + ", the " + modelLabel + " shows little change under the " + scenarioLabel + " scenario in " + year + ". The scenario stays close to the reference path.";
    }
    return "In " + geographyName + ", the " + modelLabel + " shows that the " + scenarioLabel + " scenario "
        + (difference > 0 ? "raises" : "lowers")
        + " fertility by " + formatNumber(Math.abs(difference), geoType === "msa" ? 3 : 1)
        + " births per 1,000 women aged " + WOMEN_AGE_LABEL + " in " + year
        + ", compared with the reference path. The main driver is " + (driver || "the observed pattern") + ".";
}

function getScenarioSummaryExplanation(modelId, scenarioId, difference) {
    return "";
}

function getPrimarySummaryGeography() {
    if (dashboardState.selectedGeoType === "msa" && availability.msa.available) {
        const msa = getSelectedMsa();
        return msa
            ? {
                geography_type: "msa",
                geography_id: msa.geography_id,
                geography_name: msa.geography_name,
            }
            : { geography_type: "msa", geography_id: "", geography_name: "" };
    }
    const state = getSelectedState();
    return {
        geography_type: "state",
        geography_id: state.state_fips,
        geography_name: state.state_name,
    };
}

function decodeCompactMsaForecastRecords() {
    const schema = Array.isArray(dashboardData.msa_forecast_schema) ? dashboardData.msa_forecast_schema : [];
    const rows = Array.isArray(dashboardData.msa_forecast_records) ? dashboardData.msa_forecast_records : [];
    if (!schema.length || !rows.length) {
        return [];
    }
    return rows.map(function (values) {
        const record = { geography_type: "msa" };
        schema.forEach(function (key, index) {
            record[key] = Array.isArray(values) ? values[index] : undefined;
        });
        return record;
    });
}

function decodeCountyDisplayRecords() {
    const schema = Array.isArray(dashboardData.county_display_schema) ? dashboardData.county_display_schema : [];
    const rows = Array.isArray(dashboardData.county_display_records) ? dashboardData.county_display_records : [];
    if (!schema.length || !rows.length) {
        return [];
    }
    return rows.map(function (values) {
        const record = {};
        schema.forEach(function (key, index) {
            record[key] = Array.isArray(values) ? values[index] : undefined;
        });
        return record;
    });
}

function normalizeForecastRecords() {
    const rawRecords = (dashboardData.forecast_records || []).concat(decodeCompactMsaForecastRecords());
    return rawRecords.map(function (record) {
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
            availability_flag: record.availability_flag || "",
            low_sample_flag: Boolean(record.low_sample_flag),
            caveat_flag: Boolean(record.caveat_flag),
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

function getSelectedMsa() {
    return lookup.msaById.get(dashboardState.selectedMsaId) || getFilteredMsas()[0] || null;
}

function getSelectedModel() {
    return lookup.modelById.get(dashboardState.selectedModel)
        || lookup.modelById.get(getPreferredModelForGeo(dashboardState.selectedGeoType))
        || (dashboardData.model_options || [])[0];
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

function getAvailableMsaScenarioIds() {
    const explicit = Array.isArray(dashboardData.msa_available_scenarios)
        ? dashboardData.msa_available_scenarios
        : [];
    if (explicit.length) {
        return explicit;
    }
    const rows = lookup.recordsByGeoType.get("msa") || [];
    const ids = new Set();
    rows.forEach(function (row) {
        if (row.scenario && row.scenario !== "reference_path") {
            ids.add(row.scenario);
        }
    });
    return Array.from(ids);
}

function getScenarioChoicesForGeoType(geoType) {
    const msaScenarioIds = getAvailableMsaScenarioIds();
    return (dashboardData.scenario_options || []).filter(function (scenario) {
        if (scenario.id === "reference_path") {
            return false;
        }
        if (geoType === "msa") {
            return msaScenarioIds.indexOf(scenario.id) !== -1;
        }
        return true;
    });
}

function getScenarioChoices() {
    return getScenarioChoicesForGeoType(dashboardState.selectedGeoType);
}

function getScenarioControlChoicesForGeoType(geoType) {
    const allScenarios = dashboardData.scenario_options || [];
    if (geoType === "msa") {
        const msaScenarioIds = new Set(getAvailableMsaScenarioIds());
        const hasMsaReferencePath = (lookup.recordsByGeoType.get("msa") || []).some(function (row) {
            return row.scenario === "reference_path";
        });
        return allScenarios.filter(function (scenario) {
            return scenario.id === "reference_path"
                ? hasMsaReferencePath
                : msaScenarioIds.has(scenario.id);
        });
    }
    return allScenarios.slice();
}

function getScenarioControlChoices() {
    return getScenarioControlChoicesForGeoType(dashboardState.selectedGeoType);
}

function scenarioChoiceExists(scenarioId, geoType) {
    return getScenarioControlChoicesForGeoType(geoType || dashboardState.selectedGeoType).some(function (scenario) {
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
        return "Model-based reference path";
    }
    if (outcomeId === "scenario_path") {
        return "Projected path under this scenario";
    }
    return fallbackLabel || "Change relative to reference path";
}

function buildOutcomeLabelHtml(outcome) {
    if (!outcome) {
        return buildInlineInfoLabelHtml("scenario_difference", "Change relative to reference path");
    }
    if (outcome.id === "reference_path") {
        return buildInlineInfoLabelHtml("reference_path_level", "Model-based reference path");
    }
    if (outcome.id === "scenario_path") {
        return buildInlineInfoLabelHtml("scenario_path_level", "Projected path under this scenario");
    }
    return buildInlineInfoLabelHtml("scenario_difference", "Change relative to reference path");
}

function buildHeroSummaryDetails(label, panelId, bodyHtml) {
    return [
        '<details class="scenario-summary-detail" data-utility-panel>',
        '<summary class="scenario-summary-link" aria-expanded="false" aria-controls="' + panelId + '">' + escapeHtml(label) + "</summary>",
        '<div class="scenario-summary-panel" id="' + panelId + '">' + bodyHtml + "</div>",
        "</details>",
    ].join("");
}

function getHeroScenarioDefinition(scenarioId) {
    if (scenarioId === "remote_work_saves_time") {
        return "Remote work can save commuting time and increase schedule flexibility. The scenario shows how fertility changes if this raises the scenario path relative to the model-based reference path.";
    }
    if (scenarioId === "digital_distraction_crowds_out") {
        return "Screen leisure and digital media time may reduce time available for in-person interaction, dating, or family formation.";
    }
    if (scenarioId === "online_life_helps_matching") {
        return "Online social life and digital matching tools may make it easier for people to meet, match, or maintain relationships.";
    }
    if (scenarioId === "home_centered_digital_life_increases_care_work") {
        return "More digital life may keep more activities inside the home and increase unpaid care or household work burdens.";
    }
    return "Scenario definition unavailable.";
}

function getHeroBenchmarkDefinition(modelId) {
    if (modelId === "statistical_ridge") {
        return "Primary State benchmark. Transparent, stable, and strong out of sample for the main interpretation.";
    }
    if (modelId === "tree_gradient_boosting") {
        return "State robustness benchmark with strong held-out accuracy, and the preferred MSA display model because it preserves metropolitan variation.";
    }
    if (modelId === "temporal_neural_net") {
        return "A nonlinear robustness benchmark that is shown for comparison rather than primary interpretation.";
    }
    return "Benchmark definition unavailable.";
}

function getScenarioStoryYear() {
    const years = getAvailableHorizonYears();
    if (years.includes(2050)) {
        return 2050;
    }
    return years.length ? years[years.length - 1] : dashboardState.selectedHorizon;
}

function getAverageScenarioDifference(scenarioId, year) {
    const rows = lookup.allForecastRecords.filter(function (record) {
        return record.geography_type === "state"
            && record.model === dashboardState.selectedModel
            && record.scenario === scenarioId
            && Number(record.year) === Number(year)
            && Number.isFinite(Number(record.scenario_difference));
    });
    if (!rows.length) {
        return NaN;
    }
    return rows.reduce(function (sum, row) {
        return sum + Number(row.scenario_difference);
    }, 0) / rows.length;
}

function renderOverallImpactCard(rows, unitLabel) {
    const options = typeof unitLabel === "object" && unitLabel !== null
        ? unitLabel
        : { unitLabel: unitLabel };
    const geographyPlural = options.geographyPlural || "states";
    const unavailableMessage = options.unavailableMessage || "Overall direction unavailable for the current selection.";
    const tolerance = getScenarioDifferenceToleranceForRows(rows);
    const digits = getSummaryDisplayDigitsForRows(rows);
    const differences = rows.map(function (row) {
        return Number(row.scenario_difference);
    }).filter(Number.isFinite);
    const meanDifference = differences.length
        ? differences.reduce(function (sum, value) { return sum + value; }, 0) / differences.length
        : NaN;
    const positiveCount = differences.filter(function (value) {
        return value > tolerance;
    }).length;
    const negativeCount = differences.filter(function (value) {
        return value < -tolerance;
    }).length;
    const neutralCount = differences.length - positiveCount - negativeCount;
    const directionText = !Number.isFinite(meanDifference)
        ? unavailableMessage
        : meanDifference > tolerance
            ? "On average, this scenario raises fertility relative to the model-based reference path."
            : meanDifference < -tolerance
                ? "On average, this scenario lowers fertility relative to the model-based reference path."
                : "On average, this scenario stays close to the model-based reference path.";

    return [
        '<section class="scenario-ranking-card scenario-ranking-card-summary">',
        '<div class="scenario-ranking-head">',
        "<h4>Does this scenario raise fertility overall?</h4>",
        '<div class="scenario-ranking-unit">' + escapeHtml(options.unitLabel || "State-average change") + " by " + escapeHtml(String(dashboardState.selectedHorizon)) + "</div>",
        "</div>",
        Number.isFinite(meanDifference)
            ? '<strong class="scenario-ranking-highlight">' + formatSignedValue(meanDifference, digits) + "</strong>"
            : '<strong class="scenario-ranking-highlight">N/A</strong>',
        '<p class="scenario-ranking-card-message">' + escapeHtml(directionText) + "</p>",
        '<p class="scenario-ranking-card-message">Above reference in ' + positiveCount + " " + geographyPlural + ", below in " + negativeCount + " " + geographyPlural + ", and near the reference path in " + neutralCount + " " + geographyPlural + ".</p>",
        "</section>",
    ].join("");
}

function hasFiniteScenarioDifferences(rows) {
    return rows.some(function (row) {
        return Number.isFinite(Number(row.scenario_difference));
    });
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

function buildInfoTooltipTextLinkHtml(termKey, labelOverride) {
    const info = infoTooltipCopy[termKey];
    if (!info) {
        return "";
    }
    infoTooltipSequence += 1;
    const tooltipId = "scenario-info-tooltip-" + termKey + "-" + infoTooltipSequence;
    const buttonLabel = labelOverride || info.label;
    return [
        '<button type="button" class="scenario-info-text-link" data-tooltip-button data-tooltip-id="' + tooltipId + '" aria-label="' + escapeHtml(buttonLabel) + '" aria-expanded="false" aria-controls="' + tooltipId + '" aria-describedby="' + tooltipId + '">',
        escapeHtml(buttonLabel),
        "</button>",
        '<span class="scenario-info-popover" id="' + tooltipId + '" role="tooltip" hidden>',
        "<strong>" + escapeHtml(info.label) + "</strong>",
        escapeHtml(info.description),
        "</span>",
    ].join("");
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
    const stateDefault = getModelReliabilitySummary("state", getDefaultModelIdForGeo("state"));
    const msaDefault = getModelReliabilitySummary("msa", getDefaultModelIdForGeo("msa"));
    const parts = [];
    if (stateDefault) {
        parts.push(
            "State backtests use train years "
            + (Array.isArray(stateDefault.train_years) && stateDefault.train_years.length ? stateDefault.train_years.join(", ") : "not reported")
            + ", validation years "
            + (Array.isArray(stateDefault.validation_years) && stateDefault.validation_years.length ? stateDefault.validation_years.join(", ") : "not reported")
            + ", and test years "
            + (Array.isArray(stateDefault.test_years) && stateDefault.test_years.length ? stateDefault.test_years.join(", ") : "not reported")
            + "."
        );
    }
    if (msaDefault) {
        parts.push(
            "MSA backtests use train years "
            + (Array.isArray(msaDefault.train_years) && msaDefault.train_years.length ? msaDefault.train_years.join(", ") : "not reported")
            + ", validation years "
            + (Array.isArray(msaDefault.validation_years) && msaDefault.validation_years.length ? msaDefault.validation_years.join(", ") : "not reported")
            + ", and test years "
            + (Array.isArray(msaDefault.test_years) && msaDefault.test_years.length ? msaDefault.test_years.join(", ") : "not reported")
            + "."
        );
    }
    return parts.join(" ");
}

function getModelDisplayLabel(model, geoType) {
    const label = model && model.label ? model.label : "Model";
    return label;
}

function metricCell(row, key, isPercent) {
    if (!row || !Number.isFinite(Number(row[key]))) {
        return "n/a";
    }
    return isPercent ? formatPercent(Number(row[key])) : formatNumber(Number(row[key]), 2);
}

function extractErrorMessage(error) {
    if (!error) {
        return "";
    }
    if (typeof error === "string") {
        return error;
    }
    if (typeof error.message === "string" && error.message) {
        return error.message;
    }
    try {
        return JSON.stringify(error);
    } catch (serializationError) {
        return String(error);
    }
}

function plotChart(containerId, traces, layout, onReady) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    delete container.dataset.plotError;
    setPlotContainerCompactState(containerId, false);
    window.Plotly.react(container, traces, layout, {
        displayModeBar: false,
        responsive: true,
        topojsonURL: "assets/vendor/plotly-topojson/",
    }).then(function () {
        delete container.dataset.plotError;
        setPlotContainerCompactState(containerId, false);
        if (typeof onReady === "function") {
            onReady(container);
        }
    }).catch(function (error) {
        const detail = extractErrorMessage(error);
        if (detail) {
            container.dataset.plotError = detail;
        }
        console.error("Plotly render failed", {
            containerId: containerId,
            error: error,
            traceTypes: traces.map(function (trace) { return trace.type || "unknown"; }),
        });
        renderPlotFallback(
            containerId,
            "This chart could not be rendered for the selected view.",
            shouldLogMsaDiagnostics() && detail ? detail : ""
        );
    });
}

function clearPlotContainer(containerId) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    delete container.dataset.plotError;
    if (window.Plotly && typeof window.Plotly.purge === "function") {
        try {
            window.Plotly.purge(container);
        } catch (error) {
            console.warn("Plotly purge failed", {
                containerId: containerId,
                error: error,
            });
        }
    }
    container.innerHTML = "";
}

function renderPlotFallback(containerId, message, detail) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    setPlotContainerCompactState(containerId, true);
    if (detail) {
        container.dataset.plotError = detail;
    } else {
        delete container.dataset.plotError;
    }
    container.innerHTML = '<div class="scenario-fallback">'
        + message
        + (detail ? '<br><small>' + escapeHtml(detail) + "</small>" : "")
        + "</div>";
}

function setPlotContainerCompactState(containerId, isCompact) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    container.classList.toggle("is-plot-compact", Boolean(isCompact));
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
    const geographyType = record.geography_type === "msa" ? "msa" : "state";
    const geographyId = String(record.geography_id || record.state_id || record.state_fips || record.cbsa_code || "");
    const entity = getExportEntity(geographyType, geographyId);
    const selectedOutcome = getSelectedOutcome();
    const scenarioDefinition = lookup.scenarioById.get(record.scenario || "") || null;
    const modelDefinition = lookup.modelById.get(record.model || "") || null;
    const selectedPlace = getPrimarySummaryGeography();
    const stateFips = geographyType === "msa"
        ? (record.state_fips || (entity && entity.state_fips) || "")
        : String(record.state_fips || geographyId || "").padStart(2, "0");
    const stateAbbr = record.state_abbr || (entity && entity.state_abbr) || (stateFips ? getStateAbbreviation(stateFips) : "");
    const stateName = record.state_name || (entity && entity.state_name) || (geographyType === "state" ? (record.geography_name || (entity && entity.state_name) || "") : "");
    const geographyName = (geographyType === "msa" && entity && entity.geography_name)
        || record.geography_name
        || (entity && entity.geography_name)
        || record.msa_name
        || record.state_name
        || geographyId;
    const observedValue = getObservedValueForYear(geographyType, geographyId, Number(record.year));
    const cbsaCode = geographyType === "msa"
        ? (record.cbsa_code || (entity && entity.cbsa_code) || geographyId)
        : "";
    const msaName = geographyType === "msa"
        ? ((entity && entity.msa_name) || record.msa_name || geographyName)
        : "";
    const cbsaType = geographyType === "msa"
        ? ((entity && entity.cbsa_type) || record.cbsa_type || "unknown")
        : "";
    const scenarioDifference = valueOrBlank(record.scenario_difference);
    return {
        rank: valueOrBlank(extra.rank),
        ranking_group: valueOrBlank(extra.ranking_group),
        download_scope: valueOrBlank(extra.download_scope || ""),
        view_segment: valueOrBlank(extra.view_segment || ""),
        selected_geo_type: valueOrBlank(dashboardState.selectedGeoType),
        geo_type: valueOrBlank(geographyType),
        geography_type: valueOrBlank(geographyType),
        geography_id: valueOrBlank(geographyId),
        geography_name: valueOrBlank(geographyName),
        state_fips: valueOrBlank(stateFips),
        state_abbr: valueOrBlank(stateAbbr),
        state_name: valueOrBlank(stateName),
        cbsa_code: valueOrBlank(cbsaCode),
        cbsa_type: valueOrBlank(cbsaType),
        msa_id: valueOrBlank(cbsaCode),
        msa_name: valueOrBlank(msaName),
        estimate_status: valueOrBlank(geographyType === "msa" ? "analytical_msa_sample" : "analytical_state_sample"),
        availability_flag: valueOrBlank(record.availability_flag || ""),
        low_sample_flag: valueOrBlank(record.low_sample_flag),
        caveat_flag: valueOrBlank(record.caveat_flag),
        selected_horizon_year: valueOrBlank(dashboardState.selectedHorizon),
        year: valueOrBlank(record.year),
        model: valueOrBlank(record.model),
        model_label: valueOrBlank(modelDefinition ? getModelDisplayLabel(modelDefinition) : ""),
        scenario: valueOrBlank(record.scenario),
        scenario_label: valueOrBlank(scenarioDefinition ? scenarioDefinition.label : ""),
        outcome: valueOrBlank(dashboardState.selectedOutcome),
        outcome_label: valueOrBlank(selectedOutcome ? selectedOutcome.label : ""),
        reference_path: valueOrBlank(record.reference_path),
        scenario_path: valueOrBlank(record.scenario_path),
        scenario_difference: scenarioDifference,
        change_relative_to_reference: scenarioDifference,
        observed_value: valueOrBlank(observedValue),
        unit_label: getDashboardUnitLabel(),
        scenario_shift_component: valueOrBlank(record.scenario_shift_component),
        manual_adjustment_component: valueOrBlank(record.manual_adjustment_component),
        main_driver: valueOrBlank(record.main_driver || ""),
        data_source_note: valueOrBlank(getDataSourceNoteForExport(geographyType, record.scenario || "")),
        selected_state_filter: valueOrBlank(geographyType === "msa" ? dashboardState.selectedMsaStateFilter : ""),
        selected_state_filter_label: valueOrBlank(geographyType === "msa" ? getMsaStateFilterLabel() : ""),
        selected_place_id: valueOrBlank(selectedPlace.geography_id),
        selected_place_name: valueOrBlank(selectedPlace.geography_name),
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

function getExportEntity(geoType, geographyId) {
    if (!geographyId) {
        return null;
    }
    if (geoType === "msa") {
        return lookup.msaById.get(String(geographyId)) || null;
    }
    return lookup.stateByFips.get(String(geographyId).padStart(2, "0")) || null;
}

function getObservedValueForYear(geoType, geographyId, year) {
    if (!Number.isFinite(year)) {
        return "";
    }
    const observed = getObservedSeries(geoType, geographyId).find(function (row) {
        return Number(row.year) === Number(year);
    });
    return observed && Number.isFinite(observed.value) ? observed.value : "";
}

function getDashboardUnitLabel() {
    return "births per 1,000 women aged " + WOMEN_AGE_LABEL;
}

function getMsaScenarioAvailabilityRecord(scenarioId) {
    const availabilityRows = Array.isArray(dashboardData.msa_scenario_availability)
        ? dashboardData.msa_scenario_availability
        : [];
    return availabilityRows.find(function (row) {
        return row && row.scenario === scenarioId;
    }) || null;
}

function getMsaOnlineMatchingOverlayNote() {
    return String(
        dashboardData
        && dashboardData.metadata
        && dashboardData.metadata.msa_online_matching_common_overlay_note
        || ""
    ).trim();
}

function getStateModelRecommendationNote() {
    return String(
        dashboardData
        && dashboardData.metadata
        && dashboardData.metadata.state_model_recommendation_note
        || ""
    ).trim();
}

function getMsaModelRecommendationNote() {
    return String(
        dashboardData
        && dashboardData.metadata
        && dashboardData.metadata.msa_model_recommendation_note
        || ""
    ).trim();
}

function getMsaModelSummaryDiagnostic(modelId) {
    return getModelReliabilitySummary("msa", modelId);
}

function getMsaModelYearDiagnostic(modelId, year) {
    const rows = Array.isArray(dashboardData.msa_model_diagnostics_by_year)
        ? dashboardData.msa_model_diagnostics_by_year
        : [];
    return rows.find(function (row) {
        return row
            && row.model === modelId
            && Number(row.year) === Number(year);
    }) || null;
}

function getMsaProxyScenarioNote(scenarioId) {
    if (scenarioId === "online_life_helps_matching") {
        return getMsaOnlineMatchingOverlayNote()
            || "For MSA views, the online-matching scenario currently applies a common proxy shock across MSAs at each horizon. It should be interpreted as a national scenario overlay, not as MSA-specific online-matching exposure.";
    }
    const availabilityRecord = getMsaScenarioAvailabilityRecord(scenarioId);
    const reason = availabilityRecord && availabilityRecord.reason
        ? String(availabilityRecord.reason)
        : "";
    if (reason.toLowerCase().indexOf("parent-state") === -1) {
        return "";
    }
    return "This scenario currently uses parent-state proxy inputs merged onto each MSA because fully MSA-native inputs are not yet available. MSA-specific reference paths are retained, but the scenario shock itself is proxy-based.";
}

function getDataSourceNoteForExport(geoType, scenarioId) {
    if (geoType === "msa") {
        if (scenarioId === "reference_path") {
            return "Observed MSA fertility history and model-based reference path for the selected MSA.";
        }
        const availabilityRecord = getMsaScenarioAvailabilityRecord(scenarioId);
        if (availabilityRecord && availabilityRecord.reason && String(availabilityRecord.reason).toLowerCase().indexOf("parent-state") !== -1) {
            return getMsaProxyScenarioNote(scenarioId);
        }
        if (availabilityRecord && availabilityRecord.reason) {
            return availabilityRecord.reason;
        }
        if (scenarioId === "remote_work_saves_time" || scenarioId === "online_life_helps_matching") {
            return "Available for MSAs using parent-state scenario proxy inputs merged onto each MSA. MSA-specific reference paths are retained, but the scenario shock itself is proxy-based.";
        }
        return "Supported with ACS and ATUS MSA inputs.";
    }
    if (scenarioId === "reference_path") {
        return "Observed state fertility history and model-based reference path for the selected state.";
    }
    return "State-year scenario results from the dashboard bundle.";
}

function sanitizeFilenamePart(value) {
    const text = String(value || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");
    return text || "na";
}

function buildCurrentViewDownloadFilename() {
    if (dashboardState.selectedGeoType !== "msa") {
        return "digital-life-fertility-state-current-view.csv";
    }
    const scope = dashboardState.selectedMsaStateFilter === "all"
        ? "all_states"
        : sanitizeFilenamePart(dashboardState.selectedMsaStateFilter);
    return [
        "msa",
        "scenario",
        "results",
        scope,
        sanitizeFilenamePart(dashboardState.selectedModel),
        sanitizeFilenamePart(dashboardState.selectedScenario),
        sanitizeFilenamePart(dashboardState.selectedOutcome),
        String(dashboardState.selectedHorizon),
    ].join("_") + ".csv";
}

function buildAllScenarioDataDownloadFilename() {
    return dashboardState.selectedGeoType === "msa"
        ? "msa_all_loaded_scenario_results.csv"
        : "digital-life-fertility-state-all-scenarios.csv";
}

function buildRankingsDownloadFilename() {
    return dashboardState.selectedGeoType === "msa"
        ? [
            "msa",
            "rankings",
            sanitizeFilenamePart(dashboardState.selectedModel),
            sanitizeFilenamePart(dashboardState.selectedScenario),
            String(dashboardState.selectedHorizon),
        ].join("_") + ".csv"
        : "digital-life-fertility-state-rankings.csv";
}

function updateUtilityActionLabels() {
    const allDataButton = document.getElementById("download-all-data-button");
    if (allDataButton) {
        allDataButton.textContent = dashboardState.selectedGeoType === "msa"
            ? "Download all MSA-year scenario data"
            : "Download all state-year scenario data";
    }
}

function downloadCsv(rows, filename) {
    const headers = [
        "rank",
        "ranking_group",
        "download_scope",
        "view_segment",
        "selected_geo_type",
        "geo_type",
        "geography_type",
        "geography_id",
        "geography_name",
        "state_fips",
        "state_abbr",
        "state_name",
        "cbsa_code",
        "cbsa_type",
        "msa_id",
        "msa_name",
        "estimate_status",
        "availability_flag",
        "low_sample_flag",
        "caveat_flag",
        "selected_horizon_year",
        "year",
        "model",
        "model_label",
        "scenario",
        "scenario_label",
        "outcome",
        "outcome_label",
        "reference_path",
        "scenario_path",
        "scenario_difference",
        "change_relative_to_reference",
        "observed_value",
        "unit_label",
        "scenario_shift_component",
        "manual_adjustment_component",
        "main_driver",
        "data_source_note",
        "selected_state_filter",
        "selected_state_filter_label",
        "selected_place_id",
        "selected_place_name",
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

function downloadBenchmarkCsv(rows, filename) {
    const headers = ["geography_type", "geography_id", "geography_name", "model", "split", "rmse", "mae", "mape", "r_squared", "n_obs"];
    const lines = [headers.join(",")].concat(rows.map(function (row) {
        return headers.map(function (header) {
            return escapeCsvValue(row[header]);
        }).join(",");
    }));
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function downloadCountyDisplayLayerCsv(rows, filename) {
    const headers = [
        "county_fips",
        "county_name",
        "state_fips",
        "state_abbr",
        "state_name",
        "cbsa_code",
        "cbsa_name",
        "cbsa_type",
        "estimate_status",
        "estimated_geography_id",
        "estimated_geography_name",
        "selected_horizon_year",
        "scenario",
        "scenario_label",
        "outcome",
        "outcome_label",
        "scenario_effect",
        "selected_outcome_value",
        "unit_label",
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
    link.setAttribute("download", filename);
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
    updateUtilityActionLabels();
    setButtonDisabled("download-current-view-button", getCurrentViewExportRows().length === 0);
    setButtonDisabled("download-all-data-button", !lookup.allForecastRecords.some(function (record) {
        return record.geography_type === dashboardState.selectedGeoType;
    }));
    setButtonDisabled("download-rankings-button", getRankingsExportRows().length === 0);
    setButtonDisabled("download-benchmarks-button", (
        dashboardState.selectedGeoType === "msa"
            ? !(Array.isArray(dashboardData.msa_model_metrics) && dashboardData.msa_model_metrics.length)
            : !(Array.isArray(dashboardData.model_metrics) && dashboardData.model_metrics.length)
    ));
    setButtonDisabled("download-county-display-layer-button", lookup.countyDisplayRows.length === 0);
    setButtonDisabled("copy-summary-button", getCurrentSummaryText() === "Summary unavailable for the current selection.");
    setButtonDisabled("copy-link-button", dashboardState.selectedGeoType === "msa"
        ? !lookup.msaById.has(dashboardState.selectedMsaId)
        : !lookup.stateByFips.has(dashboardState.selectedStateFips));
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
            row.geography_id || "",
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

function finiteArrayMin(values) {
    let minimum = Infinity;
    values.forEach(function (value) {
        const number = Number(value);
        if (Number.isFinite(number) && number < minimum) {
            minimum = number;
        }
    });
    return minimum === Infinity ? NaN : minimum;
}

function finiteArrayMax(values) {
    let maximum = -Infinity;
    values.forEach(function (value) {
        const number = Number(value);
        if (Number.isFinite(number) && number > maximum) {
            maximum = number;
        }
    });
    return maximum === -Infinity ? NaN : maximum;
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

function normalizeDifferenceForMeaning(value, geoType) {
    if (!Number.isFinite(value)) {
        return value;
    }
    return Math.abs(value) < getScenarioDifferenceToleranceForGeo(geoType) ? 0 : value;
}

function describeRankingDifference(value, geoType) {
    const cleanValue = normalizeDifferenceForMeaning(value, geoType || dashboardState.selectedGeoType);
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

function isApproximatelyEqualDifference(value, geoType) {
    return Number.isFinite(value) && Math.abs(value) < getScenarioDifferenceToleranceForGeo(geoType || dashboardState.selectedGeoType);
}

function getScenarioDirectionNote(scenarioDiffs) {
    if (dashboardState.selectedScenario !== "remote_work_saves_time" || !scenarioDiffs.length) {
        return "";
    }
    const tolerance = getScenarioDifferenceToleranceForGeo(dashboardState.selectedGeoType);
    const anyAbove = scenarioDiffs.some(function (value) {
        return Number(value) > tolerance;
    });
    const anyBelow = scenarioDiffs.some(function (value) {
        return Number(value) < -tolerance;
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

function shouldLogMsaDiagnostics() {
    return shouldLogDashboardDiagnostics();
}

function shouldLogDashboardDiagnostics() {
    const params = new URLSearchParams(window.location.search);
    const debugFlag = String(
        params.get("debug")
        || params.get("debugDashboard")
        || params.get("debugMsa")
        || ""
    ).toLowerCase();
    return debugFlag === "1"
        || debugFlag === "true"
        || debugFlag === "msa"
        || debugFlag === "dashboard";
}

function buildMapRenderDebugDetails(mapBranch, mapRecordCount, extraDetails) {
    return Object.assign({
        geo: dashboardState.selectedGeoType,
        model: dashboardState.selectedModel,
        scenario: dashboardState.selectedScenario,
        year: dashboardState.selectedHorizon,
        outcome: dashboardState.selectedOutcome,
        mapBranch: String(mapBranch || "").toLowerCase() === "msa" ? "MSA" : "State",
        mapRecordCount: Number(mapRecordCount) || 0,
        neutralReferenceMode: isReferenceScenarioNeutralDifferenceSelection(),
    }, extraDetails || {});
}

function doesContainerHaveSvg(container) {
    return Boolean(container && typeof container.querySelector === "function" && container.querySelector("svg"));
}

function buildMsaGeometrySuccessDebugDetails(geometry, estimatedCountyCount, countyRowCount) {
    const msaGeometry = getMsaGeometrySource();
    const countyFeatureCount = geometry && Array.isArray(geometry.features)
        ? geometry.features.length
        : 0;
    const msaFeatureCount = msaGeometry && Array.isArray(msaGeometry.features)
        ? msaGeometry.features.length
        : 0;
    return buildMapRenderDebugDetails("msa", estimatedCountyCount, {
        countyFeatureCount: countyFeatureCount,
        msaFeatureCount: msaFeatureCount,
        hasEstimatedMsaCounties: estimatedCountyCount > 0,
        estimatedCountyCount: estimatedCountyCount,
        countyRowCount: countyRowCount,
    });
}

function logDashboardDebug(message, details) {
    if (!shouldLogDashboardDiagnostics()) {
        return;
    }
    if (typeof details === "undefined") {
        console.log(message);
        return;
    }
    console.log(message, details);
}

function buildMsaDiagnosticsReport() {
    const msaRecords = lookup.recordsByGeoType.get("msa") || [];
    const modelRows = msaRecords.filter(function (record) {
        return record.model === dashboardState.selectedModel;
    });
    const scenarioRows = modelRows.filter(function (record) {
        return record.scenario === dashboardState.selectedScenario;
    });
    const yearRows = scenarioRows.filter(function (record) {
        return Number(record.year) === Number(dashboardState.selectedHorizon);
    });
    const outcomeRows = yearRows.filter(function (record) {
        return Number.isFinite(Number(record[dashboardState.selectedOutcome]));
    });
    const filteredMsas = getFilteredMsas();
    const currentViewRows = getMsaRowsForCurrentView();
    const cbsaTypeCounts = filteredMsas.reduce(function (counts, msa) {
        const key = msa && msa.cbsa_type ? msa.cbsa_type : "unknown";
        counts[key] = (counts[key] || 0) + 1;
        return counts;
    }, {});
    const effectValues = currentViewRows
        .map(function (row) { return Number(row.scenario_difference); })
        .filter(Number.isFinite);
    const rankingPreview = currentViewRows
        .filter(function (row) { return Number.isFinite(Number(row.scenario_difference)); })
        .slice()
        .sort(function (a, b) {
            return b.scenario_difference - a.scenario_difference || a.geography_name.localeCompare(b.geography_name);
        })
        .slice(0, 5)
        .map(function (row) {
            return {
                geography_id: row.geography_id,
                geography_name: row.geography_name,
                state_name: row.state_name || "",
                scenario_difference: row.scenario_difference,
                reference_path: row.reference_path,
                scenario_path: row.scenario_path,
                main_driver: row.main_driver || "",
            };
        });
    const selectedMsa = getSelectedMsa();
    const selectedMsaContext = selectedMsa
        ? getScenarioContext("msa", selectedMsa.geography_id, dashboardState.selectedModel, dashboardState.selectedScenario, dashboardState.selectedHorizon)
        : null;

    return {
        selected_model: dashboardState.selectedModel,
        selected_scenario: dashboardState.selectedScenario,
        selected_year: dashboardState.selectedHorizon,
        selected_outcome: dashboardState.selectedOutcome,
        selected_state_filter: dashboardState.selectedMsaStateFilter,
        selected_state_filter_label: getMsaStateFilterLabel(),
        selected_msa_id: selectedMsa ? selectedMsa.geography_id : "",
        selected_msa_name: selectedMsa ? selectedMsa.geography_name : "",
        msa_scenario_rows_loaded: msaRecords.length,
        rows_after_filtering_by_model: modelRows.length,
        rows_after_filtering_by_scenario: scenarioRows.length,
        rows_after_filtering_by_year: yearRows.length,
        rows_after_filtering_by_outcome: outcomeRows.length,
        rows_after_applying_state_filter: currentViewRows.length,
        filtered_msa_count: filteredMsas.length,
        filtered_cbsa_type_counts: cbsaTypeCounts,
        nonmissing_scenario_effect_values: effectValues.length,
        scenario_effect_min: effectValues.length ? finiteArrayMin(effectValues) : NaN,
        scenario_effect_max: effectValues.length ? finiteArrayMax(effectValues) : NaN,
        scenario_effect_mean: effectValues.length
            ? effectValues.reduce(function (sum, value) { return sum + value; }, 0) / effectValues.length
            : NaN,
        ranking_preview_rows: rankingPreview,
        selected_msa_reference_path: selectedMsaContext ? selectedMsaContext.referenceFinal : NaN,
        selected_msa_scenario_path: selectedMsaContext ? selectedMsaContext.scenarioFinal : NaN,
        selected_msa_scenario_difference: selectedMsaContext ? selectedMsaContext.scenarioDifference : NaN,
    };
}

function emitMsaDiagnostics() {
    const report = buildMsaDiagnosticsReport();
    window.latestMsaDashboardDiagnostics = report;
    if (!shouldLogMsaDiagnostics()) {
        return;
    }
    console.groupCollapsed("MSA dashboard diagnostics");
    console.log("MSA dashboard diagnostics", {
        selected_model: report.selected_model,
        selected_scenario: report.selected_scenario,
        selected_year: report.selected_year,
        selected_outcome: report.selected_outcome,
        selected_state_filter: report.selected_state_filter,
        selected_state_filter_label: report.selected_state_filter_label,
        selected_msa_id: report.selected_msa_id,
        selected_msa_name: report.selected_msa_name,
        msa_scenario_rows_loaded: report.msa_scenario_rows_loaded,
        rows_after_filtering_by_model: report.rows_after_filtering_by_model,
        rows_after_filtering_by_scenario: report.rows_after_filtering_by_scenario,
        rows_after_filtering_by_year: report.rows_after_filtering_by_year,
        rows_after_filtering_by_outcome: report.rows_after_filtering_by_outcome,
        rows_after_applying_state_filter: report.rows_after_applying_state_filter,
        filtered_msa_count: report.filtered_msa_count,
        filtered_cbsa_type_counts: report.filtered_cbsa_type_counts,
        nonmissing_scenario_effect_values: report.nonmissing_scenario_effect_values,
        scenario_effect_min: report.scenario_effect_min,
        scenario_effect_max: report.scenario_effect_max,
        scenario_effect_mean: report.scenario_effect_mean,
        selected_msa_reference_path: report.selected_msa_reference_path,
        selected_msa_scenario_path: report.selected_msa_scenario_path,
        selected_msa_scenario_difference: report.selected_msa_scenario_difference,
    });
    if (report.ranking_preview_rows.length && typeof console.table === "function") {
        console.table(report.ranking_preview_rows);
    } else {
        console.log("ranking_preview_rows", report.ranking_preview_rows);
    }
    console.groupEnd();
}

function exposeDashboardValidation() {
    window.runFertilityDashboardValidation = runDashboardValidation;
    window.getMsaDashboardDiagnostics = buildMsaDiagnosticsReport;
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
        return row.geography_id === selectedState.state_fips && Number(row.year) === Number(dashboardState.selectedHorizon);
    });
    const rankingsRows = getRankingsExportRows().filter(function (row) {
        return row.geography_id === selectedState.state_fips && Number(row.year) === Number(dashboardState.selectedHorizon);
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

    console.groupCollapsed("Digital Life and Fertility Future dashboard validation");
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
