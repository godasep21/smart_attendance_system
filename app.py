from flask import Flask, render_template, request, redirect, send_file, session
import os, json
from datetime import datetime
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib.pagesizes import letter

app = Flask(__name__)
app.secret_key="attendance_secret"

CLASSES = [5,6,7,8,9,10,11,12]

def load_json(path, default):

    if os.path.exists(path):

        with open(path,"r") as f:
            try:
                return json.load(f)
            except:
                return default
    return default
def save_json(path,data):
    with open(path,"w") as f:
        json.dump(data,f,indent=4)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/start",methods=["GET","POST"])
def start():
    message=None
    students=[]
    path=None
    if request.method=="POST":
        action=request.form.get("action")
        cls=request.form.get("class")
        path=f"data/students/class_{cls}.json"
        students=load_json(path,[])
        if action=="save":
            name=request.form.get("name").strip()
            roll=request.form.get("roll")

            for s in students:
                if str(s["roll"])==str(roll):
                    message="Roll number already exists"
                    return render_template(
                        "add_student.html",
                        classes=CLASSES,
                        message=message
                    )
            students.append({
                "name":name,
                "roll":roll,
                "date":datetime.now().strftime("%Y-%m-%d")
            })
            students=sorted(students,key=lambda x:int(x["roll"]))
            save_json(path,students)
            message="Student Added Successfully"

        elif action=="upload":
            file=request.files.get("student_file")
            if not file or file.filename=="":
                message="Please select a file"
                return render_template("add_student.html",classes=CLASSES,message=message)
            filename=file.filename.lower()
            names=[]
            if filename.endswith(".csv"):
                df=pd.read_csv(file)
                names=df.iloc[:,0].dropna().tolist()
            elif filename.endswith(".xlsx") or filename.endswith(".xls"):
                df=pd.read_excel(file)
                names=df.iloc[:,0].dropna().tolist()
            elif filename.endswith(".pdf"):
                import pdfplumber
                with pdfplumber.open(file) as pdf:
                    for page in pdf.pages:
                        text=page.extract_text()
                        if text:
                            lines=text.split("\n")
                            for l in lines:
                                l=l.strip()
                                if l:
                                    names.append(l)
            else:
                message="Unsupported file type"
                return render_template("add_student.html",classes=CLASSES,message=message)
            clean_names=[]
            for n in names:
                n=str(n)
                parts=n.split()
                if parts and parts[0].isdigit():
                    parts.pop(0)
                n=" ".join(parts)
                if n!="":
                    clean_names.append(n)
            existing_names=[s["name"].lower() for s in students]
            duplicates=[]
            new_students=[]
            for n in clean_names:
                if n.lower() in existing_names:
                    duplicates.append(n)
                else:
                    new_students.append(n)
            if duplicates and request.form.get("confirm_replace")!="yes":
                message="These students already exist: " + ", ".join(duplicates)
                return render_template(
                    "add_student.html",
                    classes=CLASSES,
                    message=message,
                    duplicate_names=duplicates
                )
            if students:
                last_roll=max(int(s["roll"]) for s in students)
            else:
                last_roll=0
            roll=last_roll+1
            for n in new_students:
                students.append({
                    "name":n,
                    "roll":roll,
                    "date":datetime.now().strftime("%Y-%m-%d")
                })
                roll+=1
            if request.form.get("confirm_replace")=="yes":
                students=[s for s in students if s["name"] not in duplicates]
                for n in duplicates:
                    students.append({
                        "name":n,
                        "roll":roll,
                        "date":datetime.now().strftime("%Y-%m-%d")
                    })
                    roll+=1
            students=sorted(students,key=lambda x:int(x["roll"]))
            save_json(path,students)
            message="Students Uploaded Successfully"            
    return render_template("add_student.html",classes=CLASSES,message=message)

@app.route("/student_list")
def student_list():
    all_students=[]
    for c in CLASSES:
        path=f"data/students/class_{c}.json"
        students=load_json(path,[])
        for s in students:
            student={
                "roll":s["roll"],
                "name":s["name"],
                "date":s["date"],
                "class":c
            }
            all_students.append(student)
    all_students=sorted(all_students,key=lambda x:int(x["roll"]))
    return render_template("student_list.html",students=all_students)

@app.route("/student_history")
def student_history():
    history=[]
    for c in CLASSES:
        path=f"data/students/class_{c}.json"
        students=load_json(path,[])
        for s in students:
            history.append({
                "roll":s["roll"],
                "name":s["name"],
                "date":s["date"],
                "class":c
            })
    history=sorted(history,key=lambda x:x["date"],reverse=True)
    return render_template("student_history.html",history=history)

@app.route("/add_staff",methods=["GET","POST"])
def add_staff():
    path="data/staff.json"
    staff=load_json(path,[])
    msg=""
    if request.method=="POST":
        name=request.form["name"].strip()
        for s in staff:
            if s["name"].lower()==name.lower():
                msg="Staff already exists!"
                return render_template("add_staff.html",staff=staff,msg=msg)
        new={
            "id":len(staff)+1,
            "name":name,
            "password":"1234"
        }
        staff.append(new)
        save_json(path,staff)
    return render_template("add_staff.html",staff=staff,msg=msg)

@app.route("/delete_staff/<int:staff_id>", methods=["POST"])
def delete_staff(staff_id):
    path="data/staff.json"
    staff=load_json(path,[])
    staff=[s for s in staff if s["id"]!=staff_id]
    for i,s in enumerate(staff,start=1):
        s["id"]=i
    save_json(path,staff)
    return redirect("/add_staff")

@app.route("/staff_login",methods=["GET","POST"])
def staff_login():
    staff=load_json("data/staff.json",[])
    if request.method=="POST":
        sid=request.form["staff"]
        pwd=request.form["password"]
        for s in staff:
            if str(s["id"])==sid and s["password"]==pwd:
                session["staff_name"]=s["name"]
                return redirect("/attendance")
    return render_template("staff_login.html",staff=staff)

@app.route("/attendance",methods=["GET","POST"])
def attendance():
    students=[]
    selected_class=None
    message=None
    if request.method=="POST":
        cls=request.form["class"]
        selected_class=cls
        path=f"data/students/class_{cls}.json"
        students=load_json(path,[])
        if "save_attendance" in request.form:
            date=datetime.now().strftime("%Y-%m-%d")
            att_path=f"data/attendance/class_{cls}.json"
            attendance=load_json(att_path,{})
            if isinstance(attendance,list):
                attendance={}
            staff=session.get("staff_name")
            if date not in attendance:
                attendance[date]={}
            for s in students:
                roll=str(s["roll"])
                status=request.form.get("att_"+roll,"Absent")
                key=roll+"_"+staff
                attendance[date][key]={
                    "status":status,
                    "staff":staff
                }
            save_json(att_path,attendance)
            message="Attendance Saved Successfully"
    return render_template(
        "attendance.html",
        classes=CLASSES,
        students=students,
        selected_class=selected_class,
        staff_name=session.get("staff_name"),
        message=message
    )

@app.route("/search_attendance", methods=["GET","POST"])
def search_attendance():
    data=[]
    if request.method=="POST":
        cls=request.form["class"]
        date_filter=request.form.get("date")
        att_path=f"data/attendance/class_{cls}.json"
        attendance=load_json(att_path,{})
        stu_path=f"data/students/class_{cls}.json"
        students=load_json(stu_path,[])
        name_map={str(s["roll"]):s["name"] for s in students}
        for date,rolls in attendance.items():
            if date_filter and date!=date_filter:
                continue
            for roll,info in rolls.items():
                data.append({
                    "roll":roll,
                    "name":name_map.get(roll,""),
                    "class":cls,
                    "status":info["status"],
                    "staff":info["staff"],
                    "date":date
                })
    return render_template(
"search_attendance.html",
classes=CLASSES,
data=data
)

@app.route("/search_student", methods=["GET","POST"])
def search_student():
    students=[]
    if request.method=="POST":
        cls=request.form["class"]
        keyword=request.form.get("keyword","").lower()
        stu_path=f"data/students/class_{cls}.json"
        all_students=load_json(stu_path,[])
        for s in all_students:
            if keyword in str(s["roll"]) or keyword in s["name"].lower():
                students.append({
                    "roll":s["roll"],
                    "name":s["name"],
                    "class":cls
                })
    return render_template(
        "search_student.html",
        classes=CLASSES,
        students=students
    )

@app.route("/export_pdf",methods=["GET","POST"])
def export_pdf():
    if request.method=="POST":
        cls=request.form["class"]
        path=f"data/students/class_{cls}.json"
        students=load_json(path,[])
        file=f"class_{cls}.pdf"
        data=[["Roll","Name","Date"]]
        for s in students:
            data.append([s["roll"],s["name"],s["date"]])
        pdf=SimpleDocTemplate(file,pagesize=letter)
        table=Table(data)
        pdf.build([table])
        return send_file(file,as_attachment=True)
    return render_template("export_pdf.html",classes=CLASSES)

@app.route("/export_excel",methods=["GET","POST"])
def export_excel():
    if request.method=="POST":
        cls=request.form["class"]
        path=f"data/students/class_{cls}.json"
        students=load_json(path,[])
        df=pd.DataFrame(students)
        file=f"class_{cls}.xlsx"
        df.to_excel(file,index=False)
        return send_file(file,as_attachment=True)
    return render_template("export_excel.html",classes=CLASSES)

@app.route("/student_performance",methods=["POST"])
def student_performance():
    cls=request.form["class"]
    roll=request.form["roll"]
    stu_path=f"data/students/class_{cls}.json"
    students=load_json(stu_path,[])
    name=""
    for s in students:
        if str(s["roll"])==str(roll):
            name=s["name"]
    att_path=f"data/attendance/class_{cls}.json"
    attendance=load_json(att_path,{})
    present=0
    absent=0
    today=datetime.now()
    for date,rolls in attendance.items():
        d=datetime.strptime(date,"%Y-%m-%d")        
        if (today-d).days<=30:
            if roll in rolls:
                if rolls[roll]["status"].lower()=="present":
                    present+=1
                else:
                    absent+=1
    total=present+absent
    percent=0
    marks=0
    if total>0:
        percent=round((present/total)*100,2)
        marks=round((percent/100)*30,2)
    return render_template(
        "student_performance.html",
        name=name,
        roll=roll,
        percent=percent,
        marks=marks,
        present=present,
        absent=absent
    )

@app.route("/download_pdf",methods=["GET","POST"])
def download_pdf():
    if request.method=="POST":
        cls=request.form["class"]
        date=request.form["date"]
        att_path=f"data/attendance/class_{cls}.json"
        attendance=load_json(att_path,{})
        stu_path=f"data/students/class_{cls}.json"
        students=load_json(stu_path,[])
        name_map={str(s["roll"]):s["name"] for s in students}
        file=f"attendance_{cls}_{date}.pdf"
        data=[["Roll","Name","Status","Staff"]]
        if date in attendance:
            for key,info in attendance[date].items():
                roll = key.split("_")[0]   # 🔹 staff remove
                data.append([
                    roll,
                    name_map.get(roll,""),
                    info["status"],
                    info["staff"]
                ])
        pdf=SimpleDocTemplate(file,pagesize=letter)
        table=Table(data)
        pdf.build([table])
        return send_file(file,as_attachment=True)
    return render_template("attendance_pdf.html")

@app.route("/download_excel",methods=["GET","POST"])
def download_excel():
    if request.method=="POST":
        cls=request.form["class"]
        date=request.form["date"]
        att_path=f"data/attendance/class_{cls}.json"
        attendance=load_json(att_path,{})
        stu_path=f"data/students/class_{cls}.json"
        students=load_json(stu_path,[])
        name_map={str(s["roll"]):s["name"] for s in students}
        rows=[]
        if date in attendance:
            for key,info in attendance[date].items():
                roll = key.split("_")[0]   # 🔹 staff remove
                rows.append({
                    "Roll":roll,
                    "Name":name_map.get(roll,""),
                    "Status":info["status"],
                    "Staff":info["staff"]
                })
        df=pd.DataFrame(rows)
        file=f"attendance_{cls}_{date}.xlsx"
        df.to_excel(file,index=False)
        return send_file(file,as_attachment=True)
    return render_template("attendance_excel.html")

@app.route("/show_attendance", methods=["GET","POST"])
def show_attendance():
    staff_tables={}
    selected_class=None
    selected_date=None
    if request.method=="POST":
        cls=request.form["class"]
        date=request.form["date"]
        selected_class=cls
        selected_date=date
        stu_path=f"data/students/class_{cls}.json"
        students=load_json(stu_path,[])
        name_map={str(s["roll"]):s["name"] for s in students}
        att_path=f"data/attendance/class_{cls}.json"
        attendance=load_json(att_path,{})
        if date in attendance:
            for key,info in attendance[date].items():
                roll=key.split("_")[0]
                staff=info["staff"]
                if staff not in staff_tables:
                    staff_tables[staff]=[]
                staff_tables[staff].append({
                    "roll":roll,
                    "name":name_map.get(roll,""),
                    "status":info["status"]
                })
    return render_template(
        "show_attendance.html",
        classes=CLASSES,
        staff_tables=staff_tables,
        selected_class=selected_class,
        selected_date=selected_date
    )

@app.route("/my_attendance", methods=["GET","POST"])
def my_attendance():
    staff=session.get("staff_name")
    staff_tables={}
    selected_class=None
    selected_date=None
    if request.method=="POST":
        cls=request.form["class"]
        date=request.form["date"]
        selected_class=cls
        selected_date=date
        stu_path=f"data/students/class_{cls}.json"
        students=load_json(stu_path,[])
        name_map={str(s["roll"]):s["name"] for s in students}
        att_path=f"data/attendance/class_{cls}.json"
        attendance=load_json(att_path,{})
        if date in attendance:
            data=[]
            for key,info in attendance[date].items():
                roll=key.split("_")[0]
                if info["staff"]==staff:
                    data.append({
                        "roll":roll,
                        "name":name_map.get(roll,""),
                        "status":info["status"]
                    })
            if data:
                staff_tables[staff]=data
    return render_template(
        "show_attendance.html",
        classes=CLASSES,
        staff_tables=staff_tables,
        selected_class=selected_class,
        selected_date=selected_date
    )

@app.route("/delete_student_list/<cls>/<int:roll>", methods=["POST"])
def delete_student_list(cls,roll):
    path=f"data/students/class_{cls}.json"
    students=load_json(path,[])
    students=[s for s in students if int(s["roll"])!=roll]
    save_json(path,students)
    return redirect("/student_list")

@app.route("/delete_student_history/<cls>/<int:roll>", methods=["POST"])
def delete_student_history(cls,roll):
    path=f"data/students/class_{cls}.json"
    students=load_json(path,[])
    students=[s for s in students if int(s["roll"])!=roll]
    save_json(path,students)
    return redirect("/student_history")
if __name__=="__main__":
  app.run(debug=True)
