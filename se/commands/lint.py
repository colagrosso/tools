"""
This module implements the `se lint` command.
"""

import argparse
from pathlib import Path

import regex
from rich import box
from rich.console import Console
from rich.table import Table

import se
from se.se_epub import SeEpub

def lint() -> int:
	"""
	Entry point for `se lint`
	"""

	parser = argparse.ArgumentParser(description="Check for various Standard Ebooks style errors.")
	parser.add_argument("-n", "--no-colors", dest="colors", action="store_false", help="do not use colored output")
	parser.add_argument("-p", "--plain", action="store_true", help="print plain text output, without tables or colors")
	parser.add_argument("-s", "--skip-lint-ignore", action="store_true", help="ignore rules in se-lint-ignore.xml file")
	parser.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
	parser.add_argument("-w", "--wrap", metavar="INTEGER", type=se.is_positive_integer, default=None, help="force lines to wrap at this number of columns instead of auto-wrapping")
	parser.add_argument("directories", metavar="DIRECTORY", nargs="+", help="a Standard Ebooks source directory")
	args = parser.parse_args()

	called_from_parallel = se.is_called_from_parallel()
	first_output = True
	return_code = 0
	console = Console(highlight=False) # Syntax highlighting will do weird things when printing paths

	for directory in args.directories:
		directory = Path(directory).resolve()
		messages = []
		exception = None
		table_data = []
		has_output = False

		try:
			se_epub = SeEpub(directory)
			messages = se_epub.lint(args.skip_lint_ignore)
		except se.SeException as ex:
			exception = ex
			if len(args.directories) > 1:
				return_code = se.LintFailedException.code
			else:
				return_code = ex.code

		# Print a separator newline if more than one table is printed
		if not first_output and (args.verbose or messages or exception):
			print("")
		elif first_output:
			first_output = False

		# Print the table header
		if ((len(args.directories) > 1 or called_from_parallel) and (messages or exception)) or args.verbose:
			has_output = True
			if args.plain:
				print(directory)
			else:
				console.print(f"[reverse]{directory}[/reverse]")

		if exception:
			has_output = True
			se.print_error(exception)

		# Print the tables
		if messages:
			has_output = True
			return_code = se.LintFailedException.code

			if args.plain:
				for message in messages:
					label = "Manual Review:"

					if message.message_type == se.MESSAGE_TYPE_ERROR:
						label = "Error:"

					print(f"{message.code} {label} {message.filename} {message.text}")

					if message.submessages:
						for submessage in message.submessages:
							print(f"\t{submessage}")
			else:
				for message in messages:
					alert = "Manual Review"

					if message.message_type == se.MESSAGE_TYPE_ERROR:
						alert = "Error"

					message_text = message.text

					if args.colors:
						if message.message_type == se.MESSAGE_TYPE_ERROR:
							alert = f"[bright_red]{alert}[/bright_red]"
						else:
							alert = f"[bright_yellow]{alert}[/bright_yellow]"

						# By convention, any text within the message text that is surrounded in backticks
						# is rendered in blue
						message_text = regex.sub(r"`(.+?)`", r"[bright_blue]\1[/bright_blue]", message_text)

					table_data.append([message.code, alert, message.filename, message_text])

					if message.submessages:
						for submessage in message.submessages:
							table_data.append([" ", " ", "→", f"{submessage}"])

				table = Table(show_header=True, header_style="bold", show_lines=True, width=args.wrap)
				table.add_column("Code", style="dim" if args.colors else None, width=5, no_wrap=True)
				table.add_column("Severity", no_wrap=True)
				table.add_column("File", no_wrap=True)
				table.add_column("Message")

				for row in table_data:
					table.add_row(row[0], row[1], row[2], row[3])

				console.print(table)

		if args.verbose and not messages and not exception:
			if args.plain:
				print("OK")
			else:
				table = Table(show_header=False, box=box.SQUARE)
				table.add_column("", style="white on green4 bold" if args.colors else None)
				table.add_row("OK")
				console.print(table)

		# Print a newline if we're called from parallel and we just printed something, to
		# better visually separate output blocks
		if called_from_parallel and has_output:
			print("")

	return return_code
