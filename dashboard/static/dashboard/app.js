async function sendEmergency() {
  if (!confirm("Confermi l'invio dell'avviso di MALATTIA?")) return;

  try {
    const resp = await fetch("/api/emergency/", {
      method: "POST",
      headers: {
        "X-Requested-With": "XMLHttpRequest"
      }
    });
    if (!resp.ok) {
      alert("Errore invio avviso");
      return;
    }
    alert("Avviso inviato con successo");
  } catch (err) {
    console.error(err);
    alert("Errore di rete nell'invio dell'emergenza");
  }
}

async function refreshData() {
  try {
    const resp = await fetch("/api/latest/");
    if (!resp.ok) return;

    const data = await resp.json();
    const nodes = data.nodes || [];
    const tbody = document.getElementById("nodes-tbody");
    if (!tbody) return;

    tbody.innerHTML = "";

    if (!nodes.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 6;
      td.textContent = "Nessun dato disponibile.";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    nodes.forEach((m) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${m.node_id}</td>
        <td>${m.temp_aria ?? ""}</td>
        <td>${m.umid_aria ?? ""}</td>
        <td>${m.umid_suolo ?? ""}</td>
        <td>${m.rain_mm ?? ""}</td>
        <td>${m.time || ""}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Errore refresh dati", err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const emergencyBtn = document.getElementById("emergency-btn");
  if (emergencyBtn) {
    emergencyBtn.addEventListener("click", sendEmergency);
  }

  // refresh iniziale + ogni 30 secondi
  refreshData();
  setInterval(refreshData, 30000);
});
