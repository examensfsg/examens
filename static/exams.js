let exams_list = null;
let selected_id = 0;

function load_exams() {
    const search_params = new URLSearchParams(window.location.search);
    const course_code = search_params.get("course");
    if (course_code) {
        $("#course-code").text(course_code.toUpperCase());
        $.getJSON(`${DB_LOCATION}${course_code}.json`, data => {
            exams_list = data.exams;
            search();

            $("#course-code").text(`${course_code.toUpperCase()} — ${data.name}`);
            $("#exam_count").text(exams_list?.length ?? 0);
        }).fail(() => {
            // Invalid course code, redirect to main page.
            window.location.href = ".";
        });
    } else {
        // Invalid course code, redirect to main page.
        window.location.href = ".";
    }

    // Restore selected exam ID
    selected_id = parseInt(window.location.hash.substr(1));
}

function search() {
    if (!exams_list) {
        // invalid code / no exams
        return;
    }

    const query = $("#search").val();

    // Sort exams by year (descending) then semester.
    let exams = exams_list.slice();
    exams.sort((a, b) => (b.y - a.y) || (a.s - b.s));

    // Filter courses if search query given
    if (query != null && query.trim()) {
        const query_norm = query.trim().toLowerCase().removeDiacritics();
        exams = exams.filter(exam => {
            const title_norm = exam.t.toLowerCase().removeDiacritics();
            const author_norm = exam.a.toLowerCase().removeDiacritics();
            const year_str = exam.y.toString();
            return query_norm.includesBothways(year_str) ||
                query_norm.includesBothways(title_norm) ||
                query_norm.includesBothways(author_norm);
        })
    }

    create_exam_list(exams);
}

function create_exam_list(exams) {
    // Create exam list elements
    const exam_list = $("#exam-list");
    exam_list.empty();
    for (const exam of exams) {
        const year_span = $("<span/>")
            .text(exam.y.toString() + "HEA"[exam.s])
            .addClass("listitem-start");

        let exam_text = " — ";
        if (exam.a) {
            exam_text += exam.a;
        } else {
            exam_text += "Auteur inconnu"
        }
        exam_text += " — ";
        if (exam.t) {
            exam_text += exam.t;
        } else {
            exam_text += "Examen inconnu";
        }
        const exam_li = $("<li/>");
        exam_li.addClass("listitem")
            .append(year_span)
            .append(exam_text)
            .click(() => select_exam(exam, exam_li, true))
            .appendTo(exam_list);

        if (exam.id === selected_id) {
            select_exam(exam, exam_li, false);
        }
    }
}

function select_exam(exam, exam_li, unselect) {
    // Fold last exam item
    $(".file-item").remove();

    if (!unselect || selected_id !== exam.id) {
        let last_li = exam_li;
        for (let i = 0; i < exam.h.length; i++) {
            const file_hash = exam.h[i];
            const file_url = `${EXAM_LOCATION}${file_hash.substr(0, 2)}/${file_hash}.pdf`;
            last_li = $("<li/>")
                .addClass("file-item")
                .text(`Fichier ${i + 1}`)
                .click(() => window.open(file_url, "_blank"))
                .insertAfter(last_li);
        }
        selected_id = exam.id;
        window.history.replaceState(null, null, `#${exam.id}`);
    } else {
        selected_id = 0;
        window.history.replaceState(null, null, "#");
    }
}

function init() {
    load_exams();
    register_search_events($("#search"), search);
}

$(document).ready(init);
