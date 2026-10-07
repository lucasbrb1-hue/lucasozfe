(async function () {
  const KEY = (window.CONFIG || {}).GOOGLE_MAPS_API_KEY;
  const conhecidas = await fetch("data/cachoeiras.json").then(r => r.json());
  let itens = conhecidas.map(c => ({ ...c, tipo: "conhecida" }));

  const mapa = KEY ? await mapaGoogle(KEY) : mapaLeaflet();
  document.getElementById("fonte-mapa").textContent =
    KEY ? "Mapa: Google Maps (satélite)" : "Mapa: Esri World Imagery (defina a chave Google em config.js)";

  const lista = document.getElementById("lista");
  const busca = document.getElementById("busca");
  const status = document.getElementById("status");
  const marcadores = new Map();
  itens.forEach(it => marcadores.set(it.id, mapa.marcador(it)));

  function render() {
    const q = busca.value.trim().toLowerCase();
    lista.innerHTML = "";
    itens.forEach(it => {
      const visivel = (it.nome + " " + it.estado).toLowerCase().includes(q);
      mapa.mostrar(marcadores.get(it.id), visivel);
      if (!visivel) return;
      const li = document.createElement("li");
      if (it.tipo === "candidata") li.className = "cand";
      const nome = document.createElement("strong");
      nome.textContent = it.nome;
      if (it.tipo === "candidata") {
        const pr = document.createElement("span");
        pr.className = "prob"; pr.textContent = it.probabilidade + "%";
        li.append(pr);
      }
      const det = document.createElement("small");
      det.textContent = [it.estado, it.altura_m ? it.altura_m + " m" : ""].filter(Boolean).join(" · ");
      li.append(nome, det);
      li.onclick = () => mapa.focar(it, marcadores.get(it.id));
      lista.appendChild(li);
    });
  }
  busca.oninput = render;
  render();

  document.getElementById("form-cidade").onsubmit = async e => {
    e.preventDefault();
    const cidade = document.getElementById("cidade").value;
    const btn = document.getElementById("btn-buscar");
    btn.disabled = true;
    status.textContent = "Analisando relevo e rios por satélite… pode levar até 1 minuto.";
    try {
      const r = await fetch("/api/buscar?cidade=" + encodeURIComponent(cidade));
      const dados = await r.json();
      if (!r.ok) throw new Error(dados.erro || "Erro " + r.status);
      itens.filter(i => i.tipo === "candidata").forEach(i => mapa.remover(marcadores.get(i.id)));
      itens = itens.filter(i => i.tipo !== "candidata");
      dados.candidatas.forEach((c, i) => {
        const it = {
          id: "cand-" + i, nome: "Candidata #" + (i + 1), estado: "", tipo: "candidata",
          lat: c.lat, lng: c.lng, altura_m: c.queda_m, probabilidade: c.probabilidade,
          descricao: `Probabilidade ${c.probabilidade}%. Queda estimada ${c.queda_m} m, ` +
            `área de drenagem ${c.area_km2} km².` + (c.ia_motivo ? " IA: " + c.ia_motivo : ""),
        };
        itens.push(it);
        marcadores.set(it.id, mapa.marcador(it));
      });
      mapa.ajustar(dados.local.bbox);
      status.textContent = `${dados.candidatas.length} locais prováveis perto de ${dados.local.nome.split(",")[0]}` +
        (dados.ia ? " (conferidos por IA)." : " (sem conferência por IA).");
      render();
    } catch (err) {
      status.textContent = "Erro: " + err.message;
    } finally {
      btn.disabled = false;
    }
  };

  function popupHtml(it) {
    const d = document.createElement("div");
    const b = document.createElement("b"); b.textContent = it.nome;
    const p = document.createElement("p"); p.textContent = it.descricao || "";
    d.append(b, p);
    return d;
  }
  const cor = it => it.tipo === "candidata" ? "#f6ad55" : "#4fd1c5";

  function mapaLeaflet() {
    const m = L.map("mapa").setView([-15, -50], 4);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "Esri World Imagery", maxZoom: 18 }).addTo(m);
    return {
      marcador: it => L.circleMarker([it.lat, it.lng], { radius: 7, color: cor(it), fillOpacity: .8 })
        .bindPopup(popupHtml(it)).addTo(m),
      mostrar: (mk, v) => v ? mk.addTo(m) : m.removeLayer(mk),
      remover: mk => m.removeLayer(mk),
      focar(it, mk) { m.setView([it.lat, it.lng], 15); mk.openPopup(); },
      ajustar: b => m.fitBounds([[b[1], b[0]], [b[3], b[2]]]),
    };
  }

  async function mapaGoogle(key) {
    await new Promise((ok, err) => {
      const s = document.createElement("script");
      s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&loading=async`;
      s.onload = ok; s.onerror = err; document.head.appendChild(s);
    });
    const m = new google.maps.Map(document.getElementById("mapa"),
      { center: { lat: -15, lng: -50 }, zoom: 4, mapTypeId: "hybrid" });
    const info = new google.maps.InfoWindow();
    return {
      marcador(it) {
        const mk = new google.maps.Marker({
          position: { lat: it.lat, lng: it.lng }, map: m, title: it.nome,
          icon: { path: google.maps.SymbolPath.CIRCLE, scale: 7, fillOpacity: .9, fillColor: cor(it), strokeWeight: 1 },
        });
        mk.addListener("click", () => { info.setContent(popupHtml(it)); info.open(m, mk); });
        return mk;
      },
      mostrar: (mk, v) => mk.setMap(v ? m : null),
      remover: mk => mk.setMap(null),
      focar(it, mk) { m.setCenter({ lat: it.lat, lng: it.lng }); m.setZoom(16); info.setContent(popupHtml(it)); info.open(m, mk); },
      ajustar: b => m.fitBounds({ west: b[0], south: b[1], east: b[2], north: b[3] }),
    };
  }
})();
