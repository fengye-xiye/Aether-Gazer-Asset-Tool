# Copyright (C) 2025
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, Toplevel, filedialog, Menu
import json
import dbm
import os
import csv
import shutil
from collections import Counter
from datetime import datetime
import traceback
from pathlib import Path
import threading
import queue
import tempfile

#matplotlib
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
    plt.rcParams['axes.unicode_minus'] = False
except ImportError:
    MATPLOTLIB_AVAILABLE = False


'''
ljd：https://github.com/AzurLaneTools/ljd/blob/main/setup.py
碧蓝大眼一家亲（bushi）
'''

try:
    from ljd.tools import set_luajit_version, process_folder
    LJD_AVAILABLE = True
except ImportError:
    LJD_AVAILABLE = False

class ProgressWindow(Toplevel):
    #进度条
    def __init__(self, parent, title="加载中"):
        super().__init__(parent)
        self.title(title)
        self.geometry("350x120")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # 防误触

        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=title + "，请稍候。").pack(pady=5)
        
        # 模糊进度条
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=300)
        self.progress.pack(pady=10)
        self.progress.start(15)  # 速度

        parent.update_idletasks()
        # 将窗口居中于父窗口
        x = parent.winfo_x() + (parent.winfo_width() / 2) - (self.winfo_width() / 2)
        y = parent.winfo_y() + (parent.winfo_height() / 2) - (self.winfo_height() / 2)
        self.geometry(f"+{int(x)}+{int(y)}")

    def close(self):
        self.grab_release()
        self.destroy()

class CheckbuttonList(tk.Frame):
    def __init__(self, parent, items, **kwargs):
        super().__init__(parent, **kwargs)
        self.vars = []
        control_frame = ttk.Frame(self)
        control_frame.pack(fill='x', pady=2)
        ttk.Button(control_frame, text="全选", command=self.select_all).pack(side='left', padx=5)
        ttk.Button(control_frame, text="全不选", command=self.deselect_all).pack(side='left')
        list_container = ttk.Frame(self)
        list_container.pack(fill='both', expand=True)
        canvas = tk.Canvas(list_container)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        for item_text, item_value in items:
            var = tk.BooleanVar(value=False)
            self.vars.append(((item_text, item_value), var))
            key_display_text = f"{item_text} ({item_value})"
            ttk.Checkbutton(self.scrollable_frame, text=key_display_text, variable=var).pack(anchor="w", padx=5)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    def select_all(self):
        for _, var in self.vars:
            var.set(True)
    def deselect_all(self):
        for _, var in self.vars:
            var.set(False)
    def get_checked_items(self):
        return [item_tuple for item_tuple, var in self.vars if var.get()]

class PlottingWindow(Toplevel):
    def __init__(self, parent, analysis_data):
        super().__init__(parent)
        self.title("图表分析（没啥用）")
        self.geometry("1000x700")
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showerror("依赖缺失", "Matplotlib库未安装，无法使用此功能。")
            self.destroy()
            return
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)
        left_frame = ttk.Frame(main_pane, padding=5)
        ttk.Label(left_frame, text="勾选要分析的类别:").pack(anchor='w', pady=(0, 5))
        self.check_list = CheckbuttonList(left_frame, analysis_data.most_common())
        self.check_list.pack(fill=tk.BOTH, expand=True)
        main_pane.add(left_frame, weight=1)
        right_frame = ttk.Frame(main_pane)
        control_frame = ttk.Frame(right_frame, padding=5)
        control_frame.pack(fill=tk.X)
        ttk.Label(control_frame, text="图表类型:").pack(side=tk.LEFT, padx=5)
        self.plot_type_var = tk.StringVar(value="hbar")
        plot_types = [("饼状图", "pie"), ("垂直条形图", "bar"), ("水平条形图", "hbar"), ("折线图", "line")]
        for text, value in plot_types:
            ttk.Radiobutton(control_frame, text=text, variable=self.plot_type_var, value=value).pack(side=tk.LEFT)
        ttk.Button(control_frame, text="生成图表", command=self.create_plot).pack(side=tk.LEFT, padx=10)
        ttk.Button(control_frame, text="保存图表", command=self.save_chart).pack(side=tk.LEFT, padx=5)
        self.figure = plt.figure()
        self.canvas = FigureCanvasTkAgg(self.figure, master=right_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        main_pane.add(right_frame, weight=3)

    def create_plot(self):
        checked_data = self.check_list.get_checked_items()
        if not checked_data:
            messagebox.showwarning("提示", "请至少勾选一个项目。")
            return

        if len(checked_data) > 9:
            top_items = checked_data[:9]
            other_value = sum(item[1] for item in checked_data[9:])
            processed_data = top_items + [("其他", other_value)]
        else:
            processed_data = checked_data

        labels, sizes = [list(t) for t in zip(*processed_data)]
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        plot_type = self.plot_type_var.get()
        if plot_type == "pie":
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 9})
            ax.axis('equal')
            ax.set_title("所选类别占比")
        else:
            if plot_type == "bar":
                ax.bar(labels, sizes)
                plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            elif plot_type == "hbar":
                y_pos = range(len(labels))
                ax.barh(y_pos, sizes)
                ax.set_yticks(y_pos, labels=labels)
                ax.invert_yaxis()
                for i, v in enumerate(sizes):
                    ax.text(v, i, f' {v}', va='center')
            elif plot_type == "line":
                ax.plot(labels, sizes, marker='o')
                plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            ax.set_ylabel('数量' if plot_type != 'hbar' else '')
            ax.set_xlabel('数量' if plot_type == 'hbar' else '')
            ax.set_title('所选类别数量')
        self.figure.tight_layout()
        self.canvas.draw()

    def save_chart(self):
        if not self.figure.get_axes():
            messagebox.showwarning("提示", "请先生成图表。")
            return
        file_path = filedialog.asksaveasfilename(title="保存图表", defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("SVG", "*.svg"), ("All Files", "*.*")])
        if file_path:
            try:
                self.figure.savefig(file_path, bbox_inches='tight')
                messagebox.showinfo("成功", f"图表已保存至:\n{file_path}")
            except Exception as e:
                messagebox.showerror("保存失败", f"无法保存图表:\n{e}")

class CompareDBWindow(Toplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.title("对已有比数据库")
        self.geometry("800x600")
        self.controller = controller
        self.other_db_path = tk.StringVar()
        self.compare_mode_var = tk.StringVar(value="added")
        self.compare_results = None
        self.current_mode = None

        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill='both', expand=True)

        # 选择数据控件
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill='x', pady=5)
        # 写完后才发现好像反了
        self.select_button = ttk.Button(top_frame, text="选择对比库 (新版)", command=self._select_db)
        self.select_button.pack(side='left', padx=5)
        ttk.Entry(top_frame, textvariable=self.other_db_path, state='readonly').pack(side='left', fill='x', expand=True)
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill='x', pady=5)
        #模式选择
        mode_frame = ttk.LabelFrame(action_frame, text="对比模式 (当前加载的库为“旧版”)")
        mode_frame.pack(side='left', padx=5, pady=5)
        
        modes = [
            ("新版新增 (新版有, 旧版无)", "added"),
            ("旧版移除 (旧版有, 新版无)", "removed"),
            ("哈希变更 (双版皆有, 内容不同)", "changed")
        ]
        for text, mode in modes:
            ttk.Radiobutton(mode_frame, text=text, variable=self.compare_mode_var, value=mode).pack(anchor='w', padx=5, pady=1)

        self.compare_button = ttk.Button(action_frame, text="开始对比", command=self._start_compare_task, state='disabled')
        self.compare_button.pack(side='left', padx=10, expand=True, fill='y')
        self.results_frame = ttk.LabelFrame(main_frame, text="对比结果")
        self.results_frame.pack(fill='both', expand=True, pady=10)
        
        self.results_text = scrolledtext.ScrolledText(self.results_frame, wrap=tk.WORD, state='disabled')
        self.results_text.pack(fill='both', expand=True, padx=2, pady=2)
        
        #保存
        self.save_button = ttk.Button(main_frame, text="保存对比结果", command=self._save_results, state='disabled')
        self.save_button.pack(pady=5)

    def _select_db(self):
        db_path = filedialog.askopenfilename(
            title="选择要对比的数据库文件 (新版)", 
            filetypes=[("DBM Database", "*.dbm;*.db"), ("All Files", "*.*")]
        )
        if db_path:
            self.other_db_path.set(db_path)
            self.compare_button.config(state='normal')

    def _start_compare_task(self):
        # 当前加载->旧版
        main_db_path = self.controller.db_file_path 
        other_db_path = self.other_db_path.get()
        
        if not main_db_path or not other_db_path:
            messagebox.showerror("错误", "请选择数据库")
            return
        if os.path.abspath(main_db_path) == os.path.abspath(other_db_path):
            messagebox.showerror("错误", "不能和自己比。")
            return

        selected_mode = self.compare_mode_var.get()
        self.current_mode = selected_mode

        # 防误触
        self.compare_button.config(state='disabled')
        self.select_button.config(state='disabled')
        self.save_button.config(state='disabled')
        self.controller.status_var.set(f"正在对比数据库 ({selected_mode})...")
        
        # 结果
        title_map = {
            "added": "对比结果 - 新增项",
            "removed": "对比结果 - 移除项",
            "changed": "对比结果 - 哈希变更项"
        }
        new_title = title_map.get(selected_mode, "对比结果")
        self.results_frame.config(text=new_title)

        self.controller._run_task(
            task=lambda: self._compare_dbs_worker(main_db_path, other_db_path, selected_mode),
            on_done=self._on_compare_done
        )

    def _compare_dbs_worker(self, main_db_path, other_db_path, mode):
        def _read_db(path):
            data = {}
            with dbm.open(path, 'r') as db:
                for k in db.keys():
                    if not k.startswith(b'__'):
                        data[k.decode('utf-8')] = db[k].decode('utf-8')
            return data
            
        def _get_hash(value_str):
            try:
                return value_str.split('|', 1)[0]
            except (IndexError, AttributeError):
                return "N/A"

        old_data = _read_db(main_db_path)
        new_data = _read_db(other_db_path)
        
        old_keys = set(old_data.keys())
        new_keys = set(new_data.keys())

        if mode == "added":
            # 存在于新版，但不存在于旧版
            result_keys = new_keys - old_keys
            return sorted(list(result_keys))
        
        elif mode == "removed":
            # 存在于旧版，但不存在于新版
            result_keys = old_keys - new_keys
            return sorted(list(result_keys))

        elif mode == "changed":
            # 同时存在，但哈希值不同
            common_keys = old_keys & new_keys
            changed_items = []
            for key in common_keys:
                old_hash = _get_hash(old_data.get(key))
                new_hash = _get_hash(new_data.get(key))
                if old_hash != new_hash:
                    changed_items.append((key, old_hash, new_hash))
            return sorted(changed_items, key=lambda x: x[0])

        return []

    def _on_compare_done(self, result):
        self.compare_button.config(state='normal')
        self.select_button.config(state='normal')
        
        if isinstance(result, Exception):
            self.controller._handle_error("对比数据库时出错", result)
            self.controller.status_var.set("对比失败。")
            return

        self.compare_results = result
        self.results_text.config(state='normal')
        self.results_text.delete('1.0', tk.END)

        if not self.compare_results:
            self.results_text.insert('1.0', "对比完成，未发现符合条件的项目。")
            self.controller.status_var.set("对比完成，未发现符合条件的项目。")
        else:
            count = len(self.compare_results)
            output = ""
            status_msg = ""
            if self.current_mode == "added":
                status_msg = f"对比完成，发现 {count} 个新增项。"
                output = f"{status_msg}\n\n" + "\n".join(self.compare_results)
            elif self.current_mode == "removed":
                status_msg = f"对比完成，发现 {count} 个移除项。"
                output = f"{status_msg}\n\n" + "\n".join(self.compare_results)
            elif self.current_mode == "changed":
                status_msg = f"对比完成，发现 {count} 个哈希变更项。"
                output = f"{status_msg}\n\n"
                for path, old_h, new_h in self.compare_results:
                    output += f"{path}\n  旧哈希: {old_h}\n  新哈希: {new_h}\n\n"
            
            self.results_text.insert('1.0', output)
            self.save_button.config(state='normal')
            self.controller.status_var.set(status_msg)
            self.controller._log(f"数据库对比 ({self.current_mode}) 完成: {status_msg}")
            
        self.results_text.config(state='disabled')
    
    def _save_results(self):
        if not self.compare_results:
            messagebox.showwarning("提示", "没有可保存的对比结果。")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="保存对比结果",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        try:
            is_csv = file_path.lower().endswith('.csv')
            with open(file_path, 'w', newline='', encoding='utf-8-sig' if is_csv else 'utf-8') as f:
                if is_csv:
                    writer = csv.writer(f)
                    if self.current_mode in ["added", "removed"]:
                        writer.writerow(['path'])
                        for item in self.compare_results:
                            writer.writerow([item])
                    elif self.current_mode == "changed":
                        writer.writerow(['path', 'old_hash', 'new_hash'])
                        writer.writerows(self.compare_results)
                else: # TXT
                    f.write(self.results_text.get('1.0', tk.END))

            messagebox.showinfo("成功", f"结果已保存至:\n{file_path}")
            self.controller._log(f"对比结果已保存至: {file_path}")
        except Exception as e:
            self.controller._handle_error("保存结果失败", e)

class DirectoryExplorerWindow(Toplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.title("目录浏览器 (懒加载)")
        self.geometry("800x600")
        self.controller = controller
        
        container = ttk.Frame(self)
        container.pack(fill='both', expand=True)
        
        self.tree = ttk.Treeview(container, show="tree headings")
        self.tree.heading("#0", text="资源路径", anchor='w')
        
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<Button-3>", self._show_context_menu)
        
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="显示详情", command=self._display_selected_details)
        
        self.path_map = None
        self._start_populating_tree()

    def _start_populating_tree(self):
        if not self.controller.db_file_path:
            messagebox.showerror("错误", "没有加载数据库。")
            self.destroy()
            return
            
        self.tree.insert("", "end", "loading", text="正在加载目录结构，请稍候...")
        self.controller._run_task(
            task=self._build_path_map_worker,
            on_done=self._on_path_map_built
        )

    def _build_path_map_worker(self):
        path_map = {'': []}
        all_paths = []
        with dbm.open(self.controller.db_file_path, 'r') as db:
            all_paths = [key.decode('utf-8') for key in db.keys() if not key.startswith(b'__')]

        all_dirs = set()
        for path in all_paths:
            parts = path.split('/')
            for i in range(1, len(parts)):
                all_dirs.add('/'.join(parts[:i]))

        for dir_path in sorted(all_dirs):
            parent, child = os.path.split(dir_path)
            if parent not in path_map:
                path_map[parent] = []
            if child not in path_map[parent]:
                path_map[parent].append(child)

        for path in all_paths:
            parent, child = os.path.split(path)
            if parent not in path_map:
                path_map[parent] = []
            if child not in path_map[parent]:
                 path_map[parent].append(child)
        
        return path_map


    def _on_path_map_built(self, result):
        #无法加载修复
        self.tree.delete("loading")
        if isinstance(result, Exception):
            messagebox.showerror("数据库错误", f"无法浏览数据库：\n{result}")
            self.destroy()
            return
        
        self.path_map = result
        self._populate_node('')

    def _populate_node(self, parent_id):
        parent_path = self._get_full_path(parent_id)
        
        children = self.tree.get_children(parent_id)
        for child in children:
            if self.tree.item(child, 'text') == "DUMMY":
                self.tree.delete(child)

        if parent_path in self.path_map:
            for name in sorted(self.path_map[parent_path]):
                full_child_path = os.path.join(parent_path, name).replace("\\", "/")
                is_folder = full_child_path in self.path_map
                
                item_id = self.tree.insert(parent_id, 'end', text=name, 
                                           tags=('folder' if is_folder else 'file',))
                if is_folder:
                    self.tree.insert(item_id, 'end', text="DUMMY")

    def _on_tree_open(self, event):
        item_id = self.tree.focus()
        if item_id:
            self._populate_node(item_id)
            
    def _get_full_path(self, iid):
        if not iid:
            return ''
        path_parts = [self.tree.item(iid, "text")]
        parent_iid = self.tree.parent(iid)
        while parent_iid:
            path_parts.insert(0, self.tree.item(parent_iid, "text"))
            parent_iid = self.tree.parent(parent_iid)
        return "/".join(path_parts)

    def _show_context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.context_menu.post(event.x_root, event.y_root)

    def _display_selected_details(self):
        #在树中显示详情
        selected_iid = self.tree.selection()
        if not selected_iid:
            return
        selected_iid = selected_iid[0]
        full_path = self._get_full_path(selected_iid)
        is_folder = 'folder' in self.tree.item(selected_iid, 'tags')
        
        if is_folder:
            children = self.path_map.get(full_path, [])
            subfolders = sum(1 for c in children if os.path.join(full_path, c).replace("\\", "/") in self.path_map)
            files = len(children) - subfolders
            details = (f"目录路径:\n{full_path}\n\n"
                       f"包含 (直接子项):\n"
                       f"  - 子目录: {subfolders}\n"
                       f"  - 文件: {files}")
            self.controller.display_text_details(details)
        else:
            self.controller.display_asset_details(full_path)


class UnityFSStripperWindow(Toplevel):
    # 窗口工具
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.title("UnityFS 空字节擦除")
        self.geometry("600x450")
        self.controller = controller
        self.source_dir = tk.StringVar()
        self.dest_dir = tk.StringVar()
        
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill='x', pady=5)
        self.source_button = ttk.Button(path_frame, text="选择源目录", command=self._select_source)
        self.source_button.grid(row=0, column=0, padx=5, pady=2, sticky='w')
        ttk.Entry(path_frame, textvariable=self.source_dir, state='readonly').grid(row=0, column=1, sticky='ew', padx=5)
        self.dest_button = ttk.Button(path_frame, text="选择目标目录", command=self._select_dest)
        self.dest_button.grid(row=1, column=0, padx=5, pady=2, sticky='w')
        ttk.Entry(path_frame, textvariable=self.dest_dir, state='readonly').grid(row=1, column=1, sticky='ew', padx=5)
        path_frame.columnconfigure(1, weight=1)
        
        self.start_button = ttk.Button(main_frame, text="开始处理", command=self._start_processing_task)
        self.start_button.pack(pady=10)
        
        self.progress_var = tk.DoubleVar()
        self.progressbar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progressbar.pack(fill='x', pady=5)
        
        log_frame = ttk.LabelFrame(main_frame, text="处理日志")
        log_frame.pack(fill='both', expand=True, pady=(5,0))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled')
        self.log_text.pack(fill='both', expand=True, padx=2, pady=2)

    def _select_source(self):
        self.source_dir.set(filedialog.askdirectory(title="选择包含UnityFS文件的源目录"))
    def _select_dest(self):
        self.dest_dir.set(filedialog.askdirectory(title="选择保存处理后文件的目标目录"))
        
    def _log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.update_idletasks()

    def _update_progress(self, value):
        self.progress_var.set(value)

    def _set_ui_state(self, is_running):
        state = 'disabled' if is_running else 'normal'
        self.start_button.config(state=state)
        self.source_button.config(state=state)
        self.dest_button.config(state=state)

    def _start_processing_task(self):
        source, dest = self.source_dir.get(), self.dest_dir.get()
        if not source or not dest:
            messagebox.showerror("错误", "请先选择源目录和目标目录。")
            return
        if os.path.abspath(source) == os.path.abspath(dest):
            messagebox.showerror("错误", "源目录和目标目录不能相同。")
            return
            
        self._set_ui_state(True)
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state='disabled')
        self.progress_var.set(0)

        version_str = self.luajit_version.get()
        self.controller._log("LuaJIT 工具：开始处理。")
        self._log_message(f"源目录: {source}\n目标目录: {dest}\nLuaJIT版本: {version_str}\n" + "="*40 + "\n")
        self.controller._run_task(
            task=lambda progress_queue: self._process_files_worker(source, dest, version_str, progress_queue=progress_queue),
            on_done=self._on_processing_done,
            on_progress=self._handle_progress
        )

    def _handle_progress(self, progress_data):
        msg_type, payload = progress_data
        if msg_type == 'log':
            self._log_message(payload)
        elif msg_type == 'progress':
            self._update_progress(payload)

    def _process_files_worker(self, source, dest, version_str, progress_queue=None):
        temp_dir = tempfile.mkdtemp(prefix="ljd_")
        try:
            processed_count, skipped_count, error_count = 0, 0, 0
            HEADER = b'\x1B\x4C\x4A'

            progress_queue.put(('log', "预处理Lua字节码文件...\n"))
            
            all_files_to_process = []
            for input_root_str, _, files in os.walk(source):
                for file in files:
                    all_files_to_process.append(os.path.join(input_root_str, file))
            
            total_files = len(all_files_to_process)
            for i, input_path_str in enumerate(all_files_to_process):
                input_path = Path(input_path_str)
                relative_path = input_path.relative_to(source)
                temp_output_path = Path(temp_dir) / relative_path
                temp_output_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    progress_queue.put(('log', f"  - 预处理: {input_path.name} ... "))
                    with open(input_path, 'rb') as f_in:
                        content = f_in.read()
                    
                    index = content.find(HEADER)
                    if index != -1:
                        cleaned_bytes = content[index:].rstrip(b'\x00')
                        with open(temp_output_path, 'wb') as f_out:
                            f_out.write(cleaned_bytes)
                        progress_queue.put(('log', "完成\n"))
                        processed_count += 1
                    else:
                        progress_queue.put(('log', "跳过 (未找到LuaJIT头)\n"))
                        skipped_count += 1
                except Exception as e:
                    progress_queue.put(('log', f"失败 ({e})\n"))
                    self.controller._log(f"LuaJIT工具预处理'{input_path.name}'失败: {e}")
                    error_count += 1
                
                if total_files > 0:
                    progress_queue.put(('progress', (i + 1) / total_files * 50))

            progress_queue.put(('log', f"\n完成。 " f"预处理: {processed_count}, 跳过: {skipped_count}, 失败: {error_count}\n" + "="*40 + "\n"))
            
            decompiled_count, failed_count = 0, 0
            progress_queue.put(('progress', 100))
            return True
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            progress_queue.put(('log', "\n临时文件已清理。\n"))

    def _on_processing_done(self, result):
        self._set_ui_state(False)
        self.progress_var.set(100)
        
        if isinstance(result, Exception):
            messagebox.showerror("处理中断", f"发生严重错误: {result}")
            self.controller._log(f"UnityFS工具：处理中断 - {result}")
            return
            
        processed_count, skipped_count, error_count = result
        summary = (f"\n处理完成。\n"
                   f"成功: {processed_count}\n"
                   f"跳过: {skipped_count}\n"
                   f"失败: {error_count}")
        self._log_message("="*40 + summary)
        self.controller._log(f"UnityFS工具：{summary.strip()}")

class LuaJITDecompilerWindow(Toplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.title("LuaJIT 工具")
        self.geometry("700x550")
        self.controller = controller

        if not LJD_AVAILABLE:
            messagebox.showerror("依赖缺失", "ljd库未安装，无法使用此功能。")
            self.destroy()
            return
        
        self.source_dir = tk.StringVar()
        self.dest_dir = tk.StringVar()
        self.luajit_version = tk.StringVar(value="2.1")
        
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill='both', expand=True)

        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill='x', pady=5)
        
        self.source_button = ttk.Button(path_frame, text="选择源目录 (Lua字节码)", command=self._select_source)
        self.source_button.grid(row=0, column=0, padx=5, pady=2, sticky='w')
        ttk.Entry(path_frame, textvariable=self.source_dir, state='readonly').grid(row=0, column=1, sticky='ew', padx=5)
        
        self.dest_button = ttk.Button(path_frame, text="选择目标目录 (Lua源码)", command=self._select_dest)
        self.dest_button.grid(row=1, column=0, padx=5, pady=2, sticky='w')
        ttk.Entry(path_frame, textvariable=self.dest_dir, state='readonly').grid(row=1, column=1, sticky='ew', padx=5)
        
        ttk.Label(path_frame, text="LuaJIT 版本:").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.version_combo = ttk.Combobox(path_frame, textvariable=self.luajit_version, values=["2.1", "2.0"], state="readonly")
        self.version_combo.grid(row=2, column=1, padx=5, sticky='w')
        path_frame.columnconfigure(1, weight=1)

        self.start_button = ttk.Button(main_frame, text="开始处理", command=self._start_processing_task)
        self.start_button.pack(pady=10)
        
        self.progress_var = tk.DoubleVar()
        self.progressbar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progressbar.pack(fill='x', pady=5)

        log_frame = ttk.LabelFrame(main_frame, text="处理日志")
        log_frame.pack(fill='both', expand=True, pady=(5,0))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled')
        self.log_text.pack(fill='both', expand=True, padx=2, pady=2)
    
    def _select_source(self):
        self.source_dir.set(filedialog.askdirectory(title="选择包含Lua字节码文件的源目录"))
    
    def _select_dest(self):
        self.dest_dir.set(filedialog.askdirectory(title="选择保存Lua源码的目标目录"))

    def _log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.update_idletasks()

    def _update_progress(self, value):
        self.progress_var.set(value)

    def _set_ui_state(self, is_running):
        state = 'disabled' if is_running else 'normal'
        for widget in [self.start_button, self.source_button, self.dest_button, self.version_combo]:
            widget.config(state=state)

    def _start_processing_task(self):
        source, dest = self.source_dir.get(), self.dest_dir.get()
        if not source or not dest:
            messagebox.showerror("错误", "请先选择源目录和目标目录。")
            return
        if os.path.abspath(source) == os.path.abspath(dest):
            messagebox.showerror("错误", "源目录和目标目录不能相同。")
            return
            
        self._set_ui_state(True)
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state='disabled')
        self.progress_var.set(0)

        version_str = self.luajit_version.get()
        self.controller._log("LuaJIT 工具：开始处理。")
        self._log_message(f"源目录: {source}\n目标目录: {dest}\nLuaJIT版本: {version_str}\n" + "="*40 + "\n")
        self.controller._run_task(
            task=lambda progress_queue: self._process_files_worker(source, dest, version_str, progress_queue=progress_queue),
            on_done=self._on_processing_done,
            on_progress=self._handle_progress
        )

    def _handle_progress(self, progress_data):
        msg_type, payload = progress_data
        if msg_type == 'log':
            self._log_message(payload)
        elif msg_type == 'progress':
            self._update_progress(payload)

    def _process_files_worker(self, source, dest, version_str, progress_queue=None):
        #代码来自 https://github.com/unk35h/TextDumpScripts_ag/blob/main/LuaDecode.py
        temp_dir = tempfile.mkdtemp(prefix="ljd_preprocessed_")
        try:
            processed_count, skipped_count, error_count = 0, 0, 0
            HEADER = b'\x1B\x4C\x4A'

            progress_queue.put(('log', "步骤 1/2: 预处理Lua字节码文件...\n"))
            
            all_files = []
            for input_root_str, _, files in os.walk(source):
                for file in files:
                    all_files.append((Path(input_root_str), file))
            
            total_files = len(all_files)

            for i, (input_root, file) in enumerate(all_files):
                relative_dir = input_root.relative_to(source)
                temp_output_root = Path(temp_dir) / relative_dir
                temp_output_root.mkdir(parents=True, exist_ok=True)
                input_path = input_root / file
                
                try:
                    progress_queue.put(('log', f"  - 预处理: {file} ... "))
                    with open(input_path, 'rb') as f_in:
                        content = f_in.read()
                    
                    index = content.find(HEADER)
                    if index != -1:
                        cleaned_bytes = content[index:].rstrip(b'\x00')

                        temp_path = temp_output_root / file
                        with open(temp_path, 'wb') as f_out:
                            f_out.write(cleaned_bytes)
                        progress_queue.put(('log', "完成\n"))
                        processed_count += 1
                    else:
                        progress_queue.put(('log', "跳过 (未找到LuaJIT头)\n"))
                        skipped_count += 1
                except Exception as e:
                    progress_queue.put(('log', f"失败 ({e})\n"))
                    self.controller._log(f"LuaJIT工具预处理'{file}'失败: {e}")
                    error_count += 1
                
                if total_files > 0:
                    # 预处理占总进度的 50%
                    progress_queue.put(('progress', (i + 1) / total_files * 50))

            progress_queue.put(('log', f"\n预处理完成。 " f"处理: {processed_count}, 跳过: {skipped_count}, 失败: {error_count}\n" + "="*40 + "\n"))
            

            progress_queue.put(('log', "步骤 2/2: 开始反编译...\n"))
            try:
                version_int = int(version_str.replace('.', ''))
                set_luajit_version(version_int)
                progress_queue.put(('log', f"已设置 LuaJIT 版本为: {version_str}\n"))
            except (ValueError, TypeError) as e:
                raise ValueError(f"无效的LuaJIT版本字符串: {version_str}") from e

            progress_queue.put(('log', f"正在从临时目录反编译到: {dest}\n"))
            decompiled_count, failed_count = process_folder(temp_dir, dest)
            
            progress_queue.put(('log', f"反编译完成。成功: {decompiled_count}, 失败: {failed_count}\n"))
            progress_queue.put(('progress', 100)) # 完成所有工作

            return (processed_count, skipped_count, error_count, decompiled_count, failed_count)

        finally:
            # 确保无论成功还是失败，临时目录都会被清理
            shutil.rmtree(temp_dir, ignore_errors=True)
            progress_queue.put(('log', "\n临时文件已清理。\n"))

    def _on_processing_done(self, result):
        #ai大哥力作
        self._set_ui_state(False)
        self.progress_var.set(100)
        
        if isinstance(result, Exception):
            error_msg = f"\n处理中断，发生严重错误: {result}"
            self._log_message(error_msg)
            messagebox.showerror("处理中断", error_msg)
            self.controller._log(f"LuaJIT工具：处理中断 - {result}")
            traceback.print_exc()
        else:
            # 解包从 worker 返回的详细结果
            processed, skipped, pre_errors, decompiled, failed = result
            
            summary = (
                "预处理阶段:\n"
                f"  - 成功处理文件: {processed}\n"
                f"  - 跳过 (无头): {skipped}\n"
                f"  - 发生错误: {pre_errors}\n"
                "--------------------------\n"
                "反编译阶段 (ljd):\n"
                f"  - 成功反编译: {decompiled}\n"
                f"  - 反编译失败: {failed}\n"
                "=========================="
            )
            
            self._log_message(summary)
            self.controller._log(f"LuaJIT工具：处理完成。{summary.replace('\n', ' ')}")
            messagebox.showinfo("处理完成", "所有步骤已完成，请查看日志获取详细报告。")

class AssetAnalyzerApp:
    def __init__(self, master):
        self.master = master
        master.title("深空之眼目文件工具")
        master.geometry("1200x800")
        
        self.db_file_path = None
        self.analysis_data = None
        self.logging_enabled = False
        self.log_file = None
        self.detailed_log_var = tk.BooleanVar(value=False)
        self.current_selected_path = None
        self.task_queue = queue.Queue()
        self.progress_window = None
        
        self._setup_ui()
        self._update_ui_state()
        self._process_queue()
        self._log("应用程序启动。")

    def _setup_ui(self):
        self.status_var = tk.StringVar(value="欢迎使用！请先加载文件。")
        ttk.Label(self.master, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)
        self._setup_menu()
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=5)
        log_frame = ttk.Frame(top_frame)
        log_frame.pack(side=tk.RIGHT)
        self.log_button = ttk.Button(log_frame, text="开启日志", command=self.toggle_logging)
        self.log_button.pack(side=tk.LEFT)
        self.detailed_log_check = ttk.Checkbutton(log_frame, text="详细日志", variable=self.detailed_log_var)
        self.detailed_log_check.pack(side=tk.LEFT, padx=5)
        
        search_frame_container = ttk.Frame(main_frame)
        search_frame_container.pack(fill=tk.X, pady=10)
        search_frame = ttk.LabelFrame(search_frame_container, text="搜索", padding="10")
        search_frame.pack(fill=tk.X, expand=True, side=tk.LEFT)
        ttk.Label(search_frame, text="关键字:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=50)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_button = ttk.Button(search_frame, text="搜索", command=self.search_assets)
        self.search_button.pack(side=tk.LEFT, padx=5)
        self.save_search_button = ttk.Button(search_frame_container, text="保存搜索结果", command=self.save_search_results)
        self.save_search_button.pack(side=tk.RIGHT, padx=5, anchor='e')
        
        results_frame = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        list_container = ttk.Frame(results_frame)
        ttk.Label(list_container, text="搜索结果:").pack(anchor=tk.W)
        self.listbox = tk.Listbox(list_container)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)
        results_frame.add(list_container, weight=1)
        
        detail_container = ttk.Frame(results_frame)
        detail_label_frame = ttk.LabelFrame(detail_container, text="详情")
        detail_label_frame.pack(fill='both', expand=True)
        
        self.detail_path_var = tk.StringVar()
        self.detail_hash_var = tk.StringVar()
        self.detail_size_var = tk.StringVar()

        path_frame = ttk.Frame(detail_label_frame, padding=5)
        path_frame.pack(fill='x')
        ttk.Label(path_frame, text="文件路径:", width=10).pack(side='left')
        ttk.Entry(path_frame, textvariable=self.detail_path_var, state='readonly').pack(fill='x', expand=True)
        
        hash_frame = ttk.Frame(detail_label_frame, padding=5)
        hash_frame.pack(fill='x')
        ttk.Label(hash_frame, text="哈希值:", width=10).pack(side='left')
        self.hash_entry = ttk.Entry(hash_frame, textvariable=self.detail_hash_var)
        self.hash_entry.pack(fill='x', expand=True)

        size_frame = ttk.Frame(detail_label_frame, padding=5)
        size_frame.pack(fill='x')
        ttk.Label(size_frame, text="大小/ID:", width=10).pack(side='left')
        self.size_entry = ttk.Entry(size_frame, textvariable=self.detail_size_var)
        self.size_entry.pack(fill='x', expand=True)
        
        self.save_mod_button = ttk.Button(detail_label_frame, text="保存修改", command=self.save_modification)
        self.save_mod_button.pack(pady=10)

        results_frame.add(detail_container, weight=2)
        
        analysis_frame_container = ttk.Frame(main_frame)
        analysis_frame_container.pack(fill=tk.BOTH, expand=True, pady=10)
        analysis_frame = ttk.LabelFrame(analysis_frame_container, text="分类统计结果", padding="10")
        analysis_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.analysis_text = scrolledtext.ScrolledText(analysis_frame, wrap=tk.WORD, state='disabled')
        self.analysis_text.pack(fill=tk.BOTH, expand=True)
        self.save_analysis_button = ttk.Button(analysis_frame_container, text="保存统计结果", command=self.save_analysis_results)
        self.save_analysis_button.pack(side=tk.RIGHT, padx=5, anchor='ne')

    def _setup_menu(self):
        self.menubar = Menu(self.master)
        self.master.config(menu=self.menubar)
        self.file_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="文件", menu=self.file_menu)
        self.file_menu.add_command(label="从JSON加载/重建...", command=self.load_from_json)
        self.file_menu.add_command(label="直接加载数据库...", command=self.load_from_db)
        self.file_menu.add_command(label="导出为JSON...", command=self.export_to_json)
        self.merge_menu = Menu(self.file_menu, tearoff=0)
        self.merge_menu.add_command(label="从JSON合并...", command=self._merge_from_json)
        self.merge_menu.add_command(label="从DBM合并...", command=self._merge_from_dbm)
        self.file_menu.add_cascade(label="合并数据", menu=self.merge_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="退出", command=self.master.quit)
        self.analysis_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="分析", menu=self.analysis_menu)
        self.analysis_menu.add_command(label="目录浏览器", command=self.show_explorer_window)
        self.analysis_menu.add_command(label="可视化分析", command=self.show_visualization_window)
        
        self.tools_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="工具", menu=self.tools_menu)
        self.tools_menu.add_command(label="UnityFS 抹除工具...", command=self.show_stripper_tool)
        self.tools_menu.add_command(label="LuaJIT 工具...", command=self.show_luajit_decompiler_window)
        self.tools_menu.add_command(label="对比数据库...", command=self.show_compare_db_window)

    def _run_task(self, task, on_done, on_progress=None):
        progress_queue = queue.Queue() if on_progress else None
        
        def task_wrapper():
            try:
                result = task() if not on_progress else task(progress_queue=progress_queue)
                self.task_queue.put(('done', on_done, result))
            except Exception as e:
                self.task_queue.put(('done', on_done, e))

        if on_progress:
            def progress_checker():
                try:
                    while not progress_queue.empty():
                        msg = progress_queue.get_nowait()
                        self.task_queue.put(('progress', on_progress, msg))
                    self.master.after(100, progress_checker)
                except queue.Empty:
                    pass
            self.master.after(100, progress_checker)

        thread = threading.Thread(target=task_wrapper)
        thread.daemon = True
        thread.start()

    def _process_queue(self):
        try:
            while not self.task_queue.empty():
                msg_type, handler, data = self.task_queue.get_nowait()
                if msg_type == 'done':
                    handler(data)
                elif msg_type == 'progress':
                    handler(data)
        finally:
            self.master.after(100, self._process_queue)

    def _log(self, message):
        if self.logging_enabled and self.log_file and not self.log_file.closed:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                self.log_file.write(f"[{timestamp}] {message}\n")
                self.log_file.flush()
            except Exception as e:
                print(f"日志写入失败: {e}")

    def toggle_logging(self):
        try:
            if self.logging_enabled:
                self._log("日志记录已停止。")
                if self.log_file: self.log_file.close()
                self.log_file = None
                self.logging_enabled = False
                self.log_button.config(text="开启日志")
                self.status_var.set("日志功能已关闭。")
            else:
                log_dir = "logs"
                if not os.path.exists(log_dir): os.makedirs(log_dir)
                filename = os.path.join(log_dir, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                self.log_file = open(filename, 'w', encoding='utf-8')
                self.logging_enabled = True
                self.log_button.config(text="关闭日志")
                self.status_var.set(f"日志已开启: {os.path.basename(filename)}")
                self._log("日志记录已启动。")
        except Exception as e:
            self._handle_error(f"无法切换日志状态: {e}")
        finally:
            self._update_ui_state()

    def _update_ui_state(self):
        try:
            db_loaded = self.db_file_path is not None
            analysis_done = self.analysis_data is not None
            
            self.file_menu.entryconfig("导出为JSON...", state='normal' if db_loaded else 'disabled')
            self.merge_menu.entryconfig("从JSON合并...", state='normal' if db_loaded else 'disabled')
            self.merge_menu.entryconfig("从DBM合并...", state='normal' if db_loaded else 'disabled')
            
            self.analysis_menu.entryconfig("目录浏览器", state='normal' if db_loaded else 'disabled')
            self.analysis_menu.entryconfig("可视化分析", state='normal' if db_loaded and analysis_done and MATPLOTLIB_AVAILABLE else 'disabled')
            
            self.tools_menu.entryconfig("对比数据库...", state='normal' if db_loaded else 'disabled')
            self.tools_menu.entryconfig("LuaJIT 工具...", state='normal' if LJD_AVAILABLE else 'disabled')

            self.detailed_log_check.config(state='normal' if self.logging_enabled else 'disabled')
            
            widget_state = 'normal' if db_loaded else 'disabled'
            for widget in [self.search_entry, self.search_button, self.save_search_button, 
                           self.save_analysis_button, self.hash_entry, self.size_entry, 
                           self.save_mod_button]:
                widget.config(state=widget_state)

        except (tk.TclError, IndexError) as e:
            print(f"更新UI状态时捕获到错误 (通常在关闭时发生): {e}")
        except Exception as e:
            self._handle_error(f"更新UI状态时出错: {e}")

    def _handle_error(self, message, e=None):
        full_message = f"{message}\n\n详细信息: {e}" if e else message
        self._log(f"错误: {full_message}")
        if e: traceback.print_exc(file=self.log_file if self.logging_enabled and self.log_file else None)
        messagebox.showerror("错误", message)

    def _set_menus_state(self, state='normal'):
        # ai大哥
        try:
            for menu_label in ["文件", "分析", "工具"]:
                self.menubar.entryconfig(menu_label, state=state)
        except (tk.TclError, IndexError) as e:
            print(f"无法更改菜单状态: {e}")

    def _start_long_task(self, task_worker, on_done_callback, progress_title):
        # ai大哥
        self.progress_window = ProgressWindow(self.master, title=progress_title)
        self._set_menus_state('disabled')

        def final_on_done_callback(result):
            # 任务完成后，关闭进度窗口并恢复菜单
            if self.progress_window:
                self.progress_window.close()
                self.progress_window = None
            self._set_menus_state('normal')
            
            # 调用原始的回调函数处理任务结果
            on_done_callback(result)

        self._run_task(task=task_worker, on_done=final_on_done_callback)

    def load_from_json(self):
        json_path = filedialog.askopenfilename(
            title="选择JSON资源文件", filetypes=[("JSON/Text", "*.json;*.txt"), ("All Files", "*.*")])
        if not json_path: return
        
        db_path = filedialog.asksaveasfilename(
             title="选择数据库保存位置", defaultextension=".dbm", filetypes=[("DBM Database", "*.dbm;*.db"), ("All Files", "*.*")])
        if not db_path: return

        # 使用新的任务启动器
        self._start_long_task(
            task_worker=lambda: self._load_from_json_worker(json_path, db_path),
            on_done_callback=self._on_load_done,
            progress_title="正在从JSON创建数据库..."
        )

    def _load_from_json_worker(self, json_path, db_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        parsing_strategies = [self._parse_asset_hash_list, self._parse_unity_addressables_catalog]
        asset_items, strategy_name = None, None
        for strategy in parsing_strategies:
            try:
                result = strategy(data)
                if result:
                    asset_items, strategy_name = result, strategy.__name__
                    self._log(f"成功使用 '{strategy.__name__}' 策略解析了JSON文件。")
                    break
            except Exception as e:
                self._log(f"策略 '{strategy.__name__}' 执行失败: {e}")
                continue
        if not asset_items:
            raise ValueError("加载失败：不认识这个JSON文件格式。")

        self._log(f"从JSON '{os.path.basename(json_path)}' 创建DB '{os.path.basename(db_path)}'")
        with dbm.open(db_path, 'c') as db:
            db['__parsing_strategy__'] = strategy_name.encode('utf-8')
            for path, value in asset_items:
                db[path.encode('utf-8')] = value.encode('utf-8')
            total = len(asset_items)
        return db_path, total

    def _on_load_done(self, result):
        if isinstance(result, Exception):
            self.db_file_path = None
            self._handle_error(f"创建数据库时出错", result)
            self.status_var.set("数据库创建失败。")
        else:
            db_path, total = result
            self.db_file_path = db_path
            self.analysis_data = None
            self.status_var.set(f"DB创建成功: {os.path.basename(db_path)} ({total}条记录)")
            self._log(f"DB创建成功, 共写入 {total} 条记录。")
            
            # 启动分析任务
            self._start_long_task(
                task_worker=self._analyze_categories_worker,
                on_done_callback=self._on_analyze_done,
                progress_title="正在分析分类数据..."
            )
        self._update_ui_state()
        
    def _parse_asset_hash_list(self, data):
        if "assetHashList" in data and isinstance(data["assetHashList"], list):
            items = []
            for asset_string in data["assetHashList"]:
                try:
                    parts = asset_string.split('|')
                    if len(parts) >= 3:
                        path, hash_val, size_id = parts[0], parts[1], parts[2]
                        value = f"{hash_val}|{size_id}"
                        items.append((path, value))
                except (IndexError, TypeError): continue
            return items if items else None
        return None

    def _parse_unity_addressables_catalog(self, data):
        if "m_InternalIds" in data and isinstance(data["m_InternalIds"], list):
            items, placeholder = [], "{PlatformUtils.AddressableLoadPath}/"
            for internal_id in data["m_InternalIds"]:
                try:
                    if not isinstance(internal_id, str): continue
                    path = internal_id.replace(placeholder, "")
                    value = "N/A|0" 
                    items.append((path, value))
                except TypeError: continue
            return items if items else None
        return None

    def load_from_db(self):
        db_path = filedialog.askopenfilename(title="选择数据库文件", filetypes=[("DBM Database", "*.dbm;*.db"), ("All Files", "*.*")])
        if not db_path: return
        self._log(f"加载DB: {os.path.basename(db_path)}")

        def combined_worker():
            # 1. 加载DB信息
            with dbm.open(db_path, 'r') as db:
                count = sum(1 for k in db.keys() if not k.startswith(b'__'))
            # 2. 分析数据
            analysis_result = self._analyze_categories_worker(db_path_override=db_path)
            return db_path, count, analysis_result

        def combined_on_done(result):
            if isinstance(result, Exception):
                self.db_file_path = None
                self._handle_error(f"加载或分析数据库失败", result)
                self.status_var.set("加载数据库失败。")
            else:
                db_path_res, count, analysis_res = result
                self.db_file_path = db_path_res
                self._log(f"DB加载成功, 包含 {count} 条记录。")
                self.status_var.set(f"DB加载成功: {os.path.basename(db_path_res)} ({count}条记录)")
                # 直接处理分析结果
                self._on_analyze_done(analysis_res) 
            self._update_ui_state()

        self._start_long_task(
            task_worker=combined_worker,
            on_done_callback=combined_on_done,
            progress_title="正在加载和分析数据库..."
        )

    def _merge_from_json(self):
        json_path = filedialog.askopenfilename(title="选择要合并的JSON文件", filetypes=[("JSON/Text", "*.json;*.txt"), ("All Files", "*.*")])
        if not json_path: return
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            parsing_strategies = [self._parse_asset_hash_list, self._parse_unity_addressables_catalog]
            asset_items, new_strategy_name = None, None
            for strategy in parsing_strategies:
                result = strategy(data)
                if result:
                    asset_items, new_strategy_name = result, strategy.__name__
                    break
            if not asset_items:
                self._handle_error("合并失败：不认识这个JSON文件格式。")
                return

            with dbm.open(self.db_file_path, 'r') as db:
                original_strategy = db.get(b'__parsing_strategy__', b'unknown').decode('utf-8')
            
            if original_strategy != 'unknown' and original_strategy != new_strategy_name:
                proceed = messagebox.askyesno("策略不匹配警告",
                    f"当前数据库使用 '{original_strategy}' 策略创建。\n"
                    f"您要合并的JSON文件似乎是 '{new_strategy_name}' 格式。\n\n"
                    "这两种格式不兼容，合并可能导致数据不一致。\n确定要继续合并吗？")
                if not proceed:
                    self._log("用户因策略不匹配取消了合并操作。")
                    return
            byte_items = [(p.encode('utf-8'), v.encode('utf-8')) for p, v in asset_items]
            self._log(f"开始从JSON '{os.path.basename(json_path)}' 合并数据")
            self._perform_merge(byte_items)
        except Exception as e:
            self._handle_error(f"合并JSON时出错", e)

    def _merge_from_dbm(self):
        db_path = filedialog.askopenfilename(title="选择要合并的DBM数据库", filetypes=[("DBM Database", "*.dbm;*.db"), ("All Files", "*.*")])
        if not db_path: return
        if os.path.abspath(db_path) == os.path.abspath(self.db_file_path):
            self._handle_error("不能跟自己合并。")
            return
        
        try:
            with dbm.open(db_path, 'r') as source_db:
                items = [item for item in source_db.items() if not item[0].startswith(b'__')]
            self._log(f"开始从DBM '{os.path.basename(db_path)}' 合并数据")
            self._perform_merge(items)
        except Exception as e:
            self._handle_error(f"合并DBM时出错", e)

    def _perform_merge(self, items_iterable):
        self._start_long_task(
            task_worker=lambda: self._perform_merge_worker(items_iterable),
            on_done_callback=self._on_merge_done,
            progress_title="正在合并数据..."
        )
    
    def _perform_merge_worker(self, items_iterable):
        with dbm.open(self.db_file_path, 'c') as db:
            count_before = len([k for k in db.keys() if not k.startswith(b'__')])
            items_list = list(items_iterable)
            for key, value in items_list:
                if self.detailed_log_var.get(): self._log(f"  合并/更新: {key.decode('utf-8')}")
                db[key] = value
            count_after = len([k for k in db.keys() if not k.startswith(b'__')])
        added = count_after - count_before
        updated = len(items_list) - added
        return added, updated

    def _on_merge_done(self, result):
        if isinstance(result, Exception):
            self._handle_error(f"执行合并操作时出错", result)
            self.status_var.set("合并失败。")
        else:
            added, updated = result
            message = f"合并完成。新增 {added} 条, 更新/覆盖 {updated} 条记录。"
            self.status_var.set(message)
            self._log(message)
            messagebox.showinfo("成功", message)
            

            self._start_long_task(
                task_worker=self._analyze_categories_worker,
                on_done_callback=self._on_analyze_done,
                progress_title="正在重新分析数据..."
            )
        self._update_ui_state()

    def search_assets(self):
        keyword = self.search_var.get().strip().lower()
        if not keyword: return
        self._log(f"搜索关键字: '{keyword}'")
        self.search_button.config(state='disabled') # 立即禁用搜索按钮
        
        self._start_long_task(
            task_worker=lambda: self._search_assets_worker(keyword),
            on_done_callback=self._on_search_done,
            progress_title=f"正在搜索 '{keyword}'..."
        )

    def _search_assets_worker(self, keyword):
        with dbm.open(self.db_file_path, 'r') as db:
            return sorted([k.decode('utf-8') for k in db.keys() 
                           if not k.startswith(b'__') and keyword in k.decode('utf-8').lower()])

    def _on_search_done(self, result):
        self.search_button.config(state='normal') # 恢复搜索按钮
        if isinstance(result, Exception):
            self._handle_error(f"搜索失败", result)
            self.status_var.set("搜索失败。")
            return
        
        found = result
        self.listbox.delete(0, tk.END)
        for path in found:
            self.listbox.insert(tk.END, path)
        self.status_var.set(f"搜索完成，找到 {len(found)} 个匹配项。")
        self._log(f"搜索找到 {len(found)} 个结果。")

    def _analyze_categories_worker(self, db_path_override=None):
        # 允许传入路径以支持组合任务
        path_to_use = db_path_override if db_path_override else self.db_file_path
        categories = Counter()
        with dbm.open(path_to_use, 'r') as db:
            for key in db.keys():
                if key.startswith(b'__'): continue
                category = key.decode('utf-8').split('/', 1)[0]
                categories[category] += 1
        return categories

    def _on_analyze_done(self, result):
        if isinstance(result, Exception):
            self._handle_error(f"分析失败", result)
            self.status_var.set("分类分析失败。")
        else:
            self.analysis_data = result
            total = sum(self.analysis_data.values())
            result_text = f"总资产数: {total}\n\n--- 各分类资产数量 (按数量降序) ---\n"
            result_text += "\n".join([f"{cat:<25} : {num}" for cat, num in self.analysis_data.most_common()])
            
            self.analysis_text.config(state='normal')
            self.analysis_text.delete('1.0', tk.END)
            self.analysis_text.insert('1.0', result_text)
            self.analysis_text.config(state='disabled')
            
            self.status_var.set("分类统计完成，可进行可视化分析。")
            self._log(f"分类统计完成: {len(self.analysis_data)}个分类, {total}个总资产。")
        self._update_ui_state()

    def on_listbox_select(self, event):
        selection = self.listbox.curselection()
        if not selection:
            self.current_selected_path = None
            return
        selected_path = self.listbox.get(selection[0])
        self.current_selected_path = selected_path
        self.display_asset_details(selected_path)

    def display_asset_details(self, path):
        try:
            with dbm.open(self.db_file_path, 'r') as db:
                value_str = db[path.encode('utf-8')].decode('utf-8')
            parts = value_str.split('|')
            h = parts[0] if parts else ""
            s = parts[1] if len(parts) > 1 else ""
            self.detail_path_var.set(path)
            self.detail_hash_var.set(h)
            self.detail_size_var.set(s)
            if self.detailed_log_var.get(): self._log(f"显示详情: {path}")
        except KeyError:
             self._handle_error(f"在数据库中没找到这个: {path}")
        except Exception as e:
            self._handle_error(f"没法检索详情", e)
    
    def display_text_details(self, text):
        self.detail_path_var.set(text)
        self.detail_hash_var.set("")
        self.detail_size_var.set("")

    def save_modification(self):
        if not self.current_selected_path or not self.db_file_path:
            self._handle_error("没有选中任何要修改的项。")
            return
        
        path = self.current_selected_path
        new_hash = self.detail_hash_var.get()
        new_size = self.detail_size_var.get()
        new_value = f"{new_hash}|{new_size}"

        try:
            with dbm.open(self.db_file_path, 'c') as db:
                db[path.encode('utf-8')] = new_value.encode('utf-8')
            message = f"成功修改: {os.path.basename(path)}"
            self.status_var.set(message)
            self._log(message)
            messagebox.showinfo("成功", message)
        except Exception as e:
            self._handle_error("修改数据库失败", e)

    def export_to_json(self):
        if not self.db_file_path: return
        
        file_path = filedialog.asksaveasfilename(
            title="导出为JSON", defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if not file_path: return

        self._start_long_task(
            task_worker=lambda: self._export_to_json_worker(file_path),
            on_done_callback=self._on_export_done,
            progress_title="正在导出为JSON..."
        )

    def _export_to_json_worker(self, file_path):
        with dbm.open(self.db_file_path, 'r') as db:
            strategy_name_bytes = db.get(b'__parsing_strategy__')
            if not strategy_name_bytes:
                raise KeyError("数据库中未找到解析策略信息，无法确定导出格式。")
            strategy_name = strategy_name_bytes.decode('utf-8')
            items = {k.decode('utf-8'): v.decode('utf-8') for k, v in db.items() if not k.startswith(b'__')}

        json_data = {}
        if strategy_name == '_parse_asset_hash_list':
            json_data['assetHashList'] = [f"{path}|{value}" for path, value in items.items()]
        elif strategy_name == '_parse_unity_addressables_catalog':
            placeholder = "{PlatformUtils.AddressableLoadPath}/"
            json_data['m_InternalIds'] = [placeholder + path for path in items.keys()]
        else:
            raise ValueError(f"未知的解析策略 '{strategy_name}'。")
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        return file_path
    
    def _on_export_done(self, result):
        if isinstance(result, Exception):
            self._handle_error(f"导出失败", result)
            self.status_var.set("导出JSON失败。")
        else:
            file_path = result
            message = f"成功导出到: {os.path.basename(file_path)}"
            self.status_var.set(message)
            self._log(message)
            messagebox.showinfo("成功", message)

    def save_search_results(self):
        if self.listbox.size() == 0:
            messagebox.showwarning("提示", "没有可保存的搜索结果。")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="保存搜索结果", defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv")])
        if not file_path: return

        results = self.listbox.get(0, tk.END)
        try:
            if file_path.lower().endswith('.csv'):
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(['path'])
                    for item in results:
                        writer.writerow([item])
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(results))
            messagebox.showinfo("成功", f"结果已保存至:\n{file_path}")
        except Exception as e:
            self._handle_error("保存结果失败", e)

    def save_analysis_results(self):
        if not self.analysis_data:
            messagebox.showwarning("提示", "没有可保存的分析结果。")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存统计结果", defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv")])
        if not file_path: return

        try:
            if file_path.lower().endswith('.csv'):
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Category', 'Count'])
                    for cat, num in self.analysis_data.most_common():
                        writer.writerow([cat, num])
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.analysis_text.get('1.0', tk.END))
            messagebox.showinfo("成功", f"结果已保存至:\n{file_path}")
        except Exception as e:
            self._handle_error("保存结果失败", e)

    def show_visualization_window(self):
        if not self.analysis_data: self._handle_error("请先加载数据库并完成分析。"); return
        self._log("打开可视化分析窗口。")
        PlottingWindow(self.master, self.analysis_data)
        
    def show_explorer_window(self):
        if not self.db_file_path: self._handle_error("请先加载数据库。"); return
        self._log("打开目录浏览器窗口。")
        DirectoryExplorerWindow(self.master, self)
        
    def show_stripper_tool(self):
        self._log("打开UnityFS抹除工具。")
        UnityFSStripperWindow(self.master, self)
    
    def show_compare_db_window(self):
        if not self.db_file_path: self._handle_error("请先加载数据库。"); return
        self._log("打开对比数据库窗口。")
        CompareDBWindow(self.master, self)

    def show_luajit_decompiler_window(self):
        self._log("打开LuaJIT工具。")
        LuaJITDecompilerWindow(self.master, self)

def main():
    app_instance = None
    try:
        warnings = []
        if not MATPLOTLIB_AVAILABLE:
            warnings.append("没找到matplotlib库\n")
        if not LJD_AVAILABLE:
            warnings.append("没找到ljd库\n)")
        
        if warnings:
            root_temp = tk.Tk()
            root_temp.withdraw()
            messagebox.showwarning("依赖缺失", "\n\n".join(warnings))
            root_temp.destroy()

        root = tk.Tk()
        app_instance = AssetAnalyzerApp(root)
        def on_closing():
            if app_instance:
                app_instance._log("应用程序关闭。")
                if app_instance.log_file and not app_instance.log_file.closed:
                    app_instance.log_file.close()
            root.destroy()
        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
    except Exception as e:
        error_message = f"因为v2到现在还没有心链，所以软件要崩溃了。\n\n错误信息:\n{traceback.format_exc()}"
        print(error_message)
        if app_instance and app_instance.logging_enabled:
            app_instance._log("="*20 + " 致命错误 " + "="*20)
            app_instance._log(error_message)
        try:
            messagebox.showerror("致命错误", error_message)
        except tk.TclError: 
            pass

if __name__ == "__main__":
    main()
