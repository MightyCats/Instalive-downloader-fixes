# -*- coding: utf-8 -*-
import os, re, json, shutil, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

SETTINGS=os.path.join(os.path.dirname(os.path.abspath(__file__)),"settings.json")
TOKENS=["date","username","id","time","title"]
LABELS={"date":"Date","username":"Username","id":"Stream ID","time":"Time","title":"Title"}
DEFAULT={"main":"","comments":"","output":"","temp":"","order":TOKENS[:],"sep":"_","filename_template":"{date}{time}_{username}@{id}_{title}","datefmt":"%Y%m%d","timefmt":"%H%M%S","use_date":True,"use_username":True,"use_id":True,"use_time":True,"use_title":False,"title":"","suffixes":{"date":"","username":"","id":"","time":"","title":""},"separators":["","","","",""]}

def load():
    try:
        d=json.load(open(SETTINGS,encoding="utf-8"))
        d.setdefault("app_icon","")
        for k in ("js","py"):
            d.setdefault(k,DEFAULT.copy())
            for a,b in DEFAULT.items(): d[k].setdefault(a,b)
        return d
    except: return {"js":DEFAULT.copy(),"py":DEFAULT.copy(),"app_icon":""}

def save(d):
    with open(SETTINGS,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

def pattern(c):
    order=c.get("order", TOKENS)
    separators=c.get("separators")
    if not isinstance(separators, list):
        old=c.get("suffixes", {})
        separators=[old.get(order[i], {"date":"@","username":"_","id":"-"}.get(order[i],"")) for i in range(len(order))]
    parts=[]
    for i,token in enumerate(order):
        if c.get("use_"+token, True):
            parts.append("{"+token+"}")
            if i < len(separators):
                parts.append(str(separators[i]))
    return "".join(parts) or "{username}"

def backup(p):
    q=p+".backup_"+datetime.now().strftime("%Y%m%d_%H%M%S"); shutil.copy2(p,q); return q

def edit_js(p,c):
    s=open(p,encoding="utf-8-sig").read()
    out=os.path.abspath(c["output"] or os.path.dirname(p)).replace("\\", "/")
    tmp=os.path.abspath(c["temp"] or os.path.join(out,"temp")).replace("\\", "/")
    
    s=re.sub(r"const dirname = [^\r\n]*", lambda m: "const dirname = "+json.dumps(out,ensure_ascii=False)+";", s, count=1)
    if "const editorTempDir =" in s:
        s=re.sub(r"const editorTempDir = .*?;", lambda m: "const editorTempDir = "+json.dumps(tmp,ensure_ascii=False)+";", s, count=1)
    else:
        s=re.sub(r"(const dirname = [^\r\n]*)", lambda m: m.group(1)+"\nconst editorTempDir = "+json.dumps(tmp,ensure_ascii=False)+";", s, count=1)
    
    s=s.replace("resolve(dirname, 'temp',", "resolve(editorTempDir,")
    s=s.replace("import { rm } from 'fs/promises'", "import { rm, mkdir } from 'fs/promises'")
    if "await mkdir(editorTempDir" not in s:
        s=s.replace("  const startTime = liveRecorder.startTime","  await mkdir(editorTempDir, { recursive: true })\n  const startTime = liveRecorder.startTime",1)
    b=s.find("  const outputRecordPath")
    a=s.rfind("  let initStatus",0,b) if b>=0 else -1
    if a<0 or b<0: raise ValueError("Could not find the filename configuration section in recordLiveStream.js.")
    t=json.dumps(pattern(c),ensure_ascii=False)
    block="\n".join([
      "  let initStatus",
      "  if (mpdUrl) initStatus = await liveRecorder.initializeWithMpdUrl(mpdUrl)",
      "  else if (userId) initStatus = await liveRecorder.initializeWithUserId(userId)",
      "  else if (username) initStatus = await liveRecorder.initializeWithUsername(username)",
      "  else throw new Error('You need to provide mpdUrl, userId or username')",
      "  const editorNow = new Date()",
      "  const editorPad = n => String(n).padStart(2,'0')",
      "  const editorFmt = (fmt,d) => fmt.replace(/%Y/g,String(d.getFullYear())).replace(/%m/g,editorPad(d.getMonth()+1)).replace(/%d/g,editorPad(d.getDate())).replace(/%H/g,editorPad(d.getHours())).replace(/%M/g,editorPad(d.getMinutes())).replace(/%S/g,editorPad(d.getSeconds()))",
      "  const editorDate = editorFmt("+json.dumps(c["datefmt"])+",editorNow)",
      "  const editorTime = editorFmt("+json.dumps(c["timefmt"])+",editorNow)",
      "  const editorTitle = "+json.dumps(c.get("title",""),ensure_ascii=False)+".replace(/[<>:/\\\\|?*]/g,'_')",
      "  const editorName = "+t+".replace(/\\{date\\}/g,editorDate).replace(/\\{time\\}/g,editorTime).replace(/\\{username\\}/g,String(liveRecorder.username||username||userId||'record')).replace(/\\{id\\}/g,String(liveRecorder.broadcastId||liveRecorder.mediaId||liveRecorder.userId||userId||'unknown')).replace(/\\{title\\}/g,editorTitle)",
      "  const outputRecordFile = `${editorName}.mp4`"
    ])
    s=s[:a]+block+"\n"+s[b:]
    s=s.replace("outputFile.replace(/\\.mp4$/i, '.chat.srt')", "outputFile.replace(/\\.mp4$/i, '.srt')")
    open(p,"w",encoding="utf-8",newline="").write(s)

def edit_py(p,c):
    s=open(p,encoding="utf-8-sig").read()
    out=os.path.abspath(c["output"] or os.path.dirname(p))
    tmp=os.path.abspath(c["temp"] or os.path.join(out,"temp"))
    block="\n".join([
      "# --- settings editor managed block ---",
      "DOWNLOAD_OUTPUT_DIR = "+repr(out),"DOWNLOAD_TEMP_DIR = "+repr(tmp),
      "FILENAME_TEMPLATE = "+repr(pattern(c)),"DATE_FORMAT = "+repr(c["datefmt"]),"TIME_FORMAT = "+repr(c["timefmt"]),
      "def _editor_filename(username, stream_id, epoch, ext):",
      "    from datetime import datetime",
      "    d=datetime.fromtimestamp(int(epoch))",
      "    title="+repr(c.get('title',''))+".replace('/','_').replace('\\\\','_').replace(':','_').replace('*','_').replace('?','_').replace(chr(34),'_').replace('<','_').replace('>','_').replace('|','_')",
      "    v={'date':d.strftime(DATE_FORMAT),'time':d.strftime(TIME_FORMAT),'username':str(username or 'unknown'),'id':str(stream_id or 'unknown'),'title':title}",
      "    return FILENAME_TEMPLATE.format(**v)+ext"
    ])
    if "settings editor managed block" in s:
        s=re.sub(r"\n# --- settings editor managed block ---.*?(?=\nclass Download:)",block,s,flags=re.S)
    else: s=s.replace("class Download:",block+"\nclass Download:",1)
    a=s.find("            self.video_path = os.path.join")
    if a<0: raise ValueError("Could not find the video_path setting in download.py.")
    pos=s.find("self.data_json_path",a)
    close=s.find("self.timestamp))",pos)
    endline=s.find("\n",close if close>=0 else pos)
    if endline<0: raise ValueError("Could not find the data_json_path setting in download.py.")
    newpaths="\n".join([
      "            self.video_path = os.path.join(DOWNLOAD_OUTPUT_DIR,_editor_filename(self.download_user,self.livestream_object_init.get('id'),self.timestamp,'.mp4'))",
      "            self.segments_path = os.path.join(DOWNLOAD_TEMP_DIR,_editor_filename(self.download_user,self.livestream_object_init.get('id'),self.timestamp,'_segments'))",
      "            self.data_generate_comments_path = os.path.join(DOWNLOAD_OUTPUT_DIR,_editor_filename(self.download_user,self.livestream_object_init.get('id'),self.timestamp,'.srt'))",
      "            self.data_json_path = os.path.join(DOWNLOAD_OUTPUT_DIR,_editor_filename(self.download_user,self.livestream_object_init.get('id'),self.timestamp,'.json'))"])
    s=s[:a]+newpaths+s[endline:]
    os.makedirs(out,exist_ok=True); os.makedirs(tmp,exist_ok=True)
    open(p,"w",encoding="utf-8",newline="").write(s)

class App:
 def __init__(self,r):
    self.r=r; r.title("Instagram-live-recorder / Pyinstalive Settings Editor"); r.geometry("1050x550"); r.resizable(False,False); r.minsize(850,350); r.maxsize(1050,550)
    style=ttk.Style(r); style.configure("TNotebook.Tab",font=("Yu Gothic UI",13,"bold")); style.configure("AppTitle.TLabel",font=("Yu Gothic UI",16,"bold")); style.configure("App.TLabel",font=("Yu Gothic UI",10)); style.configure("App.TCheckbutton",font=("Yu Gothic UI",10)); style.configure("App.TButton",font=("Yu Gothic UI",10)); style.configure("App.TEntry",font=("Yu Gothic UI",10)); self.d=load(); self.v={}; self.order_frames={}; self.order_area={}; self.order_vars={}; self.suffix_vars={}; self.separator_vars={}; self.separator_widgets={}; self.preview_funcs={}; self.drag_row={}
    self.nb=ttk.Notebook(r); self.nb.pack(fill="x",expand=False,padx=10,pady=(10,0))
    self.r.bind_all("<B1-Motion>", self.drag_motion_global, add="+")
    self.r.bind_all("<ButtonRelease-1>", self.drag_release_global, add="+")
    for k,label in [("js","Instagram-live-recorder"),("py","Pyinstalive")]:
        f=ttk.Frame(self.nb,padding=12); self.nb.add(f,text=label); self.make_tab(k,f)
    bar=ttk.Frame(r); bar.pack(fill="x",padx=10,pady=(2,3))
    ttk.Button(bar,text="Save Settings",command=self.save).pack(side="left")
    ttk.Button(bar,text="Apply Directly to Script (Creates Backup)",command=self.apply).pack(side="right")
 def path(self,f,k,label,key,isfile):
    row=ttk.Frame(f); row.pack(fill="x",pady=3); ttk.Label(row,text=label,width=24).pack(side="left"); v=tk.StringVar(value=self.d[k].get(key,"")); self.v[k,key]=v; ttk.Entry(row,textvariable=v).pack(side="left",fill="x",expand=True,padx=4)
    def choose():
        q=filedialog.askopenfilename(filetypes=[("Script","*.js;*.py"),("All","*.*")]) if isfile else filedialog.askdirectory()
        if q:v.set(q)
    ttk.Button(row,text="Browse",command=choose).pack(side="left")
 def make_tab(self,k,f):
    script_frame=ttk.LabelFrame(f,text="Script File to Edit",padding=8)
    script_frame.pack(fill="x",pady=(0,6))
    self.path(script_frame,k,"recordLiveStream.js" if k=="js" else "download.py","main",True)
    output_frame=ttk.LabelFrame(f,text="Output Folders",padding=8)
    output_frame.pack(fill="x",pady=(0,6))
    self.path(output_frame,k,"Download Folder","output",False)
    self.path(output_frame,k,"Temporary Files Folder","temp",False)
    ttk.Separator(f).pack(fill="x",pady=5)
    title_var=tk.StringVar(value=self.d[k].get("title","")); self.v[k,"title"]=title_var
    ttk.Label(f,text="Filename Format (drag to reorder; check to include items)",font=("Segoe UI",10,"bold")).pack(anchor="w")
    ttk.Label(f,text="Use the [ ] fields to set the text appended after each item.").pack(anchor="w",pady=(1,3))
    self.order_frames[k]=[]
    self.order_vars[k]={}
    self.suffix_vars[k]={}
    self.separator_vars[k]=[]
    self.separator_widgets[k]=[]
    area=ttk.Frame(f);area.pack(fill="x",pady=1)
    self.order_area[k]=area
    order=self.d[k].get("order",TOKENS[:])
    if "title" not in order: order=order+["title"]
    saved_separators=self.d[k].get("separators")
    if not isinstance(saved_separators,list) or len(saved_separators)!=len(order):
        old_suffixes=self.d[k].get("suffixes",{"date":"","username":"","id":""})
        saved_separators=[old_suffixes.get(order[i],{"date":"","username":"","id":""}.get(order[i],"")) for i in range(len(order))]
    for i,token in enumerate(order):
        self.add_order_row(k,token)
        if i < len(order):
            sep_var=tk.StringVar(value=str(saved_separators[i] if i < len(saved_separators) else ""))
            self.separator_vars[k].append(sep_var)
            sep_frame=ttk.Frame(area)
            ttk.Label(sep_frame,text="[").pack(side="left")
            ttk.Entry(sep_frame,textvariable=sep_var,width=4,justify="center").pack(side="left")
            ttk.Label(sep_frame,text="]").pack(side="left")
            sep_frame.pack(side="left",anchor="w",padx=(1,3),pady=1)
            self.separator_widgets[k].append(sep_frame)
    ttk.Label(f,text="Date and Time Formats").pack(anchor="w",pady=(5,1))
    row=ttk.Frame(f);row.pack(fill="x",pady=1)
    for label,key,default in [("Date format","datefmt","%Y%m%d"),("Time format","timefmt","%H%M%S")]:
        ttk.Label(row,text=label).pack(side="left",padx=(2,4))
        vv=tk.StringVar(value=self.d[k].get(key,default));self.v[k,key]=vv
        ttk.Entry(row,textvariable=vv,width=14).pack(side="left",padx=(0,15))
    preview=ttk.Label(f,text="",font=("Segoe UI",12,"bold"))
    preview.pack(anchor="w",pady=(14,0))
    def update_preview(*_):
        c=self.d[k].copy()
        c["order"]=[self.row_token(roww) for roww in self.order_frames[k]]
        for token in TOKENS:
            c["use_"+token]=self.order_vars[k][token].get()
        c["separators"]=[v.get() for v in self.separator_vars[k]]
        c["datefmt"]=self.v[k,"datefmt"].get()
        c["timefmt"]=self.v[k,"timefmt"].get()
        try:
            date=datetime(2026,11,3,18,22,0).strftime(c["datefmt"])
            time=datetime(2026,11,3,18,22,0).strftime(c["timefmt"])
            sample=pattern(c).format(date=date,time=time,username="sample_user",id="123456789",title=c.get("title",""))
            preview.config(text="Filename preview: "+sample+".mp4")
        except Exception:
            preview.config(text="Preview: Check the date/time formats and filename items.")
    self.preview_funcs[k]=update_preview
    for token in TOKENS:
        self.order_vars[k][token].trace_add("write",update_preview)
    for sep_var in self.separator_vars[k]:
        sep_var.trace_add("write",update_preview)
    self.v[k,"datefmt"].trace_add("write",update_preview)
    self.v[k,"timefmt"].trace_add("write",update_preview)
    self.v[k,"title"].trace_add("write",update_preview)
    update_preview()
 def row_token(self,row):
    return row.token
 def add_order_row(self,k,token):
    chip=ttk.Frame(self.order_area[k],padding=(3,2),relief="groove")
    chip.token=token
    checked=tk.BooleanVar(value=self.d[k].get("use_"+token,True))
    self.order_vars[k][token]=checked
    check = ttk.Checkbutton(chip,text=LABELS[token],variable=checked)
    check.pack(side="left")
    if token == "title":
        ttk.Label(chip,text="[").pack(side="left")
        title_entry=ttk.Entry(chip,textvariable=self.v[k,"title"],width=12,justify="left")
        title_entry.pack(side="left",padx=1)
        ttk.Label(chip,text="]").pack(side="left")
        token_label = check
    else:
        token_label = ttk.Label(chip,text="{"+token+"}",foreground="gray")
        token_label.pack(side="left",padx=(2,3))
    chip.pack(side="left",anchor="w",padx=2,pady=1)
    self.order_frames[k].append(chip)
    drag_start = lambda event, key=k, item=chip:self.start_drag(key,item,event)
    token_label.bind("<ButtonPress-1>",drag_start)
    check.bind("<ButtonPress-1>",drag_start)
 def start_drag(self,k,chip,event):
    self.drag_row[k]=chip
    chip.configure(relief="solid")
    self.r.configure(cursor="hand2")
 def drag_motion_global(self,event):
    if any(chip is not None for chip in self.drag_row.values()):
        self.r.configure(cursor="hand2")
 def drag_release_global(self,event):
    for k,moving in list(self.drag_row.items()):
        if moving is None:
            continue
        target_widget=self.r.winfo_containing(event.x_root,event.y_root)
        target=None
        while target_widget is not None:
            if getattr(target_widget,"token",None) in TOKENS and target_widget in self.order_frames[k]:
                target=target_widget
                break
            target_widget=getattr(target_widget,"master",None)
        if target is not None and target is not moving:
            old=self.order_frames[k].index(moving)
            new_index=self.order_frames[k].index(target)
            self.order_frames[k].pop(old)
            self.order_frames[k].insert(new_index,moving)
            for widget in self.order_area[k].winfo_children():
                widget.pack_forget()
            for i,item in enumerate(self.order_frames[k]):
                item.pack(side="left",anchor="n",padx=2,pady=1)
                if i < len(self.separator_widgets[k]):
                    self.separator_widgets[k][i].pack(side="left",anchor="w",padx=(1,3),pady=1)
            self.preview_funcs[k]()
        moving.configure(relief="ridge")
        self.drag_row[k]=None
    self.r.configure(cursor="")
 def collect(self,k):
    c=self.d[k].copy()
    for (kk,key),v in self.v.items():
        if kk!=k:continue
        if isinstance(v,tk.BooleanVar):c[key]=v.get()
        else:c[key]=v.get()
    if k in self.order_frames:
        c["order"]=[row.token for row in self.order_frames[k]]
        c["separators"]=[v.get() for v in self.separator_vars[k]]
        c["title"]=self.v[k,"title"].get()
        c["suffixes"]={token:self.d[k].get("suffixes",{}).get(token,"") for token in TOKENS}
        for token in TOKENS:c["use_"+token]=self.order_vars[k][token].get()
    c["app_icon"]=self.icon_var.get()
    return c
 def save(self):
    try:
        for k in ("js","py"):self.d[k]=self.collect(k)
        self.d["app_icon"]=self.icon_var.get()
        save(self.d);messagebox.showinfo("Saved","Settings have been saved.")
    except Exception as e:messagebox.showerror("Settings Error",str(e))
 def apply(self):
    k="js" if self.nb.index(self.nb.select())==0 else "py"
    try:c=self.collect(k)
    except Exception as e:messagebox.showerror("Settings Error",str(e));return
    fields=["main"]
    for x in fields:
        if not c.get(x) or not os.path.isfile(c[x]):messagebox.showerror("Validation",x+" must be specified.");return
    try:
        bs=[backup(c[x]) for x in fields]
        if k=="js":edit_js(c["main"],c)
        else:edit_py(c["main"],c)
        self.d[k]=c;self.d["app_icon"]=self.icon_var.get();save(self.d);messagebox.showinfo("Apply Complete","The script has been updated.\nBackup:\n" + "\n".join(bs) + "\nPlease restart the recording program.")
    except Exception as e:messagebox.showerror("Apply Error",str(e))
if __name__=="__main__":
 r=tk.Tk();App(r);r.mainloop()
