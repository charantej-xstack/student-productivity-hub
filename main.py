"""
Student Productivity Hub  -  Tkinter project (Advanced Programming Practice)

Run:  python main.py

Modules
  1. Login / Register     (hashed passwords, SQLite)
  2. Dashboard            (live stats, progress bar, upcoming deadlines)
  3. Task Manager         (Treeview, OptionMenu, Menubutton sort, context menu)
  4. Pomodoro Timer       (Canvas progress ring, Scale + Spinbox, after() countdown)
  5. Notes                (PanedWindow, Listbox + Text, search, import / export)
  6. App shell            (menu bar, Toplevel About window, status bar, shortcuts)
"""

import csv
import os
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk, messagebox, filedialog, simpledialog

from database import Database

BG = "#f3f4f6"
ACCENT = "#4f46e5"
TEXT = "#111827"
MUTED = "#6b7280"
RED = "#dc2626"
GREEN = "#16a34a"
ORANGE = "#ea580c"

# a tiny 8x8 black-and-white bitmap (XBM format) used with BitmapImage
DIAMOND_XBM = """#define d_width 8
#define d_height 8
static unsigned char d_bits[] = {
   0x18, 0x3c, 0x7e, 0xff, 0xff, 0x7e, 0x3c, 0x18 };
"""


def set_status(widget, text):
    """Show a message in the status bar of whichever window owns `widget`."""
    top = widget.winfo_toplevel()
    if hasattr(top, "status"):
        top.status.set(text)


def make_logo():
    """Draw a 64x64 app logo (purple square + white tick) with PhotoImage.put()."""
    img = tk.PhotoImage(width=64, height=64)
    img.put(ACCENT, to=(0, 0, 64, 64))
    for i in range(12):                       # short stroke of the tick
        img.put("white", to=(14 + i, 32 + i, 19 + i, 37 + i))
    for i in range(26):                       # long stroke of the tick
        img.put("white", to=(26 + i, 44 - i, 31 + i, 49 - i))
    return img


# ===========================================================================
# 1. LOGIN / REGISTER
# ===========================================================================
class LoginFrame(ttk.Frame):
    def __init__(self, parent, db, on_login):
        super().__init__(parent)
        self.db, self.on_login = db, on_login

        box = tk.Frame(self, bg="white", highlightbackground="#e5e7eb",
                       highlightthickness=1, padx=40, pady=30)
        box.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(box, text="Student Productivity Hub", bg="white", fg=ACCENT,
                 font=("Segoe UI", 20, "bold")).grid(row=0, column=0, columnspan=2)
        tk.Label(box, text="Tasks  |  Focus Timer  |  Notes", bg="white", fg=MUTED,
                 font=("Segoe UI", 10)).grid(row=1, column=0, columnspan=2, pady=(0, 20))

        tk.Label(box, text="Username", bg="white").grid(row=2, column=0, sticky="w")
        self.user_var = tk.StringVar()
        self.user_entry = ttk.Entry(box, textvariable=self.user_var, width=30)
        self.user_entry.grid(row=3, column=0, columnspan=2, pady=(0, 10))

        tk.Label(box, text="Password", bg="white").grid(row=4, column=0, sticky="w")
        self.pass_var = tk.StringVar()
        self.pass_entry = ttk.Entry(box, textvariable=self.pass_var, show="*", width=30)
        self.pass_entry.grid(row=5, column=0, columnspan=2)

        self.show_var = tk.BooleanVar(value=False)
        tk.Checkbutton(box, text="Show password", variable=self.show_var, bg="white",
                       command=self._toggle_password).grid(row=6, column=0, sticky="w", pady=6)

        ttk.Button(box, text="Login", command=self.login).grid(row=7, column=0, sticky="ew", padx=(0, 4), pady=(10, 0))
        ttk.Button(box, text="Register", command=self.register).grid(row=7, column=1, sticky="ew", padx=(4, 0), pady=(10, 0))

        self.user_entry.focus()                 # keyboard focus starts in the username box
        # pressing Enter anywhere on this screen logs in
        self.bind_all("<Return>", self._enter_pressed)

    def _enter_pressed(self, _event):
        if self.winfo_exists() and self.winfo_ismapped():
            self.login()

    def _toggle_password(self):
        self.pass_entry.config(show="" if self.show_var.get() else "*")

    def _credentials(self):
        username, password = self.user_var.get().strip(), self.pass_var.get()
        if not username or not password:
            messagebox.showwarning("Missing details", "Please enter username and password.")
            return None
        return username, password

    def login(self):
        creds = self._credentials()
        if not creds:
            return
        uid = self.db.login(*creds)
        if uid is None:
            messagebox.showerror("Login failed", "Wrong username or password.")
        else:
            self.unbind_all("<Return>")
            self.on_login(uid, creds[0])

    def register(self):
        creds = self._credentials()
        if not creds:
            return
        if len(creds[1]) < 4:
            messagebox.showwarning("Weak password", "Use at least 4 characters.")
        elif self.db.register(*creds):
            messagebox.showinfo("Success", "Account created. You can log in now.")
        else:
            messagebox.showerror("Error", "That username is already taken.")


# ===========================================================================
# 2. DASHBOARD
# ===========================================================================
class DashboardTab(ttk.Frame):
    def __init__(self, parent, db, uid, username):
        super().__init__(parent)
        self.db, self.uid = db, uid

        tk.Label(self, text=f"Welcome, {username}!", font=("Segoe UI", 20, "bold"),
                 fg=TEXT, bg=BG).pack(anchor="w", padx=20, pady=(20, 0))
        tk.Label(self, text=date.today().strftime("%A, %d %B %Y"), fg=MUTED, bg=BG,
                 font=("Segoe UI", 11)).pack(anchor="w", padx=20, pady=(0, 14))

        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=12)
        self.v_pending = self._card(row, "Pending tasks", 0)
        self.v_done = self._card(row, "Completed tasks", 1)
        self.v_focus = self._card(row, "Focus minutes today", 2)
        self.v_pomo = self._card(row, "Pomodoros today", 3)

        tk.Label(self, text="Overall task progress", bg=BG, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=20, pady=(20, 4))
        self.progress = ttk.Progressbar(self, length=400, maximum=100)
        self.progress.pack(fill="x", padx=20)
        self.progress_lbl = tk.Label(self, bg=BG, fg=MUTED)
        self.progress_lbl.pack(anchor="w", padx=20)

        tk.Label(self, text="Upcoming deadlines", bg=BG, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=20, pady=(18, 4))
        self.upcoming = tk.Listbox(self, height=6, font=("Segoe UI", 10),
                                   relief="flat", highlightthickness=1,
                                   highlightbackground="#e5e7eb")
        self.upcoming.pack(fill="x", padx=20)
        self.refresh()

    def _card(self, parent, title, col):
        parent.columnconfigure(col, weight=1)
        f = tk.Frame(parent, bg="white", highlightbackground="#e5e7eb", highlightthickness=1)
        f.grid(row=0, column=col, padx=8, sticky="nsew")
        value = tk.Label(f, text="0", font=("Segoe UI", 26, "bold"), bg="white", fg=ACCENT)
        value.pack(pady=(14, 0))
        tk.Label(f, text=title, bg="white", fg=MUTED, font=("Segoe UI", 10)).pack(pady=(0, 14))
        return value

    def refresh(self):
        s = self.db.stats(self.uid)
        self.v_pending.config(text=s["pending"])
        self.v_done.config(text=s["done"])
        self.v_focus.config(text=s["focus_minutes_today"])
        self.v_pomo.config(text=s["pomodoros_today"])
        pct = (s["done"] / s["total"] * 100) if s["total"] else 0
        self.progress["value"] = pct
        self.progress_lbl.config(text=f"{s['done']} of {s['total']} tasks done ({pct:.0f}%)")

        self.upcoming.delete(0, "end")
        rows = self.db.upcoming(self.uid)
        if not rows:
            self.upcoming.insert("end", "  No upcoming deadlines")
        for r in rows:
            self.upcoming.insert("end", f"  {r['due_date']}    {r['title']}")


# ===========================================================================
# 3. TASK MANAGER
# ===========================================================================
class TasksTab(ttk.Frame):
    PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}

    def __init__(self, parent, db, uid):
        super().__init__(parent)
        self.db, self.uid = db, uid
        self.editing_id = None
        self._build()
        self.refresh()

    def _build(self):
        form = ttk.LabelFrame(self, text=" Add / Edit task ")
        form.pack(fill="x", padx=14, pady=10)

        ttk.Label(form, text="Task:").grid(row=0, column=0, padx=6, pady=8)
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(form, textvariable=self.title_var, width=34)
        self.title_entry.grid(row=0, column=1, padx=4)
        self.title_entry.bind("<Return>", lambda e: self.save_task())

        ttk.Label(form, text="Priority:").grid(row=0, column=2, padx=(12, 4))
        self.prio_var = tk.StringVar(value="Medium")
        prio = tk.OptionMenu(form, self.prio_var, "High", "Medium", "Low")   # OptionMenu widget
        prio.config(width=8)
        prio.grid(row=0, column=3)

        ttk.Label(form, text="Due (YYYY-MM-DD):").grid(row=0, column=4, padx=(12, 4))
        self.due_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.due_var, width=12).grid(row=0, column=5)

        self.save_btn = ttk.Button(form, text="Add Task", command=self.save_task)
        self.save_btn.grid(row=0, column=6, padx=(12, 4))
        ttk.Button(form, text="Clear", command=self.clear_form).grid(row=0, column=7, padx=(0, 8))

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=14)
        ttk.Label(bar, text="Show:").pack(side="left")
        self.filter_var = tk.StringVar(value="All")
        f = ttk.Combobox(bar, textvariable=self.filter_var, state="readonly", width=9,
                         values=["All", "Pending", "Done"])
        f.pack(side="left", padx=6)
        f.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        # Menubutton: a button that drops down a menu of radio choices
        self.sort_var = tk.StringVar(value="Priority")
        self.sort_btn = ttk.Menubutton(bar, text="Sort by: Priority")
        sort_menu = tk.Menu(self.sort_btn, tearoff=0)
        for option in ("Priority", "Due date", "Title"):
            sort_menu.add_radiobutton(label=option, variable=self.sort_var,
                                      value=option, command=self.refresh)
        self.sort_btn["menu"] = sort_menu
        self.sort_btn.pack(side="left", padx=14)

        cols = ("title", "priority", "due", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        for col, text, w in (("title", "Task", 380), ("priority", "Priority", 90),
                             ("due", "Due date", 110), ("status", "Status", 90)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor="w" if col == "title" else "center")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=8)
        sb.pack(side="left", fill="y", pady=8)
        self.tree.tag_configure("done", foreground="#9ca3af")
        self.tree.tag_configure("overdue", foreground=RED)
        self.tree.tag_configure("high", foreground=ORANGE)

        # mouse + keyboard events
        self.tree.bind("<Double-1>", lambda e: self.toggle_done())
        self.tree.bind("<Delete>", lambda e: self.delete_task())
        for seq in ("<Button-3>", "<Button-2>"):          # right-click (Windows/Linux, macOS)
            self.tree.bind(seq, self.show_context_menu)
        self.context = tk.Menu(self, tearoff=0)
        self.context.add_command(label="Mark Done / Undo", command=self.toggle_done)
        self.context.add_command(label="Edit", command=self.edit_task)
        self.context.add_separator()
        self.context.add_command(label="Delete", command=self.delete_task)

        side = ttk.Frame(self)
        side.pack(side="left", fill="y", padx=14, pady=8)
        ttk.Button(side, text="Mark Done / Undo", command=self.toggle_done).pack(fill="x", pady=3)
        ttk.Button(side, text="Edit Selected", command=self.edit_task).pack(fill="x", pady=3)
        ttk.Button(side, text="Delete Selected", command=self.delete_task).pack(fill="x", pady=3)
        ttk.Separator(side, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(side, text="Copy Task List", command=self.copy_list).pack(fill="x", pady=3)
        ttk.Button(side, text="Export to CSV...", command=self.export_csv).pack(fill="x", pady=3)
        ttk.Label(side, text="Tips:\nDouble-click = done\nRight-click = menu\n\nRed = overdue\nOrange = high priority",
                  foreground=MUTED, justify="left").pack(pady=12)

    # ------------------------------------------------------------ actions
    def selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a task", "Please select a task first.")
            return None
        return int(sel[0])

    def show_context_menu(self, event):
        row = self.tree.identify_row(event.y)             # which row is under the mouse?
        if row:
            self.tree.selection_set(row)
            try:
                self.context.tk_popup(event.x_root, event.y_root)
            finally:
                self.context.grab_release()

    def clear_form(self):
        self.editing_id = None
        self.title_var.set("")
        self.due_var.set("")
        self.prio_var.set("Medium")
        self.save_btn.config(text="Add Task")
        self.title_entry.focus_set()

    def save_task(self):
        title, due = self.title_var.get().strip(), self.due_var.get().strip()
        if not title:
            messagebox.showwarning("Missing title", "Please type a task name.")
            return
        if due:
            try:
                datetime.strptime(due, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Invalid date", "Use the format YYYY-MM-DD, e.g. 2026-11-05.")
                return
        if self.editing_id:
            self.db.update_task(self.editing_id, title, self.prio_var.get(), due)
            set_status(self, f"Task updated: {title}")
        else:
            self.db.add_task(self.uid, title, self.prio_var.get(), due)
            set_status(self, f"Task added: {title}")
        self.clear_form()
        self.refresh()

    def quick_add(self):
        """Simple dialog (simpledialog) asking for just a task name."""
        title = simpledialog.askstring("Quick add task", "Task name:", parent=self.winfo_toplevel())
        if title and title.strip():
            self.db.add_task(self.uid, title.strip(), "Medium", "")
            self.refresh()
            set_status(self, f"Task added: {title.strip()}")

    def edit_task(self):
        tid = self.selected_id()
        if tid is None:
            return
        vals = self.tree.item(str(tid), "values")
        self.editing_id = tid
        self.title_var.set(vals[0])
        self.prio_var.set(vals[1])
        self.due_var.set("" if vals[2] == "-" else vals[2])
        self.save_btn.config(text="Update Task")
        self.title_entry.focus_set()

    def toggle_done(self):
        tid = self.selected_id()
        if tid is None:
            return
        done = self.tree.item(str(tid), "values")[3] == "Done"
        self.db.set_done(tid, not done)
        self.refresh()
        set_status(self, "Task marked pending" if done else "Task marked done")

    def delete_task(self):
        tid = self.selected_id()
        if tid is not None and messagebox.askyesno("Delete", "Delete this task permanently?"):
            self.db.delete_task(tid)
            if self.editing_id == tid:
                self.clear_form()
            self.refresh()
            set_status(self, "Task deleted")

    def copy_list(self):
        """Put the visible task list on the system clipboard."""
        lines = []
        for iid in self.tree.get_children():
            title, prio, due, status = self.tree.item(iid, "values")
            lines.append(f"[{'x' if status == 'Done' else ' '}] {title}  ({prio}, due {due})")
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        set_status(self, f"Copied {len(lines)} tasks to the clipboard")

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            title="Export tasks", defaultextension=".csv", initialfile="tasks.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:                                       # user pressed Cancel
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Task", "Priority", "Due date", "Status"])
                for r in self.db.get_tasks(self.uid):
                    writer.writerow([r["title"], r["priority"], r["due_date"] or "",
                                     "Done" if r["done"] else "Pending"])
        except OSError as e:
            messagebox.showerror("Export failed", str(e))
            return
        set_status(self, f"Tasks exported to {os.path.basename(path)}")

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        today = date.today().isoformat()
        rank, mode = self.PRIORITY_RANK, self.sort_var.get()
        keys = {
            "Priority": lambda r: (r["done"], rank[r["priority"]], r["due_date"] or "9999"),
            "Due date": lambda r: (r["done"], r["due_date"] or "9999", rank[r["priority"]]),
            "Title": lambda r: (r["done"], r["title"].lower()),
        }
        self.sort_btn.config(text=f"Sort by: {mode}")
        for r in sorted(self.db.get_tasks(self.uid, self.filter_var.get()), key=keys[mode]):
            tags = []
            if r["done"]:
                tags.append("done")
            elif r["due_date"] and r["due_date"] < today:
                tags.append("overdue")
            elif r["priority"] == "High":
                tags.append("high")
            self.tree.insert("", "end", iid=str(r["id"]), tags=tags,
                             values=(r["title"], r["priority"], r["due_date"] or "-",
                                     "Done" if r["done"] else "Pending"))


# ===========================================================================
# 4. POMODORO TIMER
# ===========================================================================
class PomodoroTab(ttk.Frame):
    SHORT, LONG = 5, 15

    def __init__(self, parent, db, uid):
        super().__init__(parent)
        self.db, self.uid = db, uid
        self.mode = "Focus"
        self.total = self.remaining = 25 * 60
        self.running = False
        self.job = None
        self.cycle = 0                         # completed focus sessions in a row
        self.focus_len = tk.IntVar(value=25)   # shared by the Spinbox AND the Scale
        self.sound_var = tk.BooleanVar(value=True)

        modes = ttk.Frame(self)
        modes.pack(pady=(20, 6))
        self.mode_var = tk.StringVar(value="Focus")
        for m in ("Focus", "Short Break", "Long Break"):
            ttk.Radiobutton(modes, text=m, value=m, variable=self.mode_var,
                            command=lambda: self.set_mode(self.mode_var.get())).pack(side="left", padx=10)

        self.canvas = tk.Canvas(self, width=280, height=280, bg=BG, highlightthickness=0)
        self.canvas.pack(pady=6)

        opts = ttk.Frame(self)
        opts.pack()
        ttk.Label(opts, text="Focus length (min):").pack(side="left")
        ttk.Spinbox(opts, from_=1, to=120, width=5, textvariable=self.focus_len,
                    command=self.reset).pack(side="left", padx=6)
        tk.Scale(opts, from_=1, to=120, orient="horizontal", variable=self.focus_len,
                 length=170, showvalue=False, bg=BG, highlightthickness=0,
                 command=lambda value: self.reset()).pack(side="left", padx=6)
        ttk.Checkbutton(opts, text="Sound alert", variable=self.sound_var).pack(side="left", padx=10)

        btns = ttk.Frame(self)
        btns.pack(pady=12)
        ttk.Button(btns, text="Start", command=self.start).pack(side="left", padx=5)
        ttk.Button(btns, text="Pause", command=self.pause).pack(side="left", padx=5)
        ttk.Button(btns, text="Reset", command=self.reset).pack(side="left", padx=5)

        self.info = ttk.Label(self, text="", font=("Segoe UI", 11))
        self.info.pack()
        self.draw()
        self.refresh()

    def minutes_for(self, mode):
        if mode == "Focus":
            try:
                return max(1, int(self.focus_len.get()))
            except (tk.TclError, ValueError):
                return 25
        return self.SHORT if mode == "Short Break" else self.LONG

    def set_mode(self, mode):
        self._stop()
        self.mode = mode
        self.mode_var.set(mode)
        self.total = self.remaining = self.minutes_for(mode) * 60
        self.draw()

    def draw(self):
        c = self.canvas
        c.delete("all")
        colour = ACCENT if self.mode == "Focus" else GREEN
        c.create_oval(20, 20, 260, 260, outline="#d1d5db", width=14)
        extent = 359.9 * self.remaining / self.total
        c.create_arc(20, 20, 260, 260, start=90, extent=extent, style="arc",
                     outline=colour, width=14)
        m, s = divmod(self.remaining, 60)
        c.create_text(140, 130, text=f"{m:02d}:{s:02d}", font=("Segoe UI", 40, "bold"), fill=TEXT)
        c.create_text(140, 180, text=self.mode, font=("Segoe UI", 12), fill=MUTED)

    def _stop(self):
        self.running = False
        if self.job:
            self.after_cancel(self.job)
            self.job = None

    def start(self):
        if not self.running:
            self.running = True
            set_status(self, f"{self.mode} timer started")
            self._tick()

    def pause(self):
        self._stop()
        set_status(self, "Timer paused")

    def reset(self):
        self.set_mode(self.mode)

    def _tick(self):
        if not self.running:
            return
        if self.remaining <= 0:
            self._finished()
            return
        self.remaining -= 1
        self.draw()
        self.job = self.after(1000, self._tick)

    def _finished(self):
        self._stop()
        if self.sound_var.get():
            self.bell()
        if self.mode == "Focus":
            self.db.log_session(self.uid, self.total // 60)
            self.cycle += 1
            nxt = "Long Break" if self.cycle % 4 == 0 else "Short Break"
            messagebox.showinfo("Focus session complete", f"Great work! Time for a {nxt.lower()}.")
        else:
            nxt = "Focus"
            messagebox.showinfo("Break over", "Break finished. Ready to focus?")
        self.set_mode(nxt)
        self.refresh()

    def refresh(self):
        s = self.db.stats(self.uid)
        self.info.config(text=f"Today: {s['pomodoros_today']} sessions, "
                              f"{s['focus_minutes_today']} focus minutes")

    def destroy(self):
        self._stop()                           # cancel pending after() on logout
        super().destroy()


# ===========================================================================
# 5. NOTES
# ===========================================================================
class NotesTab(ttk.Frame):
    def __init__(self, parent, db, uid):
        super().__init__(parent)
        self.db, self.uid = db, uid
        self.current_id = None
        self.note_ids = []                     # listbox row -> note id
        self._build()
        self.refresh()

    def _build(self):
        # PanedWindow: the user can drag the divider between the two halves
        pane = tk.PanedWindow(self, orient="horizontal", sashwidth=6, bd=0, bg="#d1d5db")
        pane.pack(fill="both", expand=True, padx=14, pady=12)
        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, minsize=200)
        pane.add(right, minsize=320)

        ttk.Label(left, text="Search notes:").pack(anchor="w")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        self.search_entry = ttk.Entry(left, textvariable=self.search_var, width=28)
        self.search_entry.pack(fill="x", pady=4)
        self.listbox = tk.Listbox(left, width=30, exportselection=False,
                                  font=("Segoe UI", 10), activestyle="none")
        self.listbox.pack(fill="both", expand=True, pady=4)
        self.listbox.bind("<<ListboxSelect>>", self.open_note)

        ttk.Label(right, text="Title:").pack(anchor="w", padx=(8, 0))
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(right, textvariable=self.title_var)
        self.title_entry.pack(fill="x", pady=4, padx=(8, 0))

        box = ttk.Frame(right)
        box.pack(fill="both", expand=True, pady=4, padx=(8, 0))
        self.text = tk.Text(box, wrap="word", font=("Segoe UI", 11), undo=True)
        sb = ttk.Scrollbar(box, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=4, padx=(8, 0))
        ttk.Button(btns, text="New Note", command=self.new_note).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Save", command=self.save_note).pack(side="left", padx=6)
        ttk.Button(btns, text="Delete", command=self.delete_note).pack(side="left", padx=6)
        self.msg = ttk.Label(btns, text="", foreground=MUTED)
        self.msg.pack(side="right")

        self.text.bind("<Control-s>", lambda e: (self.save_note(), "break")[1])
        self.text.bind("<Control-f>", lambda e: (self.search_entry.focus_set(), "break")[1])

    def refresh(self, select_id=None):
        self.listbox.delete(0, "end")
        self.note_ids = []
        for n in self.db.get_notes(self.uid, self.search_var.get().strip()):
            self.listbox.insert("end", n["title"])
            self.note_ids.append(n["id"])
            if n["id"] == select_id:
                self.listbox.selection_set("end")

    def open_note(self, _event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        nid = self.note_ids[sel[0]]
        note = next(n for n in self.db.get_notes(self.uid) if n["id"] == nid)
        self.current_id = nid
        self.title_var.set(note["title"])
        self.text.delete("1.0", "end")
        self.text.insert("1.0", note["content"])
        self.msg.config(text=f"Last saved: {note['updated']}")

    def new_note(self):
        self.current_id = None
        self.title_var.set("")
        self.text.delete("1.0", "end")
        self.listbox.selection_clear(0, "end")
        self.msg.config(text="New note")
        self.title_entry.focus_set()

    def save_note(self):
        title = self.title_var.get().strip() or "Untitled"
        content = self.text.get("1.0", "end-1c")
        if self.current_id:
            self.db.update_note(self.current_id, title, content)
        else:
            self.current_id = self.db.add_note(self.uid, title, content)
        self.refresh(select_id=self.current_id)
        self.msg.config(text="Saved")
        set_status(self, f"Note saved: {title}")

    def delete_note(self):
        if self.current_id and messagebox.askyesno("Delete", "Delete this note permanently?"):
            self.db.delete_note(self.current_id)
            self.new_note()
            self.refresh()
            set_status(self, "Note deleted")

    def copy_note(self):
        """Copy the text of the open note to the clipboard."""
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))
        set_status(self, "Note copied to the clipboard")

    def export_notes(self):
        notes = self.db.get_notes(self.uid)
        if not notes:
            messagebox.showinfo("Nothing to export", "You have no notes yet.")
            return
        path = filedialog.asksaveasfilename(
            title="Export all notes", defaultextension=".txt", initialfile="my_notes.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for n in notes:
                    f.write(f"=== {n['title']}  ({n['updated']}) ===\n{n['content']}\n\n")
        except OSError as e:
            messagebox.showerror("Export failed", str(e))
            return
        set_status(self, f"{len(notes)} notes exported to {os.path.basename(path)}")

    def import_note(self):
        path = filedialog.askopenfilename(
            title="Import a text file as a note",
            filetypes=[("Text files", "*.txt *.md"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            messagebox.showerror("Cannot open file", str(e))
            return
        title = os.path.splitext(os.path.basename(path))[0]
        nid = self.db.add_note(self.uid, title, content)
        self.refresh(select_id=nid)
        self.open_note()
        set_status(self, f"Imported note: {title}")


# ===========================================================================
# 6. ABOUT WINDOW (a second window using Toplevel)
# ===========================================================================
class AboutWindow(tk.Toplevel):
    def __init__(self, parent, logo):
        super().__init__(parent)
        self.title("About")
        self.resizable(False, False)
        self.configure(bg="white", padx=26, pady=20)
        self.transient(parent)                  # stays on top of the main window

        tk.Label(self, image=logo, bg="white").pack()
        tk.Label(self, text="Student Productivity Hub", bg="white", fg=ACCENT,
                 font=("Segoe UI", 16, "bold")).pack(pady=(8, 0))
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=10)

        # Message widget: multi-line text that wraps automatically at `width` pixels
        tk.Message(self, width=330, bg="white", justify="center",
                   text="A desktop app for students to manage tasks, stay focused with a "
                        "Pomodoro timer and keep notes. Built with Python, Tkinter and SQLite "
                        "for the Advanced Programming Practice course.").pack()

        try:                                    # BitmapImage: a 1-bit (two colour) image
            self.bitmap = tk.BitmapImage(data=DIAMOND_XBM, foreground=ACCENT, background="white")
            tk.Label(self, image=self.bitmap, bg="white").pack(pady=8)
        except tk.TclError:
            pass

        # winfo_* methods: ask Tk about the screen and window sizes
        info = (f"Screen: {parent.winfo_screenwidth()} x {parent.winfo_screenheight()}   |   "
                f"Window: {parent.winfo_width()} x {parent.winfo_height()}")
        tk.Label(self, text=info, bg="white", fg=MUTED, font=("Segoe UI", 9)).pack()
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=(14, 0))

        self.update_idletasks()                 # make Tk calculate the final size first
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")              # centre it over the main window
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()                         # modal: block the main window until closed
        self.focus_set()


# ===========================================================================
# MAIN WINDOW
# ===========================================================================
class HubFrame(ttk.Frame):
    def __init__(self, parent, db, uid, username, on_logout):
        super().__init__(parent)
        header = tk.Frame(self, bg=ACCENT)
        header.pack(fill="x")
        tk.Label(header, text="  Student Productivity Hub", bg=ACCENT, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(side="left", pady=8)
        ttk.Button(header, text="Logout", command=on_logout).pack(side="right", padx=10)
        ttk.Separator(self, orient="horizontal").pack(fill="x")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)
        self.dashboard = DashboardTab(self.tabs, db, uid, username)
        self.tasks = TasksTab(self.tabs, db, uid)
        self.pomodoro = PomodoroTab(self.tabs, db, uid)
        self.notes = NotesTab(self.tabs, db, uid)
        for page, name in ((self.dashboard, "  Dashboard  "), (self.tasks, "  Tasks  "),
                           (self.pomodoro, "  Pomodoro  "), (self.notes, "  Notes  ")):
            self.tabs.add(page, text=name)
        # refresh a tab's numbers every time the user switches to it
        self.tabs.bind("<<NotebookTabChanged>>", self._tab_changed)

    def _tab_changed(self, _event):
        page = self.nametowidget(self.tabs.select())
        if hasattr(page, "refresh"):
            page.refresh()

    def show_tab(self, index):
        self.tabs.select(index)

    def new_note(self):
        self.show_tab(3)
        self.notes.new_note()

    def quick_add_task(self):
        self.show_tab(1)
        self.tasks.quick_add()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Student Productivity Hub")
        self.minsize(900, 600)
        self.configure(bg=BG)

        # window management: centre the window on the screen
        w, h = 980, 640
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.logo = make_logo()                 # keep a reference or Tk garbage-collects it
        self.iconphoto(True, self.logo)         # use it as the window icon

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TNotebook.Tab", padding=(14, 7))
        style.configure("Treeview", rowheight=26, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=5)
        style.configure("TLabelframe", background=BG)

        self.db = Database()
        self.current = None
        self.status = tk.StringVar(value="Welcome! Please log in.")
        self.top_var = tk.BooleanVar(value=False)
        self.full_var = tk.BooleanVar(value=False)

        # status bar with a Sizegrip (the little drag handle to resize the window)
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x")
        ttk.Label(bar, textvariable=self.status, anchor="w",
                  padding=(10, 3)).pack(side="left", fill="x", expand=True)
        ttk.Sizegrip(bar).pack(side="right", anchor="se")

        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.leave_fullscreen)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login()

    # ------------------------------------------------------------ screens
    def _swap(self, frame):
        if self.current:
            self.current.destroy()
        self.current = frame
        frame.pack(fill="both", expand=True)

    def show_login(self):
        self._unbind_shortcuts()
        self.config(menu="")                    # no menu bar on the login screen
        self._swap(LoginFrame(self, self.db, self.show_hub))
        self.status.set("Welcome! Please log in.")

    def show_hub(self, uid, username):
        hub = HubFrame(self, self.db, uid, username, self.logout)
        self._swap(hub)
        self._build_menu(hub)
        self._bind_shortcuts(hub)
        self.status.set(f"Logged in as {username}")

    def logout(self):
        if messagebox.askyesno("Logout", "Log out of your account?"):
            self.show_login()

    # ------------------------------------------------------------ menu bar
    def _build_menu(self, hub):
        bar = tk.Menu(self)

        file_menu = tk.Menu(bar, tearoff=0)
        file_menu.add_command(label="New Note", accelerator="F2", command=hub.new_note)
        file_menu.add_command(label="Quick Add Task...", accelerator="F3", command=hub.quick_add_task)
        file_menu.add_separator()
        file_menu.add_command(label="Import Note from File...", command=hub.notes.import_note)
        file_menu.add_command(label="Export All Notes (.txt)...", command=hub.notes.export_notes)
        file_menu.add_command(label="Export Tasks (.csv)...", command=hub.tasks.export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Logout", command=self.logout)
        file_menu.add_command(label="Exit", command=self.on_close)
        bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(bar, tearoff=0)
        edit_menu.add_command(label="Copy", command=self.copy_text)
        edit_menu.add_command(label="Paste", command=self.paste_text)
        edit_menu.add_separator()
        edit_menu.add_command(label="Copy Current Note", command=hub.notes.copy_note)
        edit_menu.add_command(label="Copy Task List", command=hub.tasks.copy_list)
        bar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(bar, tearoff=0)
        for i, name in enumerate(("Dashboard", "Tasks", "Pomodoro", "Notes")):
            view_menu.add_command(label=name, accelerator=f"Ctrl+{i + 1}",
                                  command=lambda i=i: hub.show_tab(i))
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Always on top", variable=self.top_var,
                                  command=lambda: self.attributes("-topmost", self.top_var.get()))
        view_menu.add_checkbutton(label="Full screen", accelerator="F11",
                                  variable=self.full_var, command=self.apply_fullscreen)
        bar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(bar, tearoff=0)
        help_menu.add_command(label="How to use", command=self.show_help)
        help_menu.add_command(label="About", command=lambda: AboutWindow(self, self.logo))
        bar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=bar)

    def _bind_shortcuts(self, hub):
        for i in range(4):
            self.bind_all(f"<Control-Key-{i + 1}>", lambda e, i=i: hub.show_tab(i))
        self.bind_all("<F2>", lambda e: hub.new_note())
        self.bind_all("<F3>", lambda e: hub.quick_add_task())

    def _unbind_shortcuts(self):
        for seq in ("<Control-Key-1>", "<Control-Key-2>", "<Control-Key-3>",
                    "<Control-Key-4>", "<F2>", "<F3>"):
            self.unbind_all(seq)

    # ------------------------------------------------------------ clipboard
    def _focused(self):
        try:
            return self.focus_get()             # widget that currently has keyboard focus
        except (KeyError, tk.TclError):
            return None

    def copy_text(self):
        w = self._focused()
        try:
            if isinstance(w, tk.Text):
                chunk = w.get("sel.first", "sel.last")
            elif isinstance(w, tk.Entry):
                chunk = w.selection_get()
            else:
                return
        except tk.TclError:                     # nothing is selected
            return
        self.clipboard_clear()
        self.clipboard_append(chunk)
        self.status.set("Copied to the clipboard")

    def paste_text(self):
        w = self._focused()
        try:
            chunk = self.clipboard_get()
        except tk.TclError:
            self.status.set("The clipboard is empty")
            return
        if isinstance(w, (tk.Text, tk.Entry)):
            w.insert("insert", chunk)

    # ------------------------------------------------------------ window management
    def apply_fullscreen(self):
        self.attributes("-fullscreen", self.full_var.get())

    def toggle_fullscreen(self, _event=None):
        self.full_var.set(not self.full_var.get())
        self.apply_fullscreen()

    def leave_fullscreen(self, _event=None):
        if self.full_var.get():
            self.full_var.set(False)
            self.apply_fullscreen()

    # ------------------------------------------------------------ dialogs
    def show_help(self):
        messagebox.showinfo(
            "How to use",
            "Tasks: type a name, pick priority and due date, press Add.\n"
            "Double-click a task to mark it done; right-click for a menu.\n\n"
            "Pomodoro: choose a length, press Start, stay focused.\n\n"
            "Notes: write, then press Save (Ctrl+S). Ctrl+F searches.\n\n"
            "Shortcuts: Ctrl+1..4 switch tabs, F2 new note, F3 quick task, F11 full screen.")

    def on_close(self):
        if messagebox.askokcancel("Exit", "Close the Student Productivity Hub?"):
            self.db.conn.close()
            self.destroy()


if __name__ == "__main__":
    App().mainloop()
