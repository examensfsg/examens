DB_LOCATION = "db/";
EXAM_LOCATION = "exam/";

SEARCH_DEBOUNCE = 250;

String.prototype.removeDiacritics = function () {
    return this.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
};

String.prototype.includesBothways = function (str) {
    return this.includes(str) || str.includes(this);
};

function register_search_events(element, callback) {
    // Register events on search input element for:
    // - Enter key pressed
    // - Debounced typing
    let debounce = null;
    element.on("keyup", _ => {
        clearTimeout(debounce);
        debounce = setTimeout(() => {
            callback()
        }, SEARCH_DEBOUNCE)
    }).keypress(e => {
        if (e.which === 13) {
            callback();
            return false;
        }
    })
}
