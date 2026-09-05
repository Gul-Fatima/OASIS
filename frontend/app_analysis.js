/* ============================================================
   OASIS — Combined Analysis (Code Understanding + Energy)
============================================================ */

const API_BASE = "http://127.0.0.1:8000";


/* ============================================================
   HELPERS
============================================================ */

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value ?? "-";
}

function setHTML(id, value) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = value ?? "";
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
}

function show(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = "";
}


/* ============================================================
   UPDATE CODE UNDERSTANDING RESULTS
============================================================ */

function updateCodeUnderstanding(data) {

    /* SUMMARY METRICS */
    setText("functionCount", data.functions?.length ?? 0);
    setText("classCount", data.classes?.length ?? 0);
    setText("loopCount", data.loops?.length ?? 0);
    setText("conditionalCount", data.conditionals ?? 0);

    /* FUNCTION NAMES */
    const funcNames = (data.functions || [])
        .map(f => f.name)
        .join(", ");
    setText("functionNames", funcNames || "None");

    /* CLASS NAMES */
    const classNames = (data.classes || [])
        .map(c => c.name)
        .join(", ");
    setText("classNames", classNames || "None");

    /* LOOP DETAILS */
    const loopDetails = (data.loops || [])
        .map(l => `${l.kind} @ line ${l.line}`)
        .join(", ");
    setText("loopDetails", loopDetails || "None");

    /* FUNCTION LIST */
    const funcHTML = (data.functions || []).map(f => {
        const cx = f.complexity !== null
            ? ` <span class="cx-badge">cx: ${f.complexity}</span>`
            : "";
        const decos = (f.decorators || []).length > 0
            ? `<div class="detail-sub">@${f.decorators.join(", @")}</div>`
            : "";
        return `
            <div class="detail-row">
                <div>
                    <strong>${f.name}</strong>${cx}
                    <span class="detail-meta">
                        lines ${f.start_line}–${f.end_line} · ${f.arguments.length} args
                    </span>
                    ${decos}
                </div>
                <div class="detail-args">${f.arguments.join(", ") || "none"}</div>
            </div>`;
    }).join("");
    setHTML("functionList", funcHTML || '<div class="detail-empty">No functions found</div>');

    /* IO OPERATIONS */
    const ioHTML = (data.io_operations || []).map(io =>
        `<div class="detail-row"><span class="io-tag">I/O</span> ${io}</div>`
    ).join("");
    setHTML("ioList", ioHTML || '<div class="detail-empty">No I/O operations</div>');

    /* FUNCTION CALLS */
    const callHTML = (data.function_calls || []).map(c =>
        `<div class="detail-row">
            <strong>${c.name}()</strong>
            <span class="detail-meta">line ${c.line} · ${c.argument_count} args</span>
        </div>`
    ).join("");
    setHTML("callList", callHTML || '<div class="detail-empty">No function calls</div>');

    /* CLASS DETAILS */
    const clsHTML = (data.classes || []).map(cls => {
        const methods = (cls.methods || []).map(m => {
            const cx = m.complexity !== null
                ? ` <span class="cx-badge">cx: ${m.complexity}</span>`
                : "";
            return `
                <div class="detail-row">
                    <strong>${m.name}</strong>${cx}
                    <span class="detail-meta">
                        lines ${m.start_line}–${m.end_line} · ${m.arguments.join(", ")}
                    </span>
                </div>`;
        }).join("");
        return `
            <div class="class-block">
                <div class="class-header">
                    <strong>${cls.name}</strong>
                    <span class="detail-meta">
                        lines ${cls.start_line}–${cls.end_line} · ${cls.methods.length} methods
                    </span>
                </div>
                <div class="class-methods">${methods || '<div class="detail-empty">No methods</div>'}</div>
            </div>`;
    }).join("");
    setHTML("classList", clsHTML || '<div class="detail-empty">No classes found</div>');

    /* COMPLEXITY */
    const cx = data.complexity || {};
    if (cx.measured > 0) {
        setHTML("complexityInfo", `
            <div class="cx-item">
                <span>Measured Functions</span>
                <strong>${cx.measured}</strong>
            </div>
            <div class="cx-item">
                <span>Max Complexity</span>
                <strong>${cx.max}</strong>
            </div>
            <div class="cx-item">
                <span>Total Complexity</span>
                <strong>${cx.total}</strong>
            </div>
        `);
    } else {
        setHTML("complexityInfo", '<div class="detail-empty">Complexity not measured (install radon)</div>');
    }

    /* DEPENDENCIES */
    const deps = data.dependencies || [];
    if (deps.length > 0) {
        setHTML("depsList", deps.map(d =>
            `<div class="dep-tag">${d}</div>`
        ).join(""));
    } else {
        setHTML("depsList", '<div class="detail-empty">No external dependencies</div>');
    }

    /* SHOW SECTIONS */
    show("code-structure");
    show("code-details");
    if (data.classes?.length > 0) show("class-details");
    show("complexity-section");
    show("deps-section");
}


/* ============================================================
   UPDATE ENERGY RESULTS
============================================================ */

function updateEnergyResults(data) {

    const energy = Number(data.energy_consumed || 0);
    setText("energyValue", energy.toFixed(9));
    setText("energyWh", `${(energy * 1000).toFixed(6)} Wh`);

    const emissions = Number(data.emissions || 0);
    setText("emissionsValue", emissions.toExponential(2));
    setText("emissionsGrams", `${(emissions * 1000).toFixed(4)} g CO₂eq`);

    setText("durationValue", Number(data.duration || 0).toFixed(4));

    const totalPower = Number(data.cpu_power || 0) + Number(data.ram_power || 0) + Number(data.gpu_power || 0);
    setText("powerValue", totalPower.toFixed(2));

    /* CPU ENERGY */
    setText("cpuEnergy", `${Number(data.cpu_energy || 0).toFixed(9)} kWh`);
    const cpuPct = energy > 0 ? (Number(data.cpu_energy || 0) / energy) * 100 : 0;
    document.getElementById("cpuEnergyBar").style.width = `${cpuPct}%`;

    /* RAM ENERGY */
    setText("ramEnergy", `${Number(data.ram_energy || 0).toFixed(9)} kWh`);
    const ramPct = energy > 0 ? (Number(data.ram_energy || 0) / energy) * 100 : 0;
    document.getElementById("ramEnergyBar").style.width = `${ramPct}%`;

    /* GPU ENERGY */
    setText("gpuEnergy", `${Number(data.gpu_energy || 0).toFixed(9)} kWh`);
    const gpuPct = energy > 0 ? (Number(data.gpu_energy || 0) / energy) * 100 : 0;
    document.getElementById("gpuEnergyBar").style.width = `${gpuPct}%`;

    /* DONUT */
    setText("cpuPercentage", `${cpuPct.toFixed(1)}%`);
    const donut = document.getElementById("energyDonut");
    if (donut) {
        const gpuAngle = gpuPct * 3.6;
        const cpuAngle = cpuPct * 3.6;
        const ramAngle = ramPct * 3.6;
        donut.style.background = `conic-gradient(
            var(--green) 0deg ${cpuAngle}deg,
            var(--orange) ${cpuAngle}deg ${cpuAngle + ramAngle}deg,
            var(--blue) ${cpuAngle + ramAngle}deg 360deg
        )`;
    }

    /* RESOURCES */
    setText("cpuUtilization", `${Number(data.cpu_utilization_percent || 0).toFixed(2)}%`);
    document.getElementById("cpuUtilizationBar").style.width =
        `${Math.min(Number(data.cpu_utilization_percent || 0), 100)}%`;
    setText("cpuPower", `${Number(data.cpu_power || 0).toFixed(2)} W`);
    setText("cpuEnergyRes", `${Number(data.cpu_energy || 0).toFixed(9)} kWh`);
    setText("cpuModel", data.cpu_model || "-");
    setText("cpuCount", data.cpu_count || "-");

    setText("ramUtilization", `${Number(data.ram_utilization_percent || 0).toFixed(2)}%`);
    document.getElementById("ramUtilizationBar").style.width =
        `${Math.min(Number(data.ram_utilization_percent || 0), 100)}%`;
    setText("ramPower", `${Number(data.ram_power || 0).toFixed(2)} W`);
    setText("ramEnergyRes", `${Number(data.ram_energy || 0).toFixed(9)} kWh`);
    setText("ramUsed", `${Number(data.ram_used_gb || 0).toFixed(2)} GB`);

    setText("gpuUtilization", `${Number(data.gpu_utilization_percent || 0).toFixed(2)}%`);
    document.getElementById("gpuUtilizationBar").style.width =
        `${Math.min(Number(data.gpu_utilization_percent || 0), 100)}%`;
    setText("gpuPower", `${Number(data.gpu_power || 0).toFixed(2)} W`);
    setText("gpuEnergyRes", `${Number(data.gpu_energy || 0).toFixed(9)} kWh`);
    setText("gpuModel", data.gpu_model || "None");
    setText("gpuCount", data.gpu_count || 0);

    /* METADATA */
    setText("projectName", data.project_name);
    setText("runId", data.run_id);
    setText("timestamp", data.timestamp);
    setText("osInfo", data.os);
    setText("pythonVersion", data.python_version);
    setText("codecarbonVersion", data.codecarbon_version);

    /* SHOW SECTIONS */
    show("energy-overview");
    show("energy-breakdown");
    show("resources-section");
    show("metadata-section");
}


/* ============================================================
   RUN COMBINED ANALYSIS
============================================================ */

async function runCombinedAnalysis() {

    const filePath = document.getElementById("filePath").value.trim();
    const execCommand = document.getElementById("execCommand").value.trim();
    const timeout = Number(document.getElementById("timeout").value);

    if (!filePath) {
        alert("Please enter the file path.");
        return;
    }

    if (!execCommand) {
        alert("Please enter the execution command.");
        return;
    }

    const button = document.getElementById("runCombined");
    const status = document.getElementById("analysisStatus");

    button.disabled = true;
    button.innerHTML = "⏳ Analyzing...";
    status.textContent = "Step 1/2: Parsing code structure...";

    try {

        /* -------------------------------------------
         * STEP 1: CODE UNDERSTANDING
         * ------------------------------------------- */

        const parseResponse = await fetch(`${API_BASE}/api/code/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                file_path: filePath,
                language: "python"
            })
        });

        if (!parseResponse.ok) {
            const err = await parseResponse.json();
            throw new Error(err.detail || `Parse failed: ${parseResponse.status}`);
        }

        const parseResult = await parseResponse.json();
        updateCodeUnderstanding(parseResult);

        status.textContent = "Step 2/2: Measuring energy consumption...";

        /* -------------------------------------------
         * STEP 2: ENERGY ESTIMATION
         * ------------------------------------------- */

        const dirPath = filePath.replace(/[\\/][^\\/]+$/, "");

        const energyResponse = await fetch(`${API_BASE}/api/energy/estimate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                project_path: dirPath,
                command: execCommand,
                timeout: timeout
            })
        });

        if (!energyResponse.ok) {
            const err = await energyResponse.json();
            throw new Error(err.detail || `Energy failed: ${energyResponse.status}`);
        }

        const energyResult = await energyResponse.json();
        updateEnergyResults(energyResult);

        status.textContent = "Analysis completed successfully!";
        setText("sidebarStatus", "Completed");

    } catch (error) {
        console.error(error);
        status.textContent = "Analysis failed: " + error.message;
        alert("Error: " + error.message + "\n\nMake sure the OASIS backend is running.");
    } finally {
        button.disabled = false;
        button.innerHTML = "⚡ Run Combined Analysis";
    }
}


/* ============================================================
   EVENT LISTENER
============================================================ */

document
    .getElementById("runCombined")
    .addEventListener("click", runCombinedAnalysis);
