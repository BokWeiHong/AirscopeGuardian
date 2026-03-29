function getCookie(name) {
   let cookieValue = null;
   if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
         const cookie = cookies[i].trim();
         if (cookie.substring(0, name.length + 1) === (name + '=')) {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            break;
         }
      }
   }
   return cookieValue;
}

const csrftoken = getCookie('csrftoken');

let kismetLogInterval = null;

async function openKismetPopup() {
   const overlay = document.getElementById('kismetPopup');
   const select = document.getElementById('kismetIfaceSelect');
   select.innerHTML = '<option>Loading...</option>';
   overlay.style.display = 'flex';
   try {
      const res = await fetch('api/interfaces/');
      const data = await res.json();
      select.innerHTML = '';
      if (data.interfaces?.length) {
         data.interfaces.forEach(iface => {
            const opt = document.createElement('option');
            opt.value = iface;
            opt.textContent = iface;
            select.appendChild(opt);
         });
      } else {
         select.innerHTML = '<option>No interfaces found</option>';
      }
   } catch (err) {
      console.error("Failed to load interfaces:", err);
      select.innerHTML = '<option>Error loading interfaces</option>';
   }
}
function closeKismetPopup() {
   document.getElementById('kismetPopup').style.display = 'none';
}
async function runKismet() {
   const iface = document.getElementById('kismetIfaceSelect').value;
   if (!iface) return alert("Please select an interface!");
   const res = await fetch(`api/run_kismet/?iface=${iface}`);
   const data = await res.json();
   if (data.status === 'running') {
      startLogStreaming();
      document.getElementById("openKismetUI").classList.remove("hidden");
   } else {
      alert(data.error || "Failed to start Kismet");
   }
}
async function stopKismet() {
   const res = await fetch('api/stop_kismet/');
   const data = await res.json();
   if (data.status === 'stopped') {
      stopLogStreaming();
      document.getElementById("openKismetUI").classList.add("hidden");
   } else {
      alert(data.error || "Failed to stop Kismet");
   }
}
function startLogStreaming() {
   const logBox = document.getElementById('kismetLogs');
   stopLogStreaming();
   kismetLogInterval = setInterval(async () => {
      try {
         const res = await fetch('api/kismet_logs/');
         const data = await res.json();
         if (data.logs) {
            logBox.value = data.logs.join('\n');
            logBox.scrollTop = logBox.scrollHeight;
         }
      } catch (err) {
         console.error('Error fetching logs:', err);
      }
   }, 2000);
}
function stopLogStreaming() {
   if (kismetLogInterval) {
      clearInterval(kismetLogInterval);
      kismetLogInterval = null;
   }
}
function redirectToKismet() {
   const url = `${window.location.protocol}//${window.location.hostname}:2501`;
   window.open(url, "_blank");
}

let websharkLogInterval = null;

async function openWebsharkPopup() {
   const overlay = document.getElementById('websharkPopup');
   const select = document.getElementById('pcapSelect');
   select.innerHTML = '<option>Loading...</option>';
   overlay.style.display = 'flex';

   try {
      const res = await fetch('api/pcaps/');
      const data = await res.json();
      select.innerHTML = '';
      if (data.pcaps?.length) {
         data.pcaps.forEach(file => {
            const opt = document.createElement('option');
            opt.value = file.path;
            opt.textContent = file.name;
            select.appendChild(opt);
         });
      } else {
         select.innerHTML = '<option>No PCAP files found</option>';
      }
   } catch (err) {
      console.error("Failed to load PCAPs:", err);
      select.innerHTML = '<option>Error loading PCAP files</option>';
   }
}

function closeWebsharkPopup() {
   document.getElementById('websharkPopup').style.display = 'none';
}

async function runWebshark() {
   const pcapFile = document.getElementById('pcapSelect').value;
   if (!pcapFile) return alert("Please select a PCAP file!");

   const res = await fetch('api/run_webshark/', {
      method: 'POST',
      headers: {
         'Content-Type': 'application/json',
         'X-CSRFToken': csrftoken
      },
      body: JSON.stringify({ file: pcapFile })
   });

   const data = await res.json();

   if (data.status === 'running') {
      document.getElementById("openWebsharkUI").classList.remove("hidden");
   } else {
      alert(data.error || "Failed to start WebShark");
   }
}

async function stopWebshark() {
   const res = await fetch('api/stop_webshark/', {
      method: 'POST',
      headers: {
         'X-CSRFToken': csrftoken
      }
   });

   const data = await res.json();

   if (data.status === 'stopped') {
      document.getElementById("openWebsharkUI").classList.add("hidden");
   } else {
      alert(data.error || "Failed to stop WebShark");
   }
}

function redirectToWebshark() {
   const url = `${window.location.protocol}//${window.location.hostname}:8085`;
   window.open(url, "_blank");
}

// Charts service
function openChartsPopup() {
   document.getElementById('chartsPopup').style.display = 'flex';
}

function closeChartsPopup() {
   document.getElementById('chartsPopup').style.display = 'none';
}

function runCharts() {
   window.open('/charts/', '_blank');
}

// TrackerJacker service
async function openTrackerJackerPopup() {
   document.getElementById('trackerJackerPopup').style.display = 'flex';
}

async function runTrackerJacker() {
   window.open('/tracker/', '_blank');
}

function closeTrackerJackerPopup() {
   document.getElementById('trackerJackerPopup').style.display = 'none';
}
