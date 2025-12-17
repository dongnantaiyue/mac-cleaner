import os
import hashlib
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import shutil
from datetime import datetime
import threading
import ctypes # Windows 专用库，用于解决模糊问题

class DuplicateFinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Windows 重复文件清理工具 (高清版)")
        self.root.geometry("950x650") 

        # --- Windows 专属优化: 解决高分屏模糊问题 ---
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            # 调整缩放因子，让字体在Windows上看起来更舒服
            self.root.tk.call('tk', 'scaling', 1.25)
        except Exception:
            pass
        # ----------------------------------------

        # 样式设置
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        
        # 顶部操作区
        top_frame = tk.Frame(root, pady=10)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10)

        self.btn_scan = tk.Button(top_frame, text="1. 选择文件夹并扫描", command=self.start_scan_thread, height=2, width=20)
        self.btn_scan.pack(side=tk.LEFT, padx=5)

        # 状态信息区 (包含进度条)
        status_frame = tk.Frame(top_frame)
        status_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)

        self.lbl_status = tk.Label(status_frame, text="准备就绪 - 请选择文件夹开始", fg="gray", anchor="w")
        self.lbl_status.pack(fill=tk.X)

        self.progress = ttk.Progressbar(status_frame, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)

        # 中间列表区
        list_frame = tk.Frame(root)
        list_frame.pack(side=tk.TOP, expand=True, fill=tk.BOTH, padx=10, pady=5)

        columns = ("filename", "path", "size", "mod_time")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="none")
        
        self.tree.heading("filename", text="文件名")
        self.tree.heading("path", text="完整路径")
        self.tree.heading("size", text="大小")
        self.tree.heading("mod_time", text="修改时间")
        
        self.tree.column("filename", width=200)
        self.tree.column("path", width=450)
        self.tree.column("size", width=100)
        self.tree.column("mod_time", width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.tree.bind("<Button-1>", self.on_click)

        # 底部操作区
        bottom_frame = tk.Frame(root, pady=10)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10)

        tk.Label(bottom_frame, text="自动标记规则:").pack(side=tk.LEFT)
        tk.Button(bottom_frame, text="保留最早的文件 (删除新的)", command=lambda: self.auto_mark('keep_oldest')).pack(side=tk.LEFT, padx=5)
        tk.Button(bottom_frame, text="保留最新的文件 (删除旧的)", command=lambda: self.auto_mark('keep_newest')).pack(side=tk.LEFT, padx=5)
        
        self.btn_delete = tk.Button(bottom_frame, text="3. 移动选中文件到桌面的“回收文件夹”", command=self.delete_selected, bg="#ffcccc", fg="red")
        self.btn_delete.pack(side=tk.RIGHT, padx=5)

        self.duplicates_data = {} 
        self.check_state = {} 

    def get_file_hash(self, filepath, block_size=65536):
        hasher = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                buf = f.read(block_size)
                while len(buf) > 0:
                    hasher.update(buf)
                    buf = f.read(block_size)
            return hasher.hexdigest()
        except:
            return None

    def start_scan_thread(self):
        folder_selected = filedialog.askdirectory()
        if not folder_selected:
            return
        
        self.tree.delete(*self.tree.get_children())
        self.duplicates_data = {}
        self.check_state = {}
        self.btn_scan.config(state=tk.DISABLED)
        self.progress['value'] = 0
        
        thread = threading.Thread(target=self.scan_files, args=(folder_selected,))
        thread.start()

    def update_ui_progress(self, current, total, message):
        self.root.after(0, lambda: self._do_update_ui(current, total, message))

    def _do_update_ui(self, current, total, message):
        self.lbl_status.config(text=message, fg="blue")
        if total > 0:
            self.progress['maximum'] = total
            self.progress['value'] = current
        else:
            self.progress['mode'] = 'indeterminate'
            self.progress.start(10)

    def scan_files(self, folder):
        all_files = []
        
        self.update_ui_progress(0, 0, "正在遍历目录结构...")
        count = 0
        # Windows 上忽略特定的系统文件夹
        ignore_folders = ['$RECYCLE.BIN', 'System Volume Information', 'Windows']

        for dirpath, dirnames, filenames in os.walk(folder):
            # 过滤掉系统文件夹
            dirnames[:] = [d for d in dirnames if d not in ignore_folders]
            
            for f in filenames:
                full_path = os.path.join(dirpath, f)
                all_files.append(full_path)
                count += 1
                if count % 100 == 0:
                    self.update_ui_progress(0, 0, f"已发现 {count} 个文件...")

        self.root.after(0, lambda: self.progress.stop())
        self.progress['mode'] = 'determinate'
        
        self.update_ui_progress(0, len(all_files), "正在筛选文件大小...")
        file_size_map = {}
        
        for idx, path in enumerate(all_files):
            if idx % 200 == 0:
                self.update_ui_progress(idx, len(all_files), f"分析文件属性: {idx}/{len(all_files)}")
            try:
                size = os.path.getsize(path)
                if size > 0:
                    if size not in file_size_map:
                        file_size_map[size] = []
                    file_size_map[size].append(path)
            except:
                pass

        potential_groups = [paths for size, paths in file_size_map.items() if len(paths) > 1]
        total_files_to_check = sum(len(group) for group in potential_groups)
        
        if total_files_to_check == 0:
            self.root.after(0, lambda: self.scan_finished(0))
            return

        full_duplicates = {}
        total_groups_found = 0
        processed_count = 0

        for group_paths in potential_groups:
            hash_map = {}
            for path in group_paths:
                processed_count += 1
                display_name = os.path.basename(path)
                if len(display_name) > 30: display_name = display_name[:27] + "..."
                self.update_ui_progress(processed_count, total_files_to_check, 
                                      f"深度比对内容 ({processed_count}/{total_files_to_check}): {display_name}")
                
                file_hash = self.get_file_hash(path)
                if not file_hash: continue
                
                if file_hash not in hash_map:
                    hash_map[file_hash] = []
                hash_map[file_hash].append(path)
            
            for h, p_list in hash_map.items():
                if len(p_list) > 1:
                    full_duplicates[h] = []
                    size_val = os.path.getsize(p_list[0])
                    for p in p_list:
                        try:
                            stat = os.stat(p)
                            mod_time = stat.st_mtime
                        except:
                            mod_time = 0
                        
                        full_duplicates[h].append({
                            'path': p,
                            'filename': os.path.basename(p),
                            'size': size_val,
                            'mod_time': mod_time,
                            'mod_time_str': datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M')
                        })
                    total_groups_found += 1

        self.duplicates_data = full_duplicates
        self.root.after(0, lambda: self.scan_finished(total_groups_found))

    def scan_finished(self, count):
        self.populate_tree()
        self.lbl_status.config(text=f"扫描完成，发现 {count} 组重复文件。", fg="green")
        self.progress['value'] = 0
        self.btn_scan.config(state=tk.NORMAL)
        if count == 0:
            messagebox.showinfo("结果", "好消息！未发现重复文件。")

    def populate_tree(self):
        for file_hash, files in self.duplicates_data.items():
            group_id = self.tree.insert("", "end", values=("", f"--- {len(files)} 个重复文件 ---", str(files[0]['size']), ""), open=True)
            self.tree.item(group_id, tags=('group',))
            for f in files:
                item_id = self.tree.insert(group_id, "end", values=(f"☐ {f['filename']}", f['path'], f['size'], f['mod_time_str']))
                self.check_state[item_id] = False

    def on_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "tree":
            item_id = self.tree.identify_row(event.y)
            if self.tree.tag_has('group', item_id):
                return
            current_state = self.check_state.get(item_id, False)
            self.check_state[item_id] = not current_state
            self.update_item_display(item_id)

    def update_item_display(self, item_id):
        is_checked = self.check_state[item_id]
        current_values = self.tree.item(item_id, "values")
        clean_name = current_values[0].replace("☐ ", "").replace("☑ ", "")
        icon = "☑ " if is_checked else "☐ "
        self.tree.item(item_id, values=(icon + clean_name, *current_values[1:]))
        
        if is_checked:
            self.tree.item(item_id, tags=('checked',))
        else:
            self.tree.item(item_id, tags=('unchecked',))
            
        self.tree.tag_configure('checked', foreground='red')
        self.tree.tag_configure('unchecked', foreground='black')

    def auto_mark(self, mode):
        if not self.duplicates_data: return
        for group_id in self.tree.get_children():
            children = self.tree.get_children(group_id)
            if not children: continue
            
            child_items = []
            for child_id in children:
                val = self.tree.item(child_id, "values")
                try:
                    dt = datetime.strptime(val[3], '%Y-%m-%d %H:%M')
                except:
                    dt = datetime.now() # Fallback
                child_items.append({'id': child_id, 'time': dt})
            
            child_items.sort(key=lambda x: x['time'])
            
            keep_id = None
            if mode == 'keep_oldest': keep_id = child_items[0]['id']
            elif mode == 'keep_newest': keep_id = child_items[-1]['id']
                
            for item in child_items:
                is_check = (item['id'] != keep_id)
                self.check_state[item['id']] = is_check
                self.update_item_display(item['id'])

    def delete_selected(self):
        files_to_delete = [item_id for item_id, checked in self.check_state.items() if checked]
        
        if not files_to_delete:
            messagebox.showwarning("提示", "请先勾选需要删除的文件。")
            return

        if not messagebox.askyesno("确认", f"确认将这 {len(files_to_delete)} 个文件移动到桌面回收站吗？"):
            return

        # Windows 桌面路径处理
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        trash_folder = os.path.join(desktop, f"Duplicate_Trash_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        if not os.path.exists(trash_folder):
            try:
                os.makedirs(trash_folder)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建回收文件夹：\n{e}")
                return

        count = 0
        error_count = 0
        
        for item_id in files_to_delete:
            val = self.tree.item(item_id, "values")
            src_path = val[1]
            filename = os.path.basename(src_path)
            dst_path = os.path.join(trash_folder, filename)
            
            if os.path.exists(dst_path):
                base, ext = os.path.splitext(filename)
                dst_path = os.path.join(trash_folder, f"{base}_dup_{count}{ext}")

            try:
                shutil.move(src_path, dst_path)
                self.tree.delete(item_id)
                del self.check_state[item_id]
                count += 1
            except Exception as e:
                print(f"Error: {e}")
                error_count += 1

        msg = f"已移动 {count} 个文件到:\n{trash_folder}"
        if error_count > 0:
            msg += f"\n\n有 {error_count} 个文件移动失败（可能是正在被占用）。"
        messagebox.showinfo("完成", msg)
        
        for group_id in self.tree.get_children():
            if not self.tree.get_children(group_id):
                self.tree.delete(group_id)

if __name__ == "__main__":
    root = tk.Tk()
    app = DuplicateFinderApp(root)
    root.mainloop()
