import hashlib
import json
import os
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
        for e in self.db.exams.values():
            for h in e.hashes:
                self._add_hash(h)

    def add_exam(self, course: str, author: str, year: int, semester: str, title: str,
                 files: List[PathLike], course_name: str = None, date_added: date = None,
                 force: bool = False, silent: bool = False) -> Optional[Exam]:
        # basic input validation
        if author is not None:
            author = author.strip()
            if not author:
                print("WARNING: no author name provided")
                author = None
        if title is not None:
            title = title.strip()
            if not title:
                print("WARNING: no exam title provided")
                title = None
        if not isinstance(year, int) or year > datetime.today().year:
            raise DatabaseError("Invalid exam year")
        semester_num = SEMESTER_MAPPINGS.get(semester.lower(), None)
        if semester_num is None:
            raise DatabaseError(f"Invalid exam semester '{semester}'")
        if not files:
            raise DatabaseError("At least one file per exam is required")
        if not date_added:
            date_added = datetime.today()
        try:
            course = Course.parse(course.lower())
        except ValueError:
            raise DatabaseError(f"Invalid course code '{course}'")

        hashes = []
        exam = Exam(Exam.NO_ID, course, author, year, ExamSemester(semester_num),
                    title, date_added, hashes)

        # check if similar doesn't already exist
        if not force:
            for e in self.db.exams.values():
                if title is not None and e.title is not None and \
                        title.lower() == e.title.lower() and year == e.year and course == e.course:
                    # exam has same title, same year, same course: most likely the same exam
                    print(f"Duplicate exam? {format_exam(exam, count_files=False)}. "
                          f"Use --force to override check.")
                    return None

        # hash and add files
        for file in files:
            try:
                hashes.append(self._hash_and_add_file(file))
            except IOError as e:
                # error, cleanup added files
                for h in hashes:
                    self._remove_file(h)
                raise DatabaseError(f"Error while hashing file '{file}': {e}") from e

        try:
            self.db.add_exam(exam, course_name)
            print(format_exam(exam))
            if not silent:
                print("Successfully added exam to database")
            return exam
        except DatabaseError as e:
            # error, cleanup added files
            for h in hashes:
                self._remove_file(h)
            raise e

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
                except KeyError:
                    raise DatabaseError("Missing field for exam in batch data JSON")
            print(f"Successfully added {count} exams to database")

    def list_exams(self, course: str, author: str, year: int, semester: str) -> None:
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
        print(f"{len(exams)} exams found for query")

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
            self._add_hash(h)

            # copy file to database
            dst_path = self._get_file_for_hash(h)
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if not dst_path.exists():
                copyfile(filename, dst_path)
            return h

    def _remove_file(self, h: str):
        """Remove file from database. If hash is used only once, file is deleted.
        Otherwise file is kept for its other uses."""
        if h not in self.file_hashes:
            return

        self.file_hashes[h] -= 1
        if self.file_hashes == 0:
            # last use of hash, remove file
            del self.file_hashes[h]
            os.remove(self._get_file_for_hash(h))

    def _add_hash(self, h: str) -> None:
        if h not in self.file_hashes:
            self.file_hashes[h] = 1
        else:
            self.file_hashes[h] += 1

    def _get_file_for_hash(self, h: str) -> Path:
        hash_path = self.db.path / EXAM_DIR_NAME / h[:EXAM_DIR_HASH_SUBDIV]
        return hash_path / f"{h}{FILE_EXTENSION}"
