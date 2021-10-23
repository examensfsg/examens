/*
 *    Copyright 2021 examensfsg
 *
 *    Licensed under the Apache License, Version 2.0 (the "License");
 *    you may not use this file except in compliance with the License.
 *    You may obtain a copy of the License at
 *
 *        http://www.apache.org/licenses/LICENSE-2.0
 *
 *    Unless required by applicable law or agreed to in writing, software
 *    distributed under the License is distributed on an "AS IS" BASIS,
 *    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *    See the License for the specific language governing permissions and
 *    limitations under the License.
 *
 */

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
