#!/usr/bin/env python3

import argparse

# command line arguments parser
from db import Database, DatabaseError
from dbhelper import DatabaseHelper

parser = argparse.ArgumentParser(description="Database helper for FSG exam bank.")
parser.add_argument(
    "--db", action="store", type=str, dest="db_path", default=".",
    help="Path to the database, default is current path")

subparsers = parser.add_subparsers(dest="command")

# add command
add_parser = subparsers.add_parser("add", help="Add exams to the database")
add_parser.add_argument(
    action="store", type=str, nargs="*", dest="input",
    help="PDF files to add to database. At least one is required.")
add_parser.add_argument(
    "-y", "--year", type=int, action="store", dest="year", default=None,
    help="Exam year")
add_parser.add_argument(
    "-s", "--semester", type=str, action="store", dest="semester",
    help="Exam semester (accepted values: W, S, F, A, E, H)")
add_parser.add_argument(
    "-c", "--course", type=str, action="store", dest="course", default=None,
    help="Exam course code (DDD-NNNN format, where D is the department and N the class number)")
add_parser.add_argument(
    "--course-name", type=str, action="store", dest="course_name", default=None,
    help="Full name of the course. Required if this is the first exam for the course.")
add_parser.add_argument(
    "-a", "--author", type=str, action="store", dest="author", default=None,
    help="Exam author name")
add_parser.add_argument(
    "-t", "--title", type=str, action="store", dest="title", default=None,
    help="Exam title or name")
add_parser.add_argument(
    "--batch", type=str, action="store", dest="batch", default=False,
    help="Raw JSON data to add exams in batch mode. The expected JSON structure is a list of "
         "objects with the all of the following fields: 'course', 'author', 'year', 'semester', "
         "'title', 'files'. The format is the same as otherwise expected by parameters."
         "Files is a list of PDF filenames for each exam.")
add_parser.add_argument(
    "-f", "--force", action="store_true", dest="force", default=False,
    help="Disable checks to skip operation if a similar exam already exists")

list_parser = subparsers.add_parser("list", help="List exams")
list_parser.add_argument(
    "-c", "--course", type=str, action="store", dest="course", default=None,
    help="Exam course code (DDD-NNNN format, where D is the department and N the class number)")
list_parser.add_argument(
    "-a", "--author", type=str, action="store", dest="author", default=None,
    help="Exam author name")
list_parser.add_argument(
    "-y", "--year", type=int, action="store", dest="year", default=None,
    help="Exam year")
list_parser.add_argument(
    "-s", "--semester", type=str, action="store", dest="semester", default=None,
    help="Exam semester (accepted values: W, S, F, A, E, H)")

rewrite_parser = subparsers.add_parser("rewrite", help="Read and rewrite database JSON files")


def main():
    args = parser.parse_args()

    # load database
    db = Database(args.db_path)
    try:
        db.load()
    except DatabaseError as e:
        print(f"Database error: {e.args[0]}")
        exit(1)

    # perform action
    helper = DatabaseHelper(db)
    try:
        if args.command == "add":
            if args.batch:
                helper.batch_add_exam(args.batch, force=args.force)
            else:
                helper.add_exam(args.course, args.author, args.year, args.semester, args.title,
                                args.input, args.course_name, force=args.force)
        elif args.command == "list":
            helper.list_exams(args.course, args.author, args.year, args.semester)
        elif args.command == "rewrite":
            # no-op, load then save database
            pass
    except DatabaseError as e:
        print(f"Database error: {e.args[0]}")
        exit(1)
    else:
        db.save()


if __name__ == '__main__':
    main()
