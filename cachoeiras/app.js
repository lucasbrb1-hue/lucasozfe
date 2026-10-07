(async function () {
  const KEY = (window.CONFIG || {}).GOOGLE_MAPS_API_KEY;
  const [conhecidas, candidatas] = await Promise.all([
    fetch("data/cachoeiras.json").then(r => r.json()),
    fetch("data/candidatas.json").then(r => r.ok ? r.json() : []).catch(() => []),
  ]);
  const itens = [
    ...conhecidas.map(c => ({ ...c, tipo: "conhecida" })),
    ...candidatas.map((c, i) => ({
      id: "cand-" + i, nome: "Candidata #" + (i + 1), estado: "", tipo: "candidata",
      lat: c.lat, lng: c.lng, altura_m: c.queda_m,
      descricao: `Detectada por satélite: queda estimada ${c.queda_m} m, área de drenagem ${c.area_km2} km².`,
    })),
  ];

  const mapa = KEY ? await mapaGoogle(KEY) : mapaLeaflet();
  document.getElementById("fonte-mapa").textContent =
    KEY ? "Mapa: Google Maps (satélite)" : "Mapa: Esri World Imagery (defina a chave Google em config.js)";

  const lista = document.getElementById("lista");
  const busca = document.getElementById("busca");
  const chk = document.getElementById("ver-candidatas");
  const marcadores = new Map();
  itens.forEach(it => marcadores.set(it.id, mapa.marcador(it)));

  function render() {
    const q = busca.value.trim().toLowerCase();
    lista.innerHTML = "";
    itens.forEach(it => {
      const visivel = (it.tipo === "conhecida" || chk.checked) &&
        (it.nome + " " + it.estado).toLowerCase().includes(q);
      mapa.mostrar(marcadores.get(it.id), visivel);
      if (!visivel) return;
      const li = document.createElement("li");
      if (it.tipo === "candidata") li.className = "cand";
      const nome = document.createElement("strong");
      nome.textContent = it.nome;
      const det = document.createElement("small");
      det.textContent = [it.estado, it.altura_m ? it.altura_m + " m" : ""].filter(Boolean).join(" · ");
      li.append(nome, det);
      li.onclick = () => mapa.focar(it);
      lista.appendChild(li);
    });
  }
  busca.oninput = render;
  chk.onchange = render;
  render();

  function popupHtml(it) {
    const d = document.createElement("div");
    const b = document.createElement("b"); b.textContent = it.nome;
    const p = document.createElement("p"); p.textContent = it.descricao || "";
    d.append(b, p);
    return d;
  }

  function mapaLeaflet() {
    const m = L.map("mapa").setView([-15, -50], 4);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "Esri World Imagery", maxZoom: 18 }).addTo(m);
    return {
      marcador(it) {
        const mk = L.circleMarker([it.lat, it.lng], {
          radius: 7, color: it.tipo === "candidata" ? "#f6ad55" : "#4fd1c5", fillOpacity: .8,
        }).bindPopup(popupHtml(it));
        return mk.addTo(m);
      },
      mostrar(mk, v) { v ? mk.addTo(m) : m.removeLayer(mk); },
      focar(it) { m.setView([it.lat, it.lng], 14); marcadores.get(it.id).openPopup(); },
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
          icon: { path: google.maps.SymbolPath.CIRCLE, scale: 7, fillOpacity: .9,
            fillColor: it.tipo === "candidata" ? "#f6ad55" : "#4fd1c5", strokeWeight: 1 },
        });
        mk.addListener("click", () => { info.setContent(popupHtml(it)); info.open(m, mk); });
        return mk;
      },
      mostrar(mk, v) { mk.setMap(v ? m : null); },
      focar(it) { m.setCenter({ lat: it.lat, lng: it.lng }); m.setZoom(15); },
    };
  }
})();
