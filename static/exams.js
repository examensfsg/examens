EXAMS_LOCATION = "db/";
ROOT_DB_JSON = "db/root.json";

SEARCH_DEBOUNCE = 250;

let exams_json = null;
let selected_id = 0;

String.prototype.removeDiacritics = function () {
    return this.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
};

function load_exams() {
    const search_params = new URLSearchParams(window.location.search);
    const course_code = search_params.get("course");
    if (course_code) {
        $("#exam_count").text(0);
        $("#course-code").text(course_code.toUpperCase());
        $.getJSON(`${EXAMS_LOCATION}${course_code}.json`, data => {
            exams_json = data;
            search(null);

            // Set exam count
            $("#exam_count").text(exams_json?.length ?? 0);
        }).fail(() => {
            // Invalid course code, redirect to main page.
            window.location.href = "index.html";
        });
        $.getJSON(ROOT_DB_JSON, data => {
            const course_name = data.courses?.[course_code];
            if (course_name) {
                $("#course-code").text(`${course_code.toUpperCase()} — ${course_name}`);
            }
        });
    } else {
        // Invalid course code, redirect to main page.
        window.location.href = "index.html";
    }

    // Restore selected exam ID
    selected_id = parseInt(window.location.hash.substr(1));
}

/**
 * Update exams list for search query.
 * @param query Search query, can be null for none.
 */
function search(query) {
    if (!exams_json) {
        // invalid code / no exams
        return;
    }

    // Sort exams by year (descending) then semester.
    let exams = exams_json.slice();
    exams.sort((a, b) => (b.y - a.y) || (a.s - b.s));

    // Filter courses if search query given
    if (query != null && query.trim()) {
        const query_norm = query.trim().toLowerCase().removeDiacritics();
        exams = exams.filter(exam => {
            const title_norm = exam.t.toLowerCase().removeDiacritics();
            const author_norm = exam.a.toLowerCase().removeDiacritics();
            const year_str = exam.y.toString();
            return year_str.includes(query_norm) || query_norm.includes(year_str) ||
                title_norm.includes(query_norm) || query_norm.includes(title_norm) ||
                author_norm.includes(query_norm) || query_norm.includes(author_norm);
        })
    }

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
    $.each()
}

function select_exam(exam, exam_li, unselect) {
    // Fold last exam item
    $(".file-item").remove();

    if (!unselect || selected_id !== exam.id) {
        let last_li = exam_li;
        for (let i = 0; i < exam.h.length; i++) {
            const file_hash = exam.h[i];
            const file_url = `exam/${file_hash.substr(0, 2)}/${file_hash}.pdf`;
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

function main() {
    load_exams();

    // Register search event
    let debounce = null;
    const search_input = $("#search");
    search_input.on("keyup", _ => {
        clearTimeout(debounce);
        debounce = setTimeout(() => {
            search(search_input.val())
        }, SEARCH_DEBOUNCE)
    }).keypress(e => {
        if (e.which === 13) {
            search(search_input.val());
            return false;
        }
    })
}

$(document).ready(main);
