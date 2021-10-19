ROOT_DB_JSON = "db/root.json";

SEARCH_DEBOUNCE = 250;

let root_json = null;

String.prototype.removeDiacritics = function () {
    return this.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
};

function load_courses() {
    $.getJSON(ROOT_DB_JSON, data => {
        root_json = data;
        search(null);

        // Set exam count
        $("#exam_count").text(root_json.exam_count);
    })
}

/**
 * Update courses list for search query.
 * @param query Search query, can be null for none.
 */
function search(query) {
    // Get courses code and name from root JSON, sort alphabetically by course code
    const courses_dict = root_json.courses;
    let courses = [];
    for (let code in courses_dict) {
        courses.push({code: code, name: courses_dict[code]})
    }
    courses.sort((a, b) => a.code.localeCompare(b.code));

    // Filter courses if search query given
    if (query != null && query.trim()) {
        const query_norm = query.trim().toLowerCase().removeDiacritics();
        courses = courses.filter(course => {
            const name_norm = course.name.toLowerCase().removeDiacritics();
            return course.code.includes(query_norm) || query_norm.includes(course.code) ||
                name_norm.includes(query_norm) || query_norm.includes(name_norm);
        })
    }

    // Create course list elements
    const course_list = $("#course-list");
    course_list.empty();
    for (const course of courses) {
        const code_span = $("<span/>")
            .text(course.code.toUpperCase())
            .addClass("listitem-start");
        $("<li/>")
            .addClass("listitem")
            .append(code_span)
            .append(" — " + course.name)
            .click(() => {
                // Go to exam page
                window.location.href = `exams.html?course=${course.code}`
            })
            .appendTo(course_list);
    }
}

function main() {
    load_courses();

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
