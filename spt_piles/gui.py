"""Interface gráfica desktop (Tkinter) do software de cálculo de estacas via SPT."""

from __future__ import annotations

import csv
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import depth_solver as ds
from . import report as report_mod
from .ai_extraction import AIExtractionError, ExtractedReading, ExtractedSPTReport
from .models import PileGeometry, SPTProfile
from .pile_factors import PILE_TYPES
from .reinforcement import STIRRUP_DIAMETERS_MM, default_rho_min_pct, design_reinforcement
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

        self.pack(fill="both", expand=True)
        self._build_widgets()

    # ------------------------------------------------------------------ UI
    def _build_widgets(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_profile = ttk.Frame(notebook)
        self.tab_ai = ttk.Frame(notebook)
        self.tab_pile = ttk.Frame(notebook)
        self.tab_results = ttk.Frame(notebook)
        self.tab_reinforcement = ttk.Frame(notebook)

        notebook.add(self.tab_profile, text="1. Perfil SPT")
        notebook.add(self.tab_ai, text="2. Importar Laudo (IA)")
        notebook.add(self.tab_pile, text="3. Estaca e Carga")
        notebook.add(self.tab_results, text="4. Resultados")
        notebook.add(self.tab_reinforcement, text="5. Armação")

        self._build_tab_profile()
        self._build_tab_ai()
        self._build_tab_pile()
        self._build_tab_results()
        self._build_tab_reinforcement()

        footer = ttk.Label(
            self,
            text=(
                "Ferramenta de pré-dimensionamento. Não substitui ART/RRT de engenheiro "
                "habilitado nem a NBR 6118/6122 vigentes."
            ),
            foreground="#7a4a00",
        )
        footer.pack(fill="x", padx=8, pady=(0, 6))

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
        ttk.Label(grid, text="Cobrimento (cm):").grid(row=r, column=0, sticky="w", pady=4)
        self.entry_cover = ttk.Entry(grid, width=10)
        self.entry_cover.insert(0, "4.0")
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

            result = design_reinforcement(
                self._geometry,
                axial_load_kn=self.solver_result.load_kn,
                cover_cm=cover,
                rho_min_pct=rho_min,
                stirrup_diameter_mm=stirrup_d,
                stirrup_spacing_body_cm=spacing_body,
                stirrup_spacing_top_cm=spacing_top,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro no cálculo de armação", str(exc))
            return

        self.reinforcement_result = result
        self._render_reinforcement(result)

    def _render_reinforcement(self, result) -> None:
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
        lines.append("")
        lines.append(
            f"Estribos: φ{result.stirrup_diameter_mm:.1f} mm a cada {result.stirrup_spacing_body_cm:.0f} cm "
            f"no corpo da estaca"
        )
        lines.append(
            f"Zona de confinamento (primeiros {result.confinement_length_m:.2f} m a partir do topo): "
            f"estribos a cada {result.stirrup_spacing_top_cm:.0f} cm"
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


def run() -> None:
    root = tk.Tk()
    root.title("Cálculo de Estacas via SPT - Profundidade e Armação")
    root.geometry("980x680")
    SPTPilesApp(root)
    root.mainloop()
