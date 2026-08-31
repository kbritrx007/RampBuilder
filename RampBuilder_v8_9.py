#General Functions
#-----------------------------------------------

#do we want to just show whole inches on post above below etc in table and in printout?

#*********


#update draw component for triangle??


#make sure reference surface loads ok on all tabs and can be resized?


#Rails
#---------------------------------------------------------
#confirm breaking of lengths - consider looking at > 24" waste and bumping to 10' board before splitting 3 from 1 board
#84-96  108-120
#pair existing with 2 inch buffer
#repeat above split board
    #28-32 36-40 44-48

#notes - add steps after creating the deck they belong to for the post heights to default to the correct height above grade

import os
import sys

# 1. Tell Python where to find the 'gs' (Ghostscript) binary you found
os.environ['PATH'] += os.pathsep + '/usr/local/bin'

# 2. Force Pillow to use that specific Ghostscript path
try:
    from PIL import EpsImagePlugin
    EpsImagePlugin.gs_windows_binary = "/usr/local/bin/gs"
except ImportError:
    pass

import tkinter as tk
from tkinter import ttk, simpledialog
import math
import json
from tkinter import filedialog, messagebox
import tkinter.simpledialog as sd

import webbrowser
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

import urllib.request
import webbrowser
import traceback
from tkinter import messagebox

class RampArchitect:
    def __init__(self, root):
        self.root = root
        self.root.title("Ramp Builder v8.9")
        self.root.geometry("1450x950")

        # --- STATE ---
        self.scale = 2
        self.snap_dist = 15
        self.active_tag = {}
        self.sections = {} 
        self.post_entries = {}
        self.cross_brace_entries = {}
        self.rail_entries = {}
        self.manual_override_active = False
        self.boards = []
        self._drag_data = {"item": None, "x": 0, "y": 0}
        self._post_drag_data = {"item": None, "x": 0, "y": 0}
        self._rail_drag_data = {"item": None, "x": 0, "y": 0}
        self.ramp_count = 0
        self.taper_ramp_count = 0
        self.threshold_ramp_count = 0
        self.post_count = 0
        self.landing_count = 0
        self.step_count = 0
        self.paver_count = 0
        self.paver_total = 0
        self.post_block_count = 0
        self.component_tabs = {} 
        self.post_table_data = {}
        self.rail_table_data = {}
        self.comp_table_data = {}

        self.auto_snap_enabled = tk.BooleanVar(value=True)  # Enabled by default
        # --- STATE ---
        self.comment_boxes = {}  # Format: {box_id: {'text': str, 'x': float, 'y': float, 'w': float, 'h': float, 'canvas_ref': canvas_object}}
        self._comment_drag_data = {"item": None, "x": 0, "y": 0, "mode": "move"}

        self.rail_count = 0
        self.postbrace_count = 0
        self.inch_val = 0
        self.total_drop_val = 0.0
        self.p_size = 3.5 * self.scale 
        self.inset = 1.5 * self.scale 

        # --- UI LAYOUT (Notebook first!) ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both")

        self.tab_layout = tk.Frame(self.notebook)
        self.tab_posts = tk.Frame(self.notebook)
        self.tab_rails = tk.Frame(self.notebook) 
        self.tab_materials = tk.Frame(self.notebook)

        check_for_updates()

        self.notebook.add(self.tab_layout, text="1. Overall Layout")
        self.notebook.add(self.tab_posts, text="2. Post Map")
        self.notebook.add(self.tab_rails, text="3. Handrail Detail") 
        self.notebook.add(self.tab_materials, text="4. Materials")

        #self.notebook.bind(self.tab_layout, self.on_tab_change)
        #self.notebook.bind(self.tab_rails, self.on_tab_change)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed_global)

        # --- INITIALIZE TABS ---
        self.setup_layout_tab()
        self.setup_posts_tab()
        self.setup_rails_tab() 
        
        self.setup_menu()

        # Bind rotation shortcuts directly to canvas widgets
        if hasattr(self, 'post_canvas'):
            self.post_canvas.bind("<r>", self.rotate_post_item)
            self.post_canvas.bind("<R>", self.rotate_post_item)

        if hasattr(self, 'rail_canvas'):
            self.rail_canvas.bind("<r>", self.rotate_rail_item)
            self.rail_canvas.bind("<R>", self.rotate_rail_item)

        if hasattr(self, 'canvas'):
            self.canvas.bind("<r>", self.rotate_item)
            self.canvas.bind("<R>", self.rotate_item)

        self.create_reference_point(600, 100)
        tk.Label(self.root, text="Total Drop (in):").pack(side="left", padx=5)
        self.total_drop_entry = tk.Entry(self.root, width=10)
        self.total_drop_entry.pack(side="left", padx=5)
        self.rail_canvas.bind("<ButtonPress-1>", self.debug_canvas_click, add="+")

    def on_tab_change(self, event):
        # Get the name of the currently selected tab
        current_tab = self.notebook.tab(self.tab_lnotebookayout.select(), "text")
        
        if current_tab == "1. Overall Layout": # Replace "Main" with your actual tab label
            # Force the focus onto the canvas so 'R' works for rotation
            self.canvas.focus_set()
        elif current_tab == "3. Handrail Detail": # Replace "Main" with your actual tab label
            # Force the focus onto the canvas so 'R' works for rotation
            self.rail_canvas.focus_set()

    def on_tab_changed_global(self, event):
        selected_index = self.notebook.index(self.notebook.select())
        current_tab = self.notebook.tab(selected_index, "text")
        
        if current_tab == "1. Overall Layout":
            self.canvas.focus_set()
        elif current_tab == "3. Handrail Detail":
            self.rail_canvas.focus_set()
        elif current_tab == "4. Materials":
            self.refresh_materials_matrix() # Re-calculate matrix live when tab is opened


    def refresh_materials_matrix(self):
        """Assembles a structural grid of lumber types and lengths by reading pre-calculated dictionaries."""
        # Clear previous layout frame items completely
        for widget in self.tab_materials.winfo_children():
            widget.destroy()

        lumber_types = ["2x6", "2x4", "4x4", "5/4x6", "2x8"]
        standard_lengths = [8, 10, 12]

        # Gather active columns from live component entries
        active_sections = []
        for tag, data in self.sections.items():
            print (tag)
            if tag != 'REF_POINT' and 'name' in data and not tag.startswith('Paver') :
                active_sections.append((tag, data['name']))
                print (tag)
        # Append general system modules
        active_sections.append(("POST_MAP", "Post Map"))
        active_sections.append(("HANDRAIL_DETAIL", "Handrail Detail"))

        # Initialize full matrix counts
        matrix_counts = {}
        for l_type in lumber_types:
            for l_ft in standard_lengths:
                matrix_counts[(l_type, l_ft)] = {sec[0]: 0 for sec in active_sections}

        # --- HARVEST FROM SUB-COMPONENTS (Ramps, Decks, Steps) ---
        for tag, data in self.sections.items():
            if 'lumber_counts' in data and isinstance(data['lumber_counts'], dict):
                for (l_type, l_ft), qty in data['lumber_counts'].items():
                    if (l_type, l_ft) in matrix_counts and tag in matrix_counts[(l_type, l_ft)]:
                        matrix_counts[(l_type, l_ft)][tag] = qty

        # --- HARVEST FROM POST MAP (4x4 Posts and Cross-Braces) ---
        totals_source = getattr(self, 'last_optimized_totals', None)
        if totals_source:
            for length_in, count in totals_source.items():
                length_ft = length_in // 12
                if ( "4x4", length_ft ) in matrix_counts:
                    matrix_counts[("4x4", length_ft)]["POST_MAP"] += count

        if hasattr(self, 'cross_brace_entries') and self.cross_brace_entries:
            for b_tag, b_data in self.cross_brace_entries.items():
                try:
                    cut_len = float(b_data.get('material_length', 0))
                    matched_len = 8
                    if cut_len > 120: matched_len = 12
                    elif cut_len > 96: matched_len = 10
                    matrix_counts[("2x4", matched_len)]["POST_MAP"] += 1
                except (ValueError, TypeError):
                    continue

        # --- HARVEST FROM HANDRAIL DETAIL ---
        if hasattr(self, 'last_rail_boards') and self.last_rail_boards:
            for board in self.last_rail_boards:
                size_in = board.get('size', 96)
                length_ft = size_in // 12
                if ("2x4", length_ft) in matrix_counts:
                    matrix_counts[("2x4", length_ft)]["HANDRAIL_DETAIL"] += 1

        # --- RENDER TABLE UI ---
        container = ttk.Frame(self.tab_materials)
        container.pack(expand=True, fill="both", padx=10, pady=10)

        canvas = tk.Canvas(container, bg="#f8f9fa", highlightthickness=0)
        v_scroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        h_scroll = ttk.Scrollbar(container, orient="horizontal", command=canvas.xview)
        
        matrix_grid = tk.Frame(canvas, bg="#ffffff", bd=1, relief="solid")
        matrix_grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=matrix_grid, anchor="nw")
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        canvas.pack(side="left", expand=True, fill="both")
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")

        # Table Header
        tk.Label(matrix_grid, text="Material Specification Profile", font=("Arial", 10, "bold"), bg="#1a365d", fg="white", width=26, padx=6, pady=6, borderwidth=1, relief="solid").grid(row=0, column=0, sticky="nsew")
        for col_idx, (_, col_name) in enumerate(active_sections):
            tk.Label(matrix_grid, text=col_name, font=("Arial", 9, "bold"), bg="#1a365d", fg="white", width=14, padx=6, pady=6, borderwidth=1, relief="solid").grid(row=0, column=col_idx + 1, sticky="nsew")
        tk.Label(matrix_grid, text="GRAND TOTAL", font=("Arial", 9, "bold"), bg="#2e7d32", fg="white", width=15, padx=6, pady=6, borderwidth=1, relief="solid").grid(row=0, column=len(active_sections) + 1, sticky="nsew")

        # Build Matrix Rows
        current_row = 1
        for l_type in lumber_types:
            tk.Label(matrix_grid, text=f"LUMBER TYPE: {l_type}", font=("Arial", 9, "bold"), bg="#cbd5e1", anchor="w", padx=4, pady=4, borderwidth=1, relief="solid").grid(row=current_row, column=0, columnspan=len(active_sections) + 2, sticky="ew")
            current_row += 1

            for l_ft in standard_lengths:
                display_label = f"{l_type} x {l_ft}'"
                row_bg = "#ffffff" if current_row % 2 == 0 else "#f8fafc"

                tk.Label(matrix_grid, text=display_label, font=("Arial", 9), bg=row_bg, anchor="w", padx=5, pady=5, borderwidth=1, relief="solid").grid(row=current_row, column=0, sticky="nsew")

                row_grand_total = 0
                for col_idx, (sec_tag, _) in enumerate(active_sections):
                    cell_val = matrix_counts[(l_type, l_ft)][sec_tag]
                    row_grand_total += cell_val
                    
                    cell_text = self.format_stock(cell_val)
                    cell_fg = "#000000" if cell_val > 0 else "#94a3b8"
                    font_w = "bold" if cell_val > 0 else "normal"

                    tk.Label(matrix_grid, text=cell_text, font=("Arial", 9, font_w), fg=cell_fg, bg=row_bg, justify="center", borderwidth=1, relief="solid").grid(row=current_row, column=col_idx + 1, sticky="nsew")

                # Grand Total Display Row Output
                total_text = self.format_stock(row_grand_total)
                total_bg = "#a8f4ae" if row_grand_total > 0 else row_bg
                total_fg = "#000000" if row_grand_total > 0 else "#94a3b8"

                tk.Label(matrix_grid, text=total_text, font=("Arial", 9, "bold"), fg=total_fg, bg=total_bg, justify="center", borderwidth=1, relief="solid").grid(row=current_row, column=len(active_sections) + 1, sticky="nsew")
                current_row += 1

        active_stringer_sizes = set()
        for tag, data in self.sections.items():
            if tag != 'ref_point' and 'lumber_counts' in data:
                for k in data['lumber_counts'].keys():
                    if k[0] == "stringers":
                        active_stringer_sizes.add(k[1])
        
        sorted_stringer_sizes = sorted(list(active_stringer_sizes))

        if sorted_stringer_sizes:
            # Main Category Divider Header Strip
            tk.Label(matrix_grid, text="CUSTOM FABRICATED COMPONENTS", font=("Arial", 9, "bold"), bg="#cbd5e1", anchor="w", padx=4, pady=4, borderwidth=1, relief="solid").grid(row=current_row, column=0, columnspan=len(active_sections) + 2, sticky="ew")
            current_row += 1

            for steps_count in sorted_stringer_sizes:
                display_label = f"{steps_count}-Step Stringer"
                row_bg = "#ffffff" if current_row % 2 == 0 else "#f8fafc"

                tk.Label(matrix_grid, text=display_label, font=("Arial", 9), bg=row_bg, anchor="w", padx=5, pady=5, borderwidth=1, relief="solid").grid(row=current_row, column=0, sticky="nsew")

                row_grand_total = 0
                for col_idx, (sec_tag, _) in enumerate(active_sections):
                    cell_val = 0.0
                    if sec_tag in self.sections and 'lumber_counts' in self.sections[sec_tag]:
                        cell_val = self.sections[sec_tag]['lumber_counts'].get(("stringers", steps_count), 0.0)
                    
                    row_grand_total += cell_val
                    
                    cell_text = self.format_stock(cell_val)
                    cell_fg = "#000000" if cell_val > 0 else "#94a3b8"
                    font_w = "bold" if cell_val > 0 else "normal"

                    tk.Label(matrix_grid, text=cell_text, font=("Arial", 9, font_w), fg=cell_fg, bg=row_bg, justify="center", borderwidth=1, relief="solid").grid(row=current_row, column=col_idx + 1, sticky="nsew")

                # Grand Total calculation display
                total_text = self.format_stock(row_grand_total)
                total_bg = "#a8f4ae" if row_grand_total > 0 else row_bg
                total_fg = "#000000" if row_grand_total > 0 else "#94a3b8"

                tk.Label(matrix_grid, text=total_text, font=("Arial", 9, "bold"), fg=total_fg, bg=total_bg, justify="center", borderwidth=1, relief="solid").grid(row=current_row, column=len(active_sections) + 1, sticky="nsew")
                current_row += 1


        post_blocks = getattr(self, 'post_block_count', 0)
        pavers = getattr(self, 'paver_total', 0)

        if post_blocks > 0 or pavers > 0:
            # 1. Add a visual spacer row to isolate it from the matrix above
            tk.Label(matrix_grid, text="", bg="#f8f9fa").grid(row=current_row, column=0, columnspan=len(active_sections) + 2)
            current_row += 1

            # 2. Main Miscellaneous Section Category Header 
            tk.Label(matrix_grid, text="MISCELLANEOUS ITEMS", font=("Arial", 9, "bold"), bg="#cbd5e1", anchor="w", padx=4, pady=4, borderwidth=1, relief="solid").grid(row=current_row, column=0, columnspan=2, sticky="ew")
            current_row += 1

            # 3. Small Table Sub-Headers (Item & Quantity)
            tk.Label(matrix_grid, text="Item", font=("Arial", 9, "bold"), bg="#1a365d", fg="white", anchor="w", padx=5, pady=4, borderwidth=1, relief="solid").grid(row=current_row, column=0, sticky="ew")
            tk.Label(matrix_grid, text="Quantity", font=("Arial", 9, "bold"), bg="#1a365d", fg="white", justify="center", padx=5, pady=4, borderwidth=1, relief="solid").grid(row=current_row, column=1, sticky="ew")
            current_row += 1

            # 4. Conditionally display Post Blocks row
            if post_blocks > 0:
                row_bg = "#ffffff" if current_row % 2 == 0 else "#f8fafc"
                tk.Label(matrix_grid, text="Post Blocks", font=("Arial", 9), bg=row_bg, anchor="w", padx=5, pady=5, borderwidth=1, relief="solid").grid(row=current_row, column=0, sticky="ew")
                tk.Label(matrix_grid, text=str(post_blocks), font=("Arial", 9, "bold"), bg=row_bg, justify="center", borderwidth=1, relief="solid").grid(row=current_row, column=1, sticky="ew")
                current_row += 1

            # 5. Conditionally display Pavers row
            if pavers > 0:
                row_bg = "#ffffff" if current_row % 2 == 0 else "#f8fafc"
                tk.Label(matrix_grid, text="Pavers", font=("Arial", 9), bg=row_bg, anchor="w", padx=5, pady=5, borderwidth=1, relief="solid").grid(row=current_row, column=0, sticky="ew")
                tk.Label(matrix_grid, text=str(pavers), font=("Arial", 9, "bold"), bg=row_bg, justify="center", borderwidth=1, relief="solid").grid(row=current_row, column=1, sticky="ew")
                current_row += 1

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Project", command=self.load_project)
        file_menu.add_command(label="Save Project", command=self.save_project)
        file_menu.add_separator()
        # This links to your new HTML logic
        file_menu.add_command(label="Export PDF", command=self.export_to_html_report)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

    def export_to_html_report(self):
        """Generates a standalone, pixel-perfect HTML/CSS vector blueprint report."""
        file_path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML Report", "*.html")])
        if not file_path: return

        self.deselect_all_main()
        self.refresh_materials_matrix()

        # Start capturing structural data from your existing canvases
        html_content = self._build_html_document()

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # Show success message and instantly spin up the system web browser
            messagebox.showinfo("Success", "Vector Blueprint Report generated successfully! Opening in browser...")
            webbrowser.open(f"file://{os.path.abspath(file_path)}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to write file layout: {str(e)}")

    def _build_html_document(self):
        """Compiles style sheets, material layout tables, and SVG blueprints into a sequential report."""
        
        # 1. Gather materials calculations from live state lists
        counts_dict = {96: 0, 120: 0, 144: 0}
        if hasattr(self, 'last_rail_boards') and self.last_rail_boards:
            for b in self.last_rail_boards:
                size = b.get('size', 96)
                if size in counts_dict:
                    counts_dict[size] += 1

        # 2. Extract color combinations and unique split pairs directly from calculation lists
        rail_takeoff_rows = ""
        seen_pairings = set()

        if hasattr(self, 'last_rail_pairing_data') and self.last_rail_pairing_data:
            for p in self.last_rail_pairing_data:
                bg_color = p.get('color', '#9E9E9E')
                lbl_text = p.get('text', '').strip()
                if lbl_text and lbl_text not in seen_pairings:
                    seen_pairings.add(lbl_text)
                    color_box = f'<div style="width: 9px; height: 0px; border: 8px solid {bg_color}; border-radius: 2px; display: inline-block; vertical-align: middle;"></div>'
                    rail_takeoff_rows += f"""
                    <tr>
                        <td style="text-align: center; width: 60px; vertical-align: middle;">{color_box}</td>
                        <td><strong>{lbl_text}</strong></td>
                    </tr>
                    """

        # Append standard Solo base boards to match the UI legend layout
        if hasattr(self, 'last_rail_boards') and self.last_rail_boards:
            for b in self.last_rail_boards:
                if len(b.get('items', [])) == 1:
                    size = b.get('size', 96)
                    length_ft = size // 12
                    
                    solo_lbl = f"{length_ft}' Stock Board (Single Rail)"
                    if solo_lbl not in seen_pairings:
                        seen_pairings.add(solo_lbl)
                        
                        bg_color = "#4CAF50" if size == 96 else ("#2196F3" if size == 120 else "#FFEB3B")
                        color_box = f'<div style="width: 9px; height: 0px; border: 8px solid {bg_color}; border-radius: 2px; display: inline-block; vertical-align: middle;"></div>'
                        rail_takeoff_rows += f"""
                        <tr>
                            <td style="text-align: center; width: 60px; vertical-align: middle;">{color_box}</td>
                            <td><strong>{solo_lbl}</strong></td>
                        </tr>
                        """

        if not rail_takeoff_rows:
            rail_takeoff_rows = '<tr><td colspan="2" class="empty-msg">No active handrail optimizations found. Run rail layout analysis first.</td></tr>'

        # 3. Build 2x4 Purchase List Table using extracted counts
        rail_purchase_rows = ""
        for length_ft in sorted(counts_dict.keys(), reverse=False):
            count = counts_dict[length_ft]
            rail_purchase_rows += f"""
            <tr>
                <td><strong>2x4x{length_ft // 12}' </strong> </td>
                <td style="text-align: center; width: 100px;">{count}</td>
            </tr>
            """

        # 4. Assemble dense layout cards beneath handrail graphics
        rail_data_logs = f"""
        <div class="sub-tables-grid">
            <div class="data-card">
                <div class="card-title">Color Coding Key & Shared Split Cuts</div>
                <table>
                    <thead>
                        <tr>
                            <th style="text-align: center; width: 60px;">Color</th>
                            <th>Usage / Length Pairings Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rail_takeoff_rows}
                    </tbody>
                </table>
            </div>
            
            <div class="data-card">
                <div class="card-title">2x4 Purchase List (Handrails)</div>
                <table>
                    <thead>
                        <tr>
                            <th>Stock Material Size</th>
                            <th style="text-align: center; width: 100px;">Required Qty</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rail_purchase_rows}
                    </tbody>
                </table>
            </div>
        </div>"""

        # 5. Dynamic Data Table Compilation: Scraping live UI post specifications
        post_rows_html = ""
        if hasattr(self, 'post_entries') and self.post_entries:
            for p_tag, p_vars in self.post_entries.items():
                try:
                    deck_val = p_vars["deck"].get() or "0.0"
                    grade_val = p_vars["grade"].get() or "0.0"
                    below_val = p_vars["below"].get() or "0.0"
                    total_val = p_vars["total"].get() or '0.0"'
                    is_dummy_raw = p_vars["is_dummy"]
                    is_inset_raw = p_vars["is_inset"]
                    
                    isdummy = bool(is_dummy_raw.get()) if hasattr(is_dummy_raw, 'get') else bool(is_dummy_raw)
                    isinset = bool(is_inset_raw.get()) if hasattr(is_inset_raw, 'get') else bool(is_inset_raw)

                    print (f"{p_tag} is dummy: {isdummy}")

                    if isdummy:
                        label_text = p_tag + " (D)"
                    else:
                        label_text = p_tag
                
                    if isinset:
                        label_text = label_text + " (i)"
                    else:
                        label_text = label_text
                    print (label_text)

                    post_rows_html += f"""
                    <tr>
                        <td><strong>{label_text}</strong></td>
                        <td>{deck_val}"</td>
                        <td>{grade_val}"</td>
                        <td>{below_val}"</td>
                        <td>{total_val}</td>
                    </tr>
                    """
                except Exception:
                    continue
        else:
            post_rows_html = "<tr><td colspan='5' class='empty-msg'>No active posts calculated.</td></tr>"

        # 6. Dynamic Data Table Compilation: Extracting Post Pairings
        pairings_rows_html = ""
        optimized_source = getattr(self, 'last_optimized_pairings', None)
        if optimized_source:
            for p in optimized_source:
                try:
                    p_ids = p.get('ids', '-')
                    stock_ft = f"{p.get('stock', 0) // 12}'"
                    buffer_in = f"{int(p.get('remainder', 0))}\""
                    lengths_list = p.get('displaylen', '-')
                    
                    pairings_rows_html += f"""
                    <tr>
                        <td><strong>{p_ids}</strong></td>
                        <td>{stock_ft}</td>
                        <td>{buffer_in}</td>
                        <td>{lengths_list}</td>
                    </tr>
                    """
                except Exception:
                    continue
        else:
            pairings_rows_html = "<tr><td colspan='4' class='empty-msg'>No post pairings optimized yet. Run calculations first.</td></tr>"

        # 7. Dynamic Data Table Compilation: Extracting 4x4 Post Purchase List
        purchase_rows_html = ""
        totals_source = getattr(self, 'last_optimized_totals', None)
        if totals_source:
            for length_in in sorted(totals_source.keys()):
                count = totals_source[length_in]
                length_ft = f"{length_in // 12} Foot"
                purchase_rows_html += f"""
                <tr>
                    <td><strong>{length_ft}</strong></td>
                    <td style="text-align:center;">{count}</td>
                </tr>
                """
        else:
            purchase_rows_html = "<tr><td colspan='2' class='empty-msg'>No active data calculated.</td></tr>"

        # 8. Dynamic Data Table Compilation: Extracting Cross-Brace Cut Lengths Only
        cross_brace_rows_html = ""
        if hasattr(self, 'cross_brace_entries') and self.cross_brace_entries:
            for b_tag, b_data in self.cross_brace_entries.items():
                try:
                    cut_len = b_data.get('material_length', "0.0")
                    cross_brace_rows_html += f"""
                    <tr>
                        <td><strong>{b_tag}</strong></td>
                        <td>{cut_len}"</td>
                    </tr>
                    """
                except Exception:
                    continue

        # 9. Compile individual dynamic project layout tabs into separate SVG blueprints
        master_bounds = self.get_combined_master_bbox()

        overall_layout_svg = self._canvas_to_svg(self.canvas, master_bbox=master_bounds)
        post_map_svg = self._canvas_to_svg(self.post_canvas, master_bbox=master_bounds)
        
        # FIX 1: Crop tightly to rail_canvas alone (do NOT pass master_bounds)
        handrail_detail_svg = self._canvas_to_svg(self.rail_canvas)

        # 10. Compile dynamic sub-components (Ramps, Decks, Steps)
        component_pages_html = ""
        for tag, data in self.sections.items():
            if tag not in self.component_tabs: continue
            tab_info = self.component_tabs[tag]
            comp_svg = self._canvas_to_svg(tab_info['canvas'])
            
            table_rows = ""
            if 'materials_data' in data and data['materials_data']:
                for row in data['materials_data']:
                    if len(row) >= 5:
                        table_rows += f"""
                        <tr>
                            <td>{row[0]}</td>
                            <td>{row[1]}</td>
                            <td style="white-space: nowrap;">{row[2]}</td>
                            <td style="white-space: nowrap;">{row[3]}</td>
                            <td>{row[4]}</td>
                        </tr>"""
            else:
                table_rows += f"<tr><td>1</td><td>2x4</td><td>{data['name']} Structure Board</td><td>{data.get('l', 0)}\"</td><td>1</td></tr>"

            component_pages_html += f"""
            <div class="page-break"></div>
            <div class="header" style="font-size:16px; margin-top: 20px; margin-bottom:10px;">DETAIL: {data['name'].upper()}</div>
            <div class="svg-container">{comp_svg}</div>
            
            <div class="component-table-container">
                <h3 style="font-size:13px; margin-top:10px; margin-bottom:5px; color:#64748b;">Component Materials List</h3>   
                <table class="compact-component-table">
                    <thead>
                        <tr>
                            <th style="width: 18%;">Stock Qty</th>
                            <th style="width: 16%;">Size</th>
                            <th style="width: 32%;">Cut / Part</th>
                            <th style="width: 1%; white-space: nowrap;">Length</th>
                            <th style="width: 16%;">Qty</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>"""

        # 11. GENERATE FULL MATRIX MATERIALS SPECIFICATION SHEET FOR HTML
        lumber_types = ["2x6", "2x4", "4x4", "5/4x6", "2x8"]
        standard_lengths = [8, 10, 12]

        # Gather active sections/columns (excluding ref_point) exactly like the GUI Matrix Tab
        active_sections = []
        for tag, data in self.sections.items():
            if tag != 'REF_POINT' and 'name' in data:
                active_sections.append((tag, data['name']))
        
        # Append general system tracking modules
        active_sections.append(("POST_MAP", "Post Map"))
        active_sections.append(("HANDRAIL_DETAIL", "Handrail Detail"))

        # Initialize core matrix calculation structures
        matrix_counts = {}
        for l_type in lumber_types:
            for l_ft in standard_lengths:
                matrix_counts[(l_type, l_ft)] = {sec[0]: 0 for sec in active_sections}

        # Harvest structural sections data (Ramps, Decks, Steps)
        for tag, data in self.sections.items():
            if tag != 'ref_point' and 'lumber_counts' in data and isinstance(data['lumber_counts'], dict):
                for (l_type, l_ft), qty in data['lumber_counts'].items():
                    if (l_type, l_ft) in matrix_counts and tag in matrix_counts[(l_type, l_ft)]:
                        matrix_counts[(l_type, l_ft)][tag] = qty

        # Harvest post data optimizations
        totals_source = getattr(self, 'last_optimized_totals', None)
        if totals_source:
            for length_in, count in totals_source.items():
                length_ft = length_in // 12
                if ("4x4", length_ft) in matrix_counts:
                    matrix_counts[("4x4", length_ft)]["POST_MAP"] += count

        # Harvest cross braces strings
        if hasattr(self, 'cross_brace_entries') and self.cross_brace_entries:
            for b_tag, b_data in self.cross_brace_entries.items():
                try:
                    cut_len = float(b_data.get('material_length', 0))
                    matched_len = 8
                    if cut_len > 120: matched_len = 12
                    elif cut_len > 96: matched_len = 10
                    matrix_counts[("2x4", matched_len)]["POST_MAP"] += 1
                except (ValueError, TypeError):
                    continue

        # Harvest optimization handrails
        if hasattr(self, 'last_rail_boards') and self.last_rail_boards:
            for board in self.last_rail_boards:
                size_in = board.get('size', 96)
                length_ft = size_in // 12
                if ("2x4", length_ft) in matrix_counts:
                    matrix_counts[("2x4", length_ft)]["HANDRAIL_DETAIL"] += 1

        # Check for active custom stringers across sub-components
        active_stringer_sizes = set()
        for tag, data in self.sections.items():
            if tag != 'ref_point' and 'lumber_counts' in data:
                for k in data['lumber_counts'].keys():
                    if k[0] == "stringers":
                        active_stringer_sizes.add(k[1])
        sorted_stringer_sizes = sorted(list(active_stringer_sizes))

        # Build Matrix HTML Table Headers
        matrix_headers_html = '<th style="background-color: #1a365d; color: white; padding: 6px 8px;">Material List</th>'
        for _, col_name in active_sections:
            matrix_headers_html += f'<th style="text-align: center; font-size: 11px; background-color: #1a365d; color: white; padding: 6px 8px;">{col_name}</th>'
        matrix_headers_html += '<th style="text-align: center; background-color: #2e7d32; color: white; padding: 6px 8px;">GRAND TOTAL</th>'

        # Render standard dimensional rows
        matrix_rows_html = ""
        for l_type in lumber_types:
            # Header block divider for each major structural family type
            matrix_rows_html += f"""
            <tr style="background-color: #cbd5e1; font-weight: bold; color: #1e293b;">
                <td colspan="{len(active_sections) + 2}" style="padding: 6px 8px; font-size: 11px; text-transform: uppercase; border: 1px solid #cbd5e1;">Lumber Type: {l_type}</td>
            </tr>"""
            
            for l_ft in standard_lengths:
                display_label = f"{l_type} x {l_ft}'"
                row_cells = f'<td style="padding: 5px 6px;font-size: 11px; border: 1px solid #cbd5e1;"><strong>{display_label}</strong></td>'
                row_grand_total = 0

                for sec_tag, _ in active_sections:
                    cell_val = matrix_counts[(l_type, l_ft)][sec_tag]
                    row_grand_total += cell_val
                    
                    cell_text = self.format_stock(cell_val)
                    cell_style = 'style="padding: 5px 6px; text-align: center; color: #000000; font-weight: bold; border: 1px solid #cbd5e1;"' if cell_val > 0 else 'style="padding: 5px 6px; text-align: center; color: #94a3b8; border: 1px solid #cbd5e1;"'
                    row_cells += f"<td {cell_style}>{cell_text}</td>"

                total_text = self.format_stock(row_grand_total)
                total_style = 'style="padding: 5px 6px; font-size:12px; text-align: center; background-color: #e8f5e9; color: black; font-weight: bold; border: 1px solid #cbd5e1;"' if row_grand_total > 0 else 'style="padding: 5px 6px; text-align: center; color: #94a3b8; border: 1px solid #cbd5e1;"'
                row_cells += f"<td {total_style}>{total_text}</td>"
                matrix_rows_html += f"<tr>{row_cells}</tr>"

        # Append Dynamic Custom Fabricated Step Stringers if active
        if sorted_stringer_sizes:
            matrix_rows_html += f"""
            <tr style="background-color: #cbd5e1; font-weight: bold; color: #1e293b;">
                <td colspan="{len(active_sections) + 2}" style="padding: 6px 8px; font-size: 11px; text-transform: uppercase; border: 1px solid #cbd5e1;">CUSTOM FABRICATED COMPONENTS</td>
            </tr>"""
            
            for steps_count in sorted_stringer_sizes:
                display_label = f"{steps_count}-Step Stringer"
                row_cells = f'<td style="padding: 5px 6px; border: 1px solid #cbd5e1;"><strong>{display_label}</strong></td>'
                row_grand_total = 0

                for sec_tag, _ in active_sections:
                    cell_val = 0.0
                    if sec_tag in self.sections and 'lumber_counts' in self.sections[sec_tag]:
                        cell_val = self.sections[sec_tag]['lumber_counts'].get(("stringers", steps_count), 0.0)
                    
                    row_grand_total += cell_val
                    cell_text = self.format_stock(cell_val)
                    cell_style = 'style="padding: 5px 6px; text-align: center; color: #000000; font-weight: bold; border: 1px solid #cbd5e1;"' if cell_val > 0 else 'style="padding: 5px 6px; text-align: center; color: #94a3b8; border: 1px solid #cbd5e1;"'
                    row_cells += f"<td {cell_style}>{cell_text}</td>"

                total_text = self.format_stock(row_grand_total)
                total_style = 'style="padding: 5px 6px; text-align: center; background-color: #e8f5e9; color: #2e7d32; font-weight: bold; border: 1px solid #cbd5e1;"' if row_grand_total > 0 else 'style="padding: 5px 6px; text-align: center; color: #94a3b8; border: 1px solid #cbd5e1;"'
                row_cells += f"<td {total_style}>{total_text}</td>"
                matrix_rows_html += f"<tr>{row_cells}</tr>"

        # Bundle everything into a standalone structural layout card section
        materials_matrix_html = f"""
        <div class="page-break"></div>
        <div class="header" style="font-size:16px; margin-top: 20px; margin-bottom:12px;">MATERIALS MATRIX</div>
        <div class="data-card" style="padding: 0; border: 1px solid #cbd5e1; box-shadow: none;">
            <table style="width: 100%; border-collapse: collapse; margin: 0; font-size: 11px;">
                <thead>
                    <tr>
                        {matrix_headers_html}
                    </tr>
                </thead>
                <tbody>
                    {matrix_rows_html}
                </tbody>
            </table>
        </div>"""

        # 11b. NEW MODULE: EXTRACT MISCELLANEOUS HARDWARE ITEMS
        post_blocks = getattr(self, 'post_block_count', 0)
        pavers = getattr(self, 'paver_total', 0)
        miscellaneous_html = ""

        if post_blocks > 0 or pavers > 0:
            misc_rows = ""
            if post_blocks > 0:
                misc_rows += f"""
                <tr>
                    <td style="padding: 6px 8px; font-weight: bold; width: 75%;">Post Blocks</td>
                    <td style="padding: 6px 8px; text-align: center; font-weight: bold; color: #1a365d;">{post_blocks}</td>
                </tr>"""
            if pavers > 0:
                misc_rows += f"""
                <tr>
                    <td style="padding: 6px 8px; font-weight: bold; width: 75%;">Pavers</td>
                    <td style="padding: 6px 8px; text-align: center; font-weight: bold; color: #1a365d;">{pavers}</td>
                </tr>"""

            miscellaneous_html = f"""
            <div style="margin-top: 20px; max-width: 320px;" class="data-card">
                <div style="background-color: #cbd5e1; color: #1e293b; font-weight: bold; padding: 6px 8px; font-size: 11px; border: 1px solid #cbd5e1; text-transform: uppercase;">MISCELLANEOUS ITEMS</div>
                <table style="width: 100%; border-collapse: collapse; margin: 0; font-size: 11px;">
                    <thead>
                        <tr>
                            <th style="background-color: #1a365d; color: white; padding: 5px 8px;">Item</th>
                            <th style="background-color: #1a365d; color: white; padding: 5px 8px; text-align: center; width: 80px;">Quantity</th>
                        </tr>
                    </thead>
                    <tbody>
                        {misc_rows}
                    </tbody>
                </table>
            </div>"""

        # 12. Assemble integrated sequential document framework
        html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Ramp Builder Report</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; color: #1e293b; background-color: #f8fafc; max-width: 1200px; margin: 0 auto; }}
        
        .header {{ font-size: 16px; font-weight: bold; text-transform: uppercase; border-bottom: 2px solid #1a365d; padding-bottom: 4px; margin-bottom: 12px; color: #1a365d; }}
        
        /* Sequential Layout Engine */
        .workspace-flow {{ display: flex; flex-direction: column; gap: 20px; width: 100%; }}
        
        .svg-card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); overflow-x: auto; }}
        .data-card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); flex: 1; min-width: 0; }}
        .card-title {{ font-size: 11px; color: #1a365d; font-weight: bold; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.3px; border-bottom: 1.5px solid #f1f5f9; padding-bottom: 3px; }}
        
        /* Dense balanced grid for data logs beneath diagrams */
        .sub-tables-grid {{ display: flex; gap: 14px; width: 100%; margin-bottom: 10px; }}
        
        /* Column container for pairing layout and nested horizontal tables */
        .pairings-column {{ display: flex; flex-direction: column; gap: 12px; flex: 1; min-width: 0; }}
        
        /* Side-By-Side Row Container for Purchase List and Cross Braces combined */
        .materials-sub-row {{ display: flex; gap: 12px; width: 100%; }}
        
        .svg-container {{ width: 100%; border: 1px dashed #cbd5e1; background-color: #f8fafc; padding: 6px; box-sizing: border-box; margin-top: 6px; overflow-x: auto; }}
        svg {{ display: block; max-width: 100%; height: auto; margin: 0 auto; }}
        
        /* Tightened wrapper boundaries for custom component cutlists */
        .component-table-container {{ max-width: 500px; margin-top: 10px; }}
        
        /* High-density compact table metrics matching native GUI view */
        table {{ width: 100%; border-collapse: collapse; margin-top: 2px; margin-bottom: 4px; font-size: 11px; text-align: left; }}
        th {{ background-color: #1a365d; color: white; padding: 4px 6px; font-weight: 600; border: 1px solid #cbd5e1; }}
        td {{ padding: 4px 6px; border: 1px solid #cbd5e1; color: #334155; vertical-align: middle; }}
        tr:nth-child(even) td {{ background-color: #f8fafc; }}
        tr:hover td {{ background-color: #f1f5f9; }}
        
        /* Enhanced text styling for the dynamic detail cutlists (+2pt layout shift) */
        table.compact-component-table {{ font-size: 13px; }}
        table.compact-component-table th, table.compact-component-table td {{ padding: 5px 6px; }}
        
        .highlight-val {{ font-weight: bold; color: #2563eb; }}
        .empty-msg {{ text-align: center; color: #94a3b8; font-style: italic; padding: 8px; }}
        
        @media (max-width: 800px) {{
            .sub-tables-grid {{ flex-direction: column; }}
            .pairings-column {{ width: 100%; }}
            .materials-sub-row {{ flex-direction: column; }}
            .component-table-container {{ max-width: 100%; }}
        }}
        
        @media print {{
            body {{ padding: 0; margin: 0; font-size: 10px; background-color: #ffffff; max-width: 100%; }}
            .sub-tables-grid {{ flex-direction: row; page-break-inside: avoid; }}
            .pairings-column {{ flex-direction: column; }}
            .materials-sub-row {{ flex-direction: row; }}
            .page-break {{ page-break-before: always; }}
            .svg-card, .data-card, .component-table-container {{ page-break-inside: avoid; box-shadow: none; margin-bottom: 6px; }}
            .component-table-container {{ border: none; max-width: 4.5in; }}
            .svg-container {{ border: none; background: transparent; padding: 0; page-break-inside: avoid; }}
            
            * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }}
            
            th {{ background-color: #1a365d !important; }}
            tr:nth-child(even) td {{ background-color: #f8fafc !important; }}
        }}
    </style>
</head>
<body>

    <div class="workspace-flow">
        
        <div class="svg-card">
            <div class="header" style="margin-bottom:0; padding-bottom:0; border-bottom:none;">Overall Project Layout</div>
            <div class="svg-container">{overall_layout_svg}</div>
        </div>

        <div class="svg-card">
            <div class="header" style="margin-bottom:0; padding-bottom:0; border-bottom:none;">Post Map</div>
            <div class="svg-container">{post_map_svg}</div>
        </div>

        <div class="sub-tables-grid">
            <div class="data-card">
                <div class="card-title">Post Specifications</div>
                <table>
                    <thead>
                        <tr>
                            <th>Post ID</th>
                            <th>Above Deck</th>
                            <th>Above Ground</th>
                            <th>Below Ground</th>
                            <th>Total Length</th>
                        </tr>
                    </thead>
                    <tbody>
                        {post_rows_html}
                    </tbody>
                </table>
            </div>
            
            <div class="pairings-column">
                <div class="data-card">
                    <div class="card-title">Post Pairings</div>
                    <table>
                        <thead>
                            <tr>
                                <th>Post ID(s)</th>
                                <th>Stock Required</th>
                                <th>Buffer</th>
                                <th>Individual Cuts</th>
                            </tr>
                        </thead>
                        <tbody>
                            {pairings_rows_html}
                        </tbody>
                    </table>
                </div>

                <div class="materials-sub-row">
                    <div class="data-card">
                        <div class="card-title">4x4 Purchase List</div>
                        <table>
                            <thead>
                                <tr>
                                    <th style="text-align: center; width: 70px;">4x4 Length</th>
                                    <th style="text-align: center; width: 70px;">Quantity</th>
                                </tr>
                            </thead>
                            <tbody>
                                {purchase_rows_html}
                            </tbody>
                        </table>
                    </div>

                    <div class="data-card">
                        <div class="card-title">Cross Braces</div>
                        <table>
                            <thead>
                                <tr>
                                    <th style="text-align: center; width: 70px;">Brace ID</th>
                                    <th style="text-align: center; width: 70px;">Length</th>
                                </tr>
                            </thead>
                            <tbody>
                                {cross_brace_rows_html if cross_brace_rows_html else '<tr><td colspan="2" class="empty-msg">No active braces.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- FIX 2: Container wraps diagram + tables; removed page-break-before style -->
        <div style="page-break-inside: avoid;">
            <div class="svg-card">
                <div class="header" style="margin-bottom:0; padding-bottom:0; border-bottom:none;">Handrail Detail</div>
                <div class="svg-container">{handrail_detail_svg}</div>
            </div>
            
            {rail_data_logs}
        </div>

    </div>

    {component_pages_html}

    {materials_matrix_html}

    {miscellaneous_html}
</body>
</html>"""
        return html_document

    def get_combined_master_bbox(self):
        """Calculates a single bounding box that comfortably fits all elements across all 3 canvases."""
        bboxes = [
            self.canvas.bbox("all"),
            self.post_canvas.bbox("all"),
            self.rail_canvas.bbox("all")
        ]
        # Filter out empty canvases
        valid_boxes = [b for b in bboxes if b]
        
        if not valid_boxes:
            return (0, 0, 800, 600)

        # Take the furthest extremes across all canvases
        min_x = min(b[0] for b in valid_boxes)
        min_y = min(b[1] for b in valid_boxes)
        max_x = max(b[2] for b in valid_boxes)
        max_y = max(b[3] for b in valid_boxes)

        return (min_x, min_y, max_x, max_y)
    
    def _canvas_to_svg(self, canvas, master_bbox=None):
        """Parses objects on a Tkinter canvas to build clean vector HTML SVGs with exact text centering."""
        
        # If a master bounding box is provided (e.g. from self.canvas), use it so all SVGs align identically
        bbox = master_bbox if master_bbox else canvas.bbox("all")
        if not bbox: return '<svg width="800" height="400"><text x="20" y="40">Empty Diagram</text></svg>'
        
        x1, y1, x2, y2 = bbox
        
        # Roomy layout margins to catch extended dimensional text tags safely
        padding_left_top = 30
        padding_right_bottom = 70 
        
        w = (x2 - x1) + padding_left_top + padding_right_bottom
        h = (y2 - y1) + padding_left_top + padding_right_bottom
        offset_x = -x1 + padding_left_top
        offset_y = -y1 + padding_left_top


        # --- DEBUG LOGGING ---
        canvas_name = getattr(canvas, 'name', 'Canvas')
        #rint(f"--- DEBUG SVG EXPORT [{canvas_name}] ---")
        #rint(f"  bbox (x1, y1, x2, y2) : ({x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f})")
        #rint(f"  offset (x, y)          : ({offset_x:.1f}, {offset_y:.1f})")
        #rint(f"  total SVG size (w, h)  : ({w:.1f}, {h:.1f})")
        # ---------------------

        # Separate layers to force all text objects to draw OVER solid background shapes
        shape_elements = []
        text_elements = []
        
        for item in canvas.find_all():
            itype = canvas.type(item)
            tags = canvas.gettags(item)
            
            if "handle" in tags or "grid" in tags or "scroll" in tags:
                continue
                
            coords = canvas.coords(item)
            if not coords: continue

            adjusted_coords = []
            for i in range(len(coords)):
                if i % 2 == 0: adjusted_coords.append(coords[i] + offset_x)
                else: adjusted_coords.append(coords[i] + offset_y)

            try: fill = canvas.itemcget(item, "fill")
            except Exception: fill = "none"
                
            try: outline = canvas.itemcget(item, "outline")
            except Exception: outline = "none"
                
            try: width = canvas.itemcget(item, "width")
            except Exception: width = "1"

            if fill == "": fill = "none"
            if outline == "": outline = "none"
            if width == "" or float(width) == 0: width = "1"

            # Render shapes into the background layer list
            if itype == "rectangle" and len(adjusted_coords) >= 4:
                rx = min(adjusted_coords[0], adjusted_coords[2])
                ry = min(adjusted_coords[1], adjusted_coords[3])
                rw = abs(adjusted_coords[2] - adjusted_coords[0])
                rh = abs(adjusted_coords[3] - adjusted_coords[1])
                shape_elements.append(f'<rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" fill="{fill}" stroke="{outline}" stroke-width="{width}" />')

            elif itype == "line" and len(adjusted_coords) >= 4:
                stroke_color = fill if fill != "none" else (outline if outline != "none" else "black")

                try:
                    dash_val = canvas.itemcget(item, "dash")
                except Exception:
                    dash_val = ""

                # If a dash pattern exists in Tkinter, apply a matching stroke-dasharray in SVG
                dash_attr = ""
                if dash_val and dash_val != "0" and dash_val != '""' and dash_val != "none":
                    # "5 5" or "4 4" works beautifully for a clean, visible dashed separation line
                    dash_attr = ' stroke-dasharray="5,5"'

                if len(adjusted_coords) == 4:
                    shape_elements.append(f'<line x1="{adjusted_coords[0]}" y1="{adjusted_coords[1]}" x2="{adjusted_coords[2]}" y2="{adjusted_coords[3]}" stroke="{stroke_color}" stroke-width="{width}" stroke-linecap="round" {dash_attr}  />')
                else:
                    points_str = " ".join([f"{adjusted_coords[p]},{adjusted_coords[p+1]}" for p in range(0, len(adjusted_coords), 2)])
                    shape_elements.append(f'<polyline points="{points_str}" fill="none" stroke="{stroke_color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" {dash_attr}  />')

            elif itype == "oval" and len(adjusted_coords) >= 4:
                cx = (adjusted_coords[0] + adjusted_coords[2]) / 2
                cy = (adjusted_coords[1] + adjusted_coords[3]) / 2
                rx = abs(adjusted_coords[2] - adjusted_coords[0]) / 2
                ry = abs(adjusted_coords[3] - adjusted_coords[1]) / 2
                if rx == ry:
                    shape_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{rx}" fill="{fill}" stroke="{outline}" stroke-width="{width}" />')
                else:
                    shape_elements.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{outline}" stroke-width="{width}" />')
            
            elif itype == "polygon" and len(adjusted_coords) >= 6:
                points_str = " ".join([f"{adjusted_coords[p]},{adjusted_coords[p+1]}" for p in range(0, len(adjusted_coords), 2)])
                shape_elements.append(f'<polygon points="{points_str}" fill="{fill}" stroke="{outline}" stroke-width="{width}" />')

            # Render text into the foreground layer list
            # Render text into the foreground layer list
            # Clean, fresh multi-line text processing block
            # Render text into the foreground layer list centered precisely on coordinates
            # Render text into the foreground layer list centered precisely on coordinates


            elif itype == "text" and len(adjusted_coords) >= 2:
                text_str = canvas.itemcget(item, "text")
                if not text_str.strip(): continue

                # Get original configuration properties used by the GUI text items
                font_attr = canvas.itemcget(item, "font")
                fill_color = canvas.itemcget(item, "fill") or "black"
                anchor = canvas.itemcget(item, "anchor") or "center"

                # Safely retrieve angle parameter if set on the Tkinter canvas item
                try:
                    raw_angle = canvas.itemcget(item, "angle")
                    angle = float(raw_angle) if raw_angle else 0.0
                except Exception:
                    angle = 0.0
                
                # Simple fallback parser for Tkinter font strings (e.g., "Arial 10" or ("Arial", 10))
                font_parts = font_attr.split() if isinstance(font_attr, str) else font_attr
                font_family = "Arial"
                font_size = "12"
                if font_parts:
                    font_family = font_parts[0].replace("{", "").replace("}", "")
                    if len(font_parts) > 1:
                        font_size = font_parts[1]

                # Track positioning flags matching standard Tkinter anchors
                svg_anchor = "middle"
                if "w" in anchor:
                    svg_anchor = "start"
                elif "e" in anchor:
                    svg_anchor = "end"
                else:
                    svg_anchor = "middle"

                # Build rotation transform string if non-zero angle is set
                # Uses -angle to align Tkinter's counter-clockwise rotation with SVG's coordinate system
                transform_attr = ""
                if angle != 0:
                    transform_attr = f' transform="rotate({-angle}, {adjusted_coords[0]}, {adjusted_coords[1]})"'

                # Check if this item is part of our multi-line comment boxes
                is_comment = any(t.startswith("comment_") for t in tags) if tags else False

                if is_comment:
                    # Retrieve the comment width to safely break lines
                    box_width = 150
                    for t in tags:
                        if t in self.comment_boxes:
                            box_width = self.comment_boxes[t]['w'] - 12
                            break

                    # Approx character limit based on standard 10pt font size widths
                    chars_per_line = max(15, int(box_width / 6))
                    
                    # Wrap text cleanly by breaking on word boundaries
                    import textwrap
                    lines = textwrap.wrap(text_str, width=chars_per_line)
                    if not lines:
                        lines = [text_str]

                    # Force text-anchor="start" and dominant-baseline="text-before-edge"
                    # so wrapped lines start at top-left (cx + 6, cy + 6)
                    svg_comment = (
                        f'<text x="{adjusted_coords[0]}" y="{adjusted_coords[1]}" '
                        f'font-family="{font_family}, Arial" font-size="{font_size}px" fill="{fill_color}" '
                        f'text-anchor="start" dominant-baseline="text-before-edge"{transform_attr}>'
                    )
                    
                    line_height = int(font_size) + 4
                    for i, line in enumerate(lines):
                        dy_val = "0" if i == 0 else f"{line_height}px"
                        safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        svg_comment += f'<tspan x="{adjusted_coords[0]}" dy="{dy_val}">{safe_line}</tspan>'
                    
                    svg_comment += '</text>'
                    text_elements.append(svg_comment)
                elif "\n" in text_str:
                    # Handle multi-line section labels (e.g., RAMP 1\n93"x39-1/2")
                    lines = text_str.split("\n")
                    
                    # Force section block labels to center-align horizontally, 
                    # overriding any Tkinter 'east' or 'west' item placement anchors
                    label_anchor = "middle"

                    num_lines = len(lines)
                    initial_dy = -0.6 * (num_lines - 1)

                    svg_multiline = (
                        f'<text x="{adjusted_coords[0]}" y="{adjusted_coords[1]}" '
                        f'font-family="{font_family}, Arial" font-size="{font_size}px" fill="{fill_color}" '
                        f'text-anchor="{label_anchor}" dominant-baseline="central"{transform_attr}>'
                    )
                    
                    for i, line in enumerate(lines):
                        dy_val = f"{initial_dy}em" if i == 0 else "1.2em"
                        safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        svg_multiline += (
                            f'<tspan x="{adjusted_coords[0]}" dy="{dy_val}" '
                            f'text-anchor="{label_anchor}">{safe_line}</tspan>'
                        )
                    
                    svg_multiline += '</text>'
                    text_elements.append(svg_multiline)
                else:
                    # Standard single-line non-comment text items (dimension labels, titles, etc.)
                    safe_text = text_str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    
                    anchor_lower = anchor.lower()

                    # IF THE TEXT IS ROTATED (e.g. angle=90 for side dimension labels):
                    if angle != 0:
                        svg_anchor = "middle"
                        baseline_attr = 'dominant-baseline="central"'
                        transform_attr = f' transform="rotate({-angle}, {adjusted_coords[0]}, {adjusted_coords[1]})"'
                    else:
                        transform_attr = ""
                        # Normal anchor mapping for non-rotated horizontal text
                        if anchor_lower == "center" or anchor_lower == "":
                            svg_anchor = "middle"
                        elif "w" in anchor_lower:
                            svg_anchor = "start"
                        elif "e" in anchor_lower:
                            svg_anchor = "end"
                        else:
                            svg_anchor = "middle"

                        if "n" in anchor_lower:
                            baseline_attr = 'dominant-baseline="hanging"'
                        elif "s" in anchor_lower:
                            baseline_attr = 'dominant-baseline="auto"'
                        else:
                            baseline_attr = 'dominant-baseline="central"'

                    svg_text = (
                        f'<text x="{adjusted_coords[0]}" y="{adjusted_coords[1]}" '
                        f'font-family="{font_family}, Arial" font-size="{font_size}px" fill="{fill_color}" '
                        f'text-anchor="{svg_anchor}" {baseline_attr}{transform_attr}>'
                        f'{safe_text}</text>'
                    )
                    text_elements.append(svg_text)

        # Merge elements in the correct stacking order: background shapes first, then text labels on top
        combined_elements = shape_elements + text_elements
        svg_head = f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="background:#ffffff;">'
        return svg_head + "\n  ".join(combined_elements) + "\n</svg>"
    
    def export_to_pdf(self):
        """Compiles all views into a PDF with Maximized Diagrams and matched Stock tables."""
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not file_path: return

        pdf = pdf_canvas.Canvas(file_path, pagesize=landscape(letter))
        page_w, page_h = landscape(letter)

        # 1. CORE PROJECT VIEWS (Layout, Post Map, Handrails)
        # We target the main canvas tracks but pass the sidebar frame specifically to extract text labels
        core_views = [
            ("OVERALL PROJECT LAYOUT", self.tab_layout, self.canvas, None),
            ("POST & RAIL MAP", self.tab_posts, self.post_canvas, None),
            ("HANDRAIL DETAIL", self.tab_rails, self.rail_canvas, self.rail_sidebar)
        ]
        
        self.rail_scrape_data = [] # Reset

        for title, frame, cvs, sidebar_frame in core_views:
            # Switch tabs and force Tkinter to render the active canvas
            self.notebook.select(frame)
            self.root.update()
            
            if title == "HANDRAIL DETAIL":
                # Capture the full vector drawing diagram and generate the matched sidebar data
                self._add_canvas_to_pdf(pdf, title, cvs, page_w, page_h, has_table=True, sidebar_frame=sidebar_frame)
                
                # 2. Safely unpack your list data structure into a dictionary
                counts_dict = {96: 0, 120: 0, 144: 0}
                if hasattr(self, 'rail_final_totals') and isinstance(self.rail_final_totals, list):
                    for entry in self.rail_final_totals:
                        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                            key_str = str(entry[0]).replace('"', '').strip()
                            try:
                                # Convert variants like 96 or "96" to matching lookups
                                if "96" in key_str or "8'" in key_str: counts_dict[96] = entry[1]
                                elif "120" in key_str or "10'" in key_str: counts_dict[120] = entry[1]
                                elif "144" in key_str or "12'" in key_str: counts_dict[144] = entry[1]
                            except Exception:
                                pass

                rail_table_data = [
                    ["Stock Size", "Total Qty Needed"],
                    ["2x4x8' Lumber (96\")", f"{counts_dict.get(96, 0)} pcs"],
                    ["2x4x10' Lumber (120\")", f"{counts_dict.get(120, 0)} pcs"],
                    ["2x4x12' Lumber (144\")", f"{counts_dict.get(144, 0)} pcs"]
                ]

                # Style the Material Table with high-contrast headers matching your GUI
                t_rails = Table(rail_table_data, colWidths=[200, 120])
                t_rails.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A365D")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                ]))

                # Anchor the clean summary block clearly at the lower margin
                t_rails.wrapOn(pdf, 50, page_h - 150)
                t_rails.drawOn(pdf, 380, 35)

            else:
                # Full page renderings for general layout maps
                self._add_canvas_to_pdf(pdf, title, cvs, page_w, page_h, has_table=False, sidebar_frame=None)
            
            pdf.showPage()

        # 2. ALL DYNAMIC COMPONENT PAGES (Ramps, Decks, Steps Details)
        for tag, data in self.sections.items():
            if tag not in self.component_tabs: continue
            
            tab_info = self.component_tabs[tag]
            self.notebook.select(tab_info['frame'])
            self.root.update()

            # Render the canvas drawing layout across the top 50% of the document page
            self._add_canvas_to_pdf(pdf, f"DETAIL: {data['name']}", tab_info['canvas'], page_w, page_h, has_table=True, sidebar_frame=None)

            # Scrape active item tables
            comp_table_data = [["Stock Qty", "Size", "Cut / Part", "Length", "Qty"]]
            if 'materials_data' in data and data['materials_data']: 
                comp_table_data.extend(data['materials_data'])
            else:
                comp_table_data.append(["1", "2x4", f"{data['name']} Structure Board", f"{data.get('l', 0)}\"", "1"])

            t = Table(comp_table_data, colWidths=[70, 90, 200, 110, 50])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2E7D32")), # Accent green header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
                ('TOPPADDING', (0, 1), (-1, -1), 5),
            ]))

            t.wrapOn(pdf, page_w, page_h)
            t.drawOn(pdf, 50, 35)
                
            pdf.showPage()

        pdf.save()
        messagebox.showinfo("Success", "All Diagrams and Materials Exported to PDF!")


    def _add_canvas_to_pdf(self, pdf, title, canvas, page_w, page_h, has_table=False, sidebar_frame=None):
        """Vector-captures full scroll regions of canvas tracks, bypassing viewport clipping."""
        import io
        from PIL import Image

        # 1. BOOST FONTS FOR HIGH LEGIBILITY BLUEPRINTS
        original_fonts = {}
        for item in canvas.find_all():
            if canvas.type(item) == "text":
                current_font = canvas.itemcget(item, "font")
                original_fonts[item] = current_font
                canvas.itemconfig(item, font=("Arial", 12, "bold"))

        # 2. FORCE POSTSCRIPT TO USE FULL SCROLLABLE AREA BOUNDARIES
        # This prevents large, multi-section layout designs from getting clipped
        bbox = canvas.bbox("all")
        if not bbox: bbox = (0, 0, 800, 400)
        x1, y1, x2, y2 = bbox
        
        # Calculate full dimension ranges across the infinite grid space
        width = x2 - x1
        height = y2 - y1

        # CRITICAL FIX: explicitly supply x, y, width, and height to force full grid exports
        ps_data = canvas.postscript(
            colormode='color', 
            x=x1, 
            y=y1, 
            width=width, 
            height=height,
            pagewidth=width, 
            pageheight=height
        )
        
        # Restore native app fonts immediately
        for item, font in original_fonts.items():
            canvas.itemconfig(item, font=font)

        # 3. CONVERT RAW EPS DATA TO IMAGE BUFFER
        img_main = Image.open(io.BytesIO(ps_data.encode('utf-8')))
        img_buffer = io.BytesIO()
        img_main.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        # 4. DRAW PAGE HEADERS AND BORDERS
        pdf.setFont("Helvetica-Bold", 18)
        pdf.setFillColor(colors.black) 
        pdf.drawString(50, page_h - 45, title)
        pdf.line(50, page_h - 50, page_w - 50, page_h - 50)

        # Calculate canvas drawing height boundaries
        if has_table:
            available_h = page_h * 0.55
            start_y = page_h - available_h - 65
        else:
            available_h = page_h - 130
            start_y = 60

        pdf.drawImage(pdf_canvas.ImageReader(img_buffer), 50, start_y, 
                      width=page_w-100, height=available_h, 
                      preserveAspectRatio=True, mask='auto')

        # 5. IF SIDEBAR DATA EXISTS, RENDER THE LEGEND DIRECTLY VIA REPORTLAB VECTOR TABLES
        # This completely replaces unreliable frame screenshotting or Pillow font mapping bugs.
        if sidebar_frame:
            legend_data = [["Color Key", "Shared Post Specification"]]
            
            for child in sidebar_frame.winfo_children():
                if isinstance(child, (tk.Frame, ttk.Frame)):
                    sub_children = child.winfo_children()
                    bg_color = None
                    lbl_text = ""
                    
                    for sub in sub_children:
                        if isinstance(sub, tk.Label):
                            txt = sub.cget("text")
                            bg = sub.cget("bg")
                            # Snag structural color tags
                            if bg and bg not in ("SystemButtonFace", "#f0f0f0", "white", "#ffffff"):
                                bg_color = bg
                            if txt:
                                lbl_text += " " + txt

                    lbl_text = lbl_text.strip()
                    if lbl_text and bg_color:
                        legend_data.append(["", lbl_text])

            if len(legend_data) > 1:
                # Build a dedicated vector legend block table
                t_legend = Table(legend_data, colWidths=[40, 240])
                t_styles = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#334155")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ]

                # Map color bars directly to row index boxes dynamically matching your UI hex styles
                for idx, row in enumerate(legend_data):
                    if idx == 0: continue
                    # Re-extract background color assignments matching current row index
                    row_bg = None
                    lbl_counter = 1
                    for child in sidebar_frame.winfo_children():
                        if isinstance(child, (tk.Frame, ttk.Frame)):
                            for sub in child.winfo_children():
                                if isinstance(sub, tk.Label):
                                    bg = sub.cget("bg")
                                    if bg and bg not in ("SystemButtonFace", "#f0f0f0", "white", "#ffffff"):
                                        if lbl_counter == idx:
                                            row_bg = bg
                                        lbl_counter += 1
                    if row_bg:
                        t_styles.append(('BACKGROUND', (0, idx), (0, idx), colors.HexColor(row_bg)))

                t_legend.setStyle(TableStyle(t_styles))
                t_legend.wrapOn(pdf, 50, page_h - 150)
                t_legend.drawOn(pdf, 50, 35)

    def get_timestamp(self):
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    def save_project(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".ramp")
        if not file_path:
            return

        try:
            self.deselect_all_main()
            self.refresh_materials_matrix()

            # 1. Find all active post blocks on the canvas to explicitly determine which posts use them
            active_blocks = []
            for item in self.post_canvas.find_withtag("post_block"):
                tags = self.post_canvas.gettags(item)
                for t in tags:
                    if t.startswith("block_P"):
                        post_tag = t.replace("block_", "")
                        if post_tag not in active_blocks:
                            active_blocks.append(post_tag)

            # 2. Update Section Coordinates (Layout Canvas)
            for tag in self.sections:
                item = self.canvas.find_withtag(
                    f"{tag} && shape"
                ) or self.canvas.find_withtag(tag)
                if item:
                    coords = self.canvas.coords(item[0])
                    if coords:
                        # Save exact shape coordinate array
                        self.sections[tag]["points"] = coords

                        # Store bounding box coordinates for x1, y1, x2, y2 as fallback
                        self.sections[tag]["x1"] = min(coords[::2])
                        self.sections[tag]["y1"] = min(coords[1::2])
                        self.sections[tag]["x2"] = max(coords[::2])
                        self.sections[tag]["y2"] = max(coords[1::2])

                text_item = self.canvas.find_withtag(f"{tag} && text")
                if text_item:
                    full_label = self.canvas.itemcget(text_item[0], "text")
                    self.sections[tag]["full_label_text"] = full_label

            clean_sections = {}
            for tag, data in self.sections.items():
                section_copy = {
                    k: v
                    for k, v in data.items()
                    if k not in ["tab_id", "canvas", "table", "label"]
                }

                if "lumber_counts" in data:
                    section_copy["lumber_counts"] = {
                        f"{k[0]}_{k[1]}": v for k, v in data["lumber_counts"].items()
                    }

                clean_sections[tag] = section_copy

            # 3. Extract Post Data AND Visual Coordinates (Post Canvas)
            clean_posts = {}

            for p_id, p_data in self.post_entries.items():
                post_item = self.post_canvas.find_withtag(p_id)
                post_coords = (
                    self.post_canvas.coords(post_item[0])
                    if post_item
                    else [0, 0, 0, 0]
                )

                if len(post_coords) >= 4:
                    # Store dynamic centroid-derived label coords if needed
                    cx = sum(post_coords[::2]) / (len(post_coords) / 2)
                    cy = sum(post_coords[1::2]) / (len(post_coords) / 2)
                    label_coords = [cx, cy - 12]
                else:
                    label_coords = [0, 0]

                is_dummy_attr = p_data.get("is_dummy", False)
                bot_step_attr = p_data.get("bot_step", False)
                bot_ramp_attr = p_data.get("bot_ramp", False)
                og_grade_attr = p_data.get("og_grade")
                is_inset_attr = p_data.get("is_inset", False)

                # Safely evaluate and convert entry values
                clean_posts[p_id] = {
                    "deck": (
                        p_data["deck"].get()
                        if hasattr(p_data["deck"], "get")
                        else p_data["deck"]
                    ),
                    "grade": (
                        p_data["grade"].get()
                        if hasattr(p_data["grade"], "get")
                        else p_data["grade"]
                    ),
                    "below": (
                        p_data["below"].get()
                        if hasattr(p_data["below"], "get")
                        else p_data["below"]
                    ),
                    "total": (
                        p_data["total"].get()
                        if hasattr(p_data["total"], "get")
                        else p_data["total"]
                    ),
                    "canvas_coords": post_coords,
                    "label_coords": label_coords,
                    "is_dummy": (
                        is_dummy_attr.get()
                        if hasattr(is_dummy_attr, "get")
                        else is_dummy_attr
                    ),
                    "bot_step": (
                        bot_step_attr.get()
                        if hasattr(bot_step_attr, "get")
                        else bot_step_attr
                    ),
                    "bot_ramp": (
                        bot_ramp_attr.get()
                        if hasattr(bot_ramp_attr, "get")
                        else bot_ramp_attr
                    ),
                    "og_grade": (
                        og_grade_attr.get()
                        if hasattr(og_grade_attr, "get")
                        else (og_grade_attr if og_grade_attr is not None else "0.0")
                    ),
                    "is_inset": (
                        is_inset_attr.get()
                        if hasattr(is_inset_attr, "get")
                        else is_inset_attr
                    ),
                }

            # 4. Get rail locations and data
            for tag in self.rail_entries:
                item = self.rail_canvas.find_withtag(tag)
                if item:
                    coords = self.rail_canvas.coords(item[0])
                    if coords:
                        self.rail_entries[tag]["canvas_coords"] = coords
                        self.rail_entries[tag]["x1"] = coords[0]
                        self.rail_entries[tag]["y1"] = coords[1]
                        self.rail_entries[tag]["x2"] = (
                            coords[2] if len(coords) >= 4 else coords[0]
                        )
                        self.rail_entries[tag]["y2"] = (
                            coords[3] if len(coords) >= 4 else coords[1]
                        )

            clean_rails = {
                tag: {
                    k: v
                    for k, v in data.items()
                    if k not in ["tab_id", "canvas", "table", "label"]
                }
                for tag, data in self.rail_entries.items()
            }

            # 5. Package and Save
            serialized_comments = []
            canvas_mapping = {
                self.canvas: "layout",
                self.post_canvas: "posts",
                self.rail_canvas: "rails",
            }

            for dynamic_tag, tab_info in self.component_tabs.items():
                if "canvas" in tab_info:
                    canvas_mapping[tab_info["canvas"]] = dynamic_tag

            for bid, data in self.comment_boxes.items():
                serialized_comments.append({
                    "text": data["text"],
                    "x": data["x"],
                    "y": data["y"],
                    "w": data["w"],
                    "h": data["h"],
                    "target": canvas_mapping.get(data["canvas_ref"], "layout"),
                })

            project_state = {
                "sections": clean_sections,
                "posts": clean_posts,
                "cross_braces": self.cross_brace_entries,
                "total_drop": (
                    self.total_drop_val.get()
                    if hasattr(self.total_drop_val, "get")
                    else getattr(self, "total_drop_val", 0)
                ),
                "manual_override_active": getattr(
                    self, "manual_override_active", False
                ),
                "saved_boards_layout": getattr(self, "boards", []),
                "rails": clean_rails,
                "pair_label_positions": self.pair_label_positions,
                "comment_boxes": serialized_comments,
                "post_block_count": getattr(self, "post_block_count", 0),
                "active_post_blocks": active_blocks,
            }

            # Explicit UTF-8 encoding prevents crashes on Windows with special characters
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(project_state, f, indent=4)

            messagebox.showinfo("Success", "Project saved with exact UI positions!")

        except Exception as e:
            # Intercepts any execution error and displays full stack trace in a GUI dialog
            error_details = traceback.format_exc()
            messagebox.showerror(
                "Save Failed",
                f"An error occurred while saving the project:\n\n{error_details}",
            )
    
    def on_click(self, event):
        print ("On click")
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        item = self.canvas.find_closest(canvas_x, canvas_y)[0]
        print (item)
        tags = self.canvas.gettags(item)
        print (tags)
        for tag in tags:
            if tag in self.sections:
                self.active_tag = tag
                break
        self._drag_data["item"] = item
        self._drag_data["x"] = canvas_x
        self._drag_data["y"] = canvas_y
        print (self._drag_data["x"])

    def on_release(self, event):
        self._drag_data["item"] = None
        self.active_tag = None

    def load_project(self):
        file_path = filedialog.askopenfilename(filetypes=[("Ramp Files", "*.ramp")])
        if not file_path:
            return

        # Reset counters
        self.ramp_count = 0
        self.taper_ramp_count = 0
        self.threshold_ramp_count = 0
        self.post_count = 0
        self.landing_count = 0
        self.step_count = 0
        self.paver_count = 0
        self.paver_total = 0
        self.post_block_count = 0

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            # 1. Clear current UI
            self.canvas.delete("all")
            self.post_canvas.delete("all")
            self.rail_canvas.delete("all")
            self.manual_override_active = data.get("manual_override_active", False)
            
            self.pair_label_positions = data.get("pair_label_positions", {})
            
            for tag in list(self.component_tabs.keys()):
                try:
                    self.notebook.forget(self.component_tabs[tag]["frame"])
                except: 
                    pass
            
            self.sections = data.get("sections", {})

            #rint("Sections")
            #rint(self.sections)
            self.total_drop_val = data.get("total_drop", 0.0)
            self.post_block_count = data.get("post_block_count", 0)
            active_post_blocks = data.get("active_post_blocks", [])

            # 2. Rebuild Component Tabs and Layout
            self.component_tabs = {} 
            for tag, s_data in self.sections.items():
                if 'lumber_counts' in data:
                    restored_counts = {}
                    for k_str, qty in data['lumber_counts'].items():
                        parts = k_str.split('_')
                        restored_counts[(parts[0], int(parts[1]))] = qty
                    data['lumber_counts'] = restored_counts
                if tag != "REF_POINT" and not tag.startswith("Paver"): 
                    self.create_component_tab(tag)

            self.redraw_all()

            # 3. Load Posts from File (Instead of calling generate_posts)
            self.post_entries = {}
            posts_from_file = data.get("posts", {})
            self._post_drag_data = {"item": None, "x": 0, "y": 0}   # reset this on load for drag

            # --- Background Reference for Post Canvas (UPDATED FOR POLYGONS) ---
            for tag, s_data in self.sections.items():
                sid = self.canvas.find_withtag(f"{tag} && shape")[0]
                c = self.canvas.coords(sid)
                
                # Check array length: >4 means arbitrary polygon coords
                if len(c) > 4:
                    self.post_canvas.create_polygon(c, outline="#bbb", fill="", dash=(4,4))
                    cx = sum(c[::2]) / (len(c) / 2)
                    cy = sum(c[1::2]) / (len(c) / 2)
                    self.post_canvas.create_text(cx, cy, text=s_data['name'], fill="#999", font=("Arial", 10, "bold"))
                else:
                    self.post_canvas.create_rectangle(*c, outline="#bbb", dash=(4,4))
                    self.post_canvas.create_text((c[0]+c[2])/2, (c[1]+c[3])/2, text=s_data['name'], fill="#999", font=("Arial", 10, "bold"))

            # Reconstruct each post from JSON
            self.post_table_data = []
            for p_id, p_info in posts_from_file.items():
                raw_dummy_val = p_info.get("is_dummy", "False")
                raw_is_inset = p_info.get("is_inset", "False")

                self.post_entries[p_id] = {
                    'deck': tk.StringVar(value=p_info["deck"]),
                    'grade': tk.StringVar(value=p_info["grade"]),
                    'below': tk.StringVar(value=p_info["below"]),
                    'total': tk.StringVar(value=p_info["total"]),
                    'canvas_coords': p_info["canvas_coords"],
                    'label_coords': p_info["label_coords"],
                    'is_dummy': tk.StringVar(value=str(raw_dummy_val)),
                    'bot_step': tk.StringVar(value=p_info['bot_step']),
                    'bot_ramp': tk.StringVar(value=p_info['bot_ramp']),
                    'og_grade': tk.StringVar(value=p_info.get("og_grade", "0.0")), # <-- SAFE FALLBACK
                    'is_inset': tk.StringVar(value=str(raw_is_inset))
                }
                
                if isinstance(raw_dummy_val, str):
                    is_dummy = raw_dummy_val.lower() == "true"
                else:
                    is_dummy = bool(raw_dummy_val)
                
                #rint(f"Post {p_id} is {is_dummy}")

                if isinstance(raw_is_inset, str):
                    is_inset = raw_is_inset.lower() == "true"
                else:
                    is_inset = bool(raw_is_inset)
                
                # Fallback check for old naming conventions if key is missing
                if "(D)" in p_id or "dummy" in p_id:
                    is_dummy = True
                
                fill_color = "#e0e0e0" if is_dummy else "white"
                outline_color = "blue" if is_dummy else "black"
                label_text = p_id + (" (D)" if is_dummy and "(D)" not in p_id else "")
                
                label_text = f"{label_text} (i)" if is_inset else label_text
                
                coords = p_info["canvas_coords"]
                l_coords = p_info["label_coords"]
                bot_step = p_info["bot_step"]
                bot_ramp = p_info['bot_ramp']
                og_grade = p_info['og_grade']

                # --- UPDATED: Render Post as Polygon vs Rectangle ---
                if len(coords) > 4:
                    self.post_canvas.create_polygon(
                        coords, 
                        fill=fill_color, 
                        outline=outline_color, 
                        tags=(p_id, "movable_post", "post_border")
                    )
                else:
                    self.post_canvas.create_rectangle(
                        *coords, 
                        fill=fill_color, 
                        outline=outline_color, 
                        tags=(p_id, "movable_post", "post_border")
                    )

                self.post_canvas.create_text(*l_coords, text=label_text, font=("Arial", 10, "bold"), tags=(p_id, "movable_post"))
                
                # --- UPDATED: Post Block Outline Rendering ---
                if p_id in active_post_blocks:
                    block_pnum = f"block_{p_id}"
                    if len(coords) > 4:
                        cx = sum(coords[::2]) / (len(coords) / 2)
                        cy = sum(coords[1::2]) / (len(coords) / 2)
                        
                        buffered_pts = []
                        for i in range(0, len(coords), 2):
                            px, py = coords[i], coords[i+1]
                            buffered_pts.append(px + (4 if px >= cx else -4))
                            buffered_pts.append(py + (4 if py >= cy else -4))
                            
                        self.post_canvas.create_polygon(
                            buffered_pts, fill="", outline="gray", width=2,
                            tags=(block_pnum, (p_id, "movable_post", "post_border"), "post_block", "block_border")
                        )
                    elif len(coords) == 4:
                        x1, y1, x2, y2 = coords
                        buf = 4
                        self.post_canvas.create_rectangle(
                            x1 - buf, y1 - buf, x2 + buf, y2 + buf,
                            fill="", outline="gray", width=buf,
                            tags=(block_pnum, (p_id, "movable_post", "post_border"), "post_block", "block_border")
                        )
                    self.bind_item(block_pnum)

                self.bind_item(p_id)
                self.post_count = int(p_id.replace("P", "")) + 1

                num_id = int(''.join(filter(str.isdigit, p_id)))
                self.post_table_data.append((num_id, is_dummy, tag, float(p_info["grade"]), bot_step, bot_ramp, og_grade, is_inset))

            self.cross_brace_entries = {}
            saved_braces = data.get("cross_braces", {})
            
            for b_tag, b_data in saved_braces.items():
                self.cross_brace_entries[b_tag] = b_data
                if 'canvas_coords' in b_data:
                    coords = b_data['canvas_coords']
                else:
                    continue
                    
                if len(coords) > 4:
                    self.post_canvas.create_polygon(
                        coords, fill="#8B4513", outline="black", tags=(b_tag, "movable_post", "cross_brace")
                    )
                else:
                    self.post_canvas.create_rectangle(
                        *coords, fill="#8B4513", outline="black", tags=(b_tag, "movable_post", "cross_brace") 
                    )
                
                if 'label_coords' in b_data:
                    l_coords = b_data['label_coords']
                    self.post_canvas.create_text(
                        *l_coords, text=b_tag, font=("Arial", 9, "bold"), tags=(f"label_{b_tag}", "movable_post")
                    )
                else:
                    cx = sum(coords[::2]) / (len(coords) / 2)
                    cy = sum(coords[1::2]) / (len(coords) / 2)
                    self.post_canvas.create_text(
                        cx, cy, text=b_tag, font=("Arial", 9, "bold"), tags=(f"label_{b_tag}", "movable_post")
                    )
                self.bind_item(b_tag)

            if self.cross_brace_entries:
                try:
                    max_idx = max([int(str(k).replace("CrossBrace", "")) for k in self.cross_brace_entries.keys() if "CrossBrace" in str(k)])
                    self.postbrace_count = max_idx + 1
                except ValueError:
                    pass

            self.post_table_data.sort(key=lambda x: x[0])
            self.update_post_table_from_load(self.post_table_data)
            self.addCrossBrace_btn.pack(side=tk.RIGHT, padx=20)

            # 5. Load Data for Rails
            self.rail_entries = {}
            rails_from_file = data.get("rails", {})
            self._rail_drag_data = {"item": None, "x": 0, "y": 0} 

            # --- Background Reference for Rail Canvas (UPDATED FOR POLYGONS) ---
            for tag, s_data in self.sections.items():
                sid = self.canvas.find_withtag(f"{tag} && shape")[0]
                c = self.canvas.coords(sid)
                
                if len(c) > 4:
                    self.rail_canvas.create_polygon(c, outline="#bbb", fill="", dash=(4,4))
                    cx = sum(c[::2]) / (len(c) / 2)
                    cy = sum(c[1::2]) / (len(c) / 2)
                    self.rail_canvas.create_text(cx, cy, text=s_data['name'], fill="#999", font=("Arial", 10, "bold"))
                else:
                    self.rail_canvas.create_rectangle(*c, outline="#bbb", dash=(4,4))
                    self.rail_canvas.create_text((c[0]+c[2])/2, (c[1]+c[3])/2, text=s_data['name'], fill="#999", font=("Arial", 10, "bold"))

            for p_id, p_info in posts_from_file.items():
                p_coords = p_info["canvas_coords"]
                is_dummy = "(D)" in p_id or "dummy" in p_id
                p_fill = "#f0f0f0" if is_dummy else "#e1e1e1"
                p_outline = "#ccc" if is_dummy else "#999"

                if len(p_coords) > 4:
                    self.rail_canvas.create_polygon(
                        p_coords, fill=p_fill, outline=p_outline, width=1, tags=(p_id, "bg_post")
                    )
                else:
                    self.rail_canvas.create_rectangle(
                        *p_coords, fill=p_fill, outline=p_outline, width=1, tags=(p_id, "bg_post")
                    )

            # Recreate and physically draw all individual rail segments on the canvas
            for r_id, r_info in rails_from_file.items():
                coords = r_info.get("canvas_coords", [])
                
                x1 = r_info.get("x1", coords[0] if len(coords) >= 2 else 0)
                y1 = r_info.get("y1", coords[1] if len(coords) >= 2 else 0)
                x2 = r_info.get("x2", coords[2] if len(coords) >= 4 else 0)
                y2 = r_info.get("y2", coords[3] if len(coords) >= 4 else 0)

                p_type = r_info.get("ptype", "RAMP")
                r_name = r_info.get("pname") or r_info.get("name", "")

                # Pass coords explicitly so angled shapes render correctly!
                self.draw_rail_segment(x1, y1, x2, y2, p_type, r_id, r_name, coords=coords)
                
                try:
                    num_id = int(''.join(filter(str.isdigit, r_id)))
                    if not hasattr(self, 'rail_count') or num_id >= self.rail_count:
                        self.rail_count = num_id + 1
                except ValueError:
                    pass
            
            #rint("override flag")
            #rint(self.manual_override_active)

            # Process pairings loop AFTER draw_rail_segment assigns live ids
            if self.manual_override_active:
                #rint("\n=== START LOAD PROJECT DEBUG ===")
                #rint(f"Initial manual_override_active flag: {self.manual_override_active}")
                #rint(f"Available keys in self.rail_entries: {list(self.rail_entries.keys())}")

                raw_saved_boards = data.get("saved_boards_layout", [])
                #rint(f"Found {len(raw_saved_boards)} saved boards in JSON.")
                
                updated_boards = []
                for b_idx, board in enumerate(raw_saved_boards):
                    new_items = []
                    #rint(f"\nProcessing Board #{b_idx} (Size: {board.get('size')}\")")
                    
                    for item in board.get('items', []):
                        rail_key = item.get('rail')
                        old_id = item.get('id')
                        
                        #rint(f"  - Item demands rail key: '{rail_key}' (Old ID from file: {old_id})")
                        
                        if hasattr(self, 'rail_entries') and rail_key in self.rail_entries:
                            new_id = self.rail_entries[rail_key].get('id')
                            item['id'] = new_id
                            #rint(f"    SUCCESS: Found matching live ID in self.rail_entries -> New ID: {new_id}")
                        else:
                            print(f"    WARNING: '{rail_key}' NOT FOUND in self.rail_entries!")
                        
                        new_items.append(item)
                    
                    board['items'] = new_items
                    updated_boards.append(board)

                self.boards = updated_boards
                self.last_rail_boards = updated_boards
                
                # Clear previous artifacts
                self.rail_canvas.delete("pair_link")
                self.rail_canvas.delete("text")
                
                #rint("\nTriggering rail_combined_materialColor(manual_override=True)...")
                self.rail_combined_materialColor(manual_override=True)
                
                #rint(f"Generated rail_colors length: {len(getattr(self, 'rail_colors', {}))}")
                #rint(f"Sample mapping of rail_colors: {self.rail_colors}")
                
                self.draw_legend_and_tables(
                    self.last_rail_boards, 
                    self.last_rail_colors, 
                    self.last_rail_pairing_data
                )
            else:
                #rint("\nManual override not active. Running standard automatic processing path...")
                self.rail_combined_materialColor(manual_override=False)

            #rint("=== END LOAD PROJECT DEBUG ===\n")

            self.addrail_btn.pack(side=tk.RIGHT, padx=20)

            # Process comment boxes
            for bid, c_info in self.comment_boxes.items():
                if 'canvas_ref' in c_info and c_info['canvas_ref'].winfo_exists():
                    c_info['canvas_ref'].delete(bid)
            self.comment_boxes.clear()

            canvas_lookup = {
                "layout": self.canvas, 
                "posts": self.post_canvas, 
                "rails": self.rail_canvas
            }
            
            for dynamic_tag, tab_info in self.component_tabs.items():
                if 'canvas' in tab_info:
                    canvas_lookup[dynamic_tag] = tab_info['canvas']

            stored_comments = data.get("comment_boxes", [])
            for idx, item in enumerate(stored_comments):
                box_id = f"comment_{idx}"
                target_key = item.get('target', 'layout')
                target_canvas = canvas_lookup.get(target_key, self.canvas)
                
                self.comment_boxes[box_id] = {
                    'text': item.get('text', ''),
                    'x': float(item.get('x', 200)),
                    'y': float(item.get('y', 200)),
                    'w': float(item.get('w', 150)),
                    'h': float(item.get('h', 60)),
                    'canvas_ref': target_canvas
                }
                
                self.render_comment_box_ui(box_id)
            
            self.update_total_drop()
            self.refresh_materials_matrix()

            messagebox.showinfo("Success", "Project and Post Map loaded from file!")

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Load Error", f"Failed to load: {e}")

    def update_post_table_from_load(self, posts_data):
        #"""Refreshes the table UI using already existing StringVars in self.post_entries"""
        for widget in self.post_grid.winfo_children():
            widget.destroy()

        headers = ["#", "Above Deck", "Above Grade", "Below Grade", "Total Length"]
        for c, h in enumerate(headers):
            tk.Label(self.post_grid, text=h, font=("Arial", 8, "bold"), relief="solid", bg="#eee").grid(row=0, column=c, sticky="nsew")
        print (posts_data)
        for r_idx, (post_num, is_dummy, parent_tag,grade, bot_step, bot_ramp,og_grade,is_inset) in enumerate(posts_data):
            p_key = f"P{post_num}"
            if p_key not in self.post_entries: continue
            
            data = self.post_entries[p_key]
            display_name = p_key + (" (D)" if is_dummy else "")
            display_name = display_name + (" (i)" if is_inset else "")
            
            tk.Label(self.post_grid, text=display_name, relief="solid", bg="white").grid(row=r_idx+1, column=0, sticky="nsew")
            
            # Re-link the trace so the Total Length updates when users edit loaded values
            for var in [data['deck'], data['grade'], data['below']]:
                var.trace_add("write", lambda *args, p=p_key: self.calculate_total_length(p))
                
            tk.Entry(self.post_grid, textvariable=data['deck'], width=8, justify='center').grid(row=r_idx+1, column=1, sticky="nsew")
            tk.Entry(self.post_grid, textvariable=data['grade'], width=8, justify='center').grid(row=r_idx+1, column=2, sticky="nsew")
            tk.Entry(self.post_grid, textvariable=data['below'], width=8, justify='center').grid(row=r_idx+1, column=3, sticky="nsew")
            tk.Label(self.post_grid, textvariable=data['total'], relief="solid", bg="#f0f0f0").grid(row=r_idx+1, column=4, sticky="nsew")

        self.post_opt_inner = tk.Frame(self.post_grid, bg="white")
        self.post_opt_inner.grid(row=999, column=0, columnspan=5, pady=20, sticky="ew")
        self.update_post_optimization()

    def redraw_all(self):
        self.canvas.delete("all")
        tag_list = list(self.sections.keys())

        for tag, data in self.sections.items():
            idx = tag_list.index(tag)
            x1 = data.get('x1', 150 + (idx * 40))
            y1 = data.get('y1', 150 + (idx * 40))
            x2 = data.get('x2', 150 + (idx * 40))
            y2 = data.get('y2', 150 + (idx * 40))
            p_type = data.get('p_type', '')
            
            # Increment section counters
            if p_type == "RAMP": self.ramp_count += 1
            elif p_type == "TAPER RAMP": self.taper_ramp_count += 1
            elif p_type == "THRESH RAMP": self.threshold_ramp_count += 1
            elif p_type == "DECK": self.landing_count += 1
            elif p_type == "STEP": self.step_count += 1
            elif p_type == "Paver":
                paver_column = int(data.get('l', 24) / 24)
                paver_row = int(data.get('w', 24) / 24)
                self.paver_total += paver_column * paver_row
                self.paver_count += 1
                pavnum = f"PaverCount{paver_column * paver_row}"

            # --- POLYGON CONVERSION ---
            # Get explicit point array or generate standard bounding box points
            pts = data.get('points', [x1, y1, x2, y1, x2, y2, x1, y2])
            taglist = (tag, p_type, "shape", pavnum) if p_type == "Paver" else (tag, p_type, "shape")

            # Always draw via create_polygon
            rect = self.canvas.create_polygon(
                pts,
                fill=data.get('color', 'gray'),
                outline="black",
                width=2 if p_type == "POLYGON" else 1,
                tags=taglist
            )

            if p_type == "Paver":
                for i in range(1, paver_column):
                    paver_offset = (i * 12) * self.scale
                    self.canvas.create_line(x1 + paver_offset, y1, x1 + paver_offset, y2, fill="black", width=1, tags=(tag, "paver_line"))
                for i in range(1, paver_row):
                    paver_offset = (i * 12) * self.scale
                    self.canvas.create_line(x1, y1 + paver_offset, x2, y1 + paver_offset, fill="black", width=1, tags=(tag, "paver_line"))  
                
                plcoord = (x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2)
                self.canvas.create_text(plcoord, text=tag, font=("Arial", 10), tags=(tag, "Paver"))

            self.bind_item(tag)

            # Calculate centroid for section label
            if len(pts) >= 6:
                center_x = sum(pts[::2]) / (len(pts) / 2)
                center_y = sum(pts[1::2]) / (len(pts) / 2)
            else:
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2

            self.canvas.create_text(
                center_x, center_y,
                text=data.get('full_label_text', ''),
                tags=(f"label_{tag}", tag, "text")
            )
            

    def setup_rails_tab(self):
        """Updated setup with a sidebar for materials, legend, and canvas scrollbars."""
        # Main container for the tab
        self.rail_main_frame = tk.Frame(self.tab_rails)
        self.rail_main_frame.pack(expand=True, fill="both")

        # Top Control Bar
        self.rail_control_frame = tk.Frame(self.rail_main_frame)
        self.rail_control_frame.pack(side="top", fill="x", padx=5, pady=5)

        tk.Button(self.rail_control_frame, text="Generate Rail Details", 
                  command=self.generate_rails, bg="#4CAF50", fg="white").pack(side="left")

        tk.Button(self.rail_control_frame, text="Add Comment Box", command=lambda: self.spawn_comment_box(self.rail_canvas),bg="#F08AF3", fg="black",font=("Arial", 10, "bold")).pack(side="right")
        # Place this near your other button code
        self.addrail_btn = tk.Button(self.rail_control_frame, text="ADD RAIL", command=self.spawn_rail, 
                  bg="#28a745", fg="white", font=("Arial", 10, "bold"))#.pack(side=tk.RIGHT, padx=20)

        tk.Button(self.rail_control_frame,text="MANUALLY EDIT PAIRINGS", command=self.open_pairing_editor, 
                    bg="#ff9800", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=20)
        
        #tk.Button(self.rail_control_frame, text="DebugRail Details", 
        #          command=self.debug_rails, bg="#4CAF50", fg="white").pack(side="left")
        
        self.delete_rail_btn = tk.Button(
            self.rail_control_frame,text="Delete Rail", 
            command= self.delete_selected_rail, # Pass None if calling manually
            bg="#de2e2e", fg="white", font=("Arial", 10, "bold")
            )
        #tk.Label(self.rail_control_frame, text="  (D: Delete, Drag: Move)").pack(side="left")

        # Right Sidebar for Tables
        self.rail_sidebar = tk.Canvas(self.rail_main_frame, width=300, bg="#f8f9fa", highlightthickness=0)
        self.rail_sidebar.pack(side="right", fill="y", padx=5, pady=5)

        # 1. Create a parent container frame for the rail canvas and scrollbars on the left
        rail_canvas_container = ttk.Frame(self.rail_main_frame)
        rail_canvas_container.pack(side="left", expand=True, fill="both")

        # Configure container weights so the canvas expands dynamically
        rail_canvas_container.grid_rowconfigure(0, weight=1)
        rail_canvas_container.grid_columnconfigure(0, weight=1)

        # 2. Create vertical and horizontal scrollbars inside the container frame
        rail_v_scroll = ttk.Scrollbar(rail_canvas_container, orient="vertical")
        rail_v_scroll.grid(row=0, column=1, sticky="ns")

        rail_h_scroll = ttk.Scrollbar(rail_canvas_container, orient="horizontal")
        rail_h_scroll.grid(row=1, column=0, sticky="ew")

        # 3. Create the Main Design Canvas with scroll linkage and an initial scrollregion matching your standard bounds
        self.rail_canvas = tk.Canvas(
            rail_canvas_container, 
            bg="white", 
            width=900, 
            height=800,
            yscrollcommand=rail_v_scroll.set,
            xscrollcommand=rail_h_scroll.set,
            scrollregion=(0, 0, 1450, 950)
        )
        self.rail_canvas.grid(row=0, column=0, sticky="nsew")

        # 4. Link scrollbars to control the rail canvas view
        rail_v_scroll.config(command=self.rail_canvas.yview)
        rail_h_scroll.config(command=self.rail_canvas.xview)

        # Bindings
        self.rail_canvas.bind("<Button-1>", self.deselect_all_rail, add="+")

        #self.rail_canvas.bind("<Button-1>", self.on_rail_drag_start)
        #self.rail_canvas.bind("<B1-Motion>", self.on_rail_drag)
        self.rail_canvas.bind("<r>", self.rotate_rail_item)
        self.rail_canvas.bind("<R>", self.rotate_rail_item)

        
    def update_total_drop(self):
        """Calculates total ramp length and updates the floating canvas label in half-inch increments"""
        raw_drop = 0
        for tag, data in self.sections.items():
            print (f"Data - {data}")
            if "RAMP" in data['name'].upper() and not "THRESH RAMP" in data['name'].upper() :
                slope = data.get('sl', 5)
                if slope is None:
                    slope = 5
                
                raw_drop += data['l'] * slope/5/12
        
        # Calculate raw drop
        #raw_drop = total_ramp_inches / 12.0
        self.total_drop_val = raw_drop
        
        # Format using your existing half-inch logic
        formatted_drop = self.format_incheshalf(raw_drop)
        
        if self.canvas.find_withtag("drop_label"):
            self.canvas.itemconfig("drop_label", text=f"Total Drop: {formatted_drop}")
        else:
            # Default placement: Top Middle of the canvas (approx 725 for 1450 width)
            lx, ly = 725, 30
            tag = "drop_label"
            self.canvas.create_text(lx, ly, text=f"Total Drop: {formatted_drop}", 
                                   font=("Arial", 14, "bold"), fill="blue", tags=(tag, "movable_label"))
            self.canvas.tag_bind(tag, "<ButtonPress-1>", self.on_start_drag)
            self.canvas.tag_bind(tag, "<B1-Motion>", self.on_drag)
    
    def calculate_elevations(self):
        """Calculates start and end elevations for each section in sequence."""
        current_elevation = self.total_drop_val
        for tag, data in self.sections.items():
            print (f"Data - {data}")
            data['elev_start'] = current_elevation
            if "RAMP" in data['name'].upper() and not "THRESH" in data['name'].upper():
                slope = data.get('sl', 5)
                if slope is None:
                    slope = 5
                drop = data['l'] * slope/5/12 #data['l'] / 12.0
                data['elev_end'] = current_elevation - drop
                current_elevation -= drop
            else:
                data['elev_end'] = current_elevation

    def format_inchesquarter(self, val):
        whole = int(val)
        remainder = val - whole
        if remainder > 0.75: return f'{whole + 1}"'
        elif remainder > 0.5: return f'{whole}-3/4"'
        elif remainder > 0.25: return f'{whole}-1/2"'
        elif remainder > 0: return f'{whole}-1/4"'
        else: return f'{whole}"'

    def format_incheshalf(self, val):
        whole = int(val)
        remainder = val - whole
        if remainder >= 0.75: return f'{whole + 1}"'
        elif remainder >= 0.26: return f'{whole}-1/2"'
        else: return f'{whole}"'


    def format_incheseighth(self, val):
        whole = int(val)
        remainder = val - whole
        if remainder > 0.875: return f'{whole + 1}"'
        elif remainder > 0.75: return f'{whole}-7/8"'
        elif remainder > 0.625: return f'{whole}-3/4"'
        elif remainder > 0.5: return f'{whole}-5/8"'
        elif remainder > 0.375: return f'{whole}-1/2"'
        elif remainder > 0.25: return f'{whole}-3/8"'
        elif remainder > 0.125: return f'{whole}-1/4"'
        elif remainder > 0: return f'{whole}-1/8"'
        else: return f'{whole}"'

    def setup_layout_tab(self):
        self.sidebar = tk.Frame(self.tab_layout, width=280, bg="#f0f0f0", padx=20, pady=20)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # 1. Create a parent container frame for the canvas and scrollbars on the right
        canvas_container = ttk.Frame(self.tab_layout)
        canvas_container.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)

        # Configure grid weights so the canvas expands, but scrollbars remain fixed size
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)

        # 2. Create the scrollbars inside the container
        v_scroll = ttk.Scrollbar(canvas_container, orient="vertical")
        v_scroll.grid(row=0, column=1, sticky="ns")

        h_scroll = ttk.Scrollbar(canvas_container, orient="horizontal")
        h_scroll.grid(row=1, column=0, sticky="ew")

        # 3. Create the canvas, attaching it to the scrollbars
        # Added initial scrollregion matching your standard layout boundaries
        self.canvas = tk.Canvas(
            canvas_container, 
            bg="white", 
            highlightthickness=1,
            yscrollcommand=v_scroll.set,
            xscrollcommand=h_scroll.set,
            scrollregion=(0, 0, 1450, 950)
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # 4. Link scrollbars back to the canvas control methods
        v_scroll.config(command=self.canvas.yview)
        h_scroll.config(command=self.canvas.xview)

        # --- Rest of your Sidebar Elements (Unchanged) ---
        tk.Label(self.sidebar, text="GLOBAL SETTINGS", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(anchor="w")
        tk.Label(self.sidebar, text="Default Ramp Width (in):", bg="#f0f0f0").pack(anchor="w", pady=(3, 0))
        self.set_ramp_w = tk.Entry(self.sidebar); self.set_ramp_w.insert(0, "39.5")
        self.set_ramp_w.pack(fill=tk.X, pady=2)

        tk.Label(self.sidebar, text="Turn Deck Depth (in):", bg="#f0f0f0").pack(anchor="w", pady=(3, 0))
        self.set_deck_d = tk.Entry(self.sidebar); self.set_deck_d.insert(0, "72")
        self.set_deck_d.pack(fill=tk.X, pady=2)

        tk.Label(self.sidebar, text="\nINVENTORY", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(anchor="center", pady=(2, 0))

        # --- 2-COLUMN INVENTORY QUICK PICKS GRID ---
        inventory_btn_container = tk.Frame(self.sidebar, bg="#f0f0f0")
        inventory_btn_container.pack(fill=tk.X, pady=3)
        inventory_btn_container.columnconfigure(0, weight=1)
        inventory_btn_container.columnconfigure(1, weight=1)

        # Row 0
        btn_ramp = tk.Button(inventory_btn_container, text="+ Ramp", command=self.spawn_ramp, height=1)
        btn_ramp.grid(row=0, column=0, sticky="ew", padx=2, pady=2)

        btn_taperramp = tk.Button(inventory_btn_container, text="+ Taper Ramp", command=self.spawn_taperramp, height=1)
        btn_taperramp.grid(row=0, column=1, sticky="ew", padx=2, pady=2)

        btn_deck90 = tk.Button(inventory_btn_container, text="+ 90° Deck", command=lambda: self.spawn_deck(90), height=1)
        btn_deck90.grid(row=1, column=0, sticky="ew", padx=2, pady=2)

        # Row 1
        btn_deck180 = tk.Button(inventory_btn_container, text="+ 180° Deck", command=lambda: self.spawn_deck(180), height=1)
        btn_deck180.grid(row=1, column=1, sticky="ew", padx=2, pady=2)

        btn_step = tk.Button(inventory_btn_container, text="+ Step", command=self.spawn_step, height=1)
        btn_step.grid(row=2, column=0, sticky="ew", padx=2, pady=2)

        # Row 2 (Spans across column 0 to sit evenly, or sits nicely on the left)
        btn_pavers = tk.Button(inventory_btn_container, text="+ Pavers", command=self.paver_add, height=1)
        btn_pavers.grid(row=2, column=1, columnspan=2, sticky="ew", padx=2, pady=2)

        btn_polygon = tk.Button(inventory_btn_container, text="+ Polygon", command=self.spawn_polygon_deck, height=1)
        btn_polygon.grid(row=3, column=0, sticky="ew", padx=2, pady=2)
        # --------------------------------------------

        tk.Label(self.sidebar, text="\nEDIT SELECTED", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(anchor="w", pady=(2, 0))
        self.ent_len = tk.Entry(self.sidebar); self.ent_len.pack(fill=tk.X, pady=2)
        self.ent_wid = tk.Entry(self.sidebar); self.ent_wid.pack(fill=tk.X, pady=2)
        tk.Button(self.sidebar, text="Apply Size", command=self.apply_resize).pack(fill=tk.X, pady=2)

        tk.Button(self.sidebar, text="Delete Selected", fg="red", command=self.delete_item).pack(fill=tk.X, pady=2)
        tk.Button(self.sidebar, text="Add Comment Box", command=lambda: self.spawn_comment_box(self.canvas), bg="#F08AF3", fg="black", font=("Arial", 10, "bold")).pack(fill=tk.X, pady=7)
        
        # --- NEW TOGGLE BUTTON ---
        self.chk_autosnap = tk.Checkbutton(
            self.sidebar,
            text="Enable Auto-Snapping",
            variable=self.auto_snap_enabled,
            bg="#f0f0f0",
            activebackground="#f0f0f0",
            font=("Arial", 9)
        )
        self.chk_autosnap.pack(anchor="w", pady=(2, 5))

        self.canvas.bind("<r>", self.rotate_item)
        self.canvas.bind("<R>", self.rotate_item)

    def spawn_ramp(self):
        # Prompt user for length with a pop-up, pre-filling 91 as the default
        ramp_len = simpledialog.askfloat(
            "Ramp Length", 
            "Enter desired ramp length (inches):", 
            initialvalue=91.0, 
            minvalue=3.0, 
            maxvalue=144,
            parent=self.root  # or parent=self depending on your main window variable
        )

        # If user cancels the dialog or closes it, ramp_len will be None
        if ramp_len is None:
            return

        try:
            w = float(self.set_ramp_w.get())
        except ValueError:
            w = 39.5  # Fallback to standard ramp width if Entry is invalid

        # Spawn the ramp using the custom length and default width
        self.create_part(150, 150, ramp_len, w, "#dcdcdc", "RAMP")
        self.update_total_drop()

    def spawn_taperramp(self):
        #user specs all dimensions
        #ask if it's part of the ramp (include in overall drop) and change tag if not
        
        dimensions = self.ask_taperramp_dimensions("Taper Ramp")
        #result = {"w": None, "l": None, "h": None, "sl": None, "dr": None, "thresh": None}
        
        if dimensions["w"] is None:
            return
            
        print (f"Dimensions = {dimensions}")
        w = dimensions["w"]
        l = dimensions["l"]
        h = dimensions["h"]
        sl = dimensions["sl"]
        thresh = dimensions["thresh"]
        tagtext = "THRESH RAMP" if thresh == "1" else "TAPER RAMP"

        tag = self.create_part(150, 150, l, w, "#dcdcdc", tagtext, h=h, sl=sl, thresh=thresh)

        self.sections[tag]["h"] = h
        self.sections[tag]["sl"] = sl
        self.sections[tag]["thresh"] = thresh
        self.update_total_drop()
    
    def ask_taperramp_dimensions(self, ask_type):
        """
        Creates a custom dynamic modal pop-up window to collect taper/threshold ramp size.
        - Threshold Mode: Automatically calculates missing length/slope using trig.
        - Taper Mode: Allows independent entry for section length and cut slope angle.
        """
        dialogtap = tk.Toplevel(self.root)
        dialogtap.title("Add Taper/Threshold Ramp")
        dialogtap.geometry("370x510")
        dialogtap.resizable(False, False)
        
        # --- FIXES WINDOW STACKING INFRASTRUCTURE ---
        dialogtap.transient(self.root) # Mandates this window always stays drawn on top of self.root
        dialogtap.grab_set()           # Intercepts all application interactions
        
        default_width = float(self.set_ramp_w.get())
        result = {"w": None, "l": None, "h": None, "sl": None, "thresh": None}

        threshe = tk.StringVar(value="1")  # Default to Threshold ("1")
        we = tk.StringVar(value=str(default_width))
        he = tk.StringVar(value="4")       # Initial height default for Threshold
        le = tk.StringVar(value="")
        sle = tk.StringVar(value="")

        def on_type_change(*args):
            """Adjusts defaults and instructional labels when switching types."""
            if threshe.get() == "1":       # Threshold Ramp Mode
                he.set("4")
                height_label.config(text="Total Height (in) = Deck board + Joist:")
                instruction_label.config(text="Provide EITHER Length or Slope below (Auto-Calculated):")
                length_label.config(text="Ramp Length (in):")
                slope_label.config(text="Ramp Slope (Degrees):")
            else:                          # Taper Ramp Mode
                he.set("5.5")
                le.set("")
                sle.set("5") 
                height_label.config(text="Joist Thickness (in):")
                instruction_label.config(text="Provide BOTH Section Length and Slope Angle:")
                length_label.config(text="Total Section Length (in):")
                slope_label.config(text="Taper Cut Angle (Degrees):")
            
            recalculate_geometry()

        def recalculate_geometry(*args):
            """Handles geometry checking and conditional layout math."""
            try:
                h = float(he.get())
            except ValueError:
                submit_btn.config(state=tk.DISABLED, bg="#cccccc")
                return

            focused_widget = dialogtap.focus_get()

            if threshe.get() == "1":
                if focused_widget == sl_entry:
                    try:
                        slope_deg = float(sle.get())
                        if 0 < slope_deg < 90:
                            calculated_len = h / math.tan(math.radians(slope_deg))
                            rounded_len = round(calculated_len * 2) / 2
                            le.set(str(rounded_len))
                    except ValueError:
                        pass

                elif focused_widget == l_entry:
                    try:
                        length_in = float(le.get())
                        if length_in > 0:
                            calculated_slope = math.degrees(math.atan(h / length_in))
                            rounded_slope = round(calculated_slope, 1)
                            sle.set(str(rounded_slope))
                    except ValueError:
                        pass

            if we.get().strip() and he.get().strip() and le.get().strip() and sle.get().strip():
                submit_btn.config(state=tk.NORMAL, bg="#4CAF50")
            else:
                submit_btn.config(state=tk.DISABLED, bg="#cccccc")

        threshe.trace_add("write", on_type_change)
        he.trace_add("write", recalculate_geometry)
        we.trace_add("write", recalculate_geometry)
        le.trace_add("write", recalculate_geometry)
        sle.trace_add("write", recalculate_geometry)

        # --- UI LAYOUT DESIGN ---
        tk.Label(dialogtap, text="Select Type First:", font=("Arial", 10, "bold")).pack(pady=(15, 2))
        radio_frame = tk.Frame(dialogtap)
        radio_frame.pack(pady=5)
        
        rb1 = tk.Radiobutton(radio_frame, text="Threshold Ramp\n(Separate Piece)", variable=threshe, value="1", justify=tk.LEFT)
        rb1.pack(side=tk.LEFT, padx=10)
        rb2 = tk.Radiobutton(radio_frame, text="Taper Ramp\n(Continuation of Ramp)", variable=threshe, value="0", justify=tk.LEFT)
        rb2.pack(side=tk.LEFT, padx=10)

        ttk.Separator(dialogtap, orient='horizontal').pack(fill='x', padx=15, pady=10)

        tk.Label(dialogtap, text="Ramp Width (in):", font=("Arial", 10)).pack(pady=(5, 2))
        w_entry = tk.Entry(dialogtap, textvariable=we, width=15, justify="center")
        w_entry.pack()
        
        height_label = tk.Label(dialogtap, text="", font=("Arial", 10))
        height_label.pack(pady=(10, 2))
        h_entry = tk.Entry(dialogtap, textvariable=he, width=15, justify="center")
        h_entry.pack()

        ttk.Separator(dialogtap, orient='horizontal').pack(fill='x', padx=30, pady=10)
        
        instruction_label = tk.Label(dialogtap, text="", font=("Arial", 9, "italic"), fg="gray")
        instruction_label.pack()

        length_label = tk.Label(dialogtap, text="", font=("Arial", 10, "bold"))
        length_label.pack(pady=(10, 2))
        l_entry = tk.Entry(dialogtap, textvariable=le, width=15, justify="center")
        l_entry.pack()

        slope_label = tk.Label(dialogtap, text="", font=("Arial", 10, "bold"))
        slope_label.pack(pady=(10, 2))
        sl_entry = tk.Entry(dialogtap, textvariable=sle, width=15, justify="center")
        sl_entry.pack()

        btn_frame = tk.Frame(dialogtap)
        btn_frame.pack(side=tk.BOTTOM, pady=20)

        def on_submit():
            try:
                w_val = float(we.get())
                h_val = float(he.get())
                l_val = float(le.get()) if le.get() else 0.0
                sl_val = float(sle.get()) if sle.get() else 0.0
                thresh_val = threshe.get()
                
                if thresh_val == "0": 
                    if sl_val <= 0 or sl_val >= 90:
                        # Fixed parent routing here
                        messagebox.showerror("Validation Error", "Slope angle must be between 0 and 90 degrees.", parent=dialogtap)
                        dialogtap.lift()
                        dialogtap.focus_set()
                        return
                    
                    min_required_len = h_val / math.tan(math.radians(sl_val))
                    
                    if l_val < min_required_len:
                        suggested_len = round(min_required_len * 2) / 2
                        if suggested_len < min_required_len:
                            suggested_len += 0.5
                            
                        # Fixed parent routing here to keep modal lock inside the dialog window stack
                        messagebox.showwarning(
                            "Geometry Conflict", 
                            f"The entered Section Length ({l_val}\") is too short for a {h_val}\" height at a {sl_val}° slope.\n\n"
                            f"The taper cut alone requires a minimum run of {min_required_len:.2f}\".\n"
                            f"Please increase the length to at least {suggested_len}\" or steepen the slope.",
                            parent=dialogtap
                        )
                        dialogtap.lift()         
                        dialogtap.focus_set()   
                        return 

                result["w"] = w_val
                result["h"] = h_val if thresh_val == "0" else h_val-1 #correct for deckboard
                result["l"] = l_val
                result["sl"] = sl_val
                result["thresh"] = thresh_val
                
                dialogtap.destroy()
            except ValueError:
                # Fixed parent routing here
                messagebox.showerror("Validation Error", "Please ensure all structural dimensions contain valid measurements.", parent=dialogtap)
                dialogtap.lift()         
                dialogtap.focus_set()   
                
        submit_btn = tk.Button(btn_frame, text="Add to Layout", command=on_submit, width=15, state=tk.DISABLED, bg="#cccccc", fg="white")
        submit_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=dialogtap.destroy, width=10)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        on_type_change()

        self.root.wait_window(dialogtap)
        #rint(ask_type)
        return result

    def spawn_deck(self, angle):
        d = float(self.set_deck_d.get())
        w = d if angle == 90 else 82.75
        self.create_part(150, 150, d, w, "#ffd700", "DECK")
        self.update_total_drop()

    def spawn_polygon_deck(self):
        """Spawns an irregular polygon deck section on the main layout canvas."""
        dimensions = self.ask_polygon_dimensions("Polygon Deck Section")
        
        if dimensions["sides"] is None:
            return
            
        sides = dimensions["sides"]
        tagtext = f"POLY DECK"
        
        if not hasattr(self, 'polygon_count'):
            self.polygon_count = 0
        self.polygon_count += 1
        tag = f"PolygonDeck{self.polygon_count}"
        
        # Base anchor coordinates
        x1, y1 = 150, 150
        l_val = dimensions.get("side_a", 48.0)
        w_val = dimensions.get("side_b", 48.0)
        x2, y2 = x1 + (l_val * self.scale), y1 + (w_val * self.scale)
        
        # Calculate true-to-scale layout vector paths
        if sides == 3:
            points = [x1, y2, x2, y2, x1, y1]
        else:
            c_val = dimensions.get("side_c", 0.0)
            x_top_right = x1 + (c_val * self.scale)
            points = [x1, y1, x_top_right, y1, x2, y2, x1, y2]

        self.sections[tag] = {
            "p_type": "POLYGON",
            "name": f"Polygon Deck {self.polygon_count}",
            "color": "#b0c4de",
            "sides": sides,
            # Backwards-compatibility flags for drag handler & property entry forms
            "l": l_val,
            "w": w_val,
            # Poly metrics
            "side_a": dimensions["side_a"],
            "side_b": dimensions["side_b"],
            "side_c": dimensions["side_c"],
            "side_d": dimensions["side_d"],
            "angle_1": dimensions["angle_1"],
            "angle_2": dimensions["angle_2"],
            "angle_3": dimensions["angle_3"],
            "angle_4": dimensions["angle_4"],
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "points": points,
            "full_label_text": tagtext
        }

        # Render directly to layout canvas
        self.canvas.create_polygon(points, fill="#b0c4de", outline="black", width=2, tags=(tag, "POLYGON", "shape"))
        self.canvas.create_text((x1+x2)/2, (y1+y2)/2, text=tagtext, tags=(f"label_{tag}", tag, "text"))

        self.create_component_tab(tag)
        self.bind_item(tag)
        self.update_total_drop()
        self.refresh_materials_matrix()

    def ask_polygon_dimensions(self, ask_type):
        """Creates a custom dynamic modal popup window to collect irregular deck shapes."""
        import math
        dialogpoly = tk.Toplevel(self.root)
        dialogpoly.title(ask_type)
        dialogpoly.geometry("440x680")
        dialogpoly.resizable(False, False)
        
        dialogpoly.transient(self.root)
        dialogpoly.grab_set()
        
        # Safely pull global settings from sidebar entries as fallbacks
        try:
            default_deck_d = self.set_deck_d.get() or "72"
            default_ramp_w = self.set_ramp_w.get() or "39.5"
        except Exception:
            default_deck_d = "72"
            default_ramp_w = "39.5"

        result = {
            "sides": None, "side_a": None, "side_b": None, "side_c": None, "side_d": None,
            "angle_1": None, "angle_2": None, "angle_3": None, "angle_4": None
        }

        # Default radio selection to 4 Sides (Trapezoid)
        sides_var = tk.StringVar(value="4")
        sa, sb, sc, sd = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
        a1, a2, a3, a4 = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()

        preview_canvas = tk.Canvas(dialogpoly, width=320, height=150, bg="#ffffff", bd=1, relief="solid")
        preview_canvas.pack(pady=10)

        def clear_calculated_tags():
            """Clears color formatting highlights across calculated inputs."""
            for entry in [sa_ent, sb_ent, sc_ent, sd_ent, a1_ent, a2_ent, a3_ent, a4_ent]:
                entry.config(bg="white")

        def draw_default_blueprint():
            """Draws a generic reference shape showing all component labels clearly."""
            preview_canvas.delete("all")
            if sides_var.get() == "3":
                pts = [100, 120, 240, 120, 100, 30]
                preview_canvas.create_polygon(pts, fill="#f8fafc", outline="#64748b", width=2, dash=(4, 2))
                preview_canvas.create_text(170, 135, text="A (Base)", font=("Arial", 9, "bold"), fill="#0f172a")
                preview_canvas.create_text(65, 75, text="B (Height)", font=("Arial", 9, "bold"), fill="#0f172a")
                preview_canvas.create_text(190, 65, text="C (Slope)", font=("Arial", 9, "bold"), fill="#0f172a")
                preview_canvas.create_text(112, 112, text="∠1", font=("Arial", 8), fill="#64748b")
                preview_canvas.create_text(210, 112, text="∠2", font=("Arial", 8), fill="#64748b")
                preview_canvas.create_text(112, 50, text="∠3", font=("Arial", 8), fill="#64748b")
            else:
                pts = [80, 120, 240, 120, 200, 40, 80, 40]
                preview_canvas.create_polygon(pts, fill="#f8fafc", outline="#64748b", width=2, dash=(4, 2))
                preview_canvas.create_text(160, 135, text="A (Base)", font=("Arial", 9, "bold"), fill="#0f172a")
                preview_canvas.create_text(50, 80, text="B (Left)", font=("Arial", 9, "bold"), fill="#0f172a")
                preview_canvas.create_text(140, 25, text="C (Top)", font=("Arial", 9, "bold"), fill="#0f172a")
                preview_canvas.create_text(250, 80, text="D (Right)", font=("Arial", 9, "bold"), fill="#0f172a")
                preview_canvas.create_text(95, 105, text="∠1", font=("Arial", 8), fill="#64748b")
                preview_canvas.create_text(215, 105, text="∠2", font=("Arial", 8), fill="#64748b")
                preview_canvas.create_text(185, 55, text="∠3", font=("Arial", 8), fill="#64748b")
                preview_canvas.create_text(95, 55, text="∠4", font=("Arial", 8), fill="#64748b")

        def evaluate_geometry():
            """Dynamically solves remaining properties using trigonometric equations."""
            submit_btn.config(state=tk.DISABLED, bg="#cccccc")
            
            try:
                v = {
                    'a': float(sa.get()) if sa.get() else None,
                    'b': float(sb.get()) if sb.get() else None,
                    'c': float(sc.get()) if sc.get() else None,
                    'd': float(sd.get()) if sd.get() else None,
                    'a1': float(a1.get()) if a1.get() else None,
                    'a2': float(a2.get()) if a2.get() else None,
                    'a3': float(a3.get()) if a3.get() else None,
                    'a4': float(a4.get()) if a4.get() else None,
                }
            except ValueError:
                return None

            if not any(v.values()):
                clear_calculated_tags()
                draw_default_blueprint()
                return None

            if sides_var.get() == "3":
                if v['a1'] == 90:
                    if v['a'] and v['b'] and not v['c']:
                        v['c'] = math.sqrt(v['a']**2 + v['b']**2)
                        sc.set(f"{v['c']:.2f}"); sc_ent.config(bg="#e2e8f0")
                    elif v['a'] and v['c'] and not v['b']:
                        if v['c'] > v['a']:
                            v['b'] = math.sqrt(v['c']**2 - v['a']**2)
                            sb.set(f"{v['b']:.2f}"); sb_ent.config(bg="#e2e8f0")
                    elif v['b'] and v['c'] and not v['a']:
                        if v['c'] > v['b']:
                            v['a'] = math.sqrt(v['c']**2 - v['b']**2)
                            sa.set(f"{v['a']:.2f}"); sa_ent.config(bg="#e2e8f0")
                    
                    if v['a'] and v['b'] and v['c']:
                        v['a2'] = math.degrees(math.atan2(v['b'], v['a']))
                        v['a3'] = 90.0 - v['a2']
                        a2.set(f"{v['a2']:.1f}"); a2_ent.config(bg="#e2e8f0")
                        a3.set(f"{v['a3']:.1f}"); a3_ent.config(bg="#e2e8f0")

                elif v['a'] and v['b'] and v['c']:
                    try:
                        v['a1'] = math.degrees(math.acos((v['a']**2 + v['b']**2 - v['c']**2) / (2 * v['a'] * v['b'])))
                        v['a2'] = math.degrees(math.acos((v['b']**2 + v['c']**2 - v['a']**2) / (2 * v['b'] * v['c'])))
                        v['a3'] = 180.0 - v['a1'] - v['a2']
                        a1.set(f"{v['a1']:.1f}"); a1_ent.config(bg="#e2e8f0")
                        a2.set(f"{v['a2']:.1f}"); a2_ent.config(bg="#e2e8f0")
                        a3.set(f"{v['a3']:.1f}"); a3_ent.config(bg="#e2e8f0")
                    except ValueError:
                        pass

                if all(x is not None for x in [v['a'], v['b'], v['c']]):
                    preview_canvas.delete("all")
                    submit_btn.config(state=tk.NORMAL, bg="#4CAF50")
                    max_d = max(v['a'], v['b'], v['c'])
                    scale = 100.0 / max_d if max_d > 0 else 1.0
                    pts = [100, 120, 100 + (v['a'] * scale), 120, 100, 120 - (v['b'] * scale)]
                    preview_canvas.create_polygon(pts, fill="#f1f5f9", outline="#0f172a", width=2)
                    preview_canvas.create_text(100 + (v['a']*scale/2), 135, text=f"A: {v['a']:.1f}", font=("Arial", 9, "bold"))
                    preview_canvas.create_text(55, 120 - (v['b']*scale/2), text=f"B: {v['b']:.1f}", font=("Arial", 9, "bold"))
                    preview_canvas.create_text(125 + (v['a']*scale/2), 110 - (v['b']*scale/2), text=f"C: {v['c']:.1f}", font=("Arial", 9, "bold"))
                    return v

            else:
                # --- TRAPEZOID SOLVER MATRIX ---
                v['a1'], v['a4'] = 90.0, 90.0
                a1.set("90"); a4.set("90")
                
                # Scenario 2: Given A, D, and Angle 2
                if v['a'] and v['d'] and v['a2'] and not (v['b'] and v['c'] and not v['a2']):
                    ang = v['a2']
                    rad2 = math.radians(ang)
                    
                    calc_b = v['d'] * math.sin(rad2)
                    dx = v['d'] * math.cos(rad2)
                    calc_c = v['a'] - dx
                    calc_a3 = 180.0 - ang

                    if v['b'] is None or abs(v['b'] - calc_b) > 0.01:
                        v['b'] = calc_b
                        sb.set(f"{v['b']:.2f}")
                        sb_ent.config(bg="#e2e8f0")

                    if v['c'] is None or abs(v['c'] - calc_c) > 0.01:
                        v['c'] = calc_c
                        sc.set(f"{v['c']:.2f}")
                        sc_ent.config(bg="#e2e8f0")

                    v['a3'] = calc_a3
                    a3.set(f"{v['a3']:.1f}")
                    a3_ent.config(bg="#e2e8f0")

                elif v['a'] and v['b'] and v['c'] and not v['d']:
                    v['d'] = math.sqrt(v['b']**2 + (v['a'] - v['c'])**2)
                    v['a2'] = 90.0 + math.degrees(math.atan2(abs(v['a'] - v['c']), v['b']))
                    v['a3'] = 360.0 - (90.0 + 90.0 + v['a2'])
                    sd.set(f"{v['d']:.2f}"); sd_ent.config(bg="#e2e8f0")
                    a2.set(f"{v['a2']:.1f}"); a2_ent.config(bg="#e2e8f0")
                    a3.set(f"{v['a3']:.1f}"); a3_ent.config(bg="#e2e8f0")

                if all(x is not None for x in [v['a'], v['b'], v['c'], v['d']]):
                    preview_canvas.delete("all")
                    submit_btn.config(state=tk.NORMAL, bg="#4CAF50")
                    max_d = max(v['a'], v['b'], v['c'])
                    scale = 120.0 / max_d if max_d > 0 else 1.0
                    
                    pts = [
                        80, 120, 
                        80 + (v['a'] * scale), 120, 
                        80 + (v['c'] * scale), 120 - (v['b'] * scale), 
                        80, 120 - (v['b'] * scale)
                    ]
                    
                    preview_canvas.create_polygon(pts, fill="#f1f5f9", outline="#0f172a", width=2)
                    preview_canvas.create_text(80 + (v['a']*scale/2), 135, text=f"A: {v['a']:.1f}", font=("Arial", 9, "bold"))
                    preview_canvas.create_text(45, 120 - (v['b']*scale/2), text=f"B: {v['b']:.1f}", font=("Arial", 9, "bold"))
                    preview_canvas.create_text(80 + (v['c']*scale/2), 105 - (v['b']*scale), text=f"C: {v['c']:.1f}", font=("Arial", 9, "bold"))
                    preview_canvas.create_text(105 + (v['a']*scale), 120 - (v['b']*scale/2), text=f"D: {v['d']:.1f}", font=("Arial", 9, "bold"))
                    return v
            return None

        def on_sides_change(*args):
            sa.set(""); sb.set(""); sc.set(""); sd.set("")
            a1.set(""); a2.set(""); a3.set(""); a4.set("")
            clear_calculated_tags()
            
            if sides_var.get() == "3":
                sd_ent.config(state=tk.DISABLED)
                a4_ent.config(state=tk.DISABLED)
                a1_ent.config(state=tk.NORMAL)
                draw_default_blueprint()
            else:
                sd_ent.config(state=tk.NORMAL)
                a4_ent.config(state=tk.NORMAL)
                
                # Pre-populate defaults automatically from global settings
                sa.set(default_deck_d)   # Side A = Turn Deck Depth (72)
                sd.set(default_ramp_w)   # Side D = Default Ramp Width (39.5)
                a1.set("90")
                a2.set("45")             # Angle 2 = 45°
                a4.set("90")
                
                # Triggers automatic calculation for B, C, and Angle 3 right away
                evaluate_geometry()

        # Input tracking listeners 
        for var in [sa, sb, sc, sd, a1, a2, a3, a4]:
            var.trace_add("write", lambda *args: evaluate_geometry())

        # Structural Radio Form Selectors
        tk.Label(dialogpoly, text="Select Geometry Type:", font=("Arial", 10, "bold")).pack(pady=5)
        r_frame = tk.Frame(dialogpoly)
        r_frame.pack()
        #tk.Radiobutton(r_frame, text="3 Sides (Triangle)", variable=sides_var, value="3", command=on_sides_change).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(r_frame, text="4 Sides (Trapezoid)", variable=sides_var, value="4", command=on_sides_change).pack(side=tk.LEFT, padx=10)

        fields_frame = tk.Frame(dialogpoly)
        fields_frame.pack(fill="both", expand=True, padx=25, pady=10)

        # UI Grid Elements Matrix Assembly
        tk.Label(fields_frame, text="Side A (Base):").grid(row=0, column=0, sticky="w", pady=2)
        sa_ent = tk.Entry(fields_frame, textvariable=sa, width=10, justify="center"); sa_ent.grid(row=0, column=1, pady=2)

        tk.Label(fields_frame, text="Side B (Height):").grid(row=1, column=0, sticky="w", pady=2)
        sb_ent = tk.Entry(fields_frame, textvariable=sb, width=10, justify="center"); sb_ent.grid(row=1, column=1, pady=2)

        tk.Label(fields_frame, text="Side C (Slope/Top):").grid(row=2, column=0, sticky="w", pady=2)
        sc_ent = tk.Entry(fields_frame, textvariable=sc, width=10, justify="center"); sc_ent.grid(row=2, column=1, pady=2)

        tk.Label(fields_frame, text="Side D (Right Side):").grid(row=3, column=0, sticky="w", pady=2)
        sd_ent = tk.Entry(fields_frame, textvariable=sd, width=10, justify="center"); sd_ent.grid(row=3, column=1, pady=2)

        tk.Label(fields_frame, text="Angle 1 (Corner Corner deg):").grid(row=4, column=0, sticky="w", pady=2)
        a1_ent = tk.Entry(fields_frame, textvariable=a1, width=10, justify="center"); a1_ent.grid(row=4, column=1, pady=2)

        tk.Label(fields_frame, text="Angle 2 (deg):").grid(row=5, column=0, sticky="w", pady=2)
        a2_ent = tk.Entry(fields_frame, textvariable=a2, width=10, justify="center"); a2_ent.grid(row=5, column=1, pady=2)

        tk.Label(fields_frame, text="Angle 3 (deg):").grid(row=6, column=0, sticky="w", pady=2)
        a3_ent = tk.Entry(fields_frame, textvariable=a3, width=10, justify="center"); a3_ent.grid(row=6, column=1, pady=2)

        tk.Label(fields_frame, text="Angle 4 (deg):").grid(row=7, column=0, sticky="w", pady=2)
        a4_ent = tk.Entry(fields_frame, textvariable=a4, width=10, justify="center"); a4_ent.grid(row=7, column=1, pady=2)

        btn_frame = tk.Frame(dialogpoly)
        btn_frame.pack(side=tk.BOTTOM, pady=15)

        def pack_and_close():
            v = evaluate_geometry()
            if v:
                result.update({
                    "sides": int(sides_var.get()),
                    "side_a": v['a'], "side_b": v['b'], "side_c": v['c'], "side_d": v['d'] or 0.0,
                    "angle_1": v['a1'], "angle_2": v['a2'], "angle_3": v['a3'], "angle_4": v['a4'] or 0.0
                })
                dialogpoly.destroy()

        submit_btn = tk.Button(btn_frame, text="Add to Layout", command=pack_and_close, width=15, state=tk.DISABLED, bg="#cccccc", fg="white")
        submit_btn.pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialogpoly.destroy, width=10).pack(side=tk.LEFT, padx=5)

        # Initialize window state with trapezoid defaults auto-computed
        on_sides_change()
        self.root.wait_window(dialogpoly)
        return result

    def spawn_step(self):

        num_steps = sd.askinteger("Add Steps", "How many steps to add?", minvalue=1, maxvalue=8)
        if not num_steps:
            return

        w = float(self.set_ramp_w.get())
        total_l = num_steps * 10
        
        # 1. Create the base part and get the unique tag (e.g., obj_123...)
        tag = self.create_part(150, 150, total_l, w, "#ac239c", "STEP")
        
        # 2. Add visual dividing lines
        x, y = 150, 150
        for i in range(1, num_steps):
            step_offset = (i * 10) * self.scale
            # CRITICAL: 'tag' must be in the tags tuple for movement
            #print ("Tag for line")
            #print (tag)
            self.canvas.create_line(
                x + step_offset, y, 
                x + step_offset, y + (w * self.scale),
                fill="black", 
                width=1, 
                tags=(tag, "step_line") 
            )
        
        # 3. Add the label (create_part skips text for STEP types currently)
        self.canvas.create_text(
            x + (total_l * self.scale) / 2, 
            y + (w * self.scale) / 2,
            text=f"STEPS ({num_steps})", #\n{total_l}\"x{w}\"",
            font=("Arial", 9, "bold"), 
            tags=(tag, "text") 
        )
        
        self.update_total_drop()

    def create_component_tab(self, tag):
        if tag not in self.sections: return
        data = self.sections[tag]
        print ("Component")
        print (data)

        comp_tab = tk.Frame(self.notebook)
        self.notebook.add(comp_tab, text=data['name'])
        
        header_frame = tk.Frame(comp_tab)
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=20, pady=10)

        lbl = tk.Label(header_frame, text=f"{data['name']} Detail View", font=("Arial", 14, "bold"))
        lbl.pack(side=tk.LEFT)

        add_btn = tk.Button(
            header_frame, 
            text="Add Comment Box", 
            command=lambda: self.spawn_comment_box(det_canvas),
            bg="#4CAF50", 
            fg="white",
            font=("Arial", 10, "bold")
        )
        add_btn.pack(side=tk.RIGHT)
        

        # --- NEW SCROLLABLE CONTAINER FOR THE DETAIL CANVAS ---
        canvas_container = tk.Frame(comp_tab, bg="white")
        canvas_container.pack(fill=tk.X, padx=20)

        # --- NEW SCROLLABLE CONTAINER FOR THE DETAIL CANVAS ---
        canvas_container = tk.Frame(comp_tab, bg="white")
        canvas_container.pack(fill=tk.X, padx=20)

        # Create the canvas inside the container
        if data['p_type'] == "STEP":
            cht = 370
        else:
            cht = 400
        det_canvas = tk.Canvas(canvas_container, bg="white", height=cht)#400

        # Create vertical and horizontal scrollbars for the canvas
        canvas_v_scroll = tk.Scrollbar(canvas_container, orient="vertical", command=det_canvas.yview)
        canvas_h_scroll = tk.Scrollbar(canvas_container, orient="horizontal", command=det_canvas.xview)
        
        # Link the canvas to the scrollbars
        det_canvas.configure(yscrollcommand=canvas_v_scroll.set, xscrollcommand=canvas_h_scroll.set)
        
        # Layout the canvas and its scrollbars using grid inside the container frame
        det_canvas.grid(row=0, column=0, sticky="nsew")
        canvas_v_scroll.grid(row=0, column=1, sticky="ns")
        canvas_h_scroll.grid(row=1, column=0, sticky="ew")
        
        # Ensure the canvas expands to take up the frame space smoothly
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
        # ------------------------------------------------------

        # We keep the canvas at a fixed height or a slightly smaller height to save space
        #det_canvas = tk.Canvas(comp_tab, bg="white", height=400) # Reduced from 450 to 400
        #det_canvas.pack(fill=tk.X, padx=20)

        # This is the container for the material list
        # We use fill=tk.BOTH and expand=True so it claims the rest of the window
        tbl_container = tk.Frame(comp_tab, bg="white")
        tbl_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Add a scrollable sub-frame for the table itself
        tbl_canvas = tk.Canvas(tbl_container, bg="white", highlightthickness=0)
        scrollbar = tk.Scrollbar(tbl_container, orient="vertical", command=tbl_canvas.yview)
        tbl_frame = tk.Frame(tbl_canvas, bg="white")

        tbl_frame.bind("<Configure>", lambda e: tbl_canvas.configure(scrollregion=tbl_canvas.bbox("all")))
        tbl_canvas.create_window((0, 0), window=tbl_frame, anchor="nw")
        tbl_canvas.configure(yscrollcommand=scrollbar.set)

        tbl_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        data.update({
            "tab_id": comp_tab, 
            "canvas": det_canvas, 
            "table": tbl_frame, # We point the table data to the inner frame
            "label": lbl
        })
        self.component_tabs[tag] = {"frame": comp_tab, "canvas": det_canvas}

        self.draw_component_detail(data)

    import math

    def calculate_rotated_rect_points(self, x, y, l, w, rotation_deg):
        """Calculates the 4 corner coordinates of a rotated rectangle."""
        # Convert length and width to pixel scale
        scaled_l = l * self.scale
        scaled_w = w * self.scale
        
        # We rotate around the starting point (x, y) as the origin pivot.
        # If you prefer rotating around the absolute center, change the pivot point logic.
        angle = math.radians(rotation_deg)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        
        # Local offsets for a rectangle relative to its top-left pivot
        local_points = [
            (0, 0),                 # Top-Left
            (scaled_l, 0),          # Top-Right
            (scaled_l, scaled_w),   # Bottom-Right
            (0, scaled_w)           # Bottom-Left
        ]
        
        # Rotate points and translate back to canvas (x, y)
        rotated_points = []
        for px, py in local_points:
            rx = x + (px * cos_a - py * sin_a)
            ry = y + (px * sin_a + py * cos_a)
            rotated_points.append(rx)
            rotated_points.append(ry)
            
        return rotated_points # Returns a flat list: [x1, y1, x2, y2, x3, y3, x4, y4]

    def create_part(self, x, y, l, w, color, p_type, rotation=0, **kwargs):
        # --- [Keep your existing name/counter logic here] ---
        if p_type == "RAMP":
            self.ramp_count += 1
            name = f"{p_type} {self.ramp_count}"
            display_name = name
        elif p_type == "TAPER RAMP":
            self.taper_ramp_count += 1
            name = f"{p_type} {self.taper_ramp_count}"
            display_name = f"TAPER\nRAMP {self.taper_ramp_count}"
        elif p_type == "THRESH RAMP":
            self.threshold_ramp_count += 1
            name = f"{p_type} {self.threshold_ramp_count}"
            display_name = f"THRESHOLD\nRAMP {self.threshold_ramp_count}"
        elif p_type == "DECK":
            self.landing_count += 1
            name = f"{p_type} {self.landing_count}"
            display_name = name
        elif p_type == "STEP":
            self.step_count += 1
            name = f"{p_type} {self.step_count}"
            display_name = name

        tag = f"obj_{id(name)}_{x}_{y}"
        
        # Calculate the 4 rotated corner points
        points = self.calculate_rotated_rect_points(x, y, l, w, rotation)
        
        # Calculate the bounding box center for text placement
        # Averaging the 4 corners safely handles text centering no matter the rotation
        center_x = sum(points[0::2]) / 4
        center_y = sum(points[1::2]) / 4

        # Store base data for exporting / saving
        self.sections[tag] = {
            "name": name, 
            "p_type": p_type, 
            "l": l, 
            "w": w, 
            "color": color,
            "x": x,                      # Keep base tracking origin
            "y": y,                      # Keep base tracking origin
            "rotation": rotation,         # CRITICAL for saves/re-loads
            "points": points             # Flat coordinate array for exports
        }

        for key, value in kwargs.items():
            self.sections[tag][key] = value

        self.create_component_tab(tag)

        # DRAW THE POLYGON (Instead of rectangle)
        self.canvas.create_polygon(
            points, 
            fill=color, outline="black", width=2, 
            tags=(tag, p_type, "shape")
        )

        if p_type != "STEP":
            self.canvas.create_text(
                center_x, center_y, 
                text=f"{display_name}\n{self.format_inchesquarter(l)}x{self.format_inchesquarter(w)}", 
                font=("Arial", 9, "bold"), 
                justify=tk.CENTER,
                tags=(tag, "text")
            )
            
        self.bind_item(tag)
        return tag

    def bind_item(self, tag):
        """Universal item binder: Auto-detects target canvas, attaches drag handlers, and sets focus on click."""
        print(f"[DEBUG] Attempting to bind tag: {tag} (type: {type(tag).__name__})")

        bound = False

        # --- 1. Main Canvas Items ---
        if hasattr(self, 'canvas') and self.canvas.find_withtag(tag):
            print(f" -> Found {tag} on main canvas")
            self.canvas.tag_bind(tag, "<ButtonPress-1>", lambda e, t=tag: self._on_item_click(e, t, self.canvas, self.on_start_drag))
            self.canvas.tag_bind(tag, "<B1-Motion>", self.on_drag)
            self.canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_stop_drag)
            bound = True

        # --- 2. Post Canvas Items ---
        elif hasattr(self, 'post_canvas') and self.post_canvas.find_withtag(tag):
            print(f" -> Found {tag} on post canvas")
            self.post_canvas.tag_bind(tag, "<ButtonPress-1>", lambda e, t=tag: self._on_item_click(e, t, self.post_canvas, self.on_post_drag_start))
            self.post_canvas.tag_bind(tag, "<B1-Motion>", self.on_post_drag)
            self.post_canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_post_stop_drag)
            bound = True

        # --- 3. Rail Canvas Items ---
        elif hasattr(self, 'rail_canvas') and self.rail_canvas.find_withtag(tag):
            print(f" -> Found {tag} on rail canvas")
            # FIXED: Changed from on_rail_drag_start to _on_item_click (or correct wrapper)
            self.rail_canvas.tag_bind(tag, "<ButtonPress-1>", lambda e, t=tag: self._on_item_click(e, t, self.rail_canvas, self.on_rail_drag_start))
            self.rail_canvas.tag_bind(tag, "<B1-Motion>", self.on_rail_drag)
            self.rail_canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_rail_drag_stop)
            bound = True

        if not bound:
            print(f"[WARNING] COULD NOT BIND '{tag}'! Item was not found on ANY canvas.")

    def _on_item_click(self, event, tag, target_canvas, drag_start_callback):
        """Helper: Sets active tag, shifts keyboard focus to active canvas, then triggers drag start."""
        self.active_tag = tag
        target_canvas.focus_set()  # Critical: Focus enables canvas keyboard shortcuts
        
        if hasattr(self, 'update_delete_button_visibility'):
            self.update_delete_button_visibility()
            
        if drag_start_callback:
            drag_start_callback(event)

    def on_start_drag(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        item_ids = self.canvas.find_closest(canvas_x, canvas_y)
        if not item_ids: return
        
        # Get all tags for the specific item clicked
        tags = self.canvas.gettags(item_ids[0])
        if not tags: return
        
        print(f"DEBUG: Clicked item {item_ids[0]} has tags: {tags}") # <--- ADD THIS
        # The unique ID tag is always the first one in our setup (obj_... or REF_POINT)
        self.active_tag = tags[0]
        
        # UI: Highlight only the selected item
        self.canvas.itemconfig("shape", outline="black", width=2)
        self.canvas.itemconfig(f"{self.active_tag} && shape", outline="#007bff", width=4)

        print (self.active_tag)

        # CRITICAL FIX: Ensure drag data tracks the UNIQUE tag (self.active_tag)
        # This prevents the "Existing Deck" (REF_POINT) from moving by mistake.
        self._drag_data.update({"item": self.active_tag, "x": canvas_x, "y": canvas_y})

        if self.active_tag in self.sections and self.active_tag != "REF_POINT" and not self.active_tag.startswith('Paver') :
            d = self.sections[self.active_tag]
            self.ent_len.delete(0, tk.END); self.ent_len.insert(0, str(d['l']))
            self.ent_wid.delete(0, tk.END); self.ent_wid.insert(0, str(d['w']))
            self.draw_component_detail(d)
            
        

    def on_drag(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        dx, dy =  canvas_x - self._drag_data["x"], canvas_y - self._drag_data["y"]
        self.canvas.move(self._drag_data["item"], dx, dy)

        # Keep underlying dictionary coordinates synchronized during the drag
        if self.active_tag in self.sections:
            d = self.sections[self.active_tag]

            # 1. Update the base x, y origin trackers so they match the current position
            if "x" in d: d["x"] += dx
            if "y" in d: d["y"] += dy
            
            # FIXED: Include all ramp, deck, and step types that carry the points tracking array
            if "points" in d:
                # Add dx to every even index (X), dy to every odd index (Y)
                d["points"] = [
                    p + dx if i % 2 == 0 else p + dy 
                    for i, p in enumerate(d["points"])
                ]

        self._drag_data.update({"x": canvas_x, "y": canvas_y})
        
    def on_stop_drag(self, event):
        if not self.active_tag: return
        
        # Check if auto-snapping is turned off
        if not self.auto_snap_enabled.get():
            self.update_post_tab()
            self.update_total_drop()
            self.canvas.focus_set()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            return
        
        sid_list = self.canvas.find_withtag(f"{self.active_tag} && shape")
        if not sid_list: return
        sid = sid_list[0]
        c = self.canvas.coords(sid)

        # Cleaned up / Consolidated: Everything extracts actual vertices dynamically now
        curr_corners = [(c[i], c[i+1]) for i in range(0, len(c), 2)]
        
        # Get all shapes and REVERSE the list [::-1] to prioritize the newest pieces
        all_shapes_reversed = self.canvas.find_withtag("shape")[::-1]

        # Pass 1: Prioritize Decks and Reference Points (Newest First)
        for other in all_shapes_reversed:
            tags = self.canvas.gettags(other)
            if self.active_tag in tags: continue
            if self.active_tag.startswith("Paver"): continue
            
            if "DECK" in tags or "REF_POINT" in tags or "STEP" in tags:
                o = self.canvas.coords(other)
                
                # Dynamic extraction of targeted snap vertices for the 'other' shape
                other_tag = tags[0] if tags else None
                if other_tag in self.sections and self.sections[other_tag].get("p_type") in ["RAMP", "TAPER RAMP", "THRESH RAMP", "DECK", "STEP"]:
                    oth_coords = [(o[i], o[i+1]) for i in range(0, len(o), 2)]
                elif len(o) > 4: 
                    oth_coords = [(o[i], o[i+1]) for i in range(0, len(o), 2)]
                else:
                    oth_coords = [(o[0],o[1]), (o[2],o[1]), (o[0],o[3]), (o[2],o[3])]

                for cx, cy in curr_corners:
                    for index, (ox, oy) in enumerate(oth_coords, start=0):
                        if abs(cx-ox) < self.snap_dist and abs(cy-oy) < self.snap_dist:
                            dx = ox - cx
                            dy = oy - cy
                            
                            # Check if the piece being moved is a STEP
                            tags_active = self.canvas.gettags(sid)
                            if "STEP" in [t.upper() for t in tags_active]:
                                step_inset = 5 * self.scale
                                
                                # 1. Extract the rotation angle and center of the host deck object
                                other_tag = tags[0] if tags else None
                                other_data = self.sections.get(other_tag, {})
                                rot = math.radians(other_data.get('rotation', 0.0))
                                
                                center_ox = sum(p[0] for p in oth_coords) / len(oth_coords)
                                center_oy = sum(p[1] for p in oth_coords) / len(oth_coords)
                                
                                # Use standard negative rotation angle to un-rotate space
                                cos_a = math.cos(-rot)
                                sin_a = math.sin(-rot)
                                
                                # 2. Project target coordinates into unrotated space relative to center
                                rot_oth = []
                                for pt in oth_coords:
                                    tx = pt[0] - center_ox
                                    ty = pt[1] - center_oy
                                    rx = tx * cos_a - ty * sin_a
                                    ry = tx * sin_a + ty * cos_a
                                    rot_oth.append((rx, ry))
                                    
                                # Find bounding faces in local unrotated space
                                r_xs = [pt[0] for pt in rot_oth]
                                r_ys = [pt[1] for pt in rot_oth]
                                min_ox, max_ox = min(r_xs), max(r_xs)
                                min_oy, max_oy = min(r_ys), max(r_ys)
                                
                                # Project the specific matching target corner into local unrotated space
                                t_x = ox - center_ox
                                t_y = oy - center_oy
                                r_ox = t_x * cos_a - t_y * sin_a
                                r_oy = t_x * sin_a + t_y * cos_a
                                
                                # 3. Identify local edge alignment (Increased tolerance to ensure tight locks)
                                is_top_edge = math.isclose(r_oy, min_oy, abs_tol=5.0)
                                is_bottom_edge = math.isclose(r_oy, max_oy, abs_tol=5.0)
                                is_left_edge = math.isclose(r_ox, min_ox, abs_tol=5.0)
                                is_right_edge = math.isclose(r_ox, max_ox, abs_tol=5.0)
                                
                                # 4. Calculate unrotated inset delta vectors
                                local_dx, local_dy = 0.0, 0.0
                                if is_top_edge and not (is_left_edge or is_right_edge):
                                    local_dy = step_inset
                                elif is_bottom_edge and not (is_left_edge or is_right_edge):
                                    local_dy = -step_inset
                                elif is_left_edge and not (is_top_edge or is_bottom_edge):
                                    local_dx = step_inset
                                elif is_right_edge and not (is_top_edge or is_bottom_edge):
                                    local_dx = -step_inset
                                else:
                                    # Junction corner fallback: look at moving step center vs deck center
                                    step_xs = [pt[0] for pt in curr_corners]
                                    step_ys = [pt[1] for pt in curr_corners]
                                    sc_x_avg = sum(step_xs) / len(step_xs)
                                    sc_y_avg = sum(step_ys) / len(step_ys)
                                    
                                    sc_x = (sc_x_avg - center_ox) * cos_a - (sc_y_avg - center_oy) * sin_a
                                    sc_y = (sc_x_avg - center_ox) * sin_a + (sc_y_avg - center_oy) * cos_a
                                    
                                    if abs(sc_y - r_oy) > abs(sc_x - r_ox):
                                        local_dy = step_inset if sc_y > r_oy else -step_inset
                                    else:
                                        local_dx = step_inset if sc_x > r_ox else -step_inset
                                        
                                # 5. Re-rotate local delta vector back to global canvas vectors
                                dx += local_dx * math.cos(rot) - local_dy * math.sin(rot)
                                dy += local_dx * math.sin(rot) + local_dy * math.cos(rot)

                            self.canvas.move(self.active_tag, dx, dy)
                            if self.active_tag in self.sections:
                                d = self.sections[self.active_tag]
                                # Update base coordinates for snap offset
                                if "x" in d: d["x"] += dx
                                if "y" in d: d["y"] += dy
                                if "points" in d:
                                    d["points"] = [p + dx if i % 2 == 0 else p + dy for i, p in enumerate(d["points"])]
                            self.update_post_tab()
                            return

        # Pass 2: Secondary priority for Ramps (Newest First)
        for other in all_shapes_reversed:
            tags = self.canvas.gettags(other)
            if self.active_tag in tags: continue
            if self.active_tag.startswith("Paver"): continue
            
            if "RAMP" in tags:
                o = self.canvas.coords(other)
                
                # Dynamic extraction of targeted snap vertices for the 'other' shape
                other_tag = tags[0] if tags else None
                if other_tag in self.sections and self.sections[other_tag].get("p_type") in ["RAMP", "TAPER RAMP", "THRESH RAMP", "DECK", "STEP"]:
                    oth_coords = [(o[i], o[i+1]) for i in range(0, len(o), 2)]
                elif len(o) > 4:
                    oth_coords = [(o[i], o[i+1]) for i in range(0, len(o), 2)]
                else:
                    oth_coords = [(o[0],o[1]), (o[2],o[1]), (o[0],o[3]), (o[2],o[3])]

                for cx, cy in curr_corners:
                    for ox, oy in oth_coords:
                        if abs(cx-ox) < self.snap_dist and abs(cy-oy) < self.snap_dist:
                            snap_dx = ox - cx
                            snap_dy = oy - cy
                            self.canvas.move(self.active_tag, snap_dx, snap_dy)
                            if self.active_tag in self.sections:
                                d = self.sections[self.active_tag]
                                # Update base coordinates for snap offset
                                if "x" in d: d["x"] += snap_dx
                                if "y" in d: d["y"] += snap_dy
                                if "points" in d:
                                    d["points"] = [
                                        p + snap_dx if i % 2 == 0 else p + snap_dy 
                                        for i, p in enumerate(d["points"])
                                    ]
                                    
                            self.update_post_tab() 
                            return

        self.update_post_tab()
        self.update_total_drop()
        self.canvas.focus_set() 

        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def show_polygon_rotation_popup(self, tag):
        """Spawns a compact floating control window to rotate the selected item."""
        if tag not in self.sections: return
        d = self.sections[tag]
        
        # Create a transient floating window
        popup = tk.Toplevel(self.root)
        popup.title(f"Rotate: {d.get('name', 'Component')}")
        popup.geometry("400x250")  
        popup.resizable(False, False)
        popup.transient(self.root)  
        popup.grab_set()       
        
        # Center the popup relative to the main application window
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        popup.geometry(f"+{root_x + 150}+{root_y + 150}")
        
        # Label instruction
        lbl = tk.Label(popup, text="Adjust Angle (Real-time Preview)", font=("Arial", 10, "bold"))
        lbl.pack(pady=(10, 5))
        
        # Manual entry row frame
        entry_frame = tk.Frame(popup)
        entry_frame.pack(pady=5)
        
        tk.Label(entry_frame, text="Degrees:").pack(side=tk.LEFT, padx=2)
        ent_deg = tk.Entry(entry_frame, width=8, justify="center")
        ent_deg.pack(side=tk.LEFT, padx=5)
        ent_deg.insert(0, "0.0")
        
        # Track previous position to calculate delta steps cleanly
        tracking = {"last_val": 0.0}
        
        # Slider logic (Updates entry and applies relative matrix rotation)
        def on_slider_move(val):
            current_val = float(val)
            diff = current_val - tracking["last_val"]
            
            # Apply transformation
            self.rotate_polygon_by_angle(tag, diff)
            tracking["last_val"] = current_val
            
            # Synchronize text field
            ent_deg.delete(0, tk.END)
            ent_deg.insert(0, f"{current_val:.1f}")

        slider = tk.Scale(popup, from_=-180, to=180, orient=tk.HORIZONTAL, 
                          resolution=0.5, length=280, command=on_slider_move)
        slider.pack(pady=5)

        # FIXED: Quick preset helper logic applies the transformation directly
        def apply_preset(angle):
            # Apply the rotation shift directly to the canvas object
            self.rotate_polygon_by_angle(tag, angle)
            
            # Safely close the window now that canvas translation is executed
            popup.destroy()
        
        # Quick presets row frame
        preset_frame = tk.Frame(popup)
        preset_frame.pack(pady=5)

        btn_minus_90 = tk.Button(preset_frame, text="-90°", width=7, command=lambda: apply_preset(-90.0))
        btn_minus_90.pack(side=tk.LEFT, padx=7)

        btn_minus_45 = tk.Button(preset_frame, text="-45°", width=7, command=lambda: apply_preset(-45.0))
        btn_minus_45.pack(side=tk.LEFT, padx=7)

        btn_plus_45 = tk.Button(preset_frame, text="+45°", width=7, command=lambda: apply_preset(45.0))
        btn_plus_45.pack(side=tk.LEFT, padx=7)
        
        btn_plus_90 = tk.Button(preset_frame, text="+90°", width=7, command=lambda: apply_preset(90.0))
        btn_plus_90.pack(side=tk.LEFT, padx=7)
        
        # Manual Button execution logic
        def on_manual_apply():
            try:
                target_angle = float(ent_deg.get())
                # Sync slider visually to match entry
                slider.set(target_angle)
            except ValueError:
                pass

        btn_apply = tk.Button(entry_frame, text="Apply Angle", command=on_manual_apply)
        btn_apply.pack(side=tk.LEFT, padx=5)
        
        # Done/Close button
        btn_close = tk.Button(popup, text="Done / Close", command=popup.destroy, width=15)
        btn_close.pack(pady=(8, 5))

    def rotate_polygon_coords(self, coords, degrees, center=None):
        """Rotates coordinate array around a specific pivot point (cx, cy) or its own center."""
        rad = math.radians(degrees)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        
        # Extract X and Y arrays
        xs = coords[0::2]
        ys = coords[1::2]
        
        # Determine rotation center: either passed in or calculated locally
        if center is not None:
            cx, cy = center
        else:
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            
        new_coords = []
        for x, y in zip(xs, ys):
            # Translate to origin
            tx = x - cx
            ty = y - cy
            
            # Rotate
            rx = tx * cos_a - ty * sin_a
            ry = tx * sin_a + ty * cos_a
            
            # Translate back
            new_coords.append(rx + cx)
            new_coords.append(ry + cy)
            
        return new_coords

    def show_canvas_rotation_popup(self, target_canvas, data_dict, tag, title_prefix="Component"):
        """Generic floating popup to rotate items live on any canvas (main canvas, post canvas, rail canvas)."""
        if tag not in data_dict:
            return

        d = data_dict[tag]

        popup = tk.Toplevel(self.root)
        popup.title(f"Rotate: {d.get('name', tag)}")
        popup.geometry("400x250")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        popup.geometry(f"+{root_x + 150}+{root_y + 150}")

        lbl = tk.Label(popup, text="Adjust Angle (Real-time Preview)", font=("Arial", 10, "bold"))
        lbl.pack(pady=(10, 5))

        entry_frame = tk.Frame(popup)
        entry_frame.pack(pady=5)

        tk.Label(entry_frame, text="Degrees:").pack(side=tk.LEFT, padx=2)
        ent_deg = tk.Entry(entry_frame, width=8, justify="center")
        ent_deg.pack(side=tk.LEFT, padx=5)
        ent_deg.insert(0, "0.0")

        tracking = {"last_val": 0.0}

        def on_slider_move(val):
            current_val = float(val)
            diff = current_val - tracking["last_val"]

            self.apply_rotation_to_item(target_canvas, data_dict, tag, diff)
            tracking["last_val"] = current_val

            ent_deg.delete(0, tk.END)
            ent_deg.insert(0, f"{current_val:.1f}")

        slider = tk.Scale(
            popup, from_=-180, to=180, orient=tk.HORIZONTAL,
            resolution=0.5, length=280, command=on_slider_move
        )
        slider.pack(pady=5)

        def apply_preset(angle):
            self.apply_rotation_to_item(target_canvas, data_dict, tag, angle)
            popup.destroy()

        preset_frame = tk.Frame(popup)
        preset_frame.pack(pady=5)

        btn_minus_90 = tk.Button(preset_frame, text="-90°", width=7, command=lambda: apply_preset(-90.0))
        btn_minus_90.pack(side=tk.LEFT, padx=7)

        btn_minus_45 = tk.Button(preset_frame, text="-45°", width=7, command=lambda: apply_preset(-45.0))
        btn_minus_45.pack(side=tk.LEFT, padx=7)

        btn_plus_45 = tk.Button(preset_frame, text="+45°", width=7, command=lambda: apply_preset(45.0))
        btn_plus_45.pack(side=tk.LEFT, padx=7)

        btn_plus_90 = tk.Button(preset_frame, text="+90°", width=7, command=lambda: apply_preset(90.0))
        btn_plus_90.pack(side=tk.LEFT, padx=7)

        def on_manual_apply():
            try:
                target_angle = float(ent_deg.get())
                slider.set(target_angle)
            except ValueError:
                pass

        btn_apply = tk.Button(entry_frame, text="Apply Angle", command=on_manual_apply)
        btn_apply.pack(side=tk.LEFT, padx=5)

        btn_close = tk.Button(popup, text="Done / Close", command=popup.destroy, width=15)
        btn_close.pack(pady=(8, 5))

    def apply_rotation_to_item(self, target_canvas, data_dict, tag, degrees):
        """Executes relative transformation on canvas shapes using a shared centroid."""
        if tag not in data_dict:
            return
        d = data_dict[tag]

        # 1. Update stored angle tracking
        if 'rotation_angle' in d:
            d['rotation_angle'] = (d.get('rotation_angle', 0.0) + degrees) % 360.0
        elif 'rotation' in d:
            d['rotation'] = (d.get('rotation', 0.0) + degrees) % 360.0

        # 2. Rotate Main Shape / Polygon & Find Shared Centroid
        centroid = None
        shape_items = target_canvas.find_withtag(f"{tag} && post_border") or target_canvas.find_withtag(f"{tag} && shape") or target_canvas.find_withtag(f"{tag}")
        
        if shape_items:
            sid = shape_items[0]
            coords = target_canvas.coords(sid)
            if coords:
                # Calculate main body center BEFORE or AFTER rotation (pivot point is identical)
                cx = sum(coords[0::2]) / (len(coords) // 2)
                cy = sum(coords[1::2]) / (len(coords) // 2)
                centroid = (cx, cy)
                
                # Rotate main polygon around its own center
                new_coords = self.rotate_polygon_coords(coords, degrees, center=centroid)
                target_canvas.coords(sid, *new_coords)
                
                if 'canvas_coords' in d:
                    d['canvas_coords'] = new_coords
                elif 'points' in d:
                    d['points'] = new_coords

        # Stop early if we don't have a reference shape centroid
        if not centroid:
            return

        # 3. Rotate Post Block (using shared centroid)
        block_pnum = f"block_{tag}"
        block_items = target_canvas.find_withtag(block_pnum)
        if block_items:
            b_coords = target_canvas.coords(block_items[0])
            if b_coords:
                new_b_coords = self.rotate_polygon_coords(b_coords, degrees, center=centroid)
                target_canvas.coords(block_items[0], *new_b_coords)

        # 4. Rotate Step Lines (using shared centroid)
        step_lines = target_canvas.find_withtag(f"{tag} && step_line")
        for line_id in step_lines:
            lc = target_canvas.coords(line_id)
            if len(lc) >= 4:
                new_line = self.rotate_polygon_coords(lc, degrees, center=centroid)
                target_canvas.coords(line_id, *new_line)

        # 5. Rotate Paver Grid Lines (using shared centroid!)
        paver_lines = target_canvas.find_withtag(f"{tag} && paver_line")
        for line_id in paver_lines:
            lc = target_canvas.coords(line_id)
            if len(lc) >= 4:
                new_line = self.rotate_polygon_coords(lc, degrees, center=centroid)
                target_canvas.coords(line_id, *new_line)

        # 6. Optional: Rotate / Orbit Canvas Text Label (using shared centroid)
        text_items = target_canvas.find_withtag(f"{tag} && Paver") or target_canvas.find_withtag(f"{tag} && text")
        for tid in text_items:
            if target_canvas.type(tid) == "text":
                tc = target_canvas.coords(tid)
                if len(tc) >= 2:
                    new_tc = self.rotate_polygon_coords(tc, degrees, center=centroid)
                    target_canvas.coords(tid, *new_tc)

        # 7. Side Preview update
        if hasattr(self, 'draw_component_detail') and target_canvas == getattr(self, 'canvas', None):
            self.draw_component_detail(d)

    def rotate_item(self, event):
        """Main canvas item rotation entry point."""
        print("Rotate Main Canvas Item")
        if not self.active_tag:
            return
        if self.active_tag in self.sections:
            self.show_canvas_rotation_popup(self.canvas, self.sections, self.active_tag, "Section")

    def rotate_post_item(self, event=None):
        """Post canvas item rotation entry point (handles both Posts and CrossBraces)."""
        print("Rotate Post Canvas Item")
        if not self.active_tag:
            return
        
        # Handle Posts
        if self.active_tag in self.post_entries:
            self.show_canvas_rotation_popup(self.post_canvas, self.post_entries, self.active_tag, "Post")
            
        # Handle Cross Braces
        elif self.active_tag in self.cross_brace_entries:
            self.show_canvas_rotation_popup(self.post_canvas, self.cross_brace_entries, self.active_tag, "CrossBrace")

    def rotate_rail_item(self, event=None):
        """Rail canvas rotation entry point."""
        print(f"Rotate Rail Item triggered for active_tag: {self.active_tag}")
        if not self.active_tag:
            print(" -> Aborted: No active_tag selected.")
            return
            
        if self.active_tag in self.rail_entries:
            print(f" -> Key '{self.active_tag}' found in rail_entries. Spawning popup...")
            self.show_canvas_rotation_popup(
                target_canvas=self.rail_canvas, 
                data_dict=self.rail_entries, 
                tag=self.active_tag, 
                title_prefix="Rail"
            )
        else:
            print(f" -> Aborted: '{self.active_tag}' not found in rail_entries! Current keys: {list(self.rail_entries.keys())}")


    def rotate_polygon_by_angle(self, tag, degrees):
        """Rotates a polygon canvas item around its geometric center by a relative angle."""
        import math
        if tag not in self.sections: return
        d = self.sections[tag]
        if 'points' not in d: return
        
        pts = d['points']
        
        # 1. Find geometric center (average of all x and y points)
        xs = pts[0::2]
        ys = pts[1::2]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        
        # 2. Convert degrees to radians
        rad = math.radians(degrees)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        
        # 3. Rotate every coordinate point around the center (cx, cy)
        new_pts = []
        for i in range(0, len(pts), 2):
            x = pts[i]
            y = pts[i+1]
            
            # Translate to origin
            dx = x - cx
            dy = y - cy
            
            # Rotate points
            nx = cx + (dx * cos_a - dy * sin_a)
            ny = cy + (dx * sin_a + dy * cos_a)
            new_pts.append(nx)
            new_pts.append(ny)
            
        # 4. Update memory tracking and canvas display
        d['points'] = new_pts

        # Read current rotation (default to 0.0), add the delta, and keep within a 0-360 window
        current_rot = d.get('rotation', 0.0)
        d['rotation'] = (current_rot + degrees) % 360.0
        print (f"Current rotation = {d['rotation']}")
        
        # Update the main polygon shape
        shape_ids = self.canvas.find_withtag(f"{tag} && shape")
        if shape_ids:
            self.canvas.coords(shape_ids[0], *new_pts)
            
        # Update text/label positions to stay centered on the component
        text_ids = self.canvas.find_withtag(f"{tag} && text")
        if text_ids:
            self.canvas.coords(text_ids[0], cx, cy)
            
        # 5. Handle Step Lines (Safely brought over from old method to turn with the piece)
        step_lines = self.canvas.find_withtag(f"{tag} && step_line")
        for line_id in step_lines:
            lc = self.canvas.coords(line_id) # Returns [x1, y1, x2, y2]
            
            # Rotate start point (x1, y1)
            dx1, dy1 = lc[0] - cx, lc[1] - cy
            new_x1 = cx + (dx1 * cos_a - dy1 * sin_a)
            new_y1 = cy + (dx1 * sin_a + dy1 * cos_a)
            
            # Rotate end point (x2, y2)
            dx2, dy2 = lc[2] - cx, lc[3] - cy
            new_x2 = cx + (dx2 * cos_a - dy2 * sin_a)
            new_y2 = cy + (dx2 * sin_a + dy2 * cos_a)
            
            # Apply new coordinates to the line
            self.canvas.coords(line_id, new_x1, new_y1, new_x2, new_y2)
            
        # Re-render the side preview panel view to match
        self.draw_component_detail(d)


    import math

    def apply_resize(self):
        # 1. Ensure there is an active selection and it exists in our data
        if not self.active_tag or self.active_tag not in self.sections: 
            return

        data = self.sections[self.active_tag]
        p_type = data.get("p_type", "").upper()
        
        print (f"P type is {p_type}")
        # 2. Guard: Only allow resizing for standard Ramps and Decks
        # Ignore Steps, Pavers, polygons, or reference points
        if p_type in ["STEP", "PAVER", "POLYGON", "REF_POINT"]:
            return

        # Parse inputs safely
        try:
            l = float(self.ent_len.get())
            w = float(self.ent_wid.get())
        except ValueError:
            return  # Handle non-numeric input gracefully

        # Update stored mathematical dimensions
        data.update({"l": l, "w": w})

        # 3. Update the Tab Title & Tab Label
        if 'tab_id' in data:
            self.notebook.tab(data['tab_id'], text=data['name'])
        if 'label' in data and hasattr(data['label'], 'config'):
            data['label'].config(text=f"{data['name']} Detail View")

        # 4. Find Canvas Elements
        shape_items = self.canvas.find_withtag(f"{self.active_tag} && shape") or self.canvas.find_withtag(f"{self.active_tag}")
        text_items = self.canvas.find_withtag(f"{self.active_tag} && text")

        if shape_items:
            sid = shape_items[0]
            c = self.canvas.coords(sid)

            if c and len(c) >= 8:
                # Anchor point: keep top-left corner fixed at original position
                x0, y0 = c[0], c[1]

                # Convert length and width to pixel units
                l_px = l * self.scale
                w_px = w * self.scale

                # Retrieve rotation angle (defaults to 0.0 if not stored)
                angle_deg = data.get('rotation_angle', data.get('rotation', 0.0))
                rad = math.radians(angle_deg)
                cos_a = math.cos(rad)
                sin_a = math.sin(rad)

                # Local unrotated box vertices: (0,0), (L,0), (L,W), (0,W)
                local_pts = [(0, 0), (l_px, 0), (l_px, w_px), (0, w_px)]

                new_coords = []
                for lx, ly in local_pts:
                    # Rotate local coordinates
                    rx = lx * cos_a - ly * sin_a
                    ry = lx * sin_a + ly * cos_a
                    # Translate back to origin anchor (x0, y0)
                    new_coords.extend([x0 + rx, y0 + ry])

                # Update shape coordinates
                self.canvas.coords(sid, *new_coords)
                data['points'] = new_coords  # Keep coordinate tracking updated

                # 5. Update Center Text Label
                if text_items:
                    tid = text_items[0]
                    # Calculate new centroid of 4-point polygon
                    cx = sum(new_coords[0::2]) / 4
                    cy = sum(new_coords[1::2]) / 4
                    
                    self.canvas.itemconfig(
                        tid, 
                        text=f"{data['name']}\n{self.format_inchesquarter(l)}x{self.format_inchesquarter(w)}"
                    )
                    self.canvas.coords(tid, cx, cy)

        # 6. Refresh Detail Tab & Drop Calculations
        self.draw_component_detail(data)
        self.update_total_drop()

    def delete_item(self):
        print (f"Delete {self.active_tag}")
        if self.active_tag:
        # 1. Get the tags BEFORE deleting the object
            tags = self.canvas.gettags(self.active_tag)
            #rint("All tags:", tags)

            # 2. Delete the visual object from the canvas
            self.canvas.delete(self.active_tag)

            # 3. If it's a paver, find the PaverCount tag and extract the number
            if self.active_tag.startswith("Paver"):
                for tag in tags:
                    print (tag)
                    if tag.startswith("PaverCount"):
                        # Extract everything after "PaverCount"
                        num_str = tag[len("PaverCount"):]  # Slices the string from index 10 onward
                        print (num_str)
                        try:
                            count_to_remove = int(num_str)
                            
                            # Deduct from your total paver count attribute
                            if hasattr(self, 'paver_count'):
                                self.paver_total -= count_to_remove
                                # Ensure it doesn't accidentally dip below 0
                                self.paver_total = max(0, self.paver_total) 
                                self.refresh_materials_matrix()
                            
                            #rint(f"Removed {count_to_remove} pavers. New total: {self.paver_total}")
                        except ValueError:
                            print(f"Could not convert '{num_str}' to an integer.")
                        
                        break  # Found it, no need to keep looping through tags
            elif self.active_tag in self.sections:
                # Remove the specific tab from the notebook
                self.notebook.forget(self.sections[self.active_tag]['tab_id'])
            del self.sections[self.active_tag]
            self.canvas.delete(self.active_tag)
            self.active_tag = None
            self.update_total_drop()

    def setup_posts_tab(self):
        # Top control bar
        controls = tk.Frame(self.tab_posts, pady=10)
        controls.pack(fill=tk.X)
        tk.Button(controls, text="GENERATE POST PLACEMENT", command=self.generate_posts, 
                  bg="#28a745", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        # Place this near your other button code
        tk.Button(controls, text="Add Comment Box", command=lambda: self.spawn_comment_box(self.post_canvas),bg="#F08AF3", fg="black",font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=20)
        
        tk.Button(controls, text="ADD POST", command=self.spawn_post, 
                  bg="#28a745", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=10)
        #tk.Button(controls, text="DebugPosts", command=self.print_debug_info, 
        #          bg="#28a745", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=15)
        self.addCrossBrace_btn = tk.Button(controls, text="Add Cross Brace", command=self.post_crossbrace, 
                  bg="#28a745", fg="white", font=("Arial", 10, "bold")) #.pack(side=tk.RIGHT, padx=20)

        self.togglePostBlock_btn = tk.Button(controls, text="Toggle Post Block", command=self.post_block_toggle, 
                  bg="#535554", fg="white", font=("Arial", 10, "bold"))

        self.toggleDummyPost_btn = tk.Button(controls, text="Toggle Dummy Post", command=self.dummy_post_toggle, 
                  bg="#122caf", fg="white", font=("Arial", 10, "bold"))

        self.toggleInsetPost_btn = tk.Button(controls, text="Toggle Inset", command=self.inset_post_toggle, 
                          bg="#af078e", fg="white", font=("Arial", 10, "bold"))
        

        self.delete_btn = tk.Button(
            controls,text="Delete Selection", 
            command= self.delete_selected_post, # Pass None if calling manually
            bg="#de2e2e", fg="white", font=("Arial", 10, "bold")
            )

        # Main container for Canvas and Table
        self.post_container = tk.Frame(self.tab_posts)
        self.post_container.pack(expand=True, fill="both")

        # --- SCROLLABLE CANVAS SECTION ---
        # Create a frame to hold canvas + its scrollbars
        canvas_frame = tk.Frame(self.post_container)
        canvas_frame.pack(side=tk.LEFT, expand=True, fill="both")

        # Add vertical and horizontal scrollbars for the canvas
        v_scroll_c = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        h_scroll_c = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        
        self.post_canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=1,
                                     yscrollcommand=v_scroll_c.set,
                                     xscrollcommand=h_scroll_c.set)
        
        # Grid layout for canvas scrollbars
        self.post_canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll_c.grid(row=0, column=1, sticky="ns")
        h_scroll_c.grid(row=1, column=0, sticky="ew")
        
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        v_scroll_c.config(command=self.post_canvas.yview)
        h_scroll_c.config(command=self.post_canvas.xview)

        # --- SCROLLABLE TABLE SECTION ---
        # Create a frame for the Post Specification Table
        self.post_table_frame = tk.Frame(self.post_container, width=500, bg="#f8f9fa", padx=10)
        self.post_table_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.post_table_frame.pack_propagate(False)

        tk.Label(self.post_table_frame, text="POST SPECIFICATIONS", font=("Arial", 11, "bold"), bg="#f8f9fa").pack(pady=10)
        
        # Outer table container for the scrollbar
        table_scroll_container = tk.Frame(self.post_table_frame, bg="white")
        table_scroll_container.pack(fill=tk.BOTH, expand=True)

        v_scroll_t = tk.Scrollbar(table_scroll_container, orient=tk.VERTICAL)
        v_scroll_t.pack(side=tk.RIGHT, fill=tk.Y)

        # Use a canvas to make the grid scrollable
        self.table_scroll_canvas = tk.Canvas(table_scroll_container, bg="white", 
                                            highlightthickness=0, yscrollcommand=v_scroll_t.set)
        self.table_scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll_t.config(command=self.table_scroll_canvas.yview)

        # The actual grid rows live inside this frame
        self.post_grid = tk.Frame(self.table_scroll_canvas, bg="white")
        
        # Place the grid inside the scrolling canvas
        self.table_scroll_canvas.create_window((0, 0), window=self.post_grid, anchor="nw", tags="table_window")
        
        # Bind resize event to update scroll region
        self.post_grid.bind("<Configure>", lambda e: self.table_scroll_canvas.config(scrollregion=self.table_scroll_canvas.bbox("all")))
        
        # Bind table width to canvas width
        self.table_scroll_canvas.bind("<Configure>", lambda e: self.table_scroll_canvas.itemconfig("table_window", width=e.width))
        #allow user to click to unselect post
        self.post_canvas.bind("<Button-1>", self.deselect_all_post, add="+")

        self.post_canvas.bind("<r>", self.rotate_post_item)
        self.post_canvas.bind("<R>", self.rotate_post_item)
        

    def generate_posts(self):
        # 1. First, calculate the sequence elevations (start/end) for all sections
        # clear braces
        self.cross_brace_entries = {}
        self.postbrace_count = 0
        self.post_block_count = 0
        self.display_crossbracetable(self.active_tag)
                    
        self.calculate_elevations() 
        
        self.post_canvas.delete("all")
        self._post_drag_data = {"item": None, "x": 0, "y": 0}
        
        occupied_slots = [] 
        self.post_count = 1
        self.post_table_data = [] 
        
        # Background Reference logic
        for tag, data in self.sections.items():
            if tag == "REF_POINT": continue
            
            sid = self.canvas.find_withtag(f"{tag} && shape")[0]
            c = self.canvas.coords(sid)
            if len(c) > 4:
                self.post_canvas.create_polygon(*c, fill="", outline="#bbb", dash=(4,4))
                xs = c[0::2]
                ys = c[1::2]
                center_x = sum(xs) / len(xs)
                center_y = sum(ys) / len(ys)
                self.post_canvas.create_text(center_x, center_y, text=data['name'], fill="#999", font=("Arial", 10, "bold"), anchor="center")
            else:
                self.post_canvas.create_rectangle(*c, outline="#bbb", dash=(4,4))
                self.post_canvas.create_text((c[0]+c[2])/2, (c[1]+c[3])/2, text=data['name'], fill="#999", font=("Arial", 10, "bold"), anchor="center")

        previous_center = None 

        sorted_sections = sorted(
            self.sections.items(),
            key=lambda item: 0 if item[1].get('p_type') == "STEP" 
                            else (2 if item[1].get('p_type') == "THRESH RAMP" else 1)
        )

        for tag, data in sorted_sections:
            if tag == "REF_POINT" or tag.startswith("Paver"):
                continue
                
            section_name = data['name']
            sid = self.canvas.find_withtag(f"{tag} && shape")[0]
            c = self.canvas.coords(sid) 
            
            # Extract ALL corners (preserving full vertex list for polygons)
            corners = [(c[i], c[i+1]) for i in range(0, len(c), 2)]
            center_x = sum(x for x, y in corners) / len(corners)
            center_y = sum(y for x, y in corners) / len(corners)
            current_center = (center_x, center_y)

            is_ramp = "RAMP" in section_name.upper()
            is_step = data.get('p_type') == "STEP"
            is_polygon = data.get('p_type') == "POLYGON" or len(corners) != 4

            if previous_center is None:
                ref_items = self.canvas.find_withtag("REF_POINT")
                if ref_items:
                    rc = self.canvas.coords(ref_items[0])
                    compare_pt = ((rc[0] + rc[2]) / 2, (rc[1] + rc[3]) / 2)
                else:
                    compare_pt = current_center
            else:
                compare_pt = previous_center

            corner_distances = [math.hypot(cx - compare_pt[0], cy - compare_pt[1]) for cx, cy in corners]
            sorted_dists = sorted(corner_distances)
            
            if len(sorted_dists) >= 4:
                midpoint_threshold = (sorted_dists[1] + sorted_dists[2]) / 2
            else:
                midpoint_threshold = sum(sorted_dists) / len(sorted_dists)

            # ==========================================
            # 1. DYNAMIC VECTOR ANGLE EXTRACTION
            # Extract angle along target length L to handle short ramps (L < W)
            # ==========================================
            target_l_px = data.get('l', 0) * self.scale

            if is_step:
                step_lines = self.canvas.find_withtag(f"{tag} && step_line")
                if step_lines:
                    lc = self.canvas.coords(step_lines[0])
                    section_angle = math.atan2(lc[3] - lc[1], lc[2] - lc[0])
                    if abs(lc[0] - lc[2]) < 1: 
                        section_angle -= math.pi / 2
                else:
                    section_angle = math.atan2(corners[1][1] - corners[0][1], corners[1][0] - corners[0][0])
            elif is_ramp and len(corners) >= 4:
                # Find edge vector that matches target length L best
                best_diff = float('inf')
                best_angle = 0.0
                num_pts = len(corners)
                for i in range(num_pts):
                    p1 = corners[i]
                    p2 = corners[(i + 1) % num_pts]
                    edge_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                    diff = abs(edge_len - target_l_px)
                    if diff < best_diff:
                        best_diff = diff
                        best_angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
                section_angle = best_angle
            elif len(corners) >= 2:
                section_angle = math.atan2(corners[1][1] - corners[0][1], corners[1][0] - corners[0][0])
            else:
                section_angle = 0.0

            cos_a = math.cos(-section_angle) # Flatten to local
            sin_a = math.sin(-section_angle)
            cos_r = math.cos(section_angle)  # Restore to global
            sin_r = math.sin(section_angle)

            for idx, (cx, cy) in enumerate(corners):
                insetflag = False
                post_elev = data.get('elev_start', 0.0) if corner_distances[idx] < midpoint_threshold else data.get('elev_end', 0.0)

                # ==========================================
                # 2. FLATTEN CORNER TO LOCAL SPACE 
                # ==========================================
                tx = cx - center_x
                ty = cy - center_y
                local_x = tx * cos_a - ty * sin_a
                local_y = tx * sin_a + ty * cos_a
                
                loc_left = local_x < 0
                loc_top = local_y < 0

                # ==========================================
                # 3. OVERLAP PROBES (Tkinter Physics Check)
                # ==========================================
                probe_dist = 5.0
                lp_x_out = local_x + (-probe_dist if loc_left else probe_dist)
                lp_y_out = local_y + (-probe_dist if loc_top else probe_dist)
                
                # Probe 1: Outward on X axis
                gp1_x = (lp_x_out * cos_r - local_y * sin_r) + center_x
                gp1_y = (lp_x_out * sin_r + local_y * cos_r) + center_y
                
                # Probe 2: Outward on Y axis
                gp2_x = (local_x * cos_r - lp_y_out * sin_r) + center_x
                gp2_y = (local_x * sin_r + lp_y_out * cos_r) + center_y
                
                neighbor_side = False
                neighbor_top_bot = False
                
                for o_tag in self.sections:
                    if o_tag == tag or "Paver" in o_tag or o_tag == "REF_POINT": continue
                    o_ids = self.canvas.find_withtag(f"{o_tag} && shape")
                    if o_ids:
                        overlap1 = self.canvas.find_overlapping(gp1_x-1, gp1_y-1, gp1_x+1, gp1_y+1)
                        if o_ids[0] in overlap1: neighbor_side = True
                        
                        overlap2 = self.canvas.find_overlapping(gp2_x-1, gp2_y-1, gp2_x+1, gp2_y+1)
                        if o_ids[0] in overlap2: neighbor_top_bot = True

                # ==========================================
                # 4. CALCULATE POST GEOMETRY
                # ==========================================
                bot_step = False 
                bot_ramp = False 
                rotated_post_points = None # Will hold direct points for polygon branch

                if is_polygon:
                    # Helper function to check if a point lies inside any existing deck/ramp/polygon
                    def point_inside_any_other_shape(px, py, current_shape_name):
                        for shape_data in self.sections.values():
                            if shape_data.get('name') == current_shape_name:
                                continue
                            pts = shape_data.get('points', [])
                            if len(pts) >= 6:
                                poly = [(pts[i], pts[i+1]) for i in range(0, len(pts), 2)]
                                inside = False
                                j = len(poly) - 1
                                for i in range(len(poly)):
                                    if ((poly[i][1] > py) != (poly[j][1] > py)) and \
                                       (px < (poly[j][0] - poly[i][0]) * (py - poly[i][1]) / (poly[j][1] - poly[i][1]) + poly[i][0]):
                                        inside = not inside
                                    j = i
                                if inside:
                                    return True
                        return False

                    # Helper to build post square for a given edge vector choice
                    def try_build_post(use_u1):
                        target_pt = corners[(idx - 1) % len(corners)] if use_u1 else corners[(idx + 1) % len(corners)]
                        v_x, v_y = target_pt[0] - cx, target_pt[1] - cy
                        length = math.hypot(v_x, v_y)
                        u_x, u_y = (v_x / length, v_y / length) if length != 0 else (1, 0)

                        n_x, n_y = -u_y, u_x
                        dot_check = (center_x - cx) * n_x + (center_y - cy) * n_y
                        if dot_check > 0:
                            n_x, n_y = -n_x, -n_y

                        # Check if inset applies
                        was_inset = False
                        if not neighbor_side and not neighbor_top_bot:
                            b_start_x = cx + u_x * self.inset
                            b_start_y = cy + u_y * self.inset
                            was_inset = True
                        else:
                            b_start_x, b_start_y = cx, cy

                        p0 = (b_start_x, b_start_y)
                        p1 = (b_start_x + u_x * self.p_size, b_start_y + u_y * self.p_size)
                        p2 = (p1[0] + n_x * self.p_size, p1[1] + n_y * self.p_size)
                        p3 = (p0[0] + n_x * self.p_size, p0[1] + n_y * self.p_size)

                        pts = [p0[0], p0[1], p1[0], p1[1], p2[0], p2[1], p3[0], p3[1]]
                        
                        post_mid_x = (p0[0] + p2[0]) / 2.0
                        post_mid_y = (p0[1] + p2[1]) / 2.0
                        has_collision = point_inside_any_other_shape(post_mid_x, post_mid_y, section_name)
                        
                        return pts, has_collision, was_inset

                    # Try primary direction (u1 vector)
                    rotated_post_points, is_colliding, insetflag = try_build_post(use_u1=True)

                    # If candidate post collides into another deck, flip to u2 vector
                    if is_colliding:
                        rotated_post_points, _, insetflag = try_build_post(use_u1=False)

                elif is_step:
                    bot_step = not neighbor_side and not neighbor_top_bot
                    
                    step_lines = self.canvas.find_withtag(f"{tag} && step_line")
                    if step_lines:
                        lc = self.canvas.coords(step_lines[0])
                        l_x1 = (lc[0] - center_x) * cos_a - (lc[1] - center_y) * sin_a
                        l_x2 = (lc[2] - center_x) * cos_a - (lc[3] - center_y) * sin_a
                        l_y1 = (lc[0] - center_x) * sin_a + (lc[1] - center_y) * cos_a
                        l_y2 = (lc[2] - center_x) * sin_a + (lc[3] - center_y) * cos_a
                        
                        steps_are_horizontal = abs(l_y1 - l_y2) < abs(l_x1 - l_x2)
                    else:
                        steps_are_horizontal = True

                    if steps_are_horizontal:
                        local_px = local_x - self.p_size if loc_left else local_x
                        local_py = local_y if loc_top else local_y - self.p_size
                    else:
                        local_px = local_x if loc_left else local_x - self.p_size
                        local_py = local_y - self.p_size if loc_top else local_y
                    
                elif is_ramp:
                    bot_ramp = not neighbor_side and not neighbor_top_bot
                    local_py = local_y - self.p_size if loc_top else local_y
                    local_px = local_x if loc_left else local_x - self.p_size
                        
                else: # Rectangular Deck
                    if not neighbor_side and not neighbor_top_bot:
                        is_shared_junction = False
                        for o_tag in self.sections:
                            if o_tag == tag or "Paver" in o_tag or o_tag == "REF_POINT": continue
                            o_ids = self.canvas.find_withtag(f"{o_tag} && shape")
                            if o_ids:
                                oc = self.canvas.coords(o_ids[0])
                                for i in range(0, len(oc), 2):
                                    if math.isclose(cx, oc[i], abs_tol=3.0) and math.isclose(cy, oc[i+1], abs_tol=3.0):
                                        is_shared_junction = True
                                        break
                                if is_shared_junction: break
                        
                        if not is_shared_junction:
                            insetflag = True
                            local_px = local_x - self.p_size if loc_left else local_x
                            local_py = local_y + self.inset if loc_top else local_y - self.inset - self.p_size
                        else:
                            local_px = local_x if loc_left else local_x - self.p_size
                            local_py = local_y if loc_top else local_y - self.p_size
                    else:
                        if neighbor_side and not loc_top: 
                            local_py = local_y
                            local_px = local_x - self.p_size if not loc_left else local_x 
                        elif neighbor_side: 
                            local_py = local_y - self.p_size
                            local_px = local_x if loc_left else local_x - self.p_size
                        else: 
                            local_px = local_x - self.p_size if loc_left else local_x
                            local_py = local_y if loc_top else local_y - self.p_size

                # ==========================================
                # 5. BUILD POST & RESTORE TO GLOBAL SPACE
                # ==========================================
                if rotated_post_points is None:
                    local_post_corners = [
                        (local_px, local_py),
                        (local_px + self.p_size, local_py),
                        (local_px + self.p_size, local_py + self.p_size),
                        (local_px, local_py + self.p_size)
                    ]
                    
                    rotated_post_points = []
                    for lx, ly in local_post_corners:
                        gx = (lx * cos_r - ly * sin_r) + center_x
                        gy = (lx * sin_r + ly * cos_r) + center_y
                        rotated_post_points.extend([gx, gy])
                
                # --- TRUE GEOMETRIC CENTER OF POST ---
                post_xs = rotated_post_points[0::2]
                post_ys = rotated_post_points[1::2]
                post_center_x = sum(post_xs) / 4.0
                post_center_y = sum(post_ys) / 4.0

                px, py = rotated_post_points[0], rotated_post_points[1]

                too_close = False
                collision_threshold = 12.0 * self.scale

                touches_step = False
                for o_tag, o_data in self.sections.items():
                    if o_data.get('p_type') == 'STEP':
                        s_ids = self.canvas.find_withtag(f"{o_tag} && shape")
                        if s_ids:
                            sc = self.canvas.coords(s_ids[0])
                            for i in range(0, len(sc), 2):
                                if math.hypot(cx - sc[i], cy - sc[i+1]) < 10.0:
                                    touches_step = True
                                    break
                    if touches_step: break

                if not is_step and touches_step:
                    too_close = True
                else:
                    for ex, ey in occupied_slots:
                        distance = math.hypot(cx - ex, cy - ey)
                        if distance < collision_threshold:
                            too_close = True
                            break

                if not too_close or is_step:
                    p_tag = f"P{self.post_count}"

                    if is_step:
                        inset_target_distance = self.inset
                        post_corners = [(rotated_post_points[i], rotated_post_points[i+1]) for i in range(0, 8, 2)]

                        for o_tag, o_data in self.sections.items():
                            if "DECK" in o_data['name'].upper():
                                deck_shape_ids = self.canvas.find_withtag(f"{o_tag} && shape")
                                if deck_shape_ids:
                                    o = self.canvas.coords(deck_shape_ids[0])
                                    deck_corners = [(o[i], o[i+1]) for i in range(0, len(o), 2)]
                                    for pc_x, pc_y in post_corners:
                                        for dc_x, dc_y in deck_corners:
                                            if abs(math.hypot(pc_x - dc_x, pc_y - dc_y) - inset_target_distance) < 0.5:
                                                insetflag = True
                                                break
                                        if insetflag: break
                            if insetflag: break

                    if p_tag not in self.post_entries:
                        self.post_entries[p_tag] = {
                            'deck': tk.StringVar(value=f"{post_elev:.1f}"),
                            'grade': tk.StringVar(value="0.0"),
                            'below': tk.StringVar(value=18.0),
                            'total': tk.StringVar(value="0.0"),
                            'canvas_coords': rotated_post_points,
                            'label_coords': [px + self.p_size/2, py - 12],
                            'is_dummy': False,
                            'bot_step': bot_step,
                            'bot_ramp': bot_ramp,
                            'og_grade':tk.StringVar(value="0.0"),
                            'is_inset': insetflag,
                            'rotation_angle': math.degrees(section_angle)
                        }
                    
                    self.post_table_data.append((self.post_count, False, tag, post_elev, bot_step, bot_ramp, 0, insetflag))
                    
                    self.post_canvas.create_polygon(*rotated_post_points, fill="white", outline="black", tags=(p_tag, "movable_post", "post_border"))
                    self.post_entries[p_tag]['canvas_coords'] = rotated_post_points

                    postlabtext = f"P{self.post_count} (i)" if insetflag else f"P{self.post_count}"
                    self.post_canvas.create_text(post_center_x, min(post_ys) - 12, text=postlabtext, font=("Arial", 10, "bold"), tags=(p_tag, "movable_post"))
                    
                    if insetflag:
                        self.post_canvas.create_text(post_center_x, post_center_y, text="I", font=("Courier", 6, "bold"), tags=(p_tag, "movable_post"))

                    self.bind_item(p_tag)
                    occupied_slots.append((cx, cy))
                    self.post_count += 1

            # ==========================================
            # DUMMY POST LOGIC (Mid-span support > 96")
            # ==========================================
            if is_ramp and data.get('l', 0) > 96:
                l_xs = [(p[0]-center_x)*cos_a - (p[1]-center_y)*sin_a for p in corners]
                l_ys = [(p[0]-center_x)*sin_a + (p[1]-center_y)*cos_a for p in corners]
                mid_l = (min(l_xs) + max(l_xs)) / 2
                
                dummy_elev = (data.get('elev_start', 0) + data.get('elev_end', 0)) / 2
                
                dummies_local = [
                    (mid_l - self.p_size/2, min(l_ys) - self.p_size), 
                    (mid_l - self.p_size/2, max(l_ys))
                ]

                for dl_x, dl_y in dummies_local:
                    p_tag = f"P{self.post_count}" 
                    
                    local_dummy_corners = [(dl_x, dl_y), (dl_x + self.p_size, dl_y), (dl_x + self.p_size, dl_y + self.p_size), (dl_x, dl_y + self.p_size)]
                    rotated_dummy_points = []
                    for lx, ly in local_dummy_corners:
                        gx = (lx * cos_r - ly * sin_r) + center_x
                        gy = (lx * sin_r + ly * cos_r) + center_y
                        rotated_dummy_points.extend([gx, gy])

                    if p_tag not in self.post_entries:
                        self.post_entries[p_tag] = {
                            'deck': tk.StringVar(value=f"{dummy_elev:.1f}"),
                            'grade': tk.StringVar(value="0.0"),
                            'below': tk.StringVar(value="18.0"),
                            'total': tk.StringVar(value="0.0"),
                            'canvas_coords': rotated_dummy_points,
                            'label_coords': [rotated_dummy_points[0] + self.p_size/2, rotated_dummy_points[1] - 12],
                            'is_dummy': True,
                            'bot_step': False,
                            'bot_ramp': bot_ramp,
                            'og_grade': tk.StringVar(value="0.0"),
                            'is_inset': False,
                            'rotation_angle': math.degrees(section_angle)
                        }
                    
                    self.post_table_data.append((self.post_count, True, tag, dummy_elev, False, bot_ramp, 0, False))
                    self.post_canvas.create_polygon(*rotated_dummy_points, fill="#211313", outline="blue", tags=(p_tag, "movable_post", "post_border"))
                    self.post_canvas.create_text(rotated_dummy_points[0] + self.p_size/2, rotated_dummy_points[1] - 12, text=f"P{self.post_count} (D)", font=("Arial", 8, "italic"), tags=(p_tag, "movable_post"))
                    
                    self.post_count += 1
                    self.bind_item(p_tag)
                    
            if not is_step: previous_center = current_center

        self.update_post_table(self.post_table_data)
        self.post_canvas.config(scrollregion=self.post_canvas.bbox("all"))
        self.update_post_optimization()
        self.addCrossBrace_btn.pack(side=tk.RIGHT, padx=10)


    def spawn_post(self):
        p_tag = f"P{self.post_count}"

        is_dummy = messagebox.askyesno("Post Configuration", "Is this a dummy/temporary post?")
        #rint(is_dummy)
        fill_color = "#211313" if is_dummy else "white"
        outline_color = "blue" if is_dummy else "black"
        label_text = p_tag + (" (D)" if is_dummy else "")
        
        # 8-point polygon representation for rotation: top-left, top-right, bottom-right, bottom-left
        poly_coords = [
            150, 30,
            150 + self.p_size, 30,
            150 + self.p_size, 30 + self.p_size,
            150, 30 + self.p_size
        ]

        if p_tag not in self.post_entries:
            self.post_entries[p_tag] = {
                'deck': tk.StringVar(value="40.0"),
                'grade': tk.StringVar(value="0.0"),
                'below': tk.StringVar(value="18.0"),
                'total': tk.StringVar(value="0.0"),
                'canvas_coords': poly_coords,
                'label_coords': [150 + self.p_size/2, 30 - 12],
                'is_dummy': is_dummy,
                'bot_step': False,
                'bot_ramp': False,
                'og_grade': tk.StringVar(value="0.0"),
                'is_inset': False,
                'rotation_angle': 0.0
            }

        # Store (Post Num, is_dummy, parent_tag, specific_elevation)
        self.post_table_data.append((self.post_count, is_dummy, p_tag, 0, 0, 0, 0, False))
        
        self.post_canvas.create_polygon(*poly_coords, 
                                        fill=fill_color, outline=outline_color, 
                                        tags=(p_tag, "movable_post", "post_border"))
        self.post_entries[p_tag]['canvas_coords'] = poly_coords

        self.post_canvas.create_text(150 + self.p_size/2, 30 - 12, 
                                    text=label_text, 
                                    font=("Arial", 10, "bold"),
                                    tags=(p_tag, "movable_post"))
        self.post_entries[p_tag]['label_coords'] = [150 + self.p_size/2, 30 - 12]
        self.post_count += 1
        self.bind_item(p_tag)

        self.active_tag = p_tag
        self.update_delete_button_visibility()

        # 5. Refresh
        self.update_post_table(self.post_table_data)
        self.update_post_optimization()


    def dummy_post_toggle(self):
        if self.active_tag:
            print("Dummy Post Toggle")
            print(self.active_tag)
            p_tag = self.active_tag
            tags = self.post_canvas.gettags(self.active_tag)
            print(tags)
            
            print(self.post_entries[self.active_tag])

            post_data = self.post_entries[self.active_tag]              
            print(f"Post Data {post_data}")
            dummynow = post_data.get("is_dummy")
            if dummynow:
                # --- TOGGLE OFF: Remove the block ---
                print(f"Removing dummy post for {self.active_tag}")
                
                if self.active_tag in self.post_entries:
                    #change these values before evaluation
                    self.post_entries[p_tag]["is_dummy"] = False

                    post_data = self.post_entries[self.active_tag]              
                    print(f"Post Data {post_data}")
                    print(post_data.get("is_dummy"))
                    is_dummy_val = str(post_data.get("is_dummy").get()).strip().lower() == "true" if hasattr(post_data.get("is_dummy"), 'get') else bool(post_data.get("is_dummy"))
                    bot_step_val = str(post_data.get("bot_step").get()).strip().lower() == "true" if hasattr(post_data.get("bot_step"), 'get') else bool(post_data.get("bot_step"))
                    bot_ramp_val = str(post_data.get("bot_ramp").get()).strip().lower() == "true" if hasattr(post_data.get("bot_ramp"), 'get') else bool(post_data.get("bot_ramp"))
                    
                    print(f"Evaluated Flags -> is_dummy: {is_dummy_val}, bot_step: {bot_step_val}, bot_ramp: {bot_ramp_val}")
                    # Determine the correct original below grade value based on step/ramp flags
                    if (bot_step_val or bot_ramp_val) and not is_dummy_val:
                        original_below = 24.0
                    else:
                        original_below = 0.0 if is_dummy_val else 18.0
                        
                    self.post_entries[p_tag]["below"].set(str(original_below))

                    # Restore the 6 inches to Above Grade
                    try:
                        current_grade = float(post_data["og_grade"].get())
                    except ValueError:
                        current_grade = 0.0
                    
                    self.post_entries[p_tag]["grade"].set(f"{current_grade:.1f}")
            
            else:   #not a dummy now
                self.post_entries[p_tag]["below"].set(str(0.0))
                self.post_entries[p_tag]["grade"].set(f"{7.0:.1f}")
                self.post_entries[p_tag]["is_dummy"] = True
                #update naming for D
                print("Make Dummy")
            
            #formatting for dummy post
            is_dummy = self.post_entries[p_tag]["is_dummy"]
            print(f"Is this dummy now {is_dummy}")
            fill_color = "#211313" if is_dummy else "white"
            outline_color = "blue" if is_dummy else "black"
            label_text = p_tag + (" (D)" if is_dummy else "")

            # Find all canvas objects matching this post's tag
            for item in self.post_canvas.find_withtag(p_tag):
                item_type = self.post_canvas.type(item)
                if item_type in ("polygon", "rectangle"):
                    self.post_canvas.itemconfig(item, fill=fill_color, outline=outline_color)
                elif item_type == "text":
                    self.post_canvas.itemconfig(item, text=label_text)

            # Update post_table_data if it contains this tag to maintain data alignment
            try:
                tag_id = int(p_tag.replace("P", ""))
            except ValueError:
                tag_id = None

            # Update post_table_data if it contains this tag to maintain data alignment
            if tag_id is not None:
                for i, row in enumerate(self.post_table_data):
                    if row[0] == tag_id:
                        # Reconstruct tuple with updated is_dummy flag status (index 1)
                        temp_list = list(row)
                        temp_list[1] = is_dummy
                        self.post_table_data[i] = tuple(temp_list)
                        print(f"Post table update for {p_tag} (ID: {tag_id}) {is_dummy}")
                        break

            # Refresh UI elements
            #self.update_post_table(self.post_table_data)

            # Re-run post optimization regardless of whether we turned it ON or OFF
            self.update_post_table(self.post_table_data)
            self.update_post_optimization()
            self.refresh_materials_matrix()

    def inset_post_toggle(self):
        if self.active_tag:
            print("Inset Post Toggle")
            print(self.active_tag)
            p_tag = self.active_tag
            tags = self.post_canvas.gettags(self.active_tag)
            print(tags)
            
            print(self.post_entries[self.active_tag])

            post_data = self.post_entries[self.active_tag]              
            print(f"Post Data {post_data}")
            
            # Determine existing state safely (handles boolean or StringVar)
            insetnow = post_data.get("is_inset")
            if hasattr(insetnow, 'get'):
                insetnow = str(insetnow.get()).strip().lower() == "true"
            else:
                insetnow = bool(insetnow)

            # Toggle state
            new_inset_state = not insetnow
            self.post_entries[p_tag]["is_inset"] = new_inset_state

            post_data = self.post_entries[self.active_tag]              
            print(f"Post Data {post_data}")
            print(f"Is Inset now: {post_data.get('is_inset')}")

            # Safely evaluate is_dummy for label formatting
            is_dummy_val = str(post_data.get("is_dummy").get()).strip().lower() == "true" if hasattr(post_data.get("is_dummy"), 'get') else bool(post_data.get("is_dummy"))

            # Determine canvas text label format
            if is_dummy_val:
                label_text = f"{p_tag} (D)"
            else:
                label_text = f"{p_tag} (i)" if new_inset_state else f"{p_tag}"

            # Update post label text on canvas
            text_items = [
                item for item in self.post_canvas.find_withtag(p_tag) 
                if self.post_canvas.type(item) == "text"
            ]
            
            # Find post polygon center for overlay position
            coords = post_data.get('canvas_coords', [])
            if coords and len(coords) >= 8:
                post_center_x = sum(coords[0::2]) / (len(coords) / 2)
                post_center_y = sum(coords[1::2]) / (len(coords) / 2)
            else:
                post_center_x, post_center_y = 0, 0

            # Update main label text (skipping any existing 'I' center text)
            for item in text_items:
                item_tags = self.post_canvas.gettags(item)
                if "inset_indicator" not in item_tags:
                    self.post_canvas.itemconfig(item, text=label_text)

            # Handle center "I" overlay tag
            indicator_items = self.post_canvas.find_withtag(f"{p_tag}_inset_indicator")
            if new_inset_state:
                if not indicator_items:
                    self.post_canvas.create_text(
                        post_center_x, 
                        post_center_y, 
                        text="I", 
                        font=("Courier", 6, "bold"), 
                        tags=(p_tag, "movable_post", f"{p_tag}_inset_indicator")
                    )
            else:
                for item in indicator_items:
                    self.post_canvas.delete(item)

            # Extract numeric post ID for post_table_data alignment
            try:
                tag_id = int(p_tag.replace("P", ""))
            except ValueError:
                tag_id = None

            # Update post_table_data tuple (index 7 contains insetflag)
            if tag_id is not None:
                for i, row in enumerate(self.post_table_data):
                    if row[0] == tag_id:
                        # row format: (post_count, is_dummy, tag, post_elev, bot_step, bot_ramp, grade, insetflag)
                        temp_list = list(row)
                        temp_list[7] = new_inset_state
                        self.post_table_data[i] = tuple(temp_list)
                        print(f"Post table update for {p_tag} (ID: {tag_id}) inset state: {new_inset_state}")
                        break

            # Refresh UI elements and calculations
            self.update_post_table(self.post_table_data)
            self.update_post_optimization()
            self.refresh_materials_matrix()


        # Function to generate the 4 vertices of a post rotated at a given angle (theta)
    def get_rotated_post_coords(px, py, p_size, theta):
        # Cosine and sine offsets for rotation mapping
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        
        # Define local offsets for standard post box orientation
        # (Assuming px, py is the structural corner origin point)
        local_corners = [
            (0, 0),
            (p_size, 0),
            (p_size, p_size),
            (0, p_size)
        ]
        
        # Rotate each point using standard 2D rotation matrix math
        rotated_coords = []
        for lx, ly in local_corners:
            rx = px + (lx * cos_t - ly * sin_t)
            ry = py + (lx * sin_t + ly * cos_t)
            rotated_coords.extend([rx, ry])
        return rotated_coords

    def spawn_rail(self):
        dimensions = self.ask_brace_rail_dimensions("Rail")
        if dimensions["display_length"] is None:
            return
            
        rail_len = dimensions["display_length"]
        railtype = dimensions["orient_type"]

        r_type = "STEP" if railtype == "angled" else "ExtraRail"
        rail_w = 1.5 * self.scale
        self.rail_count += 1
        r_tag = f"RailNum{self.rail_count}"

        # Draw using initial 4-corner bounding box
        x1, y1 = 50.0, 50.0
        x2, y2 = x1 + ((rail_len - 1) * self.scale), y1 + rail_w
        
        # 8-point polygon coordinate array: [x1, y1, x2, y1, x2, y2, x1, y2]
        poly_coords = [x1, y1, x2, y1, x2, y2, x1, y2]

        # Call segment drawing helper
        self.draw_rail_segment(x1, y1, x2, y2, p_type=r_type, r_num=r_tag, p_name="ExtraRail")

        # Ensure rail entry has ALL necessary rotation keys
        if r_tag not in self.rail_entries:
            self.rail_entries[r_tag] = {}

        self.rail_entries[r_tag].update({
            'name': f"Extra Rail ({rail_len}\")",
            'canvas_coords': poly_coords,
            'points': poly_coords,  # Critical for universal rotation helper
            'label_coords': [(x1 + x2) / 2, (y1 + y2) / 2],
            'ptype': r_type,
            'pname': "ExtraRail",
            'rlen': rail_len,
            'rotation': 0.0
        })

        self.rail_combined_materialColor()
        
        # Ensure tag is active and bound properly
        self.bind_item(r_tag)
        self.active_tag = r_tag


    def paver_add(self):

        dimensions = self.ask_paver_dimensions("Paver")
        
        # If the user hit 'Cancel' or closed the window without data, abort safely
        if dimensions["paver_row"] is None:
            return
        #rint(f"Dimensions = {dimensions}")
        paver_row = dimensions["paver_row"]
        paver_column = dimensions["paver_column"]
        
        paver_w = 12 * self.scale   # pavers are 12x12
        self.paver_count += 1
        self.paver_total = self.paver_total + paver_row * paver_column
        p_tag = f"Paver{self.paver_count}"

        x1 = 250
        y1 = 130
        x2 = x1 + paver_w * paver_column
        y2 = y1 + paver_w * paver_row

        # --- POLYGON CONVERSION ---
        # Define all 4 corners explicitly: Top-Left, Top-Right, Bottom-Right, Bottom-Left
        poly_points = [x1, y1, x2, y1, x2, y2, x1, y2]
        
        plcoord = [x1 + (paver_w * paver_column) / 2, y1 + (paver_w * paver_row) / 2]
        
        if p_tag not in self.sections:
            self.sections[p_tag] = {
                'p_tag': p_tag,
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'points': poly_points,  # Store 8-point polygon coordinate array
                'canvas': self.canvas,
                'p_type': "Paver",
                'name': p_tag,
                'l': paver_w * paver_column,
                'w': paver_w * paver_row,
                'color': "gray"
            }
            
        pavnum = f"PaverCount{paver_column * paver_row}"
        #rint(pavnum)
        
        # Draw main paver outline as polygon instead of rectangle
        self.canvas.create_polygon(
            poly_points,       
            fill="gray", 
            outline="black", 
            tags=(p_tag, "Paver", "shape", pavnum)
        )

        # Add visual dividing lines
        for i in range(1, paver_column):
            paver_offset = (i * 12) * self.scale
            self.canvas.create_line(
                x1 + paver_offset, y1, 
                x1 + paver_offset, y2,
                fill="black", 
                width=1, 
                tags=(p_tag, "paver_line") 
            )
            
        for i in range(1, paver_row):
            paver_offset = (i * 12) * self.scale
            self.canvas.create_line(
                x1, y1 + paver_offset, 
                x2, y1 + paver_offset,
                fill="black", 
                width=1, 
                tags=(p_tag, "paver_line") 
            )
            
        self.canvas.create_text(
            plcoord,   
            text=p_tag, 
            font=("Arial", 10),
            tags=(p_tag, "Paver")
        )

        self.bind_item(p_tag)
        self.active_tag = p_tag

    def ask_paver_dimensions(self,ask_type):
        """
        Creates a custom modal pop-up window to collect paver size
        """
        # Create a blocking modal window
        dialog = tk.Toplevel(self.root)
        #dialog.title(f"Add {ask_type}")
        dialog.title("Add Pavers")
        dialog.geometry("320x240")
        dialog.resizable(False, False)
        
        # Force focus and block interactions with the main window
        dialog.grab_set()
        
        # Dictionary to store our final results
        result = {"paver_row": None, "paver_column": None}
        
        # Define Input Variables
        paver_row = tk.StringVar(value="3")
        paver_column = tk.StringVar(value="3")

        # --- UI LAYOUT ---
        # 1. Display Width Input
        tk.Label(dialog, text="How many rows (vertical on screen) of pavers?", font=("Arial", 10)).pack(pady=(15, 2))
        paver_row_entry = tk.Entry(dialog, textvariable=paver_row, width=15)
        paver_row_entry.pack()
        
        tk.Label(dialog, text="How many columns (horizontal on screen) of pavers?", font=("Arial", 10)).pack(pady=(15, 2))
        paver_column_entry = tk.Entry(dialog, textvariable=paver_column, width=15)
        paver_column_entry.pack()
    
        # Spacer Frame for Buttons
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(side=tk.BOTTOM, pady=15)
        
        # Submit / Cancel Actions
        def on_confirm():
            try:
                paver_rowint = int(paver_row.get())
                # If flat, ignore the material field entry and match the width span
                paver_columnint = int(paver_column.get())                
                if 1 <= paver_rowint <= 110 and 1 <= paver_columnint <= 10:
                    result["paver_row"] = paver_rowint
                    result["paver_column"] = paver_columnint
                    dialog.destroy()
                else:
                    from tkinter import messagebox
                    messagebox.showerror("Error", "Values must be realistic (1-10.)", parent=dialog)
            except ValueError:
                from tkinter import messagebox
                messagebox.showerror("Error", "Please enter valid integers.", parent=dialog)
                
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="OK", command=on_confirm, width=10, bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
        
        # Wait here until the dialog is closed
        self.root.wait_window(dialog)
        print (ask_type)
        return result


    def post_crossbrace(self):
        dimensions = self.ask_brace_rail_dimensions("Brace")
        
        # If the user hit 'Cancel' or closed the window without data, abort safely
        if dimensions["display_length"] is None:
            return
            
        brace_len = dimensions["display_length"]
        material_len = dimensions["material_length"]
        
        brace_w = 1.5 * self.scale
        self.postbrace_count += 1
        b_tag = f"CrossBrace{self.postbrace_count}"

        # Standard rectangle anchor bounding box values
        x1, y1 = 250.0, 130.0
        x2, y2 = x1 + (brace_len * self.scale), y1 + brace_w

        # Convert 4-point rectangle bounding box to 8-point polygon vertices:
        # Top-Left (x1, y1), Top-Right (x2, y1), Bottom-Right (x2, y2), Bottom-Left (x1, y2)
        bcoord = [x1, y1, x2, y1, x2, y2, x1, y2]
        
        # Label placed at center top of brace
        blcoord = [x1 + (brace_len * self.scale / 2.0), y1 - 12.0]

        if b_tag not in self.cross_brace_entries:
            self.cross_brace_entries[b_tag] = {
                'b_tag': b_tag,
                'name': b_tag,
                'brace_length': brace_len,
                'canvas_coords': bcoord,  # Holds 8-point polygon coordinates
                'points': bcoord,         # Shared key used by rotation engine
                'label_coords': blcoord,
                'material_length': material_len,
                'horizontal': 1,
                'rotation': 0.0           # Initialized for rotation tracking
            }

        # Draw as a polygon instead of a rectangle
        self.post_canvas.create_polygon(
            *bcoord, 
            fill="gray", outline="darkgray", width=1, 
            tags=(b_tag, str(material_len), str(brace_len), "post_border", "cross_brace")
        )

        self.post_canvas.create_text(
            *blcoord, 
            text=b_tag, 
            font=("Arial", 10), 
            tags=(b_tag, "cross_brace", "text")
        )

        self.bind_item(b_tag)
        self.active_tag = b_tag
        self.update_delete_button_visibility()
        self.display_crossbracetable(b_tag)



    def ask_brace_rail_dimensions(self,ask_type):
        """
        Creates a custom modal pop-up window to collect both display width
        and actual material cutting length for a cross brace.
        """
        # Create a blocking modal window
        dialog = tk.Toplevel(self.root)
        #dialog.title(f"Add {ask_type}")
        dialog.title("Add Item")
        dialog.geometry("320x240")
        dialog.resizable(False, False)
        
        # Force focus and block interactions with the main window
        dialog.grab_set()
        
        # Dictionary to store our final results
        result = {"display_length": None, "material_length": None, "orient_type":None}
        
        # Define Input Variables
        length_var = tk.StringVar(value="47")
        type_var = tk.StringVar(value="flat")
        material_var = tk.StringVar(value="47")
        
        # --- UI LAYOUT ---
        # 1. Display Width Input
        tk.Label(dialog, text="Horizontal Span (Display Length in.):", font=("Arial", 10)).pack(pady=(15, 2))
        length_entry = tk.Entry(dialog, textvariable=length_var, width=15)
        length_entry.pack()
        
        # 2. Brace Type Selection
        tk.Label(dialog, text="Orientation:", font=("Arial", 10)).pack(pady=(15, 2))
        
        radio_frame = tk.Frame(dialog)
        radio_frame.pack()
        
        # 3. Dynamic Material Length Input Logic
        mat_label = tk.Label(dialog, text="Actual Material Length (in.):", font=("Arial", 10))
        mat_entry = tk.Entry(dialog, textvariable=material_var, width=15)
        
        def toggle_type():
            print (ask_type)
            if type_var.get() == "flat" or ask_type == "Rail":
                # Hide material field and sync values if flat
                mat_label.pack_forget()
                mat_entry.pack_forget()
                material_var.set(length_var.get())
            else:
                # Reveal material field if angled
                mat_label.pack(pady=(10, 2), before=btn_frame)
                mat_entry.pack(before=btn_frame)

        flattext = "Flat" if ask_type == "Brace" else "Deck/Ramp"
        angletext = "Angled" if ask_type == "Brace" else "Stair Angle"        
        tk.Radiobutton(radio_frame, text=flattext, variable=type_var, value="flat", command=toggle_type).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(radio_frame, text=angletext, variable=type_var, value="angled", command=toggle_type).pack(side=tk.LEFT, padx=10)

        # Spacer Frame for Buttons
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(side=tk.BOTTOM, pady=15)
        
        # Submit / Cancel Actions
        def on_confirm():
            try:
                w = int(length_var.get())
                # If flat, ignore the material field entry and match the width span
                m = int(material_var.get()) if type_var.get() == "angled" else w
                
                if 1 <= w <= 120 and 1 <= m <= 150:
                    result["display_length"] = w
                    result["material_length"] = m
                    result["orient_type"] = type_var.get()
                    print (f"Type var {type_var.get()}")
                    dialog.destroy()
                else:
                    from tkinter import messagebox
                    messagebox.showerror("Error", "Values must be realistic lengths (1-120 in.)", parent=dialog)
            except ValueError:
                from tkinter import messagebox
                messagebox.showerror("Error", "Please enter valid integers.", parent=dialog)
                
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="OK", command=on_confirm, width=10, bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
        
        # Wait here until the dialog is closed
        self.root.wait_window(dialog)
        print (ask_type)
        return result



    
    def update_post_table(self, posts_data):
        print ("Update_post_table")
        self.debug_posts
        #print ("End of Debug") 
        # Clear existing rows
        for widget in self.post_grid.winfo_children():
            widget.destroy()

        headers = ["#", "Above Deck", "Above Grade", "Below Grade", "Total Length"]
        for c, h in enumerate(headers):
            tk.Label(self.post_grid, text=h, font=("Arial", 8, "bold"), borderwidth=1, 
                    relief="solid", bg="#eee").grid(row=0, column=c, sticky="nsew")

        self.post_entries = {}

        # Unpack the 4 items: post number, dummy flag, parent tag, and specific post elevation
        #self.post_table_data.append((num_id, is_dummy, tag, float(p_info["grade"])))    #,bot_step,bot_ramp))
        for r_idx, (post_num, is_dummy, parent_tag, post_elev,bot_step,bot_ramp,og_grade,is_inset) in enumerate(posts_data):
            p_key = f"P{post_num}"
            print (f"Post {p_key} is dummy status {is_dummy}")
            display_name = p_key + (" (D)" if is_dummy else "")
            display_name = display_name + (" (i)" if is_inset else "")
            
            #print ("Display Name")
            #print (display_name)
            #print (bot_step)

            def_deck = 40.0
            # Use the post-specific elevation we calculated via distance
            def_grade = 7.0 if is_dummy or bot_step else math.ceil(post_elev) 
            def_og_grade = def_grade
            def_below = 0.0 if is_dummy else 18.0
            if (bot_step or bot_ramp) and not is_dummy:
                def_below = 24.0

            
            # 1. Row Labels and Entries
            tk.Label(self.post_grid, text=display_name, borderwidth=1, relief="solid", bg="white").grid(row=r_idx+1, column=0, sticky="nsew")
            
            v_deck = tk.StringVar(value=str(def_deck))
            v_grade = tk.StringVar(value=f"{def_grade:.1f}")
            v_below = tk.StringVar(value=str(def_below))
            v_total = tk.StringVar()
            v_og_grade = tk.StringVar(value=f"{def_og_grade:.1f}")
            
            for var in [v_deck, v_grade, v_below]:
                var.trace_add("write", lambda *args, p=p_key: self.calculate_total_length(p))
            
            tk.Entry(self.post_grid, textvariable=v_deck, width=8, justify='center').grid(row=r_idx+1, column=1, sticky="nsew")
            tk.Entry(self.post_grid, textvariable=v_grade, width=8, justify='center').grid(row=r_idx+1, column=2, sticky="nsew")
            tk.Entry(self.post_grid, textvariable=v_below, width=8, justify='center').grid(row=r_idx+1, column=3, sticky="nsew")
            
            tk.Label(self.post_grid, textvariable=v_total, borderwidth=1, relief="solid", bg="#f0f0f0").grid(row=r_idx+1, column=4, sticky="nsew")
            
            self.post_entries[p_key] = {"deck": v_deck, "grade": v_grade, "below": v_below, "total": v_total, "is_dummy":is_dummy, "bot_step": bot_step, "bot_ramp":bot_ramp,"og_grade":v_og_grade,"is_inset":is_inset}
            self.calculate_total_length(p_key)

        for i in range(5):
            self.post_grid.grid_columnconfigure(i, weight=1)

        self.post_opt_inner = tk.Frame(self.post_grid, bg="white")
        self.post_opt_inner.grid(row=999, column=0, columnspan=5, pady=20, sticky="ew")

        self.update_post_optimization()
        

    def calculate_total_length(self, post_key):
        """Sums the three editable inputs"""
        data = self.post_entries.get(post_key)
        #print (data["below"].get())
        #print ("Calc Length")

        if not data: return
        try:
            total = float(data["deck"].get() or 0) + float(data["grade"].get() or 0) + float(data["below"].get() or 0)
            data["total"].set(f"{total}\"")
            #print (total)
            
            self.update_post_optimization()
            #print (data["below"].get())
        except ValueError:
            data["total"].set("ERR")

    def _get_probe_points(self, i, cx, cy):
        """Helper to maintain your probe logic"""
        if i == 0: return (cx - 3, cy + 3), (cx + 3, cy - 3)
        if i == 1: return (cx + 3, cy + 3), (cx - 3, cy - 3)
        if i == 2: return (cx - 3, cy - 3), (cx + 3, cy + 3)
        return (cx + 3, cy - 3), (cx - 3, cy + 3)


    def update_delete_button_visibility(self):
        if self.active_tag:
            # Show the button if something is selected
            if self.active_tag.startswith("P"):
                self.togglePostBlock_btn.pack(side=tk.RIGHT, padx=10)
                self.toggleDummyPost_btn.pack(side=tk.RIGHT, padx=10)
                self.toggleInsetPost_btn.pack(side=tk.RIGHT, padx=10)
            self.delete_btn.pack(side=tk.RIGHT, padx=20)

        else:
            # Hide the button if nothing is selected
            self.togglePostBlock_btn.pack_forget()
            self.toggleDummyPost_btn.pack_forget()
            self.toggleInsetPost_btn.pack_forget()
            self.delete_btn.pack_forget()
            
    def on_post_drag_start(self, event):
        canvas_x = self.post_canvas.canvasx(event.x)
        canvas_y = self.post_canvas.canvasy(event.y)
        item_ids = self.post_canvas.find_closest(canvas_x, canvas_y)
        #print ("Post drag start")
        #print (item_ids)
        if not item_ids: return
        
        # Get all tags for the specific item clicked
        tags = self.post_canvas.gettags(item_ids[0])
        #print (tags)
        if not tags: return
        
        # The unique ID tag is always the first one in our setup (obj_... or REF_POINT)
        self.active_tag = tags[0]
        self.update_delete_button_visibility()

        # 1. Reset all borders to black
        self.post_canvas.itemconfig("post_border", outline="black", width=2)
        
        # 2. Highlight only the border of the ACTIVE post
        # This targets the item that has BOTH the ID (e.g., P2) AND the border tag
        self.post_canvas.itemconfig(f"{self.active_tag}&&post_border", outline="#007bff", width=4)

        # Identify the unique post tag (e.g., 'post_P5')
        post_tag = next((t for t in tags if t.startswith("P")), None)    #ptagchange
        if post_tag:
            self._post_drag_data["item"] = post_tag
            self._post_drag_data["x"] = canvas_x
            self._post_drag_data["y"] = canvas_y
            #print (post_tag)
        else:
            brace_tag = next((t for t in tags if t.startswith("CrossBrace")), None)    #ptagchange
            #print ("Brace tag")
            #print (brace_tag)
            if brace_tag:
                self._post_drag_data["item"] = brace_tag
                self._post_drag_data["x"] = canvas_x
                self._post_drag_data["y"] = canvas_y
                #print (brace_tag)

    def on_post_drag(self, event):
        canvas_x = self.post_canvas.canvasx(event.x)
        canvas_y = self.post_canvas.canvasy(event.y)
        item = self._post_drag_data["item"]
        
        #print ("Item")
        #print (item)
        if not item: return
        
        dx = canvas_x - self._post_drag_data["x"]
        dy = canvas_y - self._post_drag_data["y"]
        
        # Move the physical object and its label
        print (f"item = {item}")
        self.post_canvas.move(item, dx, dy)
        self.post_canvas.move(f"label_{item}", dx, dy) # If labels are linked by ID
        
        self.post_canvas.move(f"block_{item}", dx, dy) 

        self._post_drag_data["x"] = canvas_x
        self._post_drag_data["y"] = canvas_y


    def on_post_stop_drag(self, event):
        canvas_x = self.post_canvas.canvasx(event.x)
        canvas_y = self.post_canvas.canvasy(event.y)
        #print ("start of stop drag")
        item = self._post_drag_data["item"]
        #print (item)
        if not item: return

        c = self.post_canvas.coords(item)
        curr_corners = [(c[0],c[1]), (c[2],c[1]), (c[0],c[3]), (c[2],c[3])]
        print (curr_corners)
        
        #break for post vs brace
        if "Brace" in item:
            brace_data = self.cross_brace_entries[item]
            brace_length = brace_data['brace_length']
            brace_curc = brace_data['canvas_coords']
            print (brace_data)
            xoff = c[0]-brace_curc[0]
            yoff = c[1]-brace_curc[1]
            lblx = brace_data['label_coords'][0] +xoff
            lbly = brace_data['label_coords'][1] +yoff
            is_horiz = brace_data['horizontal']
            #newbracex = canvas_x + (brace_length * self.scale) if is_horiz == 1 else canvas_x + 3
            #newbracey = canvas_y + 3 if is_horiz == 1 else canvas_y + (brace_length * self.scale)
            self.cross_brace_entries[item]['canvas_coords'] = c
            self.cross_brace_entries[item]['label_coords'] = [lblx,lbly]
            print ("End Brace Drag")
            print (self.cross_brace_entries[item])
        else:
            self.post_entries[item]['canvas_coords'] = [canvas_x,canvas_y,canvas_x+self.p_size,canvas_y+self.p_size]
            #print (self.post_entries[item]['canvas_coords'])
            #self.post_canvas.itemconfig("post_border", outline="black", width=2)
        self.post_canvas.focus_set()     #required for delete context
        
        self.post_canvas.configure(scrollregion=self.post_canvas.bbox("all"))

    def deselect_all_main(self):
        self.canvas.itemconfig("shape",outline = "black", width=1)
        # 1. Clear Post Selections & Reset Outlines
        self.active_tag = None
        self.post_canvas.itemconfig("post_border", outline="black", width=2)
        self.post_canvas.itemconfig("cross_brace", outline="black", width=1)
        if hasattr(self, 'update_delete_button_visibility'):
            self.update_delete_button_visibility()

        # 2. Clear Handrail Selections & Reset Outlines
        self.active_rail_tag = None
        self.rail_canvas.itemconfig("draggable_rail", outline="black", width=1)
        if hasattr(self, 'update_delete_button_rail_visibility'):
            self.update_delete_button_rail_visibility()

    

    def deselect_all_post(self, event):
        # Check if we clicked the background (not an item)
        #print (self.active_tag)
        if not self.post_canvas.find_withtag("current"):
            self.active_tag = None
            self.update_delete_button_visibility()
            self.post_canvas.itemconfig("post_border", outline="black", width=2)
            # Add this line to target cross brace tags and set width to 1
            self.post_canvas.itemconfig("cross_brace", outline="black", width=1)


    def deselect_all_rail(self, event):
        # Check if we clicked the background (not an item)
        #print (self.active_rail_tag)
        
        if not self.rail_canvas.find_withtag("current"):
            self.active_rail_tag = None
            self.rail_canvas.itemconfig("draggable_rail", outline="black", width=1)
        
            self.update_delete_button_rail_visibility()
            #self.rail_canvas.itemconfig("post_border", outline="black", width=2)
            #rint("Selection cleared.")


    def post_block_toggle(self):
        if self.active_tag:
            print("Post Block Toggle")
            print(self.active_tag)
            tags = self.post_canvas.gettags(self.active_tag)
            print(tags)
            
            print(self.post_entries[self.active_tag])

            block_pnum = f"block_{self.active_tag}"
            print(f"Block pnum = {block_pnum}")
            # Check if the block polygon already exists on the canvas
            existing_block = self.post_canvas.find_withtag(block_pnum)
            
            if existing_block:
                # --- TOGGLE OFF: Remove the block ---
                print(f"Removing post block for {self.active_tag}")
                
                self.post_canvas.delete(block_pnum)
                if hasattr(self, 'post_block_count'):
                    self.post_block_count = max(0, self.post_block_count - 1)
                
                if self.active_tag in self.post_entries:
                    post_data = self.post_entries[self.active_tag]              
                    print(f"Post Data {post_data}")
                    print(post_data.get("is_dummy"))
                    is_dummy_val = str(post_data.get("is_dummy").get()).strip().lower() == "true" if hasattr(post_data.get("is_dummy"), 'get') else bool(post_data.get("is_dummy"))
                    bot_step_val = str(post_data.get("bot_step").get()).strip().lower() == "true" if hasattr(post_data.get("bot_step"), 'get') else bool(post_data.get("bot_step"))
                    bot_ramp_val = str(post_data.get("bot_ramp").get()).strip().lower() == "true" if hasattr(post_data.get("bot_ramp"), 'get') else bool(post_data.get("bot_ramp"))
                    
                    print(f"Evaluated Flags -> is_dummy: {is_dummy_val}, bot_step: {bot_step_val}, bot_ramp: {bot_ramp_val}")
                    # Determine the correct original below grade value based on step/ramp flags
                    if (bot_step_val or bot_ramp_val) and not is_dummy_val:
                        original_below = 24.0
                    else:
                        original_below = 0.0 if is_dummy_val else 18.0
                        
                    post_data["below"].set(str(original_below))
                    
                    # Restore the 6 inches to Above Grade
                    try:
                        current_grade = float(post_data["grade"].get())
                    except ValueError:
                        current_grade = 0.0
                    
                    post_data["grade"].set(f"{current_grade + 6.0:.1f}")
                    
            else:
                # --- TOGGLE ON: Add the block ---
                coords = self.post_canvas.coords(self.active_tag)
                if coords:
                    buf = 4.0
                    
                    if len(coords) >= 8:
                        # Polygon coordinates: [x1, y1, x2, y2, x3, y3, x4, y4]
                        xs = coords[0::2]
                        ys = coords[1::2]
                        center_x = sum(xs) / len(xs)
                        center_y = sum(ys) / len(ys)

                        # Expand vertices outward from polygon centroid by buffer distance
                        block_coords = []
                        for x, y in zip(xs, ys):
                            vx = x - center_x
                            vy = y - center_y
                            dist = math.hypot(vx, vy)
                            if dist > 0:
                                new_x = center_x + vx * (1.0 + buf / dist)
                                new_y = center_y + vy * (1.0 + buf / dist)
                            else:
                                new_x, new_y = x, y
                            block_coords.extend([new_x, new_y])

                        self.post_canvas.create_polygon(
                            *block_coords, 
                            fill="", outline="gray", width=buf, 
                            tags=(block_pnum, tags, "post_block", "block_border")
                        )
                    else:
                        # Fallback for standard 4-point bounding rectangles [x1, y1, x2, y2]
                        x1, y1, x2, y2 = coords
                        self.post_canvas.create_rectangle(
                            x1 - buf, y1 - buf, x2 + buf, y2 + buf, 
                            fill="", outline="gray", width=buf, 
                            tags=(block_pnum, tags, "post_block", "block_border")
                        )

                    self.bind_item(block_pnum)

                if hasattr(self, 'post_block_count'):
                    self.post_block_count += 1
                else:
                    self.post_block_count = 1

                # Update Post Specification Table Values
                if self.active_tag in self.post_entries:
                    post_data = self.post_entries[self.active_tag]
                    
                    # Update Below Grade to 0.0
                    post_data["below"].set("0.0")
                    
                    # Subtract 6 inches from Above Grade
                    try:
                        current_grade = float(post_data["grade"].get())
                    except ValueError:
                        current_grade = 0.0
                    
                    new_grade = max(0.0, current_grade - 6.0)
                    post_data["grade"].set(f"{new_grade:.1f}")
                    if new_grade < 7.0:
                        messagebox.showwarning(
                            "Clearance Warning!", 
                            f"Warning: The remaining above-grade clearance for {self.active_tag} will be {new_grade:.1f}\".\n\n"
                            "There may not be enough vertical room to fit the post block properly beneath the joist!"
                        )
            
            # Re-run post optimization regardless of whether we turned it ON or OFF
            self.update_post_optimization()
            self.refresh_materials_matrix()
        

    def delete_selected_post(self):
        if self.active_tag:
            block_pnum = f"block_{self.active_tag}"
            
            # Look up if this item has an active post block on the post_canvas
            existing_block = self.post_canvas.find_withtag(block_pnum)
            if existing_block:
                print(f"Post block found for {self.active_tag}. Deleting...")
                self.post_canvas.delete(block_pnum)
                
                # Decrement our materials tracking sheet count safely
                if hasattr(self, 'post_block_count'):
                    self.post_block_count = max(0, self.post_block_count - 1)

            # 1. Visual Removal
            self.post_canvas.delete(self.active_tag)
            
            if "Brace" in self.active_tag:
                # --- BRACE DELETION LOGIC ---
                try:
                    print(f"Deleting Brace: {self.active_tag}")
                    
                    # Remove from your cross brace data dictionary
                    if self.active_tag in self.cross_brace_entries:
                        del self.cross_brace_entries[self.active_tag]
                    
                    # Refresh your cross brace table GUI view
                    self.display_crossbracetable(self.active_tag)
                    
                except Exception as e:
                    print(f"Error deleting brace: {e}")
                    
            else:
                # --- POST DELETION LOGIC ---
                try:
                    print(f"Deleting Post: {self.active_tag}")
                    selected_id = int(self.active_tag.replace("P", ""))
                    print(selected_id)
                    
                    # Filter out the deleted post from your layout data list
                    print(self.post_table_data)
                    self.post_table_data = [row for row in self.post_table_data if row[0] != selected_id]
                    
                    # Note: If you have a separate dictionary or method tracking post specs 
                    # (like self.post_entries), you would remove it here too.
                    
                    # Refresh your post specs table view here if needed
                    # self.display_post_table() 
                    
                except ValueError:
                    print(f"Active tag '{self.active_tag}' is not a standard post ID format.")
        
            # 3. Clear the selection reference so nothing stays stuck as "active"
            self.active_tag = None
                
            self.update_delete_button_visibility()

            # 5. Refresh
            self.update_post_table(self.post_table_data)
            self.update_post_optimization()
                
    
    def print_debug_info(self):
        print("\n" + "="*30)
        print("DEBUG: POST ENTRIES CONTENT")
        print("="*30)
        
        if not self.post_entries:
            print("No posts found in self.post_entries.")
        
        for p_tag, data in self.post_entries.items():
            # Get the values from the StringVars\

            print (data)
            deck = data['deck'].get()
            grade = data['grade'].get()
            total = data['total'].get()
            coords = data.get('canvas_coords', "No Coords")
            
            is_inset = data['is_inset'].get()
            is_dummy = data['is_dummy']
            #coords = data['canvas_coords'].get()
            
            print(f"ID: {p_tag}")
            print(f"  - Heights: Deck: {deck}, Grade: {grade}, Total: {total}, Inset: {is_inset}, Dummy: {is_dummy}")
            print(f"  - Canvas Position: {coords}")
            print("-" * 20)
            

    def debug_posts(self):
        print("\n--- CURRENT POST ENTRIES DATA ---")
        if not self.post_entries:
            print("Dictionary is empty.")
            return

        for p_tag, p_data in self.post_entries.items():
            #rint(f"Post ID: {p_tag}")
            # Extract values from StringVars
            deck = p_data.get('deck').get() if hasattr(p_data.get('deck'), 'get') else "N/A"
            grade = p_data.get('grade').get() if hasattr(p_data.get('grade'), 'get') else "N/A"
            total = p_data.get('total').get() if hasattr(p_data.get('total'), 'get') else "N/A"
            
            # Get coordinates
            c_coords = p_data.get('canvas_coords', [0,0,0,0])
            l_coords = p_data.get('label_coords', [0,0])
            
            #rint(f"  > Heights: Deck: {deck}, Grade: {grade}, Total: {total}")
            #rint(f"  > Canvas Box: {c_coords}")
            #rint(f"  > Label Pos:  {l_coords}")
        print("---------------------------------\n")


    def update_post_tab(self):
        self.post_canvas.delete("all")
        for tag, data in self.sections.items():
            sid_list = self.canvas.find_withtag(f"{tag} && shape")
            if not sid_list: continue
            sid = sid_list[0]
            
            # FIXED: Check if 'points' exists in the dictionary.
            # This handles RAMP, TAPER RAMP, THRESH RAMP, STEP, and POLYGON cleanly.
            if "points" in data:
                # Extracts its geometric layout canvas coordinates directly
                self.post_canvas.create_polygon(data['points'], fill=data['color'], outline="black")
            else:
                # Fallback to standard rectangular shapes if any legacy keys remain
                c = [data['x1'], data['y1'], data['x2'], data['y2']]
                self.post_canvas.create_rectangle(*c, fill=data['color'], outline="black")
            
            #self.post_canvas.create_rectangle(*c, fill=data['color'], outline="black")
            #for p in [(c[0],c[1]), (c[2],c[1]), (c[0],c[3]), (c[2],c[3])]:
            #    self.post_canvas.create_rectangle(p[0]-4, p[1]-4, p[0]+4, p[1]+4, fill="black")

    def update_post_optimization(self):
        #print ("Update post optimization")
        """Calculates pairings for minimum waste and prepares them for sorted display."""
        if not hasattr(self, 'post_entries') or not self.post_entries: return
        
        posts = []
        for p_id, data in self.post_entries.items():
            try:
                val = data['total'].get().replace('"', '')
                length = float(val)
                if length > 0:
                    # Keep ID as integer for sorting, but store original string
                    posts.append({'id_str': p_id, 'id_num': int(p_id.replace('P', '').replace('post_','')), 'len': length})
            except: continue

        # Algorithm still handles longest posts first to minimize waste
        posts.sort(key=lambda x: x['len'], reverse=True)
        
        stock_options = [96, 120, 144]
        buffer = 2.0
        temp_pairings = []
        totals = {96: 0, 120: 0, 144: 0}

        while posts:
            p1 = posts.pop(0)
            best_stock = None
            best_p2_idx = None
            min_waste = float('inf')

            for s in stock_options:
                if p1['len'] <= s:
                    current_waste = s - p1['len']
                    candidate_p2_idx = None
                    rem = s - p1['len'] - buffer
                    for i, candidate in enumerate(posts):
                        if candidate['len'] <= rem:
                            current_waste = rem - candidate['len']
                            candidate_p2_idx = i
                            break
                    if current_waste < min_waste:
                        min_waste = current_waste
                        best_stock = s
                        best_p2_idx = candidate_p2_idx

            p2 = posts.pop(best_p2_idx) if best_p2_idx is not None else None
            
            # --- NUMERICAL SORT WITHIN THE PAIR ---
            pair_list = [p1]
            if p2: pair_list.append(p2)
            # Sort the 1 or 2 posts in this specific board by their ID number
            pair_list.sort(key=lambda x: x['id_num'])
            
            # Create a display string and a sort key for the row
            display_ids = " & ".join([p['id_str'] for p in pair_list])
            sort_key = pair_list[0]['id_num'] # Sort rows by the first post in the pair

            total_used = sum(p['len'] for p in pair_list)
            # This is the literal raw remainder left on the board
            rem_inches = best_stock - total_used
            lengths_display = " & ".join([f"{self.format_inchesquarter(p['len'])}" for p in pair_list])

            temp_pairings.append({
                'ids': display_ids,
                'stock': best_stock,
                'sort_val': sort_key,
                'remainder':rem_inches,
                'displaylen':lengths_display
            })
            if best_stock: totals[best_stock] += 1

        # --- SORT THE ROWS NUMERICALLY (P1, P2, etc.) ---
        temp_pairings.sort(key=lambda x: x['sort_val'])
        
        self.display_optimization_tables(temp_pairings, totals)


    def display_optimization_tables(self, pairings, totals):
        #print ("Display optimization tables")
        # SAVE CACHE FOR HTML EXPORTS
        self.last_optimized_pairings = pairings
        self.last_optimized_totals = totals
        
        # Clear existing tables so they don't duplicate on updates
        if not hasattr(self, 'post_opt_inner') or not self.post_opt_inner.winfo_exists():
            return
        for child in self.post_opt_inner.winfo_children():
            child.destroy()

        # Table A: Pairings
        tk.Label(self.post_opt_inner, text="Post Pairings (Optimized)", font=("Arial", 12, "bold")).pack(pady=10)
        t1 = tk.Frame(self.post_opt_inner)
        t1.pack()
        
        tk.Label(t1, text="Post ID(s)", width=14, relief="solid").grid(row=0, column=0)
        tk.Label(t1, text="Stock Required", width=16, relief="solid").grid(row=0, column=1)
        tk.Label(t1, text="Buffer", width = 8, relief="solid").grid(row=0, column=2)
        tk.Label(t1, text="Lengths", width = 18, relief="solid").grid(row=0, column=3)
        
        for i, p in enumerate(pairings):
            tk.Label(t1, text=p['ids'], width=14, relief="groove").grid(row=i+1, column=0)
            tk.Label(t1, text=f"{p['stock']//12}'", width=16, relief="groove").grid(row=i+1, column=1)
            tk.Label(t1, text=f"{int(p['remainder'])}\"", width=8, relief="groove").grid(row=i+1, column=2)
            tk.Label(t1, text=p['displaylen'], width=18, relief="groove").grid(row=i+1, column=3)



        # Table B: Totals
        tk.Label(self.post_opt_inner, text="4x4 Purchase List", font=("Arial", 12, "bold")).pack(pady=10)
        t2 = tk.Frame(self.post_opt_inner)
        t2.pack()
        for child in t2.winfo_children(): #clear if data
                child.destroy()
        
        tk.Label(t2, text="4x4 Length", width=20, relief="solid").grid(row=0, column=0)
        tk.Label(t2, text="Quantity", width=20, relief="solid").grid(row=0, column=1)
        
        for i, length in enumerate([96, 120, 144]):
            tk.Label(t2, text=f"{length//12} Foot", width=20, relief="groove").grid(row=i+1, column=0)
            tk.Label(t2, text=str(totals[length]), width=20, relief="groove").grid(row=i+1, column=1)
        
        # Table C: Cross Brace Totals
        if self.postbrace_count > 0:
            self.display_crossbracetable(self.active_tag)
    
    def display_crossbracetable(self, b_tag):
        #rint("Display crossbrace")
        
        # 1. Fallback if active_tag was cleared during a deletion cascade
        if not b_tag or b_tag not in self.cross_brace_entries:
            if self.cross_brace_entries:
                b_tag = list(self.cross_brace_entries.keys())[0]
            else:
                # No braces remaining: safely clear the frame if it exists and exit
                if hasattr(self, 't3_frame') and self.t3_frame and self.t3_frame.winfo_exists():
                    for child in self.t3_frame.winfo_children():
                        child.destroy()
                return

        # 2. Check if the frame has been dropped from the UI canvas.
        # If it doesn't exist in the current layout context, reset the reference.
        if hasattr(self, 't3_frame') and self.t3_frame and not self.t3_frame.winfo_exists():
            self.t3_frame = None

        # 3. Create BOTH the Section Title and the master frame if they are missing
        if not hasattr(self, 't3_frame') or self.t3_frame is None:
            # Re-anchors the header title directly above the table frame on redraw
            title_lbl = tk.Label(self.post_opt_inner, text="Cross Brace List", font=("Arial", 12, "bold"))
            title_lbl.pack(pady=(20, 10)) # Generates breathing room below the 4x4 grid
            
            self.t3_frame = tk.Frame(self.post_opt_inner)
            self.t3_frame.pack()

        # 4. Wipe out everything currently inside the frame before drawing the updated data
        for child in self.t3_frame.winfo_children():
            child.destroy()

        # 5. Draw the clean header row at the top of the frame
        tk.Label(self.t3_frame, text="Brace", width=20, relief="solid").grid(row=0, column=0)
        tk.Label(self.t3_frame, text="Length", width=20, relief="solid").grid(row=0, column=1)
        
        #rint("CBE")
        #rint(self.cross_brace_entries)
        
        # 4. Loop through the entire dictionary and build the rows sequentially
        # enumerate(..., start=1) ensures rows go cleanly into grid row 1, 2, 3, etc.
        for row_idx, (b_tag, data) in enumerate(self.cross_brace_entries.items(), start=1):
            #rint(b_tag)
            #rint(data)
            #rint("Brace Length")
            bracelen = data['material_length']
            
            tk.Label(self.t3_frame, text=b_tag, width=20, relief="groove").grid(row=row_idx, column=0)
            tk.Label(self.t3_frame, text=bracelen, width=20, relief="groove").grid(row=row_idx, column=1)

    def pick_board_length(self,lg):
        pstocklen = 0
        pstockct = 0
        if lg <= 32:
            pstocklen = 8
        elif lg <=40:
            pstocklen = 10
        elif lg <= 48:
            pstocklen = 8
        elif lg <= 60:
            pstocklen = 10
        elif lg<=72:
            pstocklen = 12
        elif lg<= 96:
            pstocklen = 8
        elif lg<=120:
            pstocklen = 10
#            return 10, math.ceil(bdcount/2)
        else:
            pstocklen = 12
        
        if lg<=pstocklen*12/4:
            pieceperboard = 4
        elif lg<= pstocklen*12/3:
            pieceperboard = 3
        elif lg<= pstocklen*12/2:
            pieceperboard = 2
        else:
            pieceperboard = 1
        
        return pstocklen,pieceperboard

    def format_stock(self,val):
        whole = int(val)
        remainder = val - whole
        
        # Map decimals to fractions for 2 and 3 denominators
        # Using 0.05 tolerance to account for floating point math
        #if abs(remainder - 0.5) < 0.05:
        #    fraction = "-1/2"
        #elif abs(remainder - 0.25) < 0.05:
        #    fraction = "-1/4"
        #elif abs(remainder - 0.33) < 0.05:
        #    fraction = "-1/3"
        #elif abs(remainder - 0.66) < 0.05:
        #    fraction = "-2/3"
        #elif abs(remainder - 0.75) < 0.05:
        #    fraction = "-3/4"
        #else:
        #    fraction = "" # No fraction for whole numbers or unsupported decimals
        if remainder < 0.05:
            fraction = ""
        elif remainder <= 0.25:
            fraction = "-1/4"
        elif remainder <= 0.34:
            fraction = "-1/3"
        elif remainder <= 0.5:
            fraction = "-1/2"
        elif remainder <= 0.67:
            fraction = "-2/3"
        elif remainder <= 0.75:
            fraction = "-3/4"
        else:
            fraction = ""
            whole = whole + 1

        return f"{whole}{fraction}"
    
    def draw_component_detail(self, data):
        import math
        # 1. First find the tag right away so we have access to it throughout the method
        tag = next((k for k, v in self.sections.items() if v == data), None)
        print (f"Draw component {tag}")
        print (data)

        # 1. Catch custom non-framed shapes (POLYGON, Paver, etc.) and stop them from executing standard canvas logic
        p_type = data.get("p_type", "").upper()
        if p_type in ["PAVER", "REF_POINT"] or 'canvas' not in data or 'table' not in data:
            # Dynamically find sidebar detail canvas to render a safe preview if available
            detail_canvas = None
            for attr in ['detail_canvas', 'canvas_detail', 'preview_canvas', 'side_canvas']:
                if hasattr(self, attr) and getattr(self, attr) is not None:
                    detail_canvas = getattr(self, attr)
                    break
            
            # If we find a detail canvas and have point geometry, render preview
            if detail_canvas and 'points' in data:
                detail_canvas.delete("all")
                try:
                    # Shifts coordinates closer to (0,0) so the preview isn't cut off
                    min_x = min(data['points'][0::2])
                    min_y = min(data['points'][1::2])
                    preview_points = [
                        p - min_x + 20 if i % 2 == 0 else p - min_y + 20 
                        for i, p in enumerate(data['points'])
                    ]
                    detail_canvas.create_polygon(preview_points, fill=data.get('color', 'gray'), outline="black", width=2)
                except Exception as e:
                    print(f"DEBUG: Could not render detail preview: {e}")
            
            # CRITICAL: Always return here so non-deck/ramp components NEVER attempt to load data['canvas'] or data['table']
            return

        canvas = data['canvas']
        print (f"Canvas {canvas}")
        tbl_frame = data['table']
        canvas.delete("all")
        
        if tag:
            self.sections[tag]['lumber_counts'] = {}

        for widget in tbl_frame.winfo_children(): widget.destroy()
        #canvas.configure(scrollregion=(0, 0, 1250, 650))

        l, w = data['l'], data['w']
        is_ramp = "RAMP" in data['name'].upper()
        is_taper_ramp = "TAPER RAMP" in data['name'].upper()
        is_threshold_ramp = "THRESH RAMP" in data['name'].upper()
        is_step = "STEP" in data['name'].upper()
        is_poly = "POLY" in data['name'].upper()
        print (f"Polygon check {is_poly}")
        v_scale, cx, cy, stock_t = 3.5, 300, 40, 1.5

        h = data.get('h', 0.0)      # Defaults to 0.0 if normal ramp
        sl = data.get('sl', 0.0)    # Defaults to 0.0 if normal ramp
        thresh = data.get('thresh', '0')
        
        print (f"Is ramp {is_ramp}")
        print (f"Is taper ramp {is_taper_ramp} with slope {sl}")
        print (f"Is threshold ramp {is_threshold_ramp} with height {h}")


        # --- IF STEP COMPONENT: RENDER DYNAMIC MULTI-DIAGRAM VIEWS ---
        if is_step:
            steps = max(1, int((l - 1) // 10) + 1)
            outerwidth = data['w']
            innerwidth = outerwidth - stock_t*2
            
            # --- 1. AERIAL OVERHEAD VIEW (Top Middle) ---
            canvas.create_text(50, 30, text=f"Aerial Layout View ({steps} Steps) Width = {self.format_inchesquarter(outerwidth)}", font=("Arial", 12, "bold"), anchor="w")
            canvas.create_rectangle(80, 60, 550, 80, fill="#f8f9fa", outline="black", width=3)
            canvas.create_text(300, 70, text="Deck Joist over 2x8", font=("Arial", 10, "bold"))
            canvas.create_rectangle(99, 81, 139, 125, fill="#f8f9fa", outline="black", width=3)
            canvas.create_text(117, 100, text="Post", font=("Arial", 10, "bold"))
            canvas.create_rectangle(480, 81, 520, 125, fill="#f8f9fa", outline="black", width=3)
            canvas.create_text(498, 100, text="Post", font=("Arial", 10, "bold"))
            canvas.create_rectangle(160, 81, 460, 100, fill="#cd853f", outline="black",width=3)
            canvas.create_text(300, 91, text=f"2x6x{self.format_inchesquarter(innerwidth)}", fill="black", font=("Arial", 10))
            
            stringer_x_positions = [140, 240, 360, 460]
            for idx, sx in enumerate(stringer_x_positions):
                y1=100
                if idx == 0 or idx == 3:
                    y1=81
                canvas.create_rectangle(sx, y1, sx + 20, 200, fill="#cd853f", outline="black", width = 2)
            
            widthsplit = round(((innerwidth - stock_t * 2) / 3) * 2) / 2
            canvas.create_text(200, 120, text=f"{self.format_inchesquarter(widthsplit)}", font=("Arial", 12, "bold"))
            canvas.create_text(310, 120, text=f"{self.format_inchesquarter(innerwidth - stock_t*2 - widthsplit*2)}", font=("Arial", 12, "bold"))
            canvas.create_text(420, 120, text=f"{self.format_inchesquarter(widthsplit)}", font=("Arial", 12,"bold"))

            canvas.create_text(190, 240, text="Cut 1-1/2\" from back of inside stringers",font=("Arial",10), anchor="center")
            canvas.create_line(310, 225, 265, 105, arrow=tk.LAST, fill="black",width=2)
            canvas.create_line(310, 225, 355, 105, arrow=tk.LAST, fill="black",width=2)
            canvas.create_text(190, 280, text="2 Outside Stringers & 2 Inside Stringers", font=("Arial", 10, "italic"), anchor="center")
            
            # --- 2. BRACING BOARD PLACEMENT PROFILE (Top Right) ---
            canvas.create_text(600, 30, text="Bracing Board Placement", font=("Arial", 12, "bold"), anchor="center")
            bx, by = 600, 300
            b_points = [bx + 50, by]
            b_points.extend([bx, by])
            bcx, bcy = bx, by
            for _ in range(steps):
                bcy -= 35
                b_points.extend([bcx, bcy])
                bcx += 45
                b_points.extend([bcx, bcy])
            b_points.extend([bcx, bcy+35])
            b_points.extend([bx+50, by])
            canvas.create_polygon(b_points, fill="#cd853f", outline="black",width=2)
            canvas.create_rectangle(bcx, bcy - 45, bcx + 12, bcy-5, fill="white", outline="black",width=2)
            canvas.create_text(bcx + 45, bcy - 28, text="2x6 Joist", font=("Arial", 10))
            canvas.create_rectangle(bcx, bcy-5, bcx+12, bcy + 40, fill="white", outline="black",width=2)
            canvas.create_text(bcx +47, bcy + 13, text="2x8 Backer", font=("Arial", 10))
            canvas.create_rectangle(bx, by, bx + 30, by + 12, fill="white", outline="black",width=2)
            canvas.create_rectangle(bx + 31, by, bx + 53, by + 12, fill="white", outline="black",width=2)
            canvas.create_text(bx-3, by+25, text=f"2x6x{self.format_inchesquarter(outerwidth)}", font=("Arial", 10))
            canvas.create_text(bx+71, by+25, text=f"2x4x{self.format_inchesquarter(outerwidth)}", font=("Arial", 10))

        # --- DEFAULT DRAWING PATH FOR STANDARD RAMPS / PLATFORMS ---

        # --- TRAPEZOID / POLYGON CUSTOM FRAMING PATH ---
        elif is_poly:
            # --- 1. EXTRACT & FORCE LONGEST SIDE TO BOTTOM BASELINE (SIDE A) ---
            raw_sa = data.get("side_a", l)
            raw_sb = data.get("side_b", w)
            raw_sc = data.get("side_c", l * 0.7)
            raw_sd = data.get("side_d", w)

            max_side_length = max(raw_sa, raw_sb, raw_sc, raw_sd)
            sa = raw_sa # max_side_length
            sb = raw_sb #if sa != raw_sb else raw_sa
            sc = raw_sc #if sa != raw_sc else raw_sa
            sd = raw_sd #if sa != raw_sd else raw_sa

            a1 = data.get("angle_1", 90.0)
            a2 = data.get("angle_2", 90.0)
            a3 = data.get("angle_3", 135.0)
            a4 = data.get("angle_4", 90.0)

            # --- 2. CANVAS SCALE & CORNER VERTICES ---
            max_w = max_side_length # sa
            max_h = max(sb, sd, 1.0)
            poly_scale = min(420.0 / max_w, 200.0 / max_h)
            
            origin_x = cx - 80
            origin_y = cy + 200
            st_px = stock_t * poly_scale  # Stock thickness in pixels

            # Trigonometric horizontal shifts based on corner angles
            dx_a1 = st_px / math.tan(math.radians(a1)) if abs(a1 - 90.0) > 0.001 else 0.0
            dx_a2 = st_px / math.tan(math.radians(a2)) if abs(a2 - 90.0) > 0.001 else 0.0
            dx_a3 = st_px / math.tan(math.radians(180.0 - a3)) if abs(a3 - 90.0) > 0.001 and abs(a3 - 180.0) > 0.001 else 0.0
            dx_a4 = st_px / math.tan(math.radians(a4)) if abs(a4 - 90.0) > 0.001 else 0.0

            # Outer Boundary Corner Vertices
            v1_x, v1_y = origin_x, origin_y                                           # Bottom-Left (Corner 1)
            v2_x, v2_y = origin_x + (sa * poly_scale), origin_y                       # Bottom-Right (Corner 2)
            
            top_dx = (sa - sc) if abs(a2 - 90.0) > 0.001 else 0
            v3_x, v3_y = origin_x + ((sa - top_dx) * poly_scale), origin_y - (sb * poly_scale) # Top-Right (Corner 3)
            v4_x, v4_y = origin_x, origin_y - (sb * poly_scale)                       # Top-Left (Corner 4)

            # --- 3. DRAW RIM MEMBERS ---

            # Side A (Bottom Rim Board - Full length baseline)
            # Miter at A2 cuts inward from outer bottom corner (v2_x - dx_a2 at top face)
            canvas.create_polygon([v1_x, v1_y, 
                                   v2_x, v2_y, 
                                   v2_x - dx_a2, v2_y - st_px, 
                                   v1_x + dx_a1, v1_y - st_px], 
                                  fill="#f8f9fa", outline="black", width=1.5)

            # Side C (Top Rim Board)
            # Right cut extends outward to the right on the bottom face (v3_x + dx_a3) to follow slope
            canvas.create_polygon([v4_x, v4_y, 
                                   v3_x, v3_y, 
                                   v3_x + dx_a3, v3_y + st_px, 
                                   v4_x + dx_a4, v4_y + st_px], 
                                  fill="#f8f9fa", outline="black", width=1.5)

            # Side B (Left Rim Board - Fits vertically inside A & C)
            canvas.create_polygon([v1_x + dx_a1, v1_y - st_px, 
                                   v1_x + dx_a1 + st_px, v1_y - st_px, 
                                   v4_x + dx_a4 + st_px, v4_y + st_px, 
                                   v4_x + dx_a4, v4_y + st_px], 
                                  fill="#f8f9fa", outline="black", width=1.5)

            # Label Side B Inner Cut Length
            inner_sb_in = sb - (stock_t * 2)
            canvas.create_text(v1_x + (st_px / 2) + dx_a1 - 10, (v1_y + v4_y) / 2, 
                               text=f"{self.format_incheseighth(inner_sb_in)}", 
                               angle=90, font=("Arial", 9, "bold"), fill="black")

            # --- SIDE D (PARALLELOGRAM FITTING BETWEEN CUT FACES OF A & C) ---
            # --- SIDE D (PARALLELOGRAM FITTING BETWEEN CUT FACES OF A & C) ---
            d_dx_full = v2_x - v3_x
            d_dy_full = v2_y - v3_y
            board_d_angle_rad = math.atan2(d_dy_full, d_dx_full) # Angle relative to horizontal

            # Correct horizontal shift to guarantee constant perpendicular thickness (st_px)
            sin_val = math.sin(board_d_angle_rad)
            shift_x = st_px / sin_val if abs(sin_val) > 0.001 else st_px

            # Outer slope vertices (Connecting v3 top-right to v2 bottom-right)
            d_out_top_x, d_out_top_y = v3_x + dx_a3, v3_y + st_px
            d_out_bot_x, d_out_bot_y = v2_x - dx_a2, v2_y - st_px

            # Inner slope vertices (Shifted left along horizontal top/bottom faces)
            d_in_top_x = d_out_top_x - shift_x
            d_in_top_y = d_out_top_y

            d_in_bot_x = d_out_bot_x - shift_x 
            d_in_bot_y = d_out_bot_y

            # Draw Board D as a Parallelogram
            canvas.create_polygon([d_out_top_x, d_out_top_y, 
                                   d_out_bot_x, d_out_bot_y, 
                                   d_in_bot_x,  d_in_bot_y, 
                                   d_in_top_x,  d_in_top_y], 
                                  fill="#f8f9fa", outline="black", width=1.5)

            # Outer Boundary Perimeter Overlay
     #       canvas.create_polygon([v1_x, v1_y, v2_x, v2_y, v3_x, v3_y, v4_x, v4_y], fill="", outline="red", width=2)

            # --- SIDE D DIMENSIONING (Exterior Position with 1/8" Precision) ---
            d_inner_dx = d_in_bot_x - d_in_top_x
            d_inner_dy = d_in_bot_y - d_in_top_y
            d_inner_len_in = math.hypot(d_inner_dx, d_inner_dy) / poly_scale

            mid_out_x = (d_out_top_x + d_out_bot_x) / 2
            mid_out_y = (d_out_top_y + d_out_bot_y) / 2
            
            d_dx_full = v2_x - v3_x
            d_dy_full = v2_y - v3_y
            # Calculate actual line angle in degrees (Tkinter rotates counter-clockwise)
            line_angle_rad = math.atan2(-d_dy_full, d_dx_full)
            text_angle = math.degrees(line_angle_rad)

            # Keep text readable (upright) rather than upside down
            if text_angle < -90:
                text_angle += 180
            elif text_angle > 90:
                text_angle -= 180

            # Calculate perpendicular offset vector to push text outside the frame
            norm_angle = line_angle_rad + math.pi / 2
            label_offset_x = 22 * math.cos(norm_angle)
            label_offset_y = -22 * math.sin(norm_angle)
            
            # Adjust offset direction if Side C is longer than Side A
            if sc > sa:
                d_text_x = mid_out_x + label_offset_x
                d_text_y = mid_out_y - label_offset_y
            else:
                d_text_x = mid_out_x + label_offset_x
                d_text_y = mid_out_y + label_offset_y

            canvas.create_text(d_text_x, d_text_y, 
                               text=f"{self.format_incheseighth(d_inner_len_in)}", 
                               angle=text_angle, font=("Arial", 9, "bold"), fill="black")




            # --- 4. TRUNCATED VECTOR DETAIL CALLOUT BUBBLES ---
            def create_detail_bubble(target_x, target_y, bubble_x, bubble_y, corner_type, radius=45, zoom=2.5):
                """
                Renders detail bubbles centered precisely around the midpoint 
                of both stub pieces, scaling the radius to fit all vertices.
                """
                # Scaled stock thickness & miter shifts for zoom
                z_st = st_px * zoom
                z_dx1 = dx_a1 * zoom
                z_dx2 = dx_a2 * zoom
                z_dx3 = dx_a3 * zoom
                z_dx4 = dx_a4 * zoom
                
                # 4-inch stub length converted to zoomed canvas pixels
                stub_px = 4.0 * poly_scale * zoom

                # Initial anchor position for the corner joint inside the bubble
                base_r = radius
                if corner_type == 'A1_BL':
                    bx, by = bubble_x - (base_r * 0.35), bubble_y + (base_r * 0.35)
                elif corner_type == 'A2_BR':
                    bx, by = bubble_x + (base_r * 0.35), bubble_y + (base_r * 0.35)
                elif corner_type == 'A3_TR':
                    bx, by = bubble_x + (base_r * 0.35), bubble_y - (base_r * 0.35)
                elif corner_type == 'A4_TL':
                    bx, by = bubble_x - (base_r * 0.35), bubble_y - (base_r * 0.35)

                # Define polygon points for shape 1 and shape 2
                if corner_type == 'A1_BL':
                    poly1 = [bx, by, bx + stub_px, by, bx + stub_px, by - z_st, bx + z_dx1, by - z_st]
                    poly2 = [bx + z_dx1, by - z_st, bx + z_dx1 + z_st, by - z_st, bx + z_dx1 + z_st, by - stub_px, bx + z_dx1, by - stub_px]

                elif corner_type == 'A2_BR':
                    dx_raw = d_out_top_x - d_out_bot_x
                    dy_raw = d_out_top_y - d_out_bot_y
                    len_raw = math.hypot(dx_raw, dy_raw)
                    ux = dx_raw / len_raw if len_raw > 0 else 0
                    uy = dy_raw / len_raw if len_raw > 0 else 0

                    # Angle-corrected horizontal shift for zoomed callout
                    sin_val = abs(dy_raw / len_raw) if len_raw > 0 else 1.0
                    z_shift_x = z_st / sin_val if sin_val > 0.001 else z_st

                    # Side A stub
                    poly1 = [bx, by, bx - stub_px, by, bx - stub_px, by - z_st, bx - z_dx2, by - z_st]
                    
                    # Side D stub with true perpendicular width
                    p1_x, p1_y = bx - z_dx2, by - z_st
                    p2_x, p2_y = bx - z_dx2 - z_shift_x, by - z_st
                    p3_x, p3_y = p2_x + (ux * stub_px), p2_y + (uy * stub_px)
                    p4_x, p4_y = p1_x + (ux * stub_px), p1_y + (uy * stub_px)
                    poly2 = [p1_x, p1_y, p2_x, p2_y, p3_x, p3_y, p4_x, p4_y]

                elif corner_type == 'A3_TR':
                    dx_raw = d_out_bot_x - d_out_top_x
                    dy_raw = d_out_bot_y - d_out_top_y
                    len_raw = math.hypot(dx_raw, dy_raw)
                    ux = dx_raw / len_raw if len_raw > 0 else 0
                    uy = dy_raw / len_raw if len_raw > 0 else 0

                    sin_val = abs(dy_raw / len_raw) if len_raw > 0 else 1.0
                    z_shift_x = z_st / sin_val if sin_val > 0.001 else z_st

                    # Side C stub
                    poly1 = [bx, by, bx - stub_px, by, bx - stub_px, by + z_st, bx + z_dx3, by + z_st]
                    
                    # Side D stub with true perpendicular width
                    p1_x, p1_y = bx + z_dx3, by + z_st
                    p2_x, p2_y = bx + z_dx3 - z_shift_x, by + z_st
                    p3_x, p3_y = p2_x + (ux * stub_px), p2_y + (uy * stub_px)
                    p4_x, p4_y = p1_x + (ux * stub_px), p1_y + (uy * stub_px)
                    poly2 = [p1_x, p1_y, p2_x, p2_y, p3_x, p3_y, p4_x, p4_y]

                elif corner_type == 'A4_TL':
                    poly1 = [bx, by, bx + stub_px, by, bx + stub_px, by + z_st, bx + z_dx4, by + z_st]
                    poly2 = [bx + z_dx4, by + z_st, bx + z_dx4 + z_st, by + z_st, bx + z_dx4 + z_st, by + stub_px, bx + z_dx4, by + stub_px]

                # --- 1. CENTER OF SHAPE 1 (Average X and Y) ---
                c1_x = sum(poly1[::2]) / (len(poly1) / 2)
                c1_y = sum(poly1[1::2]) / (len(poly1) / 2)

                # --- 2. CENTER OF SHAPE 2 (Average X and Y) ---
                c2_x = sum(poly2[::2]) / (len(poly2) / 2)
                c2_y = sum(poly2[1::2]) / (len(poly2) / 2)

                # --- 3. MIDPOINT BETWEEN THE TWO CENTERS ---
                mid_center_x = (c1_x + c2_x) / 2.0
                mid_center_y = (c1_y + c2_y) / 2.0

                # Optional: Align the bubble center (circle origin) with the combined geometric center
                bubble_x, bubble_y = mid_center_x, mid_center_y

                # --- 4. CALCULATE DYNAMIC RADIUS FROM MIDPOINT TO ALL VERTICES ---
                all_points = poly1 + poly2
                max_dist = 0.0
                for i in range(0, len(all_points), 2):
                    vx, vy = all_points[i], all_points[i+1]
                    dist = math.hypot(vx - mid_center_x, vy - mid_center_y)
                    if dist > max_dist:
                        max_dist = dist

                # Add 10px padding for visual margin
                calc_radius = max_dist + 1

                # --- DRAWING PIPELINE ---
                # Leader Line
                angle = math.atan2(bubble_y - target_y, bubble_x - target_x)
                edge_x = bubble_x - calc_radius * math.cos(angle)
                edge_y = bubble_y - calc_radius * math.sin(angle)

                canvas.create_line(target_x, target_y, edge_x, edge_y, dash=(4, 4), fill="#939393", width=1.5)
                canvas.create_oval(target_x - 3, target_y - 3, target_x + 3, target_y + 3, fill="#333333", outline="")

                # White Background Circle
                canvas.create_oval(bubble_x - calc_radius, bubble_y - calc_radius,
                                bubble_x + calc_radius, bubble_y + calc_radius,
                                fill="white", outline="")

                # Draw Both Stubs
                colors = {
                    'A1_BL': ("black", "black"),
                    'A2_BR': ("black", "black"),
                    'A3_TR': ("black", "black"),
                    'A4_TL': ("black", "black")
                }
                c1, c2 = colors[corner_type]

                canvas.create_polygon(poly1, fill="#f8f9fa", outline=c1, width=1.5 * zoom)
                canvas.create_polygon(poly2, fill="#f8f9fa", outline=c2, width=1.5 * zoom)

                # Outer Circle Border Ring
                canvas.create_oval(bubble_x - calc_radius, bubble_y - calc_radius,
                                bubble_x + calc_radius, bubble_y + calc_radius,
                                outline="#333333", width=2)

            # --- 5. GENERATE CALLOUT BUBBLES FOR ALL 4 CORNERS ---
            create_detail_bubble(v1_x, v1_y, v1_x - 85, v1_y + 55, 'A1_BL')  # Bottom-Left
            create_detail_bubble(v2_x, v2_y, v2_x + 95, v2_y + 45, 'A2_BR')  # Bottom-Right
            create_detail_bubble(v3_x, v3_y, v3_x + 90, v3_y - 55, 'A3_TR')  # Top-Right
            create_detail_bubble(v4_x, v4_y, v4_x - 85, v4_y - 55, 'A4_TL')  # Top-Left



           
            # --- 4. CALCULATE & DRAW JOISTS (DYNAMIC CLIPPING AGAINST INNER FACES) ---
            longside = max(sa, sc)
            n_spans = math.ceil((longside - stock_t * 2) / 16.0)
            n_joists = max(2, n_spans + 1)
            spacing_in = (longside - (stock_t * 2) - (stock_t * (n_joists - 2))) / n_spans if n_spans > 0 else 16.0
            spacing_in = math.floor(spacing_in * 2 + 0.5) / 2

            joist_lengths = []

            # Linear interpolation helper for line segments: returns Y for a given X on line segment (x1,y1)->(x2,y2)
            def get_y_at_x(x, x1, y1, x2, y2):
                if abs(x2 - x1) < 0.0001:
                    return y1
                t = (x - x1) / (x2 - x1)
                return y1 + t * (y2 - y1)

            # Define top inner boundary (Side C bottom face: v4_x + dx_a4 + st_px to d_in_top_x)
            top_bound_x1, top_bound_y1 = v4_x + dx_a4 + st_px, v4_y + st_px
            top_bound_x2, top_bound_y2 = d_in_top_x, d_in_top_y

            # Define bottom inner boundary (Side A top face: v1_x + dx_a1 to d_in_bot_x)
            bot_bound_x1, bot_bound_y1 = v1_x + dx_a1, v1_y - st_px
            bot_bound_x2, bot_bound_y2 = d_in_bot_x, d_in_bot_y

            for i in range(1, n_joists - 1):
                offset_in = stock_t + (i * spacing_in) + ((i - 1) * stock_t)
                jx_left = v1_x + (offset_in * poly_scale)
                jx_right = jx_left + st_px

                if (offset_in + stock_t) >= (longside - stock_t):
                    break

                # --- CALCULATE TOP Y BOUNDARIES ---
                # Left Top Y
                if jx_left <= top_bound_x2:
                    jy_top_left = top_bound_y1  # Under Side C
                else:
                    jy_top_left = get_y_at_x(jx_left, d_in_top_x, d_in_top_y, d_in_bot_x, d_in_bot_y) # On Side D inner face

                # Right Top Y
                if jx_right <= top_bound_x2:
                    jy_top_right = top_bound_y1
                else:
                    jy_top_right = get_y_at_x(jx_right, d_in_top_x, d_in_top_y, d_in_bot_x, d_in_bot_y)

                # --- CALCULATE BOTTOM Y BOUNDARIES ---
                # Left Bottom Y
                if jx_left <= bot_bound_x2:
                    jy_bot_left = bot_bound_y1  # Above Side A
                else:
                    jy_bot_left = get_y_at_x(jx_left, d_in_top_x, d_in_top_y, d_in_bot_x, d_in_bot_y) # On Side D inner face

                # Right Bottom Y
                if jx_right <= bot_bound_x2:
                    jy_bot_right = bot_bound_y1
                else:
                    jy_bot_right = get_y_at_x(jx_right, d_in_top_x, d_in_top_y, d_in_bot_x, d_in_bot_y)

                # --- DRAW JOIST POLYGON ---
                # Vertices order: Bottom-Left, Bottom-Right, Top-Right, Top-Left
                canvas.create_polygon([jx_left,  jy_bot_left, 
                                       jx_right, jy_bot_right, 
                                       jx_right, jy_top_right, 
                                       jx_left,  jy_top_left], 
                                      fill="#f8f9fa", outline="black", width=1.5)

                # Calculate Maximum Height of Joist for Dimensioning
                h_left = abs(jy_bot_left - jy_top_left) / poly_scale
                h_right = abs(jy_bot_right - jy_top_right) / poly_scale
                actual_h_in = max(h_left, h_right)

                # Centered length text shifted left outside of joist lines
                text_y = (min(jy_bot_left, jy_bot_right) + max(jy_top_left, jy_top_right)) / 2
                canvas.create_text(jx_left - 10, text_y, 
                                   text=f"{self.format_incheseighth(actual_h_in)}", 
                                   angle=90, font=("Arial", 9, "bold"), fill="black")

                rounded_h_in = math.ceil(actual_h_in * 8) / 8

                # A joist has an angle cut if its top or bottom Y points aren't flat
                is_angled = (jy_top_left != jy_top_right) or (jy_bot_left != jy_bot_right)
                if abs(jy_top_left - jy_top_right) > 1 or abs(jy_bot_left - jy_bot_right) > 1:
                    is_angled = True
                else:
                    is_angled = False

                # Append a dictionary or tuple instead of just the float
                joist_lengths.append({
                    "length": rounded_h_in,
                    "is_angled": is_angled
                })

                # --- 5. JOIST SPACING DASHED LINES ---
                guide_y = v1_y + 15 + (i * 22)
                mark_val = offset_in

                canvas.create_line(jx_left, jy_bot_left, jx_left, guide_y, fill="gray", dash=(2, 2))
                canvas.create_line(v1_x, guide_y, jx_left, guide_y, fill="gray", dash=(2, 2))

                canvas.create_text((v1_x + jx_left) / 2, guide_y - 8, 
                                   text=f"{self.format_incheshalf(mark_val)}\"", 
                                   font=("Arial", 9))





            # --- 6. LABELS AND ANGLE CALLOUTS ---
            canvas.create_text((v1_x + v2_x) / 2, v1_y + 18, text=f"Side A (Ref Base): {self.format_incheseighth(sa)}", font=("Arial", 11, "bold"))
            canvas.create_text(v1_x - 45, (v1_y + v4_y) / 2, text=f"Side B:\n{self.format_incheseighth(sb)}", font=("Arial", 11, "bold"), justify="center")
            canvas.create_text((v4_x + v3_x) / 2, v4_y - 18, text=f"Side C: {self.format_incheseighth(sc)}", font=("Arial", 11, "bold"))
            canvas.create_text((v2_x + v3_x) / 2 + 80, (v2_y + v3_y) / 2 - 10, text=f"Side D:\n{self.format_incheseighth(sd)}", font=("Arial", 11, "bold"), justify="center")

            # Non-90 Degree Angle Annotations
            angles = [
                ("∠1", a1, v1_x - 25, v1_y + 10), 
                ("∠2", a2, v2_x - 20, v2_y +10), 
                ("∠3", a3, v3_x -10, v3_y - 10), 
                ("∠4", a4, v4_x - 25, v4_y - 10)
            ]
            for label, ang, ax, ay in angles:
                if abs(ang - 90.0) > 0.1:
                    canvas.create_text(ax, ay, text=f"{label}: {ang:.1f}°", font=("Arial", 9, "bold"), fill="#d97706")

            # Total Length Arrow Line
            pull_y = v1_y + max(120, (n_joists * 22) + 20)
            canvas.create_line(v1_x, pull_y, v2_x, pull_y, arrow=tk.BOTH, fill="black", width=1.5)
            canvas.create_text((v1_x + v2_x) / 2, pull_y + 15, text=f"Total Length: {self.format_incheseighth(sa)}", font=("Arial", 11, "bold"))



            # --- HELPER: Compute Board Reference Edge & 2x6 Lumber Stock ---
            # --- HELPER: Compute Board Reference Edge & 2x6 Lumber Stock ---
            STOCK_LUMBER_FT = [8, 10, 12]

            def get_2x6_stock_info(length_in):
                """
                Calculates stock requirements for a given length in inches.
                Returns: (fraction_needed, stock_ft)
                Examples: ("1/2", 8), ("1/3", 12), (1, 10)
                """
                req_ft = math.ceil(length_in / 12.0)
                
                for ft in STOCK_LUMBER_FT:
                    stock_in = ft * 12.0
                    if stock_in >= length_in:
                        # Maximum number of cut lengths that fit on this stock board
                        pieces_per_board = int(stock_in // length_in)
                        
                        if pieces_per_board >= 4:
                            return "1/4", ft
                        elif pieces_per_board == 3:
                            return "1/3", ft
                        elif pieces_per_board == 2:
                            return "1/2", ft
                        else:
                            return 1, ft
                            
                return 1, req_ft

            # --- BUILD STRUCTURAL RIM BOARD DATA (ALL 2x6) ---
            
            print ("Selecting cuts for polygon ****************************************")
            print (f"Angle 1 {a1} - Angle 2 {a2} - Angle 3 {a3} - Angle 4 {a4}")
            print ("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-")
            # Side A (Ref Base): If A1 or A2 > 90°, the inside corner opens outward, 
            # meaning the bottom base edge is the Short Side measurement.
            
            if abs(180-a1-a2) < 0.1:
                a_ref_side = "" #parallelogram
            elif (a1 > 90 or a2 > 90):
                a_ref_side = "(Short Side)"
            elif abs(a1-90) < 0.1 and abs(a2-90)<0.1:
                a_ref_side = "" #90 degree cuts
            else:
                a_ref_side = "(Long Side)"

            # Side A
            frac_a, ft_a = get_2x6_stock_info(sa)
            side_a_data = {
                "part": "Side A",
                "stock": f"2x6x{ft_a}'",
                "stock_frac": frac_a,  # 1, "1/2", "1/3", or "1/4"
                "stock_ft": ft_a,      # 8, 10, 12, etc.
                "angles": f"Square ({a1:.1f}°)" if abs(a1 - 90) < 0.1 else f"{a1:.1f}°",
                "angles_end2": f"Square ({a2:.1f}°)" if abs(a2 - 90) < 0.1 else f"{a2:.1f}°",
                "length": sa,
                "ref_side": a_ref_side,
                "qty": 1
            }

            # Side B (Left Vertical Rim)
            if abs(180-a4-a1) < 0.1:
                b_ref_side = "" #parallelogram
            elif (a4 > 90 or a1 > 90):
                b_ref_side = "(Short Side)"
            elif abs(a4-90) < 0.1 and abs(a1-90)<0.1:
                b_ref_side = "" #90 degree cuts
            else:
                b_ref_side = "(Long Side)"

            # Side B
            frac_b, ft_b = get_2x6_stock_info(inner_sb_in)
            side_b_data = {
                "part": "Side B",
                "stock": f"2x6x{ft_b}'",
                "stock_frac": frac_b,
                "stock_ft": ft_b,
                "angles": f"Square ({a1:.1f}°)" if abs(a1 - 90) < 0.1 else f"{a1:.1f}°",
                "angles_end2": f"Square ({a4:.1f}°)" if abs(a4 - 90) < 0.1 else f"{a4:.1f}°",
                "length": inner_sb_in,
                "ref_side": b_ref_side,
                "qty": 1
            }

            # Side C (Top Horizontal Rim)
        
            if abs(180-a3-a4) < 0.1:
                c_ref_side = "" #parallelogram
            elif (a3 > 90 or a4 > 90):
                c_ref_side = "(Short Side)"
            elif abs(a3-90) < 0.1 and abs(a4-90)<0.1:
                c_ref_side = "" #90 degree cuts
            else:
                c_ref_side = "(Long Side)"

            # Side C
            frac_c, ft_c = get_2x6_stock_info(sc)
            side_c_data = {
                "part": "Side C",
                "stock": f"2x6x{ft_c}'",
                "stock_frac": frac_c,
                "stock_ft": ft_c,
                "angles": f"Square ({a4:.1f}°)" if abs(a4 - 90) < 0.1 else f"{a4:.1f}°",
                "angles_end2": f"Square ({a3:.1f}°)" if abs(a3 - 90) < 0.1 else f"{a3:.1f}°",
                "length": sc,
                "ref_side": c_ref_side,
                "qty": 1
            }

            # Side D (Angled Sloped Rim)

            if abs(180-a2-a3) < 0.1:
                d_ref_side = "" #parallelogram
            elif (a2 > 90 or a3 > 90):
                d_ref_side = "(Short Side)"
            elif abs(a2-90) < 0.1 and abs(a3-90)<0.1:
                d_ref_side = "" #90 degree cuts
            else:
                d_ref_side = "(Long Side)"

            # Side D
            frac_d, ft_d = get_2x6_stock_info(d_inner_len_in)
            side_d_data = {
                "part": "Side D",
                "stock": f"2x6x{ft_d}'",
                "stock_frac": frac_d,
                "stock_ft": ft_d,
                "angles": f"Miter {a2:.1f}°",
                "angles_end2": f"Miter {a3:.1f}°",
                "length": d_inner_len_in,
                "ref_side": d_ref_side,
                "qty": 1
            }

            rim_table_data = [side_a_data, side_b_data, side_c_data, side_d_data]

            # --- 7. MATERIALS TABLE ---
            headers = ["Stock Qty", "Size", "Cut / Part", "Length (Cut Side)", "Qty"]

            # Clear previous table widgets if redrawing
            for child in tbl_frame.winfo_children():
                child.destroy()

            # Render Table Headers
            for col_idx, text in enumerate(headers):
                lbl = tk.Label(tbl_frame, text=text, font=("Arial", 10, "bold"), bg="#006400", fg="white", relief="solid", bd=1, padx=4, pady=4)
                lbl.grid(row=0, column=col_idx, sticky="nsew")

            table_rows = []
            rows = []

            # Populate Rim Boards (All 2x6)
            for item in rim_table_data:
                table_rows.append((
                    item["stock_frac"],
                    item["stock"],
                    f"{item['part']} - {item['angles']} / {item['angles_end2']}",
                    f"{self.format_incheseighth(item['length'])} {item['ref_side']}",
                    item["qty"]
                ))

                # 2. Append to Bill of Materials rows for global materials tab calculations
                # Converts fraction strings like "1/2" to float for correct stock aggregation
                frac_val = item["stock_frac"]
                if isinstance(frac_val, str):
                    if "/" in frac_val:
                        num, den = frac_val.split("/")
                        raw_stock_qty = float(num) / float(den)
                    else:
                        raw_stock_qty = float(frac_val)
                else:
                    raw_stock_qty = float(frac_val)

                rows.append([
                    item["stock_frac"], #raw_stock_qty,
                    item["stock"],
                    f"{item['part']} - {item['angles']} / {item['angles_end2']}",
                    f"{self.format_incheseighth(item['length'])} {item['ref_side']}".strip(),
                    item["qty"]
                ])

            print (f"Rows material data - {rows}")

            # Populate Internal Joists (2x6)
            print ("Joist Lengths")
            print (joist_lengths)

            import math
            from collections import defaultdict

            def bin_pack_joists(joist_lengths, kerf_in=0.125):
                """Groups identical or near-identical joist lengths and angle types,

                then packs them into standard 8', 10', or 12' stock boards.
                Returns a list of dicts formatted for cut-list rendering.
                """
                if not joist_lengths:
                    return []

                # 1. Round to 1/8" precision and group by BOTH (length, is_angled)
                grouped = defaultdict(int)
                for item in joist_lengths:
                    if isinstance(item, dict):
                        l = item["length"]
                        is_angled = item.get("is_angled", False)
                    else:
                        l = item
                        is_angled = False

                    key = (round(l * 8) / 8, is_angled)
                    grouped[key] += 1

                results = []

                # 2. Evaluate stock board fit per unique (length, is_angled) group
                for (length_in, is_angled), qty in grouped.items():
                    best_ft = 8
                    best_pcs_per_board = 1

                    for ft in [8, 10, 12]:
                        stock_in = ft * 12.0
                        # Account for blade saw kerf
                        pcs = int((stock_in + kerf_in) // (length_in + kerf_in))
                        if pcs > best_pcs_per_board:
                            best_pcs_per_board = pcs
                            best_ft = ft
                            if pcs >= qty:  # stop when we get to the number of pieces we need
                                break

                    # Cap maximum split to 1/4 board per yield rule (max 4 pieces accounted per board)
                    effective_pcs_per_board = min(best_pcs_per_board, 4)

                    if effective_pcs_per_board > 1:
                        boards_needed = (
                            math.ceil(qty / effective_pcs_per_board * 4) / 4
                        )

                        # Fraction display mapping
                        if effective_pcs_per_board == 2:
                            frac_str = "1/2"
                            frac_val = 0.5
                        elif effective_pcs_per_board == 3:
                            frac_str = "1/3"
                            frac_val = 1 / 3
                        else:
                            frac_str = "1/4"
                            frac_val = 0.25

                        stock_display = f"2x6x{best_ft}'"
                        # Calculate fractional stock consumption for lumber count totals
                        stock_qty_calc = (
                            boards_needed
                            if qty >= effective_pcs_per_board
                            else round(qty * frac_val, 2)
                        )
                    else:
                        boards_needed = qty
                        stock_qty_calc = float(qty)
                        stock_display = f"2x6x{best_ft}'"

                    boards_needed_rem = boards_needed % 1
                    if boards_needed_rem == 0.25:
                        boards_needed_str = (
                            str(int(boards_needed)) + "-1/4"
                            if boards_needed > 1
                            else "1/4"
                        )
                    elif boards_needed_rem == 0.5:
                        boards_needed_str = (
                            str(int(boards_needed)) + "-1/2"
                            if boards_needed > 1
                            else "1/2"
                        )
                    elif boards_needed_rem == 0.75:
                        boards_needed_str = (
                            str(int(boards_needed)) + "-3/4"
                            if boards_needed > 1
                            else "3/4"
                        )
                    else:
                        boards_needed_str = int(boards_needed)

                    results.append({
                        "stock_qty_str": boards_needed_str,
                        "raw_stock_qty": stock_qty_calc,
                        "stock_display": stock_display,
                        "stock_ft": best_ft,
                        "length_in": length_in,
                        "is_angled": is_angled,  # Passed through to building table rows
                        "qty": qty,
                        "pcs_per_board": effective_pcs_per_board,
                    })

                return results

            # Sample joists input: [24.93, 24.93, 24.93, 12.378679656440344]

            # Updated table row building logic:

            if joist_lengths:
                bundled_joists = bin_pack_joists(joist_lengths)

                for group in bundled_joists:
                    # 1. Determine angle description per group
                    if group.get("is_angled", False):
                        j_angle_str = f"Square / Angled ({a3:.1f}°)"
                        j_len_desc = f"{self.format_incheseighth(group['length_in'])} (Long Side)"
                    else:
                        j_angle_str = "Square / Square"
                        j_len_desc = self.format_incheseighth(group['length_in'])

                    # 2. Append row using the local j_angle_str
                    table_rows.append(
                        (
                            group["stock_qty_str"],  # Stock Qty Needed
                            group["stock_display"],  # Size / Stock Board
                            f"Joist - {j_angle_str}",  # Cut / Part Description
                            j_len_desc,  # Target Cut Length
                            group["qty"],  # Piece Count
                        )
                    )

                    # 2. Append to Bill of Materials rows for global lumber calculations
                    # Key schema matches: [Stock_Qty, Size_Desc, Cut_Type, Length_Str, Qty]
                    rows.append([
                        group["stock_qty_str"],
                        f"2x6x{group['stock_ft']}'",
                        j_angle_str,
                        self.format_incheseighth(group["length_in"]),
                        group["qty"]
                    ])
            print ("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$   $$$$$$$$$$       $$$$$$$$$$")
            print (f"Total Rows : {rows}")

            deck_rows = self.calculate_deck_boards(
                side_a=sa, 
                side_b=sb, 
                side_c=sc, 
                miter_angle=a2  # Your existing angle variable
            )

            table_rows.extend(deck_rows)
            rows.extend(deck_rows)
            print(f"Total Rows (with deck boards): {rows}")

            # Render Table Rows
            for row_idx, row in enumerate(table_rows, start=1):
                bg_color = "#ffffff" if row_idx % 2 == 0 else "#f8fafc"
                for col_idx, item in enumerate(row):
                    lbl = tk.Label(tbl_frame, text=str(item), font=("Arial", 9), bg=bg_color, relief="solid", bd=1, padx=4, pady=4)
                    lbl.grid(row=row_idx, column=col_idx, sticky="nsew")





        else:
            #if is_ramp and not is_threshold_ramp:
            #    n_joists = 4
            #    n_spans = 3
            #    spacing = (w-stock_t*4)/3
            #else:
            n_spans = math.ceil((w - stock_t/2) / 16)
            n_joists = n_spans + 1
            spacing = (w-stock_t*n_joists) / n_spans
            spacing = math.floor(spacing * 2 + 0.5) / 2 #round to half inch

            if is_ramp:
                #L R vertical ends
                #break out type of ramp
                if is_threshold_ramp or is_taper_ramp:
                    #break out into blocking between joists vs one large strip
                    print (f"Spans = {n_spans} with spacing {spacing}")
                    blockinset = 18 #how far in to start the braces from the edge to account for thickness
                    for tri in range(0,n_spans):
                        extra_x = 4*v_scale if tri % 2 != 0 else 0  #inset every other by 4" to allow for screws
                        bx1=cx + blockinset + extra_x,
                        by1=cy+stock_t*v_scale + tri*(stock_t+spacing)*v_scale
                        bx2=cx+blockinset+(5.5*v_scale)+ extra_x
                        if tri == n_spans-1:
                            by2=cy+w*v_scale-stock_t*v_scale
                        else:
                            by2=cy+(v_scale*(stock_t+spacing))+ tri*(stock_t+spacing)*v_scale
                        canvas.create_rectangle(bx1, by1, bx2, by2, fill="#f8f9fa", outline="black")
                else:
                    canvas.create_rectangle(cx, cy+stock_t*v_scale, cx+(stock_t*v_scale), cy+(w*v_scale)-stock_t*v_scale, fill="#f8f9fa", outline="black")
                    
                #right side unchanged
                canvas.create_rectangle(cx+((l-stock_t)*v_scale), cy, cx+(l*v_scale), cy+(w*v_scale), fill="#f8f9fa", outline="black")
                canvas.create_text(cx+(l*v_scale)+12,cy+0.5*(w*v_scale), text=f"{self.format_incheshalf(w-(stock_t*2))}", angle=90, anchor="center", font=("Arial", 10))
                                    
            else:
                canvas.create_rectangle(cx, cy, cx+(stock_t*v_scale), cy+(w*v_scale), fill="#f8f9fa", outline="black")
                                 
                canvas.create_rectangle(cx+((l-stock_t)*v_scale), cy, cx+(l*v_scale), cy+(w*v_scale), fill="#f8f9fa", outline="black")
                canvas.create_text(cx+(l*v_scale)+12,cy+0.5*(w*v_scale), text=f"{self.format_incheshalf(w)}", angle=90, anchor="center", font=("Arial", 10))
                                  
            data['spacer_blocks'] = []
            for i in range(n_joists):
                #horizontal members
                y_offset = i * (spacing + stock_t)
                if i == n_joists - 1: y_offset = w - stock_t 
                y1, y2 = cy + (y_offset * v_scale), cy + (y_offset * v_scale) + (stock_t * v_scale)
                if is_threshold_ramp or is_taper_ramp: #extend left side but not right  
                    if i == 0 or i == n_joists-1:
                        canvas.create_rectangle(cx, y1, cx+(l*v_scale), y2, fill="#f8f9fa", outline="green")
                        canvas.create_text(cx+(l*v_scale/2),y1-10, text=f"{self.format_incheshalf(l)}", anchor="center", font=("Arial", 10))                          
                                        
                    else:
                        canvas.create_rectangle(cx, y1, cx+((l-stock_t)*v_scale), y2, fill="#f8f9fa", outline="green")
                        canvas.create_text(cx+(l*v_scale/2),y1-10, text=f"{self.format_incheshalf(l-(stock_t))}", anchor="center", font=("Arial", 10))                          
                                        
                elif is_ramp and (i == 0 or i == n_joists-1): #these go all the way to the left
                    canvas.create_rectangle(cx, y1, cx+(l*v_scale), y2, fill="#f8f9fa", outline="green")
                    canvas.create_text(cx+(l*v_scale/2),y1-10, text=f"{self.format_incheshalf(l)}", anchor="center", font=("Arial", 10))                          
                else:
                    canvas.create_rectangle(cx+(stock_t*v_scale), y1, cx+((l-stock_t)*v_scale), y2, fill="#f8f9fa", outline="blue")
                    canvas.create_text(cx+(l*v_scale/2),y1-10, text=f"{self.format_incheshalf(l-(stock_t*2))}", anchor="center", font=("Arial", 10))                          
                                    
                if i > 0 and i < n_joists - 1:
                    pull_x = cx - (i * 26)
                    mark_val = y_offset - stock_t if is_ramp else y_offset
                    starty = cy+stock_t*v_scale if is_ramp else cy
                    #canvas.create_line(pull_x, starty, pull_x, y1, arrow=tk.BOTH, fill="gray")
                    canvas.create_line(pull_x, starty, pull_x, y1, fill="gray",dash=(1, 1))
                    #extend top and bottom of line for reference
                    canvas.create_line(pull_x, starty, cx-3-((i-2)*26), starty, fill="gray",dash=(1, 1)) #stop short on top
                    canvas.create_line(pull_x, y1, cx-3, y1, fill="gray",dash=(1, 1))

                    canvas.create_text(pull_x-10, (cy + y2)/2, text=f"{self.format_incheshalf(mark_val)}", angle=90, anchor="center", font=("Arial", 10))

                    

                    # 1. First spacer block (e.g., the 11" mark directly)
                    if len(data['spacer_blocks']) == 0:
                        first_block = mark_val
                        data['spacer_blocks'].append(first_block)
                        lastmark = mark_val
                    else:
                        # 2. Intermediate blocks: current arrow label - previous arrow label - thickness
                        # We fetch the actual raw math value used for the previous arrow
                        print (f"Mark val = {mark_val} and last mark = {lastmark}")
                        spacer_len = mark_val - lastmark - stock_t
                        data['spacer_blocks'].append(spacer_len)
                        lastmark = mark_val

                    # 3. Final Edge Block Check: If this is the second-to-last joist loop,
                    # calculate the final remaining gap up to the total width.
                    if i == n_joists - 2:
                        # Width minus the current layout mark minus material thickness
                        final_spacer = w - mark_val - stock_t*3
                        data['spacer_blocks'].append(final_spacer)

            canvas.create_line(cx+(l*v_scale)+30, cy, cx+(l*v_scale)+30, cy+(w*v_scale), arrow=tk.BOTH, fill="black")
            canvas.create_text(cx+(l*v_scale)+55, cy+(w*v_scale)/2, text=f"Total Width: {self.format_inchesquarter(w)}",angle=90, anchor="center", font=("Arial", 12))
            pull_y = cy + (w * v_scale) + 30
            canvas.create_line(cx+(l*v_scale), pull_y, cx, pull_y, arrow=tk.BOTH, fill="black")
            canvas.create_text(cx+(l*v_scale)/2, pull_y + 15, text=f"Total Length: {self.format_inchesquarter(l)}", font=("Arial", 12))
            
            #make the diagram for the cut angles
            if is_ramp:
                if is_taper_ramp:   #still 5 degree start
                    taper_length = h / math.tan(math.radians(sl))
                    taper_length = math.floor(taper_length * 2 + 0.5) / 2 #round to half inch

                    # Calculate where the straight part ends and the taper begins (from the left)
                    straight_length = l - taper_length
                    
                    taper_lengthtext = self.format_incheshalf(taper_length)
                    dybuffer = 45
                    dyoffset = h*5#30
                    dxoffset = 5
                    d_points = [cx, pull_y + dybuffer]  #top left
                    d_points.extend([cx+(l*v_scale), pull_y + dybuffer]) #go right
                    d_points.extend([cx+(l*v_scale)-dxoffset, pull_y + dybuffer+dyoffset]) #go down
                    d_points.extend([cx+(l*v_scale)-dxoffset-straight_length*v_scale, pull_y + dybuffer+dyoffset]) #go left until taper
                    #connect back to start corner
                    d_points.extend([cx,pull_y+dybuffer])
                    canvas.create_polygon(d_points, fill="#cd853f", outline="black",width=2)
                    #kick the joist text to the right more than normal since it's just 1 side
                    cutangletext = f"Joist Cut {sl} Degree Angle"
                    canvas.create_text(cx+(l*v_scale),pull_y + dybuffer + dyoffset + 20,text=cutangletext)
                    tapercuttext = f"Taper Cut to {taper_lengthtext}"
                    canvas.create_text(cx,pull_y + dybuffer + dyoffset + 20,text=tapercuttext)
                    canvas.create_line(cx, pull_y + dybuffer +dyoffset + 4, cx + taper_length * v_scale-3, pull_y+dybuffer + dyoffset+4, fill="black")

                elif is_threshold_ramp: #90 degree start
                    dybuffer = 45
                    dyoffset = h*5#30
                    d_points = [cx, pull_y + dybuffer + dyoffset]  #top left
                    d_points.extend([cx+(l*v_scale), pull_y + dybuffer]) #go right
                    d_points.extend([cx+(l*v_scale), pull_y + dybuffer+dyoffset]) #go down
                    #connect back to start corner
                    d_points.extend([cx,pull_y+dybuffer + dyoffset])
                    canvas.create_polygon(d_points, fill="#cd853f", outline="black",width=2)
                    #kick the joist text to the right more than normal since it's just 1 side
                    joistheighttext = f"Height = {h}\""
                    canvas.create_text(cx+(l*v_scale) + 50,pull_y + dybuffer ,text=joistheighttext)
                    totalheighttext = f"Deck Board adds another 1\" for a total finished height of {h+1}\""
                    canvas.create_text(cx+(l*v_scale) + 197,pull_y + dybuffer + 20,text=totalheighttext)
                    canvas.create_text(cx+(l*v_scale) + 90,pull_y + dybuffer + 40,text="Joist Cut 90 Degree Angle")
                    tapercuttext = f"Taper Cut at {sl} degree slope"
                    canvas.create_text(cx,pull_y + dybuffer + dyoffset + 20,text=tapercuttext)
                
                else:   #normal ramp profile
                    dybuffer = 45
                    dyoffset = 30
                    dxoffset = 15
                    d_points = [cx, pull_y + dybuffer]
                    d_points.extend([cx+(l*v_scale), pull_y + dybuffer])
                    d_points.extend([cx+(l*v_scale)-dxoffset, pull_y + dybuffer+dyoffset])
                    d_points.extend([cx-dxoffset,pull_y + dybuffer+dyoffset])
                    d_points.extend([cx,pull_y+dybuffer])
                    canvas.create_polygon(d_points, fill="#cd853f", outline="black",width=2)
                    canvas.create_text(cx+(l*v_scale)/2,pull_y + dybuffer + dyoffset + 20,text="Joist Cut 5 Degree Angle")

        # --- DATA GENERATION & BILL OF MATERIALS GENERATION ---
        if is_ramp:
            
            if is_taper_ramp or is_threshold_ramp:
                jlc_l, jlc_p = self.pick_board_length(w-stock_t*2); sjc = 1/jlc_p
                jl_l, jl_p = self.pick_board_length(l); sj = 2/jl_p
                jlb_l, jlb_p = self.pick_board_length(l-stock_t); sjb = (n_joists-2)/jlb_p #one side is longer in these from normal
                db_ct = math.ceil(l/5.5); db_l, db_p = self.pick_board_length(w); sdb = db_ct/db_p
                angletype = f"{sl}° Cut" if is_taper_ramp else "Square"
                bwid = 4 if h <= 3.5 else 6
                rows = [[self.format_stock(sjc), f"2x{bwid}x{jlc_l}'", "Square", self.format_inchesquarter(w-stock_t*2), 1],
                        [self.format_stock(sjb), f"2x{bwid}x{jlb_l}'", angletype, self.format_inchesquarter(l-stock_t), n_joists-2],
                        [self.format_stock(sj), f"2x{bwid}x{jl_l}'", angletype, self.format_inchesquarter(l), 2], #outer
                        [self.format_stock(sdb), f"5/4x6x{db_l}'", "Square", self.format_inchesquarter(w), db_ct]] 
                
                # Inside your cut-list table drawing logic:
                if data.get('spacer_blocks'):
                    total_blocks_len = sum(data['spacer_blocks'])
                sb_l, sb_p = self.pick_board_length(total_blocks_len)
                
                # Using 1 board divided by how many total lengths fit into that stock size
                ssb = 1 / sb_p 

                # 2. Map and format each individual block length for the display column
                formatted_cuts_list = [self.format_incheshalf(block_w) for block_w in data['spacer_blocks']]
                # Combine them into a single string: '11", 11-1/2", 11"'
                consolidated_lengths_str = ", ".join(formatted_cuts_list)

                # 3. Create the consolidated row
                spacer_row = [
                    self.format_stock(ssb),          # Material Quantity / Stock Piece
                    f"2x6x{sb_l}'",                  # Stock Board Length (Assuming 2x4, change if 2x6)
                    "Square Spacer",                   # Description/Cut type
                    consolidated_lengths_str,        # Combined target lengths column
                    1      #len(data['spacer_blocks'])       # Number of cut pieces total
                ]
            
                # 4. Insert the spacer row at the top or bottom of your rows list
                rows.append(spacer_row)
                
            else: #regular ramp
                jlc_l, jlc_p = self.pick_board_length(w-stock_t*2); sjc = 2/jlc_p
                jl_l, jl_p = self.pick_board_length(l); sj = 2/jl_p
                jlb_l, jlb_p = self.pick_board_length(l-stock_t*2); sjb = (n_joists-2)/jlb_p #one side is longer in these from normal
                db_ct = math.ceil(l/5.5); db_l, db_p = self.pick_board_length(w); sdb = db_ct/db_p
                rows = [[self.format_stock(sjc), f"2x6x{jlc_l}'", "Square", self.format_inchesquarter(w-stock_t*2), 2],
                        [self.format_stock(sjb), f"2x6x{jlb_l}'", "5° Cut", self.format_inchesquarter(l-stock_t*2), 2],
                        [self.format_stock(sj), f"2x6x{jl_l}'", "5° Cut", self.format_inchesquarter(l), 2],
                        [self.format_stock(sdb), f"5/4x6x{db_l}'", "Square", self.format_inchesquarter(w), db_ct]] 
        elif is_step:
            steps = max(1, int((l - 1) // 10) + 1)
            rows = [
                ["2", f"{steps} Step Stringers", "Outside","", 2],
                ["2", f"{steps} Step Stringers", "Inside", "Notch Top", 2],
                ["1/2", "2x8x8'", "Cross Post",f"{self.format_inchesquarter(outerwidth + self.p_size)}", 1]
            ]
            if innerwidth <= 40:
                rows.append(["1/3", "2x6x10'", "Top Bracing", f"{self.format_inchesquarter(innerwidth)}", 1])
            else:
                rows.append(["1/2", "2x6x8'", "Top Bracing", f"{self.format_inchesquarter(innerwidth)}", 1])
                
            if outerwidth <= 40:
                rows.append(["1/3", "2x6x10'", "Bottom Bracing", f"{self.format_inchesquarter(outerwidth)}", 1])
                rows.append(["1/3", "2x4x10'", "Bottom Bracing", f"{self.format_inchesquarter(outerwidth)}", 1])
                rows.append([steps, "5/4x6x10'", "Tread Decking", f"{self.format_inchesquarter(outerwidth)}", steps*3])
            else:
                rows.append(["1/2", "2x6x8'", "Bottom Bracing", f"{self.format_inchesquarter(outerwidth)}", 1])
                rows.append(["1/2", "2x4x8'", "Bottom Bracing", f"{self.format_inchesquarter(outerwidth)}", 1])
                rows.append([self.format_incheshalf(steps*1.5), "5/4x6x8'", "Tread Decking", f"{self.format_inchesquarter(outerwidth)}", steps*3])
        elif is_poly:
            print ("Materials is done in method above")
        else:
            jl_l, jl_p = self.pick_board_length(w); sj = 2/jl_p
            jlb_l, jlb_p = self.pick_board_length(l-stock_t*2); sjb = n_joists/jlb_p
            db_ct = math.ceil(l/5.5); db_l, db_p = self.pick_board_length(w); sdb = db_ct/db_p
            rows = [[self.format_stock(sj), f"2x6x{jl_l}'", "Square", self.format_inchesquarter(w), 2],
                    [self.format_stock(sjb), f"2x6x{jlb_l}'", "Square", self.format_inchesquarter(l-stock_t*2), n_joists],
                    [self.format_stock(sdb), f"5/4x6x{db_l}'", "Square", self.format_inchesquarter(w), db_ct]] 

        # Save rows array to sections dictionary cleanly
        if tag:
            self.sections[tag]['materials_data'] = rows 
            
            # --- AUTOMATIC LENGTHS & QUANTITIES PARSING LAYER ---
            # Loop through the compiled rows above to fill lumber_counts dictionary instantly
            for r in rows:
                try:
                    # 1. Grab Stock Qty (r[0]) instead of part count (r[4])
                    stock_qty_str = str(r[0]).strip()
                    
                    # Convert fraction strings like "5-2/3" or "1/2" into precise decimal values
                    if "-" in stock_qty_str:
                        whole_part, frac_part = stock_qty_str.split("-")
                        whole_val = float(whole_part)
                        if "/" in frac_part:
                            num, denom = frac_part.split("/")
                            stock_qty = whole_val + (float(num) / float(denom))
                        else:
                            stock_qty = whole_val
                    elif "/" in stock_qty_str:
                        num, denom = stock_qty_str.split("/")
                        stock_qty = float(num) / float(denom)
                    else:
                        stock_qty = float(stock_qty_str)

                    desc_str = str(r[1]).upper().strip() # e.g. "5/4X6X10'"

                    # Catch stringer lines explicitly to group them together
                    if "STEP STRINGERS" in desc_str:
                        # Extract the step number from the description string safely
                        try:
                            # Splitting "3 STEP STRINGERS" gets the first element '3'
                            step_num = int(desc_str.split()[0])
                        except (ValueError, IndexError):
                            step_num = steps # Fallback to standard local variable counter
                        
                        # Use a dedicated key identifier scheme for custom stringers
                        key = ("stringers", step_num)
                        self.sections[tag]['lumber_counts'][key] = self.sections[tag]['lumber_counts'].get(key, 0.0) + stock_qty
                        continue

                    if any(t in desc_str for t in ["5/4X6", "2X6", "2X4", "4X4", "2X8"]):
                        l_type = ""
                        for t in ["5/4X6", "2X6", "2X4", "4X4", "2X8"]:
                            if t in desc_str:
                                l_type = t.lower()
                                break
                        
                        l_ft = 8
                        if "10'" in desc_str: l_ft = 10
                        elif "12'" in desc_str: l_ft = 12
                        
                        if l_type:
                            key = (l_type, l_ft)
                            # Keep running tallies as floats so fractional boards aggregate properly
                            self.sections[tag]['lumber_counts'][key] = self.sections[tag]['lumber_counts'].get(key, 0.0) + stock_qty
                except (ValueError, IndexError, ZeroDivisionError):
                    continue
        if is_poly:
            print ("Handled above")
        else:        
            # Build Table Headers
            headers = ["Stock Qty", "Size", "Cut / Part", "Length", "Qty"]
            for i, h in enumerate(headers):
                col_width = 20 if i == 3 else 15
                tk.Label(data['table'], text=h, font=("Arial", 10, "bold"), 
                        bg="darkgreen", fg="white", width=col_width, relief="raised").grid(row=0, column=i, sticky="nsew")

            # Build Table Rows
            for r_idx, row in enumerate(rows, start=1):
                for c_idx, val in enumerate(row):
                    col_width = 20 if c_idx == 3 else 15
                    tk.Label(data['table'], text=val, font=("Arial", 10, "bold"), 
                            bg="white", relief="groove", width=col_width).grid(row=r_idx, column=c_idx, sticky="nsew")


    import math

    def calculate_deck_boards(self, side_a, side_b, side_c, miter_angle, kerf=0.125):
        STOCK_SIZES = [96.0, 120.0, 144.0]  # 8', 10', 12'
        BOARD_WIDTH = 5.5
        
        # 1. Normalize angle: Chop saws measure relative to perpendicular (90°)
        # 120° corner angle -> 30° miter cut
        display_miter = abs(miter_angle - 90.0) if miter_angle > 90 else miter_angle
        miter_rad = math.radians(display_miter)
        
        num_boards = math.ceil(side_b / BOARD_WIDTH)
        
        # Determine direction: Does the deck widen or narrow from bottom to top?
        # Board 1 starts at the longest edge and steps down
        start_length = max(side_a, side_c)
        min_length = min(side_a, side_c)
        
        boards = []
        for i in range(num_boards):
            y_offset = i * BOARD_WIDTH
            length = start_length - (y_offset * math.tan(miter_rad))
            length = max(length, min_length)  # Clamp to shorter edge
            boards.append({"id": i + 1, "length": round(length, 2)})
            
        sorted_boards = sorted(boards, key=lambda x: x["length"], reverse=True)
        stock_allocations = []
        
        # 2. Bin-Packing with Stock Upgrading / Bumping
        for board in sorted_boards:
            placed = False
            board_len = board["length"]
            
            # Step A: Check existing stock capacity
            for stock in stock_allocations:
                used = sum(b["length"] for b in stock["cuts"]) + (len(stock["cuts"]) * kerf)
                if board_len <= (stock["stock_length"] - used):
                    stock["cuts"].append(board)
                    placed = True
                    break
                    
            # Step B: Try upgrading an existing stock board length
            if not placed:
                for stock in stock_allocations:
                    current_size = stock["stock_length"]
                    larger_sizes = [s for s in STOCK_SIZES if s > current_size]
                    
                    for new_size in larger_sizes:
                        used = sum(b["length"] for b in stock["cuts"]) + (len(stock["cuts"]) * kerf)
                        if board_len <= (new_size - used):
                            stock["stock_length"] = new_size
                            stock["cuts"].append(board)
                            placed = True
                            break
                    if placed:
                        break
                        
            # Step C: Open a new stock board
            if not placed:
                chosen_stock = next((s for s in STOCK_SIZES if board_len <= s), 144.0)
                stock_allocations.append({"stock_length": chosen_stock, "cuts": [board]})
                
        # 3. Format rows matching your table schema
        table_rows = []
        for stock in stock_allocations:
            stock_feet = int(stock["stock_length"] // 12)
            stock_label = f"5/4x6x{stock_feet}'"
            
            part_ids = [str(b["id"]) for b in stock["cuts"]]
            part_name = f"Deck Board {' & '.join(part_ids)}" if len(part_ids) > 1 else f"Deck Board {part_ids[0]}"
            
            formatted_lengths = [self.format_incheseighth(b["length"]) for b in stock["cuts"]]
            lengths_str = " & ".join(formatted_lengths) + " (Long Side)"
            
            # Uses display_miter (30.0°) instead of raw corner angle (120.0°)
            table_rows.append((
                1,                                                                      # r[0] stock_qty
                stock_label,                                                            # r[1] size
                f"{part_name} - Square (90.0°) / Miter ({display_miter:.1f}°)",         # r[2] cut_part
                lengths_str,                                                            # r[3] length
                1                                                                       # r[4] qty
            ))
            
        return table_rows

    def generate_rails(self):
        """The Refined Engine: Rotated polygons, ramp & step end filtering, and vector post snapping.
        Uses a two-pass approach so clip_to_post_face has full knowledge of neighboring rails.
        """

        self.manual_override_active = False

        self.rail_canvas.delete("all")
        rail_w = 1.5 * self.scale
        self.rail_count = 0
        self.rail_entries = {}  # Clear previous entries

        # -------------------------------------------------------------------------
        # 1. Background: Grey Component Names for Reference
        # -------------------------------------------------------------------------
        for tag, data in self.sections.items():
            if tag == "REF_POINT":
                continue
            sid = self.canvas.find_withtag(f"{tag} && shape")[0]
            c = self.canvas.coords(sid)
            
            # Center of the section
            xs = c[0::2]
            ys = c[1::2]
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            
            # Draw section outline
            self.rail_canvas.create_polygon(*c, fill="", outline="#f0f0f0", dash=(4,4))
            name = data.get('name', tag).replace("_", " ").title()
            self.rail_canvas.create_text(mx, my, text=name, fill="#999", 
                                    font=("Arial", 10, "italic"))

        # -------------------------------------------------------------------------
        # 2. Get Live Posts (All posts)
        # -------------------------------------------------------------------------
        posts = []
        for p_item in self.post_canvas.find_withtag("movable_post"):
            if self.post_canvas.type(p_item) in ("rectangle", "polygon"):
                pc = self.post_canvas.coords(p_item)
                posts.append(pc)
                self.rail_canvas.create_polygon(*pc, outline="#ccc", fill="#f9f9f9")

        # -------------------------------------------------------------------------
        # 3. PASS 1: Build Raw Rail Segments & Populate self.rail_entries
        # -------------------------------------------------------------------------
        for tag, data in self.sections.items():
            if tag == "REF_POINT" or tag.startswith("Paver"):
                continue
            
            sid = self.canvas.find_withtag(f"{tag} && shape")[0]
            c = self.canvas.coords(sid)

            num_pts = len(c) // 2
            edges = []
            
            # Build directed edges from polygon vertices
            for i in range(num_pts):
                x1, y1 = c[i*2], c[i*2 + 1]
                next_idx = (i + 1) % num_pts
                x2, y2 = c[next_idx*2], c[next_idx*2 + 1]
                
                edge_len = math.hypot(x2 - x1, y2 - y1)
                if edge_len < 1.0: 
                    continue
                
                edges.append((x1, y1, x2, y2, edge_len))

            # --- DETECT RAMP / STEP EDGE ORIENTATION ---
            is_ramp = "RAMP" in data.get('name', '').upper()
            is_step = "STEP" in data.get('name', '').upper() or data.get('p_type') == "STEP"

            if is_ramp and len(edges) >= 4:
                # Match edges against expected length L instead of picking longest
                target_l_px = data.get('l', 0) * self.scale
                
                # Sort edges by absolute difference from target length L
                sorted_by_l_diff = sorted(edges, key=lambda e: abs(e[4] - target_l_px))
                valid_edges = sorted_by_l_diff[:2]

            elif is_step:
                # Steps: filter out edges that run parallel to step tread lines
                valid_edges = []
                step_lines = self.canvas.find_withtag(f"{tag} && step_line")

                if step_lines:
                    # Get vector of the first step tread line
                    lc = self.canvas.coords(step_lines[0])
                    step_dx = lc[2] - lc[0]
                    step_dy = lc[3] - lc[1]
                    step_len = math.hypot(step_dx, step_dy)

                    if step_len > 0:
                        s_ux, s_uy = step_dx / step_len, step_dy / step_len

                        for ex1, ey1, ex2, ey2, edge_len in edges:
                            e_ux = (ex2 - ex1) / edge_len
                            e_uy = (ey2 - ey1) / edge_len

                            # Cross-product checks vector alignment:
                            # if near 0, edge is PARALLEL to step treads (top/bottom exit)
                            cross_prod = abs(e_ux * s_uy - e_uy * s_ux)

                            if cross_prod > 0.3:
                                # Edge runs along the side stringer profile -> Valid rail
                                valid_edges.append((ex1, ey1, ex2, ey2, edge_len))
                    else:
                        valid_edges = edges
                else:
                    # Fallback if no step_line tags exist: keep 2 edges matching L
                    target_l_px = data.get('l', 0) * self.scale
                    valid_edges = sorted(edges, key=lambda e: abs(e[4] - target_l_px))[:2]
            else:
                valid_edges = edges

            # Section Centroid for Normal Direction Verification
            xs = c[0::2]
            ys = c[1::2]
            centroid_x = sum(xs) / len(xs)
            centroid_y = sum(ys) / len(ys)

            for ex1, ey1, ex2, ey2, edge_len in valid_edges:
                ux, uy = (ex2 - ex1) / edge_len, (ey2 - ey1) / edge_len
                angle = math.atan2(ey2 - ey1, ex2 - ex1)

                # Base normal (-uy, ux)
                nx, ny = -uy, ux

                # Ensure normal points INWARD toward centroid
                mid_x, mid_y = (ex1 + ex2) / 2, (ey1 + ey2) / 2
                test_x, test_y = mid_x + nx * 5, mid_y + ny * 5
                
                dist_test = math.hypot(test_x - centroid_x, test_y - centroid_y)
                dist_mid = math.hypot(mid_x - centroid_x, mid_y - centroid_y)
                
                if dist_test > dist_mid:
                    nx, ny = -nx, -ny

                # Extract exposed segments
                segments = self.get_exposed_segments(ex1, ey1, ex2, ey2, tag)
                
                for s_start, s_end in segments:
                    if (s_end - s_start) < (4*self.scale): 
                        continue
                    
                    rx1, ry1 = ex1 + ux * s_start, ey1 + uy * s_start
                    rx2, ry2 = ex1 + ux * s_end,   ey1 + uy * s_end
                    
                    self.rail_count += 1
                    r_num_tag = f"RailNum{self.rail_count}"

                    # Store raw geometry and metadata for Pass 2
                    self.rail_entries[r_num_tag] = {
                        'start_x': rx1,
                        'start_y': ry1,
                        'end_x': rx2,
                        'end_y': ry2,
                        'ux': ux,
                        'uy': uy,
                        'nx': nx,
                        'ny': ny,
                        'angle': angle,
                        'ptype': data.get('p_type'),
                        'pname': data.get('name'),
                        'section_tag': tag
                    }

        # -------------------------------------------------------------------------
        # 4. PASS 2: Clip Endpoints Against All Rails & Render to Canvas
        # -------------------------------------------------------------------------
        for r_num_tag, r_data in list(self.rail_entries.items()):
            ux, uy = r_data['ux'], r_data['uy']
            nx, ny = r_data['nx'], r_data['ny']
            tag = r_data['section_tag']
            ptype = r_data['ptype']

            # Clip start and end points using the global rail context
            rx1, ry1 = self.clip_to_post_face(
                r_data['start_x'], r_data['start_y'], 
                ux, uy, posts, "START", 
                current_rail_name=r_num_tag, all_rails=self.rail_entries
            )
            rx2, ry2 = self.clip_to_post_face(
                r_data['end_x'], r_data['end_y'], 
                ux, uy, posts, "END", 
                current_rail_name=r_num_tag, all_rails=self.rail_entries
            )
            
            final_len_px = math.hypot(rx2 - rx1, ry2 - ry1)
            actual_inches = final_len_px / self.scale

            # Apply the 22.5% slope factor for STEP sections
            if ptype == "STEP":
                actual_inches *= 1.225
                
            final_len_in = math.ceil(actual_inches)
            
            # --- REQUIRE RAIL LENGTH > 5 INCHES ---
            if final_len_in < 5: 
                del self.rail_entries[r_num_tag]
                continue

            # Construct 4-corner polygon: Outer edge (P1, P2), inner edge (P3, P4)
            p1 = (rx1, ry1)
            p2 = (rx2, ry2)
            p3 = (rx2 + nx * rail_w, ry2 + ny * rail_w)
            p4 = (rx1 + nx * rail_w, ry1 + ny * rail_w)
            
            rail_poly_coords = [p1[0], p1[1], p2[0], p2[1], p3[0], p3[1], p4[0], p4[1]]
            
            # Midpoints
            mx, my = (rx1 + rx2) / 2, (ry1 + ry2) / 2
            center_rx = (p1[0] + p2[0] + p3[0] + p4[0]) / 4
            center_ry = (p1[1] + p2[1] + p3[1] + p4[1]) / 4

            # Draw Rail Polygon
            rail_item = self.rail_canvas.create_polygon(
                rail_poly_coords, 
                fill="#555", 
                outline="black", 
                tags=("draggable_rail", "rail", r_num_tag, ptype or '', tag, final_len_in)
            )

            # Draw Board Name Label (Inside Rail)
            #self.rail_canvas.create_text(
            #    center_rx, center_ry,
            #    text=r_num_tag,
            #    fill="white",
            #    font=("Arial", 7, "bold"),
            #    tags=("rail_text", f"label_{r_num_tag}")
            #)

            # --- SMART OFFSET LENGTH LABEL (e.g. 91") ---
            is_horiz = abs(ux) > abs(uy)
            if is_horiz:
                # Place above or below edge depending on inward normal
                oy = -12 if ny < 0 else 12
                ox = 0
            else:
                ox = -15 if nx < 0 else 15
                oy = 0

            self.rail_canvas.create_text(
                mx + ox, my + oy,
                text=f'{final_len_in}"',
                fill="black",
                font=("Arial", 9, "bold"),
                tags=(f"length_label_{r_num_tag}", "rail_label")
            )

            # Finalize dict entry
            r_data.update({
                'id': rail_item,
                'canvas_coords': rail_poly_coords,
                'label_coords': [center_rx, center_ry],
                'rlen': final_len_in,
                'rotation': math.degrees(r_data['angle'])
            })
            self.bind_item(r_num_tag)

        self.rail_combined_materialColor()
        self.addrail_btn.pack(side=tk.RIGHT, padx=20)

    import math

    def clip_to_post_face(self, px, py, ux, uy, posts, point_type, current_rail_name=None, all_rails=None):
        """
        Trims rail endpoints cleanly based on exact joint relationships:
        - Co-linear parallel rails: Split 50/50 at centerline (p_mid).
        - Offset parallel, Corner & Terminal ends: Extend to exact post boundary along rail vector direction.
        - Supports orthogonal (0°/90°) AND rotated/angled ramp directions.
        """
        search_radius = 12 * self.scale

        for p in posts:
            p_xs = p[0::2]
            p_ys = p[1::2]
            
            p_mid_x = sum(p_xs) / len(p_xs)
            p_mid_y = sum(p_ys) / len(p_ys)

            # Check if rail endpoint is near this post
            if math.hypot(px - p_mid_x, py - p_mid_y) < search_radius:
                
                has_colinear_continuation = False

                if all_rails:
                    for r_name, r_data in all_rails.items():
                        if r_name == current_rail_name:
                            continue
                        
                        r_start = (r_data['start_x'], r_data['start_y'])
                        r_end = (r_data['end_x'], r_data['end_y'])
                        
                        touching_post = (math.hypot(r_start[0] - p_mid_x, r_start[1] - p_mid_y) < search_radius or
                                        math.hypot(r_end[0] - p_mid_x, r_end[1] - p_mid_y) < search_radius)
                        
                        if touching_post:
                            r_ux, r_uy = r_data.get('ux', 0), r_data.get('uy', 0)
                            
                            # Cross product check for parallel orientation
                            cross_prod = abs(ux * r_uy - uy * r_ux)
                            
                            if cross_prod < 0.15:
                                # Distance between lines check (perpendicular offset)
                                # Distance = |(y2 - y1)*ux - (x2 - x1)*uy|
                                perp_dist_start = abs((r_start[1] - py) * ux - (r_start[0] - px) * uy)
                                perp_dist_end = abs((r_end[1] - py) * ux - (r_end[0] - px) * uy)
                                
                                tol = 3.0 * self.scale
                                if min(perp_dist_start, perp_dist_end) < tol:
                                    has_colinear_continuation = True

                # -----------------------------------------------------------------
                # 1. CO-LINEAR CONTINUATION: Split 50/50 at Post Center
                # -----------------------------------------------------------------
                if has_colinear_continuation:
                    # Project (px, py) onto post midpoint along (ux, uy)
                    dot = (p_mid_x - px) * ux + (p_mid_y - py) * uy
                    return (px + dot * ux, py + dot * uy)

                # -----------------------------------------------------------------
                # 2. CORNER OR TERMINAL: Extend to Nearest/Farthest Outer Post Boundary
                # -----------------------------------------------------------------
                # Project all 4 post corner vertices along the rail direction vector (ux, uy)
                post_corners = list(zip(p_xs, p_ys))
                projections = []
                
                for cx, cy in post_corners:
                    # Scalar projection along vector (ux, uy) relative to endpoint (px, py)
                    proj = (cx - px) * ux + (cy - py) * uy
                    projections.append(proj)

                # For START point: target the closest face of the post (min projection along ux,uy)
                # For END point: target the farthest face of the post (max projection along ux,uy)
                if point_type == "START":
                    target_dot = min(projections)
                else: # END
                    target_dot = max(projections)

                return (px + target_dot * ux, py + target_dot * uy)

        return (px, py)


    def rail_combined_materialColor(self, manual_override=None):
        # Pass the override status down into your data calculator
        print ("Combined Materials start")
        print (manual_override)
        if manual_override is None:
            manual_override = self.manual_override_active

        boards, rail_colors, pairing_data = self.calculate_materials(manual_override=manual_override)
        print ("Combined Materials")
        print (boards)
        print (rail_colors)
        print (pairing_data)        

        self.rail_canvas.delete("link_label") 
        self.rail_canvas.delete("pairing_text")


        # --- SAVE VALUES FOR THE HTML EXPORT ---
        self.last_rail_boards = boards
        self.last_rail_colors = rail_colors
        self.last_rail_pairing_data = pairing_data

        # 3. APPLY COLORS TO CANVAS
        for rid, color in rail_colors.items():
            self.rail_canvas.itemconfig(rid, fill=color)

        # 4. DRAW TABLES
        self.draw_legend_and_tables(boards, rail_colors, pairing_data)
        
        self.rail_canvas.config(scrollregion=self.rail_canvas.bbox("all"))


    def get_exposed_segments(self, x1, y1, x2, y2, current_tag):
        """Vector-based subtractive logic: correctly calculates exposed edge segments 
        regardless of edge direction or vertex ordering."""
        
        edge_len = math.hypot(x2 - x1, y2 - y1)
        if edge_len < 1.0:
            return []

        # Directed unit vector along the edge
        ux = (x2 - x1) / edge_len
        uy = (y2 - y1) / edge_len

        exposed = [(0.0, edge_len)]

        for o_tag in self.sections:
            if o_tag == current_tag or o_tag == "REF_POINT" or o_tag.startswith("Paver"):
                continue

            sid_list = self.canvas.find_withtag(f"{o_tag} && shape")
            if not sid_list:
                continue

            oc = self.canvas.coords(sid_list[0])
            num_pts = len(oc) // 2

            # Find all neighbor vertices/edges that lie directly against this edge
            # Project neighbor points along edge direction vector
            projections = []
            for i in range(num_pts):
                px, py = oc[i*2], oc[i*2 + 1]
                
                # Perpendicular distance from neighbor point to edge line
                perp_dist = abs((px - x1) * (-uy) + (py - y1) * ux)
                
                # If point is flush against edge (within 3px tolerance)
                if perp_dist < 3.0:
                    # Parallel distance along the edge from (x1, y1)
                    proj = (px - x1) * ux + (py - y1) * uy
                    projections.append(proj)

            if len(projections) >= 2:
                # Calculate start and end of overlap along directed vector
                overlap_start = max(0.0, min(projections))
                overlap_end = min(edge_len, max(projections))

                # Clip the covered segment if there is a valid overlap
                if overlap_start < overlap_end and (overlap_end - overlap_start) > 2.0:
                    new_exposed = []
                    for s, e in exposed:
                        if overlap_start >= e or overlap_end <= s:
                            new_exposed.append((s, e))
                        else:
                            if overlap_start > s:
                                new_exposed.append((s, overlap_start))
                            if overlap_end < e:
                                new_exposed.append((overlap_end, e))
                    exposed = new_exposed

        return exposed

    
    def is_section_at(self, x, y):
        for tag in self.sections:
            # Find the shape with this tag
            shapes = self.canvas.find_withtag(f"{tag} && shape")
            if not shapes:
                continue
                
            c = self.canvas.coords(shapes[0])
            
            # Check if coordinates are within the click area
            if (c[0]-2 <= x <= c[2]+2) and (c[1]-2 <= y <= c[3]+2):
                return True, tag  # Return both values
                
        return False, None  # Return False and None if nothing is found
    
    def calculate_materials(self, manual_override=False):
        # --- NEW MANUAL OVERRIDE GUARD INJECTION ---
        if manual_override:
            print ("Manual override")
            # 1. Reset standard stock counters for tallying
            self.total_8ft_boards = 0
            self.total_10ft_boards = 0
            self.total_12ft_boards = 0
            
            self.rail_colors = {}
            self.pairing_data = []

            self.rail_canvas.delete("link_line")
            self.rail_canvas.delete("link_label")
            self.rail_canvas.delete("pairing_text")
            self.rail_canvas.delete("pair_label")    # Target for mid-point text assets
            self.rail_canvas.delete("pair_link")   # Target for stock type indicators
            self.rail_canvas.delete("text")

            # Use the exact same color palette your automatic layout mode uses
            pair_colors = ["#FF9800", "#E91E63", "#9C27B0", "#3F51B5", "#00BCD4", "#4CAF50", "#FFEB3B"]
            color_map = {}

            # First, clean up any previous manual linkage lines or text blocks left on the canvas
            self.rail_canvas.delete("link_line")
            self.rail_canvas.delete("link_label")

            # 2. Iterate through your modified custom board groupings
            for b in self.boards:
                print (f"Boards {b}")
                unique_ids = list(set(item['id'] for item in b['items']))
                is_single_split = (len(b['items']) > 1 and len(unique_ids) == 1)
                # Re-tally current active material stock sizes
                size = b.get('size', 96)
                board_qty = b.get('multiplier', 3)
                print (f"Board qty {board_qty}")
                if size == 96: self.total_8ft_boards += 1
                elif size == 120: self.total_10ft_boards += 1
                elif size == 144: self.total_12ft_boards += 1

                items = b.get('items', [])
                print (f"Items {items}")
                if not items:
                    continue

                # Safely extract the component IDs representing the physical canvas rails
                unique_ids = []
                clean_lengths = []
                for item in items:
                    print (f"Item {item}")
                    if isinstance(item, dict):
                        unique_ids.append(item.get('id'))
                        clean_lengths.append(float(item.get('len', 0)))
                    else:
                        # Fallback case if item is a direct structural dictionary reference
                        unique_ids.append(b.get('id'))
                        clean_lengths.append(float(item))
                    print (f"Unique id {item} ' ' {unique_ids}")
                # Filter out None values to keep canvas engine happy
                unique_ids = list(set([uid for uid in unique_ids if uid is not None]))

                # 3. IF SPLIT/COMBINED RAIL BOARD PROFILE
                if len(items) > 1:
                    combo_key = "+".join(sorted([f'{l:.1f}' for l in clean_lengths]))
                    lbl_text = f"{size//12}' Board: {combo_key}\""

                    if combo_key not in color_map:
                        color_map[combo_key] = pair_colors[len(color_map) % len(pair_colors)]
                        self.pairing_data.append({'color': color_map[combo_key], 'text': lbl_text})
                    
                    clr = color_map[combo_key]
                    b['color'] = clr
                    
                    for rid in unique_ids:
                        self.rail_colors[rid] = clr

                    if unique_ids:
                        # If 1 rail was split into 3 pieces on 1 board, qty is 1.
                        # Otherwise, calculate based on total boards generated for this pairing.
                        self.draw_pair_links(unique_ids, clr, size / 12, is_single_split, qty=board_qty)

                # 4. IF SINGLE FULL MATERIAL CUT
                else:
                    if size == 96: clr = "#4CAF50"
                    elif size == 120: clr = "#2196F3"
                    elif size == 144: clr = "#FFEB3B"
                    else: clr = "#9E9E9E"
                    
                    b['color'] = clr
                    for rid in unique_ids:
                        self.rail_colors[rid] = clr
                    
                    if unique_ids:
                        # Single full-length rail runs need 3 boards to construct the 3 handrail height tiers
                        self.draw_pair_links(unique_ids, clr, size / 12, is_single_split, qty=board_qty)


            # 5. Cache variables for downstream print/export structures
            self.last_rail_boards = self.boards
            self.last_rail_colors = self.rail_colors
            self.last_rail_pairing_data = self.pairing_data

            return self.boards, self.rail_colors, self.pairing_data
        # --------------------------------------------

        # Otherwise, run your normal, automated optimizer algorithm below:
        """Processes rails and forces the visual colors to match the legend exactly."""
        all_segments = []
        rail_info = {}
        print ("Calc Rail")
        # 1. Gather visual rails
        for item in self.rail_canvas.find_withtag("draggable_rail"):
            c = self.rail_canvas.coords(item)
            #print (c)
            # Get the tags for this specific rail
            tags = self.rail_canvas.gettags(item)
            # Calculate the base horizontal length
            base_length = math.sqrt((c[2]-c[0])**2 + (c[3]-c[1])**2) / self.scale
            
            # Check the tags for the p_type
            if "STEP" in tags:
                actual_inches = base_length * 1.225
            else:
                actual_inches = base_length
                
            length_in = math.ceil(actual_inches)
            for i in range(1):#changed to be single and adjust for third of board below
                all_segments.append({'id': item, 'len': length_in,'rail':tags[2], 'section':tags[4]})

        all_segments.sort(key=lambda x: x['len'], reverse=True)

        standard_lengths = [96, 120, 144]
        self.boards = [] 
        
        for seg in all_segments:
            boardsleft = 3
            #print (seg)
            #first see if it's close to an 8 or 10' length already
            if seg['len'] >= 84 and seg['len'] <= 96:
                for ib in range(boardsleft):
                    self.boards.append({'size': 96, 'used': seg['len'], 'items': [seg],'openbo': 0})
                boardsleft = 0
            elif seg['len'] >= 108 and seg['len'] <= 120:
                for ib in range(boardsleft):
                    self.boards.append({'size': 120, 'used': seg['len'], 'items': [seg],'openbo': 0})
                boardsleft = 0
            #if not then see if it can pair with something else well either as is or if bumped from 8 to 10
            tryboard = 0
            while boardsleft > 0 and tryboard < 3:
                for b in self.boards:
                    #print (b)
                    if b['used'] + seg['len'] <= b['size']-2 and len(b['items']) == 1 and boardsleft > 0 and b['openbo']==1:
                        b['items'].append(seg)
                        b['used'] += seg['len']
                        boardsleft = boardsleft-1
                    
                tryboard +=1

            #see if there are multiple rails per board in an option
            if boardsleft > 0 and seg['len']*boardsleft >= 84 and seg['len']*boardsleft <= 96:
                self.boards.append({'size': 96, 'used': seg['len']*boardsleft, 'items': [seg] * boardsleft,'openbo':1})
                boardsleft = 0
            elif boardsleft > 0 and seg['len']*boardsleft >= 108 and seg['len']*boardsleft <= 120:
                self.boards.append({'size': 120, 'used': seg['len']*boardsleft, 'items': [seg] * boardsleft, 'openbo':1})
                boardsleft = 0
            elif boardsleft > 0 and seg['len']*boardsleft >= 132 and seg['len']*boardsleft <= 144:
                self.boards.append({'size': 144, 'used': seg['len']*boardsleft, 'items': [seg] * boardsleft, 'openbo':1})
                boardsleft = 0

            tryboard = 0
            while boardsleft > 0 and tryboard < 3:
                for b in self.boards:
                    #see if we can bump it up and make it fit too
                    #try to bump up from 8 to 10
                    if b['used'] + seg['len'] <= b['size']+22 and len(b['items']) == 1 and b['size'] == 96 and boardsleft > 0 and b['openbo']==1:
                        b['items'].append(seg)
                        b['used'] += seg['len']
                        b['size'] = 120
                        boardsleft = boardsleft-1
                    elif seg['len'] < 50 and b['used'] + seg['len'] <= b['size']+46 and len(b['items']) == 1 and b['size'] == 96 and boardsleft > 0 and b['openbo']==1:
                        b['items'].append(seg)
                        b['used'] += seg['len']
                        b['size'] = 144
                        boardsleft = boardsleft-1
                    elif b['used'] + seg['len'] <= b['size']+22 and b['size'] == 120 and len(b['items']) == 1 and boardsleft > 0 and b['openbo']==1:
                        b['items'].append(seg)
                        b['used'] += seg['len']
                        b['size'] = 144
                        boardsleft = boardsleft-1
                tryboard +=1

            while boardsleft > 0:
                size = next((s for s in standard_lengths if s >= seg['len']), 144)
                #print ("Size")
                #print (size)
                self.boards.append({'size': size, 'used': seg['len'], 'items': [seg],'openbo':1})
                boardsleft-=1

        # 2. COLOR & LINKING LOGIC
        rail_colors = {}
        pairing_data = []
        pair_colors = ["#9C27B0", "#00BCD4","#FF9800", "#5035B1",  "#FF5722", "#795548"]
        color_map = {} 
        self.rail_canvas.delete("pair_link") # Clear old connection lines

        for b in self.boards:
            unique_ids = list(set(item['id'] for item in b['items']))
            is_single_split = (len(b['items']) > 1 and len(unique_ids) == 1)
            

            if len(b['items']) > 1:
                combo_key = "+".join(sorted([str(item['len']) for item in b['items']]))
                if combo_key not in color_map:
                    color = pair_colors[len(color_map) % len(pair_colors)]
                    color_map[combo_key] = color
                    pairing_data.append({'color': color, 'text': f"{b['size']//12}' Board: {combo_key}\""})
                
                clr = color_map[combo_key]
                for item in b['items']:
                    rail_colors[item['id']] = clr

                # Split boards (3 pieces cut from 1 stock board) = qty 1
                board_qty = 1 if is_single_split else b.get('qty', 1)
                self.draw_pair_links(unique_ids, clr, b['size']/12, is_single_split, qty=board_qty)
            
            else:
                rid = unique_ids[0]
                if rid not in rail_colors:
                    if b['size'] == 96: rail_colors[rid] = "#4CAF50"
                    elif b['size'] == 120: rail_colors[rid] = "#2196F3"
                    elif b['size'] == 144: rail_colors[rid] = "#FFEB3B"
                    else: rail_colors[rid] = "#9E9E9E"
                
                # Single un-split rail positions require 3 full stock boards
                board_qty = 3
                self.draw_pair_links(unique_ids, rail_colors[rid], b['size']/12, is_single_split, qty=board_qty)

        return self.boards, rail_colors, pairing_data

    def draw_pair_links(self, ids, color, board_length, is_split_board=False, qty=1):
        """Draws dashed lines and records the specific pair data for the PDF."""
        if not hasattr(self, 'rail_scrape_data'):
            self.rail_scrape_data = []
        
        if not hasattr(self, 'pair_label_positions'):
            self.pair_label_positions = {}

        print("Pair Links")
        centers = []
        rail_names = []
        persistent_keys = []
        
        for rid in ids:
            c = self.rail_canvas.coords(rid)

            rail_key = None
            
            # Inspect canvas tags to find structural name
            tags = self.rail_canvas.gettags(rid)
            for tag in tags:
                if tag.startswith("RailNum"):
                    rail_key = tag
                    break

            if not rail_key and hasattr(self, 'rail_assignments'):
                rail_key = self.rail_assignments.get(rid)

            if not c or len(c) < 4:
                if hasattr(self, 'loaded_plan_data') and 'rails' in self.loaded_plan_data:
                    rails_dict = self.loaded_plan_data['rails']
                    matched_coords = None
                    for k, rdata in rails_dict.items():
                        if str(rid) in k or (hasattr(self, 'current_id_to_key_map') and self.current_id_to_key_map.get(rid) == k):
                            matched_coords = rdata.get('canvas_coords')
                            rail_key = k
                            break
                    if matched_coords:
                        c = matched_coords
            
            # Calculate true center point
            if c and len(c) >= 4:
                all_x = c[0::2]
                all_y = c[1::2]
                center_x = sum(all_x) / len(all_x)
                center_y = sum(all_y) / len(all_y)
                centers.append((center_x, center_y))
            
            if rail_key:
                persistent_keys.append(str(rail_key))
            else:
                persistent_keys.append(str(rid))

            label_tag = next((t for t in tags if t.startswith("label_")), None)
            if label_tag:
                matching_items = self.rail_canvas.find_withtag(label_tag)
                text_found = False
                for item_id in matching_items:
                    if self.rail_canvas.type(item_id) == "text":
                        rail_names.append(self.rail_canvas.itemcget(item_id, "text"))
                        text_found = True
                        break
                if not text_found and rail_key:
                    rail_names.append(str(rail_key))
            elif rail_key:
                rail_names.append(str(rail_key))
                
        if not centers:
            return

        # Correctly pluralize "Board" vs "Boards" based strictly on quantity
        boardtext = "Board" if qty == 1 else "Boards"
        
        # Format string: (3) 8' Boards OR (1) 8' Board
        label_str = f"({qty}) {int(board_length)}' {boardtext}"
        
        # Build synchronized key
        pair_key = f"{'_'.join(sorted(persistent_keys))}_link"
        
        avg_x = sum(c[0] for c in centers) / len(centers)
        avg_y = sum(c[1] for c in centers) / len(centers)
        
        yofst = -12 if len(centers) > 1 else 12
        default_lx = avg_x
        default_ly = avg_y + yofst
        
        if pair_key in self.pair_label_positions:
            lx, ly = self.pair_label_positions[pair_key]
        else:
            lx, ly = default_lx, default_ly
            self.pair_label_positions[pair_key] = [lx, ly]

        lbl_tag = f"pair_lbl_{pair_key}"
        
        self.rail_canvas.delete(lbl_tag)
        for idx in range(len(centers)):
            self.rail_canvas.delete(f"pair_line_{pair_key}_{idx}")

        for idx, (rx, ry) in enumerate(centers):
            line_specific_tag = f"pair_line_{pair_key}_{idx}"
            self.rail_canvas.create_line(rx, ry, lx, ly, fill=color, dash=(4,4), width=2, tags=("pair_link", line_specific_tag))
        
        # --- NEW LABEL FORMAT: (qty) length' Board(s) ---
        label_str = f"({qty}) {int(board_length)}' {boardtext}"
        
        self.rail_canvas.create_text(
            lx, ly, text=label_str, 
            fill=color, font=("Arial", 10, "bold"), tags=("pair_link", lbl_tag)
        )

        self.rail_canvas.tag_bind(lbl_tag, "<ButtonPress-1>", lambda e, pk=pair_key: self.on_pair_label_start(e, pk))
        self.rail_canvas.tag_bind(lbl_tag, "<B1-Motion>", lambda e, pk=pair_key, cts=centers: self.on_pair_label_drag(e, pk, cts))

        pair_desc = " + ".join(rail_names) if len(rail_names) > 1 else "Single Rail"
        self.rail_scrape_data.append({
            "color": color.lower(),
            "length": f"({qty}) {int(board_length)}'",
            "desc": pair_desc
        })

    def on_pair_label_start(self, event, pair_key):
        """Initializes dragging data for a pairing label."""
        self._pair_label_drag_data = {
            "x": self.rail_canvas.canvasx(event.x),
            "y": self.rail_canvas.canvasy(event.y)
        }

    def on_pair_label_drag(self, event, pair_key, centers):
        """Moves the single label and dynamically updates all radiating connecting lines."""
        cx = self.rail_canvas.canvasx(event.x)
        cy = self.rail_canvas.canvasy(event.y)
        
        dx = cx - self._pair_label_drag_data["x"]
        dy = cy - self._pair_label_drag_data["y"]
        
        lbl_tag = f"pair_lbl_{pair_key}"
        
        # Shift text label position on canvas
        self.rail_canvas.move(lbl_tag, dx, dy)
        
        # Log new coordinates inside dictionary
        new_coords = self.rail_canvas.coords(lbl_tag)
        if new_coords:
            lx, ly = new_coords[0], new_coords[1]
            self.pair_label_positions[pair_key] = [lx, ly]
            print (f"New label location {lx}, {ly} for {pair_key}")

            # Dynamically update the endpoint for every line tracking this label
            for idx, (rx, ry) in enumerate(centers):
                line_specific_tag = f"pair_line_{pair_key}_{idx}"
                self.rail_canvas.coords(line_specific_tag, rx, ry, lx, ly)
                
        self._pair_label_drag_data["x"] = cx
        self._pair_label_drag_data["y"] = cy

    def draw_rail_segment(self, x1, y1, x2, y2, p_type, r_num, p_name, coords=None):
        """Draws rail and places label with collision detection to prevent overlap."""
        
        # Use stored polygon coordinates if available, otherwise fallback to bounding box
        if coords and len(coords) >= 6:
            poly_points = coords
            # Calculate length from start/end points in array
            px_len = math.sqrt((coords[2] - coords[0])**2 + (coords[3] - coords[1])**2)
            mx = (coords[0] + coords[2]) / 2
            my = (coords[1] + coords[3]) / 2
        else:
            poly_points = [x1, y1, x2, y1, x2, y2, x1, y2]
            px_len = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2

        actual_inches = px_len / self.scale
        
        # Apply the slope factor if it's a STEP
        if p_type == "STEP":
            actual_inches *= 1.225  # 22.5% increase for the diagonal run
            
        self.inch_val = math.ceil(actual_inches)
        
        # Draw the rail using the full coordinate list
        rid = self.rail_canvas.create_polygon(
            *poly_points,
            fill="#a0522d", outline="black", 
            tags=("draggable_rail", p_type, r_num, self.inch_val, p_name)
        )
        
        

        if self.manual_override_active:
            boardid = f"board_{r_num}"
            if not hasattr(self, 'boards'):
                self.boards = []
                
            board_exists = any(b.get('id') == boardid for b in self.boards)
            
            if not board_exists:
                itemdt = [{
                    'id': rid,
                    'len': self.inch_val,
                    'rail': r_num,
                    'section': p_name
                }]
                bsize = 96 if self.inch_val <= 96 else 120
                
                for ib in range(0, 3):
                    self.boards.append({
                        'id': boardid,
                        'size': bsize, 
                        'used': self.inch_val, 
                        'items': itemdt,
                        'openbo': 0
                    })
                    
        if r_num in self.rail_entries:
            self.rail_entries[r_num]['id'] = rid
        else:
            self.rail_entries[r_num] = {
                'id': rid,
                'canvas_coords': poly_points,
                'ptype': p_type,
                'pname': p_name,
                'rlen': self.inch_val,
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2
            }
        
        # Smart Label Offset
        is_horiz = abs(x2 - x1) > abs(y2 - y1) if (x1 is not None and x2 is not None) else True
        
        if is_horiz:
            target_y = my - 12
            overlap = self.rail_canvas.find_overlapping(mx - 10, target_y - 5, mx + 10, target_y + 5)
            oy = 12 if any("rail_label" in self.rail_canvas.gettags(o) for o in overlap) else -12
            ox = 0
        else:
            target_x = mx - 25
            overlap = self.rail_canvas.find_overlapping(target_x - 5, my - 5, target_x + 5, my + 5)
            ox = 25 if any("rail_label" in self.rail_canvas.gettags(o) for o in overlap) else -25
            oy = 0
        
        self.rail_canvas.create_text(
            mx + ox, my + oy, 
            text=f"{self.inch_val}\"", 
            fill="black", font=("Arial", 9, "bold"),
            tags=(f"length_label_{r_num}", "rail_label")
        )

        #self.bind_item(r_num)

    def debug_rails(self):
        print("\n--- CURRENT RAIL ENTRIES DATA ---")
        if not self.rail_entries:
            print("Dictionary is empty.")
            return

        for r_tag, r_data in self.rail_entries.items():
            #rint(f"Post ID: {p_tag}")
            # Extract values from StringVars
            deck = r_data.get('deck').get() if hasattr(r_data.get('deck'), 'get') else "N/A"
            grade = r_data.get('grade').get() if hasattr(r_data.get('grade'), 'get') else "N/A"
            total = r_data.get('total').get() if hasattr(r_data.get('total'), 'get') else "N/A"
            
            # Get coordinates
            c_coords = r_data.get('canvas_coords', [0,0,0,0])
            l_coords = r_data.get('label_coords', [0,0])
            print (r_tag)
            print (r_data)
        for b in self.boards:
            print (b)
            
        print("---------------------------------\n")
        #rint("\n--- UNIQUE BOARDS OUTPUT ---")
        seen_boards = set()
        for b in self.boards:
            # Convert dictionary to a string representation to make it hashable
            board_str = str(b)
            if board_str not in seen_boards:
                #rint(b)
                seen_boards.add(board_str)


    def update_delete_button_rail_visibility(self):
        print ("NEED TO UPDATE THIS delete visible")
        if self.active_rail_tag:
            # Show the button if something is selected
            self.delete_rail_btn.pack(side=tk.RIGHT, padx=20)
        else:
            # Hide the button if nothing is selected
            self.delete_rail_btn.pack_forget()


    def apply_manual_board_modifications(self, updated_boards):
        """Callback executed when the user saves their manual overrides layout window."""
        # Commit the manual modifications to your state variables
        self.manual_override_active = True

        self.boards = updated_boards
        self.last_rail_boards = updated_boards 
        
        # Re-run your exact drawing pipeline with manual override enabled
        self.rail_combined_materialColor(manual_override=True)
        
        # --- FIX: Forward those captured values into the drawing visual method ---
        self.draw_legend_and_tables(
            self.last_rail_boards, 
            self.last_rail_colors, 
            self.last_rail_pairing_data
        )
        #messagebox.showinfo("Success", "Manual board layout customizations applied successfully!")
    def draw_legend_and_tables(self, boards, rail_colors, pairing_data):
        """Draws the summary with a cleaner visual layout."""
        self.rail_sidebar.delete("all")
        # This stores the math you just did into a variable the PDF can see
        self.rail_final_totals = boards

        y = 20
        margin_x = 15
        
        # Header: Supplies
        self.rail_sidebar.create_text(margin_x, y, text="SUPPLIES REQUIRED", anchor="w", font=("Arial", 10, "bold"))
        y += 25
        
        counts = {96: 0, 120: 0, 144: 0}
        for b in boards: 
            counts[b['size']] += 1
        
        for length in [96, 120, 144]:
            self.rail_sidebar.create_text(margin_x, y, text=f"2x4x{length//12}':", anchor="w", font=("Arial", 10))
            self.rail_sidebar.create_text(margin_x + 90, y, text=f"{counts[length]}", anchor="w", font=("Arial", 10, "bold"))
            y += 20

        # Header: Pairing Key
        y += 20
        self.rail_sidebar.create_text(margin_x, y, text="COLOR KEY / PAIRINGS", anchor="w", font=("Arial", 10, "bold"))
        y += 25
        
        # Single board indicators
        for c, t in [("#4CAF50", "Solo 8' Board"), ("#2196F3", "Solo 10' Board")]:
            self.rail_sidebar.create_rectangle(margin_x, y - 6, margin_x + 15, y + 9, fill=c, outline="black")
            self.rail_sidebar.create_text(margin_x + 22, y, text=t, anchor="w", font=("Arial", 9))
            y += 22

        # Pair indicators
        for pair in pairing_data:
            self.rail_sidebar.create_rectangle(margin_x, y - 6, margin_x + 15, y + 9, fill=pair['color'], outline="black")
            self.rail_sidebar.create_text(margin_x + 22, y, text=pair['text'], anchor="w", font=("Arial", 9))
            y += 22


    def delete_selected_rail(self):
        if not hasattr(self, 'active_rail_tag') or not self.active_rail_tag:
            return

        target_tag = self.active_rail_tag
        print(f"Deleting Rail: {target_tag}")

        # 1. Visual Removal from Canvas
        self.rail_canvas.delete(target_tag)
        self.rail_canvas.delete(f"label_{target_tag}")        # Deletes spawned/name labels
        self.rail_canvas.delete(f"length_label_{target_tag}") # Deletes generated length labels (e.g. 91")
        self.rail_canvas.delete("pair_link")                  # Clear pair links

        # 2. Data Removal from rail_entries
        if hasattr(self, 'rail_entries') and target_tag in self.rail_entries:
            self.rail_entries.pop(target_tag, None)
            #rint(f"Successfully popped {target_tag} from self.rail_entries.")

        # 3. Handle Manual Override Sync
        if getattr(self, 'manual_override_active', False) and hasattr(self, 'boards'):
            updated_boards = []
            for board in self.boards:
                filtered_items = [item for item in board.get('items', []) if item.get('rail') != target_tag]
                if filtered_items:
                    board['items'] = filtered_items
                    updated_boards.append(board)
            
            self.boards = updated_boards
            self.last_rail_boards = updated_boards

        # 4. Clear Selection Variable State
        self.active_rail_tag = None
        self.active_tag = None

        # 5. Safe Recalculation & UI Redraw
        is_manual = getattr(self, 'manual_override_active', False)
        self.rail_combined_materialColor(manual_override=is_manual)


    def on_rail_drag_start(self, event):
        print ("This is the rail drag start")
        canvas_x = self.rail_canvas.canvasx(event.x)
        canvas_y = self.rail_canvas.canvasy(event.y)
        item_ids = self.rail_canvas.find_closest(canvas_x, canvas_y)
        if not item_ids: return
        
        clicked_id = item_ids[0]
        tags = self.rail_canvas.gettags(clicked_id)
        if not tags: return

        # Make sure we clicked a rail or its length label
        if "draggable_rail" in tags or "rail_label" in tags or any(t.startswith("RailNum") for t in tags):
            
            # Extract the RailNum string tag for state tracking
            rail_tag = next((t for t in tags if t.startswith("RailNum") or t.startswith("length_label_RailNum")), None)
            if rail_tag and rail_tag.startswith("length_label_"):
                rail_tag = rail_tag.replace("length_label_", "")

            if not rail_tag:
                return

            self.active_rail_tag = rail_tag
            self.active_tag = rail_tag
            
            self.rail_canvas.focus_set()
            self.update_delete_button_rail_visibility()

            # Reset all rail outlines
            self.rail_canvas.itemconfig("draggable_rail", outline="black", width=1)
            
            # Highlight the selected rail tag
            self.rail_canvas.itemconfig(rail_tag, outline="#007bff", width=3)

            # Store BOTH the string tag AND the specific rail tag for moving
            self._rail_drag_data["item"] = rail_tag
            self._rail_drag_data["x"] = canvas_x
            self._rail_drag_data["y"] = canvas_y

    def on_rail_drag(self, event):
        canvas_x = self.rail_canvas.canvasx(event.x)
        canvas_y = self.rail_canvas.canvasy(event.y)
        rail_tag = self._rail_drag_data.get("item")
        if not rail_tag: return
        
        dx = canvas_x - self._rail_drag_data["x"]
        dy = canvas_y - self._rail_drag_data["y"]
        
        # Move the rail polygon AND its corresponding length label tag together
        self.rail_canvas.move(rail_tag, dx, dy)
        self.rail_canvas.move(f"length_label_{rail_tag}", dx, dy)
        
        self._rail_drag_data["x"] = canvas_x
        self._rail_drag_data["y"] = canvas_y


    def debug_canvas_click(self, event):
        cx = self.rail_canvas.canvasx(event.x)
        cy = self.rail_canvas.canvasy(event.y)
        
        closest = self.rail_canvas.find_closest(cx, cy)
        overlapping = self.rail_canvas.find_overlapping(cx - 2, cy - 2, cx + 2, cy + 2)
        
        print("\n================ CLICK DEBUG ================")
        print(f"Mouse Clicked At Canvas Coords: ({cx}, {cy})")
        print(f"find_closest Item ID: {closest}")
        
        if closest:
            c_id = closest[0]
            print(f"  -> Type: {self.rail_canvas.type(c_id)}")
            print(f"  -> Tags: {self.rail_canvas.gettags(c_id)}")
            print(f"  -> Coords: {self.rail_canvas.coords(c_id)}")
            
        print(f"find_overlapping Item IDs: {overlapping}")
        for item_id in overlapping:
            print(f"  -> ID {item_id} | Type: {self.rail_canvas.type(item_id)} | Tags: {self.rail_canvas.gettags(item_id)}")
        print("=============================================\n")
                    
    def on_rail_drag_stop(self, event):
        print("Rail Drag Stop")
        item = self._rail_drag_data.get("item")
        if not item: return

        # --- FIX: Get the actual updated coordinates directly from the canvas shape ---
        updated_coords = self.rail_canvas.coords(item)
        
        if item in self.rail_entries and updated_coords:
            # Save exact polygon points in memory so rotation works cleanly
            self.rail_entries[item]['canvas_coords'] = updated_coords
            self.rail_entries[item]['points'] = updated_coords

        self.rail_combined_materialColor()
        self.rail_canvas.focus_set()

        self.rail_canvas.configure(scrollregion=self.rail_canvas.bbox("all"))

    def create_reference_point(self, x, y):
        tag = "REF_POINT"
        
        # Define all 4 corner coordinates explicitly: [x1, y1, x2, y1, x2, y2, x1, y2]
        poly_points = [
            x, y,          # Top-Left
            x + 350, y,    # Top-Right
            x + 350, y + 30, # Bottom-Right
            x, y + 30      # Bottom-Left
        ]

        # Draw as polygon using full 8-coordinate array
        self.canvas.create_polygon(
            poly_points, 
            fill="", 
            outline="black", 
            dash=(4, 2), 
            tags=(tag, "REF_POINT", "shape")
        )
        
        self.canvas.create_text(
            x + 175, y + 15, 
            text="Reference Surface", 
            font=("Arial", 9, "bold"), 
            tags=(tag, "text")
        )
        
        self.bind_item(tag)
        
        # Store full coordinate array alongside bounding points
        self.sections[tag] = {
            "name": tag, 
            "color": "black",
            "l": 30, 
            "w": 350,
            "x1": x, 
            "y1": y,
            "x2": x + 350,
            "y2": y + 30,
            "points": poly_points
        }

    def spawn_comment_box(self, target_canvas):
        """Creates an adjustable and editable text comment box on the active canvas."""
        text_content = sd.askstring("New Comment", "Enter your text comment:")
        if not text_content or not text_content.strip(): return
        
        # Determine unique id token strings matching existing project patterns
        box_idx = len(self.comment_boxes)
        box_id = f"comment_{box_idx}"
        
        # Starting metrics matching internal coordinate offsets
        cx, cy, cw, ch = 200, 200, 150, 60
        
        # Save tracking attributes internally
        self.comment_boxes[box_id] = {
            'text': text_content, 'x': cx, 'y': cy, 'w': cw, 'h': ch, 'canvas_ref': target_canvas
        }
        
        self.render_comment_box_ui(box_id)

    def render_comment_box_ui(self, box_id):
        """Draws or redraws the vector pieces belonging to a comment box."""
        b_data = self.comment_boxes[box_id]
        canvas = b_data['canvas_ref']
        
        # Wipe old iterations of this tag bundle if renewing layout bounds
        canvas.delete(box_id)
        
        cx, cy, cw, ch = b_data['x'], b_data['y'], b_data['w'], b_data['h']
        
        # Border box
        canvas.create_rectangle(
            cx, cy, cx + cw, cy + ch, 
            fill="#FFFDE7", outline="#F9CC5A", width=2, 
            tags=(box_id, "comment_rect")
        )
        
        # Main text value block
        canvas.create_text(
            cx + 6, cy + 6, text=b_data['text'], 
            font=("Arial", 11), fill="#000000", anchor="nw", width=cw-12,
            tags=(box_id, "comment_text")
        )
        
        # Interactive Resize Handle node placed at bottom right corner
        canvas.create_rectangle(
            cx + cw - 8, cy + ch - 8, cx + cw, cy + ch, 
            fill="#F9DA8C", outline="", 
            tags=(box_id, "comment_resize_handle")
        )
        
        # Context bindings for text-box interaction layers
        canvas.tag_bind(box_id, "<ButtonPress-1>", lambda e, bid=box_id: self.on_comment_press(e, bid))
        canvas.tag_bind(box_id, "<B1-Motion>", self.on_comment_drag)
        canvas.tag_bind(box_id, "<ButtonRelease-1>", self.on_comment_release)
        canvas.tag_bind(box_id, "<Double-Button-1>", lambda e, bid=box_id: self.edit_comment_text(bid))
        canvas.tag_bind(box_id, "<Button-3>", lambda e, bid=box_id: self.prompt_delete_comment(bid))


    def on_comment_press(self, event, box_id):
        """Records anchor metrics using persistent hard references to prevent drag drops."""
        canvas = self.comment_boxes[box_id]['canvas_ref']
        
        # Translate viewport metrics to absolute canvas space coordinates
        cx = canvas.canvasx(event.x)
        cy = canvas.canvasy(event.y)
        
        # Find exactly what sub-element tag was clicked
        current_tags = canvas.gettags(canvas.find_withtag("current")[0])
        
        mode = "move"
        if "comment_resize_handle" in current_tags:
            mode = "resize"
            
        self._comment_drag_data["item"] = box_id
        self._comment_drag_data["x"] = cx
        self._comment_drag_data["y"] = cy
        self._comment_drag_data["mode"] = mode

    def on_comment_drag(self, event):
        box_id = self._comment_drag_data["item"]
        if not box_id: return
        
        b_data = self.comment_boxes[box_id]
        canvas = b_data['canvas_ref']
        
        # Calculate true delta shifts in absolute coordinate spaces
        cx = canvas.canvasx(event.x)
        cy = canvas.canvasy(event.y)
        
        dx = cx - self._comment_drag_data["x"]
        dy = cy - self._comment_drag_data["y"]
        
        if self._comment_drag_data["mode"] == "move":
            b_data['x'] += dx
            b_data['y'] += dy
            # Smoothly move everything matching this box tag sequence globally
            canvas.move(box_id, dx, dy)
            
        elif self._comment_drag_data["mode"] == "resize":
            b_data['w'] = max(40, b_data['w'] + dx)
            b_data['h'] = max(30, b_data['h'] + dy)
            
            # Update geometries of existing structural components dynamically
            bx, by, bw, bh = b_data['x'], b_data['y'], b_data['w'], b_data['h']
            
            # Resize outer yellow frame
            for rect in canvas.find_withtag(f"{box_id} && comment_rect"):
                canvas.coords(rect, bx, by, bx + bw, by + bh)
                
            # Readjust boundaries of multi-line text blocks
            for txt in canvas.find_withtag(f"{box_id} && comment_text"):
                canvas.coords(txt, bx + 6, by + 6)
                canvas.itemconfig(txt, width=bw - 12)
                
            # Reposition resize node to lock onto bottom right corner
            for handle in canvas.find_withtag(f"{box_id} && comment_resize_handle"):
                canvas.coords(handle, bx + bw - 8, by + bh - 8, bx + bw, by + bh)
            
        # Update relative drag anchors safely
        self._comment_drag_data["x"] = cx
        self._comment_drag_data["y"] = cy

    def on_comment_release(self, event):
        """Cleans dragging stacks explicitly on mouse release loops."""
        self._comment_drag_data = {"item": None, "x": 0, "y": 0, "mode": "move"}

    def edit_comment_text(self, box_id):
        """Triggers string request popups to rewrite active values."""
        old_txt = self.comment_boxes[box_id]['text']
        new_txt = sd.askstring("Edit Comment", "Update your comment text:", initialvalue=old_txt)
        # If user clicked Cancel, make no changes
        if new_txt is None: 
            return
            
        # --- UPDATE: If user cleared the text completely, delete the comment box ---
        if not new_txt.strip():
            canvas = self.comment_boxes[box_id]['canvas_ref']
            canvas.delete(box_id)          # Remove vector elements from the GUI
            del self.comment_boxes[box_id]  # Remove from application tracking data
            return
            
        # Otherwise, save the updated text string and refresh the layout
        self.comment_boxes[box_id]['text'] = new_txt.strip()
        self.render_comment_box_ui(box_id)

    def prompt_delete_comment(self, box_id):
        """Allows right-click context cleanup blocks."""
        ans = messagebox.askyesno("Delete Comment", "Do you want to delete this comment box?")
        if ans:
            canvas = self.comment_boxes[box_id]['canvas_ref']
            canvas.delete(box_id)
            del self.comment_boxes[box_id]

            
    def open_pairing_editor(self):
        """Launches a modal top-level editor to customize rail groupings visually."""
        if not hasattr(self, 'boards') or not self.boards:
            messagebox.showwarning("No Data", "Please calculate materials first to generate the initial board list.")
            return
        
        # Open our manual overrides window frame
        RailPairingEditorWindow(self, self.boards, self.apply_manual_board_modifications)

        
def check_for_updates():
    CURRENT_VERSION = "8.9" \
    # A link to a raw text file on your GitHub repository containing just the version number (e.g., "4.2")
    VERSION_URL = "https://raw.githubusercontent.com/kbritrx007/RampBuilder/main/version.txt"
    # The link where they can download the latest installer or executable
    DOWNLOAD_URL = "https://github.com/kbritrx007/RampBuilder/releases/latest"
    
    #Write your new code, and change your internal script variable to CURRENT_VERSION = "4.2".
    #archive the files in RampBuilder folder so new creation doesn't have issues 
    #open terminal
    # cd ~/RampBuilder
    #Compile the new file using PyInstaller: python3 -m PyInstaller --onefile --windowed RampBuilder_v7_7.py
    #Go to GitHub, click Releases, draft a New Release, tag it v4.2, and drop your new executable from the Dist folder inside.
    #Go to your version.txt file on GitHub, edit it to say 4.2, and save.
    #for windows you drop the 3 so save the file to the desktop then in terminal do the following
    #cd Desktop
    #python -m PyInstaller --onefile --windowed RampBuilder_v7_7.py
    #load to github with _Win tag
    
    try:
        # Set a short timeout (2 seconds) so if they are offline, the app doesn't hang on startup
        with urllib.request.urlopen(VERSION_URL, timeout=2) as response:
            latest_version = response.read().decode('utf-8').strip()

        print (latest_version)    
        if latest_version != CURRENT_VERSION:
            # Prompt the user to update
            ans = messagebox.askyesno(
                "Update Available", 
                f"A new version of Ramp Architect Pro ({latest_version}) is available.\n"
                f"You are currently running v{CURRENT_VERSION}.\n\n"
                "Would you like to go to the download page now?"
            )
            if ans:
                webbrowser.open(DOWNLOAD_URL)
        else:
            print ("Running current version")
    except Exception:
        # If offline or GitHub is down, silently fail and let the user work normally
        print ("Version check not completed")
        pass

class RailPairingEditorWindow(tk.Toplevel):
    def __init__(self, parent, current_boards, save_callback):
        super().__init__(parent.root)
        self.title("Manual Nesting Optimization Override")
        self.geometry("1100x750")
        self.transient(parent.root)
        self.grab_set()
        
        self.parent = parent
        self.save_callback = save_callback
        
        # Group identical boards together visually (since they exist in triplicates)
        self.board_groups = self.compress_boards_into_visual_groups(current_boards)
        
        self.selected_item = None
        self.drag_data = {"x": 0, "y": 0, "board_idx": None, "item_idx": None}
        
        self.init_ui()
        self.draw_layout()

    def compress_boards_into_visual_groups(self, raw_boards):
        """Groups raw board triplicates visually into unique slots so users modify 3 rows at once."""
        groups = []
        for board in raw_boards:
            matched = False
            for g in groups:
                if g['size'] == board['size'] and str(g['items']) == str(board['items']):
                    g['multiplier'] += 1
                    matched = True
                    break
            if not matched:
                groups.append({
                    'size': board['size'],
                    'used': board['used'],
                    'items': json.loads(json.dumps(board['items'])), # deep copy structure
                    'multiplier': 1
                })
        return groups

    def decompress_visual_groups(self):
        """Converts visual groups back into individual triplicate boards for the main app loop."""
        raw_boards = []
        for group in self.board_groups:
            for _ in range(group['multiplier']):
                raw_boards.append({
                    'size': group['size'],
                    'used': group['used'],
                    'items': json.loads(json.dumps(group['items'])),
                    'multiplier': group['multiplier'],
                    'openbo': 1 if len(group['items']) < 2 else 0
                })
        return raw_boards

    def init_ui(self):
        # Upper Command Strip Frame
        controls = tk.Frame(self, bg="#2c3e50", pady=10)
        controls.pack(side=tk.TOP, fill=tk.X)
        
        lbl = tk.Label(controls, text="Drag & Drop segments to mix layouts. Click buttons to isolate stacks or add blank lumber.", 
                       fg="white", bg="#2c3e50", font=("Arial", 10, "italic"))
        lbl.pack(side=tk.LEFT, padx=15)

        tk.Button(controls, text="Save & Sync Layout", command=self.save_and_exit, 
                  bg="#2ecc71", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=15)
        
        # Canvas workspace with scrollbars
        frame = tk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(frame, bg="#f5f6fa")
        v_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=v_scroll.set)
        
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Interactive UI Interaction Mouse Triggers
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_drop)

    def draw_layout(self):
        self.canvas.delete("all")
        
        if hasattr(self, '_inline_buttons'):
            for btn in self._inline_buttons:
                btn.destroy()
        self._inline_buttons = []
        
        scale = 6 
        y = 40
        ysc = 40
        xst = 170

        for b_idx, board in enumerate(self.board_groups):
            bw = board['size'] * scale
            # Drawing the background track bounding boxes
            self.canvas.create_rectangle(xst, y, xst + bw, y + ysc, fill="#dcdde1", outline="#7f8c8d", width=2, tags=f"board_{b_idx}")
            
            lbl_text = f"Group x{board['multiplier']}\nSize: {board['size']//12}' ({board['size']}\")\nUsed: {board['used']}\""
            self.canvas.create_text(15, y + int(ysc/2), text=lbl_text, anchor="w", font=("Arial", 9, "bold"), fill="#2c3e50")
            
            # Non-overlapping stacked configurations
            if board['multiplier'] > 1:
                split_btn = tk.Button(
                    self.canvas, text="Split 1", bg="#e74c3c", fg="white", font=("Arial", 8, "bold"),
                    padx=2, pady=0, command=lambda idx=b_idx: self.split_board_by_index(idx)
                )
                self.canvas.create_window(125, y + 10, window=split_btn, anchor="c")
                self._inline_buttons.append(split_btn)
                
            if board['multiplier'] == 1 and len(board['items']) > 1:
                explode_btn = tk.Button(
                    self.canvas, text="Distribute x3", bg="#3498db", fg="white", font=("Arial", 8, "bold"),
                    padx=2, pady=0, command=lambda idx=b_idx: self.explode_board_to_triplicates(idx)
                )
                self.canvas.create_window(120, y + ysc-9, window=explode_btn, anchor="c")
                self._inline_buttons.append(explode_btn)
            
            x_offset = xst
            for i_idx, item in enumerate(board['items']):
                iw = item['len'] * scale
                bg_color = "#2980b9" if "RAMP" in str(item.get('section','')).upper() else "#27ae60"
                
                seg = self.canvas.create_rectangle(
                    x_offset + 2, y + 5, x_offset + iw - 2, y + ysc-5, 
                    fill=bg_color, outline="white", width=1,
                    tags=("segment", f"b_{b_idx}", f"i_{i_idx}")
                )
                
                # Get user-friendly section name instead of the raw object ID
                section_display = self.get_friendly_section_name(item.get('section', ''))
                
                txt = f"{item['rail']}\n{item['len']}\" ({section_display})"
                self.canvas.create_text(
                    x_offset + (iw/2), y + int(ysc/2), text=txt, 
                    justify="center", fill="white", font=("Arial", 8, "bold"),
                    tags=("segment", f"b_{b_idx}", f"i_{i_idx}")
                )
                x_offset += iw
                
            y += 55
            
        # Distinct empty placeholder slot at the bottom row track
        self.canvas.create_rectangle(xst, y, xst + (96 * scale), y + ysc, 
                                     fill="#f5f6fa", outline="#bdc3c7", dash=(4, 4), width=2, tags="empty_drop_zone")
        self.canvas.create_text(15, y + int(ysc/2), text="[ New Board Target ]\nDrop item here to\nisolate grouping", 
                                anchor="center", font=("Arial", 9, "italic"), fill="#7f8c8d")
        
        y += 55
        self.canvas.configure(scrollregion=(0, 0, 1100, y + 100))

    def on_click(self, event):
        item = self.canvas.find_withtag("current")
        if item:
            tags = self.canvas.gettags(item[0])
            if "segment" in tags:
                b_idx = int([t for t in tags if t.startswith("b_")][0].split("_")[1])
                i_idx = int([t for t in tags if t.startswith("i_")][0].split("_")[1])
                
                self.selected_item = item[0]
                self.drag_data = {"x": event.x, "y": event.y, "board_idx": b_idx, "item_idx": i_idx}

    def on_drag(self, event):
        if self.selected_item:
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            
            tags = self.canvas.gettags(self.selected_item)
            b_tag = [t for t in tags if t.startswith("b_")][0]
            i_tag = [t for t in tags if t.startswith("i_")][0]
            
            for item_id in self.canvas.find_withtag(b_tag):
                if i_tag in self.canvas.gettags(item_id):
                    self.canvas.move(item_id, dx, dy)
                    
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def on_drop(self, event):
        if not self.selected_item:
            return
            
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        dropped_on = self.canvas.find_overlapping(cx, cy, cx + 1, cy + 1)
        target_board_idx = None
        dropped_on_empty_zone = False
        
        for obj in dropped_on:
            tags = self.canvas.gettags(obj)
            if "empty_drop_zone" in tags:
                dropped_on_empty_zone = True
                break
            for t in tags:
                if t.startswith("board_"):
                    target_board_idx = int(t.split("_")[1])
                    break
                    
        src_b_idx = self.drag_data["board_idx"]
        src_i_idx = self.drag_data["item_idx"]
        src_multiplier = self.board_groups[src_b_idx]['multiplier']
        
        # CASE A: Explicitly dropped in the blank board target slot row
        if dropped_on_empty_zone:
            moving_item = self.board_groups[src_b_idx]['items'].pop(src_i_idx)
            new_board_slot = {
                'size': 96,
                'used': moving_item['len'],
                'items': [moving_item],
                'multiplier': src_multiplier
            }
            self.board_groups.append(new_board_slot)
            self.compress_and_refresh_visuals()
            
        # CASE B: Dropped inside an existing stock board bar track row
        elif target_board_idx is not None and target_board_idx != src_b_idx:
            dest_board = self.board_groups[target_board_idx]
            dest_multiplier = dest_board['multiplier']
            
            # --- RULE 1: Group multipliers must match exactly ---
            if src_multiplier != dest_multiplier:
                messagebox.showwarning(
                    "Mismatched Grouping", 
                    f"Cannot combine items with different row counts!\n\n"
                    f"Source: Group x{src_multiplier}\n"
                    f"Destination: Group x{dest_multiplier}\n\n"
                    f"Use 'Split 1' or 'Distribute x3' first to match groupings."
                )
                self.draw_layout()
                self.selected_item = None
                return
                
            # --- NEW RULE 2: Combined length must not exceed maximum lumber length (144") ---
            moving_item = self.board_groups[src_b_idx]['items'][src_i_idx]
            current_dest_len = sum(item['len'] for item in dest_board['items'])
            potential_total_len = current_dest_len + moving_item['len']
            
            if potential_total_len > 144:
                messagebox.showerror(
                    "Over-Allocation Error", 
                    f"Cannot complete drop! Combining these items requires a length of {potential_total_len}\".\n\n"
                    f"The absolute maximum allowable length for standard stock boards is 12' (144\")."
                )
                self.draw_layout() # Snaps the segment back to its starting row
                self.selected_item = None
                return
                
            # If both validation checks pass, execute the relocation mutation safely
            moving_item = self.board_groups[src_b_idx]['items'].pop(src_i_idx)
            self.board_groups[target_board_idx]['items'].append(moving_item)
            self.compress_and_refresh_visuals()
            
        else:
            # Fallback refresh if drop missed geometry targets completely
            self.draw_layout()
            
        self.selected_item = None

    def split_board_by_index(self, b_idx):
        """Isolates a single board row out of a visual triplicate stack using an on-screen button."""
        group = self.board_groups[b_idx]
        if group['multiplier'] > 1:
            group['multiplier'] -= 1
            isolated_copy = {
                'size': group['size'],
                'used': group['used'],
                'items': json.loads(json.dumps(group['items'])),
                'multiplier': 1
            }
            self.board_groups.insert(b_idx + 1, isolated_copy)
            self.draw_layout()
            #messagebox.showinfo("Split Successful", "Isolated 1 board row from the group tracker for independent editing.")

    def explode_board_to_triplicates(self, b_idx):
        """Splits a single multi-item board into separate individual boards."""
        group = self.board_groups[b_idx]
        items_to_distribute = list(group['items'])
        
        if len(items_to_distribute) < 2:
            return
            
        self.board_groups.pop(b_idx)
        
        for item in items_to_distribute:
            new_board = {
                'size': 96,
                'used': item['len'],
                'items': [item],
                'multiplier': 1
            }
            self.board_groups.insert(b_idx, new_board)
            
        self.compress_and_refresh_visuals()

    def recalculate_board_capacities(self):
        """Automatically updates used capacity and resizes stock to the shortest fit (8', 10', 12')."""
        standard_stock_cutoffs = [96, 120, 144]
        
        for group in self.board_groups:
            total_cuts_len = sum(item['len'] for item in group['items'])
            group['used'] = total_cuts_len
            
            assigned_size = 144
            for stock_size in standard_stock_cutoffs:
                if total_cuts_len <= stock_size:
                    assigned_size = stock_size
                    break
            group['size'] = assigned_size
            
        self.board_groups = [g for g in self.board_groups if len(g['items']) > 0]

    def compress_and_refresh_visuals(self):
        """Re-bundles matching row footprints into unified Group rows to keep things clean."""
        compressed = []
        for board in self.board_groups:
            matched = False
            for c in compressed:
                if c['size'] == board['size'] and str(c['items']) == str(board['items']):
                    c['multiplier'] += board['multiplier']
                    matched = True
                    break
            if not matched:
                compressed.append(board)
                
        self.board_groups = compressed
        self.recalculate_board_capacities()
        self.draw_layout()

    def save_and_exit(self):
        for group in self.board_groups:
            if group['used'] > group['size']:
                messagebox.showerror("Nesting Error", f"Over-allocation detected! Items total {group['used']}\" on a {group['size']}\" board track profile.")
                return
                
        flattened_boards = self.decompress_visual_groups()
        self.save_callback(flattened_boards)
        self.destroy()

    def get_friendly_section_name(self, raw_section):
        """Translates section tags (or widget strings) into clean user-visible names like 'Deck 1'."""
        if not raw_section:
            return ""

        raw_str = str(raw_section).strip()

        # 1. Lookup in parent.sections dictionary
        if hasattr(self.parent, "sections"):
            # Direct match in sections dict
            if raw_str in self.parent.sections:
                sec_data = self.parent.sections[raw_str]
                sec_name = sec_data.get('name') or sec_data.get('label') or sec_data.get('p_type')
                if sec_name:
                    return str(sec_name).replace("_", " ").title()

            # Partial key match (if tag contains extra suffixes)
            for sec_key, sec_data in self.parent.sections.items():
                if sec_key in raw_str or raw_str in sec_key:
                    sec_name = sec_data.get('name') or sec_data.get('label') or sec_data.get('p_type')
                    if sec_name:
                        return str(sec_name).replace("_", " ").title()

        # 2. Fallback: If raw_str is a Tkinter widget string like '.!notebook.!frame5...'
        if raw_str.startswith("."):
            try:
                widget = self.nametowidget(raw_str)
                txt = widget.cget("text")
                if txt:
                    return str(txt).replace("_", " ").title()
            except Exception:
                pass

        # 3. Clean up raw fallback string if nothing matched
        cleaned = raw_str.replace("obj_", "").split("_")[0]
        return cleaned.title()

if __name__ == "__main__":
    root = tk.Tk(); app = RampArchitect(root); root.mainloop()