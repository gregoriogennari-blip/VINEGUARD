async function sendEmergency() {
  const selectedNode = document.getElementById("emergency-btn")?.dataset.selectedNode;
  if (!selectedNode) {
    alert("Seleziona un nodo dal filtro prima di segnare una malattia.");
    return;
  }

  if (!confirm(`Confermi malattia per ${selectedNode}?`)) return;

  try {
    const resp = await fetch("/api/emergency/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({
        node_id: selectedNode,
        window_days: 7,
      }),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      alert(data.error || "Errore invio avviso");
      return;
    }
    alert("Avviso salvato come malattia per la serie temporale del nodo.");
  } catch (err) {
    console.error(err);
    alert("Errore di rete nell'invio dell'emergenza");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const emergencyBtn = document.getElementById("emergency-btn");
  if (emergencyBtn) {
    emergencyBtn.addEventListener("click", sendEmergency);
  }

  setInterval(() => {
    if (document.hidden) return;
    const active = document.activeElement;
    if (active && ["SELECT", "INPUT", "BUTTON"].includes(active.tagName)) return;
    window.location.reload();
  }, 30000);
});
