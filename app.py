# ResumeForge - my online resume builder backend
# Built with Flask + SQLite + ReportLab for the PDF stuff
# - Arpit

import os
import sqlite3
import base64
import traceback
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g, send_from_directory, send_file
from werkzeug.exceptions import HTTPException

# reportlab imports for making the PDFs
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "resumes.db")

app = Flask(
    __name__,
    template_folder=BASE_DIR,
    static_folder=os.path.join(BASE_DIR, "static"),
)
# allow bigger requests because photos can be a few MB in base64
# 16MB is plenty for a 2MB photo (base64 inflates by ~33%) plus the JSON body
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    # make the table if it doesnt exist yet
    print("[init_db] using database file:", DATABASE)
    try:
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                college TEXT,
                skills TEXT,
                experience TEXT,
                education TEXT,
                summary TEXT,
                template TEXT DEFAULT 'modern',
                photo TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # if upgrading from old db version, add the new columns
        existing_cols = [r[1] for r in cur.execute("PRAGMA table_info(resumes)").fetchall()]
        if "template" not in existing_cols:
            cur.execute("ALTER TABLE resumes ADD COLUMN template TEXT DEFAULT 'modern'")
        if "photo" not in existing_cols:
            cur.execute("ALTER TABLE resumes ADD COLUMN photo TEXT")
        conn.commit()
        conn.close()
        print("[init_db] ok - columns:", existing_cols)
    except Exception as e:
        # if init fails the app is unusable, but at least log clearly
        print("[init_db] FAILED:", repr(e))
        traceback.print_exc()
        raise


# run init at module import time so the DB is ready no matter how the app is
# started (python app.py, flask run, gunicorn, etc.)
init_db()


# ------ make every error a JSON response so the frontend can show it ------

@app.errorhandler(HTTPException)
def handle_http_error(err):
    # 400/404/405/413/etc - keep the status code, return JSON
    return jsonify({
        "error": err.description or err.name,
        "status": err.code
    }), err.code


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    # log the traceback to the terminal so we can actually debug
    print("[unhandled error]", repr(err))
    traceback.print_exc()
    return jsonify({"error": str(err) or "Server error"}), 500


@app.route("/api/health")
def health():
    # quick check - confirms DB is reachable and schema is right
    try:
        db = get_db()
        cnt = db.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
        return jsonify({"ok": True, "resumes": cnt, "db": DATABASE})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/")
def index():
    return render_template("index.html")


# serve css and js right out of the project folder
@app.route("/style.css")
def style():
    return send_from_directory(BASE_DIR, "style.css", mimetype="text/css")


@app.route("/script.js")
def script():
    return send_from_directory(BASE_DIR, "script.js", mimetype="application/javascript")


# ---------- CRUD endpoints ----------

@app.route("/api/resumes", methods=["GET"])
def list_resumes():
    db = get_db()
    rows = db.execute(
        "SELECT id, name, email, template, updated_at FROM resumes ORDER BY updated_at DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/resumes/<int:rid>", methods=["GET"])
def get_resume(rid):
    db = get_db()
    row = db.execute("SELECT * FROM resumes WHERE id = ?", (rid,)).fetchone()
    if row is None:
        return jsonify({"error": "Resume not found"}), 404
    return jsonify(dict(row))


def grab_form_fields(data):
    # pulls all the resume fields out of the json body so I dont repeat
    # myself in the create and update routes
    return (
        data.get("name", "").strip(),
        data.get("email", "").strip(),
        data.get("phone", "").strip(),
        data.get("college", "").strip(),
        data.get("skills", "").strip(),
        data.get("experience", "").strip(),
        data.get("education", "").strip(),
        data.get("summary", "").strip(),
        (data.get("template") or "modern").strip() or "modern",
        data.get("photo") or None,  # base64 data url, or None
    )


@app.route("/api/resumes", methods=["POST"])
def create_resume():
    if not request.is_json:
        # if Content-Type isnt JSON we still try - get_json(silent=True) returns None
        print("[create_resume] WARNING: request is not application/json, content-type=",
              request.headers.get("Content-Type"))

    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"error": "Name is required"}), 400

    now = datetime.utcnow().isoformat(timespec="seconds")
    fields = grab_form_fields(data)
    try:
        db = get_db()
        cur = db.execute(
            """INSERT INTO resumes
               (name, email, phone, college, skills, experience, education,
                summary, template, photo, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            fields + (now, now)
        )
        db.commit()
    except sqlite3.OperationalError as e:
        # most likely cause - schema mismatch from an old resumes.db. Log and explain.
        print("[create_resume] sqlite error:", repr(e))
        return jsonify({
            "error": "Database error: " + str(e) +
                     " (try deleting resumes.db and restarting the server)"
        }), 500
    except Exception as e:
        print("[create_resume] unexpected:", repr(e))
        traceback.print_exc()
        return jsonify({"error": "Could not save resume: " + str(e)}), 500

    return jsonify({"id": cur.lastrowid, "message": "Resume saved"}), 201


@app.route("/api/resumes/<int:rid>", methods=["PUT"])
def update_resume(rid):
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"error": "Name is required"}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM resumes WHERE id = ?", (rid,)).fetchone()
    if existing is None:
        return jsonify({"error": "Resume not found"}), 404

    now = datetime.utcnow().isoformat(timespec="seconds")
    fields = grab_form_fields(data)
    try:
        db.execute(
            """UPDATE resumes SET
                  name=?, email=?, phone=?, college=?, skills=?,
                  experience=?, education=?, summary=?, template=?, photo=?,
                  updated_at=?
               WHERE id=?""",
            fields + (now, rid)
        )
        db.commit()
    except sqlite3.OperationalError as e:
        print("[update_resume] sqlite error:", repr(e))
        return jsonify({
            "error": "Database error: " + str(e) +
                     " (try deleting resumes.db and restarting the server)"
        }), 500
    except Exception as e:
        print("[update_resume] unexpected:", repr(e))
        traceback.print_exc()
        return jsonify({"error": "Could not update resume: " + str(e)}), 500

    return jsonify({"id": rid, "message": "Resume updated"})


@app.route("/api/resumes/<int:rid>", methods=["DELETE"])
def delete_resume(rid):
    db = get_db()
    existing = db.execute("SELECT id FROM resumes WHERE id = ?", (rid,)).fetchone()
    if existing is None:
        return jsonify({"error": "Resume not found"}), 404
    db.execute("DELETE FROM resumes WHERE id = ?", (rid,))
    db.commit()
    return jsonify({"message": "Resume deleted"})


# ---------- PDF generation stuff ----------

def decode_photo(photo_b64):
    # turn the base64 data url into bytes that reportlab can read
    if not photo_b64:
        return None
    try:
        # frontend sends "data:image/png;base64,XXXX" - strip the prefix
        if "," in photo_b64:
            photo_b64 = photo_b64.split(",", 1)[1]
        return BytesIO(base64.b64decode(photo_b64))
    except Exception as err:
        print("photo decode failed:", err)
        return None


def split_lines(txt):
    # split a textarea value into clean lines, no blanks
    if not txt:
        return []
    out = []
    for ln in txt.split("\n"):
        ln = ln.strip()
        if ln:
            out.append(ln)
    return out


def make_safe_para(text, style):
    # paragraphs in reportlab break on raw < and & so escape them
    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def build_modern_pdf(resume, buf):
    # Modern - blue accent, sans serif, photo on the right side of the header
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )
    elements = []
    styles = getSampleStyleSheet()
    accent = colors.HexColor("#2563eb")

    name_style = ParagraphStyle('Name', parent=styles['Heading1'],
        fontSize=22, textColor=accent, spaceAfter=2,
        fontName='Helvetica-Bold')
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor("#444"), fontName='Helvetica')
    section_style = ParagraphStyle('Section', parent=styles['Heading2'],
        fontSize=12, textColor=accent, fontName='Helvetica-Bold',
        spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
        fontSize=10, leading=14, fontName='Helvetica')

    # build header with photo if there is one
    photo_io = decode_photo(resume.get("photo"))
    name_para = make_safe_para(resume.get("name") or "", name_style)
    contact_bits = []
    if resume.get("email"):   contact_bits.append(resume["email"])
    if resume.get("phone"):   contact_bits.append(resume["phone"])
    if resume.get("college"): contact_bits.append(resume["college"])
    contact_para = make_safe_para(" | ".join(contact_bits), contact_style)

    if photo_io:
        try:
            img = Image(photo_io, width=25*mm, height=25*mm)
            # name+contact on the left, photo on the right
            header_tbl = Table([[[name_para, contact_para], img]],
                               colWidths=[None, 28*mm])
            header_tbl.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            elements.append(header_tbl)
        except Exception:
            elements.append(name_para)
            elements.append(contact_para)
    else:
        elements.append(name_para)
        elements.append(contact_para)

    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=accent))
    elements.append(Spacer(1, 4))

    if resume.get("summary"):
        elements.append(Paragraph("SUMMARY", section_style))
        elements.append(make_safe_para(resume["summary"], body_style))

    if resume.get("skills"):
        elements.append(Paragraph("SKILLS", section_style))
        skills = [s.strip() for s in resume["skills"].split(",") if s.strip()]
        elements.append(make_safe_para("  •  ".join(skills), body_style))

    if resume.get("experience"):
        elements.append(Paragraph("EXPERIENCE", section_style))
        for line in split_lines(resume["experience"]):
            if line[0] in "-•*":
                elements.append(make_safe_para("&bull; " + line[1:].strip(), body_style))
            else:
                elements.append(Paragraph("<b>" + line + "</b>", body_style))

    if resume.get("education"):
        elements.append(Paragraph("EDUCATION", section_style))
        for line in split_lines(resume["education"]):
            if line[0] in "-•*":
                elements.append(make_safe_para("&bull; " + line[1:].strip(), body_style))
            else:
                elements.append(Paragraph("<b>" + line + "</b>", body_style))

    doc.build(elements)


def build_classic_pdf(resume, buf):
    # Classic - serif, centered name, traditional resume look
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm, bottomMargin=18*mm)
    elements = []
    styles = getSampleStyleSheet()

    name_style = ParagraphStyle('Name', parent=styles['Heading1'],
        fontSize=24, alignment=TA_CENTER,
        fontName='Times-Bold', spaceAfter=2)
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'],
        fontSize=10, alignment=TA_CENTER, fontName='Times-Roman')
    section_style = ParagraphStyle('Section', parent=styles['Heading2'],
        fontSize=12, fontName='Times-Bold',
        spaceBefore=10, spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
        fontSize=10.5, leading=14, fontName='Times-Roman')

    # photo centered above the name
    photo_io = decode_photo(resume.get("photo"))
    if photo_io:
        try:
            img = Image(photo_io, width=28*mm, height=28*mm)
            img.hAlign = 'CENTER'
            elements.append(img)
            elements.append(Spacer(1, 4))
        except Exception:
            pass

    elements.append(make_safe_para(resume.get("name") or "", name_style))
    contact = []
    if resume.get("email"):   contact.append(resume["email"])
    if resume.get("phone"):   contact.append(resume["phone"])
    if resume.get("college"): contact.append(resume["college"])
    elements.append(make_safe_para(" • ".join(contact), contact_style))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))

    def add_section(title, body_lines):
        elements.append(Paragraph(title.upper(), section_style))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        elements.append(Spacer(1, 2))
        for ln in body_lines:
            elements.append(ln)

    if resume.get("summary"):
        add_section("Summary", [make_safe_para(resume["summary"], body_style)])
    if resume.get("skills"):
        add_section("Skills", [make_safe_para(resume["skills"], body_style)])
    if resume.get("experience"):
        items = []
        for line in split_lines(resume["experience"]):
            if line[0] in "-•*":
                items.append(make_safe_para("&nbsp;&nbsp;&bull; " + line[1:].strip(), body_style))
            else:
                items.append(Paragraph("<b>" + line + "</b>", body_style))
        add_section("Experience", items)
    if resume.get("education"):
        items = []
        for line in split_lines(resume["education"]):
            if line[0] in "-•*":
                items.append(make_safe_para("&nbsp;&nbsp;&bull; " + line[1:].strip(), body_style))
            else:
                items.append(Paragraph("<b>" + line + "</b>", body_style))
        add_section("Education", items)

    doc.build(elements)


def build_minimal_pdf(resume, buf):
    # Minimal - lots of whitespace, no colors, light type
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=25*mm, rightMargin=25*mm,
        topMargin=22*mm, bottomMargin=22*mm)
    elements = []
    styles = getSampleStyleSheet()

    name_style = ParagraphStyle('Name', parent=styles['Heading1'],
        fontSize=20, fontName='Helvetica', spaceAfter=2,
        textColor=colors.HexColor("#222"))
    contact_style = ParagraphStyle('Contact', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor("#777"), spaceAfter=8)
    section_style = ParagraphStyle('Section', parent=styles['Heading2'],
        fontSize=10, fontName='Helvetica-Bold',
        textColor=colors.HexColor("#222"),
        spaceBefore=14, spaceAfter=6)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
        fontSize=10, leading=14, textColor=colors.HexColor("#333"),
        fontName='Helvetica')

    photo_io = decode_photo(resume.get("photo"))
    if photo_io:
        try:
            img = Image(photo_io, width=22*mm, height=22*mm)
            img.hAlign = 'LEFT'
            elements.append(img)
            elements.append(Spacer(1, 6))
        except Exception:
            pass

    elements.append(make_safe_para(resume.get("name") or "", name_style))
    contact = []
    if resume.get("email"):   contact.append(resume["email"])
    if resume.get("phone"):   contact.append(resume["phone"])
    if resume.get("college"): contact.append(resume["college"])
    elements.append(make_safe_para("  ·  ".join(contact), contact_style))

    if resume.get("summary"):
        elements.append(Paragraph("Summary", section_style))
        elements.append(make_safe_para(resume["summary"], body_style))
    if resume.get("skills"):
        elements.append(Paragraph("Skills", section_style))
        elements.append(make_safe_para(resume["skills"], body_style))
    if resume.get("experience"):
        elements.append(Paragraph("Experience", section_style))
        for line in split_lines(resume["experience"]):
            if line[0] in "-•*":
                elements.append(make_safe_para("— " + line[1:].strip(), body_style))
            else:
                elements.append(Paragraph("<b>" + line + "</b>", body_style))
    if resume.get("education"):
        elements.append(Paragraph("Education", section_style))
        for line in split_lines(resume["education"]):
            if line[0] in "-•*":
                elements.append(make_safe_para("— " + line[1:].strip(), body_style))
            else:
                elements.append(Paragraph("<b>" + line + "</b>", body_style))

    doc.build(elements)


@app.route("/api/resumes/<int:rid>/pdf", methods=["GET"])
def download_pdf(rid):
    db = get_db()
    row = db.execute("SELECT * FROM resumes WHERE id = ?", (rid,)).fetchone()
    if row is None:
        return jsonify({"error": "Resume not found"}), 404
    resume = dict(row)

    # let user pass ?template= to override the saved one
    tpl = (request.args.get("template") or resume.get("template") or "modern").lower()

    buf = BytesIO()
    if tpl == "classic":
        build_classic_pdf(resume, buf)
    elif tpl == "minimal":
        build_minimal_pdf(resume, buf)
    else:
        build_modern_pdf(resume, buf)

    buf.seek(0)
    # make a safe-ish filename
    safe_name = "".join(c for c in (resume["name"] or "") if c.isalnum() or c in "_-") or "resume"
    filename = safe_name + "_resume.pdf"
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)


if __name__ == "__main__":
    # init_db() has already run at import; we just start the server here
    print("[startup] ResumeForge running at http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
