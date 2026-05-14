#!/usr/bin/env python3
"""
Simple GUI for editing the Autopolls config file (~/Desktop/configs).

Run with:
    python3 utils/config_editor.py
    python3 utils/config_editor.py /path/to/configs
"""

import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser('~'), 'Desktop', 'configs')

FIELD_META = {
    'hostname':            {'label': 'Hostname',             'type': 'str',   'tip': 'Device hostname written to /etc/hostname on startup'},
    'model_inference':     {'label': 'Model Inference',      'type': 'bool',  'tip': 'Enable/disable TFLite inference'},
    'classes':             {'label': 'Classes',              'type': 'choice','choices': ['single', 'multi'], 'tip': 'single = one bee class; multi = multiple insect classes'},
    'coral':               {'label': 'Coral Edge TPU',       'type': 'bool',  'tip': 'Use a Coral USB Edge TPU accelerator'},
    'threshold':           {'label': 'Detection Threshold',  'type': 'float', 'min': 0.0, 'max': 1.0, 'tip': 'Minimum confidence score to trigger a detection (0.0–1.0)'},
    'periodic_still':      {'label': 'Periodic Still (s)',   'type': 'int',   'min': 1,   'max': 3600, 'tip': 'Save a still image every N seconds'},
    'autofocus':           {'label': 'Autofocus',            'type': 'bool',  'tip': 'Enable camera autofocus'},
    'focus':               {'label': 'Focus Position',       'type': 'int',   'min': 1,   'max': 999,  'tip': 'Manual focus value (1–999; larger = closer)'},
    'csv':                 {'label': 'Save CSV',             'type': 'bool',  'tip': 'Save detection results as CSV (instead of JSON)'},
    'save_all_detections': {'label': 'Save All Detections',  'type': 'bool',  'tip': 'Save every detection frame, not just triggered events'},
}

FIELD_ORDER = [
    'hostname', 'model_inference', 'classes', 'coral',
    'threshold', 'periodic_still', 'autofocus', 'focus',
    'csv', 'save_all_detections',
]


class ConfigEditor(tk.Tk):
    def __init__(self, config_path):
        super().__init__()
        self.title('Autopolls Config Editor')
        self.resizable(False, False)

        self.config_path = config_path
        self.data = {}
        self.widgets = {}

        self._build_menu()
        self._build_header()
        self._build_fields()
        self._build_footer()

        self.load_config(self.config_path)

    # ------------------------------------------------------------------
    def _build_menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label='Open...', command=self._open_file)
        file_menu.add_command(label='Save',    command=self._save)
        file_menu.add_command(label='Save As...', command=self._save_as)
        file_menu.add_separator()
        file_menu.add_command(label='Quit',    command=self.quit)
        menu.add_cascade(label='File', menu=file_menu)
        self.config(menu=menu)

    def _build_header(self):
        hdr = tk.Frame(self, bg='#2e7d32', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text='Autopolls Config Editor', bg='#2e7d32',
                 fg='white', font=('Helvetica', 14, 'bold')).pack()
        self.path_label = tk.Label(hdr, text='', bg='#2e7d32', fg='#c8e6c9',
                                   font=('Helvetica', 9))
        self.path_label.pack()

    def _build_fields(self):
        frame = tk.Frame(self, padx=16, pady=12)
        frame.pack(fill='both')

        for row, key in enumerate(FIELD_ORDER):
            meta = FIELD_META.get(key, {'label': key, 'type': 'str', 'tip': ''})
            label = tk.Label(frame, text=meta['label'] + ':', anchor='w', width=22)
            label.grid(row=row, column=0, sticky='w', pady=4)

            widget, var = self._make_widget(frame, meta)
            widget.grid(row=row, column=1, sticky='ew', padx=(8, 0), pady=4)
            self.widgets[key] = (widget, var, meta)

            if meta.get('tip'):
                tip_label = tk.Label(frame, text=meta['tip'], fg='#666',
                                     font=('Helvetica', 8), anchor='w', wraplength=320)
                tip_label.grid(row=row, column=2, sticky='w', padx=(12, 0))

        frame.columnconfigure(1, minsize=160)

    def _make_widget(self, parent, meta):
        t = meta['type']
        if t == 'bool':
            var = tk.IntVar()
            w = tk.Checkbutton(parent, variable=var)
            return w, var
        elif t == 'choice':
            var = tk.StringVar()
            w = ttk.Combobox(parent, textvariable=var,
                             values=meta['choices'], state='readonly', width=14)
            return w, var
        elif t == 'float':
            var = tk.DoubleVar()
            frame = tk.Frame(parent)
            scale = tk.Scale(frame, variable=var, from_=meta['min'], to=meta['max'],
                             resolution=0.01, orient='horizontal', length=140,
                             showvalue=False)
            scale.pack(side='left')
            entry = tk.Entry(frame, textvariable=var, width=6)
            entry.pack(side='left', padx=(6, 0))
            return frame, var
        elif t == 'int':
            var = tk.IntVar()
            w = tk.Spinbox(parent, textvariable=var,
                           from_=meta.get('min', 0), to=meta.get('max', 9999),
                           width=8)
            return w, var
        else:  # str
            var = tk.StringVar()
            w = tk.Entry(parent, textvariable=var, width=24)
            return w, var

    def _build_footer(self):
        footer = tk.Frame(self, pady=10)
        footer.pack(fill='x', padx=16)
        tk.Button(footer, text='Save', command=self._save,
                  bg='#2e7d32', fg='white', padx=16, pady=4,
                  font=('Helvetica', 10, 'bold')).pack(side='right')
        tk.Button(footer, text='Reload', command=lambda: self.load_config(self.config_path),
                  padx=12, pady=4).pack(side='right', padx=(0, 8))

    # ------------------------------------------------------------------
    def load_config(self, path):
        if not os.path.isfile(path):
            messagebox.showwarning(
                'File not found',
                f'Config not found at:\n{path}\n\nStarting with default values.')
            self.data = {k: '' for k in FIELD_ORDER}
        else:
            with open(path) as f:
                self.data = json.load(f)

        self.config_path = path
        self.path_label.config(text=path)

        for key, (widget, var, meta) in self.widgets.items():
            val = self.data.get(key, '')
            try:
                if meta['type'] == 'bool':
                    var.set(1 if val else 0)
                elif meta['type'] == 'choice':
                    var.set(str(val))
                elif meta['type'] == 'float':
                    var.set(float(val) if val != '' else 0.0)
                elif meta['type'] == 'int':
                    var.set(int(val) if val != '' else 0)
                else:
                    var.set(str(val))
            except (ValueError, TypeError):
                var.set(val)

    def _collect(self):
        out = {}
        for key, (widget, var, meta) in self.widgets.items():
            t = meta['type']
            try:
                if t == 'bool':
                    out[key] = int(var.get())
                elif t == 'float':
                    out[key] = round(float(var.get()), 4)
                elif t == 'int':
                    out[key] = int(var.get())
                else:
                    out[key] = var.get()
            except (ValueError, tk.TclError) as e:
                messagebox.showerror('Validation error', f"Invalid value for '{key}': {e}")
                return None
        return out

    def _save(self):
        data = self._collect()
        if data is None:
            return
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent='\t')
        messagebox.showinfo('Saved', f'Config saved to:\n{self.config_path}')

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            title='Save config as',
            initialfile='configs',
            defaultextension='',
            filetypes=[('JSON config', '*'), ('All files', '*.*')],
        )
        if path:
            self.config_path = path
            self.path_label.config(text=path)
            self._save()

    def _open_file(self):
        path = filedialog.askopenfilename(
            title='Open config file',
            initialdir=os.path.dirname(self.config_path),
            filetypes=[('JSON config', '*'), ('All files', '*.*')],
        )
        if path:
            self.load_config(path)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    app = ConfigEditor(path)
    app.mainloop()


if __name__ == '__main__':
    main()
