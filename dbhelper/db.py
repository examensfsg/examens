import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Any

DB_DIR_NAME = "db"
DB_ROOT_NAME = "root"

DB_EXAM_ID_FIELD = "id"
DB_EXAM_AUTHOR_FIELD = "a"
DB_EXAM_YEAR_FIELD = "y"
DB_EXAM_SEMESTER_FIELD = "s"
DB_EXAM_TITLE_FIELD = "t"
DB_EXAM_DATE_ADDED_FIELD = "d"
DB_EXAM_HASHES_FIELD = "h"

DATE_FORMAT = "%Y-%m-%d"

HASH_REGEX = re.compile(r"^[0-9a-f]{40}$")
COURSE_REGEX = re.compile(r"^([a-z]{3})-([0-9]{4})$")


class DatabaseError(RuntimeError):
    pass


@dataclass(unsafe_hash=True)
class Course:
    department: str
    number: int

    @staticmethod
    def parse(code: str) -> "Course":
        """Parse course code in the format DDD-NNNN
        where D is the department and N is the course number."""
        match = COURSE_REGEX.match(code)
        if not match:
            raise ValueError(f"Invalid course code '{code}'")
        return Course(match.group(1), int(match.group(2)))

    def canonical_name(self) -> str:
        return f"{self.department}-{self.number:0>4}"

    def __repr__(self) -> str:
        return self.canonical_name().upper()


class ExamSemester(Enum):
    WINTER = 0
    SUMMER = 1
    FALL = 2


@dataclass
class Exam:
    id: int
    course: Course
    author: Optional[str]
    year: int
    semester: ExamSemester
    title: Optional[str]
    date_added: Optional[date]
    hashes: List[str]

    NO_ID = 0


class Database:
    """Class representing the exam database."""
    path: Path
    exams: Dict[int, Exam]
    course_names: Dict[Course, str]
    last_id: int

    def __init__(self, path: str):
        self.path = Path(path)
        self.exams = {}
        self.course_names = {}
        self.last_id = 0

    def load(self) -> None:
        """Populate database from data contained at path."""
        self.exams = {}
        db_path = self.path / DB_DIR_NAME
        try:
            with open(db_path / f"{DB_ROOT_NAME}.json", "r") as db_root_file:
                root_json = json.load(db_root_file)
                courses_json = root_json.get("courses", None)
                if not isinstance(courses_json, dict):
                    raise DatabaseError("Invalid root database JSON")
                for code, name in courses_json.items():
                    self._load_course(code, name)
        except IOError:
            # file doesn't exist? ignore it.
            pass

    def _load_course(self, course_code: str, course_name: str) -> None:
        """Load single course to database from JSON course file."""
        db_path = self.path / DB_DIR_NAME
        try:
            course = Course.parse(course_code)
        except ValueError:
            raise DatabaseError(f"Invalid course code '{course_code}'")
        try:
            with open(db_path / f"{course_code}.json", "r") as course_file:
                course_json = json.load(course_file)
                self.add_course(course, course_name)
                for exam in course_json:
                    self._load_exam(course, exam)
        except IOError as e:
            raise DatabaseError(f"Error reading course JSON file {course_code}: {e}")

    def _load_exam(self, course: Course, exam_json: Any) -> None:
        """Load single exam in database from JSON representation."""
        exam_id_num = exam_json.get(DB_EXAM_ID_FIELD, None)
        if not isinstance(exam_id_num, int) or exam_id_num < 0 or exam_id_num == Exam.NO_ID:
            raise DatabaseError(f"Exam {course}/{exam_id_num} has invalid or missing ID")
        if exam_id_num in self.exams:
            raise DatabaseError(f"Database has duplicate exam ID {exam_id_num} (in {course})")
        exam_id = f"{course}/{exam_id_num}"

        # parse author
        author = exam_json.get(DB_EXAM_AUTHOR_FIELD, None)
        if author is not None and not isinstance(author, str):
            raise DatabaseError(f"Exam {exam_id} author is invalid")

        # parse year
        year = exam_json.get(DB_EXAM_YEAR_FIELD, None)
        if not isinstance(year, int):
            raise DatabaseError(f"Exam {exam_id} year is invalid or missing")

        # parse semester
        semester = exam_json.get(DB_EXAM_SEMESTER_FIELD, None)
        if not isinstance(semester, int) or not any([s.value == semester for s in ExamSemester]):
            raise DatabaseError(f"Exam {exam_id} semester is invalid or missing")
        semester = ExamSemester(semester)

        title = exam_json.get(DB_EXAM_TITLE_FIELD, None)
        if title is not None and not isinstance(title, str):
            raise DatabaseError(f"Exam {exam_id} title is invalid or missing")

        # parse added date
        try:
            date_str = exam_json.get(DB_EXAM_DATE_ADDED_FIELD, None)
            date_added: Optional[date] = None
            if date_str is not None:
                date_added = datetime.strptime(date_str, DATE_FORMAT)
        except ValueError:
            raise DatabaseError(f"Exam {exam_id} has invalid added date")

        # parse file hashes
        hashes = exam_json.get(DB_EXAM_HASHES_FIELD, None)
        if not isinstance(hashes, list) or \
                any([not isinstance(h, str) or not HASH_REGEX.match(h) for h in hashes]):
            raise DatabaseError(f"Exam {exam_id} has invalid file hashes")

        # create and add exam
        exam = Exam(exam_id_num, course, author, year, semester, title, date_added, hashes)
        self.add_exam(exam)

    def add_exam(self, exam: Exam, course_name: str = None):
        """Add exam to database."""
        exam_id = "" if exam.id == Exam.NO_ID else f" ({exam.course}/{exam.id})"
        if exam.author is not None and not exam.author.strip():
            raise DatabaseError(f"Exam author cannot be blank{exam_id}")
        if exam.title is not None and not exam.title.strip():
            raise DatabaseError(f"Exam title cannot be blank{exam_id}")
        if exam.year > datetime.today().year:
            raise DatabaseError(f"Exam year is in the future{exam_id}")
        if exam.date_added > datetime.today():
            raise DatabaseError(f"Exam added date is in the future{exam_id}")
        if not exam.hashes:
            raise DatabaseError(f"Exam must have at least one hashed file{exam_id}")

        if exam.id == Exam.NO_ID:
            self.last_id += 1
            exam.id = self.last_id
        elif exam.id in self.exams:
            raise DatabaseError("Exam ID already exists in database")
        elif exam.id > self.last_id:
            self.last_id = exam.id

        if exam.course not in self.course_names:
            if course_name is None:
                raise DatabaseError(f"First exam for course {exam.course}, course name expected")
            self.add_course(exam.course, course_name)

        self.exams[exam.id] = exam

    def add_course(self, course: Course, name: str) -> None:
        if not name.strip():
            raise DatabaseError("Course name cannot be blank")
        self.course_names[course] = name

    def save(self):
        """Save database as JSON files."""
        # group exams by course
        course_exams: Dict[Course, List[Exam]] = {}
        for e in self.exams.values():
            if e.course not in course_exams:
                course_exams[e.course] = []
            course_exams[e.course].append(e)

        # save root database JSON
        db_path = self.path / DB_DIR_NAME
        db_path.mkdir(parents=True, exist_ok=True)
        with open(db_path / f"{DB_ROOT_NAME}.json", "w") as db_root_file:
            root_json = {}
            courses = {}
            for course, name in self.course_names.items():
                cname = course.canonical_name()
                if course in course_exams:
                    courses[cname] = name
                else:
                    # no exams for course, delete json file if it exists
                    os.remove(db_path / f"{cname}.json")
            root_json["courses"] = courses
            root_json["exam_count"] = len(self.exams)

            json.dump(root_json, db_root_file, separators=(',', ':'), ensure_ascii=False)

        # save JSON file per course
        for course, exams in course_exams.items():
            with open(db_path / f"{course.canonical_name()}.json", "w") as course_file:
                exams_json = []
                for e in exams:
                    exam_json = {DB_EXAM_ID_FIELD: e.id}
                    if e.author:
                        exam_json[DB_EXAM_AUTHOR_FIELD] = e.author
                    exam_json[DB_EXAM_YEAR_FIELD] = e.year
                    exam_json[DB_EXAM_SEMESTER_FIELD] = e.semester.value
                    if e.title:
                        exam_json[DB_EXAM_TITLE_FIELD] = e.title
                    if e.date_added:
                        exam_json[DB_EXAM_DATE_ADDED_FIELD] = e.date_added.strftime(DATE_FORMAT)
                    exam_json[DB_EXAM_HASHES_FIELD] = e.hashes
                    exams_json.append(exam_json)
                json.dump(exams_json, course_file, separators=(',', ':'), ensure_ascii=False)

    def __repr__(self) -> str:
        return f"Database({len(self.exams)} exams)"
