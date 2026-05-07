// resume forge ka frontend script
// ye file pure UI ka kaam dekhti hai - form input, preview update, save/load
// IIFE me wrap kiya hai taaki global scope clean rahe (otherwise everything leaks out)

(function () {
    "use strict";

    // saari form fields ke names ek array me - looping easy ho jaata hai
    var fields = ["name", "email", "phone", "college", "summary", "skills", "experience", "education"];

    // input elements ko ek object me daal diya
    var inputs = {};
    fields.forEach(function (f) {
        inputs[f] = document.getElementById(f);
    });

    // preview wale elements - sab ek jagah taaki dhundna na pade
    var pv = {
        name:               document.getElementById("pvName"),
        photo:              document.getElementById("pvPhoto"),
        email:              document.getElementById("pvEmail"),
        emailSep:           document.getElementById("pvEmailSep"),
        phone:              document.getElementById("pvPhone"),
        phoneSep:           document.getElementById("pvPhoneSep"),
        college:            document.getElementById("pvCollege"),
        summary:            document.getElementById("pvSummary"),
        summarySection:     document.getElementById("pvSummarySection"),
        skills:             document.getElementById("pvSkills"),
        skillsSection:      document.getElementById("pvSkillsSection"),
        experience:         document.getElementById("pvExperience"),
        experienceSection:  document.getElementById("pvExperienceSection"),
        education:          document.getElementById("pvEducation"),
        educationSection:   document.getElementById("pvEducationSection")
    };

    // top buttons aur dropdowns
    var resumeBox = document.getElementById("resumePreview");
    var savedSelect = document.getElementById("savedResumes");
    var templatePicker = document.getElementById("templatePicker");
    var newBtn = document.getElementById("newBtn");
    var saveBtn = document.getElementById("saveBtn");
    var updateBtn = document.getElementById("updateBtn");
    var deleteBtn = document.getElementById("deleteBtn");
    var pdfBtn = document.getElementById("pdfBtn");
    var printBtn = document.getElementById("printBtn");
    var statusMsg = document.getElementById("statusMsg");

    // photo upload wala stuff
    var photoInput = document.getElementById("photoInput");
    var photoPreview = document.getElementById("photoPreview");
    var removePhotoBtn = document.getElementById("removePhotoBtn");

    // app state
    var currentId = null;     // jo resume edit ho raha hai uska id (null = naya)
    var photoData = "";       // base64 data url of profile pic

    console.log("[ResumeForge] script loaded");


    // chota helper - status message dikhata hai 2.5 sec ke liye
    function showStatus(text, type) {
        statusMsg.textContent = text;
        statusMsg.className = "status-msg " + (type || "");
        if (text) {
            setTimeout(function () {
                statusMsg.textContent = "";
                statusMsg.className = "status-msg";
            }, 2500);
        }
    }


    // form se saara data nikaalke ek object me daal deta hai
    function getFormData() {
        var d = {};
        fields.forEach(function (f) {
            d[f] = inputs[f].value;
        });
        d.template = templatePicker.value || "modern";
        d.photo = photoData || "";
        // console.log("getFormData", d);
        return d;
    }


    // experience/education ka raw text -> preview ke liye lines banata hai
    // jo line - se start ho woh bullet, baaki normal title
    function renderEntries(container, raw) {
        container.innerHTML = "";
        var lines = (raw || "").split("\n");
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (!line) continue;

            var div = document.createElement("div");
            var firstChar = line.charAt(0);
            var isBullet = (firstChar === "-" || firstChar === "•" || firstChar === "*");

            if (isBullet) {
                div.className = "entry-line bullet";
                div.textContent = line.replace(/^[-•*]\s*/, "");
            } else {
                div.className = "entry-line title";
                div.textContent = line;
            }
            container.appendChild(div);
        }
    }


    // ye bada function hai - jab bhi kuch type karte hain preview ko refresh karta hai
    function updatePreview() {
        var d = getFormData();

        // template class change kardo - CSS isko handle karta hai automatically
        resumeBox.className = "resume-paper template-" + d.template;

        // basic text fields
        pv.name.textContent     = d.name.trim() || "Your Name";
        pv.email.textContent    = d.email.trim();
        pv.phone.textContent    = d.phone.trim();
        pv.college.textContent  = d.college.trim();

        // separators ko hide kardo agar neighbours nahi hain (otherwise weird hota hai)
        var hasEmail   = d.email.trim()   !== "";
        var hasPhone   = d.phone.trim()   !== "";
        var hasCollege = d.college.trim() !== "";
        pv.emailSep.style.display = (hasEmail && (hasPhone || hasCollege)) ? "" : "none";
        pv.phoneSep.style.display = (hasPhone && hasCollege) ? "" : "none";

        // photo show/hide
        if (photoData) {
            pv.photo.src = photoData;
            pv.photo.style.display = "";
        } else {
            pv.photo.removeAttribute("src");
            pv.photo.style.display = "none";
        }

        // summary section - empty hai toh hide
        if (d.summary.trim() !== "") {
            pv.summary.textContent = d.summary.trim();
            pv.summarySection.style.display = "";
        } else {
            pv.summarySection.style.display = "none";
        }

        // skills - comma se split karke chip banao
        var skillsArr = d.skills.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        pv.skills.innerHTML = "";
        if (skillsArr.length > 0) {
            for (var j = 0; j < skillsArr.length; j++) {
                var li = document.createElement("li");
                li.textContent = skillsArr[j];
                pv.skills.appendChild(li);
            }
            pv.skillsSection.style.display = "";
        } else {
            pv.skillsSection.style.display = "none";
        }

        // experience
        if (d.experience.trim()) {
            renderEntries(pv.experience, d.experience);
            pv.experienceSection.style.display = "";
        } else {
            pv.experienceSection.style.display = "none";
        }

        //education
        if (d.education.trim()) {
            renderEntries(pv.education, d.education);
            pv.educationSection.style.display = "";
        } else {
            pv.educationSection.style.display = "none";
        }
    }


    // save vs update mode toggle - id hai matlab edit ho raha hai
    function setEditMode(id) {
        currentId = id;
        if (id) {
            saveBtn.style.display = "none";
            updateBtn.style.display = "";
            deleteBtn.style.display = "";
        } else {
            saveBtn.style.display = "";
            updateBtn.style.display = "none";
            deleteBtn.style.display = "none";
        }
    }


    // form ko empty kardo - new resume banane ke liye
    function clearForm() {
        fields.forEach(function (f) { inputs[f].value = ""; });
        photoData = "";
        photoInput.value = "";
        renderPhotoBox();
        savedSelect.value = "";
        templatePicker.value = "modern";
        setEditMode(null);
        updatePreview();
        console.log("[clearForm] form reset ho gaya");
    }


    // ---------- API helpers ----------
    // backend se baat karne ke liye common function

    async function api(path, options) {
        // network error ko alag se catch karna - taaki user ko proper msg mile
        var res;
        try {
            res = await fetch(path, Object.assign({
                headers: { "Content-Type": "application/json" }
            }, options || {}));
        } catch (netErr) {
            console.error("[api] network error on " + path, netErr);
            throw new Error("Cannot reach the server - is it running on port 5000?");
        }

        // body ko text me read karo pehle - JSON parse fail bhi ho toh kuch toh dikhe
        var rawText = "";
        var body = null;
        try {
            rawText = await res.text();
            if (rawText) {
                try {
                    body = JSON.parse(rawText);
                } catch (parseErr) {
                    // server ne non-JSON return kiya (HTML error page, plain text, empty)
                    console.warn("[api] non-JSON response from " + path + ":", rawText.slice(0, 200));
                }
            }
        } catch (readErr) {
            console.error("[api] couldnt read response body", readErr);
        }

        if (!res.ok) {
            // sabse useful error message banao
            var msg;
            if (body && body.error) {
                msg = body.error;
            } else if (rawText) {
                // HTML tags hata do taaki readable lage
                var clean = rawText.replace(/<[^>]+>/g, "").trim().slice(0, 160);
                msg = clean || ("HTTP " + res.status + " " + res.statusText);
            } else {
                msg = "HTTP " + res.status + " " + (res.statusText || "");
            }
            console.error("[api] " + res.status + " from " + path + ": " + msg);
            throw new Error(msg);
        }
        return body || {};
    }

    // saved resumes ki list dropdown me daalo
    async function loadList() {
        try {
            var list = await api("/api/resumes");
            var keep = savedSelect.value;
            savedSelect.innerHTML = '<option value="">— Saved resumes —</option>';

            list.forEach(function (r) {
                var opt = document.createElement("option");
                opt.value = r.id;
                opt.textContent = r.name + (r.email ? " (" + r.email + ")" : "");
                savedSelect.appendChild(opt);
            });
            if (keep) savedSelect.value = keep;
        } catch (e) {
            showStatus("Failed to load saved resumes", "error");
        }
    }

    // dropdown se ek particular resume load karo
    async function loadResume(id) {
        try {
            var r = await api("/api/resumes/" + id);
            fields.forEach(function (f) { inputs[f].value = r[f] || ""; });
            templatePicker.value = r.template || "modern";
            // template change ka event manually fire karna padta hai - .value set se trigger nahi hota
            try { templatePicker.dispatchEvent(new Event("change")); } catch (e) {}

            photoData = r.photo || "";
            renderPhotoBox();
            setEditMode(r.id);
            updatePreview();
            showStatus("Loaded resume", "success");
            console.log("[loadResume] loaded id =", id);
        } catch (e) {
            showStatus(e.message, "error");
        }
    }

    // ye wala function naya resume save karta hai
    async function saveResume() {
        var data = getFormData();
        if (!data.name.trim()) {
            showStatus("Name is required", "error");
            return;
        }
        try {
            var result = await api("/api/resumes", {
                method: "POST",
                body: JSON.stringify(data)
            });
            setEditMode(result.id);
            await loadList();
            savedSelect.value = String(result.id);
            showStatus("Resume saved", "success");
            console.log("[saveResume] saved, id =", result.id);
        } catch (e) {
            showStatus(e.message, "error");
        }
    }

    // existing resume ko update karta hai
    async function updateResume() {
        if (!currentId) return;
        var data = getFormData();
        if (!data.name.trim()) {
            showStatus("Name is required", "error");
            return;
        }
        try {
            await api("/api/resumes/" + currentId, {
                method: "PUT",
                body: JSON.stringify(data)
            });
            await loadList();
            savedSelect.value = String(currentId);
            showStatus("Resume updated", "success");
        } catch (e) {
            showStatus(e.message, "error");
        }
    }

    // delete - confirm karke remove kardo
    async function deleteResume() {
        if (!currentId) return;
        if (!confirm("Delete this resume? This cant be undone.")) return;
        try {
            await api("/api/resumes/" + currentId, { method: "DELETE" });
            clearForm();
            await loadList();
            showStatus("Resume deleted", "success");
        } catch (e) {
            showStatus(e.message, "error");
        }
    }


    // ---------- PDF download ----------
    // backend pe PDF generate hota hai - hum bas save karke open kardete hain

    async function downloadPdf() {
        var data = getFormData();
        if (!data.name.trim()) {
            showStatus("Add your name first", "error");
            return;
        }

        // agar resume already saved nahi hai, pehle save karo
        if (!currentId) {
            try {
                var result = await api("/api/resumes", {
                    method: "POST",
                    body: JSON.stringify(data)
                });
                setEditMode(result.id);
                await loadList();
                savedSelect.value = String(result.id);
                showStatus("Saved - downloading PDF", "success");
            } catch (e) {
                showStatus(e.message, "error");
                return;
            }
        } else {
            // already saved hai - update karke phir PDF lo (taaki latest changes aaye)
            try {
                await api("/api/resumes/" + currentId, {
                    method: "PUT",
                    body: JSON.stringify(data)
                });
            } catch (e) {
                showStatus(e.message, "error");
                return;
            }
        }

        var tpl = templatePicker.value || "modern";
        var url = "/api/resumes/" + currentId + "/pdf?template=" + encodeURIComponent(tpl);
        // naye tab me kholo, current page navigate na ho jaaye
        window.open(url, "_blank");
    }


    // ---------- photo upload ----------

    function renderPhotoBox() {
        if (photoData) {
            // thumbnail banao
            var img = document.createElement("img");
            img.src = photoData;
            img.alt = "profile";
            photoPreview.innerHTML = "";
            photoPreview.appendChild(img);
        } else {
            photoPreview.innerHTML = '<span style="color:#94a3b8; font-size:11px;">No photo</span>';
        }
    }

    function handlePhotoUpload(e) {
        var file = e.target.files && e.target.files[0];
        if (!file) return;

        // size check - 2MB se zyada nahi
        if (file.size > 2 * 1024 * 1024) {
            showStatus("Photo too big - please use under 2MB", "error");
            photoInput.value = "";
            return;
        }
        // image hi honi chahiye
        if (!/^image\//.test(file.type)) {
            showStatus("Please upload an image file", "error");
            photoInput.value = "";
            return;
        }

        var reader = new FileReader();
        reader.onload = function (ev) {
            photoData = ev.target.result;   // data URL
            renderPhotoBox();
            updatePreview();
            console.log("[photo] loaded, size =", file.size);
        };
        reader.readAsDataURL(file);
    }


    // ---------- saare events wire karo ----------

    // har input pe preview turant update karo
    fields.forEach(function (f) {
        inputs[f].addEventListener("input", updatePreview);
    });
    templatePicker.addEventListener("change", updatePreview);

    // dropdown se saved resume load
    savedSelect.addEventListener("change", function (e) {
        var id = e.target.value;
        if (id) {
            loadResume(id);
        } else {
            clearForm();
        }
    });

    newBtn.addEventListener("click", clearForm);
    saveBtn.addEventListener("click", saveResume);
    updateBtn.addEventListener("click", updateResume);
    deleteBtn.addEventListener("click", deleteResume);
    pdfBtn.addEventListener("click", downloadPdf);
    printBtn.addEventListener("click", function () { window.print(); });

    photoInput.addEventListener("change", handlePhotoUpload);
    removePhotoBtn.addEventListener("click", function () {
        photoData = "";
        photoInput.value = "";
        renderPhotoBox();
        updatePreview();
    });

    // pehli baar render
    renderPhotoBox();
    updatePreview();
    loadList();
})();
