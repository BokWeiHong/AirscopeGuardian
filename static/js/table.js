const schemaUrl = "/api_tester/schema/tables/";
const fetchUrl  = "/api_tester/data/fetch/";

const tabNavigation      = document.getElementById("tabNavigation");
const tabContents        = document.getElementById("tabContents");
const selectAllTables    = document.getElementById("selectAllTables");
const activeFiltersInput = document.getElementById("activeFilters");
const tablesContainer    = document.getElementById("tablesContainer");

let currentTab = null;

/* ---------- CSRF ---------- */
function getCSRFToken() {
    return document.cookie
        .split("; ")
        .find(row => row.startsWith("csrftoken="))
        ?.split("=")[1];
}

/* ---------- TAB SWITCH ---------- */
function switchTab(tableName) {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

    const tab   = document.querySelector(`.tab[data-table="${tableName}"]`);
    const panel = document.querySelector(`.tab-panel[data-table="${tableName}"]`);

    if (tab && panel) {
        tab.classList.add("active");
        panel.classList.add("active");
        currentTab = tableName;
    }
}

/* ---------- ACTIVE FILTERS ---------- */
function updateActiveFilters() {
    const selected = {};

    document.querySelectorAll(".tab-panel").forEach(panel => {
        const tableName = panel.dataset.table;
        const tabCheckbox = document.querySelector(
            `.tab-checkbox[data-table="${tableName}"]`
        );

        if (!tabCheckbox.checked) return;

        const cols = [...panel.querySelectorAll(".column-checkbox")]
            .filter(cb => cb.checked)
            .map(cb => cb.dataset.col);

        if (cols.length) selected[tableName] = cols;
    });

    activeFiltersInput.value = JSON.stringify(selected);
}

/* ---------- TABLE RENDER ---------- */
function renderTables(data) {
    tablesContainer.innerHTML = "";

    if (!data || Object.keys(data).length === 0) {
        tablesContainer.innerHTML = "<p>No data returned.</p>";
        return;
    }

    Object.entries(data).forEach(([tableName, rows]) => {
        if (!Array.isArray(rows) || rows.length === 0) return;

        const columns = Object.keys(rows[0]);

        const wrapper = document.createElement("div");
        wrapper.className = "api-table-wrapper";

        const title = document.createElement("h3");
        title.textContent = tableName;
        wrapper.appendChild(title);

        /* SEARCH BAR */
        const searchDiv = document.createElement("div");
        searchDiv.className = "api-table-search";

        const searchInput = document.createElement("input");
        searchInput.type = "text";
        searchInput.placeholder = "SEARCH...";
        searchDiv.appendChild(searchInput);

        wrapper.appendChild(searchDiv);

        /* TABLE */
        const table = document.createElement("table");
        table.className = "retro-table";

        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");

        columns.forEach(col => {
            const th = document.createElement("th");
            th.classList.add("sortable");

            th.appendChild(document.createTextNode(col));

            const icon = document.createElement("span");
            icon.className = "sort-icon";
            th.appendChild(icon);

            th.addEventListener("click", () => {
                sortTable(table, col, icon);
            });

            headerRow.appendChild(th);
        });

        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");

        rows.forEach(row => {
            const tr = document.createElement("tr");
            columns.forEach(col => {
                const td = document.createElement("td");
                td.textContent = row[col] ?? "-";
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        wrapper.appendChild(table);
        tablesContainer.appendChild(wrapper);

        /* SEARCH LOGIC */
        searchInput.addEventListener("input", () => {
            const terms = searchInput.value
                .toLowerCase()
                .split(/[,\s]+/)   // split by space OR comma
                .filter(Boolean); // remove empty strings

            Array.from(tbody.rows).forEach(tr => {
                const rowText = Array.from(tr.cells)
                    .map(td => td.textContent.toLowerCase())
                    .join(" ");

                const match = terms.every(term => rowText.includes(term));
                tr.style.display = match ? "" : "none";
            });
        });
    });
}

/* ---------- SORT ---------- */
function sortTable(table, colName, iconElement) {
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.rows);
    const headers = Array.from(table.querySelectorAll("th"));

    const colIndex = headers.findIndex(
        th => th.childNodes[0]?.textContent?.trim() === colName
    );
    if (colIndex === -1) return;

    const ascending = iconElement.dataset.order !== "asc";
    iconElement.dataset.order = ascending ? "asc" : "desc";

    table.querySelectorAll(".sort-icon").forEach(ic => {
        if (ic !== iconElement) {
            ic.textContent = "";
            delete ic.dataset.order;
        }
    });

    iconElement.textContent = ascending ? "▲" : "▼";

    rows.sort((a, b) => {
        const aText = a.children[colIndex].textContent.trim();
        const bText = b.children[colIndex].textContent.trim();

        const aNum = parseFloat(aText);
        const bNum = parseFloat(bText);

        if (!isNaN(aNum) && !isNaN(bNum)) {
            return ascending ? aNum - bNum : bNum - aNum;
        }
        return ascending
            ? aText.localeCompare(bText)
            : bText.localeCompare(aText);
    });

    rows.forEach(r => tbody.appendChild(r));
}

/* ---------- SCHEMA LOAD ---------- */
fetch(schemaUrl)
    .then(res => res.json())
    .then(schema => {
        Object.entries(schema).forEach(([tableName, tableData], index) => {
            const tab = document.createElement("div");
            tab.className = "tab";
            tab.dataset.table = tableName;

            const tabCheckbox = document.createElement("input");
            tabCheckbox.type = "checkbox";
            tabCheckbox.className = "tab-checkbox";
            tabCheckbox.dataset.table = tableName;

            const tabLabel = document.createElement("span");
            tabLabel.textContent = tableData.label;
            tabLabel.style.cursor = "pointer";

            tab.appendChild(tabCheckbox);
            tab.appendChild(tabLabel);
            tabNavigation.appendChild(tab);

            const panel = document.createElement("div");
            panel.className = "tab-panel";
            panel.dataset.table = tableName;

            Object.entries(tableData.groups).forEach(([groupName, columns]) => {
                const group = document.createElement("div");
                group.className = "api-column-group";

                const title = document.createElement("strong");
                title.textContent = groupName;
                group.appendChild(title);

                columns.forEach(col => {
                    const label = document.createElement("label");
                    const cb = document.createElement("input");
                    cb.type = "checkbox";
                    cb.className = "column-checkbox";
                    cb.dataset.col = col;

                    cb.addEventListener("change", () => {
                        if (cb.checked) tabCheckbox.checked = true;
                        updateActiveFilters();
                    });

                    label.appendChild(cb);
                    label.append(" " + col);
                    group.appendChild(label);
                });

                panel.appendChild(group);
            });

            tabContents.appendChild(panel);

            tabLabel.addEventListener("click", () => switchTab(tableName));

            tabCheckbox.addEventListener("change", e => {
                e.stopPropagation();
                panel.querySelectorAll(".column-checkbox")
                    .forEach(cb => cb.checked = tabCheckbox.checked);
                updateActiveFilters();
            });

            if (index === 0) switchTab(tableName);
        });
    });

/* ---------- SELECT ALL ---------- */
selectAllTables.addEventListener("change", e => {
    document.querySelectorAll(".tab-checkbox").forEach(cb => {
        cb.checked = e.target.checked;
        cb.dispatchEvent(new Event("change"));
    });
});

/* ---------- APPLY FILTERS ---------- */
document.getElementById("applyFilters").addEventListener("click", () => {
    const payload = {
        tables: JSON.parse(activeFiltersInput.value || "{}")
    };

    fetch(fetchUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken()
        },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        console.log("Filtered data:", data);
        renderTables(data);
    })
    .catch(err => console.error("Fetch error:", err));
});

function getTableData() {
    const data = {};
    const wrappers = document.querySelectorAll(".api-table-wrapper");
    
    wrappers.forEach(wrapper => {
        const tableName = wrapper.querySelector("h3").textContent;
        const table = wrapper.querySelector("table");
        const headers = [...table.querySelectorAll("th")].map(th => th.childNodes[0].textContent.trim());
        const rows = [...table.querySelectorAll("tbody tr")].map(tr => 
            [...tr.cells].map(td => td.textContent.trim())
        );
        data[tableName] = { headers, rows };
    });
    return data;
}

// 1. CSV DOWNLOAD
document.getElementById("downloadCSV").addEventListener("click", () => {
    const data = getTableData();
    if (Object.keys(data).length === 0) return alert("No data to download.");

    Object.entries(data).forEach(([tableName, content]) => {
        let csvContent = "data:text/csv;charset=utf-8," 
            + content.headers.join(",") + "\n"
            + content.rows.map(e => e.join(",")).join("\n");

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `AirscopeGuardian_${tableName}_${new Date().getTime()}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });
});

// 2. PDF DOWNLOAD
document.getElementById("downloadPDF").addEventListener("click", () => {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({
        orientation: 'landscape',
        unit: 'mm',
        format: 'a4'
    });

    const data = getTableData();
    if (Object.keys(data).length === 0) return alert("No data to download.");

    let firstPage = true;
    Object.entries(data).forEach(([tableName, content]) => {
        if (!firstPage) doc.addPage();
        
        doc.setFontSize(14);
        doc.text(`Kismet Report: ${tableName}`, 14, 12);
        
        doc.autoTable({
            head: [content.headers],
            body: content.rows,
            startY: 18,
            theme: 'grid',

            horizontalPageBreak: true, 

            horizontalPageBreakRepeat: 0, 

            styles: { 
                fontSize: 7,
                cellPadding: 2,
                overflow: 'ellipis', 
                noWrap: true,
                minCellHeight: 6
            },

            columnStyles: {
                all: { cellWidth: 35 } 
            },

            headStyles: { fillColor: [40, 40, 40] },
            margin: { top: 20, bottom: 20 },
            pageBreak: 'auto',
        });
        
        firstPage = false;
    });

    doc.save(`AirscopeGuardian_Log_${new Date().getTime()}.pdf`);
});