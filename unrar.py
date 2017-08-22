#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys

parser = argparse.ArgumentParser(description='Extract multipart rar archives while deleting finished parts to save disk space')
parser.add_argument('-p', '--password', dest='password', help='password for extraction')
#parser.add_argument('--unsafe', help='delete finished archives immediately, instead of waiting for the current file to be finished', action='store_true')
parser.add_argument('-v', '--verbose', help='increase output verbosity', action='store_true')
parser.add_argument('archive', help='Archive filepath')
args = parser.parse_args()

if args.password is None:
	command = ['unrar', 'x', '-p-', args.archive]
else:
	command = ['unrar', 'x', '-p' + args.password, args.archive]

# https://stackoverflow.com/a/5980173
verboseprint = print if args.verbose else lambda *a, **k: None

# Directly get the string matched by a regex group (or None)
def get_regex_group(pattern, string, group = 1):
	matches = re.search(pattern, string)
	if matches is None:
		return None
	else:
		return matches.group(group)

finished_archives = []
current_archive = None
current_file = None
finished_file = None

# Call unrar binary
process = subprocess.Popen(command, stdout=subprocess.PIPE)

# Iterate over unrar output to get current/finisdhed files and archives
for raw_line in iter(process.stdout.readline, b''):
	line = raw_line.decode(sys.stdout.encoding).strip()

	# Check free diskspace and quit if <1GB
	statvfs = os.statvfs(os.path.abspath(current_file if current_file is not None else args.archive))
	if statvfs.f_frsize * statvfs.f_bavail < 1e9:
		print('ERROR: Hard drive full! Aborting...')
		process.terminate()
		sys.exit(1)

	# Only search non-empty lines
	if line == '':
		continue

	# Print 'raw' unrar output if verbose is set
	verboseprint('unrar: "%s"' % line)

	# Get current archive, unrar output should look like:
	# Extracting from <file>
	# if current archive switches, the old one can be deleted after the current file is finished
	current_archive_match = get_regex_group(r'^\s*Extracting\s+from\s+(.*?)$', line)
	if current_archive_match is not None and current_archive_match != current_archive:
		if current_archive is not None:
			finished_archives.append(current_archive)
		current_archive = current_archive_match
		print('Extracting from {}'.format(current_archive))
		verboseprint('Finished parts: {}'.format(', '.join(str(p) for p in finished_archives)))

	# Get current_file, unrar output should look like:
	# Extracting|...  <file>   n%
	# use for disk space check and printing information
	current_file_match = get_regex_group(r'^\s*(?:Extracting|\.+)\s+(.*?)(?:(?:\s|[\b])+\d+%)+(?:\s|[\b])*$', line)
	if current_file_match is not None and current_file_match != current_file:
		current_file = current_file_match
		print('Extracting {}'.format(current_file))

	# Get finished files, unrar output should look like:
	# Extracting|...  <file>  OK
	# if there are elements in finished_archives they can be deleted now
	finished_file_match = get_regex_group(r'^\s*(?:Extracting|\.+)+\s+(.*?)(?:(?:\s|[\b])+\d+%)*(?:\s|[\b])*OK\s*$', line)
	if finished_file_match is not None:
		finished_file = finished_file_match
		print('Finished extracting {}'.format(finished_file))
		if finished_archives:
			print('Deleting parts: {}'.format(', '.join(str(p) for p in finished_archives)))
			for file in finished_archives:
				os.remove(file)
			finished_archives = []
		else:
			verboseprint('Nothing to delete')

finished_archives.append(current_archive)
print('Extraction finished')
print('Deleting remaining parts: {}'.format(', '.join(str(p) for p in finished_archives)))
for file in finished_archives:
	os.remove(file)
