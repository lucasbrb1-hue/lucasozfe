"""Interface gráfica desktop (Tkinter) do software de cálculo de estacas via SPT."""

from __future__ import annotations

import csv
import math
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import depth_solver as ds
from . import pile_group as pg
from . import report as report_mod
from .ai_extraction import (
    AIExtractionError,
    ExtractedLoadItem,
    ExtractedLoadsReport,
    ExtractedReading,
    ExtractedSPTReport,
)
from .loads import FoundationLoad, LoadSet
from .models import PileGeometry, SPTProfile
from .pile_factors import PILE_TYPES
from .reinforcement import STIRRUP_DIAMETERS_MM, default_rho_min_pct, design_reinforcement
from .structural_design import GAMMA_C_CONCRETE_PILE
from .soil_data import get_soil, soil_options

METHOD_LABELS = {
    ds.METHOD_DQ: "Décourt-Quaresma",
    ds.METHOD_AV: "Aoki-Velloso",
    ds.METHOD_BOTH: "Ambos (adota o mais conservador)",
}


class SPTPilesApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.master = master
        self.profile = SPTProfile()
        self.solver_result: ds.DepthSolverResult | None = None
        self.reinforcement_result = None
        self._soil_options = soil_options()
        self._soil_labels = [label for _, label in self._soil_options]
        self._soil_key_by_label = {label: key for key, label in self._soil_options}

        self.ai_pdf_path: str | None = None
        self.ai_extraction_result: ExtractedSPTReport | None = None
        self.ai_review_rows: list[ExtractedReading] = []

        self.load_set = LoadSet()
        self.pile_designs: list[pg.PileDesign] = []
        self.uniformized: bool = False
        self.n_groups_used: int | None = None
        self.ai_loads_pdf_path: str | None = None
        self.ai_loads_extraction_result: ExtractedLoadsReport | None = None
        self.ai_loads_review_rows: list[ExtractedLoadItem] = []

        self.pack(fill="both", expand=True)
        self._build_widgets()

    # ------------------------------------------------------------------ UI
    def _build_widgets(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_settings = ttk.Frame(notebook)
        self.tab_profile = ttk.Frame(notebook)
        self.tab_ai = ttk.Frame(notebook)
        self.tab_pile = ttk.Frame(notebook)
        self.tab_results = ttk.Frame(notebook)
        self.tab_reinforcement = ttk.Frame(notebook)
        self.tab_loads = ttk.Frame(notebook)

        notebook.add(self.tab_settings, text="⚙ Configurações")
        notebook.add(self.tab_profile, text="1. Perfil SPT")
        notebook.add(self.tab_ai, text="2. Importar Laudo (IA)")
        notebook.add(self.tab_pile, text="3. Estaca e Carga")
        notebook.add(self.tab_results, text="4. Resultados")
        notebook.add(self.tab_reinforcement, text="5. Armação")
        notebook.add(self.tab_loads, text="6. Esforços e Uniformização")

        self._build_tab_settings()
        self._build_tab_profile()
        self._build_tab_ai()
        self._build_tab_pile()
        self._build_tab_results()
        self._build_tab_reinforcement()
        self._build_tab_loads()

        footer = ttk.Label(
            self,
            text=(
                "Ferramenta de pré-dimensionamento. Não substitui ART/RRT de engenheiro "
                "habilitado nem a NBR 6118/6122 vigentes."
            ),
            foreground="#7a4a00",
        )
        footer.pack(fill="x", padx=8, pady=(0, 6))

    # -- Aba de Configurações ------------------------------------------------
    def _build_tab_settings(self) -> None:
        frame = self.tab_settings

        info = ttk.Label(
            frame,
            text=(
                "Cole aqui sua própria chave de API da Anthropic (Claude) para usar as "
                "abas de importação por IA (laudo SPT e esforços de fundação). A chave é "
                "salva apenas neste computador, em um arquivo de configuração local (em "
                "texto simples) - cada pessoa que usar este programa deve configurar a "
                "sua própria chave. Obtenha uma chave em https://console.anthropic.com/"
            ),
            wraplength=900,
            justify="left",
        )
        info.pack(fill="x", padx=8, pady=8)

        form = ttk.Frame(frame)
        form.pack(fill="x", padx=8, pady=4)
        ttk.Label(form, text="Chave de API (ANTHROPIC_API_KEY):").grid(row=0, column=0, sticky="w")
        self.entry_api_key = ttk.Entry(form, width=55, show="•")
        self.entry_api_key.grid(row=0, column=1, padx=6)

        self.var_show_api_key = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            form, text="Mostrar", variable=self.var_show_api_key, command=self._toggle_api_key_visibility
        ).grid(row=0, column=2, padx=6)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", padx=8, pady=6)
        ttk.Button(buttons, text="Salvar chave", command=self._save_api_key).pack(side="left")
        ttk.Button(buttons, text="Remover chave salva", command=self._clear_api_key).pack(side="left", padx=8)

        self.label_api_key_status = ttk.Label(frame, text="", font=("TkDefaultFont", 10, "bold"))
        self.label_api_key_status.pack(fill="x", padx=8, pady=8)

        self._refresh_api_key_status()

    def _toggle_api_key_visibility(self) -> None:
        self.entry_api_key.config(show="" if self.var_show_api_key.get() else "•")

    def _save_api_key(self) -> None:
        from .config import save_api_key

        key = self.entry_api_key.get().strip()
        try:
            save_api_key(key)
        except ValueError as exc:
            messagebox.showerror("Chave inválida", str(exc))
            return
        self.entry_api_key.delete(0, tk.END)
        self._refresh_api_key_status()
        messagebox.showinfo("Chave salva", "Chave de API salva neste computador.")

    def _clear_api_key(self) -> None:
        from .config import clear_api_key

        clear_api_key()
        self._refresh_api_key_status()

    def _refresh_api_key_status(self) -> None:
        import os

        from .config import load_api_key

        env_key = os.environ.get("ANTHROPIC_API_KEY")
        saved_key = load_api_key()
        if env_key:
            text = (
                "Usando chave da variável de ambiente ANTHROPIC_API_KEY "
                "(tem prioridade sobre a chave salva na aba Configurações)."
            )
            color = "#0a6e0a"
        elif saved_key:
            tail = saved_key[-4:] if len(saved_key) >= 4 else saved_key
            text = f"Chave salva neste computador (terminando em ...{tail})."
            color = "#0a6e0a"
        else:
            text = "Nenhuma chave configurada. As abas de importação por IA não vão funcionar até configurar."
            color = "#b00020"
        self.label_api_key_status.config(text=text, foreground=color)

    # -- Tab 1: Perfil SPT -------------------------------------------------
    def _build_tab_profile(self) -> None:
        frame = self.tab_profile

        form = ttk.Frame(frame)
        form.pack(fill="x", padx=8, pady=8)

        ttk.Label(form, text="Profundidade (m):").grid(row=0, column=0, sticky="w")
        self.entry_depth = ttk.Entry(form, width=10)
        self.entry_depth.grid(row=0, column=1, padx=4)

        ttk.Label(form, text="N-SPT:").grid(row=0, column=2, sticky="w")
        self.entry_nspt = ttk.Entry(form, width=8)
        self.entry_nspt.grid(row=0, column=3, padx=4)

        ttk.Label(form, text="Tipo de solo:").grid(row=0, column=4, sticky="w")
        self.combo_soil = ttk.Combobox(form, values=self._soil_labels, width=22, state="readonly")
        self.combo_soil.current(0)
        self.combo_soil.grid(row=0, column=5, padx=4)

        ttk.Button(form, text="Adicionar", command=self._add_spt_row).grid(row=0, column=6, padx=6)

        columns = ("depth", "nspt", "soil")
        self.tree_profile = ttk.Treeview(frame, columns=columns, show="headings", height=14)
        self.tree_profile.heading("depth", text="Profundidade (m)")
        self.tree_profile.heading("nspt", text="N-SPT")
        self.tree_profile.heading("soil", text="Solo")
        self.tree_profile.column("depth", width=120, anchor="center")
        self.tree_profile.column("nspt", width=80, anchor="center")
        self.tree_profile.column("soil", width=200, anchor="center")
        self.tree_profile.pack(fill="both", expand=True, padx=8, pady=4)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", padx=8, pady=4)
        ttk.Button(buttons, text="Remover selecionada", command=self._remove_selected_row).pack(side="left")
        ttk.Button(buttons, text="Limpar tudo", command=self._clear_profile).pack(side="left", padx=6)
        ttk.Button(buttons, text="Carregar CSV...", command=self._load_csv).pack(side="left", padx=6)
        ttk.Button(buttons, text="Salvar CSV...", command=self._save_csv).pack(side="left", padx=6)

        water_frame = ttk.Frame(frame)
        water_frame.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(water_frame, text="Nível d'água (N.A.), em m [deixe em branco se seco/não identificado]:").pack(
            side="left"
        )
        self.entry_water_table = ttk.Entry(water_frame, width=10)
        self.entry_water_table.pack(side="left", padx=6)

    def _add_spt_row(self) -> None:
        try:
            depth = float(self.entry_depth.get().replace(",", "."))
            n_spt = int(float(self.entry_nspt.get().replace(",", ".")))
            soil_label = self.combo_soil.get()
            soil_key = self._soil_key_by_label[soil_label]
            self.profile.add(depth, n_spt, soil_key)
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Entrada inválida", str(exc))
            return
        self._refresh_profile_tree()
        self.entry_depth.delete(0, tk.END)
        self.entry_nspt.delete(0, tk.END)

    def _remove_selected_row(self) -> None:
        selected = self.tree_profile.selection()
        if not selected:
            return
        depths_to_remove = {float(self.tree_profile.item(i, "values")[0]) for i in selected}
        self.profile.points = [p for p in self.profile.points if p.depth_m not in depths_to_remove]
        self._refresh_profile_tree()

    def _clear_profile(self) -> None:
        self.profile.clear()
        self._refresh_profile_tree()

    def _refresh_profile_tree(self) -> None:
        self.tree_profile.delete(*self.tree_profile.get_children())
        for p in self.profile.points:
            from .soil_data import get_soil

            self.tree_profile.insert("", "end", values=(f"{p.depth_m:.2f}", p.n_spt, get_soil(p.soil_key).label))

    def _load_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if not path:
            return
        try:
            new_profile = SPTProfile()
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
            start = 1 if rows and not rows[0][0].replace(".", "", 1).replace(",", "", 1).isdigit() else 0
            for row in rows[start:]:
                if not row:
                    continue
                depth, n_spt, soil_key = row[0], row[1], row[2]
                new_profile.add(float(depth.replace(",", ".")), int(float(n_spt)), soil_key.strip())
            self.profile = new_profile
            self._refresh_profile_tree()
        except Exception as exc:  # noqa: BLE001 - reportar qualquer erro de leitura ao usuário
            messagebox.showerror("Erro ao carregar CSV", str(exc))

    def _save_csv(self) -> None:
        if not self.profile.points:
            messagebox.showinfo("Perfil vazio", "Não há leituras de SPT para salvar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["profundidade_m", "n_spt", "solo"])
            for p in self.profile.points:
                writer.writerow([p.depth_m, p.n_spt, p.soil_key])

    def _get_water_table(self) -> tuple[bool, float | None]:
        text = self.entry_water_table.get().strip()
        if not text:
            return False, None
        try:
            return True, float(text.replace(",", "."))
        except ValueError:
            return False, None

    # -- Tab 2: Importar laudo SPT via IA -----------------------------------
    def _build_tab_ai(self) -> None:
        frame = self.tab_ai

        info = ttk.Label(
            frame,
            text=(
                "Envie o PDF do laudo de sondagem SPT para a IA (Claude) interpretar: profundidade, "
                "N-SPT, tipo de solo e nível d'água. Requer a variável de ambiente ANTHROPIC_API_KEY "
                "configurada antes de abrir o programa. Os dados extraídos SEMPRE aparecem abaixo para "
                "revisão e correção manual antes de serem importados para o Perfil SPT (aba 1)."
            ),
            wraplength=900,
            justify="left",
        )
        info.pack(fill="x", padx=8, pady=8)

        top = ttk.Frame(frame)
        top.pack(fill="x", padx=8, pady=4)
        ttk.Button(top, text="Selecionar PDF do laudo...", command=self._select_ai_pdf).pack(side="left")
        self.label_ai_pdf = ttk.Label(top, text="Nenhum arquivo selecionado.")
        self.label_ai_pdf.pack(side="left", padx=8)

        self.button_ai_run = ttk.Button(top, text="Interpretar com IA", command=self._run_ai_extraction)
        self.button_ai_run.pack(side="left", padx=12)

        self.label_ai_status = ttk.Label(frame, text="")
        self.label_ai_status.pack(fill="x", padx=8)

        water_frame = ttk.Frame(frame)
        water_frame.pack(fill="x", padx=8, pady=4)
        ttk.Label(water_frame, text="Nível d'água identificado pela IA (m):").pack(side="left")
        self.label_ai_water = ttk.Label(water_frame, text="-")
        self.label_ai_water.pack(side="left", padx=6)

        columns = ("depth", "nspt", "soil", "original")
        self.tree_ai = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        self.tree_ai.heading("depth", text="Profundidade (m)")
        self.tree_ai.heading("nspt", text="N-SPT")
        self.tree_ai.heading("soil", text="Solo (classificado pela IA)")
        self.tree_ai.heading("original", text="Descrição original do laudo")
        self.tree_ai.column("depth", width=110, anchor="center")
        self.tree_ai.column("nspt", width=70, anchor="center")
        self.tree_ai.column("soil", width=200, anchor="center")
        self.tree_ai.column("original", width=300, anchor="w")
        self.tree_ai.pack(fill="both", expand=True, padx=8, pady=4)

        edit_form = ttk.Frame(frame)
        edit_form.pack(fill="x", padx=8, pady=4)
        ttk.Label(edit_form, text="Editar linha selecionada -> Prof.(m):").pack(side="left")
        self.entry_ai_edit_depth = ttk.Entry(edit_form, width=8)
        self.entry_ai_edit_depth.pack(side="left", padx=2)
        ttk.Label(edit_form, text="N-SPT:").pack(side="left")
        self.entry_ai_edit_nspt = ttk.Entry(edit_form, width=6)
        self.entry_ai_edit_nspt.pack(side="left", padx=2)
        ttk.Label(edit_form, text="Solo:").pack(side="left")
        self.combo_ai_edit_soil = ttk.Combobox(edit_form, values=self._soil_labels, width=20, state="readonly")
        self.combo_ai_edit_soil.pack(side="left", padx=2)
        ttk.Button(edit_form, text="Aplicar correção", command=self._apply_ai_row_edit).pack(side="left", padx=6)
        self.tree_ai.bind("<<TreeviewSelect>>", self._on_ai_row_select)

        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", padx=8, pady=8)
        ttk.Button(bottom, text="Remover linha selecionada", command=self._remove_ai_row).pack(side="left")
        ttk.Button(
            bottom,
            text="Confirmar e importar para o Perfil SPT",
            command=self._confirm_ai_import,
        ).pack(side="left", padx=12)

    def _select_ai_pdf(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if not path:
            return
        self.ai_pdf_path = path
        self.label_ai_pdf.config(text=path)

    def _run_ai_extraction(self) -> None:
        if not self.ai_pdf_path:
            messagebox.showinfo("Selecione um PDF", "Selecione o arquivo PDF do laudo SPT primeiro.")
            return

        self.button_ai_run.config(state="disabled")
        self.label_ai_status.config(text="Processando com IA... isso pode levar até 1 minuto.", foreground="#1a6fd6")

        def worker() -> None:
            try:
                from .ai_extraction import extract_spt_report

                result = extract_spt_report(self.ai_pdf_path)
            except AIExtractionError as exc:
                self.after(0, lambda: self._on_ai_extraction_error(str(exc)))
                return
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: self._on_ai_extraction_error(f"Erro inesperado: {exc}"))
                return
            self.after(0, lambda: self._on_ai_extraction_done(result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_extraction_error(self, message: str) -> None:
        self.button_ai_run.config(state="normal")
        self.label_ai_status.config(text="", foreground="black")
        messagebox.showerror("Erro na interpretação por IA", message)

    def _on_ai_extraction_done(self, result: ExtractedSPTReport) -> None:
        self.button_ai_run.config(state="normal")
        self.label_ai_status.config(
            text=f"{len(result.readings)} leituras extraídas. Revise cuidadosamente antes de importar.",
            foreground="#0a6e0a",
        )
        self.ai_extraction_result = result
        self.ai_review_rows = list(result.readings)
        if result.water_table_found and result.water_table_depth_m is not None:
            self.label_ai_water.config(text=f"{result.water_table_depth_m:.2f} m")
        elif result.water_table_found:
            self.label_ai_water.config(text="identificado, profundidade não especificada")
        else:
            self.label_ai_water.config(text="não identificado / seco")
        self._refresh_ai_tree()

    def _refresh_ai_tree(self) -> None:
        self.tree_ai.delete(*self.tree_ai.get_children())
        for i, r in enumerate(self.ai_review_rows):
            self.tree_ai.insert(
                "",
                "end",
                iid=str(i),
                values=(f"{r.depth_m:.2f}", r.n_spt, get_soil(r.soil_key).label, r.soil_description_original),
            )

    def _on_ai_row_select(self, _event=None) -> None:
        selected = self.tree_ai.selection()
        if not selected:
            return
        idx = int(selected[0])
        row = self.ai_review_rows[idx]
        self.entry_ai_edit_depth.delete(0, tk.END)
        self.entry_ai_edit_depth.insert(0, f"{row.depth_m:.2f}")
        self.entry_ai_edit_nspt.delete(0, tk.END)
        self.entry_ai_edit_nspt.insert(0, str(row.n_spt))
        self.combo_ai_edit_soil.set(get_soil(row.soil_key).label)

    def _apply_ai_row_edit(self) -> None:
        selected = self.tree_ai.selection()
        if not selected:
            messagebox.showinfo("Nenhuma linha selecionada", "Selecione uma linha na tabela para editar.")
            return
        idx = int(selected[0])
        try:
            depth = float(self.entry_ai_edit_depth.get().replace(",", "."))
            n_spt = int(float(self.entry_ai_edit_nspt.get().replace(",", ".")))
            soil_label = self.combo_ai_edit_soil.get()
            soil_key = self._soil_key_by_label[soil_label]
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Entrada inválida", str(exc))
            return
        original = self.ai_review_rows[idx].soil_description_original
        self.ai_review_rows[idx] = ExtractedReading(depth, n_spt, soil_key, original)
        self._refresh_ai_tree()

    def _remove_ai_row(self) -> None:
        selected = self.tree_ai.selection()
        if not selected:
            return
        idx_to_remove = {int(i) for i in selected}
        self.ai_review_rows = [r for i, r in enumerate(self.ai_review_rows) if i not in idx_to_remove]
        self._refresh_ai_tree()

    def _confirm_ai_import(self) -> None:
        if not self.ai_review_rows:
            messagebox.showinfo("Nada para importar", "Interprete um laudo e revise as linhas extraídas primeiro.")
            return
        if self.profile.points:
            if not messagebox.askyesno(
                "Substituir perfil atual?",
                "Isso vai substituir o perfil de SPT atual (aba 1) pelos dados revisados da IA. Continuar?",
            ):
                return
        new_profile = SPTProfile()
        for r in self.ai_review_rows:
            new_profile.add(r.depth_m, r.n_spt, r.soil_key)
        self.profile = new_profile
        self._refresh_profile_tree()

        if self.ai_extraction_result is not None and self.ai_extraction_result.water_table_found:
            self.entry_water_table.delete(0, tk.END)
            if self.ai_extraction_result.water_table_depth_m is not None:
                self.entry_water_table.insert(0, f"{self.ai_extraction_result.water_table_depth_m:.2f}")

        messagebox.showinfo(
            "Perfil importado",
            "Perfil de SPT atualizado com os dados revisados da IA. Confira a aba 1 antes de calcular.",
        )

    # -- Tab 3: Estaca e carga ---------------------------------------------
    def _build_tab_pile(self) -> None:
        frame = self.tab_pile
        grid = ttk.Frame(frame)
        grid.pack(fill="x", padx=12, pady=12)

        r = 0
        ttk.Label(grid, text="Tipo de estaca:").grid(row=r, column=0, sticky="w", pady=4)
        self.combo_pile_type = ttk.Combobox(
            grid, values=list(PILE_TYPES.values()), state="readonly", width=28
        )
        self.combo_pile_type.current(0)
        self.combo_pile_type.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Diâmetro da estaca (cm):").grid(row=r, column=0, sticky="w", pady=4)
        self.entry_diameter = ttk.Entry(grid, width=10)
        self.entry_diameter.insert(0, "40")
        self.entry_diameter.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Carga de projeto (kN):").grid(row=r, column=0, sticky="w", pady=4)
        self.entry_load = ttk.Entry(grid, width=10)
        self.entry_load.insert(0, "500")
        self.entry_load.grid(row=r, column=1, sticky="w")
        ttk.Label(grid, text="(1 tf ≈ 10 kN)").grid(row=r, column=2, sticky="w")
        r += 1

        ttk.Label(grid, text="Fator de segurança global:").grid(row=r, column=0, sticky="w", pady=4)
        self.entry_fs = ttk.Entry(grid, width=10)
        self.entry_fs.insert(0, "2.0")
        self.entry_fs.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Profundidade mínima de embutimento (m):").grid(row=r, column=0, sticky="w", pady=4)
        self.entry_min_depth = ttk.Entry(grid, width=10)
        self.entry_min_depth.insert(0, "1.0")
        self.entry_min_depth.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Método de cálculo:").grid(row=r, column=0, sticky="w", pady=4)
        self.combo_method = ttk.Combobox(
            grid, values=list(METHOD_LABELS.values()), state="readonly", width=32
        )
        self.combo_method.current(2)
        self.combo_method.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Button(grid, text="Calcular profundidade necessária", command=self._calculate).grid(
            row=r, column=0, columnspan=2, pady=12
        )

    def _selected_pile_type_key(self) -> str:
        label = self.combo_pile_type.get()
        for key, value in PILE_TYPES.items():
            if value == label:
                return key
        raise ValueError("Tipo de estaca inválido.")

    def _selected_method_key(self) -> str:
        label = self.combo_method.get()
        for key, value in METHOD_LABELS.items():
            if value == label:
                return key
        raise ValueError("Método inválido.")

    # -- Tab 3: Resultados ---------------------------------------------------
    def _build_tab_results(self) -> None:
        frame = self.tab_results

        self.label_summary = ttk.Label(frame, text="Execute o cálculo na aba 2.", font=("TkDefaultFont", 11, "bold"))
        self.label_summary.pack(fill="x", padx=8, pady=8)

        columns = ("depth", "qadm_dq", "qadm_av", "qadm_gov")
        self.tree_results = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        self.tree_results.heading("depth", text="Profundidade (m)")
        self.tree_results.heading("qadm_dq", text="Qadm Décourt-Quaresma (kN)")
        self.tree_results.heading("qadm_av", text="Qadm Aoki-Velloso (kN)")
        self.tree_results.heading("qadm_gov", text="Qadm governante (kN)")
        for c in columns:
            self.tree_results.column(c, width=170, anchor="center")
        self.tree_results.pack(fill="both", expand=True, padx=8, pady=4)

        self.canvas_chart = tk.Canvas(frame, height=180, background="white")
        self.canvas_chart.pack(fill="x", padx=8, pady=8)

        export_frame = ttk.Frame(frame)
        export_frame.pack(fill="x", padx=8, pady=6)
        ttk.Button(export_frame, text="Exportar relatório resumido (.txt)", command=self._export_report).pack(
            side="left"
        )
        ttk.Button(
            export_frame,
            text="Gerar memorial de cálculo completo (.docx)",
            command=self._export_memorial,
        ).pack(side="left", padx=12)

    def _build_tab_reinforcement(self) -> None:
        frame = self.tab_reinforcement
        grid = ttk.Frame(frame)
        grid.pack(fill="x", padx=12, pady=12)

        r = 0
        ttk.Label(
            grid, text="Cobrimento (cm) [mín. NBR 6122:2022: 5cm classe II, 7cm classes III/IV]:"
        ).grid(row=r, column=0, sticky="w", pady=4)
        self.entry_cover = ttk.Entry(grid, width=10)
        self.entry_cover.insert(0, "5.0")
        self.entry_cover.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Taxa mínima de armadura (%) [vazio = padrão]:").grid(
            row=r, column=0, sticky="w", pady=4
        )
        self.entry_rho_min = ttk.Entry(grid, width=10)
        self.entry_rho_min.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Bitola do estribo (mm):").grid(row=r, column=0, sticky="w", pady=4)
        self.combo_stirrup = ttk.Combobox(
            grid, values=[str(v) for v in STIRRUP_DIAMETERS_MM], state="readonly", width=10
        )
        self.combo_stirrup.current(1)
        self.combo_stirrup.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Espaçamento estribo no fuste (cm):").grid(row=r, column=0, sticky="w", pady=4)
        self.entry_stirrup_body = ttk.Entry(grid, width=10)
        self.entry_stirrup_body.insert(0, "15")
        self.entry_stirrup_body.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Espaçamento estribo na zona de confinamento (cm):").grid(
            row=r, column=0, sticky="w", pady=4
        )
        self.entry_stirrup_top = ttk.Entry(grid, width=10)
        self.entry_stirrup_top.insert(0, "10")
        self.entry_stirrup_top.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Profundidade de armação (m) [vazio = toda a extensão da estaca]:").grid(
            row=r, column=0, sticky="w", pady=4
        )
        self.entry_armor_length = ttk.Entry(grid, width=10)
        self.entry_armor_length.grid(row=r, column=1, sticky="w")
        ttk.Label(
            grid,
            text="(armadura parcial só vale para estacas só à compressão axial - confirme com o eng. responsável)",
            foreground="#7a4a00",
        ).grid(row=r, column=2, sticky="w", padx=6)
        r += 1

        ttk.Separator(grid, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", pady=8)
        r += 1
        ttk.Label(
            grid,
            text=(
                "Dimensionamento estrutural (opcional): informe o momento para substituir a "
                "armadura mínima por um dimensionamento real de flexo-compressão (N-M) e "
                "cisalhamento (V). Use sempre valores CARACTERÍSTICOS (não majorados)."
            ),
            wraplength=650, justify="left", foreground="#7a4a00",
        ).grid(row=r, column=0, columnspan=3, sticky="w", pady=(0, 4))
        r += 1

        ttk.Label(grid, text="Momento característico Mk (kN·m) [opcional]:").grid(row=r, column=0, sticky="w", pady=4)
        self.entry_moment = ttk.Entry(grid, width=10)
        self.entry_moment.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="  ...ou componentes Mx, My (kN·m):").grid(row=r, column=0, sticky="w")
        mxy_frame = ttk.Frame(grid)
        mxy_frame.grid(row=r, column=1, columnspan=2, sticky="w")
        self.entry_moment_x = ttk.Entry(mxy_frame, width=8)
        self.entry_moment_x.pack(side="left", padx=2)
        self.entry_moment_y = ttk.Entry(mxy_frame, width=8)
        self.entry_moment_y.pack(side="left", padx=2)
        ttk.Button(
            mxy_frame, text="Calcular Mk = √(Mx²+My²)", command=self._compute_moment_resultant
        ).pack(side="left", padx=6)
        r += 1

        ttk.Label(grid, text="Cortante característico Hk (kN) [opcional]:").grid(row=r, column=0, sticky="w", pady=4)
        self.entry_shear = ttk.Entry(grid, width=10)
        self.entry_shear.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="  ...ou componentes Hx, Hy (kN):").grid(row=r, column=0, sticky="w")
        hxy_frame = ttk.Frame(grid)
        hxy_frame.grid(row=r, column=1, columnspan=2, sticky="w")
        self.entry_shear_x = ttk.Entry(hxy_frame, width=8)
        self.entry_shear_x.pack(side="left", padx=2)
        self.entry_shear_y = ttk.Entry(hxy_frame, width=8)
        self.entry_shear_y.pack(side="left", padx=2)
        ttk.Button(
            hxy_frame, text="Calcular Hk = √(Hx²+Hy²)", command=self._compute_shear_resultant
        ).pack(side="left", padx=6)
        r += 1

        ttk.Label(
            grid, text="fck do concreto (MPa) [mín. NBR 6122:2022: 30 classe I/II, 40 classes III/IV]:"
        ).grid(row=r, column=0, sticky="w", pady=4)
        self.entry_fck = ttk.Entry(grid, width=10)
        self.entry_fck.insert(0, "30")
        self.entry_fck.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="fyk do aço (MPa):").grid(row=r, column=0, sticky="w", pady=4)
        self.entry_fyk = ttk.Entry(grid, width=10)
        self.entry_fyk.insert(0, "500")
        self.entry_fyk.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Fator de majoração γf (Nk/Mk/Hk -> Nd/Md/Vd):").grid(row=r, column=0, sticky="w", pady=4)
        self.entry_load_factor = ttk.Entry(grid, width=10)
        self.entry_load_factor.insert(0, "1.4")
        self.entry_load_factor.grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(
            grid, text="Coef. de ponderação do concreto γc (estacas, NBR 6122:2022 8.6.3):"
        ).grid(row=r, column=0, sticky="w", pady=4)
        self.entry_gamma_c = ttk.Entry(grid, width=10)
        self.entry_gamma_c.insert(0, str(GAMMA_C_CONCRETE_PILE))
        self.entry_gamma_c.grid(row=r, column=1, sticky="w")
        ttk.Label(
            grid,
            text="  padrão conservador p/ moldada in loco; use 1.4 para pré-moldada c/ controle de fábrica",
            foreground="#666666",
        ).grid(row=r, column=2, sticky="w", padx=6)
        r += 1

        ttk.Button(grid, text="Calcular armação", command=self._calculate_reinforcement).grid(
            row=r, column=0, columnspan=2, pady=12
        )

        self.text_reinforcement = tk.Text(frame, height=14, wrap="word")
        self.text_reinforcement.pack(fill="both", expand=True, padx=12, pady=8)

    # ------------------------------------------------------------- ações
    def _calculate(self) -> None:
        try:
            if not self.profile.is_valid():
                raise ValueError("Adicione ao menos 2 leituras de SPT na aba 1.")
            diameter_cm = float(self.entry_diameter.get().replace(",", "."))
            load_kn = float(self.entry_load.get().replace(",", "."))
            fs = float(self.entry_fs.get().replace(",", "."))
            min_depth = float(self.entry_min_depth.get().replace(",", "."))
            pile_type = self._selected_pile_type_key()
            method = self._selected_method_key()

            geometry = PileGeometry(diameter_cm=diameter_cm)
            result = ds.solve(
                self.profile, geometry, pile_type, load_kn, method=method, safety_factor=fs, min_depth_m=min_depth
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro no cálculo", str(exc))
            return

        self.solver_result = result
        self._geometry = PileGeometry(diameter_cm=diameter_cm)
        self._pile_type = pile_type
        self._fs = fs
        self._refresh_results()

    def _refresh_results(self) -> None:
        result = self.solver_result
        self.tree_results.delete(*self.tree_results.get_children())
        if result is None:
            return
        for row in result.rows:
            dq_txt = f"{row.qadm_dq_kn:.1f}" if row.qadm_dq_kn is not None else "-"
            av_txt = f"{row.qadm_av_kn:.1f}" if row.qadm_av_kn is not None else "-"
            self.tree_results.insert(
                "", "end", values=(f"{row.depth_m:.2f}", dq_txt, av_txt, f"{row.qadm_governing_kn:.1f}")
            )

        if result.required_depth_m is not None:
            self.label_summary.config(
                text=(
                    f"Profundidade mínima necessária: {result.required_depth_m:.2f} m "
                    f"para Qadm ≥ {result.load_kn:.1f} kN"
                ),
                foreground="#0a6e0a",
            )
        else:
            self.label_summary.config(
                text="A carga de projeto não é atingida dentro da profundidade sondada.",
                foreground="#b00020",
            )
        self._draw_chart()

    def _draw_chart(self) -> None:
        canvas = self.canvas_chart
        canvas.delete("all")
        result = self.solver_result
        if result is None or not result.rows:
            return

        width = int(canvas.winfo_width() or 760)
        height = int(canvas.winfo_height() or 180)
        margin = 40

        depths = [r.depth_m for r in result.rows]
        qadms = [r.qadm_governing_kn for r in result.rows]
        max_depth = max(depths)
        max_q = max(max(qadms), result.load_kn) * 1.1 or 1.0

        def x_for(q: float) -> float:
            return margin + (q / max_q) * (width - 2 * margin)

        def y_for(depth: float) -> float:
            return margin + (depth / max_depth) * (height - 2 * margin) if max_depth else margin

        canvas.create_line(margin, margin, margin, height - margin)
        canvas.create_line(margin, height - margin, width - margin, height - margin)
        canvas.create_text(margin, margin - 10, text="Qadm (kN) x Profundidade (m)", anchor="w")

        points = []
        for depth, qadm in zip(depths, qadms):
            points.extend([x_for(qadm), y_for(depth)])
        if len(points) >= 4:
            canvas.create_line(*points, fill="#1a6fd6", width=2)

        load_x = x_for(result.load_kn)
        canvas.create_line(load_x, margin, load_x, height - margin, fill="#c62828", dash=(4, 2))
        canvas.create_text(load_x, margin - 10, text="carga projeto", fill="#c62828", anchor="w")

        if result.required_depth_m is not None:
            req_y = y_for(result.required_depth_m)
            canvas.create_line(margin, req_y, width - margin, req_y, fill="#2e7d32", dash=(2, 2))

    @staticmethod
    def _resultant_from_entries(entry_x: ttk.Entry, entry_y: ttk.Entry) -> float | None:
        x_txt = entry_x.get().strip()
        y_txt = entry_y.get().strip()
        if not x_txt and not y_txt:
            return None
        x_val = float(x_txt.replace(",", ".")) if x_txt else 0.0
        y_val = float(y_txt.replace(",", ".")) if y_txt else 0.0
        return math.hypot(x_val, y_val)

    def _compute_moment_resultant(self) -> None:
        try:
            resultant = self._resultant_from_entries(self.entry_moment_x, self.entry_moment_y)
        except ValueError as exc:
            messagebox.showerror("Entrada inválida", str(exc))
            return
        if resultant is None:
            messagebox.showinfo("Componentes vazios", "Preencha Mx e/ou My para calcular a resultante.")
            return
        self.entry_moment.delete(0, tk.END)
        self.entry_moment.insert(0, f"{resultant:.3f}")

    def _compute_shear_resultant(self) -> None:
        try:
            resultant = self._resultant_from_entries(self.entry_shear_x, self.entry_shear_y)
        except ValueError as exc:
            messagebox.showerror("Entrada inválida", str(exc))
            return
        if resultant is None:
            messagebox.showinfo("Componentes vazios", "Preencha Hx e/ou Hy para calcular a resultante.")
            return
        self.entry_shear.delete(0, tk.END)
        self.entry_shear.insert(0, f"{resultant:.3f}")

    def _calculate_reinforcement(self) -> None:
        if self.solver_result is None or getattr(self, "_geometry", None) is None:
            messagebox.showinfo("Calcule primeiro", "Calcule a profundidade necessária na aba 2/3 antes de dimensionar a armação.")
            return
        try:
            cover = float(self.entry_cover.get().replace(",", "."))
            rho_txt = self.entry_rho_min.get().strip()
            rho_min = float(rho_txt.replace(",", ".")) if rho_txt else None
            stirrup_d = float(self.combo_stirrup.get())
            spacing_body = float(self.entry_stirrup_body.get().replace(",", "."))
            spacing_top = float(self.entry_stirrup_top.get().replace(",", "."))
            armor_txt = self.entry_armor_length.get().strip()
            armor_length = float(armor_txt.replace(",", ".")) if armor_txt else None
            moment_txt = self.entry_moment.get().strip()
            moment_kn_m = float(moment_txt.replace(",", ".")) if moment_txt else None
            shear_txt = self.entry_shear.get().strip()
            shear_kn = float(shear_txt.replace(",", ".")) if shear_txt else None
            fck = float(self.entry_fck.get().replace(",", "."))
            fyk = float(self.entry_fyk.get().replace(",", "."))
            load_factor = float(self.entry_load_factor.get().replace(",", "."))
            gamma_c = float(self.entry_gamma_c.get().replace(",", "."))

            result = design_reinforcement(
                self._geometry,
                axial_load_kn=self.solver_result.load_kn,
                cover_cm=cover,
                rho_min_pct=rho_min,
                stirrup_diameter_mm=stirrup_d,
                stirrup_spacing_body_cm=spacing_body,
                stirrup_spacing_top_cm=spacing_top,
                armor_length_m=armor_length,
                moment_kn_m=moment_kn_m,
                shear_kn=shear_kn,
                load_factor=load_factor,
                fck_mpa=fck,
                fyk_mpa=fyk,
                gamma_c=gamma_c,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro no cálculo de armação", str(exc))
            return

        self.reinforcement_result = result
        pile_depth = self.solver_result.required_depth_m if self.solver_result else None
        self._render_reinforcement(result, pile_depth_m=pile_depth)

    def _render_reinforcement(self, result, pile_depth_m: float | None = None) -> None:
        self.text_reinforcement.delete("1.0", tk.END)
        lines = [
            f"Diâmetro da estaca: {result.diameter_cm:.1f} cm",
            f"Área bruta: {result.gross_area_cm2:.1f} cm²",
            f"Taxa mínima adotada: {result.rho_min_pct:.2f} %  (referência: {default_rho_min_pct(result.diameter_cm):.2f} %)",
            f"Área de aço mínima (As,min): {result.as_min_cm2:.2f} cm²",
            "",
        ]
        if result.longitudinal:
            lg = result.longitudinal
            lines.append(
                f"Armadura longitudinal sugerida: {lg.n_bars} barras de φ{lg.bar_diameter_mm:.1f} mm"
            )
            lines.append(f"As fornecido: {lg.as_provided_cm2:.2f} cm²  (>= As,min: OK)")
            lines.append(f"Espaçamento livre estimado entre barras: {lg.clear_spacing_cm:.1f} cm")
        else:
            lines.append("Não foi encontrada combinação padrão viável de barras - ver avisos abaixo.")

        if result.structural is not None:
            s = result.structural
            lines.append("")
            lines.append(
                f"--- Dimensionamento estrutural (γf={s.load_factor:.2f}, γc={s.gamma_c:.2f}, "
                f"fck={s.fck_mpa:.0f} MPa, fyk={s.fyk_mpa:.0f} MPa) ---"
            )
            fc = s.flexo_check
            if fc is not None and fc.m_capacity_knm is not None:
                status = "OK" if fc.adequate else "INSUFICIENTE"
                lines.append(
                    f"Flexo-compressão: Nd={fc.n_design_kn:.1f} kN, Md={fc.m_design_knm:.1f} kN·m, "
                    f"Mrd={fc.m_capacity_knm:.1f} kN·m, utilização={fc.utilization * 100:.0f}% [{status}]"
                )
            elif fc is not None:
                lines.append(
                    f"Flexo-compressão: Nd={fc.n_design_kn:.1f} kN excede a capacidade última à "
                    "compressão da seção testada [INSUFICIENTE]"
                )
            if s.shear is not None:
                sh = s.shear
                crush_status = "OK" if sh.crushing_ok else "FALHA (esmagamento da biela)"
                lines.append(
                    f"Cisalhamento: Vd={sh.v_design_kn:.1f} kN, Vrd2={sh.vrd2_kn:.1f} kN [{crush_status}], "
                    f"Vc={sh.vc_kn:.1f} kN"
                    + (f", espaçamento necessário dos estribos={sh.required_spacing_cm:.1f} cm" if sh.required_spacing_cm else "")
                )
        lines.append("")
        lines.append(
            f"Estribos: φ{result.stirrup_diameter_mm:.1f} mm a cada {result.stirrup_spacing_body_cm:.0f} cm "
            f"no corpo da estaca"
        )
        lines.append(
            f"Zona de confinamento (primeiros {result.confinement_length_m:.2f} m a partir do topo): "
            f"estribos a cada {result.stirrup_spacing_top_cm:.0f} cm"
        )
        lines.append("")
        if result.requested_armor_length_m is None:
            lines.append("Comprimento de armadura: toda a extensão da estaca (armadura corrida).")
        else:
            lines.append(
                f"Comprimento de armadura solicitado: {result.requested_armor_length_m:.2f} m a partir do "
                f"topo (limitado à profundidade real de cada estaca, se ela for menor que esse valor)."
            )
        if pile_depth_m is not None:
            from .reinforcement import effective_armor_length_m

            eff = effective_armor_length_m(result, pile_depth_m)
            lines.append(
                f"Nesta estaca (profundidade adotada = {pile_depth_m:.2f} m): comprimento efetivo de "
                f"armadura = {eff:.2f} m."
            )
        for w in result.warnings:
            lines.append(f"\nAVISO: {w}")

        self.text_reinforcement.insert("1.0", "\n".join(lines))

    def _export_report(self) -> None:
        if self.solver_result is None:
            messagebox.showinfo("Nada para exportar", "Calcule a profundidade necessária primeiro.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Texto", "*.txt")])
        if not path:
            return
        text = report_mod.build_report(
            self.profile,
            self._geometry,
            self._pile_type,
            self.solver_result,
            self.reinforcement_result,
            self._fs,
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        messagebox.showinfo("Relatório salvo", f"Relatório salvo em:\n{path}")

    def _export_memorial(self) -> None:
        if self.solver_result is None:
            messagebox.showinfo("Nada para exportar", "Calcule a profundidade necessária primeiro.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("Word", "*.docx")])
        if not path:
            return
        try:
            from .memorial import build_memorial
        except ImportError as exc:
            messagebox.showerror(
                "Dependência ausente",
                f"Biblioteca 'python-docx' não está instalada. Rode: pip install python-docx\n\n{exc}",
            )
            return

        water_found, water_depth = self._get_water_table()
        try:
            build_memorial(
                path,
                self.profile,
                self._geometry,
                self._pile_type,
                self.solver_result,
                self.reinforcement_result,
                self._fs,
                water_table_depth_m=water_depth,
                water_table_found=water_found,
                ai_extraction=self.ai_extraction_result,
            )
        except ImportError as exc:
            messagebox.showerror(
                "Dependência ausente",
                f"Biblioteca 'python-docx' não está instalada. Rode: pip install python-docx\n\n{exc}",
            )
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao gerar memorial", str(exc))
            return
        messagebox.showinfo("Memorial gerado", f"Memorial de cálculo salvo em:\n{path}")

    # -- Tab 6: Esforços e Uniformização ------------------------------------
    def _build_tab_loads(self) -> None:
        frame = self.tab_loads

        info = ttk.Label(
            frame,
            text=(
                "Importe os esforços (cargas) de fundação por pilar/bloco/estaca vindos do "
                "seu software de dimensionamento estrutural. Use a carga CARACTERÍSTICA (de "
                "serviço, Nk) - nunca a carga majorada (ELU/Nd). Quando um bloco tiver mais de "
                "uma estaca, a carga é dividida igualmente entre elas."
            ),
            wraplength=900,
            justify="left",
            foreground="#7a4a00",
        )
        info.pack(fill="x", padx=8, pady=8)

        form = ttk.Frame(frame)
        form.pack(fill="x", padx=8, pady=4)
        ttk.Label(form, text="Elemento (pilar/bloco):").grid(row=0, column=0, sticky="w")
        self.entry_load_id = ttk.Entry(form, width=12)
        self.entry_load_id.grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Carga característica (kN):").grid(row=0, column=2, sticky="w")
        self.entry_load_value = ttk.Entry(form, width=10)
        self.entry_load_value.grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Nº de estacas no bloco:").grid(row=0, column=4, sticky="w")
        self.entry_load_npiles = ttk.Entry(form, width=6)
        self.entry_load_npiles.insert(0, "1")
        self.entry_load_npiles.grid(row=0, column=5, padx=4)

        ttk.Label(form, text="Momento Mk (kN·m) [opcional]:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.entry_load_moment = ttk.Entry(form, width=10)
        self.entry_load_moment.grid(row=1, column=1, padx=4, pady=(4, 0))
        ttk.Label(form, text="Cortante Hk (kN) [opcional]:").grid(row=1, column=2, sticky="w", pady=(4, 0))
        self.entry_load_shear = ttk.Entry(form, width=10)
        self.entry_load_shear.grid(row=1, column=3, padx=4, pady=(4, 0))
        ttk.Button(form, text="Adicionar", command=self._add_load_row).grid(row=1, column=5, padx=6, pady=(4, 0))

        ttk.Label(form, text="  ...ou Mx, My (kN·m):").grid(row=2, column=0, sticky="w", pady=(4, 0))
        load_mxy_frame = ttk.Frame(form)
        load_mxy_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=(4, 0))
        self.entry_load_moment_x = ttk.Entry(load_mxy_frame, width=8)
        self.entry_load_moment_x.pack(side="left", padx=2)
        self.entry_load_moment_y = ttk.Entry(load_mxy_frame, width=8)
        self.entry_load_moment_y.pack(side="left", padx=2)
        ttk.Label(form, text="  ...ou Hx, Hy (kN):").grid(row=2, column=3, sticky="w", pady=(4, 0))
        load_hxy_frame = ttk.Frame(form)
        load_hxy_frame.grid(row=2, column=4, columnspan=2, sticky="w", pady=(4, 0))
        self.entry_load_shear_x = ttk.Entry(load_hxy_frame, width=8)
        self.entry_load_shear_x.pack(side="left", padx=2)
        self.entry_load_shear_y = ttk.Entry(load_hxy_frame, width=8)
        self.entry_load_shear_y.pack(side="left", padx=2)
        ttk.Label(
            form,
            text="(preencha Mx/My e/ou Hx/Hy para combinar automaticamente ao clicar Adicionar - ignora Mk/Hk diretos acima, se preenchidos)",
            foreground="#7a4a00", wraplength=750, justify="left",
        ).grid(row=3, column=0, columnspan=6, sticky="w", pady=(2, 0))

        columns = ("id", "load", "npiles", "per_pile", "moment", "moment_xy", "shear", "shear_xy")
        self.tree_loads = ttk.Treeview(frame, columns=columns, show="headings", height=8)
        self.tree_loads.heading("id", text="Elemento")
        self.tree_loads.heading("load", text="Carga característica (kN)")
        self.tree_loads.heading("npiles", text="Nº estacas no bloco")
        self.tree_loads.heading("per_pile", text="Carga por estaca (kN)")
        self.tree_loads.heading("moment", text="Mk (kN·m)")
        self.tree_loads.heading("moment_xy", text="Mx / My (kN·m)")
        self.tree_loads.heading("shear", text="Hk (kN)")
        self.tree_loads.heading("shear_xy", text="Hx / Hy (kN)")
        for c in columns:
            self.tree_loads.column(c, width=115, anchor="center")
        self.tree_loads.pack(fill="both", expand=True, padx=8, pady=4)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", padx=8, pady=4)
        ttk.Button(buttons, text="Remover selecionada", command=self._remove_load_row).pack(side="left")
        ttk.Button(buttons, text="Limpar tudo", command=self._clear_loads).pack(side="left", padx=6)
        ttk.Button(buttons, text="Carregar CSV...", command=self._load_loads_csv).pack(side="left", padx=6)
        ttk.Button(buttons, text="Salvar CSV...", command=self._save_loads_csv).pack(side="left", padx=6)
        ttk.Button(buttons, text="Importar PDF via IA...", command=self._select_ai_loads_pdf).pack(side="left", padx=12)
        self.button_ai_loads_run = ttk.Button(buttons, text="Interpretar com IA", command=self._run_ai_loads_extraction)
        self.button_ai_loads_run.pack(side="left", padx=6)
        self.label_ai_loads_pdf = ttk.Label(frame, text="Nenhum PDF selecionado.")
        self.label_ai_loads_pdf.pack(fill="x", padx=8)
        self.label_ai_loads_status = ttk.Label(frame, text="")
        self.label_ai_loads_status.pack(fill="x", padx=8)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=8, pady=8)

        calc_form = ttk.Frame(frame)
        calc_form.pack(fill="x", padx=8, pady=4)
        ttk.Label(calc_form, text="Uniformizar profundidades?").grid(row=0, column=0, sticky="w")
        self.combo_uniformize = ttk.Combobox(calc_form, values=["Não", "Sim"], state="readonly", width=8)
        self.combo_uniformize.current(0)
        self.combo_uniformize.grid(row=0, column=1, padx=4)
        ttk.Label(calc_form, text="Nº de grupos/profundidades padrão:").grid(row=0, column=2, sticky="w")
        self.entry_n_groups = ttk.Entry(calc_form, width=6)
        self.entry_n_groups.insert(0, "3")
        self.entry_n_groups.grid(row=0, column=3, padx=4)
        ttk.Button(calc_form, text="Calcular profundidade de todas as estacas", command=self._calculate_batch).grid(
            row=0, column=4, padx=12
        )

        self.label_batch_summary = ttk.Label(frame, text="", font=("TkDefaultFont", 10, "bold"))
        self.label_batch_summary.pack(fill="x", padx=8, pady=4)

        columns2 = ("id", "per_pile", "individual", "group", "adopted", "armor")
        self.tree_batch = ttk.Treeview(frame, columns=columns2, show="headings", height=10)
        self.tree_batch.heading("id", text="Elemento")
        self.tree_batch.heading("per_pile", text="Carga/estaca (kN)")
        self.tree_batch.heading("individual", text="Prof. individual (m)")
        self.tree_batch.heading("group", text="Grupo")
        self.tree_batch.heading("adopted", text="Prof. adotada (m)")
        self.tree_batch.heading("armor", text="Compr. armadura (m)")
        for c in columns2:
            self.tree_batch.column(c, width=170, anchor="center")
        self.tree_batch.pack(fill="both", expand=True, padx=8, pady=4)

        ttk.Button(
            frame, text="Gerar memorial de cálculo em lote (.docx)", command=self._export_batch_memorial
        ).pack(padx=8, pady=8, anchor="w")

    def _add_load_row(self) -> None:
        try:
            element_id = self.entry_load_id.get().strip()
            load_kn = float(self.entry_load_value.get().replace(",", "."))
            n_piles = int(float(self.entry_load_npiles.get().replace(",", ".")))
            mx_txt = self.entry_load_moment_x.get().strip()
            moment_x_knm = float(mx_txt.replace(",", ".")) if mx_txt else None
            my_txt = self.entry_load_moment_y.get().strip()
            moment_y_knm = float(my_txt.replace(",", ".")) if my_txt else None
            moment_resultant = self._resultant_from_entries(self.entry_load_moment_x, self.entry_load_moment_y)
            if moment_resultant is not None:
                moment_kn_m = moment_resultant
            else:
                moment_txt = self.entry_load_moment.get().strip()
                moment_kn_m = float(moment_txt.replace(",", ".")) if moment_txt else None

            hx_txt = self.entry_load_shear_x.get().strip()
            shear_x_kn = float(hx_txt.replace(",", ".")) if hx_txt else None
            hy_txt = self.entry_load_shear_y.get().strip()
            shear_y_kn = float(hy_txt.replace(",", ".")) if hy_txt else None
            shear_resultant = self._resultant_from_entries(self.entry_load_shear_x, self.entry_load_shear_y)
            if shear_resultant is not None:
                shear_kn = shear_resultant
            else:
                shear_txt = self.entry_load_shear.get().strip()
                shear_kn = float(shear_txt.replace(",", ".")) if shear_txt else None

            self.load_set.add(
                element_id, load_kn, n_piles, moment_kn_m, shear_kn,
                moment_x_knm, moment_y_knm, shear_x_kn, shear_y_kn,
            )
        except ValueError as exc:
            messagebox.showerror("Entrada inválida", str(exc))
            return
        self._refresh_loads_tree()
        self.entry_load_id.delete(0, tk.END)
        self.entry_load_value.delete(0, tk.END)
        self.entry_load_npiles.delete(0, tk.END)
        self.entry_load_npiles.insert(0, "1")
        self.entry_load_moment.delete(0, tk.END)
        self.entry_load_shear.delete(0, tk.END)
        self.entry_load_moment_x.delete(0, tk.END)
        self.entry_load_moment_y.delete(0, tk.END)
        self.entry_load_shear_x.delete(0, tk.END)
        self.entry_load_shear_y.delete(0, tk.END)

    def _remove_load_row(self) -> None:
        selected = self.tree_loads.selection()
        if not selected:
            return
        ids_to_remove = {self.tree_loads.item(i, "values")[0] for i in selected}
        kept = []
        removed_once = {k: False for k in ids_to_remove}
        for item in self.load_set.items:
            key = item.element_id
            if key in ids_to_remove and not removed_once[key]:
                removed_once[key] = True
                continue
            kept.append(item)
        self.load_set.items = kept
        self._refresh_loads_tree()

    def _clear_loads(self) -> None:
        self.load_set.clear()
        self._refresh_loads_tree()

    def _refresh_loads_tree(self) -> None:
        self.tree_loads.delete(*self.tree_loads.get_children())
        for item in self.load_set.items:
            moment_txt = f"{item.moment_kn_m:.1f}" if item.moment_kn_m is not None else "-"
            shear_txt = f"{item.shear_kn:.1f}" if item.shear_kn is not None else "-"
            if item.moment_x_knm is not None or item.moment_y_knm is not None:
                moment_xy_txt = f"{item.moment_x_knm or 0:.1f} / {item.moment_y_knm or 0:.1f}"
            else:
                moment_xy_txt = "-"
            if item.shear_x_kn is not None or item.shear_y_kn is not None:
                shear_xy_txt = f"{item.shear_x_kn or 0:.1f} / {item.shear_y_kn or 0:.1f}"
            else:
                shear_xy_txt = "-"
            self.tree_loads.insert(
                "",
                "end",
                values=(
                    item.element_id, f"{item.characteristic_load_kn:.1f}", item.n_piles,
                    f"{item.load_per_pile_kn:.1f}", moment_txt, moment_xy_txt, shear_txt, shear_xy_txt,
                ),
            )

    def _load_loads_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if not path:
            return
        try:
            new_loads = LoadSet()
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
            start = 1 if rows and not rows[0][1].replace(".", "", 1).replace(",", "", 1).isdigit() else 0
            for row in rows[start:]:
                if not row:
                    continue

                def _cell(index: int) -> str:
                    return row[index].strip() if len(row) > index else ""

                element_id = row[0].strip()
                load_kn = float(row[1].replace(",", "."))
                n_piles = int(float(row[2])) if _cell(2) else 1

                mx_txt, my_txt = _cell(5), _cell(6)
                moment_x_knm = float(mx_txt.replace(",", ".")) if mx_txt else None
                moment_y_knm = float(my_txt.replace(",", ".")) if my_txt else None
                if moment_x_knm is not None or moment_y_knm is not None:
                    moment_kn_m = math.hypot(moment_x_knm or 0.0, moment_y_knm or 0.0)
                else:
                    moment_kn_m = float(_cell(3).replace(",", ".")) if _cell(3) else None

                hx_txt, hy_txt = _cell(7), _cell(8)
                shear_x_kn = float(hx_txt.replace(",", ".")) if hx_txt else None
                shear_y_kn = float(hy_txt.replace(",", ".")) if hy_txt else None
                if shear_x_kn is not None or shear_y_kn is not None:
                    shear_kn = math.hypot(shear_x_kn or 0.0, shear_y_kn or 0.0)
                else:
                    shear_kn = float(_cell(4).replace(",", ".")) if _cell(4) else None

                new_loads.add(
                    element_id, load_kn, n_piles, moment_kn_m, shear_kn,
                    moment_x_knm, moment_y_knm, shear_x_kn, shear_y_kn,
                )
            self.load_set = new_loads
            self._refresh_loads_tree()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao carregar CSV", str(exc))

    def _save_loads_csv(self) -> None:
        if not self.load_set.items:
            messagebox.showinfo("Nada para salvar", "Não há esforços para salvar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "elemento", "carga_caracteristica_kn", "n_estacas", "momento_knm", "cortante_kn",
                "mx_knm", "my_knm", "hx_kn", "hy_kn",
            ])
            for item in self.load_set.items:
                writer.writerow([
                    item.element_id, item.characteristic_load_kn, item.n_piles,
                    item.moment_kn_m if item.moment_kn_m is not None else "",
                    item.shear_kn if item.shear_kn is not None else "",
                    item.moment_x_knm if item.moment_x_knm is not None else "",
                    item.moment_y_knm if item.moment_y_knm is not None else "",
                    item.shear_x_kn if item.shear_x_kn is not None else "",
                    item.shear_y_kn if item.shear_y_kn is not None else "",
                ])

    def _select_ai_loads_pdf(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if not path:
            return
        self.ai_loads_pdf_path = path
        self.label_ai_loads_pdf.config(text=path)

    def _run_ai_loads_extraction(self) -> None:
        if not self.ai_loads_pdf_path:
            messagebox.showinfo("Selecione um PDF", "Selecione o PDF do relatório de esforços primeiro.")
            return

        self.button_ai_loads_run.config(state="disabled")
        self.label_ai_loads_status.config(text="Processando com IA... isso pode levar até 1 minuto.", foreground="#1a6fd6")

        def worker() -> None:
            try:
                from .ai_extraction import extract_foundation_loads

                result = extract_foundation_loads(self.ai_loads_pdf_path)
            except AIExtractionError as exc:
                self.after(0, lambda: self._on_ai_loads_extraction_error(str(exc)))
                return
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: self._on_ai_loads_extraction_error(f"Erro inesperado: {exc}"))
                return
            self.after(0, lambda: self._on_ai_loads_extraction_done(result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_loads_extraction_error(self, message: str) -> None:
        self.button_ai_loads_run.config(state="normal")
        self.label_ai_loads_status.config(text="", foreground="black")
        messagebox.showerror("Erro na interpretação por IA", message)

    def _on_ai_loads_extraction_done(self, result: ExtractedLoadsReport) -> None:
        self.button_ai_loads_run.config(state="normal")
        self.ai_loads_extraction_result = result
        self.label_ai_loads_status.config(
            text="", foreground="black",
        )
        added = 0
        for item in result.items:
            try:
                self.load_set.add(
                    item.element_id, item.characteristic_load_kn, item.n_piles,
                    item.moment_kn_m, item.shear_kn,
                    item.moment_x_knm, item.moment_y_knm, item.shear_x_kn, item.shear_y_kn,
                )
                added += 1
            except ValueError:
                continue
        self._refresh_loads_tree()
        messagebox.showinfo(
            "Esforços importados",
            f"{added} elemento(s) importados pela IA para a lista de esforços. Revise os "
            "valores na tabela (compare com o PDF original) antes de calcular.",
        )

    def _calculate_batch(self) -> None:
        if not self.load_set.is_valid():
            messagebox.showinfo("Nenhum esforço", "Adicione ou importe ao menos um esforço de fundação.")
            return
        try:
            if not self.profile.is_valid():
                raise ValueError("Adicione ao menos 2 leituras de SPT na aba 1.")
            diameter_cm = float(self.entry_diameter.get().replace(",", "."))
            fs = float(self.entry_fs.get().replace(",", "."))
            min_depth = float(self.entry_min_depth.get().replace(",", "."))
            pile_type = self._selected_pile_type_key()
            method = self._selected_method_key()
            geometry = PileGeometry(diameter_cm=diameter_cm)

            designs = pg.compute_individual_designs(
                self.load_set.items, self.profile, geometry, pile_type, method=method,
                safety_factor=fs, min_depth_m=min_depth,
            )

            uniformize = self.combo_uniformize.get() == "Sim"
            n_groups = None
            if uniformize:
                n_groups = int(float(self.entry_n_groups.get().replace(",", ".")))
                pg.apply_group_uniformization(designs, n_groups)
            else:
                pg.apply_no_uniformization(designs)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro no cálculo em lote", str(exc))
            return

        self.pile_designs = designs
        self.uniformized = uniformize
        self.n_groups_used = n_groups
        self._geometry = geometry
        self._pile_type = pile_type
        self._fs = fs

        try:
            cover = float(self.entry_cover.get().replace(",", "."))
            rho_txt = self.entry_rho_min.get().strip()
            rho_min = float(rho_txt.replace(",", ".")) if rho_txt else None
            stirrup_d = float(self.combo_stirrup.get())
            spacing_body = float(self.entry_stirrup_body.get().replace(",", "."))
            spacing_top = float(self.entry_stirrup_top.get().replace(",", "."))
            armor_txt = self.entry_armor_length.get().strip()
            armor_length = float(armor_txt.replace(",", ".")) if armor_txt else None
            fck = float(self.entry_fck.get().replace(",", "."))
            fyk = float(self.entry_fyk.get().replace(",", "."))
            load_factor = float(self.entry_load_factor.get().replace(",", "."))
            gamma_c = float(self.entry_gamma_c.get().replace(",", "."))
            self.reinforcement_result = pg.compute_batch_reinforcement(
                self.load_set.items, geometry, cover_cm=cover, rho_min_pct=rho_min,
                stirrup_diameter_mm=stirrup_d, stirrup_spacing_body_cm=spacing_body,
                stirrup_spacing_top_cm=spacing_top, armor_length_m=armor_length,
                load_factor=load_factor, fck_mpa=fck, fyk_mpa=fyk, gamma_c=gamma_c,
            )
            self._render_reinforcement(self.reinforcement_result)
        except Exception:  # noqa: BLE001 - armação é complementar; falha aqui não impede o resultado em lote
            pass

        self._refresh_batch_tree()

    def _refresh_batch_tree(self) -> None:
        from .reinforcement import effective_armor_length_m

        self.tree_batch.delete(*self.tree_batch.get_children())
        n_infeasible = 0
        for d in self.pile_designs:
            individual_txt = f"{d.individual_required_depth_m:.2f}" if d.individual_required_depth_m is not None else "INVIÁVEL"
            adopted_txt = f"{d.adopted_depth_m:.2f}" if d.adopted_depth_m is not None else "-"
            if d.individual_required_depth_m is None:
                n_infeasible += 1
            if d.adopted_depth_m is not None and self.reinforcement_result is not None:
                armor_txt = f"{effective_armor_length_m(self.reinforcement_result, d.adopted_depth_m):.2f}"
            else:
                armor_txt = "-"
            self.tree_batch.insert(
                "", "end",
                values=(
                    d.element_id, f"{d.load_per_pile_kn:.1f}", individual_txt, d.group_label or "-",
                    adopted_txt, armor_txt,
                ),
            )
        total = len(self.pile_designs)
        summary = f"{total} elemento(s) calculado(s)"
        if n_infeasible:
            summary += f" - {n_infeasible} inviável(is) (carga não atingida no perfil sondado)"
        if self.uniformized:
            distinct = {d.adopted_depth_m for d in self.pile_designs if d.adopted_depth_m is not None}
            summary += f" - uniformizado em {len(distinct)} profundidade(s) padrão"
        self.label_batch_summary.config(
            text=summary, foreground=("#b00020" if n_infeasible else "#0a6e0a")
        )

    def _export_batch_memorial(self) -> None:
        if not self.pile_designs:
            messagebox.showinfo("Nada para exportar", "Calcule a profundidade de todas as estacas primeiro.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("Word", "*.docx")])
        if not path:
            return
        try:
            from .batch_memorial import build_batch_memorial
        except ImportError as exc:
            messagebox.showerror(
                "Dependência ausente",
                f"Biblioteca 'python-docx' não está instalada. Rode: pip install python-docx\n\n{exc}",
            )
            return

        water_found, water_depth = self._get_water_table()
        method = self._selected_method_key()
        try:
            build_batch_memorial(
                path,
                self.load_set.items,
                self.pile_designs,
                self.profile,
                self._geometry,
                self._pile_type,
                method,
                self._fs,
                self.reinforcement_result,
                uniformized=self.uniformized,
                n_groups=self.n_groups_used,
                water_table_depth_m=water_depth,
                water_table_found=water_found,
                ai_loads_extraction=self.ai_loads_extraction_result,
            )
        except ImportError as exc:
            messagebox.showerror(
                "Dependência ausente",
                f"Biblioteca 'python-docx' não está instalada. Rode: pip install python-docx\n\n{exc}",
            )
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao gerar memorial", str(exc))
            return
        messagebox.showinfo("Memorial gerado", f"Memorial de cálculo em lote salvo em:\n{path}")


def run() -> None:
    root = tk.Tk()
    root.title("Cálculo de Estacas via SPT - Profundidade e Armação")
    root.geometry("980x680")
    SPTPilesApp(root)
    root.mainloop()
