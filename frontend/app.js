const sampleData = {
    timestamp: "2026-09-02T15:59:26",

    project_name: "OASIS",

    run_id:
        "76191031-1f09-4c7a-a55b-6025d3adab4f",

    experiment_id:
        "5b0fa12a-3dd7-45bb-9766-cc326314d9f1",

    duration: 51.6586578,

    emissions: 9.11e-05,

    emissions_rate: 1.76e-06,

    cpu_power: 5.171820322,

    gpu_power: 0,

    ram_power: 10,

    cpu_energy: 7.49e-05,

    gpu_energy: 0,

    ram_energy: 0.000131852,

    energy_consumed: 0.000206706,

    water_consumed: 0,

    country_name: "Pakistan",

    country_iso_code: "PAK",

    region: "sindh",

    cloud_provider: "",

    cloud_region: "",

    os:
        "Windows-11-10.0.26200-SP0",

    python_version:
        "3.14.3",

    codecarbon_version:
        "3.3.0",

    cpu_count: 12,

    cpu_model:
        "AMD Ryzen 5 7430U with Radeon Graphics",

    gpu_count: 0,

    gpu_model: "",

    longitude: 66.9983,

    latitude: 24.8591,

    ram_total_size: 7.405101776,

    tracking_mode: "machine",

    cpu_utilization_percent: 6.382978723,

    gpu_utilization_percent: 0,

    ram_utilization_percent: 90.45744681,

    ram_used_gb: 6.698439172,

    on_cloud: "N",

    pue: 1,

    wue: 0
};


/* ============================================================
   HELPERS
============================================================ */

function formatNumber(value, digits = 6) {

    if (value === null || value === undefined) {
        return "-";
    }

    return Number(value).toFixed(digits);
}


function formatScientific(value) {

    if (value === null || value === undefined) {
        return "-";
    }

    return Number(value).toExponential(2);
}


/* ============================================================
   UPDATE DASHBOARD
============================================================ */

function updateDashboard(data) {

    /*
     * ENERGY
     */

    const energy =
        Number(data.energy_consumed || 0);

    document.getElementById("energyValue")
        .textContent =
        energy.toFixed(9);

    document.getElementById("energyWh")
        .textContent =
        `${(energy * 1000).toFixed(6)} Wh`;


    /*
     * EMISSIONS
     */

    const emissions =
        Number(data.emissions || 0);

    document.getElementById("emissionsValue")
        .textContent =
        emissions.toExponential(2);

    document.getElementById("emissionsGrams")
        .textContent =
        `${(emissions * 1000).toFixed(4)} g CO₂eq`;


    /*
     * DURATION
     */

    document.getElementById("durationValue")
        .textContent =
        Number(data.duration || 0).toFixed(4);


    /*
     * POWER
     */

    const totalPower =
        Number(data.cpu_power || 0) +
        Number(data.ram_power || 0) +
        Number(data.gpu_power || 0);

    document.getElementById("powerValue")
        .textContent =
        totalPower.toFixed(2);


    /*
     * CPU ENERGY
     */

    document.getElementById("cpuEnergy")
        .textContent =
        `${Number(data.cpu_energy || 0).toFixed(9)} kWh`;

    document.getElementById("cpuEnergyBar")
        .style.width =
        `${getPercentage(
            data.cpu_energy,
            energy
        )}%`;


    /*
     * RAM ENERGY
     */

    document.getElementById("ramEnergy")
        .textContent =
        `${Number(data.ram_energy || 0).toFixed(9)} kWh`;

    const ramPercentage =
        getPercentage(
            data.ram_energy,
            energy
        );

    document.getElementById("ramEnergyBar")
        .style.width =
        `${ramPercentage}%`;

    document.getElementById("ramPercentage")
        .textContent =
        `${ramPercentage.toFixed(1)}%`;


    /*
     * GPU ENERGY
     */

    document.getElementById("gpuEnergy")
        .textContent =
        `${Number(data.gpu_energy || 0).toFixed(9)} kWh`;


    /*
     * CPU UTILIZATION
     */

    const cpuUtil =
        Number(data.cpu_utilization_percent || 0);

    document.getElementById("cpuUtilization")
        .textContent =
        `${cpuUtil.toFixed(2)}%`;

    document.getElementById("cpuUtilizationBar")
        .style.width =
        `${Math.min(cpuUtil, 100)}%`;


    /*
     * RAM UTILIZATION
     */

    const ramUtil =
        Number(data.ram_utilization_percent || 0);

    document.getElementById("ramUtilization")
        .textContent =
        `${ramUtil.toFixed(2)}%`;

    document.getElementById("ramUtilizationBar")
        .style.width =
        `${Math.min(ramUtil, 100)}%`;


    /*
     * CPU POWER
     */

    document.getElementById("cpuPower")
        .textContent =
        `${Number(data.cpu_power || 0).toFixed(2)} W`;


    /*
     * SYSTEM
     */

    setText("os", data.os);

    setText(
        "pythonVersion",
        data.python_version
    );

    setText(
        "codecarbonVersion",
        data.codecarbon_version
    );


    /*
     * METADATA
     */

    setText(
        "projectName",
        data.project_name
    );

    setText(
        "runId",
        data.run_id
    );

    setText(
        "experimentId",
        data.experiment_id
    );

    setText(
        "timestamp",
        data.timestamp
    );


    /*
     * TRACKING STATUS
     */

    const badge =
        document.getElementById(
            "executionBadge"
        );

    badge.textContent =
        "Measurement Available";

    badge.className =
        "badge success";
}


/* ============================================================
   PERCENTAGE
============================================================ */

function getPercentage(value, total) {

    value = Number(value || 0);

    total = Number(total || 0);

    if (total === 0) {
        return 0;
    }

    return (value / total) * 100;
}


/* ============================================================
   SET TEXT
============================================================ */

function setText(id, value) {

    const element =
        document.getElementById(id);

    if (!element) {
        return;
    }

    element.textContent =
        value ?? "-";
}


/* ============================================================
   RUN OASIS ANALYSIS
============================================================ */

async function runAnalysis() {

    const projectPath =
        document
            .getElementById("projectPath")
            .value
            .trim();

    const executionCommand =
        document
            .getElementById("executionCommand")
            .value
            .trim();

    const timeout =
        Number(
            document
                .getElementById("timeout")
                .value
        );


    /*
     * VALIDATION
     */

    if (!projectPath) {

        alert(
            "Please enter the project path."
        );

        return;
    }

    if (!executionCommand) {

        alert(
            "Please enter the execution command."
        );

        return;
    }


    /*
     * UI STATE
     */

    const button =
        document.getElementById(
            "runAnalysis"
        );

    const status =
        document.getElementById(
            "analysisStatus"
        );

    button.disabled = true;

    button.innerHTML =
        "⏳ Running analysis...";

    status.textContent =
        "Executing project and measuring energy...";


    try {

        /*
         * OASIS BACKEND API
         *
         * Your Python backend should expose:
         *
         * POST /api/energy/estimate
         */

        const response =
            await fetch(
                "http://127.0.0.1:8000/api/energy/estimate",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        project_path:
                            projectPath,

                        command:
                            executionCommand,

                        timeout:
                            timeout

                    })
                }
            );


        if (!response.ok) {

            throw new Error(
                `Server returned ${response.status}`
            );
        }


        const result =
            await response.json();


        /*
         * UPDATE DASHBOARD
         */

        updateDashboard(result);


        status.textContent =
            "Analysis completed successfully.";

    }

    catch (error) {

        console.error(error);

        status.textContent =
            "Analysis failed.";

        alert(
            "Could not connect to the OASIS backend.\n\n" +
            "Make sure your Python backend is running."
        );

    }

    finally {

        button.disabled = false;

        button.innerHTML =
            "⚡ Run Energy Analysis";
    }
}


/* ============================================================
   BUTTON
============================================================ */

document
    .getElementById("runAnalysis")
    .addEventListener(
        "click",
        runAnalysis
    );


/* ============================================================
   INITIAL DASHBOARD
============================================================ */

updateDashboard(sampleData);