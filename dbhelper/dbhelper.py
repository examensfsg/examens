import copy
import hashlib
import json
import os
import re
from datetime import datetime, date
from pathlib import Path
from shutil import copyfile
from typing import List, Dict, TypeVar, Optional

import unidecode

from db import Database, DatabaseError, Exam, Course, ExamSemester

EXAM_DIR_NAME = "exam"
EXAM_DIR_HASH_SUBDIV = 2

# this is the only supported extension!
FILE_EXTENSION = ".pdf"

SEMESTER_MAPPINGS = {
    'w': 0, 'h': 0,
    's': 1, 'e': 1,
    'f': 2, 'a': 2,
}

PathLike = TypeVar("PathLike", str, Path)

HASH_REGEX = re.compile(r"^[0-9a-f]{40}$")


def format_exam(exam: Exam, count_files: bool = True, show_date_added: bool = False) -> str:
    s = (("" if exam.id == Exam.NO_ID else f"[{exam.id}] ") +
         f"{exam.course}, {exam.year}{'HEA'[exam.semester.value]}, "
         f"{exam.author or '[unknown]'}, "
         f"{exam.title or '[untitled]'}")
    if count_files:
        s += f", {len(exam.hashes)} file(s)"
    if show_date_added and exam.date_added:
        s += f", added on {exam.date_added.strftime('%Y-%m-%d')}"
    return s


def ask_confirm(message: str) -> bool:
    ans = ""
    while ans.lower() not in ["y", "n"]:
        ans = input(f"{message} (Y/n) ")
        if not ans:
            ans = "y"
    return ans.lower() == "y"


class DatabaseHelper:
    """
    Class used to do operations on the database.
    Used to execute commands from parsed arguments.
    """
    db: Database
    file_hashes: Dict[str, int]  # hash mapped to number of uses

    def __init__(self, db: Database):
        self.db = db
        self.file_hashes = {}
        self._load_hashes()

    def add_exam(self, course: Optional[str], author: Optional[str], year: Optional[int],
                 semester: Optional[str], title: Optional[str], files: List[PathLike],
                 course_name: Optional[str] = None, date_added: Optional[date] = None,
                 force: bool = False, confirm: bool = False,
                 silent: bool = False) -> Optional[Exam]:
        # basic input validation
        if author is not None:
            author = author.strip()
        if not author and not silent:
            print("WARNING: no author name provided")
            author = None

        if title is not None:
            title = title.strip()
        if not title and not silent:
            print("WARNING: no exam title provided")
            title = None

        if not isinstance(year, int) or year > datetime.today().year:
            raise DatabaseError("Invalid or missing exam year")

        if not semester:
            raise DatabaseError(f"Semester is required")
        semester_num = SEMESTER_MAPPINGS.get(semester.lower(), None)
        if semester_num is None:
            raise DatabaseError(f"Invalid exam semester '{semester}'")
        semester = ExamSemester(semester_num)

        if not files:
            raise DatabaseError("At least one file per exam is required")

        if not course:
            raise DatabaseError("Course code is required")
        try:
            course = Course.parse(course.lower())
        except ValueError:
            raise DatabaseError(f"Invalid course code '{course}'")

        if not date_added:
            date_added = datetime.today()

        hashes = []
        exam = Exam(Exam.NO_ID, course, author, year, semester,
                    title, date_added, hashes)

        # check if similar doesn't already exist
        if not force:
            for e in self.db.exams.values():
                if title is not None and e.title is not None and \
                        title.lower() == e.title.lower() and year == e.year and \
                        semester == e.semester and course == e.course:
                    # exam has same title, same year, same course: most likely the same exam
                    print(f"Duplicate exam? {format_exam(exam, count_files=False)}. "
                          f"Use --force to override check.")
                    return None

        # confirm
        if confirm:
            print(format_exam(exam, count_files=False))
            if not ask_confirm("Add exam to database?"):
                return

        # hash and add files
        hashes += self.hash_files(files, silent)

        self.db.add_exam(exam, course_name)
        for h in hashes:
            self._use_hash(h)

        print(format_exam(exam))
        if not silent:
            print("Successfully added exam to database")
        return exam

    def batch_add_exam(self, batch_json: PathLike, force: bool = False) -> None:
        with open(batch_json, "r") as batch_file:
            count = 0
            batch_data = json.load(batch_file)
            if not isinstance(batch_data, list):
                raise DatabaseError("Invalid batch data JSON")
            for exam_json in batch_data:
                if not isinstance(exam_json, dict):
                    raise DatabaseError("Invalid batch data JSON")
                try:
                    exam = self.add_exam(
                        exam_json["course"],
                        exam_json.get("author", None),
                        exam_json["year"],
                        exam_json["semester"],
                        exam_json.get("title", None),
                        exam_json["files"],
                        exam_json.get("course_name", None),
                        force=force, silent=True)
                    if exam:
                        count += 1
                except KeyError as e:
                    raise DatabaseError(f"Missing field for exam in batch data JSON: {e}")
            print(f"Successfully added {count} exams to database")

    def edit_exam(self, exam_id: Optional[int], course: Optional[str], author: Optional[str],
                  year: Optional[int], semester: Optional[str], title: Optional[str],
                  course_name: Optional[str], hashes: List[str], confirm: bool = False):
        try:
            exam = self.db.exams[exam_id]
        except KeyError:
            raise DatabaseError(f"Exam ID {exam_id} doesn't exist")

        new_exam = copy.copy(exam)
        if course is not None:
            try:
                course = Course.parse(course.lower())
            except ValueError:
                raise DatabaseError(f"Invalid course code '{course}'")
            new_exam.course = course
            if course not in self.db.course_names and course_name is None:
                raise DatabaseError("Expected course name for course that doesn't exist yet")
        elif course_name is not None:
            raise DatabaseError("Course name given without course code")

        if author is not None:
            author = author.strip()
            if not author:
                author = None
            new_exam.author = author

        if title is not None:
            title = title.strip()
            if not title:
                title = None
            new_exam.title = title

        if year is not None:
            if year > datetime.today().year:
                raise DatabaseError("Invalid exam year")
            new_exam.year = year

        if semester is not None:
            semester_num = SEMESTER_MAPPINGS.get(semester.lower(), None)
            if semester_num is None:
                raise DatabaseError(f"Invalid exam semester '{semester}'")
            new_exam.semester = ExamSemester(semester_num)

        if hashes is not None:
            for i, file_hash in enumerate(hashes):
                file_hash = file_hash.lower()
                found = 0
                for h in self.file_hashes.keys():
                    if h.startswith(file_hash):
                        hashes[i] = h
                        found += 1
                if found == 0:
                    raise DatabaseError(f"Hash doesn't exist in database '{file_hash}'")
                elif found > 1:
                    raise DatabaseError(f"Hash is ambiguous '{file_hash}'")
            new_exam.hashes = hashes

        # confirm
        if confirm:
            print(f"Old exam: {format_exam(exam)}")
            print(f"New exam: {format_exam(new_exam)}")
            if course_name is not None:
                if course in self.db.course_names:
                    print(f"Course name changes from '{self.db.course_names[course]}' "
                          f"to '{course_name}'")
                else:
                    print(f"New course name: '{course_name}'")
            if not ask_confirm("Edit exam in database?"):
                return

        # edit course name if needed
        if course_name is not None and course in self.db.course_names:
            self.db.course_names[course] = course_name

        # edit exam
        del self.db.exams[exam_id]
        self.db.add_exam(new_exam, course_name)

        # update hashes
        for h in exam.hashes:
            self.file_hashes[h] -= 1
        for h in new_exam.hashes:
            self._use_hash(h)

        print("Successfully edited exam in database.")

    def remove_exams(self, exam_ids: List[int], confirm: bool = False) -> None:
        exams = []
        for exam_id in exam_ids:
            exam = self.db.exams.get(exam_id, None)
            if not exam:
                raise DatabaseError(f"Exam ID {exam_id} is not in database")
            exams.append(exam)

        # print exams and confirm
        for exam in exams:
            print(format_exam(exam))
        if confirm and not ask_confirm("Delete these exams from the database?"):
            return

        # delete exams and update hashes
        for exam in exams:
            del self.db.exams[exam.id]
            for h in self.file_hashes:
                self.file_hashes[h] -= 1
        print(f"Successfully deleted {len(exams)} exams from the database")


    def hash_files(self, files: List[PathLike], silent: bool = False) -> List[str]:
        hashes = []
        for file in files:
            try:
                file_hash = self._hash_and_add_file(file)
                hashes.append(file_hash)
                if not silent:
                    print(f"{file_hash}: {file}")
            except IOError as e:
                raise DatabaseError(f"Error while hashing file '{file}': {e}") from e
        return hashes

    def list_exams(self, course: Optional[str], author: Optional[str],
                   year: Optional[int], semester: Optional[str],
                   show_hashes: bool = False) -> None:
        if course is not None:
            try:
                course = Course.parse(course)
            except ValueError:
                raise DatabaseError(f"Invalid course code '{course}'")
        if author is not None:
            author = unidecode.unidecode(author.strip().lower())
        if semester is not None:
            semester_num = SEMESTER_MAPPINGS.get(semester.lower(), None)
            if semester_num is None:
                raise DatabaseError(f"Invalid exam semester '{semester}'")
            else:
                semester = ExamSemester(semester_num)

        exams = list(filter(lambda e: (course is None or e.course == course) and
                                      (author is None or e.author is not None and
                                       author in unidecode.unidecode(e.author.lower())) and
                                      (year is None or e.year == year) and
                                      (semester is None or e.semester == semester),
                            self.db.exams.values()))
        exams.sort(key=lambda e: (e.course.canonical_name(), e.semester.value,
                                  e.year, e.title or "", e.id))
        for exam in exams:
            print(format_exam(exam, count_files=True, show_date_added=True))
            if show_hashes:
                for h in exam.hashes:
                    print(f"  {h}")
                print("--------------------------------------------")
        print(f"{len(exams)} exams found for query")

    def garbarge_collect(self) -> None:
        count = 0
        freed = 0
        removed_hashes = []
        for h, uses in self.file_hashes.items():
            if uses == 0:
                try:
                    path = self._get_file_for_hash(h)
                    freed += os.path.getsize(path)
                    os.remove(path)
                except IOError as e:
                    raise DatabaseError(f"Could not remove hash '{h}': {e}")
                removed_hashes.append(h)
                print(h)
                count += 1
        for h in removed_hashes:
            del self.file_hashes[h]
        print(f"Removed {count} hashes, freed {freed / 1048576:.1f} MB")

    def _hash_and_add_file(self, filename: PathLike) -> str:
        """
        Hash and add file to the database. File must be one of the accepted formats.
        The SHA-1 hash of the file is returned.

        :raises DatabaseError If file has invalid extension.
        :raises IOError If file doesn't exist or cannot be read.
        """
        filepath = Path(filename)
        if not filepath.exists():
            raise IOError("File doesn't exist")
        if filepath.suffix.lower() != FILE_EXTENSION:
            raise DatabaseError(f"File doesn't have {FILE_EXTENSION} extension")

        with open(filepath, "rb") as file:
            h = hashlib.sha1(file.read()).hexdigest()

            # copy file to database
            if h not in self.file_hashes:
                dst_path = self._get_file_for_hash(h)
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                if dst_path.exists():
                    raise DatabaseError("File for hash already exists")
                copyfile(filename, dst_path)
                self.file_hashes[h] = 0
            return h

    def _load_hashes(self):
        """Load hashes from database files."""
        # load all hashes
        hash_path = self.db.path / EXAM_DIR_NAME
        if hash_path.exists():
            for subdir in hash_path.iterdir():
                for file in subdir.iterdir():
                    if file.is_file() and file.suffix == FILE_EXTENSION and \
                            HASH_REGEX.match(file.stem):
                        self.file_hashes[file.stem] = 0

        # update use count from exam
        for exam in self.db.exams.values():
            for h in exam.hashes:
                self._use_hash(h)

    def _use_hash(self, h: str) -> None:
        """Increment use count for hash. Use count is needed for garbage collection."""
        if h not in self.file_hashes:
            raise DatabaseError(f"Hash not in database: {h}")
        self.file_hashes[h] += 1

    def _get_file_for_hash(self, h: str) -> Path:
        hash_path = self.db.path / EXAM_DIR_NAME / h[:EXAM_DIR_HASH_SUBDIV]
        return hash_path / f"{h}{FILE_EXTENSION}"
