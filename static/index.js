COURSES_JSON = "root.json";
SEARCH_DEBOUNCE = 250;

let courses_dict = null;

function load_courses() {
    $.getJSON(DB_LOCATION + COURSES_JSON, data => {
        courses_dict = data.courses;
        search();

        // Set exam count
        $("#exam_count").text(data.exam_count);
    })
}

function search() {
    const query = $("#search").val();

    // Get courses code and name from root JSON, sort alphabetically by course code
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
            return query_norm.includesBothways(course.code) ||
                query_norm.includesBothways(name_norm);
        })
    }

    create_course_list(courses);
}

function create_course_list(courses) {
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

function init() {
    load_courses();
    register_search_events($("#search"), search);
}

$(document).ready(init);
