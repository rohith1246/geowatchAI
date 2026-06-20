document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const searchInput = document.getElementById('location-search');
    const searchClearBtn = document.getElementById('search-clear-btn');
    const searchSpinner = document.getElementById('search-spinner');
    const searchDropdown = document.getElementById('search-dropdown');
    
    const selectedLatSpan = document.getElementById('selected-lat');
    const selectedLngSpan = document.getElementById('selected-lng');
    const selectedNameSpan = document.getElementById('selected-name');
    const locationNameRow = document.getElementById('location-name-row');
    
    const btnSaveLoc = document.getElementById('btn-save-loc');
    const btnAnalyzeAi = document.getElementById('btn-analyze-ai');
    
    // GeoWatch v2 Timeline & Metrics Elements
    const btnCompareTimeline = document.getElementById('btn-compare-timeline');
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');
    
    const metricsPanel = document.getElementById('metrics-panel');
    const metricVeg = document.getElementById('metric-veg');
    const metricWater = document.getElementById('metric-water');
    const metricRoad = document.getElementById('metric-road');
    const metricUrban = document.getElementById('metric-urban');
    const metricRisk = document.getElementById('metric-risk');
    
    const savedLocationsList = document.getElementById('saved-locations-list');
    const historyCount = document.getElementById('history-count');
    
    const archivedReportsList = document.getElementById('archived-reports-list');
    const archiveCount = document.getElementById('archive-count');
    
    const terminalScreen = document.getElementById('terminal-screen');
    const terminalWelcome = document.querySelector('.terminal-welcome');
    const terminalLoading = document.getElementById('terminal-loading');
    const terminalOutput = document.getElementById('terminal-output');
    const terminalFooter = document.getElementById('terminal-footer');
    const engineTag = document.getElementById('engine-tag');
    
    // Map State variables
    let map;
    let activeMarker = null;
    let selectedCoords = null;
    let selectedLocationName = '';
    let searchDebounceTimeout = null;

    // 1. Initialize Map
    function initMap() {
        // Set default view to a global perspective
        map = L.map('map', {
            zoomControl: true,
            maxZoom: 18,
            minZoom: 2
        }).setView([20.0, 0.0], 3);

        // Define ESRI Satellite base layer
        const esriWorldImagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
        }).addTo(map);

        // Define ESRI hybrid borders and labels overlay
        const esriLabels = L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Labels &copy; Esri',
            opacity: 0.85
        }).addTo(map);

        // Map Click Event
        map.on('click', onMapClick);
    }

    // 2. Map Click Handler
    function onMapClick(e) {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        
        selectedCoords = { lat, lng };
        
        // Pinned coordinate naming convention
        selectedLocationName = `Hotspot [${lat.toFixed(4)}, ${lng.toFixed(4)}]`;
        
        updateSelectedCoordinatesUI(lat, lng, selectedLocationName);
        placeMarker(lat, lng, selectedLocationName);
        
        // Clear search input since we clicked manually
        searchInput.value = '';
        searchClearBtn.style.display = 'none';
        searchDropdown.style.display = 'none';
    }

    // 3. Update Coordinates Selection Panel
    function updateSelectedCoordinatesUI(lat, lng, name) {
        selectedLatSpan.textContent = lat.toFixed(6);
        selectedLngSpan.textContent = lng.toFixed(6);
        
        if (name) {
            selectedNameSpan.textContent = name;
            locationNameRow.style.display = 'flex';
        } else {
            locationNameRow.style.display = 'none';
        }
        
        // Enable buttons
        btnSaveLoc.disabled = false;
        btnAnalyzeAi.disabled = false;
        btnCompareTimeline.disabled = false;
        
        // Reset save button layout (in case it was checked)
        btnSaveLoc.innerHTML = '<i class="fa-regular fa-bookmark"></i> Save Location';
    }

    // 4. Place Marker on Map
    function placeMarker(lat, lng, popupText) {
        if (activeMarker) {
            map.removeLayer(activeMarker);
        }
        
        // Create custom icon or style
        activeMarker = L.marker([lat, lng]).addTo(map);
        
        // Bind modern dark themed popup
        activeMarker.bindPopup(`
            <div class="popup-details">
                <h4>Pinned Location</h4>
                <p>${popupText}</p>
                <div>Lat: <span>${lat.toFixed(5)}</span></div>
                <div>Lng: <span>${lng.toFixed(5)}</span></div>
            </div>
        `).openPopup();
    }

    // 5. Search Autocomplete Debounce
    searchInput.addEventListener('input', () => {
        const query = searchInput.value.trim();
        
        if (query.length === 0) {
            clearSearchState();
            return;
        }
        
        searchClearBtn.style.display = 'block';
        searchSpinner.style.display = 'block';
        
        clearTimeout(searchDebounceTimeout);
        searchDebounceTimeout = setTimeout(() => {
            executeSearch(query);
        }, 400); // 400ms debounce
    });

    searchClearBtn.addEventListener('click', () => {
        clearSearchState();
    });

    function clearSearchState() {
        searchInput.value = '';
        searchClearBtn.style.display = 'none';
        searchSpinner.style.display = 'none';
        searchDropdown.style.display = 'none';
        searchDropdown.innerHTML = '';
    }

    // 6. Execute Remote Location Search
    function executeSearch(query) {
        fetch(`/api/search?q=${encodeURIComponent(query)}`)
            .then(res => res.json())
            .then(data => {
                searchSpinner.style.display = 'none';
                
                if (data.error || data.length === 0) {
                    searchDropdown.innerHTML = '<div class="search-result-item">No results found</div>';
                    searchDropdown.style.display = 'block';
                    return;
                }
                
                searchDropdown.innerHTML = '';
                data.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'search-result-item';
                    div.textContent = item.display_name;
                    div.addEventListener('click', () => {
                        selectSearchResult(item);
                    });
                    searchDropdown.appendChild(div);
                });
                
                searchDropdown.style.display = 'block';
            })
            .catch(err => {
                console.error("Search error:", err);
                searchSpinner.style.display = 'none';
                searchDropdown.innerHTML = '<div class="search-result-item">Search failed. Try again.</div>';
                searchDropdown.style.display = 'block';
            });
    }

    // 7. Select Result from Search Box
    function selectSearchResult(item) {
        const lat = item.lat;
        const lon = item.lon;
        const name = item.display_name;
        
        selectedCoords = { lat: lat, lng: lon };
        selectedLocationName = name;
        
        searchInput.value = name;
        searchDropdown.style.display = 'none';
        
        // Fly map smoothly to the search location
        map.flyTo([lat, lon], 13, {
            animate: true,
            duration: 1.8
        });
        
        updateSelectedCoordinatesUI(lat, lon, name);
        placeMarker(lat, lon, name);
    }

    // Close search dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
            searchDropdown.style.display = 'none';
        }
    });

    // 8. Fetch Saved Locations History
    function loadSavedLocations() {
        fetch('/api/locations')
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    console.error("API error fetching locations:", data.error);
                    return;
                }
                
                renderLocationsList(data);
            })
            .catch(err => {
                console.error("Network error fetching locations:", err);
            });
    }

    // 9. Render Saved Locations List
    function renderLocationsList(locations) {
        historyCount.textContent = locations.length;
        
        if (locations.length === 0) {
            savedLocationsList.innerHTML = `
                <div class="history-placeholder">
                    <i class="fa-solid fa-globe-asia"></i>
                    <p>No locations saved yet. Click the map to pin and save a hotspot.</p>
                </div>
            `;
            return;
        }
        
        savedLocationsList.innerHTML = '';
        locations.forEach(loc => {
            const item = document.createElement('div');
            item.className = 'history-item';
            item.setAttribute('data-id', loc.id);
            
            item.innerHTML = `
                <div class="history-info">
                    <div class="history-name" title="${loc.location_name}">${loc.location_name}</div>
                    <div class="history-coords">${loc.latitude.toFixed(4)}°, ${loc.longitude.toFixed(4)}°</div>
                </div>
                <button class="btn-delete-history" title="Delete Location">
                    <i class="fa-regular fa-trash-can"></i>
                </button>
            `;
            
            // Fly-to click event on the item body
            item.addEventListener('click', (e) => {
                if (e.target.closest('.btn-delete-history')) return; // ignore delete click
                
                selectedCoords = { lat: loc.latitude, lng: loc.longitude };
                selectedLocationName = loc.location_name;
                
                map.flyTo([loc.latitude, loc.longitude], 12, {
                    animate: true,
                    duration: 1.5
                });
                
                updateSelectedCoordinatesUI(loc.latitude, loc.longitude, loc.location_name);
                placeMarker(loc.latitude, loc.longitude, loc.location_name);
            });
            
            // Delete click event
            const deleteBtn = item.querySelector('.btn-delete-history');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteLocation(loc.id);
            });
            
            savedLocationsList.appendChild(item);
        });
    }

    // 10. Save Selected Location
    btnSaveLoc.addEventListener('click', () => {
        if (!selectedCoords) return;
        
        // Prompt the user for custom location name, prefilled with resolved name
        const promptName = prompt("Enter a name for this saved hotspot:", selectedLocationName);
        if (promptName === null) return; // user cancelled
        
        const finalName = promptName.trim() || `Hotspot [${selectedCoords.lat.toFixed(4)}, ${selectedCoords.lng.toFixed(4)}]`;
        
        btnSaveLoc.disabled = true;
        btnSaveLoc.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        
        fetch('/api/locations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                location_name: finalName,
                latitude: selectedCoords.lat,
                longitude: selectedCoords.lng
            })
        })
        .then(res => {
            if (!res.ok) throw new Error("Failed to save location");
            return res.json();
        })
        .then(savedLoc => {
            btnSaveLoc.innerHTML = '<i class="fa-solid fa-check"></i> Saved!';
            selectedLocationName = savedLoc.location_name;
            selectedNameSpan.textContent = savedLoc.location_name;
            
            // Refresh list
            loadSavedLocations();
            
            // Re-enable after delay
            setTimeout(() => {
                btnSaveLoc.disabled = false;
                btnSaveLoc.innerHTML = '<i class="fa-regular fa-bookmark"></i> Save Location';
            }, 1500);
        })
        .catch(err => {
            console.error("Error saving location:", err);
            alert("Error saving location. Please try again.");
            btnSaveLoc.disabled = false;
            btnSaveLoc.innerHTML = '<i class="fa-regular fa-bookmark"></i> Save Location';
        });
    });

    // 11. Delete Location Endpoint Call
    function deleteLocation(id) {
        if (!confirm("Are you sure you want to remove this hotspot from your history?")) return;
        
        fetch(`/api/locations/${id}`, {
            method: 'DELETE'
        })
        .then(res => {
            if (!res.ok) throw new Error("Failed to delete");
            return res.json();
        })
        .then(() => {
            loadSavedLocations();
        })
        .catch(err => {
            console.error("Error deleting location:", err);
            alert("Could not delete location.");
        });
    }

    // 12. AI Analysis Handler
    btnAnalyzeAi.addEventListener('click', () => {
        if (!selectedCoords) return;
        
        // UI transitions
        terminalWelcome.style.display = 'none';
        terminalOutput.style.display = 'none';
        terminalFooter.style.display = 'none';
        terminalLoading.style.display = 'flex';
        
        btnAnalyzeAi.disabled = true;
        btnAnalyzeAi.innerHTML = '<i class="fa-solid fa-satellite-dish fa-spin"></i> Modeling...';
        
        fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                location_name: selectedLocationName,
                latitude: selectedCoords.lat,
                longitude: selectedCoords.lng
            })
        })
        .then(res => {
            if (!res.ok) throw new Error("Analysis failed");
            return res.json();
        })
        .then(data => {
            terminalLoading.style.display = 'none';
            btnAnalyzeAi.disabled = false;
            btnAnalyzeAi.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Ask AI Changes';
            
            // Load content using marked markdown parser
            const htmlContent = marked.parse(data.analysis);
            terminalOutput.innerHTML = htmlContent;
            terminalOutput.style.display = 'block';
            
            // Setup footer engine tag details
            engineTag.textContent = `Engine: ${data.source}`;
            terminalFooter.style.display = 'flex';
            
            // Scroll terminal content container to the bottom
            terminalScreen.scrollTop = 0;
            
            // Terminal typewriter accent glow effect
            terminalOutput.style.animation = 'none';
            terminalOutput.offsetHeight; /* trigger reflow */
            terminalOutput.style.animation = 'fadeIn 0.6s ease';
        })
        .catch(err => {
            console.error("AI Analysis error:", err);
            terminalLoading.style.display = 'none';
            btnAnalyzeAi.disabled = false;
            btnAnalyzeAi.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Ask AI Changes';
            
            terminalOutput.innerHTML = `
                <p style="color: #ef4444;"><i class="fa-solid fa-circle-exclamation"></i> ERROR: Neural telemetry connection timed out.</p>
                <p style="color: #94a3b8; font-size: 0.8rem;">Reason: ${err.message}. Ensure backend endpoints are online.</p>
            `;
            terminalOutput.style.display = 'block';
        });
    });

    // 13. GeoWatch Timeline Compare Handler (v2)
    btnCompareTimeline.addEventListener('click', () => {
        if (!selectedCoords) return;
        
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;
        
        if (!startDate || !endDate) {
            alert("Please select both a Start Date and an End Date.");
            return;
        }

        // UI transitions
        terminalWelcome.style.display = 'none';
        terminalOutput.style.display = 'none';
        terminalFooter.style.display = 'none';
        terminalLoading.style.display = 'flex';
        metricsPanel.style.display = 'none'; // reset metrics view
        
        btnCompareTimeline.disabled = true;
        btnCompareTimeline.innerHTML = '<i class="fa-solid fa-satellite-dish fa-spin"></i> Comparing...';

        fetch('/api/analyze-change', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                location_name: selectedLocationName,
                latitude: selectedCoords.lat,
                longitude: selectedCoords.lng,
                start_date: startDate,
                end_date: endDate
            })
        })
        .then(res => {
            if (!res.ok) throw new Error("Temporal comparison analysis failed");
            return res.json();
        })
        .then(data => {
            terminalLoading.style.display = 'none';
            btnCompareTimeline.disabled = false;
            btnCompareTimeline.innerHTML = '<i class="fa-solid fa-clock-rotate-left"></i> Run GeoWatch Analysis';

            // Populate Visual Metric Cards
            metricVeg.textContent = data.metrics.vegetation_change;
            metricWater.textContent = data.metrics.water_change;
            metricRoad.textContent = data.metrics.road_growth;
            metricUrban.textContent = data.metrics.urban_growth;
            metricRisk.textContent = data.metrics.risk_score;
            metricsPanel.style.display = 'block';

            // Render Markdown AI report
            const htmlContent = marked.parse(data.report);
            terminalOutput.innerHTML = htmlContent;
            terminalOutput.style.display = 'block';

            // Setup footer engine tag
            engineTag.textContent = `Engine: ${data.source}`;
            terminalFooter.style.display = 'flex';

            terminalScreen.scrollTop = 0;

            // Trigger animation
            terminalOutput.style.animation = 'none';
            terminalOutput.offsetHeight; /* trigger reflow */
            terminalOutput.style.animation = 'fadeIn 0.6s ease';

            // Reload archives list
            loadArchivedReports();
        })
        .catch(err => {
            console.error("Temporal compare error:", err);
            terminalLoading.style.display = 'none';
            btnCompareTimeline.disabled = false;
            btnCompareTimeline.innerHTML = '<i class="fa-solid fa-clock-rotate-left"></i> Run GeoWatch Analysis';

            terminalOutput.innerHTML = `
                <p style="color: #ef4444;"><i class="fa-solid fa-circle-exclamation"></i> ERROR: Temporal telemetry modeling failed.</p>
                <p style="color: #94a3b8; font-size: 0.8rem;">Reason: ${err.message}. Ensure backend is online.</p>
            `;
            terminalOutput.style.display = 'block';
        });
    });

    // 14. Fetch Archived Reports
    function loadArchivedReports() {
        fetch('/api/analysis-records')
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    console.error("API error fetching archives:", data.error);
                    return;
                }
                renderArchivedReportsList(data);
            })
            .catch(err => {
                console.error("Error fetching archives:", err);
            });
    }

    // 15. Render Archived Reports List
    function renderArchivedReportsList(records) {
        archiveCount.textContent = records.length;
        
        if (records.length === 0) {
            archivedReportsList.innerHTML = `
                <div class="history-placeholder">
                    <i class="fa-solid fa-file-invoice"></i>
                    <p>No archives saved yet. Run a temporal comparison analysis.</p>
                </div>
            `;
            return;
        }

        archivedReportsList.innerHTML = '';
        records.forEach(rec => {
            const item = document.createElement('div');
            item.className = 'history-item';
            item.setAttribute('data-id', rec.id);

            // Reuses .btn-delete-history class for styling the delete button
            item.innerHTML = `
                <div class="history-info">
                    <div class="history-name" title="${rec.location_name}">${rec.location_name}</div>
                    <div class="history-coords">${rec.start_date.substring(0,4)} ➔ ${rec.end_date.substring(0,4)} | Risk: ${rec.metrics.risk_score}</div>
                </div>
                <button class="btn-delete-history btn-delete-archive" title="Delete Archive">
                    <i class="fa-regular fa-trash-can"></i>
                </button>
            `;

            // Fly-to and restore state on click
            item.addEventListener('click', (e) => {
                if (e.target.closest('.btn-delete-archive')) return;

                selectedCoords = { lat: rec.latitude, lng: rec.longitude };
                selectedLocationName = rec.location_name;

                map.flyTo([rec.latitude, rec.longitude], 12, {
                    animate: true,
                    duration: 1.5
                });

                // Update date pickers
                startDateInput.value = rec.start_date;
                endDateInput.value = rec.end_date;

                // Update UI panels
                updateSelectedCoordinatesUI(rec.latitude, rec.longitude, rec.location_name);
                placeMarker(rec.latitude, rec.longitude, rec.location_name);

                // Populate metrics cards
                metricVeg.textContent = rec.metrics.vegetation_change;
                metricWater.textContent = rec.metrics.water_change;
                metricRoad.textContent = rec.metrics.road_growth;
                metricUrban.textContent = rec.metrics.urban_growth;
                metricRisk.textContent = rec.metrics.risk_score;
                metricsPanel.style.display = 'block';

                // Populate terminal report
                terminalWelcome.style.display = 'none';
                terminalLoading.style.display = 'none';
                terminalOutput.innerHTML = marked.parse(rec.report);
                terminalOutput.style.display = 'block';

                engineTag.textContent = `Engine: Archived Report (ID: ${rec.id})`;
                terminalFooter.style.display = 'flex';

                terminalScreen.scrollTop = 0;
            });

            // Delete click event
            const deleteBtn = item.querySelector('.btn-delete-archive');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteArchivedReport(rec.id);
            });

            archivedReportsList.appendChild(item);
        });
    }

    // 16. Delete Archived Report
    function deleteArchivedReport(id) {
        if (!confirm("Are you sure you want to permanently delete this archived report?")) return;

        fetch(`/api/analysis-records/${id}`, {
            method: 'DELETE'
        })
        .then(res => {
            if (!res.ok) throw new Error("Failed to delete archive");
            return res.json();
        })
        .then(() => {
            loadArchivedReports();
        })
        .catch(err => {
            console.error("Error deleting archive:", err);
            alert("Could not delete archived report.");
        });
    }

    // Run Initializations
    initMap();
    loadSavedLocations();
    loadArchivedReports();
});
