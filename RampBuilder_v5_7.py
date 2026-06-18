#General Functions
#-----------------------------------------------

#update the taper ramps for the image on the threshold vs the taper and the joist profiles
#update material selection on taper ramp for thickness based on height

#adjust total drop for slope on taper ramps vs default 5 degree



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
from tkinter import ttk
import math
import json
from tkinter import filedialog, messagebox
import tkinter.simpledialog as sd

import json
import webbrowser
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

import urllib.request
import webbrowser
from tkinter import messagebox

class RampArchitect:
    def __init__(self, root):
        self.root = root
        self.root.title("Ramp Builder v5.7")
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

        self.create_reference_point(600, 100)
        tk.Label(self.root, text="Total Drop (in):").pack(side="left", padx=5)
        self.total_drop_entry = tk.Entry(self.root, width=10)
        self.total_drop_entry.pack(side="left", padx=5)

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
                    
                    post_rows_html += f"""
                    <tr>
                        <td><strong>{p_tag}</strong></td>
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
        overall_layout_svg = self._canvas_to_svg(self.canvas)
        post_map_svg = self._canvas_to_svg(self.post_canvas)
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
                            <td>{row[2]}</td>
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
            .sub-tables-grid {{ flex-direction: row; }}
            .pairings-column {{ flex-direction: column; }}
            .materials-sub-row {{ flex-direction: row; }}
            .page-break {{ page-break-before: always; }}
            .svg-card, .data-card, .component-table-container {{ page-break-inside: avoid; box-shadow: none; margin-bottom: 10px; }}
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

        <div class="svg-card" style="page-break-before: always;">
            <div class="header" style="margin-bottom:0; padding-bottom:0; border-bottom:none;">Handrail Detail</div>
            <div class="svg-container">{handrail_detail_svg}</div>
        </div>
        
        {rail_data_logs}

    </div>

    {component_pages_html}

    {materials_matrix_html}

    {miscellaneous_html}
</body>
</html>"""
        return html_document
    


    def _canvas_to_svg(self, canvas):
        """Parses objects on a Tkinter canvas to build clean vector HTML SVGs with exact text centering."""
        bbox = canvas.bbox("all")
        if not bbox: return '<svg width="800" height="400"><text x="20" y="40">Empty Diagram</text></svg>'
        
        x1, y1, x2, y2 = bbox
        
        # Roomy layout margins to catch extended dimensional text tags safely
        padding_left_top = 30
        padding_right_bottom = 70 
        
        w = (x2 - x1) + padding_left_top + padding_right_bottom
        h = (y2 - y1) + padding_left_top #+ padding_right_bottom
        offset_x = -x1 + padding_left_top
        offset_y = -y1 + padding_left_top

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

                    # Setup the parent SVG text block. 
                    # Note: Adding 'dominant-baseline="text-before-edge"' forces SVG to measure from the top down, matching Tkinter!
                    svg_comment = (
                        f'<text x="{adjusted_coords[0]}" y="{adjusted_coords[1]}" '
                        f'font-family="{font_family}, Arial" font-size="{font_size}px" fill="{fill_color}" '
                        f'text-anchor="{svg_anchor}" dominant-baseline="text-before-edge">'
                    )
                    
                    # Append each wrapped line segment with a clean down-step (dy) line-height spacer
                    line_height = int(font_size) + 4
                    for i, line in enumerate(lines):
                        dy_val = "0" if i == 0 else f"{line_height}px"
                        # Escape text strings for valid web formatting layouts
                        safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        svg_comment += f'<tspan x="{adjusted_coords[0]}" dy="{dy_val}">{safe_line}</tspan>'
                    
                    svg_comment += '</text>'
                    text_elements.append(svg_comment)
                else:
                    # Fallback implementation for basic canvas text labels (e.g., Post dimensions, Step titles)
                    base_x = adjusted_coords[0]
                    base_y = adjusted_coords[1]
                    text_fill = fill_color if fill_color != "none" and fill_color != "white" and fill_color != "#ffffff" else "#808080"
                    lines = text_str.split('\n')
                    
                    line_height_em = 1.2
                    if len(lines) > 1:
                        initial_shift = -((len(lines) - 1) * line_height_em) / 2
                        first_line_dy = f"{initial_shift}em"
                    else:
                        first_line_dy = "0.35em"

                    # --- SAFELY COMPRISING ANCHOR CHECKS ---
                    # If anchor is an empty string from Tkinter, default it to center alignment
                    svg_label_anchor = "middle"
                    if anchor and "w" in anchor:
                        svg_label_anchor = "start"
                    elif anchor and "e" in anchor:
                        svg_label_anchor = "end"

                    if svg_label_anchor == "start":
                        # Clean layout line for left-aligned headers ("Aerial Layout", etc.)
                        svg_text = (
                            f'<text x="{base_x}" y="{base_y}" fill="{text_fill}" '
                            f'font-family="Arial, Helvetica, sans-serif" font-size="12px" font-weight="bold" '
                            f'text-anchor="start" dominant-baseline="text-before-edge">'
                        )
                        for idx, line_text in enumerate(lines):
                            clean_text = line_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                            dy_val = "0" if idx == 0 else f"{line_height_em}em"
                            svg_text += f'<tspan x="{base_x}" dy="{dy_val}">{clean_text}</tspan>'
                    else:
                        # LEAVE ALONE: This is your exact original code structure for standard drawing dimensions!
                        svg_text = (
                            f'<text x="{base_x}" y="{base_y}" fill="{text_fill}" '
                            f'font-family="Arial, Helvetica, sans-serif" font-size="12px" font-weight="bold" '
                            f'text-anchor="middle">'
                        )
                        for idx, line_text in enumerate(lines):
                            clean_text = line_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                            if idx == 0:
                                svg_text += f'<tspan x="{base_x}" dy="{first_line_dy}">{clean_text}</tspan>'
                            else:
                                svg_text += f'<tspan x="{base_x}" dy="{line_height_em}em">{clean_text}</tspan>'
                    
                    svg_text += '</text>'
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
        if not file_path: return

        self.deselect_all_main()
        self.refresh_materials_matrix()

        # Find all active post blocks on the canvas to explicitly determine which posts use them
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
            item = self.canvas.find_withtag(tag)
            print (tag)
            if item:
                coords = self.canvas.coords(item[0])
                if len(coords) == 4:
                    self.sections[tag]['x1'], self.sections[tag]['y1'] = coords[0], coords[1]
                    self.sections[tag]['x2'], self.sections[tag]['y2'] = coords[2], coords[3]

            text_item = self.canvas.find_withtag(f"{tag} && text")
            if text_item:
                full_label = self.canvas.itemcget(text_item[0], "text")
                self.sections[tag]['full_label_text'] = full_label

        clean_sections = {}
        for tag, data in self.sections.items():
            section_copy = {k: v for k, v in data.items() if k not in ['tab_id', 'canvas', 'table', 'label']}
            
            if 'lumber_counts' in data:
                section_copy['lumber_counts'] = {f"{k[0]}_{k[1]}": v for k, v in data['lumber_counts'].items()}
                
            clean_sections[tag] = section_copy

        # 3. Extract Post Data AND Visual Coordinates (Post Canvas)
        clean_posts = {}

        for p_id, p_data in self.post_entries.items():
            post_item = self.post_canvas.find_withtag(p_id)
            print (post_item)
            post_coords = self.post_canvas.coords(post_item[0]) if post_item else [0, 0, 0, 0] 
            
            items_found = self.post_canvas.find_withtag(p_id)

            if not items_found:
                print(f"DEBUG: Tag '{p_id}' NOT FOUND on post_canvas.")
                actual_coords = [0, 0, 0, 0]
            else:
                actual_coords = self.post_canvas.coords(items_found[0])
                print(f"DEBUG: Post {p_id} found! Raw Coords: {actual_coords}")
            
            label_coords = [post_coords[0]+self.p_size, post_coords[1]-12]
            print (label_coords)
            print (p_data)
            
            # --- FIX: Added .get() to is_dummy, bot_step, and bot_ramp ---
            clean_posts[p_id] = {
                "deck": p_data["deck"].get(),
                "grade": p_data["grade"].get(),
                "below": p_data["below"].get(),
                "total": p_data["total"].get(),
                "canvas_coords": post_coords, 
                "label_coords": label_coords,
                "is_dummy": p_data["is_dummy"].get() if hasattr(p_data["is_dummy"], "get") else p_data["is_dummy"],
                "bot_step": p_data["bot_step"].get() if hasattr(p_data["bot_step"], "get") else p_data["bot_step"],
                "bot_ramp": p_data["bot_ramp"].get() if hasattr(p_data["bot_ramp"], "get") else p_data["bot_ramp"]
            }

        # 4. Get rail locations and data
        print ("Get rails")
        for tag in self.rail_entries:
            item = self.rail_canvas.find_withtag(tag)
            coords = self.rail_canvas.coords(item[0])
            if len(coords) == 4:
                self.rail_entries[tag]['x1'], self.rail_entries[tag]['y1'] = coords[0], coords[1]
                self.rail_entries[tag]['x2'], self.rail_entries[tag]['y2'] = coords[2], coords[3]

        clean_rails = {tag: {k: v for k, v in data.items() if k not in ['tab_id', 'canvas', 'table', 'label']} 
                         for tag, data in self.rail_entries.items()}

        # 5. Package and Save
        serialized_comments = []
        canvas_mapping = {self.canvas: "layout", self.post_canvas: "posts", self.rail_canvas: "rails"}
        
        for dynamic_tag, tab_info in self.component_tabs.items():
            if 'canvas' in tab_info:
                canvas_mapping[tab_info['canvas']] = dynamic_tag

        for bid, data in self.comment_boxes.items():
            serialized_comments.append({
                'text': data['text'], 
                'x': data['x'], 
                'y': data['y'],
                'w': data['w'], 
                'h': data['h'],
                'target': canvas_mapping.get(data['canvas_ref'], "layout")
            })

        project_state = {
            "sections": clean_sections,
            "posts": clean_posts,
            "cross_braces": self.cross_brace_entries,
            "total_drop": self.total_drop_val,
            "manual_override_active": getattr(self, 'manual_override_active', False),
            "saved_boards_layout": getattr(self, 'boards', []),
            "rails": clean_rails,
            "comment_boxes": serialized_comments,
            "post_block_count": getattr(self, 'post_block_count', 0),  # Save total post block counter
            "active_post_blocks": active_blocks                        # Save list of posts on blocks
        }

        with open(file_path, "w") as f:
            json.dump(project_state, f, indent=4)
            
        messagebox.showinfo("Success", "Project saved with exact UI positions!")
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

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            # 1. Clear current UI
            self.canvas.delete("all")
            self.post_canvas.delete("all")
            self.rail_canvas.delete("all")
            self.manual_override_active = data.get("manual_override_active", False)

            for tag in list(self.component_tabs.keys()):
                try:
                    self.notebook.forget(self.component_tabs[tag]["frame"])
                except: pass
            
            self.sections = data.get("sections", {})

            print("Sections")
            print(self.sections)
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
                if tag != "REF_POINT" and not tag.startswith("Paver"): self.create_component_tab(tag)

            self.redraw_all()

            # 3. Load Posts from File (Instead of calling generate_posts)
            self.post_entries = {}
            posts_from_file = data.get("posts", {})
            self._post_drag_data = {"item": None, "x": 0, "y": 0}   # reset this on load for drag

            # Background Reference for Post Canvas
            for tag, s_data in self.sections.items():
                sid = self.canvas.find_withtag(f"{tag} && shape")[0]
                c = self.canvas.coords(sid)
                self.post_canvas.create_rectangle(*c, outline="#bbb", dash=(4,4))
                self.post_canvas.create_text((c[0]+c[2])/2, (c[1]+c[3])/2, 
                                            text=s_data['name'], fill="#999", font=("Arial", 10, "bold"))

            # Reconstruct each post from JSON
            self.post_table_data = []
            for p_id, p_info in posts_from_file.items():
                raw_dummy_val = p_info.get("is_dummy", "False")

                self.post_entries[p_id] = {
                    'deck': tk.StringVar(value=p_info["deck"]),
                    'grade': tk.StringVar(value=p_info["grade"]),
                    'below': tk.StringVar(value=p_info["below"]),
                    'total': tk.StringVar(value=p_info["total"]),
                    'canvas_coords': p_info["canvas_coords"],
                    'label_coords': p_info["label_coords"],
                    'is_dummy': tk.StringVar(value=str(raw_dummy_val)),
                    'bot_step': tk.StringVar(value=p_info['bot_step']),
                    'bot_ramp': tk.StringVar(value=p_info['bot_ramp'])
                }

                if isinstance(raw_dummy_val, str):
                    is_dummy = raw_dummy_val.lower() == "true"
                else:
                    is_dummy = bool(raw_dummy_val)
                
                # Fallback check for old naming conventions if key is missing
                if "(D)" in p_id or "dummy" in p_id:
                    is_dummy = True
                
                fill_color = "#e0e0e0" if is_dummy else "white"
                outline_color = "blue" if is_dummy else "black"
                label_text = p_id + (" (D)" if is_dummy and "(D)" not in p_id else "")
                
                coords = p_info["canvas_coords"]
                l_coords = p_info["label_coords"]
                bot_step = p_info["bot_step"]
                bot_ramp = p_info['bot_ramp']

                self.post_canvas.create_rectangle(*coords, fill=fill_color, outline=outline_color, tags=(p_id, "movable_post","post_border"))
                self.post_canvas.create_text(*l_coords, text=label_text, font=("Arial", 10, "bold"), tags=(p_id, "movable_post"))
                
                if p_id in active_post_blocks:
                    if len(coords) == 4:
                        x1, y1, x2, y2 = coords
                        buf = 4
                        block_pnum = f"block_{p_id}"
                        self.post_canvas.create_rectangle(
                            x1 - buf, y1 - buf, x2 + buf, y2 + buf,
                            fill="", outline="gray", width=buf,
                            tags=(block_pnum, (p_id, "movable_post", "post_border"), "post_block", "block_border")
                        )
                        self.bind_item(block_pnum)

                self.bind_item(p_id)
                self.post_count = int(p_id.replace("P", ""))+1

                num_id = int(''.join(filter(str.isdigit, p_id)))
                self.post_table_data.append((num_id, is_dummy, tag, float(p_info["grade"]),bot_step,bot_ramp))

            self.cross_brace_entries = {}
            saved_braces = data.get("cross_braces", {})
            
            for b_tag, b_data in saved_braces.items():
                self.cross_brace_entries[b_tag] = b_data
                if 'canvas_coords' in b_data:
                    coords = b_data['canvas_coords']
                else:
                    continue
                    
                self.post_canvas.create_rectangle(
                    *coords, 
                    fill="#8B4513",             
                    outline="black", 
                    tags=(b_tag, "movable_post", "cross_brace") 
                )
                
                if 'label_coords' in b_data:
                    l_coords = b_data['label_coords']
                    self.post_canvas.create_text(
                        *l_coords, 
                        text=b_tag, 
                        font=("Arial", 9, "bold"), 
                        tags=(f"label_{b_tag}", "movable_post")
                    )
                else:
                    cx = (coords[0] + coords[2]) / 2
                    cy = (coords[1] + coords[3]) / 2
                    self.post_canvas.create_text(
                        cx, cy, 
                        text=b_tag, 
                        font=("Arial", 9, "bold"), 
                        tags=(f"label_{b_tag}", "movable_post")
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
            rails_from_file = data.get("rails",{})
            self._rail_drag_data = {"item": None, "x": 0, "y": 0} 

            # Background Reference for Rail Canvas
            for tag, s_data in self.sections.items():
                sid = self.canvas.find_withtag(f"{tag} && shape")[0]
                c = self.canvas.coords(sid)
                self.rail_canvas.create_rectangle(*c, outline="#bbb", dash=(4,4))
                self.rail_canvas.create_text((c[0]+c[2])/2, (c[1]+c[3])/2, 
                                            text=s_data['name'], fill="#999", font=("Arial", 10, "bold"))

            for p_id, p_info in posts_from_file.items():
                p_coords = p_info["canvas_coords"]
                is_dummy = "(D)" in p_id or "dummy" in p_id
                p_fill = "#f0f0f0" if is_dummy else "#e1e1e1"
                p_outline = "#ccc" if is_dummy else "#999"

                self.rail_canvas.create_rectangle(
                    *p_coords, 
                    fill=p_fill, 
                    outline=p_outline, 
                    width=1,
                    tags=(p_id, "bg_post")
                )

            # Recreate and physically draw all individual rail segments on the canvas
            for r_id, r_info in rails_from_file.items():
                x1 = r_info.get("x1")
                y1 = r_info.get("y1")
                x2 = r_info.get("x2")
                y2 = r_info.get("y2")
                self.rail_entries[r_id] = {
                    'canvas_coords': r_info["canvas_coords"],
                    'ptype': r_info.get("ptype", "RAMP"),
                    'pname': r_info.get('name',""),
                    'rlen': r_info.get("rlen", 0),
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'id': None
                }

                p_type = r_info["ptype"]
                r_name = r_info.get('name', "")
                
                # 2. Call draw_rail_segment. It will natively look up r_id in self.rail_entries
                #    and assign the true canvas shape 'rid' to the 'id' key.
                self.draw_rail_segment(x1, y1, x2, y2, p_type, r_id, r_name)
                
                # 3. DO NOT catch a return variable or re-assign self.rail_entries[r_id]['id'] here!
                
                try:
                    num_id = int(''.join(filter(str.isdigit, r_id)))
                    if not hasattr(self, 'rail_count') or num_id >= self.rail_count:
                        self.rail_count = num_id + 1
                except ValueError:
                    pass
            
            print("override flag")
            print(self.manual_override_active)

            # --- CORRECTION: Process pairings loop AFTER draw_rail_segment assigns live ids ---
            if self.manual_override_active:
                print("\n=== START LOAD PROJECT DEBUG ===")
            print(f"Initial manual_override_active flag: {self.manual_override_active}")
            print(f"Available keys in self.rail_entries: {list(self.rail_entries.keys())}")

            if self.manual_override_active:
                raw_saved_boards = data.get("saved_boards_layout", [])
                print(f"Found {len(raw_saved_boards)} saved boards in JSON.")
                
                updated_boards = []
                for b_idx, board in enumerate(raw_saved_boards):
                    new_items = []
                    print(f"\nProcessing Board #{b_idx} (Size: {board.get('size')}\")")
                    
                    for item in board.get('items', []):
                        rail_key = item.get('rail')  # e.g., "RailNum4"
                        old_id = item.get('id')
                        
                        print(f"  - Item demands rail key: '{rail_key}' (Old ID from file: {old_id})")
                        
                        # Fetch the fresh dynamic ID out of our populated rail_entries map
                        if hasattr(self, 'rail_entries') and rail_key in self.rail_entries:
                            new_id = self.rail_entries[rail_key].get('id')
                            item['id'] = new_id
                            print(f"    SUCCESS: Found matching live ID in self.rail_entries -> New ID: {new_id}")
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
                
                print("\nTriggering rail_combined_materialColor(manual_override=True)...")
                self.rail_combined_materialColor(manual_override=True)
                
                print(f"Generated rail_colors length: {len(getattr(self, 'rail_colors', {}))}")
                print(f"Sample mapping of rail_colors: {self.rail_colors}")
                
                self.draw_legend_and_tables(
                    self.last_rail_boards, 
                    self.last_rail_colors, 
                    self.last_rail_pairing_data
                )
            else:
                print("\nManual override not active. Running standard automatic processing path...")
                self.rail_combined_materialColor(manual_override=False)

            print("=== END LOAD PROJECT DEBUG ===\n")

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
        for r_idx, (post_num, is_dummy, parent_tag,grade, bot_step, bot_ramp) in enumerate(posts_data):
            p_key = f"P{post_num}"
            if p_key not in self.post_entries: continue
            
            data = self.post_entries[p_key]
            display_name = p_key + (" (D)" if is_dummy else "")
            
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
        #print (tag_list)

        for tag, data in self.sections.items():
            idx = tag_list.index(tag)
            x1 = data.get('x1', 150 + (idx * 40)) # Stagger them clearly
            y1 = data.get('y1', 150 + (idx * 40))
            x2 = data.get('x2', 150 + (idx * 40)) # Stagger them clearly
            y2 = data.get('y2', 150 + (idx * 40))
            p_type = data.get('p_type','')
            name = data.get('name')
            l = data.get('l')
            w = data.get('w')
            color = data.get('color')

            if p_type == "RAMP": 
                self.ramp_count += 1

            if p_type == "TAPER RAMP": 
                self.taper_ramp_count += 1

            if p_type == "THRESH RAMP": 
                self.threshold_ramp_count += 1

            if p_type == "DECK":
                self.landing_count += 1
            
            if p_type == "STEP":
                self.step_count += 1

            if p_type=="Paver":
                paver_column = int(data.get('l', 24)/24) #12 inches x 2 pixel per inch
                print (paver_column)
                paver_row = int(data.get('w', 24)/24)
                self.paver_total = self.paver_total + paver_column * paver_row
                self.paver_count +=1
                pavnum = f"PaverCount{paver_column*paver_row}"
            taglist = (tag, p_type, "shape",pavnum) if p_type=="Paver" else (tag, p_type, "shape")   
            rect = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=data.get('color', 'gray'),
                # Add p_type back into the tags so on_stop_drag can find it

                tags=taglist    #(tag, p_type, "shape") 
            )
            print (f"P type = {p_type}")
            
            if p_type == "Paver":
                # 1. Add visual dividing lines back on canvas load
                for i in range(1, paver_column):
                    paver_offset = (i * 12) * self.scale
                    self.canvas.create_line(
                        x1 + paver_offset, y1, 
                        x1 + paver_offset, y2,
                        fill="black", 
                        width=1, 
                        tags=(tag, "paver_line") 
                    )
                for i in range(1, paver_row):
                    paver_offset = (i * 12) * self.scale
                    self.canvas.create_line(
                        x1, y1 + paver_offset, 
                        x2, y1 + paver_offset,
                        fill="black", 
                        width=1, 
                        tags=(tag, "paver_line") 
                    )    
                plcoord = (x1 + (x2 - x1) / 2, y1 + (y2-y1)/2)
                self.canvas.create_text(
                    plcoord,   
                    text=tag, 
                    font=("Arial", 10),
                    tags=(tag, "Paver")
                )
            
            self.bind_item(tag)
            
            self.canvas.create_text(
                (x2-x1)/2+x1, (y2-y1)/2+y1,
                text=data.get('full_label_text', ''),
                # Add "text" tag so it moves/rotates with the shape
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
        
        tk.Button(self.rail_control_frame, text="DebugRail Details", 
                  command=self.debug_rails, bg="#4CAF50", fg="white").pack(side="left")
        
        self.delete_rail_btn = tk.Button(
            self.rail_control_frame,text="Delete Rail", 
            command= self.delete_selected_rail, # Pass None if calling manually
            bg="#de2e2e", fg="white", font=("Arial", 10, "bold")
            )
        tk.Label(self.rail_control_frame, text="  (D: Delete, Drag: Move)").pack(side="left")

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
        total_ramp_inches = 0
        for tag, data in self.sections.items():
            if "RAMP" in data['name'].upper() and not "THRESH RAMP" in data['name'].upper() :
                total_ramp_inches += data['l']
        
        # Calculate raw drop
        raw_drop = total_ramp_inches / 12.0
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
            data['elev_start'] = current_elevation
            if "RAMP" in data['name'].upper() and not "THRESH" in data['name'].upper():
                drop = data['l'] / 12.0
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
        # --------------------------------------------

        tk.Label(self.sidebar, text="\nEDIT SELECTED", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(anchor="w", pady=(2, 0))
        self.ent_len = tk.Entry(self.sidebar); self.ent_len.pack(fill=tk.X, pady=2)
        self.ent_wid = tk.Entry(self.sidebar); self.ent_wid.pack(fill=tk.X, pady=2)
        tk.Button(self.sidebar, text="Apply Size", command=self.apply_resize).pack(fill=tk.X, pady=2)

        tk.Button(self.sidebar, text="Delete Selected", fg="red", command=self.delete_item).pack(fill=tk.X, pady=2)
        tk.Button(self.sidebar, text="Add Comment Box", command=lambda: self.spawn_comment_box(self.canvas), bg="#F08AF3", fg="black", font=("Arial", 10, "bold")).pack(fill=tk.X, pady=7)
        
        self.canvas.bind("<r>", self.rotate_item)
        self.canvas.bind("<R>", self.rotate_item)

    def spawn_ramp(self):
        w = float(self.set_ramp_w.get())
        self.create_part(150, 150, 91, w, "#dcdcdc", "RAMP")
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
        print(ask_type)
        return result

    def spawn_deck(self, angle):
        d = float(self.set_deck_d.get())
        w = d if angle == 90 else 82.75
        self.create_part(150, 150, d, w, "#ffd700", "DECK")
        self.update_total_drop()

    
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

    def create_part(self, x, y, l, w, color, p_type, **kwargs):
        #name = f"{p_type} {self.ramp_count + 1}" if p_type == "RAMP" else f"{p_type} {self.landing_count + 1}"
        
        if p_type == "RAMP":
            self.ramp_count += 1
            name = f"{p_type} {self.ramp_count}"
            display_name = name
        
        if p_type == "TAPER RAMP":
            self.taper_ramp_count += 1
            name = f"{p_type} {self.taper_ramp_count}"
            display_name = f"TAPER\nRAMP {self.taper_ramp_count}"

        if p_type == "THRESH RAMP":
            self.threshold_ramp_count += 1
            name = f"{p_type} {self.threshold_ramp_count}"
            display_name = f"THRESHOLD\nRAMP {self.threshold_ramp_count}"

        if p_type == "DECK":
            self.landing_count += 1
            name = f"{p_type} {self.landing_count}"
            display_name = name
        
        if p_type == "STEP":
            self.step_count += 1
            name = f"{p_type} {self.step_count}"
            display_name = name

        tag = f"obj_{id(name)}_{x}_{y}"
        print ("create part")
        print (tag)
        # Store the base data first
        self.sections[tag] = {"name": name, "p_type":p_type, "l": l, "w": w, "color": color,"x1":x, "y1":y,
                               "x2":x+l*self.scale,"y2":y+w*self.scale}
        print (self.sections[tag])

        for key, value in kwargs.items():
            self.sections[tag][key] = value
            
        print(f"Updated tags = {self.sections[tag]}")

        # Use our new helper to build the tab
        self.create_component_tab(tag)

        # Draw the rectangle on the main layout
        self.canvas.create_rectangle(x, y, x+(l*self.scale), y+(w*self.scale), 
                                 fill=color, outline="black", width=2, 
                                 tags=(tag, p_type, "shape"))

        if p_type != "STEP":
            self.canvas.create_text(
                x+(l*self.scale)/2, y+(w*self.scale)/2, 
                text=f"{display_name}\n{self.format_inchesquarter(l)}x{self.format_inchesquarter(w)}", 
                font=("Arial", 9, "bold"), 
                justify=tk.CENTER,  # Ensures multi-line blocks center-align nicely within the box boundaries
                tags=(tag, "text")
            )
        self.bind_item(tag)
        return tag

    def bind_item(self, tag):
        print (f"Binding {tag}")
        self.canvas.tag_bind(tag, "<ButtonPress-1>", self.on_start_drag)
        self.canvas.tag_bind(tag, "<B1-Motion>", self.on_drag)
        self.canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_stop_drag)

        self.post_canvas.tag_bind(tag, "<ButtonPress-1>", self.on_post_drag_start)
        self.post_canvas.tag_bind(tag, "<B1-Motion>", self.on_post_drag)
        self.post_canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_post_stop_drag)

        self.post_canvas.tag_bind(tag, "<r>", self.rotate_post_item)
        self.post_canvas.tag_bind(tag, "<R>", self.rotate_post_item)


    def bind_rail_item(self,tag):
        self.rail_canvas.tag_bind(tag, "<ButtonPress-1>", self.on_rail_drag_start)
        self.rail_canvas.tag_bind(tag, "<B1-Motion>", self.on_rail_drag)
        self.rail_canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_rail_drag_stop)
        self.rail_canvas.tag_bind(tag, "<r>", self.rotate_rail_item)
        self.rail_canvas.tag_bind(tag, "<R>", self.rotate_rail_item)


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

        if self.active_tag in self.sections and self.active_tag != "REF_POINT" and not self.active_tag.startswith('Paver') :
            d = self.sections[self.active_tag]
            self.ent_len.delete(0, tk.END); self.ent_len.insert(0, str(d['l']))
            self.ent_wid.delete(0, tk.END); self.ent_wid.insert(0, str(d['w']))
            self.draw_component_detail(d)
            
        # CRITICAL FIX: Ensure drag data tracks the UNIQUE tag (self.active_tag)
        # This prevents the "Existing Deck" (REF_POINT) from moving by mistake.
        self._drag_data.update({"item": self.active_tag, "x": canvas_x, "y": canvas_y})

    def on_drag(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        dx, dy =  canvas_x - self._drag_data["x"], canvas_y - self._drag_data["y"]
        self.canvas.move(self._drag_data["item"], dx, dy)
        self._drag_data.update({"x": canvas_x, "y": canvas_y})

    def on_stop_drag(self, event):
        if not self.active_tag: return
        
        sid_list = self.canvas.find_withtag(f"{self.active_tag} && shape")
        if not sid_list: return
        sid = sid_list[0]
        c = self.canvas.coords(sid)
        curr_corners = [(c[0],c[1]), (c[2],c[1]), (c[0],c[3]), (c[2],c[3])]
        #print (curr_corners)
        #print (self.active_tag)
        # Get all shapes and REVERSE the list [::-1] to prioritize the newest pieces
        all_shapes_reversed = self.canvas.find_withtag("shape")[::-1]

        # Pass 1: Prioritize Decks and Reference Points (Newest First)
        for other in all_shapes_reversed:
            tags = self.canvas.gettags(other)
            if self.active_tag in tags: continue
            if self.active_tag.startswith("Paver"): continue
            
            if "DECK" in tags or "REF_POINT" in tags or "STEP" in tags:
                o = self.canvas.coords(other)
                for cx, cy in curr_corners:
                    oth_coords = [(o[0],o[1]), (o[2],o[1]), (o[0],o[3]), (o[2],o[3])]

                    for index, (ox, oy) in enumerate(oth_coords, start=0):
                        #print(f"Processing pair #{index}: ox={ox}, oy={oy}")
                        if abs(cx-ox) < self.snap_dist and abs(cy-oy) < self.snap_dist:
                            #self.canvas.move(self.active_tag, ox-cx, oy-cy)
                            #self.update_post_tab()
                            dx = ox - cx
                            dy = oy - cy
                            
                            # Check if the piece being moved is a STEP
                            tags_active = self.canvas.gettags(sid)
                            if "STEP" in [t.upper() for t in tags_active]:
                                step_inset = 5 * self.scale
                                
                                # Determine corner index to decide inset direction
                                # corners = [0:TL, 1:TR, 2:BL, 3:BR]
                                #determine which side the neighbor is on
                                
                                print (index)
                                #this works for steps on the east or west side
                                corner_idx = curr_corners.index((cx, cy))
                                if corner_idx == 0: # Top Left
                                    if index == 1: #other top right
                                        dx+= 0; dy+= step_inset #inset down  
                                    else:
                                        dx += step_inset; dy += 0 # Inset right
                                elif corner_idx == 1: # Top Right
                                    if index == 0: #other top left
                                        dx+= 0; dy+= step_inset #inset down  
                                    else:
                                        dx -= step_inset; dy -= 0 # Inset left
                                elif corner_idx == 2: # Bottom Left
                                    if index == 0: #other top left
                                        dx+= step_inset; dy+= 0 #inset right  
                                    else:
                                        dx += 0; dy -= step_inset # Inset up
                                elif corner_idx == 3: # Bottom Right
                                    if index == 1: #other top right
                                        dx-= step_inset; dy-= 0 #inset left  
                                    else:
                                        dx -= 0; dy -= step_inset # Inset up


                                #this works for posts on the north or south side
                                #if corner_idx == 0 and cx > ox:   # Top Left
                                #    dx += step_inset; dy += 0 # Inset right
                                #elif corner_idx == 1 and cx < ox: # Top Right
                                #    dx -= step_inset; dy += 0 # Inset left
                                #elif corner_idx == 2 and cx > ox: # Bottom Left
                                #    dx += step_inset; dy -= 0 # Inset right
                                #elif corner_idx == 3 and cx < ox: # Bottom Right
                                #    dx -= step_inset; dy -= 0 # Inset left
        

                            self.canvas.move(self.active_tag, dx, dy)
                            self.update_post_tab()
                            return

        # Pass 2: Secondary priority for Ramps (Newest First)
        for other in all_shapes_reversed:
            tags = self.canvas.gettags(other)
            if self.active_tag in tags: continue
            if self.active_tag.startswith("Paver"): continue
            
            if "RAMP" in tags:
                o = self.canvas.coords(other)
                for cx, cy in curr_corners:
                    for ox, oy in [(o[0],o[1]), (o[2],o[1]), (o[0],o[3]), (o[2],o[3])]:
                        if abs(cx-ox) < self.snap_dist and abs(cy-oy) < self.snap_dist:
                            self.canvas.move(self.active_tag, ox-cx, oy-cy)
                            #add updates to the section tags here for the new location
                            #needs to consider orientation for second tags? or just use difference in current tags

                            self.update_post_tab() #keep here since this has a return next
                            return

        self.update_post_tab()
        self.update_total_drop()
        self.canvas.focus_set() #required for R to rotate

        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    

    def rotate_item(self, event):
        print ("Rotate")
        print (self.active_tag)
        if not self.active_tag: return
        
        # 1. Get the main shape (the rectangle)
        sid = self.canvas.find_withtag(f"{self.active_tag} && shape")[0]
        c = self.canvas.coords(sid)
        
        # Calculate center and current dimensions
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        curr_w_px, curr_h_px = c[2] - c[0], c[3] - c[1]
        
        # 2. Swap main rectangle dimensions
        self.canvas.coords(sid, cx - curr_h_px / 2, cy - curr_w_px / 2, 
                                cx + curr_h_px / 2, cy + curr_w_px / 2)

        # 3. Handle Text
        try:
            tid = self.canvas.find_withtag(f"{self.active_tag} && text")[0]
            self.canvas.coords(tid, cx, cy)
        except IndexError:
            pass

        # 4. Handle Step Lines
        # Find all lines associated with this specific step group
        step_lines = self.canvas.find_withtag(f"{self.active_tag} && step_line")
        
        for line_id in step_lines:
            lc = self.canvas.coords(line_id) # Returns [x1, y1, x2, y2]
            
            # Rotate start point (x1, y1)
            dx1, dy1 = lc[0] - cx, lc[1] - cy
            new_x1, new_y1 = cx - dy1, cy + dx1
            
            # Rotate end point (x2, y2)
            dx2, dy2 = lc[2] - cx, lc[3] - cy
            new_x2, new_y2 = cx - dy2, cy + dx2
            
            # Apply new coordinates to the line
            self.canvas.coords(line_id, new_x1, new_y1, new_x2, new_y2)

    def rotate_post_item(self, event):
        print ("Rotate post")
        if not self.active_tag: return
        
        #print (self.active_tag)
        # 1. Get the main shape (the rectangle)
        if "CrossBrace" in str(self.active_tag):
            sid = self.post_canvas.find_withtag(f"{self.active_tag} && post_border")[0]
            #print (sid)
            c = self.post_canvas.coords(sid)
            self.cross_brace_entries[self.active_tag]['horizontal']=0 if self.cross_brace_entries[self.active_tag]['horizontal']==1 else 1
            #sid = self.cross_brace_entries[self.active_tag]
            #c=sid['canvas_coords']
            #print (c)
        else:
            sid = self.post_canvas.find_withtag(f"{self.active_tag}")# && moveablerail")[0]
            #print (sid)
            c = self.post_canvas.coords(sid)
        #print (c)
        # Calculate center and current dimensions
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        curr_w_px, curr_h_px = c[2] - c[0], c[3] - c[1]
        
        # 2. Swap main rectangle dimensions
        new_coords = [cx - curr_h_px / 2, cy - curr_w_px / 2, 
                                cx + curr_h_px / 2, cy + curr_w_px / 2]
        self.post_canvas.coords(sid, new_coords)
        if "CrossBrace" in str(self.active_tag):
            self.cross_brace_entries[self.active_tag]['canvas_coords']=new_coords

        # 3. Handle Text
        try:
            tid = self.post_canvas.find_withtag(f"{self.active_tag} && text")[0]
            self.post_canvas.coords(tid, cx, cy)
            if "CrossBrace" in str(self.active_tag):
                self.cross_brace_entries[self.active_tag]['label_coords']=[cx,cy]
        except IndexError:
            pass

    def rotate_rail_item(self, event):
        print ("Rotate rail")
        if not self.active_rail_tag: return
        
        #print (self.active_rail_tag)
        # 1. Get the main shape (the rectangle)
        sid = self.rail_canvas.find_withtag(f"{self.active_rail_tag}")# && moveablerail")[0]
        #print (sid)
        c = self.rail_canvas.coords(sid)
        #print (c)
        # Calculate center and current dimensions
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        curr_w_px, curr_h_px = c[2] - c[0], c[3] - c[1]
        
        # 2. Swap main rectangle dimensions
        self.rail_canvas.coords(sid, cx - curr_h_px / 2, cy - curr_w_px / 2, 
                                cx + curr_h_px / 2, cy + curr_w_px / 2)

        # 3. Handle Text
        try:
            tid = self.rail_canvas.find_withtag(f"{self.active_rail_tag} && text")[0]
            self.rail_canvas.coords(tid, cx, cy)
        except IndexError:
            pass

    def apply_resize(self):
        # Ensure there is an active selection and it exists in our data
        if not self.active_tag or self.active_tag not in self.sections: 
            return
            
        try:
            l = float(self.ent_len.get())
            w = float(self.ent_wid.get())
        except ValueError:
            return # Handle non-numeric input gracefully

        data = self.sections[self.active_tag]
        data.update({"l": l, "w": w})
        
        # 1. Update the Tab Title in the Notebook
        # This uses the tab_id (the Frame) stored during create_part
        self.notebook.tab(data['tab_id'], text=data['name'])
        
        # 2. Update the Label inside the Detail Tab
        data['label'].config(text=f"{data['name']} Detail View")
        
        # 3. Update the Shape on the Main Layout Canvas
        sid = self.canvas.find_withtag(f"{self.active_tag} && shape")[0]
        tid = self.canvas.find_withtag(f"{self.active_tag} && text")[0]
        c = self.canvas.coords(sid)
        
        # Resize rectangle based on new dimensions
        self.canvas.coords(sid, c[0], c[1], c[0] + (l * self.scale), c[1] + (w * self.scale))
        
        # Update text label on the main canvas (Name + Dimensions)
        self.canvas.itemconfig(tid, text=f"{data['name']}\n{self.format_inchesquarter(l)}x{self.format_inchesquarter(w)}")
        self.canvas.coords(tid, c[0] + (l * self.scale) / 2, c[1] + (w * self.scale) / 2)
        
        # 4. Refresh the technical drawing and materials list in the detail tab
        self.draw_component_detail(data)

        self.update_total_drop()

    def delete_item(self):
        print (f"Delete {self.active_tag}")
        if self.active_tag:
        # 1. Get the tags BEFORE deleting the object
            tags = self.canvas.gettags(self.active_tag)
            print("All tags:", tags)

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
                            
                            print(f"Removed {count_to_remove} pavers. New total: {self.paver_total}")
                        except ValueError:
                            print(f"Could not convert '{num_str}' to an integer.")
                        
                        break  # Found it, no need to keep looping through tags
            elif self.active_tag in self.sections:
                # Remove the specific tab from the notebook
                self.notebook.forget(self.sections[self.active_tag]['tab_id'])
            del self.sections[self.active_tag]
            self.canvas.delete(self.active_tag)
            self.active_tag = None

    def setup_posts_tab(self):
        # Top control bar
        controls = tk.Frame(self.tab_posts, pady=10)
        controls.pack(fill=tk.X)
        tk.Button(controls, text="GENERATE POST PLACEMENT", command=self.generate_posts, 
                  bg="#28a745", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=20)
        # Place this near your other button code
        tk.Button(controls, text="Add Comment Box", command=lambda: self.spawn_comment_box(self.post_canvas),bg="#F08AF3", fg="black",font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=20)
        
        tk.Button(controls, text="ADD POST", command=self.spawn_post, 
                  bg="#28a745", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=20)
        #tk.Button(controls, text="DebugPosts", command=self.print_debug_info, 
        #          bg="#28a745", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=20)
        self.addCrossBrace_btn = tk.Button(controls, text="Add Cross Brace", command=self.post_crossbrace, 
                  bg="#28a745", fg="white", font=("Arial", 10, "bold")) #.pack(side=tk.RIGHT, padx=20)

        self.togglePostBlock_btn = tk.Button(controls, text="Toggle Post Block", command=self.post_block_toggle, 
                  bg="#28a745", fg="white", font=("Arial", 10, "bold"))

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
        #clear braces
        self.cross_brace_entries = {}
        self.postbrace_count = 0
        self.post_block_count = 0
        self.display_crossbracetable(self.active_tag)
                    
        self.calculate_elevations() 
        
        self.post_canvas.delete("all")
        self._post_drag_data = {"item": None, "x": 0, "y": 0}
        
        occupied_slots = [] 
        self.post_count = 1
        self.post_table_data = [] # List of (post_num, is_dummy, parent_tag, post_elev)
        
        #p_size = 3.5 * self.scale 
        #inset = 1.5 * self.scale  

        # Background Reference logic
        for tag, data in self.sections.items():
            if tag == "REF_POINT":
                continue
            #if tag.startswith("Paver"):
                #continue
            
            sid = self.canvas.find_withtag(f"{tag} && shape")[0]
            c = self.canvas.coords(sid)
            self.post_canvas.create_rectangle(*c, outline="#bbb", dash=(4,4))
            self.post_canvas.create_text((c[0]+c[2])/2, (c[1]+c[3])/2, 
                                        text=data['name'], fill="#999", font=("Arial", 10, "bold"))

        # TRACKING FOR DISTANCE LOGIC
        previous_center = None 

        #sorting for sections - steps are priority, threshold ramp is last option since posts are custom
        #key=lambda item: 0 if item[1].get('p_type') == "STEP" else 1
        sorted_sections = sorted(
        self.sections.items(),
        key=lambda item: 0 if item[1].get('p_type') == "STEP" 
                        else (2 if item[1].get('p_type') == "THRESH RAMP" else 1)
    )

        for tag, data in sorted_sections:
            if tag == "REF_POINT":
                continue
            if tag.startswith("Paver"):
                continue
            section_name = data['name']
            sid = self.canvas.find_withtag(f"{tag} && shape")[0]
            c = self.canvas.coords(sid) 
            current_center = ((c[0] + c[2]) / 2, (c[1] + c[3]) / 2)
            
            is_ramp = "RAMP" in section_name.upper()
            is_step = data.get('p_type') == "STEP"
            corners = [(c[0], c[1]), (c[2], c[1]), (c[0], c[3]), (c[2], c[3])]
            
            if is_step:
                # NEW: Determine Step orientation by looking at its lines
                is_vertical_orientation = False
                step_lines = self.canvas.find_withtag(f"{tag} && step_line")
                if step_lines:
                    # Get coordinates of the first dividing line [x1, y1, x2, y2]
                    lc = self.canvas.coords(step_lines[0])
                    # If x1 == x2, the line is vertical, meaning steps run horizontally
                    # If y1 == y2, the line is horizontal, meaning steps run vertically
                    if abs(lc[1] - lc[3]) < 1: # Horizontal line
                        is_vertical_orientation = True

            # Distance Check: If first piece, compare to REF_POINT. Otherwise, compare to previous piece.
            #starting with steps but don't set previous center until we get to the first ramp piece so the "top" is correct
            #otherwise the first ramp may have the lower end get the larger above grade value
            if previous_center is None:
                ref_items = self.canvas.find_withtag("REF_POINT")
                if ref_items:
                    rc = self.canvas.coords(ref_items[0])
                    compare_pt = ((rc[0] + rc[2]) / 2, (rc[1] + rc[3]) / 2)
                else:
                    compare_pt = current_center
            else:
                compare_pt = previous_center

            # Calculate distances from every corner to the comparison point
            corner_distances = []
            for cx, cy in corners:
                dist = math.sqrt((cx - compare_pt[0])**2 + (cy - compare_pt[1])**2)
                corner_distances.append(dist)
            
            # Sort distances to find the threshold between the 2 closest (uphill) and 2 furthest (downhill)
            sorted_dists = sorted(corner_distances)
            midpoint_threshold = (sorted_dists[1] + sorted_dists[2]) / 2

            for i, (cx, cy) in enumerate(corners):
                # i=0:TL, i=1:TR, i=2:BL, i=3:BR
                # Assign Elevation based on distance from previous section
                if corner_distances[i] < midpoint_threshold:
                    post_elev = data.get('elev_start', 0.0)
                else:
                    post_elev = data.get('elev_end', 0.0)

                # Diagonal Probe Points for neighbor detection
                if i == 0: p1, p2 = (cx - 3, cy + 3), (cx + 3, cy - 3)
                elif i == 1: p1, p2 = (cx + 3, cy + 3), (cx - 3, cy - 3)
                elif i == 2: p1, p2 = (cx - 3, cy - 3), (cx + 3, cy + 3)
                else: p1, p2 = (cx + 3, cy - 3), (cx - 3, cy + 3)

                neighbor_side = False
                neighbor_top_bot = False

                for o_tag in self.sections:
                    if o_tag == tag: continue
                    o = self.canvas.coords(self.canvas.find_withtag(f"{o_tag} && shape"))
                    matching_ids = self.canvas.find_withtag(f"{o_tag} && shape")
        
                    # 2. Filter out any element that carries the "Paver" tag using Python
                    filtered_ids = [item_id for item_id in matching_ids if "Paver" not in self.canvas.gettags(item_id)]
                    
                    if filtered_ids:

                        if (o[0] <= p1[0] <= o[2]) and (o[1] <= p1[1] <= o[3]): neighbor_side = True
                        if (o[0] <= p2[0] <= o[2]) and (o[1] <= p2[1] <= o[3]): neighbor_top_bot = True

                # Coordinate Calculation
                px, py = cx, cy
                bot_step=False #reset
                bot_ramp = False #reset for terminal end
                if is_step:
                    bot_step = True if neighbor_side == False and neighbor_top_bot == False else False
                    print ("Bottom step")
                    print (bot_step)
                    if not is_vertical_orientation: 
                        # Steps run Horizontally (Dividing lines are vertical)
                        # Posts go on Top (i=0,1) or Bottom (i=2,3)
                        px = cx if i in [0, 2] else cx - self.p_size
                        py = cy - self.p_size if i < 2 else cy
                    else: 
                        # Steps run Vertically (Dividing lines are horizontal)
                        # Posts go on Left (i=0,2) or Right (i=1,3)
                        px = cx - self.p_size if i % 2 == 0 else cx
                        py = cy if i < 2 else cy - self.p_size
                    
                elif is_ramp:
                    bot_ramp = True if neighbor_side == False and neighbor_top_bot == False else False
                    if (c[2]-c[0]) > (c[3]-c[1]): # Horizontal Ramp
                        px, py = (cx, cy-self.p_size) if i < 2 else (cx, cy)
                        if i == 1 or i == 3: px -= self.p_size 
                    else: # Vertical Ramp
                        px, py = (cx-self.p_size, cy) if i % 2 == 0 else (cx, cy)
                        if i >= 2: py -= self.p_size
                
                else: # Deck Logic
                    if not neighbor_side and not neighbor_top_bot:
                        if i == 0: px, py = cx - self.p_size, cy + self.inset
                        elif i == 1: px, py = cx, cy + self.inset
                        elif i == 2: px, py = cx - self.p_size, cy - (self.inset + self.p_size)
                        else: px, py = cx, cy - (self.inset + self.p_size)
                    else:
                        if neighbor_side and i in [2, 3]:
                            py = cy; px = cx - self.p_size if i == 3 else cx 
                        elif neighbor_side:
                            py = cy - self.p_size; px = cx if i == 0 else cx - self.p_size
                        else:
                            px = cx - self.p_size if i in [0, 2] else cx
                            py = cy if i in [0, 1] else cy - self.p_size

                # Collision Shield
                too_close = False
                collision_threshold = 7.5 * self.scale
                #for ex, ey in occupied_slots:
                    #if math.sqrt((px - ex)**2 + (py - ey)**2) < 10:
                    #    too_close = True; break
                for ex, ey in occupied_slots:
                    distance = math.sqrt((px - ex)**2 + (py - ey)**2)
                    if distance < collision_threshold:
                        too_close = True
                        print(f"Skipping post at {px},{py} - too close to existing post at {ex},{ey} (Dist: {distance:.1f})")
                        break

                if not too_close or is_step:
                    p_tag = f"P{self.post_count}"     #ptagchange

                    if p_tag not in self.post_entries:
                        self.post_entries[p_tag] = {
                            'deck': tk.StringVar(value=f"{post_elev:.1f}"),
                            'grade': tk.StringVar(value="0.0"),
                            'below': tk.StringVar(value=18.0),
                            'total': tk.StringVar(value="0.0"),
                            'canvas_coords': [px,py,px+self.p_size,py+self.p_size], #[0,0,0,0],
                            'label_coords': [0,0],
                            'is_dummy': False,
                            'bot_step': bot_step,
                            'bot_ramp': bot_ramp
                        }
                    # Store (Post Num, is_dummy, parent_tag, specific_elevation)
                    self.post_table_data.append((self.post_count, False, tag, post_elev,bot_step,bot_ramp))
                    
                    self.post_canvas.create_rectangle(px, py, px + self.p_size, py + self.p_size, 
                                                     fill="white", outline="black", 
                                                     tags=(p_tag, "movable_post", "post_border"))
                    self.post_entries[p_tag]['canvas_coords'] = [px,py,px+self.p_size,py+self.p_size]
                    

                    self.post_canvas.create_text(px + self.p_size/2, py - 12, 
                                               text=f"P{self.post_count}", 
                                               font=("Arial", 10, "bold"),
                                               tags=(p_tag, "movable_post"))
                    self.post_entries[p_tag]['label_coords'] = [px + self.p_size/2,py-12]
                    #print (self.post_entries[p_tag]['label_coords'] )

                    #self.post_canvas.tag_bind(p_tag, "<ButtonPress-1>", self.on_post_drag_start)
                    #self.post_canvas.tag_bind(p_tag, "<B1-Motion>", self.on_post_drag)
                    #self.post_canvas.tag_bind(p_tag, "<ButtonRelease-1>", self.on_post_stop_drag)
                    self.bind_item(p_tag)

                    occupied_slots.append((px, py))
                    self.post_count += 1

            # Dummy Posts Logic
            if is_ramp and data['l'] > 96:
                mid_l = (c[0] + c[2]) / 2
                mid_w = (c[1] + c[3]) / 2
                is_horiz = (c[2] - c[0]) > (c[3] - c[1])
                
                # For dummies, we calculate a midpoint elevation (start + end / 2)
                dummy_elev = (data.get('elev_start', 0) + data.get('elev_end', 0)) / 2
                
                dummies = []
                if is_horiz:
                    dummies.append((mid_l - self.p_size/2, c[1] - self.p_size))
                    dummies.append((mid_l - self.p_size/2, c[3]))
                else:
                    dummies.append((c[0] - self.p_size, mid_w - self.p_size/2))
                    dummies.append((c[2], mid_w - self.p_size/2))

                for dx, dy in dummies:
                    p_tag = f"P{self.post_count}"   #ptagchange
                    
                    if p_tag not in self.post_entries:
                        self.post_entries[p_tag] = {
                            'deck': tk.StringVar(value=f"{post_elev:.1f}"),
                            'grade': tk.StringVar(value="0.0"),
                            'below': tk.StringVar(value="18.0"),
                            'total': tk.StringVar(value="0.0"),
                            'canvas_coords': [dx,dy,dx+self.p_size,dy+self.p_size],  #[0,0,0,0],
                            'label_coords': [0,0],
                            'is_dummy': True,
                            'bot_step': bot_step,
                            'bot_ramp': bot_ramp

                        }
                    print (self.post_entries[p_tag])
                    # Dummies use the dummy flag (True) which triggers the 7.0 override in the table
                    self.post_table_data.append((self.post_count, True, tag, dummy_elev,bot_step,bot_ramp))
                    
                    self.post_canvas.create_rectangle(dx, dy, dx + self.p_size, dy + self.p_size, 
                                                     fill="#e0e0e0", outline="blue", 
                                                     tags=(p_tag, "movable_post", "post_border"))
                    self.post_entries[p_tag]['canvas_coords'] = [dx,dy,dx+self.p_size,dy+self.p_size]

                    self.post_canvas.create_text(dx + self.p_size/2, dy - 12, 
                                               text=f"P{self.post_count} (D)", 
                                               font=("Arial", 8, "italic"),
                                               tags=(p_tag, "movable_post"))
                    self.post_entries[p_tag]['label_coords'] = [dx + self.p_size/2,dy-12]
                    
                    self.post_count += 1
                    self.bind_item(p_tag)
            
            # Update previous center for the next section iteration
            #only if it's not a step so we still get the right "top" for the first piece
            if not is_step:
                previous_center = current_center

        # Final Table Update
        self.update_post_table(self.post_table_data)
        self.post_canvas.config(scrollregion=self.post_canvas.bbox("all"))
        self.update_post_optimization()
        self.addCrossBrace_btn.pack(side=tk.RIGHT, padx=20)

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
        
        print(f"\n--- DEBUG SPAWN RAIL START ---")
        print(f"Target Tag: {r_tag}, Parsed User Length: {rail_len}")
        print(f"Before draw_rail_segment, tag in rail_entries?: {r_tag in self.rail_entries}")

        self.draw_rail_segment(50, 50, 50+(rail_len-1) * self.scale, 50 + rail_w, p_type=r_type, r_num=r_tag, p_name="ExtraRail")
        
        print(f"After draw_rail_segment, tag in rail_entries?: {r_tag in self.rail_entries}")
        if r_tag in self.rail_entries:
            print(f"Contents built by draw_rail_segment: {self.rail_entries[r_tag]}")

        # Fix key verification and update data safely
        if r_tag not in self.rail_entries:
            print("Tag NOT found in entries. Manual injection fallback running.")
            self.rail_entries[r_tag] = {
                'canvas_coords': [50, 50, 50+(rail_len-1) * self.scale, 50 + rail_w],
                'label_coords': [0, 0],
                'ptype': "ExtraRail",
                'pname': "ExtraRail",
                'rlen': rail_len, # <-- FIX: Use rail_len instead of self.inch_val
            }
        else:
            print("Tag ALREADY found. Explicitly patching user lengths to ensure sync.")
            self.rail_entries[r_tag]['rlen'] = rail_len
            self.rail_entries[r_tag]['ptype'] = "ExtraRail"

        print(f"Final state of entry before material colors run: {self.rail_entries[r_tag]}")
        print(f"--- DEBUG SPAWN RAIL END ---\n")

        self.rail_combined_materialColor()


    def paver_add (self):

        dimensions = self.ask_paver_dimensions("Paver")
        
        # If the user hit 'Cancel' or closed the window without data, abort safely
        if dimensions["paver_row"] is None:
            return
        print (f"Dimensions = {dimensions}")
        paver_row = dimensions["paver_row"]
        paver_column = dimensions["paver_column"]
        
        paver_w = 12 * self.scale   #pavers are 12x12
        self.paver_count +=1
        self.paver_total = self.paver_total + paver_row*paver_column
        p_tag = f"Paver{self.paver_count}"


        x1=250
        y1=130
        x2=x1+paver_w * paver_column
        y2=y1 + paver_w * paver_row

        pcoord = [x1, y1, x2, y2]
        plcoord = [x1 + paver_w * paver_column/2, y1 + paver_w * paver_row/2]
        if p_tag not in self.sections:
            self.sections[p_tag] = {
                'p_tag': p_tag,
                'x1':x1,
                'y1': y1,  #[150,30,150+brace_len,30+brace_w], #[0,0,0,0],
                'x2': x2, #[0,0]
                'y2':y2,
                'p_type':"Paver",
                'name': p_tag,
                'l': paver_w*paver_column,
                'w': paver_w*paver_row,
                'color': "gray"

            }
        pavnum = f"PaverCount{paver_column*paver_row}"
        print (pavnum)
        self.canvas.create_rectangle(pcoord,       #250, 130, 250 + brace_len * self.scale, 130 + brace_w, 
                                            fill="gray", outline="gray", 
                                            tags=( p_tag,"Paver","shape",pavnum))

        # 2. Add visual dividing lines
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
                x1 , y1+ paver_offset, 
                x2, y1+ paver_offset,
                fill="black", 
                width=1, 
                tags=(p_tag, "paver_line") 
            )
        self.canvas.create_text(plcoord,   #250+brace_len*self.scale/2, 130 - 12, 
                                               text=p_tag, 
                                               font=("Arial", 10),#, "bold"),
                                               tags=(p_tag, "Paver"))

        self.bind_item(p_tag)
        #print ("After bind tag")
        self.active_tag = p_tag
        #print (self.active_tag)
        #add to materials tab - total # (row * column)

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


    def post_crossbrace (self):

        #brace_len = sd.askinteger("Add Brace", "How long is the cross brace?", minvalue=1, maxvalue=120)
        #if not brace_len:
        #    return
        dimensions = self.ask_brace_rail_dimensions("Brace")
        
        # If the user hit 'Cancel' or closed the window without data, abort safely
        if dimensions["display_length"] is None:
            return
            
        brace_len = dimensions["display_length"]
        material_len = dimensions["material_length"]
        
        #print(f"Drawing structural width: {brace_len} in.")
        #print(f"Adding to material list cost: {material_len} in.")
        
        brace_w = 1.5 * self.scale
        self.postbrace_count +=1
        b_tag = f"CrossBrace{self.postbrace_count}"

        bcoord = [250, 130, 250 + brace_len * self.scale, 130 + brace_w]
        blcoord = [250+brace_len*self.scale/2, 130 - 12]
        if b_tag not in self.cross_brace_entries:
            self.cross_brace_entries[b_tag] = {
                'b_tag': b_tag,
                'brace_length':brace_len,
                'canvas_coords': bcoord,  #[150,30,150+brace_len,30+brace_w], #[0,0,0,0],
                'label_coords': blcoord, #[0,0]
                'material_length':material_len,
                'horizontal':1
            }

        self.post_canvas.create_rectangle(bcoord,       #250, 130, 250 + brace_len * self.scale, 130 + brace_w, 
                                            fill="gray", outline="gray", 
                                            tags=( b_tag,material_len,brace_len,"post_border","cross_brace"))

        self.post_canvas.create_text(blcoord,   #250+brace_len*self.scale/2, 130 - 12, 
                                               text=b_tag, 
                                               font=("Arial", 10),#, "bold"),
                                               tags=(b_tag, "cross_brace"))

        self.bind_item(b_tag)
        #print ("After bind tag")
        self.active_tag = b_tag
        #print (self.active_tag)
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



    def spawn_post(self):
        p_tag = f"P{self.post_count}"     #ptagchange

        is_dummy = messagebox.askyesno("Post Configuration", "Is this a dummy/temporary post?")
        print (is_dummy)
        p_tag = f"P{self.post_count}"
        fill_color = "#211313" if is_dummy else "white"
        outline_color = "blue" if is_dummy else "black"
        label_text = p_tag + (" (D)" if is_dummy else "")
        

        if p_tag not in self.post_entries:
            self.post_entries[p_tag] = {
                'deck': tk.StringVar(value="40.0"),
                'grade': tk.StringVar(value="0.0"),
                'below': tk.StringVar(value="18.0"),
                'total': tk.StringVar(value="0.0"),
                'canvas_coords': [150,30,150+self.p_size,30+self.p_size], #[0,0,0,0],
                'label_coords': [0,0],
                'is_dummy':is_dummy,
                'bot_step': False,
                'bot_ramp': False
            }

        # Store (Post Num, is_dummy, parent_tag, specific_elevation)
        self.post_table_data.append((self.post_count, is_dummy, p_tag, 0,0,0))
        
        self.post_canvas.create_rectangle(150, 30, 150 + self.p_size, 30 + self.p_size, 
                                            fill=fill_color, outline=outline_color, 
                                            tags=(p_tag, "movable_post", "post_border"))
        self.post_entries[p_tag]['canvas_coords'] = [150,30,150+self.p_size,30+self.p_size]
        

        self.post_canvas.create_text(150 + self.p_size/2, 30 - 12, 
                                    text=label_text,    #f"P{self.post_count}", 
                                    font=("Arial", 10, "bold"),
                                    tags=(p_tag, "movable_post"))
        self.post_entries[p_tag]['label_coords'] = [150 + self.p_size/2,30-12]
        self.post_count += 1
        self.bind_item(p_tag)

        self.active_tag = p_tag
        self.update_delete_button_visibility()

        # 5. Refresh
        self.update_post_table(self.post_table_data)
        self.update_post_optimization()

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
        for r_idx, (post_num, is_dummy, parent_tag, post_elev,bot_step,bot_ramp) in enumerate(posts_data):
            p_key = f"P{post_num}"
            display_name = p_key + (" (D)" if is_dummy else "")
            #print ("Display Name")
            #print (display_name)
            #print (bot_step)

            def_deck = 40.0
            # Use the post-specific elevation we calculated via distance
            def_grade = 7.0 if is_dummy or bot_step else math.ceil(post_elev) 
            def_below = 0.0 if is_dummy else 18.0
            if (bot_step or bot_ramp) and not is_dummy:
                def_below = 24.0

            
            # 1. Row Labels and Entries
            tk.Label(self.post_grid, text=display_name, borderwidth=1, relief="solid", bg="white").grid(row=r_idx+1, column=0, sticky="nsew")
            
            v_deck = tk.StringVar(value=str(def_deck))
            v_grade = tk.StringVar(value=f"{def_grade:.1f}")
            v_below = tk.StringVar(value=str(def_below))
            v_total = tk.StringVar()
            
            for var in [v_deck, v_grade, v_below]:
                var.trace_add("write", lambda *args, p=p_key: self.calculate_total_length(p))
            
            tk.Entry(self.post_grid, textvariable=v_deck, width=8, justify='center').grid(row=r_idx+1, column=1, sticky="nsew")
            tk.Entry(self.post_grid, textvariable=v_grade, width=8, justify='center').grid(row=r_idx+1, column=2, sticky="nsew")
            tk.Entry(self.post_grid, textvariable=v_below, width=8, justify='center').grid(row=r_idx+1, column=3, sticky="nsew")
            
            tk.Label(self.post_grid, textvariable=v_total, borderwidth=1, relief="solid", bg="#f0f0f0").grid(row=r_idx+1, column=4, sticky="nsew")
            
            self.post_entries[p_key] = {"deck": v_deck, "grade": v_grade, "below": v_below, "total": v_total, "is_dummy":is_dummy, "bot_step": bot_step, "bot_ramp":bot_ramp}
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
                self.togglePostBlock_btn.pack(side=tk.RIGHT, padx=20)
            self.delete_btn.pack(side=tk.RIGHT, padx=20)

        else:
            # Hide the button if nothing is selected
            self.togglePostBlock_btn.pack_forget()
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
            print("Selection cleared.")


    def post_block_toggle(self):
        if self.active_tag:
            print ("Post Block Toggle")
            print (self.active_tag)
            tags = self.post_canvas.gettags(self.active_tag)
            print (tags)
            
            print (self.post_entries[self.active_tag])

            block_pnum = f"block_{self.active_tag}"
            print (f"Block pnum = {block_pnum}")
            # Check if the block rectangle already exists on the canvas
            existing_block = self.post_canvas.find_withtag(block_pnum)
            
            if existing_block:
                # --- TOGGLE OFF: Remove the block ---
                print(f"Removing post block for {self.active_tag}")
                
                self.post_canvas.delete(block_pnum)
                if hasattr(self, 'post_block_count'):
                    self.post_block_count = max(0, self.post_block_count - 1)
                
                if self.active_tag in self.post_entries:
                    post_data = self.post_entries[self.active_tag]              
                    print (f"Post Data {post_data}")
                    print (post_data.get("is_dummy"))
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
                #get x and y from drag to make rectangle
                if coords:
                    x1, y1, x2, y2 = coords
                    buf = 4
                    self.post_canvas.create_rectangle(x1 - buf, y1 - buf, x2 + buf , y2 + buf, 
                                                fill="", outline="gray",width=buf, 
                                                tags=(block_pnum, tags,"post_block", "block_border"))
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
            # Get the values from the StringVars
            deck = data['deck'].get()
            grade = data['grade'].get()
            total = data['total'].get()
            coords = data.get('canvas_coords', "No Coords")
            print (data)
            #coords = data['canvas_coords'].get()
            
            print(f"ID: {p_tag}")
            print(f"  - Heights: Deck: {deck}, Grade: {grade}, Total: {total}")
            print(f"  - Canvas Position: {coords}")
            print("-" * 20)
            

    def debug_posts(self):
        print("\n--- CURRENT POST ENTRIES DATA ---")
        if not self.post_entries:
            print("Dictionary is empty.")
            return

        for p_tag, p_data in self.post_entries.items():
            #print(f"Post ID: {p_tag}")
            # Extract values from StringVars
            deck = p_data.get('deck').get() if hasattr(p_data.get('deck'), 'get') else "N/A"
            grade = p_data.get('grade').get() if hasattr(p_data.get('grade'), 'get') else "N/A"
            total = p_data.get('total').get() if hasattr(p_data.get('total'), 'get') else "N/A"
            
            # Get coordinates
            c_coords = p_data.get('canvas_coords', [0,0,0,0])
            l_coords = p_data.get('label_coords', [0,0])
            
            #print(f"  > Heights: Deck: {deck}, Grade: {grade}, Total: {total}")
            #print(f"  > Canvas Box: {c_coords}")
            #print(f"  > Label Pos:  {l_coords}")
        print("---------------------------------\n")


    def update_post_tab(self):
        self.post_canvas.delete("all")
        for tag, data in self.sections.items():
            sid_list = self.canvas.find_withtag(f"{tag} && shape")
            if not sid_list: continue
            sid = sid_list[0]
            c = self.canvas.coords(sid)
            self.post_canvas.create_rectangle(*c, fill=data['color'], outline="black")
            for p in [(c[0],c[1]), (c[2],c[1]), (c[0],c[3]), (c[2],c[3])]:
                self.post_canvas.create_rectangle(p[0]-4, p[1]-4, p[0]+4, p[1]+4, fill="black")

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
        #print("Display crossbrace")
        
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
        
        #print("CBE")
        #print(self.cross_brace_entries)
        
        # 4. Loop through the entire dictionary and build the rows sequentially
        # enumerate(..., start=1) ensures rows go cleanly into grid row 1, 2, 3, etc.
        for row_idx, (b_tag, data) in enumerate(self.cross_brace_entries.items(), start=1):
            #print(b_tag)
            #print(data)
            #print("Brace Length")
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
        if abs(remainder - 0.5) < 0.05:
            fraction = "-1/2"
        elif abs(remainder - 0.25) < 0.05:
            fraction = "-1/4"
        elif abs(remainder - 0.33) < 0.05:
            fraction = "-1/3"
        elif abs(remainder - 0.66) < 0.05:
            fraction = "-2/3"
        elif abs(remainder - 0.75) < 0.05:
            fraction = "-3/4"
        else:
            fraction = "" # No fraction for whole numbers or unsupported decimals
            
        return f"{whole}{fraction}"
    
    def draw_component_detail(self, data):
        # 1. First find the tag right away so we have access to it throughout the method
        tag = next((k for k, v in self.sections.items() if v == data), None)
        
        canvas = data['canvas']
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

            canvas.create_text(190, 240, text="Cut 1-1/2\" from back of inside stringers",font=("Arial",10), anchor="w")
            canvas.create_line(310, 225, 265, 105, arrow=tk.LAST, fill="black",width=2)
            canvas.create_line(310, 225, 355, 105, arrow=tk.LAST, fill="black",width=2)
            canvas.create_text(190, 280, text="2 Outside Stringers & 2 Inside Stringers", font=("Arial", 10, "italic"), anchor="w")
            
            # --- 2. BRACING BOARD PLACEMENT PROFILE (Top Right) ---
            canvas.create_text(600, 30, text="Bracing Board Placement", font=("Arial", 12, "bold"), anchor="w")
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
            else:
                canvas.create_rectangle(cx, cy, cx+(stock_t*v_scale), cy+(w*v_scale), fill="#f8f9fa", outline="black")
                canvas.create_rectangle(cx+((l-stock_t)*v_scale), cy, cx+(l*v_scale), cy+(w*v_scale), fill="#f8f9fa", outline="black")
            data['spacer_blocks'] = []
            for i in range(n_joists):
                #horizontal members
                y_offset = i * (spacing + stock_t)
                if i == n_joists - 1: y_offset = w - stock_t 
                y1, y2 = cy + (y_offset * v_scale), cy + (y_offset * v_scale) + (stock_t * v_scale)
                if is_threshold_ramp or is_taper_ramp: #extend left side but not right  
                    if i == 0 or i == n_joists-1:
                        canvas.create_rectangle(cx, y1, cx+(l*v_scale), y2, fill="#f8f9fa", outline="green")
                    else:
                        canvas.create_rectangle(cx, y1, cx+((l-stock_t)*v_scale), y2, fill="#f8f9fa", outline="green")
                elif is_ramp and (i == 0 or i == n_joists-1): #these go all the way to the left
                    canvas.create_rectangle(cx, y1, cx+(l*v_scale), y2, fill="#f8f9fa", outline="green")
                else:
                    canvas.create_rectangle(cx+(stock_t*v_scale), y1, cx+((l-stock_t)*v_scale), y2, fill="#f8f9fa", outline="blue")
                if i > 0 and i < n_joists - 1:
                    pull_x = cx - (i * 25)
                    mark_val = y_offset - stock_t if is_ramp else y_offset
                    starty = cy+stock_t*v_scale if is_ramp else cy
                    canvas.create_line(pull_x, starty, pull_x, y1, arrow=tk.BOTH, fill="gray")
                    canvas.create_text(pull_x-3, (cy + y2)/2, text=f"{self.format_incheshalf(mark_val)}", angle=90, anchor="s", font=("Arial", 10))

                    

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
            canvas.create_text(cx+(l*v_scale)+55, cy+(w*v_scale)/2, text=f"Total Width: {self.format_inchesquarter(w)}",angle=90, anchor="s", font=("Arial", 12))
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

    def draw_legend_and_tables(self, boards, rail_colors, pairing_data):
        """Draws the summary with a cleaner visual layout."""
        self.rail_sidebar.delete("all")
        # This stores the math you just did into a variable the PDF can see
        self.rail_final_totals = boards

        y = 20
        
        # Header: Supplies
        self.rail_sidebar.create_text(20, y, text="SUPPLIES REQUIRED", anchor="w", font=("Arial", 10, "bold"))
        y += 25
        
        counts = {96: 0, 120: 0, 144: 0}
        for b in boards: counts[b['size']] += 1
        
        for length in [96, 120, 144]:
            self.rail_sidebar.create_text(20, y, text=f"2x4x{length//12}':", anchor="w")
            self.rail_sidebar.create_text(100, y, text=f"{counts[length]}", anchor="w", font=("Arial", 10, "bold"))
            y += 20

        # Header: Pairing Key
        y += 30
        self.rail_sidebar.create_text(20, y, text="COLOR KEY / PAIRINGS", anchor="w", font=("Arial", 10, "bold"))
        y += 25
        
        # Single board indicators
        for c, t in [("#4CAF50", "Solo 8' Board"), ("#2196F3", "Solo 10' Board")]:
            self.rail_sidebar.create_rectangle(20, y, 35, y+15, fill=c, outline="black")
            self.rail_sidebar.create_text(45, y+8, text=t, anchor="w")
            y += 22

        # Pair indicators
        for pair in pairing_data:
            self.rail_sidebar.create_rectangle(20, y, 35, y+15, fill=pair['color'], outline="black")
            self.rail_sidebar.create_text(45, y+8, text=pair['text'], anchor="w", font=("Arial", 9))
            y += 22

    def generate_rails(self):
        """The Refined Engine: Now with component names and tighter post-snapping."""

        self.manual_override_active = False

        self.rail_canvas.delete("all")
        rail_w = 1.5 * self.scale
        self.rail_count = 0

        # 1. Background: Grey Component Names for Reference
        for tag, data in self.sections.items():
            if tag == "REF_POINT":
                continue
            sid = self.canvas.find_withtag(f"{tag} && shape")[0]
            c = self.canvas.coords(sid)
            # Center of the section
            mx, my = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
            
            # Draw section outline (very light)
            self.rail_canvas.create_rectangle(*c, outline="#f0f0f0", dash=(4,4))
            # Place name in medium gray
            name = data.get('name', tag).replace("_", " ").title()
            self.rail_canvas.create_text(mx, my, text=name, fill="#999", 
                                       font=("Arial", 10, "italic"))

        # 2. Get Live Posts (Real ones only)
        posts = []
        for p_item in self.post_canvas.find_withtag("movable_post"):
            if self.post_canvas.type(p_item) == "rectangle":
                tags = self.post_canvas.gettags(p_item)
                p_id = next((t for t in tags if t.startswith("P")), None)    #ptagchange
                is_dummy = False
                for t_item in self.post_canvas.find_withtag(p_id):
                    if self.post_canvas.type(t_item) == "text":
                        if "(D)" in self.post_canvas.itemcget(t_item, "text"): is_dummy = True
                
                if not is_dummy:
                    pc = self.post_canvas.coords(p_item)
                    posts.append(pc)
                    # Draw a nice clean post outline for reference
                    self.rail_canvas.create_rectangle(*pc, outline="#ccc", fill="#f9f9f9")

        # 3. Process Edges
        for tag, data in self.sections.items():
            if tag == "REF_POINT":
                continue
            if tag.startswith("Paver"):
                continue
            sid = self.canvas.find_withtag(f"{tag} && shape")[0]
            c = self.canvas.coords(sid)
            is_ramp = "RAMP" in data['name'].upper()
            is_step = data.get('p_type') == "STEP"

            edges = [
                (c[0], c[1], c[2], c[1], "TOP", True),
                (c[0], c[3], c[2], c[3], "BOTTOM", True),
                (c[0], c[1], c[0], c[3], "LEFT", False),
                (c[2], c[1], c[2], c[3], "RIGHT", False)
            ]

            for ex1, ey1, ex2, ey2, side, is_h in edges:
                if is_ramp:
                    ramp_h = (c[2]-c[0]) > (c[3]-c[1])
                    if ramp_h and not is_h: continue
                    if not ramp_h and is_h: continue

                if is_step:
                    # Determine orientation based on dividing lines
                    # (True = Steps run Horizontally, False = Steps run Vertically)
                    steps_are_horizontal = True 
                    step_lines = self.canvas.find_withtag(f"{tag} && step_line")
                    if step_lines:
                        lc = self.canvas.coords(step_lines[0])
                        if abs(lc[1] - lc[3]) < 1: # Lines are horizontal
                            steps_are_horizontal = False
                    
                    # LOGIC: If steps are horizontal, we only want LEFT/RIGHT rails.
                    # If steps are vertical, we only want TOP/BOTTOM rails.
                    if steps_are_horizontal:
                        if not is_h: continue # Skip TOP/BOTTOM
                    else:
                        if is_h: continue # Skip LEFT/RIGHT
                    
            
                segments = self.get_exposed_segments(ex1, ey1, ex2, ey2, tag)
                for s_start, s_end in segments:
                    if (s_end - s_start) < 6: continue
                    #print (side)
                    if is_h:
                        rx1, rx2 = ex1 + s_start, ex1 + s_end
                        rx1 = self.stretch_to_post(rx1, ey1, posts, "START", is_h)
                        rx2 = self.stretch_to_post(rx2, ey1, posts, "END", is_h)
                        
                        # VERIFICATION: Calculate final length in inches
                        final_len_in = abs(rx2 - rx1) / self.scale
                        #print (final_len_in)
                        if final_len_in < 3: continue # Ignore rails < 3"
                        #ry = ey1 - rail_w if side == "TOP" else ey1
                        if side == "BOTTOM":
                            ry=ey1-rail_w
                        else:
                            ry=ey1
                        #print (ry)
                        self.rail_count+=1
                        self.draw_rail_segment(rx1, ry, rx2, ry + rail_w, p_type=data.get('p_type'),r_num=f"RailNum{self.rail_count}",p_name=data.get('name'))
                        #add the tags from either one
                        
                        r_tag = f"RailNum{self.rail_count}"
                        #print (r_tag)
                        if r_tag not in self.rail_entries:
                            self.rail_entries[r_tag] = {
                                'canvas_coords': [rx1,ry,rx2,ry + rail_w], #[0,0,0,0],
                                'label_coords': [0,0],
                                'ptype':data.get('p_type'),
                                'pname':data.get('name'),
                                'rlen':self.inch_val
                            }
                    else:
                        ry1, ry2 = ey1 + s_start, ey1 + s_end
                        ry1 = self.stretch_to_post(ex1, ry1, posts, "START", is_h)
                        ry2 = self.stretch_to_post(ex1, ry2, posts, "END", is_h)
                        
                        # VERIFICATION: Calculate final length in inches
                        final_len_in = abs(ry2 - ry1) / self.scale
                        if final_len_in < 3: continue # Ignore rails < 3"

                        #rx = ex1 - rail_w if side == "LEFT" else ex1
                        if side == "RIGHT":
                            rx=ex1-rail_w
                        else:
                            rx = ex1
                        self.rail_count+=1
                        #print ("Rail count")
                        #print (self.rail_count)
                        self.draw_rail_segment(rx, ry1, rx + rail_w, ry2, p_type=data.get('p_type'),r_num=f"RailNum{self.rail_count}",p_name=data.get('name'))
                        #add the tags from either one
                        
                        r_tag = f"RailNum{self.rail_count}"
                        #print (r_tag)
                        if r_tag not in self.rail_entries:
                            self.rail_entries[r_tag] = {
                                'canvas_coords': [rx,ry1,rx+rail_w,ry2], #[0,0,0,0],
                                'label_coords': [0,0],
                                'ptype':data.get('p_type'),
                                'pname':data.get('name'),
                                'rlen':self.inch_val
                            }
            self.rail_combined_materialColor()
            self.addrail_btn.pack(side=tk.RIGHT, padx=20)


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
        """The 'Subtractive' logic: identifies segments of an edge not blocked by other sections."""
        is_horiz = abs(y2 - y1) < 2
        edge_len = math.sqrt((x2-x1)**2 + (y2-y1)**2)
        exposed = [(0, edge_len)]
        
        for o_tag in self.sections:
            if o_tag == current_tag: continue
            oc = self.canvas.coords(self.canvas.find_withtag(f"{o_tag} && shape")[0])
            
            # If horizontal edge, check for vertical section overlap
            if is_horiz:
                if abs(oc[1] - y1) < 2 or abs(oc[3] - y1) < 2:
                    overlap_start = max(0, min(oc[0], oc[2]) - min(x1, x2))
                    overlap_end = min(edge_len, max(oc[0], oc[2]) - min(x1, x2))
                    if overlap_start < overlap_end:
                        new_exposed = []
                        for s, e in exposed:
                            if overlap_start >= e or overlap_end <= s:
                                new_exposed.append((s, e))
                            else:
                                if overlap_start > s: new_exposed.append((s, overlap_start))
                                if overlap_end < e: new_exposed.append((overlap_end, e))
                        exposed = new_exposed
            else: # Vertical Edge
                if abs(oc[0] - x1) < 2 or abs(oc[2] - x1) < 2:
                    overlap_start = max(0, min(oc[1], oc[3]) - min(y1, y2))
                    overlap_end = min(edge_len, max(oc[1], oc[3]) - min(y1, y2))
                    if overlap_start < overlap_end:
                        new_exposed = []
                        for s, e in exposed:
                            if overlap_start >= e or overlap_end <= s:
                                new_exposed.append((s, e))
                            else:
                                if overlap_start > s: new_exposed.append((s, overlap_start))
                                if overlap_end < e: new_exposed.append((overlap_end, e))
                        exposed = new_exposed
        return exposed

    def stretch_to_post(self, x, y, posts, point_type, is_h):
        """
        Refined snapping: 
        - Parallel neighbors (same direction) = Split Post (Center)
        - Perpendicular neighbors (turns) = Full Face (Flush)
        - No neighbors = Full Face (Flush)
        """
        best_dist = 12 * self.scale
        new_val = x if is_h else y
        
        for p in posts:
            px_mid = (p[0] + p[2]) / 2
            py_mid = (p[1] + p[3]) / 2
            dist = math.sqrt((x - px_mid)**2 + (y - py_mid)**2)
            
            if dist < best_dist:
                # Check for a neighbor section CONTINUING in the same direction
                if is_h:
                    # Look for a section to the left or right along the same horizontal line
                    search_pt = p[0] - 10 if point_type == "START" else p[2] + 10
                    neighbor_exists,section_name = self.is_section_at(search_pt, y)
                    currentsection = self.is_section_at(p[0]if point_type == "START" else p[2],y)

                    if section_name == currentsection[1]:neighbor_exists = False
                    #change this since it's it's itself and not another section so it's an inside corner
                    # NEW: Verify the neighbor is actually a horizontal continuation
                    # We check the section at the search point to see if it shares this Y-edge
                    is_parallel = False
                    if neighbor_exists:
                        for tag in self.sections:
                            c = self.canvas.coords(self.canvas.find_withtag(f"{tag} && shape")[0])
                            if (c[0]-2 <= search_pt <= c[2]+2) and (abs(c[1]-y) < 2 or abs(c[3]-y) < 2):
                                # If the neighbor has the same Y boundary, it's parallel
                                is_parallel = True
                                break

                    if is_parallel:
                        new_val = px_mid # Shared Face: Split 50/50
                    else:
                        # Perpendicular or Terminal: Full Face + 1px tuck
                        new_val = (p[0] + 1) if point_type == "START" else (p[2] - 1)
                
                else: # Vertical Rail
                    search_pt = p[1] - 10 if point_type == "START" else p[3] + 10
                    neighbor_exists,section_name = self.is_section_at(x, search_pt)
                    currentsection = self.is_section_at(x,p[1]if point_type == "START" else p[3])

                    if section_name == currentsection[1]:neighbor_exists = False
                    is_parallel = False
                    if neighbor_exists:
                        for tag in self.sections:
                            #check 
                            c = self.canvas.coords(self.canvas.find_withtag(f"{tag} && shape")[0])
                            if (c[1]-2 <= search_pt <= c[3]+2) and (abs(c[0]-x) < 2 or abs(c[2]-x) < 2):
                                is_parallel = True
                                break
                    print ("end neighbor")
                    if is_parallel:
                        new_val = py_mid
                    else:
                        new_val = (p[1] + 1) if point_type == "START" else (p[3] - 1)
                break
        return new_val

    def zzis_section_at(self, x, y):
        for tag in self.sections:
            c = self.canvas.coords(self.canvas.find_withtag(f"{tag} && shape")[0])
            if (c[0]-2 <= x <= c[2]+2) and (c[1]-2 <= y <= c[3]+2): return True
        return False
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

                    # Assign or fetch a synchronized matching hex color code
                    if combo_key not in color_map:
                        color_map[combo_key] = pair_colors[len(color_map) % len(pair_colors)]
                        self.pairing_data.append({'color': color_map[combo_key], 'text': lbl_text})
                    
                    clr = color_map[combo_key]
                    b['color'] = clr
                    
                    # Map the color to every physical canvas asset row ID in this combination
                    for rid in unique_ids:
                        self.rail_colors[rid] = clr

                    # --- RUN THE CANVAS LINKER LINES ---
                    if unique_ids:
                        print ("split")
                        print (unique_ids)

                        self.draw_pair_links(unique_ids, clr, size / 12,is_single_split)

                # 4. IF SINGLE FULL MATERIAL CUT
                else:
                    # Pick background placeholder shades matching standard stock colors
                    if size == 96: clr = "#4CAF50"
                    elif size == 120: clr = "#2196F3"
                    elif size == 144: clr = "#FFEB3B"
                    else: clr = "#9E9E9E"
                    
                    b['color'] = clr
                    for rid in unique_ids:
                        self.rail_colors[rid] = clr
                    
                    # Let single boards map their baseline identifiers out safely
                    if unique_ids:
                        print ("Single")
                        print (unique_ids)
                        self.draw_pair_links(unique_ids, clr, size / 12,is_single_split)

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
            
            if len(b['items']) >1:
                combo_key = "+".join(sorted([str(item['len']) for item in b['items']]))
                if combo_key not in color_map:
                    color = pair_colors[len(color_map) % len(pair_colors)]
                    color_map[combo_key] = color
                    pairing_data.append({'color': color, 'text': f"{b['size']//12}' Board: {combo_key}\""})
                
                clr = color_map[combo_key]
                for item in b['items']:
                    rail_colors[item['id']] = clr

                # Draw connection lines between paired rail segments (if different)
                #if len(unique_ids) > 1:
                #print (unique_ids)
                #print ("Pair")
                self.draw_pair_links(unique_ids, clr,b['size']/12,is_single_split)
            
            else:
                rid = unique_ids[0]
                if rid not in rail_colors:
                    if b['size'] == 96: rail_colors[rid] = "#4CAF50"
                    elif b['size'] == 120: rail_colors[rid] = "#2196F3"
                    elif b['size'] == 144: rail_colors[rid] = "#FFEB3B"
                    else: rail_colors[rid] = "#9E9E9E"
                self.draw_pair_links(unique_ids, rail_colors[rid],b['size']/12,is_single_split)

        return self.boards, rail_colors, pairing_data

    def draw_pair_links(self, ids, color, board_length,is_split_board=False):
        """Draws dashed lines and records the specific pair data for the PDF."""
        if not hasattr(self, 'rail_scrape_data'):
            self.rail_scrape_data = []

        print ("Pair Links")
        centers = []
        rail_names = []
        for rid in ids:
            print (rid)
            # Get coordinates for the line
            c = self.rail_canvas.coords(rid)
            print (c)

            if not c or len(c) < 4:
                # Find the rail matching this dynamic identifier inside your script mappings
                # Let's see if we can locate its original string key (e.g., 'RailNum4')
                rail_key = None
                
                # Check if we can find the key inside a master lookup or state dictionary
                if hasattr(self, 'rail_assignments'):
                    rail_key = self.rail_assignments.get(rid)
                
                # If we have the loaded plan data dictionary available, pull coords directly
                if hasattr(self, 'loaded_plan_data') and 'rails' in self.loaded_plan_data:
                    # Look through saved rails to see if coordinates match up
                    rails_dict = self.loaded_plan_data['rails']
                    
                    # Alternatively, iterate to match based on unique lengths or positions
                    matched_coords = None
                    for k, rdata in rails_dict.items():
                        # Try matching by checking if this dynamic id corresponds to this asset string
                        if str(rid) in k or (hasattr(self, 'current_id_to_key_map') and self.current_id_to_key_map.get(rid) == k):
                            matched_coords = rdata.get('canvas_coords')
                            break
                    
                    if matched_coords:
                        c = matched_coords
            print (c)
            centers.append(((c[0]+c[2])/2, (c[1]+c[3])/2))
            
            # Get the text label associated with this rail (e.g., "Ramp 1")
            tags = self.rail_canvas.gettags(rid)
            label_tag = next((t for t in tags if t.startswith("label_")), None)
            if label_tag:
                rail_names.append(self.rail_canvas.itemcget(label_tag, "text"))
            cict = 1
            if len(centers)==1:cict=0   #force it to go once for the solo locations that are split
            boardtext = "Board" if is_split_board else "Boards"
        for i in range(len(centers)-cict):
            x1, y1 = centers[i]
            x2, y2 = centers[i+cict]
            
            # Draw the line and the label on UI
            yofst =-12 if cict == 1 else 12
            print (ids)
            print (board_length)
            self.rail_canvas.create_line(x1, y1, x2, y2, fill=color, dash=(4,4), width=2, tags=("pair_link",))
            self.rail_canvas.create_text((x1+x2)/2, (y1+y2)/2 + yofst, text=f"{int(board_length)}' {boardtext}", 
                                         fill=color, font=("Arial", 10, "bold"), tags=("pair_link",))

            # RECORD FOR PDF: [Color, Board Size, Pair Description]
            pair_desc = " + ".join(rail_names) if len(rail_names) > 1 else "Single Rail"
            self.rail_scrape_data.append({
                "color": color.lower(),
                "length": f"{board_length}'",
                "desc": pair_desc
            })

    def draw_rail_segment(self, x1, y1, x2, y2, p_type, r_num, p_name):
        """Draws rail and places label with collision detection to prevent overlap."""
        px_len = math.sqrt((x2-x1)**2 + (y2-y1)**2)
        actual_inches = px_len / self.scale
        
        # Apply the slope factor if it's a STEP
        if p_type == "STEP":
            actual_inches *= 1.225  # 22.5% increase for the diagonal run
            
        self.inch_val = math.ceil(actual_inches)
        
        rid = self.rail_canvas.create_rectangle(x1, y1, x2, y2, 
                                               fill="#a0522d", outline="black", 
                                               tags=("draggable_rail", p_type, r_num, self.inch_val, p_name))
        self.bind_rail_item(rid)

        if self.manual_override_active:
            # --- UPDATED MANUALLY SPAWNED BOARD ENTRY LOGIC ---
            # Generate a distinct board group ID tracking this manual placement
            boardid = f"board_{r_num}"
            
            # Ensure self.boards exists as a list and this unique board profile isn't already appended
            if not hasattr(self, 'boards'):
                self.boards = []
                
            # Check if this board ID has already been recorded
            board_exists = any(b.get('id') == boardid for b in self.boards)
            
            if not board_exists:
                # Structure individual nesting items inside a dictionary matching your solver spec
                itemdt = [{
                    'id': rid,               # Canvas object ID integer
                    'len': self.inch_val,    # Calculated length in inches
                    'rail': r_num,           # Rail identifier (e.g. "R1")
                    'section': p_name        # Section tag (e.g. "Deck 1")
                }]
                
                # Assign stock threshold cutoff profile
                bsize = 96 if self.inch_val <= 96 else 120
                
                # Append to self.boards tracking matrix matching your template
                for ib in range(0,3):
                    self.boards.append({
                        'id': boardid,
                        'size': bsize, 
                        'used': self.inch_val, 
                        'items': itemdt,
                        'openbo': 0
                    })
                
        print (f"rid {rid}")
        print (f"rnum {r_num}")
        # --- FIX: Update self.rail_entries dynamically inside the method ---
        if r_num in self.rail_entries:
            print ("Updated")
            # If the entry was pre-initialized by load_project, inject the live canvas ID
            self.rail_entries[r_num]['id'] = rid
        else:
            print ("New")
            # If creating a fresh rail interactively from the UI layout tool
            self.rail_entries[r_num] = {
                'id': rid,
                'canvas_coords': [x1, y1, x2, y2],
                'ptype': p_type,
                'pname': p_name,
                'rlen': self.inch_val,
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2
            }
        
        mx, my = (x1+x2)/2, (y1+y2)/2
        
        is_horiz = abs(x2-x1) > abs(y2-y1)
        
        # Smart Label Offset
        if is_horiz:
            # Try TOP first
            target_y = my - 12
            overlap = self.rail_canvas.find_overlapping(mx-10, target_y-5, mx+10, target_y+5)
            # If we hit another label, move to BOTTOM
            if any("rail_label" in self.rail_canvas.gettags(o) for o in overlap):
                oy = 12
            else:
                oy = -12
            ox = 0
        else:
            # Try LEFT first
            target_x = mx - 25
            overlap = self.rail_canvas.find_overlapping(target_x-5, my-5, target_x+5, my+5)
            # If we hit another label, move to RIGHT
            if any("rail_label" in self.rail_canvas.gettags(o) for o in overlap):
                ox = 25
            else:
                ox = -25
            oy = 0
        
        self.rail_canvas.create_text(mx + ox, my + oy, text=f"{self.inch_val}\"", 
                                   fill="black", font=("Arial", 9, "bold"),
                                   tags=(f"label_{r_num}", "rail_label"))

    def debug_rails(self):
        print("\n--- CURRENT RAIL ENTRIES DATA ---")
        if not self.rail_entries:
            print("Dictionary is empty.")
            return

        for r_tag, r_data in self.rail_entries.items():
            #print(f"Post ID: {p_tag}")
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
        print("\n--- UNIQUE BOARDS OUTPUT ---")
        seen_boards = set()
        for b in self.boards:
            # Convert dictionary to a string representation to make it hashable
            board_str = str(b)
            if board_str not in seen_boards:
                print(b)
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


    def delete_selected_rail(self):
        # Ensure we have an active rail tag selected to delete
        if not hasattr(self, 'active_rail_tag') or not self.active_rail_tag:
            return

        target_tag = self.active_rail_tag
        print(f"Deleting Rail: {target_tag}")

        # 1. Visual Removal from Canvas
        self.rail_canvas.delete(target_tag)
        self.rail_canvas.delete(f"label_{target_tag}")
        self.rail_canvas.delete("pair_link")  # Clear old links out so they don't look broken

        # 2. Data Removal from rail_entries
        if hasattr(self, 'rail_entries') and target_tag in self.rail_entries:
            self.rail_entries.pop(target_tag, None)
            print(f"Successfully popped {target_tag} from self.rail_entries.")

        # 3. Handle Manual Override Sync (Scrub out of saved nesting boards)
        if getattr(self, 'manual_override_active', False) and hasattr(self, 'boards'):
            updated_boards = []
            for board in self.boards:
                # Filter out any nested item piece that matches our deleted rail tag name
                filtered_items = [item for item in board.get('items', []) if item.get('rail') != target_tag]
                
                # Only keep the physical board stock if it still contains items on it
                if filtered_items:
                    board['items'] = filtered_items
                    updated_boards.append(board)
            
            self.boards = updated_boards
            self.last_rail_boards = updated_boards

        # 4. Clear Selection Variable State
        self.active_rail_tag = None

        # 5. Safe Recalculation & UI Redraw
        # Pass manual_override explicit status state to prevent recalculation engine overlap
        is_manual = getattr(self, 'manual_override_active', False)
        self.rail_combined_materialColor(manual_override=is_manual)


    def on_rail_drag_start(self, event):
        canvas_x = self.rail_canvas.canvasx(event.x)
        canvas_y = self.rail_canvas.canvasy(event.y)
        item_ids = self.rail_canvas.find_closest(canvas_x, canvas_y)
        if not item_ids: return
        
        # Get all tags for the specific item clicked
        tags = self.rail_canvas.gettags(item_ids[0])
        if not tags: return
        #print ("Active tag drag")
        #print (tags)
        # The unique ID tag is always the first one in our setup (obj_... or REF_POINT)
        self.active_rail_tag = tags[2]
        #print (self.active_rail_tag)
        self.update_delete_button_rail_visibility()

        self.rail_canvas.itemconfig("draggable_rail", outline="black", width=1)
        self.rail_canvas.itemconfig(f"{self.active_rail_tag}", outline="#007bff", width=2)
        

        rail_tag = next((t for t in tags if t.startswith("RailNum")), None)    #ptagchange
        if rail_tag:
            self._rail_drag_data["item"] = rail_tag
            self._rail_drag_data["x"] = canvas_x
            self._rail_drag_data["y"] = canvas_y

    def on_rail_drag(self,event):
        canvas_x = self.rail_canvas.canvasx(event.x)
        canvas_y = self.rail_canvas.canvasy(event.y)
        item = self._rail_drag_data["item"]
        if not item: return
        
        dx = canvas_x - self._rail_drag_data["x"]
        dy = canvas_y - self._rail_drag_data["y"]
        
        # Move the physical object and its label
        self.rail_canvas.move(item, dx, dy)
        self.rail_canvas.move(f"label_{item}", dx, dy) # If labels are linked by ID
        
        self._rail_drag_data["x"] = canvas_x
        self._rail_drag_data["y"] = canvas_y


    
    def on_rail_drag_stop(self,event):
        print ("Rail Drag Stop")
        canvas_x = self.rail_canvas.canvasx(event.x)
        canvas_y = self.rail_canvas.canvasy(event.y)
        item = self._rail_drag_data["item"]
        print (item)
        if not item: return

        c = self.rail_canvas.coords(item)
        curr_corners = [(c[0],c[1]), (c[2],c[1]), (c[0],c[3]), (c[2],c[3])]
        dx = c[2]-c[0]
        dy = c[3]-c[1]
        #print (curr_corners)
        print (self.rail_entries)
        self.rail_entries[item]['canvas_coords'] = [canvas_x,canvas_y,canvas_x + dx,canvas_y + dy]
        #self.post_canvas.itemconfig("post_border", outline="black", width=2)
        self.rail_combined_materialColor()
        self.rail_canvas.focus_set()     #required for delete context

        self.rail_canvas.configure(scrollregion=self.rail_canvas.bbox("all"))
        #print ("Active tag after move")
        #print (self.active_rail_tag)

    def create_reference_point(self, x, y):
        tag = "REF_POINT"
        self.canvas.create_rectangle(x, y, x+350, y+30, fill="black", tags=(tag,"REF_POINT", "shape"))
        self.canvas.create_text(x+165, y-15, text="Reference Surface", font=("Arial", 9, "bold"), tags=(tag, "text"))
        self.bind_item(tag)
        self.sections[tag] = {"name": tag, "color": "black","l":300, "w":350,"x1":x, "y1":y,
                               "x2":x+350,"y2":y+30}

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
    CURRENT_VERSION = "5.7" \
    # A link to a raw text file on your GitHub repository containing just the version number (e.g., "4.2")
    VERSION_URL = "https://raw.githubusercontent.com/kbritrx007/RampBuilder/main/version.txt"
    # The link where they can download the latest installer or executable
    DOWNLOAD_URL = "https://github.com/kbritrx007/RampBuilder/releases/latest"
    
    #Write your new code, and change your internal script variable to CURRENT_VERSION = "4.2".
    #archive the files in RampBuilder folder so new creation doesn't have issues 
    #open terminal
    # cd ~/RampBuilder
    #Compile the new file using PyInstaller: python3 -m PyInstaller --onefile --windowed RampBuilder_v5_7.py
    #Go to GitHub, click Releases, draft a New Release, tag it v4.2, and drop your new executable inside.
    #Go to your version.txt file on GitHub, edit it to say 4.2, and save.
    
    
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
                
                txt = f"{item['rail']}\n{item['len']}\" ({item['section']})"
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
                                anchor="w", font=("Arial", 9, "italic"), fill="#7f8c8d")
        
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


if __name__ == "__main__":
    root = tk.Tk(); app = RampArchitect(root); root.mainloop()