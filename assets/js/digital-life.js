(function () {
    "use strict";

    const DATA_URL = "assets/data/digital_life_state_year.csv";
    const METRICS = {
        digital_life_index: {
            label: "Digital Life Index",
            field: "digital_life_index",
            color: "#174b73",
            source: "ACS and ATUS"
        },
        digital_work: {
            label: "Digital Work Score",
            field: "digital_work_score_01",
            color: "#bf7138",
            source: "ACS"
        },
        digital_leisure: {
            label: "Digital Leisure Score",
            field: "digital_leisure_score_01",
            color: "#42735d",
            source: "ATUS"
        },
        digital_accessibility: {
            label: "Digital Accessibility Score",
            field: "digital_accessibility_score_01",
            color: "#78669b",
            source: "ACS"
        }
    };
    const TREND_METRIC_ORDER = [
        "digital_life_index",
        "digital_work",
        "digital_leisure",
        "digital_accessibility"
    ];
    const NUMBER_FIELDS = new Set([
        "statefip",
        "year",
        "remote_share",
        "digital_leisure_minutes_mean",
        "share_internet",
        "share_highspeed",
        "share_cellular_data_plan",
        "z_remote",
        "z_leisure",
        "z_leisure_share",
        "z_internet",
        "z_highspeed",
        "z_cellular",
        "digital_access",
        "pc1",
        "digital_life_index",
        "digital_work_score_01",
        "digital_leisure_score_01",
        "digital_accessibility_score_01"
    ]);
    const STATISTIC_MEASURES = [
        { field: "remote_share", label: "Remote work share", unit: "percent", color: "#bf7138" },
        { field: "digital_leisure_minutes_mean", label: "Digital leisure time", unit: "minutes", color: "#42735d" },
        { field: "share_internet", label: "Internet access", unit: "percent", color: "#286c86" },
        { field: "share_highspeed", label: "High-speed internet", unit: "percent", color: "#687f48" },
        { field: "share_cellular_data_plan", label: "Cellular data plan", unit: "percent", color: "#9a6887" }
    ];
    const MAP_COLORS = [
        [0, "#edf1f1"],
        [0.2, "#c8d7dc"],
        [0.45, "#91b0bd"],
        [0.72, "#527f94"],
        [1, "#17465f"]
    ];

    let rows = [];
    let years = [];
    let fixedDomains = {};
    let availableStatisticMeasures = [];

    function parseCSVRow(line) {
        const fields = [];
        let field = "";
        let quoted = false;
        for (let i = 0; i < line.length; i += 1) {
            const character = line[i];
            if (character === '"') {
                if (quoted && line[i + 1] === '"') {
                    field += '"';
                    i += 1;
                } else {
                    quoted = !quoted;
                }
            } else if (character === "," && !quoted) {
                fields.push(field);
                field = "";
            } else {
                field += character;
            }
        }
        fields.push(field);
        return fields;
    }

    function parseCSV(text) {
        const lines = text.replace(/^\uFEFF/, "").trim().split(/\r?\n/);
        if (lines.length < 2) {
            throw new Error("The state-year CSV has no data rows.");
        }
        const headers = parseCSVRow(lines[0]);
        return lines.slice(1).filter(Boolean).map(function (line) {
            const values = parseCSVRow(line);
            const row = {};
            headers.forEach(function (header, index) {
                const value = values[index] === undefined ? "" : values[index];
                row[header] = NUMBER_FIELDS.has(header) && value !== "" ? Number(value) : value;
            });
            return row;
        });
    }

    function metricValue(row, metricKey) {
        return Number(row[METRICS[metricKey].field]);
    }

    function formatValue(value) {
        return Number(value).toLocaleString("en-US", {
            minimumFractionDigits: 3,
            maximumFractionDigits: 3
        });
    }

    function setPlotError(elementId, message) {
        const element = document.getElementById(elementId);
        if (!element) {
            return;
        }
        element.classList.add("plot-error");
        element.textContent = message;
    }

    function averageForYear(year, metricKey) {
        const yearRows = rows.filter(function (row) {
            return row.year === year;
        });
        const total = yearRows.reduce(function (sum, row) {
            return sum + metricValue(row, metricKey);
        }, 0);
        return yearRows.length ? total / yearRows.length : null;
    }

    function renderTrendChart() {
        const chart = document.getElementById("trend-chart");
        const showDirectLabels = window.innerWidth > 760;
        const indices = years.map(function (_year, index) {
            return index;
        });
        const traces = TREND_METRIC_ORDER.map(function (metricKey) {
            const metric = METRICS[metricKey];
            return {
                type: "scatter",
                mode: "lines",
                name: metric.label,
                x: indices,
                y: years.map(function (year) {
                    return averageForYear(year, metricKey);
                }),
                line: {
                    color: metric.color,
                    width: 3
                },
                hovertemplate: "<b>" + metric.label + "</b><br>%{customdata}: %{y:.3f}<br>Normalized score; not a percentage.<extra></extra>",
                customdata: years.map(String),
                connectgaps: false
            };
        });
        const separatorIndex = years.indexOf(2019);
        const shapes = [];
        const annotations = [];
        if (showDirectLabels) {
            const endLabels = traces.map(function (trace) {
                return {
                    text: trace.name,
                    color: trace.line.color,
                    value: trace.y[trace.y.length - 1],
                    labelY: trace.y[trace.y.length - 1]
                };
            }).filter(function (label) {
                return Number.isFinite(label.value);
            }).sort(function (a, b) {
                return a.value - b.value;
            });
            const minLabelGap = 0.068;
            endLabels.forEach(function (label, index) {
                if (index > 0) {
                    label.labelY = Math.max(label.value, endLabels[index - 1].labelY + minLabelGap);
                }
            });
            if (endLabels.length) {
                const overflow = Math.max(0, endLabels[endLabels.length - 1].labelY - 0.96);
                const underflow = Math.max(0, 0.04 - (endLabels[0].labelY - overflow));
                endLabels.forEach(function (label) {
                    label.labelY -= overflow;
                    label.labelY += underflow;
                    annotations.push({
                        x: years.length - 1,
                        y: label.labelY,
                        xref: "x",
                        yref: "y",
                        xshift: 9,
                        text: label.text,
                        showarrow: false,
                        xanchor: "left",
                        yanchor: "middle",
                        align: "left",
                        font: {
                            family: "Inter, Arial, sans-serif",
                            size: window.innerWidth <= 900 ? 11 : 13,
                            color: label.color
                        }
                    });
                });
            }
        }
        if (separatorIndex >= 0 && years.indexOf(2021) === separatorIndex + 1) {
            shapes.push({
                type: "line",
                xref: "x",
                yref: "paper",
                x0: separatorIndex + 0.5,
                x1: separatorIndex + 0.5,
                y0: 0,
                y1: 1,
                line: {
                    color: "#a9aca7",
                    width: 1,
                    dash: "dash"
                }
            });
            annotations.push({
                x: separatorIndex + 0.5,
                y: 1.07,
                xref: "x",
                yref: "paper",
                text: "2020 omitted",
                showarrow: false,
                font: {
                    family: "Inter, Arial, sans-serif",
                    size: 14,
                    color: "#747a75"
                }
            });
        }
        const layout = {
            autosize: true,
            height: window.innerWidth <= 640 ? 385 : window.innerWidth <= 900 ? 440 : 472,
            margin: {
                l: window.innerWidth <= 760 ? 58 : 72,
                r: !showDirectLabels ? 20 : window.innerWidth <= 900 ? 188 : window.innerWidth <= 1100 ? 220 : 240,
                t: 43,
                b: 46
            },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: {
                family: "Inter, Arial, sans-serif",
                size: window.innerWidth <= 900 ? 14 : 15,
                color: "#4c534f"
            },
            xaxis: {
                range: showDirectLabels
                    ? [-0.12, window.innerWidth <= 900
                        ? years.length + 2.8
                        : window.innerWidth <= 1100 ? years.length + 1.5 : years.length + 1.0]
                    : [-0.12, years.length - 0.88],
                tickmode: "array",
                tickvals: indices,
                ticktext: years.map(String),
                showgrid: false,
                showline: true,
                linecolor: "#c9cbc5",
                tickfont: {
                    size: window.innerWidth <= 900 ? 14 : 15
                },
                fixedrange: true,
                zeroline: false
            },
            yaxis: {
                range: [0, 1],
                tickmode: "array",
                tickvals: [0, 0.25, 0.5, 0.75, 1],
                tickformat: ".2f",
                tickfont: { size: window.innerWidth <= 900 ? 14 : 15 },
                showgrid: true,
                gridcolor: "#e6e7e2",
                gridwidth: 1,
                zeroline: false,
                showline: false,
                fixedrange: true
            },
            shapes: shapes,
            annotations: annotations,
            hovermode: "x unified",
            showlegend: false
        };
        const plotPromise = Plotly.react(chart, traces, layout, {
            responsive: true,
            displayModeBar: false,
            scrollZoom: false
        });
        return plotPromise;
    }

    function getRowsForYear(year) {
        return rows.filter(function (row) {
            return row.year === year;
        });
    }

    function selectedMapMetric() {
        return document.getElementById("map-metric").value;
    }

    function selectedMapYear() {
        return Number(document.getElementById("map-year").value);
    }

    function mapPlotHeight() {
        return window.innerWidth <= 640 ? (window.innerWidth <= 380 ? 410 : 440) : window.innerWidth <= 900 ? 520 : 570;
    }

    function renderMap() {
        const chart = document.getElementById("state-map");
        const metricKey = selectedMapMetric();
        const year = selectedMapYear();
        const metric = METRICS[metricKey];
        const yearRows = getRowsForYear(year);
        const domain = fixedDomains[metricKey];
        const trace = {
            type: "choropleth",
            locationmode: "USA-states",
            locations: yearRows.map(function (row) {
                return row.state_abbr;
            }),
            z: yearRows.map(function (row) {
                return metricValue(row, metricKey);
            }),
            text: yearRows.map(function (row) {
                return row.state_name;
            }),
            customdata: yearRows.map(function (row) {
                return [row.state_abbr, year];
            }),
            zmin: domain[0],
            zmax: domain[1],
            colorscale: MAP_COLORS,
            autocolorscale: false,
            reversescale: false,
            marker: {
                line: {
                    color: "#fbfaf7",
                    width: 0.7
                }
            },
            showscale: false,
            hovertemplate: "<b>%{text}</b><br>" + metric.label + " · " + year + ": %{z:.3f}<br>Normalized score; not a percentage.<extra></extra>"
        };
        const layout = {
            autosize: true,
            height: mapPlotHeight(),
            margin: {
                l: 8,
                r: 8,
                t: 8,
                b: 8
            },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: {
                family: "Inter, Arial, sans-serif",
                color: "#4c534f"
            },
            geo: {
                scope: "usa",
                bgcolor: "rgba(0,0,0,0)",
                showframe: false,
                showcoastlines: false,
                showlakes: false,
                showcountries: false,
                projection: {
                    type: "albers usa"
                }
            },
            transition: {
                duration: 320,
                easing: "cubic-in-out"
            },
            showlegend: false
        };
        const plotPromise = Plotly.react(chart, [trace], layout, {
            responsive: true,
            displayModeBar: false,
            scrollZoom: false
        });
        document.getElementById("map-legend-title").textContent = metric.label;
        document.getElementById("map-legend-min").textContent = formatValue(domain[0]);
        document.getElementById("map-legend-mid").textContent = formatValue((domain[0] + domain[1]) / 2);
        document.getElementById("map-legend-max").textContent = formatValue(domain[1]);
        document.getElementById("map-note").textContent =
            metric.label + " · " + year +
            " · Source: " + metric.source +
            ". Darker shades indicate higher values; this measure's scale is fixed across all years. " +
            "2020 is omitted because ATUS did not produce a comparable full-year estimate.";
        return plotPromise;
    }

    function profilePlotHeight() {
        return window.innerWidth <= 640 ? 370 : 350;
    }

    function renderStateProfile() {
        const stateAbbr = document.getElementById("state-select").value;
        const year = selectedMapYear();
        const stateRow = rows.find(function (row) {
            return row.state_abbr === stateAbbr && row.year === year;
        });
        const title = document.getElementById("profile-state-year");
        const chart = document.getElementById("state-profile-chart");
        if (!stateRow) {
            title.textContent = "No observation available for the selected state and year.";
            chart.replaceChildren();
            return Promise.resolve();
        }
        title.textContent = stateRow.state_name + " \u00b7 " + year;
        const yearRows = getRowsForYear(year);
        const chartRows = TREND_METRIC_ORDER.map(function (metricKey) {
            const value = metricValue(stateRow, metricKey);
            return {
                label: METRICS[metricKey].label,
                color: METRICS[metricKey].color,
                value: value,
                rank: 1 + yearRows.filter(function (row) {
                    return metricValue(row, metricKey) > value;
                }).length
            };
        }).reverse();
        const trace = {
            type: "bar",
            orientation: "h",
            x: chartRows.map(function (row) { return row.value; }),
            y: chartRows.map(function (row) { return row.label; }),
            text: chartRows.map(function (row) { return formatValue(row.value); }),
            textposition: "outside",
            textfont: { family: "Inter, Arial, sans-serif", size: window.innerWidth <= 900 ? 14 : 15, color: "#454c48" },
            cliponaxis: false,
            marker: { color: chartRows.map(function (row) { return row.color; }), line: { width: 0 } },
            customdata: chartRows.map(function (row) { return row.rank; }),
            hovertemplate: "<b>%{y}</b><br>" + stateRow.state_name + " · " + year + ": %{x:.3f}<br>Rank: #%{customdata} of " + yearRows.length + "<br>Normalized score; not a percentage.<extra></extra>"
        };
        const layout = {
            autosize: true,
            height: profilePlotHeight(),
            margin: { l: window.innerWidth <= 640 ? 170 : 228, r: window.innerWidth <= 640 ? 50 : 58, t: 5, b: 72 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: "Inter, Arial, sans-serif", size: window.innerWidth <= 900 ? 14 : 15, color: "#4c534f" },
            xaxis: {
                range: [0, 1],
                title: { text: "Normalized score (0–1)", standoff: 10, font: { size: window.innerWidth <= 900 ? 15 : 16 } },
                tickmode: "array",
                tickvals: [0, 0.25, 0.5, 0.75, 1],
                tickformat: ".2f",
                tickfont: { size: window.innerWidth <= 900 ? 14 : 15 },
                showgrid: true,
                gridcolor: "#e7e8e3",
                zeroline: false,
                fixedrange: true
            },
            yaxis: {
                categoryorder: "array",
                categoryarray: chartRows.map(function (row) { return row.label; }),
                tickmode: "array",
                tickvals: chartRows.map(function (row) { return row.label; }),
                ticktext: chartRows.map(function (row) {
                    return window.innerWidth <= 640 ? row.label.replace(" Score", "<br>Score") : row.label;
                }),
                showgrid: false,
                tickfont: { size: window.innerWidth <= 900 ? 14 : 15, color: "#343a37" },
                fixedrange: true
            },
            bargap: 0.42,
            transition: { duration: 320, easing: "cubic-in-out" },
            showlegend: false
        };
        return Plotly.react(chart, [trace], layout, {
            responsive: true,
            displayModeBar: false,
            scrollZoom: false
        });
    }

    function statisticsPlotHeight() {
        const stateCount = getRowsForYear(Number(document.getElementById("stat-year").value)).length || 51;
        const rowHeight = window.innerWidth <= 640 ? 34 : 29;
        return stateCount * rowHeight + (window.innerWidth <= 640 ? 150 : 120);
    }

    function populateControls() {
        const latestYear = years[years.length - 1];
        ["map-year", "stat-year"].forEach(function (selectId) {
            const select = document.getElementById(selectId);
            select.replaceChildren();
            years.forEach(function (year) {
                const option = document.createElement("option");
                option.value = String(year);
                option.textContent = String(year);
                select.appendChild(option);
            });
            select.value = String(latestYear);
        });

        const measureSelect = document.getElementById("stat-measure");
        measureSelect.replaceChildren();
        availableStatisticMeasures = STATISTIC_MEASURES.filter(function (measure) {
            return Object.prototype.hasOwnProperty.call(rows[0] || {}, measure.field);
        });
        availableStatisticMeasures.forEach(function (measure) {
            const option = document.createElement("option");
            option.value = measure.field;
            option.textContent = measure.label;
            measureSelect.appendChild(option);
        });
        if (availableStatisticMeasures.length) {
            measureSelect.value = availableStatisticMeasures[0].field;
        }

        const stateSelect = document.getElementById("state-select");
        const states = rows.filter(function (row) {
            return row.year === latestYear;
        }).slice().sort(function (a, b) {
            return a.state_name.localeCompare(b.state_name);
        });
        states.forEach(function (row) {
            const option = document.createElement("option");
            option.value = row.state_abbr;
            option.textContent = row.state_name;
            stateSelect.appendChild(option);
        });
        if (states.length) {
            stateSelect.value = states[0].state_abbr;
        }
    }

    function computeFixedDomains() {
        TREND_METRIC_ORDER.forEach(function (metricKey) {
            const values = rows.map(function (row) {
                return metricValue(row, metricKey);
            });
            fixedDomains[metricKey] = [Math.min.apply(null, values), Math.max.apply(null, values)];
        });
    }

    function formatStatisticValue(value, unit) {
        if (unit === "percent") {
            return Number(value).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
        }
        return Number(value).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " minutes/day";
    }

    function renderStatisticsChart() {
        const chart = document.getElementById("statistics-chart");
        const measureField = document.getElementById("stat-measure").value;
        const year = Number(document.getElementById("stat-year").value);
        const measure = availableStatisticMeasures.find(function (item) {
            return item.field === measureField;
        });
        const ranked = getRowsForYear(year).filter(function (row) {
            return Number.isFinite(Number(row[measureField]));
        }).slice().sort(function (a, b) {
            return Number(b[measureField]) - Number(a[measureField]);
        });

        if (!measure || !ranked.length) {
            chart.replaceChildren();
            chart.textContent = "No source values are available for this measure and year.";
            return Promise.resolve();
        }

        const pooledRawValues = rows.map(function (row) { return Number(row[measure.field]); }).filter(Number.isFinite);
        const rawMin = Math.min.apply(null, pooledRawValues);
        const rawMax = Math.max.apply(null, pooledRawValues);
        const multiplier = measure.unit === "percent" && rawMin >= 0 && rawMax <= 1 ? 100 : 1;
        const displayValues = ranked.map(function (row) { return Number(row[measure.field]) * multiplier; });
        const displayMax = Math.max.apply(null, displayValues);
        const selectedState = document.getElementById("state-select").value;
        const unitSuffix = measure.unit === "percent" ? "%" : " minutes/day";
        const trace = {
            type: "bar",
            orientation: "h",
            x: displayValues,
            y: ranked.map(function (row) { return row.state_name; }),
            text: displayValues.map(function (value) { return formatStatisticValue(value, measure.unit); }),
            textposition: "outside",
            textfont: { family: "Inter, Arial, sans-serif", size: window.innerWidth <= 900 ? 14 : 15, color: "#454c48" },
            cliponaxis: false,
            marker: {
                color: measure.color,
                line: {
                    color: ranked.map(function (row) { return row.state_abbr === selectedState ? "#243c33" : "#fbfaf7"; }),
                    width: ranked.map(function (row) { return row.state_abbr === selectedState ? 2.4 : 0.5; })
                }
            },
            hovertemplate: "<b>%{y}</b><br>" + measure.label + ": %{x:.1f}" + unitSuffix + "<extra></extra>"
        };
        const axisMax = measure.unit === "percent" ? Math.max(100, displayMax * 1.08) : displayMax * 1.18;
        const layout = {
            autosize: true,
            height: statisticsPlotHeight(),
            margin: { l: window.innerWidth <= 640 ? 164 : 202, r: 76, t: 8, b: 68 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: "Inter, Arial, sans-serif", size: window.innerWidth <= 900 ? 14 : 15, color: "#4c534f" },
            xaxis: {
                range: [0, axisMax],
                title: { text: measure.unit === "percent" ? "Percent" : "Minutes per day", standoff: 10, font: { size: window.innerWidth <= 900 ? 15 : 16 } },
                tickmode: measure.unit === "percent" ? "array" : "auto",
                tickvals: measure.unit === "percent" ? [0, 20, 40, 60, 80, 100] : undefined,
                ticksuffix: measure.unit === "percent" ? "%" : "",
                tickformat: ".0f",
                tickfont: { size: window.innerWidth <= 900 ? 14 : 15 },
                showgrid: true,
                gridcolor: "#e7e8e3",
                gridwidth: 1,
                zeroline: false,
                fixedrange: true
            },
            yaxis: {
                categoryorder: "array",
                categoryarray: ranked.map(function (row) { return row.state_name; }),
                autorange: "reversed",
                showgrid: false,
                tickfont: { size: window.innerWidth <= 900 ? 14 : 15, color: "#343a37" },
                fixedrange: true
            },
            bargap: 0.24,
            transition: { duration: 320, easing: "cubic-in-out" },
            showlegend: false
        };
        return Plotly.react(chart, [trace], layout, {
            responsive: true,
            displayModeBar: false,
            scrollZoom: false
        });
    }

    function setUpSectionControls() {
        const sectionIds = [
            "intro",
            "trends",
            "map-section",
            "state-profile",
            "state-statistics",
            "measure-definitions",
            "method",
            "download"
        ];
        const sections = sectionIds.map(function (id) {
            return document.getElementById(id);
        }).filter(Boolean);
        const upButton = document.getElementById("section-up");
        const downButton = document.getElementById("section-down");
        let currentIndex = 0;
        let scheduled = false;

        function syncCurrentSection() {
            scheduled = false;
            let active = 0;
            sections.forEach(function (section, index) {
                if (section.getBoundingClientRect().top <= window.innerHeight * 0.42) {
                    active = index;
                }
            });
            if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 5) {
                active = sections.length - 1;
            }
            currentIndex = active;
            upButton.disabled = currentIndex <= 0;
            downButton.disabled = currentIndex >= sections.length - 1;
        }

        function scheduleSync() {
            if (!scheduled) {
                scheduled = true;
                window.requestAnimationFrame(syncCurrentSection);
            }
        }

        function scrollToIndex(index) {
            const target = sections[index];
            if (!target) {
                return;
            }
            target.scrollIntoView({
                behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
                block: "start"
            });
        }

        upButton.addEventListener("click", function () {
            syncCurrentSection();
            scrollToIndex(Math.max(0, currentIndex - 1));
        });
        downButton.addEventListener("click", function () {
            syncCurrentSection();
            scrollToIndex(Math.min(sections.length - 1, currentIndex + 1));
        });
        window.addEventListener("scroll", scheduleSync, { passive: true });
        window.addEventListener("resize", scheduleSync);
        syncCurrentSection();
    }

    function attachInteractions() {
        const mapYear = document.getElementById("map-year");
        const statYear = document.getElementById("stat-year");
        const stateSelect = document.getElementById("state-select");

        document.getElementById("map-metric").addEventListener("change", renderMap);
        document.getElementById("stat-measure").addEventListener("change", renderStatisticsChart);
        statYear.addEventListener("change", renderStatisticsChart);
        mapYear.addEventListener("change", function () {
            renderMap();
            renderStateProfile();
        });
        stateSelect.addEventListener("change", function () {
            renderStateProfile();
            renderStatisticsChart();
        });

        const mapElement = document.getElementById("state-map");
        mapElement.on("plotly_click", function (event) {
            const point = event && event.points && event.points[0];
            if (!point || !point.location) {
                return;
            }
            stateSelect.value = point.location;
            renderStateProfile();
            renderStatisticsChart();
        });

        let resizeTimer;
        window.addEventListener("resize", function () {
            window.clearTimeout(resizeTimer);
            resizeTimer = window.setTimeout(function () {
                Promise.all([
                    renderTrendChart(),
                    Plotly.relayout("state-map", { height: mapPlotHeight() }),
                    Plotly.relayout("state-profile-chart", { height: profilePlotHeight() }),
                    Plotly.relayout("statistics-chart", { height: statisticsPlotHeight() })
                ]);
            }, 180);
        });
        setUpSectionControls();
    }

    function validateSourceRows() {
        const keys = new Set();
        const stateYearDuplicates = [];
        rows.forEach(function (row) {
            const key = String(row.statefip) + "-" + String(row.year);
            if (keys.has(key)) {
                stateYearDuplicates.push(key);
            }
            keys.add(key);
        });
        const observedStates = new Set(rows.map(function (row) {
            return row.state_abbr;
        }));
        const expectedFields = TREND_METRIC_ORDER.every(function (metricKey) {
            return rows.every(function (row) {
                return Number.isFinite(metricValue(row, metricKey));
            });
        });
        const completeYearCoverage = years.every(function (year) {
            return getRowsForYear(year).length === 51;
        });
        if (stateYearDuplicates.length || observedStates.size !== 51 || !completeYearCoverage || !expectedFields) {
            throw new Error("The loaded file did not pass the state-year uniqueness and coverage checks.");
        }
    }

    function showLoadError(error) {
        ["trend-chart", "state-map", "state-profile-chart", "statistics-chart"].forEach(function (id) {
            setPlotError(id, "The Digital Life Index data could not be loaded. Check the CSV path and reload the page.");
        });
        const detail = document.getElementById("map-note");
        detail.textContent = error && error.message ? error.message : "The data could not be loaded.";
    }

    async function init() {
        if (!window.Plotly) {
            showLoadError(new Error("Plotly is not available."));
            return;
        }
        try {
            const response = await fetch(DATA_URL);
            if (!response.ok) {
                throw new Error("The CSV returned HTTP " + response.status + ".");
            }
            rows = parseCSV(await response.text());
            rows.sort(function (a, b) {
                return a.statefip - b.statefip || a.year - b.year;
            });
            years = Array.from(new Set(rows.map(function (row) {
                return row.year;
            }))).sort(function (a, b) {
                return a - b;
            });
            validateSourceRows();
            computeFixedDomains();
            populateControls();
            await Promise.all([
                renderTrendChart(),
                renderMap(),
                renderStateProfile(),
                renderStatisticsChart()
            ]);
            attachInteractions();
        } catch (error) {
            showLoadError(error);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    } else {
        init();
    }
}());
